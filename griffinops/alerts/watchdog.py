import time
import threading
from typing import Optional, List

class BackgroundAlertWatchdog:
    """
    Automated Background Watchdog Daemon for GriffinOps.
    Continuously monitors PyTorch TCN failure forecasts. When a pre-mortem hazard
    trajectory is predicted, it automatically dispatches email notifications to developers
    in the background immediately—without requiring manual UI clicks.
    """
    def __init__(self, telemetry_ingestor, normalizer, tcn_predictor, rca_engine, fault_simulator, notifier):
        self.telemetry_ingestor = telemetry_ingestor
        self.normalizer = normalizer
        self.tcn_predictor = tcn_predictor
        self.rca_engine = rca_engine
        self.fault_simulator = fault_simulator
        self.notifier = notifier
        
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self.last_alert_time: float = 0.0
        self.cooldown_seconds: float = 45.0 # Prevent duplicate email spam during single fault window
        self.dispatch_log: List[dict] = []
        self.registered_developer_emails = ["griffinops26@gmail.com", "sre-dev@sies.edu"]

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.is_running = False

    def _watchdog_loop(self):
        while self.is_running:
            try:
                self._evaluate_and_dispatch()
            except Exception:
                pass
            time.sleep(5)

    def _evaluate_and_dispatch(self):
        active_fault = self.fault_simulator.get_status().get("fault")
        telemetry = self.telemetry_ingestor.generate_synthetic_telemetry(sequence_length=60, active_fault=active_fault)
        z_scores = self.normalizer.compute_z_scores(telemetry)
        tensor, service_names = self.normalizer.to_tensor_format(z_scores, sequence_length=30)
        tcn_results = self.tcn_predictor.predict(tensor, service_names=service_names)
        
        # Check if an anomaly breach is predicted
        if tcn_results.get("system_anomaly_detected") or (active_fault is not None):
            now = time.time()
            if now - self.last_alert_time >= self.cooldown_seconds:
                # Generate Pre-Mortem Audit Report
                report = self.rca_engine.analyze_root_cause(tcn_results, z_scores, active_fault=active_fault)
                
                # Automatically dispatch background email alerts to all registered developer emails
                for email in self.registered_developer_emails:
                    email_res = self.notifier.send_email_notification(report, recipient_email=email)
                    
                    log_entry = {
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(now)),
                        "report_id": report.get("report_id"),
                        "target_service": report.get("root_cause_analysis", {}).get("service"),
                        "recipient": email,
                        "status": email_res.get("status"),
                        "preview_path": email_res.get("preview_path")
                    }
                    self.dispatch_log.insert(0, log_entry)
                
                self.last_alert_time = now

    def get_dispatch_history(self) -> List[dict]:
        return self.dispatch_log[:20]
