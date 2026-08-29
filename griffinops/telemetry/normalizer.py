import torch
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from griffinops.telemetry.ingestion import MICROSERVICES, SIGNALS

class ZScoreNormalizer:
    """
    Transforms raw microservice telemetry metrics into application-agnostic Z-scores:
    z = (x - mean) / (std + epsilon)
    
    Includes Robust Variance Smoothing to handle flat metric streams and zero-variance cold starts.
    """
    def __init__(self, window_size: int = 30, epsilon: float = 1e-5):
        self.window_size = window_size
        self.epsilon = epsilon
        self.services = MICROSERVICES
        self.signals = SIGNALS
        self.stats: Dict[str, Dict[str, Dict[str, float]]] = {}
        self._init_default_stats()

    def _init_default_stats(self):
        for svc in self.services:
            self.stats[svc] = {
                "latency_ms": {"mean": 50.0, "std": 10.0},
                "traffic_rps": {"mean": 150.0, "std": 35.0},
                "error_rate": {"mean": 0.002, "std": 0.001},
                "cpu_percent": {"mean": 40.0, "std": 8.0},
                "memory_percent": {"mean": 50.0, "std": 7.0},
            }

    def compute_z_scores(self, telemetry_by_service: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        z_scores_by_service = {}

        for svc, df in telemetry_by_service.items():
            z_df = pd.DataFrame()
            if "timestamp" in df.columns:
                z_df["timestamp"] = df["timestamp"]

            svc_stats = self.stats.get(svc, {})

            for sig in self.signals:
                if sig in df.columns:
                    series = df[sig]
                    if len(series) >= 3:
                        # Robust Median Absolute Deviation (MAD) Modified Z-Score
                        roll_median = series.rolling(window=self.window_size, min_periods=3).median()
                        abs_diff = (series - roll_median).abs()
                        roll_mad = abs_diff.rolling(window=self.window_size, min_periods=3).median()
                        
                        # 0.6745 factor aligns MAD scale with standard deviation under normal distribution
                        z_series = 0.6745 * (series - roll_median) / (roll_mad + self.epsilon)
                        
                        # Fallback for static baseline stats
                        med_val = svc_stats.get(sig, {}).get("mean", 50.0)
                        std_val = svc_stats.get(sig, {}).get("std", 10.0)
                        z_fallback = 0.6745 * (series - med_val) / (std_val + self.epsilon)
                        z_series = z_series.fillna(z_fallback)
                    else:
                        med_val = svc_stats.get(sig, {}).get("mean", 50.0)
                        std_val = svc_stats.get(sig, {}).get("std", 10.0)
                        z_series = 0.6745 * (series - med_val) / (std_val + self.epsilon)

                    # Clip extreme outliers for numerical stability
                    z_series = np.clip(z_series.astype(float), -10.0, 10.0)
                    z_df[sig] = z_series

            z_scores_by_service[svc] = z_df

        return z_scores_by_service

    def to_tensor_format(self, z_scores_by_service: Dict[str, pd.DataFrame], sequence_length: int = 30) -> Tuple[torch.Tensor, List[str]]:
        service_names = list(z_scores_by_service.keys())
        if not service_names:
            return torch.zeros((0, len(self.signals), sequence_length), dtype=torch.float32), []

        num_services = len(service_names)
        num_features = len(self.signals)
        tensor_data = np.zeros((num_services, num_features, sequence_length), dtype=np.float32)

        for s_idx, svc in enumerate(service_names):
            df = z_scores_by_service.get(svc, pd.DataFrame())
            for f_idx, sig in enumerate(self.signals):
                if sig in df.columns:
                    vals = df[sig].values
                    if len(vals) >= sequence_length:
                        seq_vals = vals[-sequence_length:]
                    else:
                        seq_vals = np.pad(vals, (sequence_length - len(vals), 0), 'edge') if len(vals) > 0 else np.zeros(sequence_length)
                    tensor_data[s_idx, f_idx, :] = seq_vals

        return torch.tensor(tensor_data, dtype=torch.float32), service_names

    def quantize_telemetry_tokens(
        self,
        z_scores_by_service: Dict[str, pd.DataFrame],
        num_bins: int = 64,
        z_min: float = -6.0,
        z_max: float = 6.0
    ) -> Dict[str, np.ndarray]:
        """
        Quantized Telemetry Tokenizer (Chronos Foundation Model - Amazon Research 2024-2025).
        Discretizes continuous metric standard deviations into uniform categorical token bins [0..num_bins-1]
        centered around baseline zero. Enables zero-shot generalization across heterogeneous microservice domains.
        """
        tokenized_by_service = {}
        for svc, df in z_scores_by_service.items():
            numeric_cols = [c for c in self.signals if c in df.columns]
            if not numeric_cols:
                continue
            z_matrix = df[numeric_cols].values # [TimeSteps, NumSignals]
            # Linear quantization to discrete token IDs
            norm_val = np.clip((z_matrix - z_min) / (z_max - z_min), 0.0, 1.0)
            token_ids = np.floor(norm_val * (num_bins - 1)).astype(np.int32)
            tokenized_by_service[svc] = token_ids
        return tokenized_by_service

    def compute_zero_shot_cold_start_score(self, token_ids: np.ndarray, num_bins: int = 64) -> float:
        """
        Zero-shot anomaly scoring based on token entropy distance from nominal center bins.
        Provides instant cold-start anomaly detection for newly registered API keys/websites.
        """
        if token_ids is None or len(token_ids) == 0:
            return 0.0
        center_bin = num_bins // 2
        # Calculate token distance from nominal baseline center
        tail_distance = np.abs(token_ids - center_bin) / center_bin
        max_tail_breach = float(np.max(tail_distance))
        # Map to calibrated anomaly probability [0.0, 1.0]
        return round(float(np.clip(max_tail_breach * 1.25 - 0.2, 0.0, 1.0)), 4)
