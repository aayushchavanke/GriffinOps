import os
import sys
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from griffinops.rca.lag_rca import LagRCAEngine
from griffinops.rca.granger_causality import GrangerCausalityEngine
from griffinops.rca.causal_engine import CausalRCAEngine


class TestLagRCAAndGrangerCausality(unittest.TestCase):

    def setUp(self):
        self.lag_engine = LagRCAEngine()
        self.granger_engine = GrangerCausalityEngine()
        self.causal_engine = CausalRCAEngine()

    def test_lag_rca_cross_correlation(self):
        # Create a signal where service B lags service A by 2 steps
        t = np.linspace(0, 10, 30)
        signal_a = np.sin(t) + np.random.normal(0, 0.05, 30)
        signal_b = np.roll(signal_a, 2)  # Service B lags service A

        telemetry = {
            "service-a": pd.DataFrame({"timestamp": t, "latency_ms": signal_a}),
            "service-b": pd.DataFrame({"timestamp": t, "latency_ms": signal_b})
        }

        lag_scores, optimal_lags = self.lag_engine.compute_spatio_temporal_lag_correlation(telemetry)
        self.assertIn(("service-a", "service-b"), lag_scores)
        self.assertGreater(lag_scores[("service-a", "service-b")], 0.0)

    def test_granger_causality_matrix(self):
        t = np.linspace(0, 10, 40)
        signal_a = np.sin(t)
        signal_b = np.sin(t - 0.5)

        telemetry = {
            "service-a": pd.DataFrame({"timestamp": t, "latency_ms": signal_a}),
            "service-b": pd.DataFrame({"timestamp": t, "latency_ms": signal_b})
        }

        f_scores, p_values = self.granger_engine.compute_granger_causality_matrix(telemetry)
        self.assertIsInstance(f_scores, dict)
        self.assertIsInstance(p_values, dict)

    def test_end_to_end_2026_sota_rca(self):
        df_pay = pd.DataFrame({"timestamp": range(20), "latency_ms": np.random.normal(5.0, 1.0, 20)})
        df_fe = pd.DataFrame({"timestamp": range(20), "latency_ms": np.random.normal(0.5, 0.1, 20)})

        z_scores = {"paymentservice": df_pay, "frontend-service": df_fe}
        tcn_results = {"services": {"paymentservice": {"failure_probability": 0.92}}}

        report = self.causal_engine.analyze_root_cause(
            tcn_results=tcn_results,
            z_scores_by_service=z_scores,
            algorithm="composite"
        )

        rca = report.get("root_cause_analysis", {})
        self.assertIn("rcaeval_breakdown", rca)
        breakdown = rca.get("rcaeval_breakdown", {})
        self.assertIn("paymentservice", breakdown)
        self.assertIn("granger_out_influence", breakdown["paymentservice"])
        self.assertIn("lag_rca_offset_sec", breakdown["paymentservice"])


if __name__ == "__main__":
    unittest.main()
