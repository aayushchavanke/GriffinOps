import os
import sys
import unittest
import torch
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from griffinops.telemetry.ingestion import TelemetryIngestor
from griffinops.telemetry.normalizer import ZScoreNormalizer
from griffinops.models.tcn_forecaster import PyTorchTCNForecaster, TCNPredictorEngine
from griffinops.rca.causal_engine import CausalRCAEngine
from griffinops.simulation.fault_simulator import FaultSimulatorManager
from griffinops.alerts.notifier import DualNotifier
from griffinops.api.keys import APIKeyManager
from griffinops.reports.pdf_generator import PDFReportGenerator
from griffinops.auth.supabase_auth import SupabaseAuthEngine
from griffinops.telemetry.real_website_monitor import RealWebsiteMonitor
from griffinops.reports.docx_generator import DOCXReportGenerator

from fastapi.testclient import TestClient
from griffinops.api.main import app

class TestGriffinOpsEnterprisePipeline(unittest.TestCase):

    def setUp(self):
        self.real_monitor = RealWebsiteMonitor()
        self.key_manager = APIKeyManager()
        self.docx_gen = DOCXReportGenerator()
        self.client = TestClient(app)

    def test_api_monitored_site_store(self):
        site = self.real_monitor.add_monitored_site("My Store App", "https://store.example.com", api_key="gop_live_test123")
        self.assertEqual(site["name"], "My Store App")
        
        # Record incoming SDK telemetry
        dp = self.real_monitor.record_telemetry("https://store.example.com", latency_ms=48.2, status_code=200, api_key="gop_live_test123")
        self.assertEqual(dp["latency_ms"], 48.2)
        self.assertEqual(dp["status_code"], 200)

        metrics = self.real_monitor.get_live_site_metrics()
        self.assertIn("https://store.example.com", metrics)
        self.assertEqual(metrics["https://store.example.com"]["latest"]["latency_ms"], 48.2)

    def test_api_key_manager(self):
        key = self.key_manager.generate_api_key(
            name="Checkout Service",
            endpoint="/api/v1/checkout",
            sla_latency_ms=150.0,
            sla_tier="Payment ($850/min)",
            owner_email="developer@test.com"
        )
        self.assertTrue(key["api_key"].startswith("gop_live_"))
        self.assertIn("html", key["sdk_snippets"])
        self.assertIn("python", key["sdk_snippets"])

        validated = self.key_manager.validate_api_key(key["api_key"])
        self.assertIsNotNone(validated)
        self.assertEqual(validated["name"], "Checkout Service")

    def test_docx_generator(self):
        filepath = self.docx_gen.generate_docx()
        self.assertTrue(os.path.exists(filepath))
        self.assertTrue(filepath.endswith(".docx"))
        self.assertGreater(os.path.getsize(filepath), 100)

    def test_fastapi_endpoints(self):
        # 1. Health check
        res_health = self.client.get("/api/v1/health")
        self.assertEqual(res_health.status_code, 200)

        # 2. Auth Login
        res_auth = self.client.post("/api/v1/auth/login", json={"email": "admin@griffinops.io", "password": "admin123"})
        self.assertEqual(res_auth.status_code, 200)
        token = res_auth.json().get("access_token")
        self.assertTrue(bool(token))

        # 3. Create API Key
        res_key = self.client.post("/api/v1/keys/create", json={
            "name": "User Portal Web App",
            "endpoint": "https://portal.myapp.internal",
            "sla_latency_ms": 120.0
        })
        self.assertEqual(res_key.status_code, 200)
        api_key = res_key.json()["api_key"]

        # 4. Ingest Telemetry via API Key
        res_ingest = self.client.post("/api/v1/telemetry/ingest", json={
            "api_key": api_key,
            "latency_ms": 38.4,
            "status_code": 200,
            "payload_bytes": 4096
        })
        self.assertEqual(res_ingest.status_code, 200)
        self.assertEqual(res_ingest.json()["status"], "INGESTED")

        # 5. Live Telemetry & Forecast
        res_live = self.client.get("/api/v1/telemetry/live")
        self.assertEqual(res_live.status_code, 200)

        res_forecast = self.client.get("/api/v1/forecast")
        self.assertEqual(res_forecast.status_code, 200)

        # 6. Topology DAG
        res_topo = self.client.get("/api/v1/topology")
        self.assertEqual(res_topo.status_code, 200)
        self.assertIn("nodes", res_topo.json())
        self.assertIn("edges", res_topo.json())

        # 7. Architecture docx
        docx_res = self.client.get("/api/v1/docs/architecture.docx")
        self.assertEqual(docx_res.status_code, 200)
        self.assertIn("wordprocessingml.document", docx_res.headers["content-type"])

if __name__ == "__main__":
    unittest.main()
