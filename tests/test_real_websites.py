import os
import sys
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from griffinops.telemetry.real_website_monitor import RealWebsiteMonitor
from griffinops.telemetry.normalizer import ZScoreNormalizer
from griffinops.models.tcn_forecaster import TCNPredictorEngine
from griffinops.rca.causal_engine import CausalRCAEngine


class TestRealWebsiteMonitoring(unittest.TestCase):
    """
    Live Telemetry Verification Test Suite for GriffinOps.
    Executes real live HTTP GET telemetry pings against external web targets
    and runs the full 2026 SOTA RCA (LagRCA + Granger Causality + RCAEval).
    """

    def setUp(self):
        self.monitor = RealWebsiteMonitor()
        self.normalizer = ZScoreNormalizer()
        self.causal_engine = CausalRCAEngine()
        self.tcn_predictor = TCNPredictorEngine()

        sites = [
            {"name": "HTTPBin GET API", "url": "https://httpbin.org/get", "type": "REST API"},
            {"name": "GitHub Platform", "url": "https://github.com", "type": "Live Web App"},
            {"name": "Google Search Gateway", "url": "https://google.com", "type": "Live Web App"},
            {"name": "Wikipedia Engine", "url": "https://wikipedia.org", "type": "Live Web App"}
        ]
        for site in sites:
            self.monitor.add_monitored_site(name=site["name"], url=site["url"], site_type=site["type"])

    def test_live_website_ping_and_rca(self):
        # Perform 2 consecutive ping cycles
        for _ in range(2):
            pings = self.monitor.ping_all_sites()
            time.sleep(0.5)

        telemetry = {}
        for url, data in pings.items():
            name = data["name"].lower().replace(" ", "-")
            df = self.monitor.get_real_telemetry_dataframe(url)
            telemetry[name] = df

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
