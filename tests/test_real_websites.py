import os
import sys
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from griffinops.telemetry.real_website_monitor import RealWebsiteMonitor
from griffinops.telemetry.normalizer import ZScoreNormalizer
from griffinops.models.tcn_forecaster import TCNPredictorEngine
from griffinops.rca.causal_engine import CausalRCAEngine


class TestAPIMonitoredWebsites(unittest.TestCase):
    """
    API/SDK Monitored Website Verification Test Suite for GriffinOps.
    Tests telemetry ingestion, robust MAD normalization, PyTorch TCN forecasting,
    and causal discovery.
    """

    def setUp(self):
        self.monitor = RealWebsiteMonitor()
        self.normalizer = ZScoreNormalizer()
        self.causal_engine = CausalRCAEngine()
        self.tcn_predictor = TCNPredictorEngine()

        sites = [
            {"name": "E-Commerce Web App", "url": "https://store.example.com", "type": "Live Web App (SDK)", "api_key": "gop_live_store01"},
            {"name": "Checkout API Gateway", "url": "https://api.example.com/checkout", "type": "Microservice Ingress (API)", "api_key": "gop_live_chk02"},
            {"name": "Auth Session Service", "url": "https://auth.example.com/session", "type": "Security Microservice (API)", "api_key": "gop_live_auth03"},
            {"name": "Postgres Database", "url": "tcp://db.example.internal:5432", "type": "Datastore Cluster", "api_key": "gop_live_db04"}
        ]
        for site in sites:
            self.monitor.add_monitored_site(name=site["name"], url=site["url"], site_type=site["type"], api_key=site["api_key"])

    def test_api_website_telemetry_and_rca(self):
        # Simulate incoming white-box SDK telemetry
        for _ in range(5):
            self.monitor.record_telemetry("https://store.example.com", latency_ms=42.0, status_code=200, api_key="gop_live_store01")
            self.monitor.record_telemetry("https://api.example.com/checkout", latency_ms=185.0, status_code=200, api_key="gop_live_chk02")
            self.monitor.record_telemetry("https://auth.example.com/session", latency_ms=35.0, status_code=200, api_key="gop_live_auth03")
            self.monitor.record_telemetry("tcp://db.example.internal:5432", latency_ms=15.0, status_code=200, api_key="gop_live_db04")

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


if __name__ == "__main__":
    unittest.main()
