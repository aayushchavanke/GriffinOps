import time
import uuid
from typing import Dict, List, Optional

# API Keys Registry: key_id -> key_info
API_KEYS_DB: Dict[str, dict] = {}

class APIKeyManager:
    """
    Manages generation, validation, and revocation of GriffinOps API Keys (gop_live_...).
    Tracks active APIs in use and correlates telemetry with target services.
    """
    def __init__(self):
        self.keys = API_KEYS_DB

    def generate_api_key(self, name: str, environment: str = "production", target_url: str = "https://httpbin.org/get") -> dict:
        raw_key = f"gop_live_{uuid.uuid4().hex[:12]}"
        key_id = f"key_{uuid.uuid4().hex[:8]}"
        
        record = {
            "key_id": key_id,
            "api_key": raw_key,
            "name": name,
            "environment": environment,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "assigned_service": name.lower().replace(" ", "-"),
            "target_url": target_url,
            "requests_total": 0,
            "status": "ACTIVE"
        }
        self.keys[raw_key] = record
        return record

    def list_api_keys(self) -> List[dict]:
        return list(self.keys.values())

    def revoke_api_key(self, key_id: str) -> bool:
        for k, info in list(self.keys.items()):
            if info["key_id"] == key_id:
                info["status"] = "REVOKED"
                return True
        return False

    def validate_api_key(self, api_key: str) -> Optional[dict]:
        info = self.keys.get(api_key)
        if info and info["status"] == "ACTIVE":
            info["requests_total"] += 1
            return info
        return None

    def get_monitored_apis(self) -> List[dict]:
        """
        Returns list of active APIs created by user in real time.
        """
        monitored = []
        for k, info in self.keys.items():
            if info["status"] == "ACTIVE":
                monitored.append({
                    "api_endpoint": info.get("target_url", "/api/v1/telemetry"),
                    "service": info["assigned_service"],
                    "method": "POST",
                    "api_key_name": info["name"],
                    "rpm": info.get("requests_total", 0),
                    "avg_latency_ms": 45.0,
                    "error_rate": 0.0,
                    "health_status": "ACTIVE"
                })
        return monitored
