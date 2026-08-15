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
                    if len(series) >= self.window_size:
                        roll_mean = series.rolling(window=self.window_size, min_periods=5).mean()
                        roll_std = series.rolling(window=self.window_size, min_periods=5).std().fillna(1.0)
                        
                        # Apply epsilon variance smoothing to prevent divide-by-zero
                        z_series = (series - roll_mean) / (roll_std + self.epsilon)
                        
                        mean_val = svc_stats.get(sig, {}).get("mean", 50.0)
                        std_val = svc_stats.get(sig, {}).get("std", 10.0)
                        z_fallback = (series - mean_val) / (std_val + self.epsilon)
                        z_series = z_series.fillna(z_fallback)
                    else:
                        mean_val = svc_stats.get(sig, {}).get("mean", 50.0)
                        std_val = svc_stats.get(sig, {}).get("std", 10.0)
                        z_series = (series - mean_val) / (std_val + self.epsilon)

                    # Clip extreme infinite outliers for numerical stability
                    z_series = np.clip(z_series.astype(float), -10.0, 10.0)
                    z_df[sig] = z_series

            z_scores_by_service[svc] = z_df

        return z_scores_by_service

    def to_tensor_format(self, z_scores_by_service: Dict[str, pd.DataFrame], sequence_length: int = 30) -> torch.Tensor:
        num_services = len(self.services)
        num_features = len(self.signals)
        
        tensor_data = np.zeros((num_services, num_features, sequence_length), dtype=np.float32)

        for s_idx, svc in enumerate(self.services):
            df = z_scores_by_service.get(svc, pd.DataFrame())
            for f_idx, sig in enumerate(self.signals):
                if sig in df.columns:
                    vals = df[sig].values
                    if len(vals) >= sequence_length:
                        seq_vals = vals[-sequence_length:]
                    else:
                        seq_vals = np.pad(vals, (sequence_length - len(vals), 0), 'edge')
                    tensor_data[s_idx, f_idx, :] = seq_vals

        return torch.tensor(tensor_data, dtype=torch.float32)
