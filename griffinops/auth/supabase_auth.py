import os
import time
import requests
import secrets
import uuid
import re
from typing import Optional, Dict

from griffinops.auth.security import (
    hash_password,
    verify_password,
    create_session,
    get_session
)
from griffinops.db.storage import storage

def load_env_file():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    if key.strip() not in os.environ:
                        os.environ[key.strip()] = val.strip()

load_env_file()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://jxdsgzwdwoscyqrowsde.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

class SupabaseAuthEngine:
    """
    Robust Dual-Engine Authentication:
    - Multi-Tenant Cloud Supabase Auth (GoTrue REST API)
    - Persistent Local SQLite / PostgreSQL DB with salted PBKDF2 hashing
    - Safe error propagation (no silent auto-login bypasses)
    - Forgot Password & Reset Password workflows
    """
    def __init__(self):
        self.supabase_url = SUPABASE_URL.rstrip("/")
        self.supabase_key = SUPABASE_KEY.strip() if SUPABASE_KEY else ""
        self.is_supabase_configured = bool(
            self.supabase_url 
            and self.supabase_key 
            and not self.supabase_key.startswith("YOUR_")
            and len(self.supabase_key) > 20
        )
        self._ensure_seed_admin()

    def _ensure_seed_admin(self):
        """Ensures the default demo admin account is seeded for instant evaluation."""
        try:
            admin_user = storage.get_auth_user("admin@griffinops.io")
            if not admin_user:
                p_hash, salt = hash_password("admin123")
                storage.create_auth_user(
                    user_id="usr_admin001",
                    email="admin@griffinops.io",
                    name="SRE Lead Engineer",
                    password_hash=p_hash,
                    salt=salt,
                    role="CHIEF SRE ARCHITECT"
                )
        except Exception:
            pass

    def _validate_credentials(self, email: str, password: str, is_registration: bool = False):
        if not email or not email.strip():
            raise ValueError("Email address is required.")
        email_clean = email.strip()
        if not EMAIL_REGEX.match(email_clean):
            raise ValueError("Please provide a valid email address (e.g. user@company.com).")
        if not password or not password.strip():
            raise ValueError("Password is required.")
        if is_registration and len(password) < 6:
            raise ValueError("Password must be at least 6 characters long.")

    def register(self, email: str, password: str, name: str) -> dict:
        email_clean = (email or "").strip().lower()
        name_clean = (name or "").strip() or email_clean.split("@")[0].title()
        self._validate_credentials(email_clean, password, is_registration=True)

        # Check existing user in local/persistent store first
        existing_local = storage.get_auth_user(email_clean)
        if existing_local:
            raise ValueError("An account with this email address already exists. Please sign in.")

        if self.is_supabase_configured:
            url = f"{self.supabase_url}/auth/v1/signup"
            headers = {"apikey": self.supabase_key, "Content-Type": "application/json"}
            payload = {
                "email": email_clean,
                "password": password,
                "data": {"name": name_clean, "role": "DEVELOPER"}
            }
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=6.0)
                if resp.status_code in [200, 201]:
                    data = resp.json()
                    user_data = data.get("user", {})
                    # Supabase GoTrue returns empty identities array when user already exists (enumeration prevention)
                    identities = user_data.get("identities")
                    if identities is not None and len(identities) == 0:
                        raise ValueError("An account with this email address already exists. Please sign in.")

                    user_id = user_data.get("id") or f"usr_{uuid.uuid4().hex[:8]}"
                    p_hash, salt = hash_password(password)
                    storage.create_auth_user(user_id, email_clean, name_clean, p_hash, salt, "DEVELOPER")

                    return {
                        "status": "SUCCESS",
                        "mode": "SUPABASE",
                        "message": "Account created successfully via Supabase Auth. Please sign in.",
                        "user": {
                            "user_id": user_id,
                            "email": email_clean,
                            "name": name_clean,
                            "role": "DEVELOPER"
                        }
                    }
                else:
                    err_json = {}
                    try:
                        err_json = resp.json()
                    except Exception:
                        pass
                    msg = err_json.get("msg") or err_json.get("error_description") or err_json.get("message") or ""
                    if any(term in msg.lower() for term in ["already registered", "already exists", "user_already_exists"]):
                        raise ValueError("An account with this email address already exists. Please sign in.")
                    raise ValueError(msg or f"Supabase registration error (HTTP {resp.status_code}).")
            except requests.exceptions.RequestException as e:
                # Network or connection timeout
                raise ValueError(f"Unable to connect to Supabase Auth service: {str(e)}")

        # Persistent Local DB registration
        user_id = f"usr_{uuid.uuid4().hex[:8]}"
        p_hash, salt = hash_password(password)
        storage.create_auth_user(user_id, email_clean, name_clean, p_hash, salt, "DEVELOPER")

        return {
            "status": "SUCCESS",
            "mode": "LOCAL_DB",
            "message": "Account created successfully. Please sign in.",
            "user": {
                "user_id": user_id,
                "email": email_clean,
                "name": name_clean,
                "role": "DEVELOPER"
            }
        }

    def login(self, email: str, password: str) -> dict:
        email_clean = (email or "").strip().lower()
        self._validate_credentials(email_clean, password, is_registration=False)

        if self.is_supabase_configured:
            url = f"{self.supabase_url}/auth/v1/token?grant_type=password"
            headers = {"apikey": self.supabase_key, "Content-Type": "application/json"}
            payload = {"email": email_clean, "password": password}
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=6.0)
                if resp.status_code == 200:
                    data = resp.json()
                    token = data.get("access_token")
                    user_data = data.get("user", {})
                    user_name = user_data.get("user_metadata", {}).get("name", email_clean.split("@")[0].title())
                    user_role = user_data.get("user_metadata", {}).get("role", "DEVELOPER")
                    return {
                        "access_token": token,
                        "token_type": "bearer",
                        "mode": "SUPABASE",
                        "user": {
                            "user_id": user_data.get("id"),
                            "email": user_data.get("email", email_clean),
                            "name": user_name,
                            "role": user_role
                        }
                    }
                else:
                    err_json = {}
                    try:
                        err_json = resp.json()
                    except Exception:
                        pass
                    msg = err_json.get("error_description") or err_json.get("msg") or err_json.get("message") or ""
                    if "email not confirmed" in msg.lower():
                        raise ValueError("Email not confirmed yet. Please verify your email or sign in with verified credentials.")
                    
                    # If user is local seed admin, allow fallback check for local admin
                    if email_clean == "admin@griffinops.io":
                        local_admin = storage.get_auth_user("admin@griffinops.io")
                        if local_admin and verify_password(password, local_admin["password_hash"], local_admin.get("salt")):
                            token = create_session(local_admin["user_id"], local_admin["email"], local_admin["name"], local_admin["role"])
                            return {
                                "access_token": token,
                                "token_type": "bearer",
                                "mode": "LOCAL_DB",
                                "user": {
                                    "user_id": local_admin["user_id"],
                                    "email": local_admin["email"],
                                    "name": local_admin["name"],
                                    "role": local_admin["role"]
                                }
                            }
                    
                    raise ValueError("Invalid email or password.")
            except requests.exceptions.RequestException as e:
                # In case Supabase cloud is temporarily unreachable, check local store
                pass

        # Persistent Local DB verification
        user = storage.get_auth_user(email_clean)
        if not user:
            raise ValueError("Invalid email or password.")

        if not verify_password(password, user["password_hash"], user.get("salt")):
            raise ValueError("Invalid email or password.")

        token = create_session(user["user_id"], user["email"], user["name"], user["role"])
        return {
            "access_token": token,
            "token_type": "bearer",
            "mode": "LOCAL_DB",
            "user": {
                "user_id": user["user_id"],
                "email": user["email"],
                "name": user["name"],
                "role": user["role"]
            }
        }

    def forgot_password(self, email: str) -> dict:
        email_clean = (email or "").strip().lower()
        if not email_clean or not EMAIL_REGEX.match(email_clean):
            raise ValueError("Please provide a valid email address.")

        if self.is_supabase_configured:
            url = f"{self.supabase_url}/auth/v1/recover"
            headers = {"apikey": self.supabase_key, "Content-Type": "application/json"}
            try:
                resp = requests.post(url, json={"email": email_clean}, headers=headers, timeout=6.0)
                if resp.status_code in [200, 204]:
                    return {
                        "status": "SUCCESS",
                        "mode": "SUPABASE",
                        "message": f"Password recovery instructions have been sent to {email_clean} via Supabase Auth."
                    }
            except Exception:
                pass

        # Local DB reset flow
        user = storage.get_auth_user(email_clean)
        if not user:
            # Check if it exists; provide actionable feedback
            raise ValueError("No account found with this email address. Please create an account.")

        reset_code = f"{secrets.randbelow(900000) + 100000}"
        expires_at = time.time() + 900.0  # 15 minutes
        storage.set_password_reset_code(email_clean, reset_code, expires_at)

        return {
            "status": "SUCCESS",
            "mode": "LOCAL_DB",
            "reset_code": reset_code,
            "message": f"Password reset verification code generated for {email_clean}: {reset_code} (Valid for 15 minutes)."
        }

    def reset_password(self, email: str, reset_code: str, new_password: str) -> dict:
        email_clean = (email or "").strip().lower()
        code_clean = (reset_code or "").strip()
        new_pass = (new_password or "").strip()

        if not email_clean or not EMAIL_REGEX.match(email_clean):
            raise ValueError("Please provide a valid email address.")
        if not code_clean:
            raise ValueError("Please provide the 6-digit reset code.")
        if len(new_pass) < 6:
            raise ValueError("New password must be at least 6 characters long.")

        user = storage.get_auth_user(email_clean)
        if not user:
            raise ValueError("Account not found.")

        if not storage.verify_and_consume_reset_code(email_clean, code_clean):
            raise ValueError("Invalid or expired reset code. Please generate a new code.")

        p_hash, salt = hash_password(new_pass)
        storage.update_auth_user_password(email_clean, p_hash, salt)

        return {
            "status": "SUCCESS",
            "message": "Password updated successfully! You can now sign in with your new password."
        }

    def verify_token(self, token: str) -> Optional[dict]:
        if not token:
            return None
        if token.startswith("Bearer "):
            token = token.split(" ")[1]

        # 1. Check local session store
        session = get_session(token)
        if session:
            return session

        # 2. Check Supabase token if configured
        if self.is_supabase_configured:
            url = f"{self.supabase_url}/auth/v1/user"
            headers = {"apikey": self.supabase_key, "Authorization": f"Bearer {token}"}
            try:
                resp = requests.get(url, headers=headers, timeout=3.0)
                if resp.status_code == 200:
                    u = resp.json()
                    return {
                        "user_id": u.get("id"),
                        "email": u.get("email"),
                        "name": u.get("user_metadata", {}).get("name", u.get("email")),
                        "role": u.get("user_metadata", {}).get("role", "DEVELOPER")
                    }
            except Exception:
                pass

        return None
