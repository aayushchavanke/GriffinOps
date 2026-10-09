import os
import sys
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ---------------------------------------------------------------------------
# TEST DATABASE ISOLATION
# All imports that touch griffinops.db.storage must come AFTER we replace the
# module-level singleton with an in-memory StorageManager.  We do this by:
#   1. Importing the storage module first.
#   2. Replacing storage.storage (the singleton) with a fresh in-memory instance.
#   3. Patching every other module that imported the singleton so they all
#      reference the same test instance.
# ---------------------------------------------------------------------------
import griffinops.db.storage as _storage_module
from griffinops.db.storage import StorageManager

# Create a fresh, isolated in-memory storage for this test run
_TEST_STORAGE = StorageManager(":memory:")

# Replace the module-level singleton BEFORE any other griffinops module imports it
_storage_module.storage = _TEST_STORAGE

# Now import the modules that consume `storage`; they will pick up the patched singleton
from griffinops.telemetry.real_website_monitor import RealWebsiteMonitor
from griffinops.telemetry.normalizer import ZScoreNormalizer
from griffinops.models.tcn_forecaster import TCNPredictorEngine
from griffinops.rca.causal_engine import CausalRCAEngine

# Patch the already-imported singletons in each consumer module so they also
# use the test instance (these modules captured `storage` at import time)
import griffinops.telemetry.real_website_monitor as _rwm_mod
_rwm_mod.storage = _TEST_STORAGE


class TestAPIMonitoredWebsites(unittest.TestCase):
    """
    API/SDK Monitored Website Verification Test Suite for GriffinOps.
    Tests telemetry ingestion, robust MAD normalization, PyTorch TCN forecasting,
    and causal discovery.

    Uses an isolated in-memory SQLite database — never writes to the production
    griffinops/data/griffinops.db file.
    """

    def setUp(self):
        # Wipe the in-memory DB so tests start completely clean and isolated
        with _TEST_STORAGE._lock:
            conn = _TEST_STORAGE._get_connection()
            conn.execute("DELETE FROM monitored_sites")
            conn.execute("DELETE FROM telemetry_history")
            conn.execute("DELETE FROM api_keys")
            conn.commit()

        # Each test gets a clean in-memory monitor backed by the test storage
        self.monitor = RealWebsiteMonitor()
        self.normalizer = ZScoreNormalizer()
        self.causal_engine = CausalRCAEngine()
        self.tcn_predictor = TCNPredictorEngine()

        sites = [
            {"name": "E-Commerce Web App",   "url": "https://store.example.com",        "type": "Live Web App (SDK)",          "api_key": "gop_live_store01"},
            {"name": "Checkout API Gateway", "url": "https://api.example.com/checkout",  "type": "Microservice Ingress (API)",   "api_key": "gop_live_chk02"},
            {"name": "Auth Session Service", "url": "https://auth.example.com/session",  "type": "Security Microservice (API)", "api_key": "gop_live_auth03"},
            {"name": "Postgres Database",    "url": "tcp://db.example.internal:5432",    "type": "Datastore Cluster",           "api_key": "gop_live_db04"},
        ]
        for site in sites:
            self.monitor.add_monitored_site(
                name=site["name"], url=site["url"],
                site_type=site["type"], api_key=site["api_key"]
            )

    def tearDown(self):
        # Wipe the in-memory DB between tests so they stay independent
        with _TEST_STORAGE._lock:
            conn = _TEST_STORAGE._get_connection()
            conn.execute("DELETE FROM monitored_sites")
            conn.execute("DELETE FROM telemetry_history")
            conn.execute("DELETE FROM api_keys")
            conn.commit()

    def test_api_website_telemetry_and_rca(self):
        # Simulate incoming white-box SDK telemetry
        for _ in range(5):
            self.monitor.record_telemetry("https://store.example.com",        latency_ms=42.0,  status_code=200, api_key="gop_live_store01")
            self.monitor.record_telemetry("https://api.example.com/checkout",  latency_ms=185.0, status_code=200, api_key="gop_live_chk02")
            self.monitor.record_telemetry("https://auth.example.com/session",  latency_ms=35.0,  status_code=200, api_key="gop_live_auth03")
            self.monitor.record_telemetry("tcp://db.example.internal:5432",    latency_ms=15.0,  status_code=200, api_key="gop_live_db04")

        metrics = self.monitor.get_live_site_metrics()
        self.assertEqual(len(metrics), 4)

        telemetry = self.monitor.get_all_real_telemetry()
        self.assertTrue(len(telemetry) >= 2)

        z_scores = self.normalizer.compute_z_scores(telemetry)
        tensor, service_names = self.normalizer.to_tensor_format(z_scores, sequence_length=30)
        tcn_results = self.tcn_predictor.predict(tensor, service_names=service_names)

        report = self.causal_engine.analyze_root_cause(tcn_results, z_scores, algorithm="composite")

        self.assertIn("report_id", report)
        self.assertIn("root_cause_analysis", report)
        rca = report["root_cause_analysis"]
        self.assertIn("service", rca)
        self.assertIn("causal_scores_ranking", rca)

    def test_no_hardcoded_cloud_target_seed(self):
        from griffinops.api.keys import APIKeyManager
        km = APIKeyManager()
        self.assertNotIn("gop_live_demo01", km.keys)
        self.assertFalse(any(k.get("name") == "Cloud Target Web Application" for k in km.keys.values()))

        # Also verify RealWebsiteMonitor sites list does not contain Cloud Target Web Application
        monitor_fresh = RealWebsiteMonitor()
        self.assertFalse(any(s.get("name") == "Cloud Target Web Application" for s in monitor_fresh.sites))

    def test_email_alert_dispatch_status(self):
        from griffinops.alerts.notifier import DualNotifier
        notifier = DualNotifier()
        mock_report = {
            "report_id": "GO-TEST-001",
            "system_status": "SEV-1 CRITICAL HAZARD",
            "severity_level": "CRITICAL (SEV-1)",
            "forecasted_time_to_failure_human": "2m 15s",
            "root_cause_analysis": {
                "service": "checkout-service",
                "primary_metric": "latency_ms",
                "max_z_score_deviation": 3.8
            },
            "suggested_action": "Rollback deployment"
        }
        res = notifier.send_email_notification(mock_report, recipient_email="developer@example.com")
        self.assertIn(res["status"], ["STORED_IN_PREVIEW", "DELIVERED", "FAILED"])
        self.assertEqual(res["recipient"], "developer@example.com")


if __name__ == "__main__":
    unittest.main()
