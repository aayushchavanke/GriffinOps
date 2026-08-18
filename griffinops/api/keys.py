import time
import uuid
import random
from typing import Dict, List, Optional

# API Keys Registry: key_id -> key_info
API_KEYS_DB: Dict[str, dict] = {}


class APIKeyManager:
    """
    Industry-Grade API Key Manager: Handles generation, validation, and revocation
    of GriffinOps API Keys (gop_live_...). Stores endpoint routes, SLA latency targets,
    and SLA financial risk tiers.
    """
    def __init__(self):
        self.keys = API_KEYS_DB

    def generate_api_key(
        self,
        name: str,
        environment: str = "production",
        endpoint: str = "/api/v1/checkout",
        sla_latency_ms: float = 200.0,
        sla_tier: str = "Payment ($850/min)",
        target_url: str = "https://httpbin.org/get"
    ) -> dict:
        raw_key = f"gop_live_{uuid.uuid4().hex[:12]}"
        key_id = f"key_{uuid.uuid4().hex[:8]}"
        service_slug = name.lower().replace(" ", "-").replace("&", "and")

        python_snippet = f"""import requests

headers = {{"X-GriffinOps-API-Key": "{raw_key}"}}
requests.post("http://localhost:8000/api/v1/telemetry/ingest", headers=headers, json={{"latency_ms": 125.4, "status_code": 200}})"""

        nodejs_snippet = f"""const axios = require('axios');

axios.post('http://localhost:8000/api/v1/telemetry/ingest', 
  {{ latency_ms: 125.4, status_code: 200 }}, 
  {{ headers: {{ 'X-GriffinOps-API-Key': '{raw_key}' }} }}
);"""

        curl_snippet = f"""curl -X POST http://localhost:8000/api/v1/telemetry/ingest \\
  -H "X-GriffinOps-API-Key: {raw_key}" \\
  -H "Content-Type: application/json" \\
  -d '{{\"latency_ms\": 125.4, \"status_code\": 200}}'"""

        record = {
            "key_id": key_id,
            "api_key": raw_key,
            "name": name,
            "assigned_service": service_slug,
            "endpoint": endpoint if endpoint.startswith("/") else f"/{endpoint}",
            "environment": environment,
            "sla_latency_ms": sla_latency_ms,
            "sla_tier": sla_tier,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "target_url": target_url,
            "requests_total": 0,
            "status": "ACTIVE",
            "sdk_snippets": {
                "python": python_snippet,
                "nodejs": nodejs_snippet,
                "curl": curl_snippet
            }
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
        monitored = []
        for k, info in self.keys.items():
            if info["status"] == "ACTIVE":
                sla_target = info.get("sla_latency_ms", 200.0)
                monitored.append({
                    "api_endpoint": info.get("endpoint", "/api/v1/telemetry"),
                    "service": info["assigned_service"],
                    "method": "POST",
                    "api_key_name": info["name"],
                    "rpm": info.get("requests_total", 0),
                    "sla_latency_ms": sla_target,
                    "sla_tier": info.get("sla_tier", "General ($250/min)"),
                    "avg_latency_ms": info.get("latest_latency_ms", 45.0),
                    "error_rate": 0.0,
                    "health_status": "ACTIVE"
                })
        return monitored
