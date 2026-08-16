"""
LagRCA: Lag-Aware Spatio-Temporal Causal Inference Engine for Microservices.
Based on ACM FSE 2026 Distinguished Paper Award:
"Bridging the Delay: Lag-Aware Spatio-Temporal Causal Inference for Microservice Root Cause Analysis"
(Zhang et al. FSE 2026 / Nankai, Tsinghua, Alibaba Group)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from scipy.signal import correlate


class LagRCAEngine:
    """
    LagRCA Engine calculating temporal lag cross-correlations over distributed trace spans
    and metrics to resolve microservice propagation delays (tau in [0, 90s]).
    """
    def __init__(self, max_lag_steps: int = 15, sample_interval_sec: float = 5.0):
        self.max_lag_steps = max_lag_steps
        self.sample_interval_sec = sample_interval_sec

    def compute_spatio_temporal_lag_correlation(
        self,
        telemetry_by_service: Dict[str, pd.DataFrame],
        primary_metric: str = "latency_ms"
    ) -> Tuple[Dict[Tuple[str, str], float], Dict[Tuple[str, str], float]]:
        """
        Calculates pairwise Lag-Aware Cross-Correlation:
        Lag-Score(u -> v) = max_{tau in [0, tau_max]} CrossCorr(X_u(t), X_v(t + tau))
        Returns:
            - lag_scores: Dict[(svc_u, svc_v)] -> max_correlation_score
            - optimal_lags: Dict[(svc_u, svc_v)] -> lag_time_sec
        """
        services = list(telemetry_by_service.keys())
        lag_scores = {}
        optimal_lags = {}

        if len(services) < 2:
            return lag_scores, optimal_lags

        for i, u in enumerate(services):
            df_u = telemetry_by_service.get(u, pd.DataFrame())
            if df_u.empty or primary_metric not in df_u.columns:
                continue
            x_u = df_u[primary_metric].values.astype(float)
            x_u_norm = x_u - np.mean(x_u)
            std_u = np.std(x_u) + 1e-6

            for j, v in enumerate(services):
                if i == j:
                    continue
                df_v = telemetry_by_service.get(v, pd.DataFrame())
                if df_v.empty or primary_metric not in df_v.columns:
                    continue
                x_v = df_v[primary_metric].values.astype(float)
                x_v_norm = x_v - np.mean(x_v)
                std_v = np.std(x_v) + 1e-6

                min_len = min(len(x_u_norm), len(x_v_norm))
                if min_len < 5:
                    continue

                u_vec = x_u_norm[-min_len:]
                v_vec = x_v_norm[-min_len:]

                corr = correlate(v_vec, u_vec, mode='full') / (std_u * std_v * min_len)
                lags = np.arange(-min_len + 1, min_len)

                # Filter valid positive lag window tau in [0, max_lag_steps]
                valid_mask = (lags >= 0) & (lags <= self.max_lag_steps)
                if not np.any(valid_mask):
                    continue

                valid_corrs = corr[valid_mask]
                valid_lags = lags[valid_mask]

                best_idx = np.argmax(valid_corrs)
                max_score = round(float(valid_corrs[best_idx]), 4)
                best_lag_sec = round(float(valid_lags[best_idx] * self.sample_interval_sec), 1)

                lag_scores[(u, v)] = max(0.0, max_score)
                optimal_lags[(u, v)] = best_lag_sec

        return lag_scores, optimal_lags
