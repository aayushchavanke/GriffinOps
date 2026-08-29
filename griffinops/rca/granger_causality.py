"""
Granger Causality Discovery Engine for Microservice Root Cause Analysis.
Based on RCASage (2026): "AI-Driven Root Cause Analysis Framework for Distributed Microservices Architecture"
Uses Pairwise Granger Causality F-tests to prove directional causal dependencies (X -> Y).
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple

try:
    from statsmodels.tsa.stattools import grangercausalitytests
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False


class GrangerCausalityEngine:
    """
    Granger Causality Discovery Engine testing if past time-series values of service X
    provide statistically significant predictive power for future failures in service Y.
    """
    def __init__(self, max_lag: int = 3, significance_level: float = 0.05):
        self.max_lag = max_lag
        self.significance_level = significance_level

    def compute_granger_causality_matrix(
        self,
        telemetry_by_service: Dict[str, pd.DataFrame],
        primary_metric: str = "latency_ms"
    ) -> Tuple[Dict[Tuple[str, str], float], Dict[Tuple[str, str], float]]:
        """
        Computes Granger F-statistics and p-values for all service pairs (X -> Y).
        Returns:
            - f_scores: Dict[(svc_x, svc_y)] -> F_stat
            - p_values: Dict[(svc_x, svc_y)] -> p_value
        """
        services = list(telemetry_by_service.keys())
        f_scores = {}
        p_values = {}

        if not HAS_STATSMODELS or len(services) < 2:
            return f_scores, p_values

        for i, x_svc in enumerate(services):
            df_x = telemetry_by_service.get(x_svc, pd.DataFrame())
            if df_x.empty or primary_metric not in df_x.columns:
                continue
            x_series = df_x[primary_metric].values

            for j, y_svc in enumerate(services):
                if i == j:
                    continue
                df_y = telemetry_by_service.get(y_svc, pd.DataFrame())
                if df_y.empty or primary_metric not in df_y.columns:
                    continue
                y_series = df_y[primary_metric].values

                min_len = min(len(x_series), len(y_series))
                if min_len < 10:
                    continue

                # Prepare Granger 2D array [Y, X] -> tests if X Granger-causes Y
                data_matrix = np.column_stack((y_series[-min_len:], x_series[-min_len:]))

                # Add tiny jitter variance if series is completely flat to prevent singular matrix error
                if np.std(data_matrix[:, 0]) < 1e-6:
                    data_matrix[:, 0] += np.random.normal(0, 1e-4, size=min_len)
                if np.std(data_matrix[:, 1]) < 1e-6:
                    data_matrix[:, 1] += np.random.normal(0, 1e-4, size=min_len)

                try:
                    res = grangercausalitytests(data_matrix, maxlag=min(self.max_lag, min_len // 4), verbose=False)
                    # Extract best lag F-statistic and p-value
                    best_f = 0.0
                    min_p = 1.0
                    for lag_k, test_dict in res.items():
                        f_stat, p_val, _, _ = test_dict[0]['params_ftest']
                        if p_val < min_p:
                            min_p = float(p_val)
                            best_f = float(f_stat)

                    f_scores[(x_svc, y_svc)] = round(best_f, 4)
                    p_values[(x_svc, y_svc)] = round(min_p, 4)
                except Exception:
                    pass

        return f_scores, p_values
