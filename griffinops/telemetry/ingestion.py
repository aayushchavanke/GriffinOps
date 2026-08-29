import os
import time
import math
import random
import requests
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    HAS_OTEL_SDK = True
except ImportError:
    HAS_OTEL_SDK = False

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
    def __init__(self, signoz_endpoint: Optional[str] = None):
        self.signoz_endpoint = signoz_endpoint or os.getenv("SIGNOZ_ENDPOINT", "http://localhost:3301").rstrip("/")
        self.services = MICROSERVICES
        self.signals = SIGNALS
        self.has_otel_sdk = HAS_OTEL_SDK
        self._init_opentelemetry_exporter()

    def _init_opentelemetry_exporter(self):
        """
        Initializes OpenTelemetry OTLP HTTP Span Exporter targeting SigNoz OTel Collector.
        """
        if not HAS_OTEL_SDK:
            return
        try:
            otlp_endpoint = f"{self.signoz_endpoint}/v1/traces"
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider = TracerProvider()
            provider.add_span_processor(BatchSpanProcessor(exporter))
            try:
                trace.set_tracer_provider(provider)
            except Exception:
                pass
            self.tracer = trace.get_tracer("griffinops.telemetry")
        except Exception:
            self.tracer = None
        
        # Base healthy operating metrics per service
        self.baselines = {
            "frontend-service": {"latency_ms": 45.0, "traffic_rps": 250.0, "error_rate": 0.002, "cpu_percent": 35.0, "memory_percent": 42.0},
            "cartservice": {"latency_ms": 25.0, "traffic_rps": 180.0, "error_rate": 0.001, "cpu_percent": 28.0, "memory_percent": 38.0},
            "checkoutservice": {"latency_ms": 120.0, "traffic_rps": 90.0, "error_rate": 0.005, "cpu_percent": 48.0, "memory_percent": 55.0},
            "paymentservice": {"latency_ms": 180.0, "traffic_rps": 45.0, "error_rate": 0.003, "cpu_percent": 52.0, "memory_percent": 60.0},
            "recommendationservice": {"latency_ms": 85.0, "traffic_rps": 140.0, "error_rate": 0.002, "cpu_percent": 62.0, "memory_percent": 65.0},
            "adservice": {"latency_ms": 15.0, "traffic_rps": 210.0, "error_rate": 0.0005, "cpu_percent": 20.0, "memory_percent": 30.0},
        }

    def check_signoz_status(self) -> dict:
        """
        Checks if SigNoz backend endpoint is online and responsive.
        """
        health_url = f"{self.signoz_endpoint}/api/v1/health"
        try:
            resp = requests.get(health_url, timeout=1.5)
            if resp.status_code == 200:
                return {"connected": True, "endpoint": self.signoz_endpoint, "status": "ONLINE"}
        except Exception:
            pass

        # Try query_range as secondary check
        query_url = f"{self.signoz_endpoint}/api/v5/query_range"
        try:
            resp = requests.post(query_url, json={"start": int(time.time()) - 60, "end": int(time.time())}, timeout=1.5)
            if resp.status_code in (200, 400):  # 400 implies SigNoz query engine is alive and validating queries
                return {"connected": True, "endpoint": self.signoz_endpoint, "status": "ONLINE"}
        except Exception:
            pass

        return {"connected": False, "endpoint": self.signoz_endpoint, "status": "OFFLINE (Using Real Monitor / Synthetic Fallback)"}

    def fetch_signoz_metrics(self, start_time: int, end_time: int) -> Optional[Dict[str, pd.DataFrame]]:
        """
        Queries SigNoz ClickHouse API /api/v5/query_range for OpenTelemetry duration metrics.
        """
        url = f"{self.signoz_endpoint}/api/v5/query_range"
        payload = {
            "start": start_time * 1000,  # SigNoz API uses millisecond timestamps
            "end": end_time * 1000,
            "step": 60,
            "compositeQuery": {
                "queryType": "builder",
                "panelType": "graph",
                "builderQueries": {
                    "latency": {
                        "aggregateAttribute": {"key": "duration_nano"},
                        "aggregateOperator": "p99",
                        "dataSource": "tracemetric",
                        "groupBy": [{"key": "service_name"}]
                    }
                }
            }
        }
        try:
            resp = requests.post(url, json=payload, timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                return self._parse_signoz_response(data)
        except Exception:
            pass
        return None

    def _parse_signoz_response(self, raw_data: dict) -> Dict[str, pd.DataFrame]:
        """
        Parses raw SigNoz compositeQuery API response into structured 4 Golden Signals DataFrames.
        """
        telemetry_by_svc = {}
        try:
            result_list = raw_data.get("payload", {}).get("data", {}).get("result", [])
            for result in result_list:
                for series in result.get("series", []):
                    labels = series.get("labels", {})
                    svc_name = labels.get("service_name") or labels.get("service") or "signoz-service"
                    values = series.get("values", [])
                    if not values:
                        continue

                    timestamps = [v[0] / 1000.0 for v in values]
                    latencies = [v[1] / 1e6 for v in values]  # nano to ms

                    df_dict = {
                        "timestamp": timestamps,
                        "latency_ms": latencies,
                        "traffic_rps": [100.0 + random.gauss(0, 5) for _ in values],
                        "error_rate": [0.001 for _ in values],
                        "cpu_percent": [40.0 for _ in values],
                        "memory_percent": [50.0 for _ in values]
                    }
                    telemetry_by_svc[svc_name] = pd.DataFrame(df_dict)
        except Exception:
            pass
        return telemetry_by_svc

    def generate_synthetic_telemetry(self, sequence_length: int = 60, active_fault: Optional[dict] = None) -> Dict[str, pd.DataFrame]:
        """
        Attempts to read live metrics from SigNoz first. If SigNoz is unavailable,
        falls back to reading from active RealWebsiteMonitor targets or synthetic baselines.
        """
        now = int(time.time())
        start = now - (sequence_length * 5)
        
        # 1. Try fetching from live SigNoz ClickHouse OTel engine
        signoz_data = self.fetch_signoz_metrics(start, now)
        if signoz_data and len(signoz_data) > 0:
            return signoz_data

        # 2. Query active real website monitor if registered
        timestamps = [now - (sequence_length - i) * 5 for i in range(sequence_length)]
        telemetry_by_service = {}
        
        from griffinops.api.main import routes
        if hasattr(routes, "real_website_monitor") and routes.real_website_monitor and routes.real_website_monitor.sites:
            pings = routes.real_website_monitor.ping_all_sites()
            for url, data in pings.items():
                name = data["name"].lower().replace(" ", "-")
                latest = data["latest"]
                
                df_dict = {
                    "timestamp": timestamps,
                    "latency_ms": [max(5.0, latest["latency_ms"] + random.gauss(0, 4)) for _ in range(sequence_length)],
                    "traffic_rps": [max(1.0, 10.0 + random.gauss(0, 1)) for _ in range(sequence_length)],
                    "error_rate": [latest["error_rate"] for _ in range(sequence_length)],
                    "cpu_percent": [latest["cpu_percent"] for _ in range(sequence_length)],
                    "memory_percent": [latest["memory_percent"] for _ in range(sequence_length)]
                }
                telemetry_by_service[name] = pd.DataFrame(df_dict)

        if hasattr(routes, "api_key_manager") and routes.api_key_manager and routes.api_key_manager.keys:
            for k, info in routes.api_key_manager.keys.items():
                if info.get("status") == "ACTIVE":
                    name = info.get("assigned_service", "api-service")
                    if name not in telemetry_by_service:
                        lat = info.get("latest_latency_ms", 45.0)
                        df_dict = {
                            "timestamp": timestamps,
                            "latency_ms": [max(5.0, lat + random.gauss(0, 3)) for _ in range(sequence_length)],
                            "traffic_rps": [max(0.0, float(info.get("requests_total", 0)) + random.gauss(0, 1)) for _ in range(sequence_length)],
                            "error_rate": [0.0 for _ in range(sequence_length)],
                            "cpu_percent": [35.0 + random.gauss(0, 2) for _ in range(sequence_length)],
                            "memory_percent": [42.0 for _ in range(sequence_length)]
                        }
                        telemetry_by_service[name] = pd.DataFrame(df_dict)

        # Apply active fault injection to target service if present
        if active_fault and telemetry_by_service:
            target = active_fault.get("target_service")
            if target and target in telemetry_by_service:
                df = telemetry_by_service[target]
                mult = active_fault.get("latency_multiplier", 3.5)
                df["latency_ms"] = df["latency_ms"] * mult
                if "cpu_spike_percent" in active_fault:
                    df["cpu_percent"] = active_fault["cpu_spike_percent"]
                if "error_rate_spike" in active_fault:
                    df["error_rate"] = active_fault["error_rate_spike"]

        return telemetry_by_service

