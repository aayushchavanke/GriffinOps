import os
import sys
import unittest
import torch
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from griffinops.telemetry.ingestion import TelemetryIngestor, MICROSERVICES
from griffinops.telemetry.normalizer import ZScoreNormalizer
from griffinops.models.tcn_forecaster import PyTorchTCNForecaster, TCNPredictorEngine
from griffinops.rca.causal_engine import CausalRCAEngine
from griffinops.simulation.fault_simulator import FaultSimulatorManager
from griffinops.alerts.notifier import DualNotifier
from griffinops.api.keys import APIKeyManager
from griffinops.dummy_app.app import DummyECommerceApp
from griffinops.reports.pdf_generator import PDFReportGenerator
from griffinops.auth.supabase_auth import SupabaseAuthEngine
from griffinops.telemetry.real_website_monitor import RealWebsiteMonitor
from griffinops.reports.docx_generator import DOCXReportGenerator

from fastapi.testclient import TestClient
from griffinops.api.main import app

class TestGriffinOpsRealTelemetryAndDOCXPipeline(unittest.TestCase):

    def setUp(self):
        self.real_monitor = RealWebsiteMonitor()
        self.docx_gen = DOCXReportGenerator()
        self.client = TestClient(app)

    def test_real_website_monitor(self):
        res = self.real_monitor.ping_all_sites()
        self.assertTrue(len(res) > 0)
        first_url = list(res.keys())[0]
        latest = res[first_url]["latest"]
        self.assertIn("latency_ms", latest)
        self.assertIsInstance(latest["status_code"], int)
        self.assertGreater(latest["status_code"], 0)

    def test_docx_generator(self):
        filepath = self.docx_gen.generate_docx()
        self.assertTrue(os.path.exists(filepath))
        self.assertTrue(filepath.endswith(".docx"))
        self.assertGreater(os.path.getsize(filepath), 100)

    def test_fastapi_real_monitor_and_docx(self):
        monitor_res = self.client.get("/api/v1/real-monitor/live")
        self.assertEqual(monitor_res.status_code, 200)

        docx_res = self.client.get("/api/v1/docs/architecture.docx")
        self.assertEqual(docx_res.status_code, 200)
        self.assertIn("wordprocessingml.document", docx_res.headers["content-type"])

if __name__ == "__main__":
    unittest.main()
