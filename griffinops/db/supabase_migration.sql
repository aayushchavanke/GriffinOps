-- ==============================================================================
-- GriffinOps Enterprise — Supabase PostgreSQL Schema Migration
-- Project: jxdsgzwdwoscyqrowsde.supabase.co
-- ==============================================================================

-- 1. SRE User Profiles & Notification Channels
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

-- 2. Monitored Microservices & Ingress Websites
CREATE TABLE IF NOT EXISTS monitored_sites (
    url TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    api_key TEXT,
    created_at DOUBLE PRECISION
);

-- 3. Developer Production API Keys & Integration Snippets
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

-- 4. High-Throughput Ingested Telemetry Time-Series
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

-- Index for fast time-series queries
CREATE INDEX IF NOT EXISTS idx_telemetry_url_ts ON telemetry_history(url, timestamp DESC);

-- 5. Autonomous Watchdog Alert Dispatch Audit Logs
CREATE TABLE IF NOT EXISTS dispatch_logs (
    id SERIAL PRIMARY KEY,
    timestamp TEXT NOT NULL,
    report_id TEXT NOT NULL,
    target_service TEXT,
    recipient TEXT NOT NULL,
    status TEXT NOT NULL,
    preview_path TEXT
);
