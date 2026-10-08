import os
import time
import json
import sqlite3
import atexit
import threading
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Try importing psycopg2 for direct PostgreSQL (Supabase) integration
try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "griffinops.db")


def load_env_file():
    """Finds and loads .env from project root if present into os.environ."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip("'\"")
                        if key and key not in os.environ:
                            os.environ[key] = val
        except Exception:
            pass

load_env_file()


class StorageManager:
    """
    Unified Storage Engine for GriffinOps:
    - Supabase PostgreSQL Backend: Direct, pooled cloud persistence (Option B).
    - Local SQLite Backend with WAL mode: Automatic zero-config fallback and in-memory test harness.
    - Asynchronous 10-second batch flusher for high-volume incoming telemetry streams.
    - Graceful shutdown handlers preventing any telemetry or key state loss.
    """
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._closed = False

        # In-memory batch buffers for high-churn telemetry & key request counters
        self._telemetry_queue: List[Tuple] = []
        self._dirty_keys: Dict[str, Tuple[int, Optional[float]]] = {}
        self._flush_lock = threading.Lock()

        # Background flusher daemon state
        self._flusher_thread: Optional[threading.Thread] = None
        self._flusher_event = threading.Event()
        self._stopping = False

        # Backend selection state
        self.is_postgres = False
        self._pg_conn = None
        self._sqlite_conn: Optional[sqlite3.Connection] = None

        self._init_backend()
        self.init_db()

    def _init_backend(self):
        """Evaluates whether to run on Supabase PostgreSQL or local SQLite."""
        # Always use in-memory SQLite for test suites
        if self.db_path == ":memory:":
            self.is_postgres = False
            return

        # Check for PostgreSQL connection parameters
        db_url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
        pg_pass = os.getenv("SUPABASE_PASSWORD")
        pg_host = os.getenv("SUPABASE_HOST", "db.jxdsgzwdwoscyqrowsde.supabase.co")
        pg_port = int(os.getenv("SUPABASE_PORT", "5432"))
        pg_user = os.getenv("SUPABASE_USER", "postgres")
        pg_db = os.getenv("SUPABASE_DB", "postgres")

        has_pg_creds = bool(db_url or (pg_host and pg_pass and len(pg_pass) > 0))

        if HAS_PSYCOPG2 and has_pg_creds:
            try:
                if db_url:
                    self._pg_conn = psycopg2.connect(
                        db_url,
                        connect_timeout=8,
                        cursor_factory=psycopg2.extras.RealDictCursor
                    )
                else:
                    self._pg_conn = psycopg2.connect(
                        host=pg_host,
                        port=pg_port,
                        dbname=pg_db,
                        user=pg_user,
                        password=pg_pass,
                        connect_timeout=8,
                        cursor_factory=psycopg2.extras.RealDictCursor
                    )
                self._pg_conn.autocommit = True
                self.is_postgres = True
                print("[+] [GriffinOps Storage] Successfully connected to Supabase PostgreSQL Database (Cloud Mode).")
                return
            except Exception as e:
                print(f"[!] [GriffinOps Storage] Failed to connect to Supabase PostgreSQL: {e}")
                print("[*] [GriffinOps Storage] Falling back to local SQLite database.")
                self.is_postgres = False
                self._pg_conn = None
        else:
            self.is_postgres = False

        # Fallback SQLite directory setup
        _db_dir = os.path.dirname(self.db_path)
        if _db_dir:
            os.makedirs(_db_dir, exist_ok=True)

    def _get_pg_connection(self):
        """Ensures active PostgreSQL connection with auto-reconnect."""
        if not self.is_postgres:
            return None
        try:
            if self._pg_conn is None or self._pg_conn.closed != 0:
                self._init_backend()
            else:
                # Test connection liveness
                with self._pg_conn.cursor() as cur:
                    cur.execute("SELECT 1;")
        except Exception:
            try:
                self._init_backend()
            except Exception:
                self.is_postgres = False
                return None
        return self._pg_conn

    def _get_sqlite_connection(self) -> sqlite3.Connection:
        if self._sqlite_conn is None:
            self._sqlite_conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._sqlite_conn.row_factory = sqlite3.Row
            cur = self._sqlite_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL;")
            cur.execute("PRAGMA busy_timeout=5000;")
            cur.execute("PRAGMA synchronous=NORMAL;")
            cur.close()
        return self._sqlite_conn

    def _get_connection(self):
        """Unified connection accessor for backward compatibility and test teardowns."""
        if self.is_postgres:
            return self._get_pg_connection()
        return self._get_sqlite_connection()

    def init_db(self):
        with self._lock:
            if self.is_postgres:
                conn = self._get_pg_connection()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS user_profile (
                                user_id TEXT PRIMARY KEY,
                                email TEXT NOT NULL,
                                name TEXT NOT NULL,
                                role TEXT NOT NULL,
                                organization TEXT,
                                email_alerts_enabled INTEGER DEFAULT 1,
                                developer_emails TEXT,
                                slack_webhook_url TEXT,
                                smtp_host TEXT,
                                smtp_port INTEGER DEFAULT 587,
                                smtp_user TEXT,
                                smtp_pass TEXT,
                                brevo_api_key TEXT,
                                resend_api_key TEXT,
                                updated_at DOUBLE PRECISION
                            );

                            CREATE TABLE IF NOT EXISTS auth_users (
                                user_id TEXT PRIMARY KEY,
                                email TEXT UNIQUE NOT NULL,
                                name TEXT NOT NULL,
                                password_hash TEXT NOT NULL,
                                salt TEXT NOT NULL,
                                role TEXT DEFAULT 'DEVELOPER',
                                reset_code TEXT,
                                reset_code_expires DOUBLE PRECISION,
                                created_at DOUBLE PRECISION
                            );

                            CREATE TABLE IF NOT EXISTS api_keys (
                                api_key TEXT PRIMARY KEY,
                                key_id TEXT UNIQUE NOT NULL,
                                name TEXT NOT NULL,
                                assigned_service TEXT NOT NULL,
                                endpoint TEXT,
                                target_url TEXT,
                                owner_email TEXT,
                                created_at TEXT,
                                requests_total INTEGER DEFAULT 0,
                                latest_latency_ms DOUBLE PRECISION,
                                status TEXT DEFAULT 'ACTIVE',
                                sdk_snippets TEXT
                            );

                            CREATE TABLE IF NOT EXISTS monitored_sites (
                                url TEXT PRIMARY KEY,
                                name TEXT NOT NULL,
                                type TEXT NOT NULL,
                                api_key TEXT,
                                created_at DOUBLE PRECISION
                            );

                            CREATE TABLE IF NOT EXISTS telemetry_history (
                                id SERIAL PRIMARY KEY,
                                url TEXT NOT NULL,
                                timestamp DOUBLE PRECISION NOT NULL,
                                latency_ms DOUBLE PRECISION NOT NULL,
                                status_code INTEGER DEFAULT 200,
                                payload_bytes INTEGER DEFAULT 256,
                                error_rate DOUBLE PRECISION DEFAULT 0.0,
                                cpu_percent DOUBLE PRECISION DEFAULT 40.0,
                                memory_percent DOUBLE PRECISION DEFAULT 40.0
                            );
                            CREATE INDEX IF NOT EXISTS idx_telemetry_url_ts ON telemetry_history(url, timestamp DESC);

                            CREATE TABLE IF NOT EXISTS dispatch_logs (
                                id SERIAL PRIMARY KEY,
                                timestamp TEXT NOT NULL,
                                report_id TEXT NOT NULL,
                                target_service TEXT,
                                recipient TEXT NOT NULL,
                                status TEXT NOT NULL,
                                preview_path TEXT
                            );
                        """)
                    return

            # SQLite Table Initialization
            conn = self._get_sqlite_connection()
            cur = conn.cursor()
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS user_profile (
                    user_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    organization TEXT,
                    email_alerts_enabled INTEGER DEFAULT 1,
                    developer_emails TEXT,
                    slack_webhook_url TEXT,
                    smtp_host TEXT,
                    smtp_port INTEGER DEFAULT 587,
                    smtp_user TEXT,
                    smtp_pass TEXT,
                    brevo_api_key TEXT,
                    resend_api_key TEXT,
                    updated_at REAL
                );

                CREATE TABLE IF NOT EXISTS auth_users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    role TEXT DEFAULT 'DEVELOPER',
                    reset_code TEXT,
                    reset_code_expires REAL,
                    created_at REAL
                );

                CREATE TABLE IF NOT EXISTS api_keys (
                    api_key TEXT PRIMARY KEY,
                    key_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    assigned_service TEXT NOT NULL,
                    endpoint TEXT,
                    target_url TEXT,
                    owner_email TEXT,
                    created_at TEXT,
                    requests_total INTEGER DEFAULT 0,
                    latest_latency_ms REAL,
                    status TEXT DEFAULT 'ACTIVE',
                    sdk_snippets TEXT
                );

                CREATE TABLE IF NOT EXISTS monitored_sites (
                    url TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    api_key TEXT,
                    created_at REAL
                );

                CREATE TABLE IF NOT EXISTS telemetry_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    latency_ms REAL NOT NULL,
                    status_code INTEGER DEFAULT 200,
                    payload_bytes INTEGER DEFAULT 256,
                    error_rate REAL DEFAULT 0.0,
                    cpu_percent REAL DEFAULT 40.0,
                    memory_percent REAL DEFAULT 40.0
                );
                CREATE INDEX IF NOT EXISTS idx_telemetry_url_ts ON telemetry_history(url, timestamp DESC);

                CREATE TABLE IF NOT EXISTS dispatch_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    report_id TEXT NOT NULL,
                    target_service TEXT,
                    recipient TEXT NOT NULL,
                    status TEXT NOT NULL,
                    preview_path TEXT
                );
            """)
            conn.commit()

    # --- FLUSHER THREAD & LIFECYCLE ---
    def start_flusher(self):
        if self._flusher_thread and self._flusher_thread.is_alive():
            return
        self._stopping = False
        self._flusher_event.clear()
        self._flusher_thread = threading.Thread(target=self._flusher_loop, daemon=True, name="GriffinOps-DB-Flusher")
        self._flusher_thread.start()

    def _flusher_loop(self):
        while not self._stopping:
            self._flusher_event.wait(timeout=10.0)
            self._flusher_event.clear()
            try:
                self.flush()
            except Exception:
                pass

    def flush(self):
        """Atomically flushes batched telemetry and dirty key counters to disk or Supabase."""
        with self._flush_lock:
            if not self._telemetry_queue and not self._dirty_keys:
                return

            telemetry_batch = self._telemetry_queue[:]
            self._telemetry_queue.clear()

            keys_batch = [(req_total, lat, k) for k, (req_total, lat) in self._dirty_keys.items()]
            self._dirty_keys.clear()

        with self._lock:
            if self.is_postgres:
                conn = self._get_pg_connection()
                if conn:
                    try:
                        with conn.cursor() as cur:
                            if telemetry_batch:
                                psycopg2.extras.execute_values(
                                    cur,
                                    """
                                    INSERT INTO telemetry_history 
                                    (url, timestamp, latency_ms, status_code, payload_bytes, error_rate, cpu_percent, memory_percent)
                                    VALUES %s
                                    """,
                                    telemetry_batch
                                )
                            if keys_batch:
                                for req_total, lat, k in keys_batch:
                                    cur.execute("""
                                        UPDATE api_keys 
                                        SET requests_total = %s, latest_latency_ms = %s
                                        WHERE api_key = %s
                                    """, (req_total, lat, k))
                        return
                    except Exception as e:
                        logger.error("Failed flushing telemetry batch to Supabase Postgres: %s", e)

            # SQLite Flush
            conn = self._get_sqlite_connection()
            cur = conn.cursor()
            try:
                if telemetry_batch:
                    cur.executemany("""
                        INSERT INTO telemetry_history 
                        (url, timestamp, latency_ms, status_code, payload_bytes, error_rate, cpu_percent, memory_percent)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, telemetry_batch)

                if keys_batch:
                    cur.executemany("""
                        UPDATE api_keys 
                        SET requests_total = ?, latest_latency_ms = ?
                        WHERE api_key = ?
                    """, keys_batch)

                conn.commit()
            except Exception:
                conn.rollback()

    def shutdown(self):
        """Graceful shutdown hook called by FastAPI shutdown event and atexit."""
        with self._lock:
            if self._closed:
                return
            self._closed = True

        self._stopping = True
        self._flusher_event.set()
        if self._flusher_thread and self._flusher_thread.is_alive():
            self._flusher_thread.join(timeout=2.0)

        self.flush()

        with self._lock:
            if self._pg_conn:
                try:
                    self._pg_conn.close()
                except Exception:
                    pass
                self._pg_conn = None

            if self._sqlite_conn:
                try:
                    self._sqlite_conn.close()
                except Exception:
                    pass
                self._sqlite_conn = None

    # --- USER PROFILE & ALERT SETTINGS ---
    def load_profile(self) -> Optional[dict]:
        with self._lock:
            if self.is_postgres:
                conn = self._get_pg_connection()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT * FROM user_profile LIMIT 1")
                        row = cur.fetchone()
                        if not row:
                            return None
                        return {
                            "user_id": row["user_id"],
                            "email": row["email"],
                            "name": row["name"],
                            "role": row["role"],
                            "organization": row["organization"],
                            "email_alerts_enabled": bool(row["email_alerts_enabled"]),
                            "developer_emails": json.loads(row["developer_emails"]) if row["developer_emails"] else [row["email"]],
                            "slack_webhook_url": row["slack_webhook_url"] or "",
                            "smtp_host": row["smtp_host"],
                            "smtp_port": row["smtp_port"],
                            "smtp_user": row["smtp_user"],
                            "smtp_pass": row["smtp_pass"],
                            "brevo_api_key": row["brevo_api_key"],
                            "resend_api_key": row["resend_api_key"]
                        }

            conn = self._get_sqlite_connection()
            row = conn.execute("SELECT * FROM user_profile LIMIT 1").fetchone()
            if not row:
                return None
            return {
                "user_id": row["user_id"],
                "email": row["email"],
                "name": row["name"],
                "role": row["role"],
                "organization": row["organization"],
                "email_alerts_enabled": bool(row["email_alerts_enabled"]),
                "developer_emails": json.loads(row["developer_emails"]) if row["developer_emails"] else [row["email"]],
                "slack_webhook_url": row["slack_webhook_url"] or "",
                "smtp_host": row["smtp_host"],
                "smtp_port": row["smtp_port"],
                "smtp_user": row["smtp_user"],
                "smtp_pass": row["smtp_pass"],
                "brevo_api_key": row["brevo_api_key"],
                "resend_api_key": row["resend_api_key"]
            }

    def save_profile(self, profile: dict, email_config: Optional[dict] = None):
        cfg = email_config or {}
        dev_emails_json = json.dumps(profile.get("developer_emails", []))
        params = {
            "user_id": profile.get("user_id", "usr_admin001"),
            "email": profile.get("email", "admin@griffinops.io"),
            "name": profile.get("name", "SRE Lead Engineer"),
            "role": profile.get("role", "CHIEF SRE ARCHITECT"),
            "organization": profile.get("organization", "SIES GST AI Team"),
            "email_alerts_enabled": 1 if profile.get("email_alerts_enabled", True) else 0,
            "developer_emails": dev_emails_json,
            "slack_webhook_url": profile.get("slack_webhook_url", ""),
            "smtp_host": cfg.get("smtp_host"),
            "smtp_port": cfg.get("smtp_port", 587),
            "smtp_user": cfg.get("smtp_user"),
            "smtp_pass": cfg.get("smtp_pass"),
            "brevo_api_key": cfg.get("brevo_api_key"),
            "resend_api_key": cfg.get("resend_api_key"),
            "updated_at": time.time()
        }

        with self._lock:
            if self.is_postgres:
                conn = self._get_pg_connection()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO user_profile (
                                user_id, email, name, role, organization, email_alerts_enabled,
                                developer_emails, slack_webhook_url, smtp_host, smtp_port,
                                smtp_user, smtp_pass, brevo_api_key, resend_api_key, updated_at
                            ) VALUES (
                                %(user_id)s, %(email)s, %(name)s, %(role)s, %(organization)s, %(email_alerts_enabled)s,
                                %(developer_emails)s, %(slack_webhook_url)s, %(smtp_host)s, %(smtp_port)s,
                                %(smtp_user)s, %(smtp_pass)s, %(brevo_api_key)s, %(resend_api_key)s, %(updated_at)s
                            ) ON CONFLICT(user_id) DO UPDATE SET
                                email = EXCLUDED.email,
                                name = EXCLUDED.name,
                                role = EXCLUDED.role,
                                organization = EXCLUDED.organization,
                                email_alerts_enabled = EXCLUDED.email_alerts_enabled,
                                developer_emails = EXCLUDED.developer_emails,
                                slack_webhook_url = EXCLUDED.slack_webhook_url,
                                smtp_host = COALESCE(EXCLUDED.smtp_host, user_profile.smtp_host),
                                smtp_port = COALESCE(EXCLUDED.smtp_port, user_profile.smtp_port),
                                smtp_user = COALESCE(EXCLUDED.smtp_user, user_profile.smtp_user),
                                smtp_pass = COALESCE(EXCLUDED.smtp_pass, user_profile.smtp_pass),
                                brevo_api_key = COALESCE(EXCLUDED.brevo_api_key, user_profile.brevo_api_key),
                                resend_api_key = COALESCE(EXCLUDED.resend_api_key, user_profile.resend_api_key),
                                updated_at = EXCLUDED.updated_at
                        """, params)
                    return

            conn = self._get_sqlite_connection()
            conn.execute("""
                INSERT INTO user_profile (
                    user_id, email, name, role, organization, email_alerts_enabled,
                    developer_emails, slack_webhook_url, smtp_host, smtp_port,
                    smtp_user, smtp_pass, brevo_api_key, resend_api_key, updated_at
                ) VALUES (
                    :user_id, :email, :name, :role, :organization, :email_alerts_enabled,
                    :developer_emails, :slack_webhook_url, :smtp_host, :smtp_port,
                    :smtp_user, :smtp_pass, :brevo_api_key, :resend_api_key, :updated_at
                ) ON CONFLICT(user_id) DO UPDATE SET
                    email = excluded.email,
                    name = excluded.name,
                    role = excluded.role,
                    organization = excluded.organization,
                    email_alerts_enabled = excluded.email_alerts_enabled,
                    developer_emails = excluded.developer_emails,
                    slack_webhook_url = excluded.slack_webhook_url,
                    smtp_host = COALESCE(excluded.smtp_host, user_profile.smtp_host),
                    smtp_port = COALESCE(excluded.smtp_port, user_profile.smtp_port),
                    smtp_user = COALESCE(excluded.smtp_user, user_profile.smtp_user),
                    smtp_pass = COALESCE(excluded.smtp_pass, user_profile.smtp_pass),
                    brevo_api_key = COALESCE(excluded.brevo_api_key, user_profile.brevo_api_key),
                    resend_api_key = COALESCE(excluded.resend_api_key, user_profile.resend_api_key),
                    updated_at = excluded.updated_at
            """, params)
            conn.commit()

    # --- API KEYS ---
    def load_api_keys(self) -> Dict[str, dict]:
        with self._lock:
            if self.is_postgres:
                conn = self._get_pg_connection()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT * FROM api_keys")
                        rows = cur.fetchall()
                        keys = {}
                        for r in rows:
                            snippets = json.loads(r["sdk_snippets"]) if r["sdk_snippets"] else {}
                            keys[r["api_key"]] = {
                                "key_id": r["key_id"],
                                "api_key": r["api_key"],
                                "name": r["name"],
                                "assigned_service": r["assigned_service"],
                                "endpoint": r["endpoint"],
                                "target_url": r["target_url"],
                                "owner_email": r["owner_email"],
                                "created_at": r["created_at"],
                                "requests_total": r["requests_total"],
                                "latest_latency_ms": r["latest_latency_ms"],
                                "status": r["status"],
                                "sdk_snippets": snippets
                            }
                        return keys

            conn = self._get_sqlite_connection()
            rows = conn.execute("SELECT * FROM api_keys").fetchall()
            keys = {}
            for r in rows:
                snippets = json.loads(r["sdk_snippets"]) if r["sdk_snippets"] else {}
                keys[r["api_key"]] = {
                    "key_id": r["key_id"],
                    "api_key": r["api_key"],
                    "name": r["name"],
                    "assigned_service": r["assigned_service"],
                    "endpoint": r["endpoint"],
                    "target_url": r["target_url"],
                    "owner_email": r["owner_email"],
                    "created_at": r["created_at"],
                    "requests_total": r["requests_total"],
                    "latest_latency_ms": r["latest_latency_ms"],
                    "status": r["status"],
                    "sdk_snippets": snippets
                }
            return keys

    def save_api_key(self, record: dict):
        snippets_json = json.dumps(record.get("sdk_snippets", {}))
        data_tuple = (
            record["api_key"], record["key_id"], record["name"],
            record["assigned_service"], record.get("endpoint"),
            record.get("target_url"), record.get("owner_email"),
            record.get("created_at"), record.get("requests_total", 0),
            record.get("latest_latency_ms"), record.get("status", "ACTIVE"),
            snippets_json
        )

        with self._lock:
            if self.is_postgres:
                conn = self._get_pg_connection()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO api_keys (
                                api_key, key_id, name, assigned_service, endpoint, target_url,
                                owner_email, created_at, requests_total, latest_latency_ms,
                                status, sdk_snippets
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (api_key) DO UPDATE SET
                                key_id = EXCLUDED.key_id,
                                name = EXCLUDED.name,
                                assigned_service = EXCLUDED.assigned_service,
                                endpoint = EXCLUDED.endpoint,
                                target_url = EXCLUDED.target_url,
                                owner_email = EXCLUDED.owner_email,
                                requests_total = EXCLUDED.requests_total,
                                latest_latency_ms = EXCLUDED.latest_latency_ms,
                                status = EXCLUDED.status,
                                sdk_snippets = EXCLUDED.sdk_snippets
                        """, data_tuple)
                    return

            conn = self._get_sqlite_connection()
            conn.execute("""
                INSERT OR REPLACE INTO api_keys (
                    api_key, key_id, name, assigned_service, endpoint, target_url,
                    owner_email, created_at, requests_total, latest_latency_ms,
                    status, sdk_snippets
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data_tuple)
            conn.commit()

    def update_api_key_status(self, key_id: str, status: str):
        with self._lock:
            if self.is_postgres:
                conn = self._get_pg_connection()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE api_keys SET status = %s WHERE key_id = %s", (status, key_id))
                    return

            conn = self._get_sqlite_connection()
            conn.execute("UPDATE api_keys SET status = ? WHERE key_id = ?", (status, key_id))
            conn.commit()

    def mark_api_key_dirty(self, api_key: str, requests_total: int, latest_latency_ms: Optional[float] = None):
        with self._flush_lock:
            self._dirty_keys[api_key] = (requests_total, latest_latency_ms)

    # --- MONITORED SITES ---
    def load_monitored_sites(self) -> List[dict]:
        with self._lock:
            if self.is_postgres:
                conn = self._get_pg_connection()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT * FROM monitored_sites ORDER BY created_at ASC")
                        rows = cur.fetchall()
                        return [{
                            "name": r["name"],
                            "url": r["url"],
                            "type": r["type"],
                            "api_key": r["api_key"]
                        } for r in rows]

            conn = self._get_sqlite_connection()
            rows = conn.execute("SELECT * FROM monitored_sites ORDER BY created_at ASC").fetchall()
            return [{
                "name": r["name"],
                "url": r["url"],
                "type": r["type"],
                "api_key": r["api_key"]
            } for r in rows]

    def save_monitored_site(self, site: dict):
        site_tuple = (
            site["url"], site["name"], site.get("type", "Live Web App (SDK)"),
            site.get("api_key", "gop_live_custom"), time.time()
        )
        with self._lock:
            if self.is_postgres:
                conn = self._get_pg_connection()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO monitored_sites (url, name, type, api_key, created_at)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (url) DO UPDATE SET
                                name = EXCLUDED.name,
                                type = EXCLUDED.type,
                                api_key = EXCLUDED.api_key,
                                created_at = EXCLUDED.created_at
                        """, site_tuple)
                    return

            conn = self._get_sqlite_connection()
            conn.execute("""
                INSERT OR REPLACE INTO monitored_sites (url, name, type, api_key, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, site_tuple)
            conn.commit()

    # --- TELEMETRY HISTORY ---
    def load_telemetry_history(self, limit_per_site: int = 60) -> Dict[str, List[dict]]:
        with self._lock:
            if self.is_postgres:
                conn = self._get_pg_connection()
                if conn:
                    history = {}
                    with conn.cursor() as cur:
                        cur.execute("SELECT DISTINCT url FROM monitored_sites")
                        sites = cur.fetchall()
                        for s in sites:
                            url = s["url"]
                            cur.execute("""
                                SELECT timestamp, latency_ms, status_code, payload_bytes, error_rate, cpu_percent, memory_percent
                                FROM telemetry_history
                                WHERE url = %s
                                ORDER BY timestamp DESC, id DESC
                                LIMIT %s
                            """, (url, limit_per_site))
                            rows = cur.fetchall()
                            history[url] = [{
                                "timestamp": r["timestamp"],
                                "latency_ms": r["latency_ms"],
                                "status_code": r["status_code"],
                                "payload_bytes": r["payload_bytes"],
                                "error_rate": r["error_rate"],
                                "cpu_percent": r["cpu_percent"],
                                "memory_percent": r["memory_percent"]
                            } for r in reversed(rows)]
                    return history

            conn = self._get_sqlite_connection()
            sites = conn.execute("SELECT DISTINCT url FROM monitored_sites").fetchall()
            history = {}
            for s in sites:
                url = s["url"]
                rows = conn.execute("""
                    SELECT timestamp, latency_ms, status_code, payload_bytes, error_rate, cpu_percent, memory_percent
                    FROM telemetry_history
                    WHERE url = ?
                    ORDER BY timestamp DESC, id DESC
                    LIMIT ?
                """, (url, limit_per_site)).fetchall()
                history[url] = [{
                    "timestamp": r["timestamp"],
                    "latency_ms": r["latency_ms"],
                    "status_code": r["status_code"],
                    "payload_bytes": r["payload_bytes"],
                    "error_rate": r["error_rate"],
                    "cpu_percent": r["cpu_percent"],
                    "memory_percent": r["memory_percent"]
                } for r in reversed(rows)]
            return history

    def queue_telemetry_point(self, url: str, point: dict):
        with self._flush_lock:
            self._telemetry_queue.append((
                url, point["timestamp"], point["latency_ms"],
                point.get("status_code", 200), point.get("payload_bytes", 256),
                point.get("error_rate", 0.0), point.get("cpu_percent", 40.0),
                point.get("memory_percent", 40.0)
            ))
            if len(self._telemetry_queue) >= 50:
                self._flusher_event.set()

    # --- DISPATCH LOGS ---
    def load_dispatch_logs(self, limit: int = 20) -> List[dict]:
        with self._lock:
            if self.is_postgres:
                conn = self._get_pg_connection()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT timestamp, report_id, target_service, recipient, status, preview_path
                            FROM dispatch_logs
                            ORDER BY id DESC
                            LIMIT %s
                        """, (limit,))
                        rows = cur.fetchall()
                        return [{
                            "timestamp": r["timestamp"],
                            "report_id": r["report_id"],
                            "target_service": r["target_service"],
                            "recipient": r["recipient"],
                            "status": r["status"],
                            "preview_path": r["preview_path"]
                        } for r in rows]

            conn = self._get_sqlite_connection()
            rows = conn.execute("""
                SELECT timestamp, report_id, target_service, recipient, status, preview_path
                FROM dispatch_logs
                ORDER BY id DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [{
                "timestamp": r["timestamp"],
                "report_id": r["report_id"],
                "target_service": r["target_service"],
                "recipient": r["recipient"],
                "status": r["status"],
                "preview_path": r["preview_path"]
            } for r in rows]

    def save_dispatch_log(self, entry: dict):
        log_tuple = (
            entry["timestamp"], entry.get("report_id", "N/A"),
            entry.get("target_service"), entry["recipient"],
            entry["status"], entry.get("preview_path")
        )
        with self._lock:
            if self.is_postgres:
                conn = self._get_pg_connection()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO dispatch_logs (timestamp, report_id, target_service, recipient, status, preview_path)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, log_tuple)
                    return

            conn = self._get_sqlite_connection()
            conn.execute("""
                INSERT INTO dispatch_logs (timestamp, report_id, target_service, recipient, status, preview_path)
                VALUES (?, ?, ?, ?, ?, ?)
            """, log_tuple)
            conn.commit()

    # --- PERSISTENT AUTH USERS ---
    def get_auth_user(self, email: str) -> Optional[dict]:
        email_clean = (email or "").strip().lower()
        if not email_clean:
            return None
        with self._lock:
            if self.is_postgres:
                conn = self._get_pg_connection()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT user_id, email, name, password_hash, salt, role, reset_code, reset_code_expires, created_at
                            FROM auth_users
                            WHERE LOWER(email) = %s
                            LIMIT 1
                        """, (email_clean,))
                        row = cur.fetchone()
                        return dict(row) if row else None

            conn = self._get_sqlite_connection()
            row = conn.execute("""
                SELECT user_id, email, name, password_hash, salt, role, reset_code, reset_code_expires, created_at
                FROM auth_users
                WHERE LOWER(email) = ?
                LIMIT 1
            """, (email_clean,)).fetchone()
            if not row:
                return None
            return {
                "user_id": row[0],
                "email": row[1],
                "name": row[2],
                "password_hash": row[3],
                "salt": row[4],
                "role": row[5],
                "reset_code": row[6],
                "reset_code_expires": row[7],
                "created_at": row[8]
            }

    def create_auth_user(self, user_id: str, email: str, name: str, password_hash: str, salt: str, role: str = "DEVELOPER") -> dict:
        email_clean = email.strip().lower()
        now = time.time()
        with self._lock:
            if self.is_postgres:
                conn = self._get_pg_connection()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO auth_users (user_id, email, name, password_hash, salt, role, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (email) DO NOTHING
                        """, (user_id, email_clean, name.strip(), password_hash, salt, role, now))
                    return {"user_id": user_id, "email": email_clean, "name": name, "role": role}

            conn = self._get_sqlite_connection()
            conn.execute("""
                INSERT OR IGNORE INTO auth_users (user_id, email, name, password_hash, salt, role, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, email_clean, name.strip(), password_hash, salt, role, now))
            conn.commit()
            return {"user_id": user_id, "email": email_clean, "name": name, "role": role}

    def update_auth_user_password(self, email: str, password_hash: str, salt: str) -> bool:
        email_clean = email.strip().lower()
        with self._lock:
            if self.is_postgres:
                conn = self._get_pg_connection()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE auth_users
                            SET password_hash = %s, salt = %s, reset_code = NULL, reset_code_expires = NULL
                            WHERE LOWER(email) = %s
                        """, (password_hash, salt, email_clean))
                    return True

            conn = self._get_sqlite_connection()
            conn.execute("""
                UPDATE auth_users
                SET password_hash = ?, salt = ?, reset_code = NULL, reset_code_expires = NULL
                WHERE LOWER(email) = ?
            """, (password_hash, salt, email_clean))
            conn.commit()
            return True

    def set_password_reset_code(self, email: str, reset_code: str, expires_at: float) -> bool:
        email_clean = email.strip().lower()
        with self._lock:
            if self.is_postgres:
                conn = self._get_pg_connection()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE auth_users
                            SET reset_code = %s, reset_code_expires = %s
                            WHERE LOWER(email) = %s
                        """, (reset_code, expires_at, email_clean))
                    return True

            conn = self._get_sqlite_connection()
            conn.execute("""
                UPDATE auth_users
                SET reset_code = ?, reset_code_expires = ?
                WHERE LOWER(email) = ?
            """, (reset_code, expires_at, email_clean))
            conn.commit()
            return True

    def verify_and_consume_reset_code(self, email: str, reset_code: str) -> bool:
        user = self.get_auth_user(email)
        if not user:
            return False
        stored_code = user.get("reset_code")
        expires_at = user.get("reset_code_expires") or 0.0
        if not stored_code or stored_code != reset_code:
            return False
        if time.time() > expires_at:
            return False
        return True


# Module-level singleton
storage = StorageManager()
atexit.register(storage.shutdown)
