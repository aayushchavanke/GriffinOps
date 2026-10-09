import time
import threading
from typing import Optional, List
from griffinops.db.storage import storage

class BackgroundAlertWatchdog:
    """
    Automated Background Watchdog Daemon for GriffinOps.
    Continuously monitors PyTorch TCN failure forecasts and incoming telemetry streams.
    When a pre-mortem hazard or metric breach is detected, it automatically dispatches
    notifications to registered developers.
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
        self.cooldown_seconds: float = 20.0
        self.dispatch_log: List[dict] = storage.load_dispatch_logs(limit=20)
        persisted_profile = storage.load_profile()
        dev_emails = persisted_profile.get("developer_emails") if persisted_profile else None
        if dev_emails:
            self.registered_developer_emails = [e.strip() for e in dev_emails if e and "@" in e]
        elif persisted_profile and persisted_profile.get("email"):
            self.registered_developer_emails = [persisted_profile["email"].strip()]
        else:
            self.registered_developer_emails = ["sre-lead@company.com"]

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _watchdog_loop(self):
        while self.is_running:
            try:
                self._evaluate_and_dispatch()
            except Exception:
                pass
            time.sleep(3)

    def _evaluate_and_dispatch(self, force_trigger: bool = False):
        active_fault = self.fault_simulator.get_status().get("fault") if self.fault_simulator else None
        telemetry = self.telemetry_ingestor.generate_synthetic_telemetry(sequence_length=60, active_fault=active_fault)
        
        if not telemetry:
            return None

        z_scores = self.normalizer.compute_z_scores(telemetry)
        min_len = min([len(df) for df in telemetry.values()])
        tensor, service_names = self.normalizer.to_tensor_format(z_scores, sequence_length=min(30, max(3, min_len)))
        tcn_results = self.tcn_predictor.predict(tensor, service_names=service_names) if tensor is not None and len(service_names) > 0 else {"services": {}}
        
        # Detect anomaly condition
        has_anomaly = tcn_results.get("system_anomaly_detected") or (active_fault is not None) or force_trigger
        
        if not has_anomaly:
            for svc, df in telemetry.items():
                if not df.empty:
                    latest = df.iloc[-1]
                    if latest.get("latency_ms", 0) >= 200 or latest.get("status_code", 200) >= 400 or latest.get("error_rate", 0) > 0.05:
                        has_anomaly = True
                        break

        if has_anomaly:
            now = time.time()
            if now - self.last_alert_time >= self.cooldown_seconds or force_trigger:
                report = self.rca_engine.analyze_root_cause(tcn_results, z_scores, active_fault=active_fault)
                
                # Dispatch Slack alert if webhook configured
                slack_res = self.notifier.dispatch_slack_if_anomaly(tcn_results, audit_report=report)
                if slack_res:
                    slack_entry = {
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(now)),
                        "report_id": report.get("report_id"),
                        "target_service": report.get("root_cause_analysis", {}).get("service"),
                        "recipient": "Slack Webhook",
                        "status": slack_res.get("status"),
                        "preview_path": None
                    }
                    self.dispatch_log.insert(0, slack_entry)
                    storage.save_dispatch_log(slack_entry)

                # Dynamically retrieve registered recipients from runtime state if updated
                recipients = list(self.registered_developer_emails) if self.registered_developer_emails else []
                email_alerts_active = True
                try:
                    from griffinops.api import routes
                    if routes and hasattr(routes, "USER_PROFILE_STATE"):
                        email_alerts_active = routes.USER_PROFILE_STATE.get("email_alerts_enabled", True)
                        p_emails = routes.USER_PROFILE_STATE.get("developer_emails", [])
                        if p_emails:
                            recipients = [e.strip() for e in p_emails if e and "@" in e]
                        elif routes.USER_PROFILE_STATE.get("email"):
                            recipients = [routes.USER_PROFILE_STATE["email"].strip()]
                except Exception:
                    pass

                if email_alerts_active and recipients:
                    for email in recipients:
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
                        storage.save_dispatch_log(log_entry)
                
                self.last_alert_time = now
                return report
        return None

    def get_dispatch_history(self) -> List[dict]:
        return self.dispatch_log[:20]
