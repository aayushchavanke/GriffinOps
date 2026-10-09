import os
import time
import uuid
from typing import Dict, List, Optional
from griffinops.db.storage import storage

# In-memory API Keys Registry: api_key -> key_info (Starts completely clean)
API_KEYS_DB: Dict[str, dict] = {}


class APIKeyManager:
    """
    Clean, Developer-Centric API Key Manager.
    Generates and validates GriffinOps API Keys (gop_live_...) for monitored websites and microservices.
    Zero mockups, zero hardcoded seed data.
    """
    def __init__(self):
        self.keys = API_KEYS_DB
        persisted = storage.load_api_keys()
        if persisted:
            self.keys.update(persisted)
        # Purge legacy hardcoded demo seed if present in database or memory
        legacy_keys = [k for k, v in list(self.keys.items()) if k == "gop_live_demo01" or (isinstance(v, dict) and v.get("name") == "Cloud Target Web Application")]
        for lk in legacy_keys:
            self.keys.pop(lk, None)
            storage.delete_api_key(lk)
            storage.delete_monitored_site_by_name_or_key(lk)
        storage.delete_monitored_site_by_name_or_key("Cloud Target Web Application")

    def generate_api_key(
        self,
        name: str,
        target_url: Optional[str] = None,
        endpoint: Optional[str] = None,
        owner_email: str = "admin@griffinops.io",
        predefined_key: Optional[str] = None,
        **kwargs
    ) -> dict:
        raw_key = predefined_key or f"gop_live_{uuid.uuid4().hex[:12]}"
        key_id = f"key_{uuid.uuid4().hex[:8]}"
        service_slug = name.lower().replace(" ", "-").replace("&", "and").replace("/", "-")
        clean_url = target_url or f"https://{service_slug}.internal"
        base_url = os.getenv("GRIFFINOPS_PUBLIC_URL", "https://griffinops.up.railway.app").rstrip("/")

        html_snippet = f'<!-- GriffinOps 1-Line JavaScript Telemetry SDK -->\n<script src="{base_url}/static/js/griffinops-sdk.js" data-api-key="{raw_key}"></script>'
        python_snippet = f'import requests\n\nheaders = {{"X-GriffinOps-API-Key": "{raw_key}"}}\nrequests.post("{base_url}/api/v1/telemetry/ingest", headers=headers, json={{"latency_ms": 42.5, "status_code": 200}})'
        nodejs_snippet = f"const axios = require('axios');\n\naxios.post('{base_url}/api/v1/telemetry/ingest', \n  {{ latency_ms: 42.5, status_code: 200 }}, \n  {{ headers: {{ 'X-GriffinOps-API-Key': '{raw_key}' }} }}\n);"
        curl_snippet = f'curl -X POST "{base_url}/api/v1/telemetry/ingest" \\\n  -H "X-GriffinOps-API-Key: {raw_key}" \\\n  -H "Content-Type: application/json" \\\n  -d \'{{"latency_ms": 42.5, "status_code": 200}}\''

        record = {
            "key_id": key_id,
            "api_key": raw_key,
            "name": name,
            "assigned_service": service_slug,
            "endpoint": clean_url,
            "target_url": clean_url,
            "owner_email": owner_email,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "requests_total": 0,
            "latest_latency_ms": None,
            "status": "ACTIVE",
            "sdk_snippets": {
                "html": html_snippet,
                "python": python_snippet,
                "nodejs": nodejs_snippet,
                "curl": curl_snippet
            }
        }
        self.keys[raw_key] = record
        storage.save_api_key(record)
        return record

    def list_api_keys(self, owner_email: Optional[str] = None) -> List[dict]:
        if owner_email and owner_email != "admin@griffinops.io":
            user_keys = [k for k in self.keys.values() if k.get("owner_email") == owner_email]
            if user_keys:
                return user_keys
        return list(self.keys.values())

    def revoke_api_key(self, key_id: str) -> bool:
        for k, info in list(self.keys.items()):
            if info["key_id"] == key_id:
                info["status"] = "REVOKED"
                storage.update_api_key_status(key_id, "REVOKED")
                return True
        return False

    def validate_api_key(self, api_key: str) -> Optional[dict]:
        info = self.keys.get(api_key)
        if info and info["status"] == "ACTIVE":
            info["requests_total"] += 1
            storage.mark_api_key_dirty(api_key, info["requests_total"], info.get("latest_latency_ms"))
            return info
        return None

    def get_monitored_apis(self) -> List[dict]:
        monitored = []
        for k, info in self.keys.items():
            if info["status"] == "ACTIVE":
                lat = info.get("latest_latency_ms")
                monitored.append({
                    "api_endpoint": info.get("endpoint", "/api/v1/telemetry"),
                    "service": info["assigned_service"],
                    "method": "POST",
                    "api_key": info["api_key"],
                    "api_key_name": info["name"],
                    "rpm": info.get("requests_total", 0),
                    "avg_latency_ms": round(lat, 1) if lat is not None else 0.0,
                    "error_rate": 0.0,
                    "health_status": "ACTIVE" if lat is not None else "AWAITING TELEMETRY"
                })
        return monitored
