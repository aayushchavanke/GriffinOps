import time
import pandas as pd
from typing import Dict, List, Optional
from griffinops.db.storage import storage


class RealWebsiteMonitor:
    """
    Pure White-Box Telemetry Store for API & SDK Monitored Applications.
    Stores and manages telemetry exclusively from incoming API & SDK pings.
    Zero mockups, zero artificial ping loops, zero hardcoded seed data.
    """
    def __init__(self):
        loaded_sites = storage.load_monitored_sites()
        # Filter out any legacy hardcoded Cloud Target demo site
        self.sites: List[dict] = [s for s in loaded_sites if s.get("name") != "Cloud Target Web Application" and s.get("api_key") != "gop_live_demo01"]
        self.history: Dict[str, List[dict]] = storage.load_telemetry_history(limit_per_site=60)
        for s in self.sites:
            if s["url"] not in self.history:
                self.history[s["url"]] = []

    def _normalize_url(self, url: str) -> str:
        url = url.strip()
        if not (url.startswith("http://") or url.startswith("https://") or url.startswith("tcp://") or url.startswith("file://")):
            if url.startswith("/"):
                url = f"https://api.internal{url}"
            else:
                url = f"https://{url}"
        return url

    def add_monitored_site(self, name: str, url: str, site_type: str = "Live Web App (SDK)", api_key: Optional[str] = None) -> dict:
        url = self._normalize_url(url)
        
        # Check if site already exists
        for existing in self.sites:
            if existing["url"] == url or existing["name"].lower() == name.lower():
                if api_key:
                    existing["api_key"] = api_key
                    storage.save_monitored_site(existing)
                return existing

        new_site = {
            "name": name,
            "url": url,
            "type": site_type,
            "api_key": api_key or "gop_live_custom"
        }
        self.sites.append(new_site)

        if url not in self.history:
            self.history[url] = []

        storage.save_monitored_site(new_site)
        return new_site

    def record_telemetry(self, url: str, latency_ms: float, status_code: int = 200, payload_bytes: int = 1024, api_key: Optional[str] = None, site_name: Optional[str] = None, cpu_percent: Optional[float] = None, memory_percent: Optional[float] = None) -> dict:
        """
        Records genuine white-box telemetry received directly from the 1-Line JavaScript SDK or backend API stream.
        cpu_percent and memory_percent are used as-is when provided by the Python SDK (real psutil values).
        Falls back to formula/constant for backward compatibility with JS SDK and cURL clients.
        """
        if api_key:
            matching = next((s for s in self.sites if s.get("api_key") == api_key), None)
            if matching:
                url = matching["url"]
            else:
                url = self._normalize_url(url)
        else:
            url = self._normalize_url(url)

        now = time.time()
        error_rate = 0.0 if status_code < 400 else 1.0
        # Use real psutil value if provided; otherwise derive from latency (JS/cURL clients)
        cpu_pct = round(float(cpu_percent), 2) if cpu_percent is not None else round(min(100.0, max(5.0, latency_ms / 2.5)), 2)
        # Use real psutil value if provided; otherwise fall back to constant 40.0 (JS/cURL clients)
        mem_pct = round(float(memory_percent), 2) if memory_percent is not None else 40.0

        # Auto-register site if not present
        if not any(s["url"] == url for s in self.sites):
            name = site_name or url.split("//")[-1].split("/")[0] or "Web Application"
            self.add_monitored_site(name=name, url=url, site_type="Live Web App (SDK)", api_key=api_key)

        data_point = {
            "timestamp": now,
            "latency_ms": round(latency_ms, 2),
            "status_code": status_code,
            "payload_bytes": payload_bytes,
            "error_rate": error_rate,
            "cpu_percent": cpu_pct,
            "memory_percent": mem_pct
        }

        if url not in self.history:
            self.history[url] = []
        self.history[url].append(data_point)
        if len(self.history[url]) > 60:
            self.history[url] = self.history[url][-60:]

        storage.queue_telemetry_point(url, data_point)
        return data_point

    def get_live_site_metrics(self) -> Dict[str, dict]:
        """
        Returns the latest recorded telemetry snapshot for all API-monitored websites and microservices.
        Includes newly registered sites/APIs immediately with pending/standby state so they appear on the Overview tab.
        """
        results = {}
        for site in self.sites:
            url = site["url"]
            hist = self.history.get(url, [])
            if hist:
                latest = hist[-1]
                results[url] = {
                    "name": site["name"],
                    "url": url,
                    "type": site.get("type", "Live Web App (SDK)"),
                    "api_key": site.get("api_key", "gop_live_default"),
                    "latest": latest,
                    "history_length": len(hist),
                    "is_pending": False
                }
            else:
                results[url] = {
                    "name": site["name"],
                    "url": url,
                    "type": site.get("type", "Live Web App (SDK)"),
                    "api_key": site.get("api_key", "gop_live_default"),
                    "latest": {
                        "latency_ms": 0.0,
                        "status_code": 200,
                        "payload_bytes": 0,
                        "error_rate": 0.0,
                        "cpu_percent": 0.0,
                        "memory_percent": 0.0
                    },
                    "history_length": 0,
                    "is_pending": True
                }
        return results

    # Compatibility alias
    def ping_all_sites(self) -> Dict[str, dict]:
        return self.get_live_site_metrics()

    def get_real_telemetry_dataframe(self, url: str) -> pd.DataFrame:
        hist = self.history.get(url, [])
        return pd.DataFrame(hist)

    def get_all_real_telemetry(self) -> Dict[str, pd.DataFrame]:
        telemetry = {}
        for site in self.sites:
            url = site["url"]
            df = self.get_real_telemetry_dataframe(url)
            if not df.empty:
                clean_name = site["name"].lower().replace(" ", "-").replace("&", "and").replace("/", "-")
                telemetry[clean_name] = df
        return telemetry
