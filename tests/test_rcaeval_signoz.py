import os
import sys
import unittest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from griffinops.rca.rcaeval_engine import RCAEvalEngine
from griffinops.rca.causal_engine import CausalRCAEngine
from griffinops.telemetry.ingestion import TelemetryIngestor


class TestRCAEvalAndSigNozIntegration(unittest.TestCase):

    def setUp(self):
        self.rcaeval = RCAEvalEngine()
        self.causal_engine = CausalRCAEngine()
        self.telemetry = TelemetryIngestor()

    def test_pagerank_causal_walk(self):
        topology = {
            "frontend-service": ["cartservice", "checkoutservice"],
            "checkoutservice": ["paymentservice"],
            "cartservice": ["recommendationservice"]
        }
        anomaly_scores = {
            "frontend-service": 1.2,
            "cartservice": 0.8,
            "checkoutservice": 4.5,
            "paymentservice": 5.0,
            "recommendationservice": 0.5
        }

        pr_scores = self.rcaeval.pagerank_causal_walk(topology, anomaly_scores)
        self.assertEqual(len(pr_scores), 5)
        self.assertIn("paymentservice", pr_scores)
        self.assertGreaterEqual(pr_scores["paymentservice"], 0.0)

    def test_nsigma_anomaly_scoring(self):
        df_checkout = pd.DataFrame({
            "timestamp": range(10),
            "latency_ms": [2.5, 3.1, 4.2, 5.0, 6.1, 7.8, 8.9, 9.5, 10.2, 12.0],
            "error_rate": [0.01, 0.02, 0.05, 0.08, 0.12, 0.15, 0.20, 0.25, 0.30, 0.35]
        })
        df_cart = pd.DataFrame({
            "timestamp": range(10),
            "latency_ms": [0.1] * 10,
            "error_rate": [0.001] * 10
        })

        z_scores = {
            "checkoutservice": df_checkout,
            "cartservice": df_cart
        }

        nsigma = self.rcaeval.nsigma_anomaly_scoring(z_scores)
        self.assertGreater(nsigma["checkoutservice"], nsigma["cartservice"])

    def test_composite_rcaeval_scoring(self):
        topology = {"frontend": ["backend"], "backend": ["db"]}
        df_db = pd.DataFrame({"timestamp": range(10), "latency_z": [5.0] * 10})
        df_fe = pd.DataFrame({"timestamp": range(10), "latency_z": [0.5] * 10})
        z_scores = {"db": df_db, "frontend": df_fe}
        tcn_probs = {"db": 0.95, "frontend": 0.05}

        scores, meta = self.rcaeval.compute_composite_rcaeval_score(
            topology=topology,
            z_scores_by_service=z_scores,
            tcn_probabilities=tcn_probs,
            algorithm="composite"
        )
        self.assertGreater(scores["db"], scores["frontend"])
        self.assertIn("pagerank_centrality", meta["db"])
        self.assertIn("nsigma_score", meta["db"])

    def test_signoz_status_check(self):
        status = self.telemetry.check_signoz_status()
        self.assertIn("connected", status)
        self.assertIn("status", status)
        self.assertIn("endpoint", status)

    def test_causal_engine_algorithm_switch(self):
        df_payment = pd.DataFrame({"timestamp": range(10), "latency_ms": [4.0] * 10})
        z_scores = {"paymentservice": df_payment}
        tcn_results = {"services": {"paymentservice": {"failure_probability": 0.88}}}

        report = self.causal_engine.analyze_root_cause(
            tcn_results=tcn_results,
            z_scores_by_service=z_scores,
            algorithm="pagerank"
        )
        rca = report.get("root_cause_analysis", {})
        self.assertEqual(rca.get("algorithm_used"), "pagerank")
        self.assertIn("rcaeval_breakdown", rca)

    def test_rcaeval_package_import(self):
        import RCAEval
        self.assertIsNotNone(RCAEval)
        self.assertTrue(self.rcaeval.rcaeval_pkg_available)

    def test_opentelemetry_sdk_integration(self):
        from opentelemetry import trace
        self.assertTrue(self.telemetry.has_otel_sdk)
        self.assertIsNotNone(trace.get_tracer_provider())


if __name__ == "__main__":
    unittest.main()
