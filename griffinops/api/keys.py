import time
import uuid
from typing import Dict, List, Optional

# API Keys Registry: key_id -> key_info
API_KEYS_DB: Dict[str, dict] = {}

# Seed initial default API Key for demo
DEFAULT_API_KEY = "gop_live_7a39e1f40b2"
API_KEYS_DB[DEFAULT_API_KEY] = {
    "key_id": "key_demo_001",
    "api_key": DEFAULT_API_KEY,
    "name": "Production E-Commerce Key",
    "environment": "production",
    "created_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    "assigned_service": "checkoutservice",
    "requests_total": 14250,
    "status": "ACTIVE"
}

class APIKeyManager:
    """
    Manages generation, validation, and revocation of GriffinOps API Keys (gop_live_...).
    Tracks active APIs in use and correlates telemetry with target services.
    """
    def __init__(self):
        self.keys = API_KEYS_DB

    def generate_api_key(self, name: str, environment: str = "production", assigned_service: str = "checkoutservice") -> dict:
        raw_key = f"gop_live_{uuid.uuid4().hex[:12]}"
        key_id = f"key_{uuid.uuid4().hex[:8]}"
        
        record = {
            "key_id": key_id,
            "api_key": raw_key,
            "name": name,
            "environment": environment,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "assigned_service": assigned_service,
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
        Returns list of active APIs in use across the microservices ecosystem.
        """
        return [
            {
                "api_endpoint": "/api/checkout",
                "service": "checkoutservice",
                "method": "POST",
                "api_key_name": "Production E-Commerce Key",
                "rpm": 180,
                "avg_latency_ms": 125.4,
                "error_rate": 0.002,
                "health_status": "MONITORED"
            },
            {
                "api_endpoint": "/api/payment",
                "service": "paymentservice",
                "method": "POST",
                "api_key_name": "Payment Gateway Key",
                "rpm": 95,
                "avg_latency_ms": 185.0,
                "error_rate": 0.001,
                "health_status": "MONITORED"
            },
            {
                "api_endpoint": "/api/cart",
                "service": "cartservice",
                "method": "POST",
                "api_key_name": "Cart Service Key",
                "rpm": 240,
                "avg_latency_ms": 28.5,
                "error_rate": 0.0005,
                "health_status": "MONITORED"
            },
            {
                "api_endpoint": "/api/recommendations",
                "service": "recommendationservice",
                "method": "GET",
                "api_key_name": "ML Rec Engine Key",
                "rpm": 310,
                "avg_latency_ms": 88.0,
                "error_rate": 0.001,
                "health_status": "MONITORED"
            }
        ]
