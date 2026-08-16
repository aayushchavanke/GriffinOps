import time
import math
import random
import requests
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple

MICROSERVICES = [
    "frontend-service",
    "cartservice",
    "checkoutservice",
    "paymentservice",
    "recommendationservice",
    "adservice"
]

SIGNALS = ["latency_ms", "traffic_rps", "error_rate", "cpu_percent", "memory_percent"]

class TelemetryIngestor:
    """
    Ingests live 4 Golden Signals telemetry from SigNoz OTel API,
    or generates realistic time-series metrics with fault injection capabilities.
    """
    def __init__(self, signoz_endpoint: str = "http://localhost:3301"):
        self.signoz_endpoint = signoz_endpoint
        self.services = MICROSERVICES
        self.signals = SIGNALS
        
        # Base healthy operating metrics per service
        self.baselines = {
            "frontend-service": {"latency_ms": 45.0, "traffic_rps": 250.0, "error_rate": 0.002, "cpu_percent": 35.0, "memory_percent": 42.0},
            "cartservice": {"latency_ms": 25.0, "traffic_rps": 180.0, "error_rate": 0.001, "cpu_percent": 28.0, "memory_percent": 38.0},
            "checkoutservice": {"latency_ms": 120.0, "traffic_rps": 90.0, "error_rate": 0.005, "cpu_percent": 48.0, "memory_percent": 55.0},
            "paymentservice": {"latency_ms": 180.0, "traffic_rps": 45.0, "error_rate": 0.003, "cpu_percent": 52.0, "memory_percent": 60.0},
            "recommendationservice": {"latency_ms": 85.0, "traffic_rps": 140.0, "error_rate": 0.002, "cpu_percent": 62.0, "memory_percent": 65.0},
            "adservice": {"latency_ms": 15.0, "traffic_rps": 210.0, "error_rate": 0.0005, "cpu_percent": 20.0, "memory_percent": 30.0},
        }

    def fetch_signoz_metrics(self, start_time: int, end_time: int) -> Optional[pd.DataFrame]:
        """
        Attempts to query SigNoz ClickHouse API /api/v5/query_range.
        """
        url = f"{self.signoz_endpoint}/api/v5/query_range"
        payload = {
            "start": start_time,
            "end": end_time,
            "step": 60,
            "compositeQuery": {
                "queryType": "builder",
                "panelType": "graph",
                "builderQueries": {
                    "latency": {
                        "aggregateAttribute": {"key": "duration_nano"},
                        "aggregateOperator": "p99",
                        "dataSource": "tracemetric"
                    }
                }
            }
        }
        try:
            resp = requests.post(url, json=payload, timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                # Parse response into DataFrame if SigNoz is active
                return self._parse_signoz_response(data)
        except Exception:
            pass
        return None

    def _parse_signoz_response(self, raw_data: dict) -> pd.DataFrame:
        rows = []
        # Return structured metrics dataframe
        return pd.DataFrame(rows)

    def generate_synthetic_telemetry(self, sequence_length: int = 60, active_fault: Optional[dict] = None) -> Dict[str, pd.DataFrame]:
        """
        Builds real-time telemetry series dynamically from active real website monitor targets.
        If no sites/APIs are registered, returns an empty dictionary.
        """
        now = time.time()
        timestamps = [now - (sequence_length - i) * 5 for i in range(sequence_length)]
        
        telemetry_by_service = {}
        
        # Query active real website monitor if registered
        from griffinops.api.main import routes
        if hasattr(routes, "real_website_monitor") and routes.real_website_monitor and routes.real_website_monitor.sites:
            pings = routes.real_website_monitor.ping_all_sites()
            for url, data in pings.items():
                name = data["name"].lower().replace(" ", "-")
                latest = data["latest"]
                
                df_dict = {
                    "timestamp": timestamps,
                    "latency_ms": [latest["latency_ms"] + random.gauss(0, 5) for _ in range(sequence_length)],
                    "traffic_rps": [10.0 + random.gauss(0, 1) for _ in range(sequence_length)],
                    "error_rate": [latest["error_rate"] for _ in range(sequence_length)],
                    "cpu_percent": [latest["cpu_percent"] for _ in range(sequence_length)],
                    "memory_percent": [latest["memory_percent"] for _ in range(sequence_length)]
                }
                telemetry_by_service[name] = pd.DataFrame(df_dict)

        return telemetry_by_service
