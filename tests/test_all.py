import os
import sys
import unittest
import uuid
import torch
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ---------------------------------------------------------------------------
# TEST DATABASE ISOLATION  — must run before any griffinops module is imported
#
# griffinops.db.storage is a module that creates a singleton `storage` at
# import time pointing to the production griffinops/data/griffinops.db.
# We replace it with an in-memory StorageManager here so that every subsequent
# import (including `from griffinops.api.main import app`) picks up the test
# instance instead of the real file.
# ---------------------------------------------------------------------------
import griffinops.db.storage as _storage_module
from griffinops.db.storage import StorageManager

_TEST_STORAGE = StorageManager(":memory:")
_storage_module.storage = _TEST_STORAGE

# Now safe to import modules that consume `storage`
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

# Patch each consumer module that captured the singleton at their own import time
import griffinops.telemetry.real_website_monitor as _rwm_mod
import griffinops.api.keys as _keys_mod
_rwm_mod.storage = _TEST_STORAGE
_keys_mod.storage = _TEST_STORAGE

# Import the FastAPI app last — it uses the now-patched singletons
from fastapi.testclient import TestClient
from griffinops.api.main import app
import griffinops.api.routes as _routes
import griffinops.api.main as _main_mod
# Patch storage reference inside routes and main as well
_routes.storage = _TEST_STORAGE
_main_mod.storage = _TEST_STORAGE


class TestGriffinOpsEnterprisePipeline(unittest.TestCase):

    def setUp(self):
        # Each monitor/manager instance constructed here uses _TEST_STORAGE
        # because we patched the module-level `storage` reference above.
        self.real_monitor = RealWebsiteMonitor()
        self.key_manager = APIKeyManager()
        self.docx_gen = DOCXReportGenerator()
        self.client = TestClient(app)

    def tearDown(self):
        # Wipe test data between tests to keep them isolated
        with _TEST_STORAGE._lock:
            conn = _TEST_STORAGE._get_connection()
            conn.execute("DELETE FROM monitored_sites")
            conn.execute("DELETE FROM telemetry_history")
            conn.execute("DELETE FROM api_keys")
            conn.execute("DELETE FROM dispatch_logs")
            conn.commit()

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

    def test_robust_authentication_flow(self):
        test_email = f"sarah_{uuid.uuid4().hex[:6]}@cyberdyne.io"

        # 1. Reject invalid login credentials
        res_fail = self.client.post("/api/v1/auth/login", json={"email": "nonexistent@griffinops.io", "password": "wrong"})
        self.assertEqual(res_fail.status_code, 401)

        # 2. Reject existing seed admin registration
        res_dup_admin = self.client.post("/api/v1/auth/register", json={
            "name": "Admin Impostor", "email": "admin@griffinops.io", "password": "password123"
        })
        self.assertEqual(res_dup_admin.status_code, 400)
        self.assertIn("already exists", res_dup_admin.json()["detail"].lower())

        # 3. Successfully register new user
        res_reg = self.client.post("/api/v1/auth/register", json={
            "name": "Sarah Connor", "email": test_email, "password": "securePassword123"
        })
        self.assertEqual(res_reg.status_code, 200)
        self.assertEqual(res_reg.json()["status"], "SUCCESS")

        # 4. Attempting to register Sarah again MUST be rejected
        res_dup = self.client.post("/api/v1/auth/register", json={
            "name": "Sarah Connor", "email": test_email, "password": "anotherPassword"
        })
        self.assertEqual(res_dup.status_code, 400)
        self.assertIn("already exists", res_dup.json()["detail"].lower())

        # 5. Wrong password rejected
        res_wrong = self.client.post("/api/v1/auth/login", json={
            "email": test_email, "password": "wrongPassword"
        })
        self.assertEqual(res_wrong.status_code, 401)

        # 6. Correct password succeeds
        res_ok = self.client.post("/api/v1/auth/login", json={
            "email": test_email, "password": "securePassword123"
        })
        self.assertEqual(res_ok.status_code, 200)
        token = res_ok.json()["access_token"]
        self.assertTrue(bool(token))

        # 7. Forgot password flow generates reset code
        res_forgot = self.client.post("/api/v1/auth/forgot-password", json={"email": test_email})
        self.assertEqual(res_forgot.status_code, 200)
        reset_code = res_forgot.json().get("reset_code")
        self.assertTrue(bool(reset_code))

        # 8. Reset password with invalid code fails
        res_reset_bad = self.client.post("/api/v1/auth/reset-password", json={
            "email": test_email, "reset_code": "000000", "new_password": "brandNewPassword123"
        })
        self.assertEqual(res_reset_bad.status_code, 400)

        # 9. Reset password with valid code succeeds
        res_reset_ok = self.client.post("/api/v1/auth/reset-password", json={
            "email": test_email, "reset_code": reset_code, "new_password": "brandNewPassword123"
        })
        self.assertEqual(res_reset_ok.status_code, 200)

        # 10. Old password fails
        res_old_fail = self.client.post("/api/v1/auth/login", json={
            "email": test_email, "password": "securePassword123"
        })
        self.assertEqual(res_old_fail.status_code, 401)

        # 11. New password succeeds
        res_new_ok = self.client.post("/api/v1/auth/login", json={
            "email": test_email, "password": "brandNewPassword123"
        })
        self.assertEqual(res_new_ok.status_code, 200)
        self.assertTrue(bool(res_new_ok.json().get("access_token")))


if __name__ == "__main__":
    unittest.main()
