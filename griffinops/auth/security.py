import time
import hashlib
import uuid
from typing import Optional, Dict

SECRET_KEY = "griffinops-secret-key-sies-gst-ai-sre-copilot"

# In-memory user database
USERS_DB: Dict[str, dict] = {
    "admin@griffinops.io": {
        "user_id": "usr_admin001",
        "email": "admin@griffinops.io",
        "name": "SRE Lead Engineer",
        "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
        "role": "ADMIN"
    }
}

# Active session tokens: token -> user_info
SESSIONS_DB: Dict[str, dict] = {}

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash

def register_user(email: str, password: str, name: str) -> dict:
    if email in USERS_DB:
        raise ValueError(f"User with email '{email}' already exists.")
    user_id = f"usr_{uuid.uuid4().hex[:8]}"
    user = {
        "user_id": user_id,
        "email": email,
        "name": name,
        "password_hash": hash_password(password),
        "role": "DEVELOPER"
    }
    USERS_DB[email] = user
    return user

def authenticate_user(email: str, password: str) -> Optional[dict]:
    user = USERS_DB.get(email)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    
    # Generate session token
    token = f"gop_sess_{uuid.uuid4().hex}"
    SESSIONS_DB[token] = {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "created_at": time.time()
    }
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": user["user_id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"]
        }
    }

def get_user_from_token(token: str) -> Optional[dict]:
    if not token:
        return None
    if token.startswith("Bearer "):
        token = token.split(" ")[1]
    return SESSIONS_DB.get(token)
