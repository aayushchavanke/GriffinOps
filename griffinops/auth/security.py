import time
import hashlib
import hmac
import secrets
import uuid
from typing import Optional, Dict, Tuple

SECRET_KEY = "griffinops-secret-key-sies-gst-ai-sre-copilot"

def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """
    Cryptographically secure password hashing using PBKDF2 HMAC SHA-256
    with 100,000 iterations and 16-byte random hex salt.
    """
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=100_000
    ).hex()
    return hashed, salt

def verify_password(password: str, stored_hash: str, salt: Optional[str] = None) -> bool:
    """
    Verifies a password against the stored hash and salt.
    Supports PBKDF2 with constant-time comparison, plus legacy SHA-256 fallback.
    """
    if not password or not stored_hash:
        return False

    if salt:
        computed = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations=100_000
        ).hex()
        if hmac.compare_digest(computed, stored_hash):
            return True

    # Legacy raw SHA-256 check (for backward compatibility with seeded accounts)
    legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy_hash, stored_hash)

# Active session tokens: token -> session dict
SESSIONS_DB: Dict[str, dict] = {}

def create_session(user_id: str, email: str, name: str, role: str) -> str:
    token = f"gop_sess_{uuid.uuid4().hex}"
    SESSIONS_DB[token] = {
        "user_id": user_id,
        "email": email,
        "name": name,
        "role": role,
        "created_at": time.time()
    }
    return token

def get_session(token: str) -> Optional[dict]:
    if not token:
        return None
    if token.startswith("Bearer "):
        token = token.split(" ")[1]
    return SESSIONS_DB.get(token)

def revoke_session(token: str) -> bool:
    if not token:
        return False
    if token.startswith("Bearer "):
        token = token.split(" ")[1]
    return SESSIONS_DB.pop(token, None) is not None
