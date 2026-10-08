import os
import json
import time
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict

class DualNotifier:
    """
    Handles Multi-Channel Alert Delivery for GriffinOps Pre-Mortem Audit Reports:
    - Slack Webhook Integration
    - Real Free Email Sending Engine:
      - Brevo (Sendinblue API - Free 300 emails/day)
      - Resend (REST API - Free 3,000 emails/month)
      - SendGrid (SMTP - Free 100 emails/day)
      - Standard SMTP / Gmail SMTP (Free 500 emails/day)
      - Local HTML File Preview
    """
    def __init__(
        self,
        slack_webhook_url: Optional[str] = None,
        smtp_host: Optional[str] = None,
        smtp_port: int = 587,
        smtp_user: Optional[str] = None,
        smtp_pass: Optional[str] = None,
        brevo_api_key: Optional[str] = None,
        resend_api_key: Optional[str] = None
    ):
        self.slack_webhook_url = slack_webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        self.slack_last_state: str = "HEALTHY"
        self.slack_last_alert_time: float = 0.0
        self.slack_cooldown_seconds: float = 60.0
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", str(smtp_port)))
        self.smtp_user = smtp_user or os.getenv("SMTP_USER", "alerts@griffinops.io")
        self.smtp_pass = smtp_pass or os.getenv("SMTP_PASS")
        self.brevo_api_key = brevo_api_key or os.getenv("BREVO_API_KEY")
        self.resend_api_key = resend_api_key or os.getenv("RESEND_API_KEY")
        
        self.email_preview_dir = os.path.join(os.getcwd(), "email_previews")
        os.makedirs(self.email_preview_dir, exist_ok=True)

    def send_slack_alert(self, audit_report: dict) -> dict:
        rca = audit_report.get("root_cause_analysis", {})
        commit = audit_report.get("ci_cd_correlation", {})
        service_name = rca.get("service") or audit_report.get("target_service", "Unknown Microservice")
        fail_prob_pct = audit_report.get("failure_probability_pct", "N/A")
        
        payload = {
            "text": f"🚨 GriffinOps Alert: High Crash Risk on {service_name} ({fail_prob_pct})",
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"🚨 GriffinOps Alert: {audit_report.get('report_id')}", "emoji": True}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*System Status:*\n`{audit_report.get('system_status')}`"},
                        {"type": "mrkdwn", "text": f"*Forecasted TTF:*\n*{audit_report.get('forecasted_time_to_failure_human')}*"}
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Affected Service:*\n`{service_name}`"},
                        {"type": "mrkdwn", "text": f"*Failure Probability:*\n*{fail_prob_pct}*"}
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Root Cause Service:*\n`{rca.get('service')}`"},
                        {"type": "mrkdwn", "text": f"*Primary Metric Breach:*\n`{rca.get('primary_metric')}` (+{rca.get('max_z_score_deviation')} σ)"}
                    ]
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Suggested Remediation:*\n```{audit_report.get('suggested_action')}```"}
                }
            ]
        }
        
        if self.slack_webhook_url:
            try:
                resp = requests.post(self.slack_webhook_url, json=payload, timeout=4.0)
                return {"status": "SUCCESS", "slack_response_code": resp.status_code}
            except Exception as e:
                return {"status": "ERROR", "message": str(e), "payload": payload}
        
        return {"status": "SIMULATED", "payload": payload}

    def send_slack_test_alert(self, target_url: Optional[str] = None) -> dict:
        url = (target_url or self.slack_webhook_url or "").strip()
        if not url:
            return {"status": "ERROR", "message": "No Slack Webhook URL provided or configured."}
        
        payload = {
            "text": "🚨 GriffinOps Test Alert: Slack Webhook Connected Successfully!",
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "🔔 GriffinOps Slack Webhook Verification", "emoji": True}
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Your Slack webhook is successfully configured with *GriffinOps AI SRE Copilot*. Autonomous pre-mortem alerts will appear here when microservice anomalies or threshold breaches are forecasted."
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": "*Service (Sample):*\n`checkout-service`"},
                        {"type": "mrkdwn", "text": "*Failure Probability:*\n*86.4% (CRITICAL)*"},
                        {"type": "mrkdwn", "text": "*Forecasted TTF:*\n*T-2m 30s (150s)*"},
                        {"type": "mrkdwn", "text": "*Test Status:*\n`VERIFIED`"}
                    ]
                }
            ]
        }
        try:
            resp = requests.post(url, json=payload, timeout=4.0)
            if resp.status_code == 200:
                return {"status": "SUCCESS", "message": "Test alert delivered to Slack!", "code": resp.status_code}
            return {"status": "ERROR", "message": f"Slack rejected webhook with HTTP {resp.status_code}: {resp.text}", "code": resp.status_code}
        except Exception as e:
            return {"status": "ERROR", "message": f"Failed to reach Slack webhook: {str(e)}"}

    def dispatch_slack_if_anomaly(self, tcn_results: dict, audit_report: Optional[dict] = None) -> Optional[dict]:
        if not self.slack_webhook_url:
            return None
            
        sys_anomaly = bool(tcn_results.get("system_anomaly_detected", False))
        max_prob = float(tcn_results.get("max_failure_prob", 0.0))
        is_at_risk = sys_anomaly or (max_prob >= 0.5)
        
        if not is_at_risk:
            self.slack_last_state = "HEALTHY"
            return None
            
        now = time.time()
        state_transition = (self.slack_last_state == "HEALTHY")
        cooldown_elapsed = (now - self.slack_last_alert_time >= self.slack_cooldown_seconds)
        
        if not (state_transition or cooldown_elapsed):
            return None  # Suppress duplicate alert during cooldown
            
        self.slack_last_state = "AT_RISK"
        self.slack_last_alert_time = now
        
        highest_svc = tcn_results.get("highest_risk_service") or "system"
        svc_data = tcn_results.get("services", {}).get(highest_svc, {})
        prob = svc_data.get("failure_probability", max_prob)
        ttf_sec = svc_data.get("predicted_time_to_failure_sec", 0)
        
        if ttf_sec > 0:
            mins = ttf_sec // 60
            secs = ttf_sec % 60
            ttf_human = f"T-{f'{mins}m ' if mins > 0 else ''}{secs}s"
        else:
            ttf_human = "Imminent (< 30s)"
            
        report_payload = {
            "report_id": audit_report.get("report_id") if audit_report else f"GO-ALERT-{int(now) % 100000}",
            "system_status": "SEV-1 CRITICAL HAZARD" if max_prob >= 0.7 else "SEV-2 WARNING",
            "forecasted_time_to_failure_human": ttf_human,
            "target_service": highest_svc,
            "failure_probability_pct": f"{round(prob * 100, 1)}%",
            "root_cause_analysis": {
                "service": highest_svc,
                "primary_metric": svc_data.get("breached_signals", [{}])[0].get("signal", "forecast_anomaly") if svc_data.get("breached_signals") else "latency_ms",
                "max_z_score_deviation": svc_data.get("max_z_score", 3.0)
            },
            "suggested_action": audit_report.get("suggested_action") if audit_report else f"Scale replicas for {highest_svc} and inspect container resource allocation."
        }
        
        return self.send_slack_alert(report_payload)

    def update_credentials(
        self,
        slack_webhook_url: Optional[str] = None,
        smtp_host: Optional[str] = None,
        smtp_port: int = 587,
        smtp_user: Optional[str] = None,
        smtp_pass: Optional[str] = None,
        brevo_api_key: Optional[str] = None,
        resend_api_key: Optional[str] = None
    ):
        if slack_webhook_url is not None: self.slack_webhook_url = slack_webhook_url.strip() or None
        if smtp_host is not None: self.smtp_host = smtp_host
        if smtp_port is not None: self.smtp_port = int(smtp_port)
        if smtp_user is not None: self.smtp_user = smtp_user
        if smtp_pass is not None: self.smtp_pass = smtp_pass
        if brevo_api_key is not None: self.brevo_api_key = brevo_api_key
        if resend_api_key is not None: self.resend_api_key = resend_api_key

    def get_config_status(self) -> dict:
        return {
            "has_slack": bool(self.slack_webhook_url),
            "slack_webhook_url": self.slack_webhook_url or "",
            "has_brevo": bool(self.brevo_api_key),
            "has_resend": bool(self.resend_api_key),
            "has_smtp": bool(self.smtp_host and self.smtp_user and self.smtp_pass),
            "smtp_host": self.smtp_host or "smtp.gmail.com",
            "smtp_port": self.smtp_port,
            "smtp_user": self.smtp_user or "alerts@griffinops.io",
            "active_provider": "BREVO_API" if self.brevo_api_key else ("RESEND_API" if self.resend_api_key else ("SMTP_SERVER" if (self.smtp_host and self.smtp_user and self.smtp_pass) else "LOCAL_HTML_PREVIEW"))
        }

    def send_email_notification(self, audit_report: dict, recipient_email: str) -> dict:
        report_id = audit_report.get("report_id", "GO-REPORT")
        rca = audit_report.get("root_cause_analysis", {})
        commit = audit_report.get("ci_cd_correlation", {})
        impact = audit_report.get("business_impact", {})
        sev_level = audit_report.get("severity_level", "CRITICAL (SEV-1)")
        time_left = audit_report.get("forecasted_time_to_failure_human", "4m 00s")
        remediation_cmd = audit_report.get("remediation_command", f"kubectl rollout undo deployment/{rca.get('service', 'target-service')} -n production")
        
        subject = f"🚨 [{sev_level}] PRE-MORTEM OUTAGE ALERT: {rca.get('service')} - Time Left: {time_left}"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <style>
            body {{ font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; background-color: #0b0f19; color: #f8fafc; margin: 0; padding: 24px; }}
            .container {{ max-width: 680px; margin: 0 auto; background: #121827; border: 1px solid rgba(245,158,11,0.3); border-radius: 16px; padding: 32px; box-shadow: 0 20px 50px rgba(0,0,0,0.8); }}
            .header {{ display: flex; align-items: center; justify-content: space-between; border-bottom: 2px solid #e11d48; padding-bottom: 18px; margin-bottom: 24px; }}
            .brand {{ color: #f59e0b; font-size: 24px; font-weight: 800; margin: 0; letter-spacing: -0.5px; }}
            .badge-sev {{ background: linear-gradient(135deg, #e11d48, #9f1239); color: white; padding: 6px 16px; border-radius: 20px; font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: 1px; display: inline-block; }}
            
            .banner-countdown {{ background: rgba(225,29,72,0.12); border: 1.5px solid #e11d48; color: #fb7185; padding: 18px; border-radius: 12px; text-align: center; margin-bottom: 24px; }}
            .countdown-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: #fda4af; margin-bottom: 4px; font-weight: 700; }}
            .countdown-time {{ font-size: 28px; font-weight: 900; color: #ffffff; text-shadow: 0 0 20px rgba(225,29,72,0.5); }}
            
            .impact-card {{ background: linear-gradient(135deg, rgba(245,158,11,0.1), rgba(180,83,9,0.05)); border: 1px solid rgba(245,158,11,0.4); border-radius: 12px; padding: 20px; margin-bottom: 24px; }}
            .card-title {{ color: #f59e0b; font-size: 13px; font-weight: 800; text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }}
            
            .metric-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 12px; }}
            .metric-box {{ background: #0b0f19; padding: 12px 16px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.06); }}
            .metric-label {{ color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: 0.8px; display: block; margin-bottom: 4px; }}
            .metric-value {{ color: #ffffff; font-size: 16px; font-weight: 700; }}
            .metric-value.highlight {{ color: #f43f5e; }}
            .metric-value.warning {{ color: #fbbf24; }}
            
            .code-box {{ background: #070a11; border-left: 4px solid #3b82f6; padding: 16px; font-family: 'Consolas', 'Courier New', monospace; font-size: 13px; color: #93c5fd; border-radius: 6px; line-height: 1.6; margin-bottom: 20px; overflow-x: auto; }}
            .action-box {{ background: rgba(16,185,129,0.1); border: 1.5px solid #10b981; color: #d1fae5; padding: 20px; border-radius: 12px; margin-bottom: 24px; line-height: 1.6; }}
            .cmd-snippet {{ background: #042f2e; border: 1px solid #14b8a6; color: #2dd4bf; padding: 10px 14px; font-family: monospace; font-size: 13px; border-radius: 6px; margin-top: 10px; word-break: break-all; }}
            
            .footer {{ text-align: center; color: #64748b; font-size: 12px; margin-top: 32px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 18px; line-height: 1.5; }}
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1 class="brand">🦅 GriffinOps AI SRE Copilot</h1>
              <span class="badge-sev">{sev_level}</span>
            </div>
            
            <!-- TIME LEFT COUNTDOWN BANNER -->
            <div class="banner-countdown">
              <div class="countdown-label">⏳ ESTIMATED TIME REMAINING BEFORE TOTAL SYSTEM CRASH</div>
              <div class="countdown-time">{time_left}</div>
            </div>
            
            <!-- ESTIMATED BUSINESS IMPACT CARD -->
            <div class="impact-card">
              <div class="card-title">📉 ESTIMATED BUSINESS & FINANCIAL IMPACT</div>
              <div class="metric-grid">
                <div class="metric-box">
                  <span class="metric-label">Financial Risk Rate</span>
                  <span class="metric-value highlight">{impact.get('estimated_loss_per_minute', '$450/min')}</span>
                </div>
                <div class="metric-box">
                  <span class="metric-label">Affected Customer Sessions</span>
                  <span class="metric-value warning">{impact.get('affected_active_user_sessions', '14,200 active users')}</span>
                </div>
              </div>
              <div style="font-size: 13px; color: #cbd5e1; font-weight: 500;">
                <strong>Impact Summary:</strong> {impact.get('summary', 'High revenue loss risk across active customer sessions.')}
              </div>
            </div>
            
            <!-- ROOT CAUSE DIAGNOSIS -->
            <div class="impact-card" style="background: rgba(30,41,59,0.5); border-color: rgba(148,163,184,0.2);">
              <div class="card-title" style="color: #60a5fa;">🔍 ROOT CAUSE DIAGNOSIS (PyTorch TCN & RCAEval)</div>
              <div class="metric-grid">
                <div class="metric-box">
                  <span class="metric-label">Faulty Microservice</span>
                  <span class="metric-value">{rca.get('service', 'checkoutservice')}</span>
                </div>
                <div class="metric-box">
                  <span class="metric-label">Target API Endpoint</span>
                  <span class="metric-value">{rca.get('api_endpoint', '/api/checkout')}</span>
                </div>
                <div class="metric-box">
                  <span class="metric-label">Primary Metric Breach</span>
                  <span class="metric-value warning">{rca.get('primary_metric', 'latency_ms')}</span>
                </div>
                <div class="metric-box">
                  <span class="metric-label">Anomaly Deviation</span>
                  <span class="metric-value highlight">+{rca.get('max_z_score_deviation', 3.5)} σ Z-Score</span>
                </div>
              </div>
            </div>
            
            <!-- CORRELATED CI/CD COMMIT -->
            <div style="margin-bottom: 20px;">
              <div style="font-size: 12px; font-weight: 800; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">
                💻 CORRELATED CI/CD DEPLOYMENT COMMIT
              </div>
              <div class="code-box">
                <strong>Commit ID:</strong> {commit.get('commit_id')}<br/>
                <strong>Author:</strong> {commit.get('author')}<br/>
                <strong>Message:</strong> {commit.get('message')}<br/>
                <strong>Changed Files:</strong> {", ".join(commit.get('changed_files', []))}
              </div>
            </div>
            
            <!-- ACTIONABLE REMEDIATION SUGGESTION -->
            <div class="action-box">
              <div style="font-weight: 800; font-size: 15px; color: #34d399; margin-bottom: 6px;">
                🛠️ ACTIONABLE SRE REMEDIATION SUGGESTIONS:
              </div>
              <div style="font-size: 14px; margin-bottom: 10px;">
                {audit_report.get('suggested_action')}
              </div>
              <div style="font-size: 12px; font-weight: 700; color: #6ee7b7;">IMMEDIATE CLI REMEDIATION COMMAND:</div>
              <div class="cmd-snippet">
                {remediation_cmd}
              </div>
            </div>
            
            <div class="footer">
              <strong>Report ID:</strong> {report_id} &bull; <strong>Timestamp:</strong> {audit_report.get('generated_at')}<br/>
              GriffinOps Autonomous AI SRE Copilot &bull; Human-in-the-Loop Observability Platform
            </div>
          </div>
        </body>
        </html>
        """
        
        filename = f"alert_{report_id}_{int(time.time())}.html"
        filepath = os.path.join(self.email_preview_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_body)

        errors = []

        # 1. Dispatch via Brevo API (Sendinblue free tier 300/day)
        if self.brevo_api_key:
            try:
                brevo_url = "https://api.brevo.com/v3/smtp/email"
                headers = {"api-key": self.brevo_api_key, "Content-Type": "application/json"}
                payload = {
                    "sender": {"name": "GriffinOps Autonomous AI SRE", "email": "alerts@griffinops.io"},
                    "to": [{"email": recipient_email}],
                    "subject": subject,
                    "htmlContent": html_body
                }
                resp = requests.post(brevo_url, json=payload, headers=headers, timeout=5.0)
                if resp.status_code in [200, 201]:
                    return {
                        "status": "DELIVERED",
                        "recipient": recipient_email,
                        "provider": "BREVO_API",
                        "sender": "GriffinOps AI SRE Copilot <alerts@griffinops.io>",
                        "message": f"Email successfully delivered to {recipient_email} from alerts@griffinops.io via Brevo API!",
                        "preview_path": filepath
                    }
                else:
                    errors.append(f"Brevo API error HTTP {resp.status_code}: {resp.text}")
            except Exception as e:
                errors.append(f"Brevo API exception: {str(e)}")

        # 2. Dispatch via Resend API (Free 3,000/month)
        if self.resend_api_key:
            try:
                resend_url = "https://api.resend.com/emails"
                headers = {"Authorization": f"Bearer {self.resend_api_key}", "Content-Type": "application/json"}
                payload = {
                    "from": "GriffinOps AI SRE <alerts@griffinops.io>",
                    "to": [recipient_email],
                    "subject": subject,
                    "html": html_body
                }
                resp = requests.post(resend_url, json=payload, headers=headers, timeout=5.0)
                if resp.status_code in [200, 201]:
                    return {
                        "status": "DELIVERED",
                        "recipient": recipient_email,
                        "provider": "RESEND_API",
                        "sender": "GriffinOps AI SRE Copilot <alerts@griffinops.io>",
                        "message": f"Email successfully delivered to {recipient_email} from alerts@griffinops.io via Resend API!",
                        "preview_path": filepath
                    }
                else:
                    errors.append(f"Resend API error HTTP {resp.status_code}: {resp.text}")
            except Exception as e:
                errors.append(f"Resend API exception: {str(e)}")

        # 3. Dispatch via SMTP Server / Gmail SMTP
        if self.smtp_host and self.smtp_user and self.smtp_pass:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = f"GriffinOps AI SRE Copilot <{self.smtp_user}>"
                msg["To"] = recipient_email
                msg.attach(MIMEText(html_body, "html"))
                
                if self.smtp_port == 465:
                    with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=8.0) as server:
                        server.login(self.smtp_user, self.smtp_pass)
                        server.sendmail(self.smtp_user, recipient_email, msg.as_string())
                else:
                    with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=8.0) as server:
                        server.starttls()
                        server.login(self.smtp_user, self.smtp_pass)
                        server.sendmail(self.smtp_user, recipient_email, msg.as_string())
                    
                return {
                    "status": "DELIVERED",
                    "recipient": recipient_email,
                    "provider": f"SMTP ({self.smtp_host})",
                    "sender": f"GriffinOps AI SRE Copilot <{self.smtp_user}>",
                    "message": f"Email successfully delivered to {recipient_email} from GriffinOps AI SRE Copilot!",
                    "preview_path": filepath
                }
            except Exception as e:
                errors.append(f"SMTP error ({self.smtp_host}:{self.smtp_port}): {str(e)}")

        # 4. Fallback to Local Preview with clear user notification
        err_msg = "; ".join(errors) if errors else "No SMTP or Brevo/Resend API keys configured."
        return {
            "status": "STORED_IN_PREVIEW",
            "recipient": recipient_email,
            "provider": "LOCAL_HTML_PREVIEW",
            "message": f"Email alert stored in preview folder ({filepath}). {err_msg} Please enter your Gmail SMTP / Brevo credentials in User Profile & Alert Settings to receive emails directly in your inbox.",
            "preview_path": filepath,
            "errors": errors
        }
