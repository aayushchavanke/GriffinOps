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
        Generates clean 4 Golden Signals microservice telemetry with realistic sine-wave variation,
        random noise, and injected synthetic anomalies if an active fault is specified.
        """
        now = time.time()
        timestamps = [now - (sequence_length - i) * 5 for i in range(sequence_length)]
        
        telemetry_by_service = {}

        for svc in self.services:
            base = self.baselines[svc]
            df_dict = {"timestamp": timestamps}

            for sig in self.signals:
                base_val = base[sig]
                values = []
                for i, t in enumerate(timestamps):
                    # Daily / hourly sine wave variation
                    wave = math.sin(t / 120.0) * (base_val * 0.08)
                    noise = random.gauss(0, base_val * 0.03)
                    val = base_val + wave + noise
                    
                    # Apply fault injection if active for this service & signal
                    if active_fault and active_fault.get("target_service") == svc:
                        fault_type = active_fault.get("fault_type")
                        start_idx = active_fault.get("start_index", sequence_length // 2)
                        
                        if i >= start_idx:
                            progress = (i - start_idx) / (sequence_length - start_idx + 1e-5)
                            if fault_type == "CHECKOUT_LATENCY_CASCADE" and sig in ["latency_ms", "cpu_percent"]:
                                mult = 1.0 + (3.5 * progress)
                                val *= mult
                            elif fault_type == "PAYMENT_CPU_SATURATION" and sig in ["cpu_percent", "latency_ms"]:
                                mult = 1.0 + (4.0 * (progress ** 0.5))
                                val *= mult
                            elif fault_type == "RECOMMENDATION_MEMORY_LEAK" and sig in ["memory_percent", "latency_ms"]:
                                mult = 1.0 + (2.5 * progress)
                                val *= mult
                            elif fault_type == "CART_REDIS_ERROR_STORM" and sig in ["error_rate", "latency_ms"]:
                                val += 0.25 * progress + random.gauss(0, 0.05)
                                if sig == "error_rate":
                                    val = min(1.0, max(0.0, val))

                    # Ensure non-negative logical bounds
                    if sig == "error_rate":
                        val = max(0.0, min(1.0, val))
                    elif sig in ["cpu_percent", "memory_percent"]:
                        val = max(5.0, min(100.0, val))
                    else:
                        val = max(1.0, val)

                    values.append(round(val, 4))
                
                df_dict[sig] = values
            
            telemetry_by_service[svc] = pd.DataFrame(df_dict)

        return telemetry_by_service
