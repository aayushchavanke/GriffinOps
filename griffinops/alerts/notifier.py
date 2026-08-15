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
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST")
        self.smtp_port = int(os.getenv("SMTP_PORT", smtp_port))
        self.smtp_user = smtp_user or os.getenv("SMTP_USER")
        self.smtp_pass = smtp_pass or os.getenv("SMTP_PASS")
        self.brevo_api_key = brevo_api_key or os.getenv("BREVO_API_KEY")
        self.resend_api_key = resend_api_key or os.getenv("RESEND_API_KEY")
        
        self.email_preview_dir = os.path.join(os.getcwd(), "email_previews")
        os.makedirs(self.email_preview_dir, exist_ok=True)

    def send_slack_alert(self, audit_report: dict) -> dict:
        rca = audit_report.get("root_cause_analysis", {})
        commit = audit_report.get("ci_cd_correlation", {})
        
        payload = {
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
                resp = requests.post(self.slack_webhook_url, json=payload, timeout=3.0)
                return {"status": "SUCCESS", "slack_response_code": resp.status_code}
            except Exception as e:
                return {"status": "ERROR", "message": str(e), "payload": payload}
        
        return {"status": "SIMULATED", "payload": payload}

    def send_email_notification(self, audit_report: dict, recipient_email: str) -> dict:
        report_id = audit_report.get("report_id", "GO-REPORT")
        rca = audit_report.get("root_cause_analysis", {})
        commit = audit_report.get("ci_cd_correlation", {})
        
        subject = f"[GriffinOps AI SRE Alert] Predicted Outage in {rca.get('service')} ({audit_report.get('forecasted_time_to_failure_human')})"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #080a0f; color: #f8fafc; margin: 0; padding: 24px; }}
            .container {{ max-width: 650px; margin: 0 auto; background: #121622; border: 1px solid rgba(245,158,11,0.2); border-radius: 16px; padding: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.6); }}
            .header {{ display: flex; align-items: center; justify-content: space-between; border-bottom: 2px solid #e11d48; padding-bottom: 15px; margin-bottom: 20px; }}
            .title {{ color: #f59e0b; font-size: 22px; font-weight: bold; margin: 0; }}
            .badge {{ background: #e11d48; color: white; padding: 5px 14px; border-radius: 20px; font-size: 12px; font-weight: bold; text-transform: uppercase; }}
            .countdown {{ background: rgba(225,29,72,0.15); border: 1px solid #e11d48; color: #ff4d8d; padding: 15px; border-radius: 10px; font-size: 18px; font-weight: bold; text-align: center; margin-bottom: 25px; }}
            .section {{ margin-bottom: 22px; }}
            .section-title {{ color: #f59e0b; font-size: 14px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }}
            .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; background: #181f30; padding: 16px; border-radius: 8px; }}
            .label {{ color: #94a3b8; font-size: 12px; display: block; }}
            .value {{ color: #ffffff; font-size: 14px; font-weight: 600; }}
            .code-box {{ background: #0b0f19; border-left: 4px solid #f59e0b; padding: 14px; font-family: monospace; font-size: 12px; color: #fef3c7; border-radius: 4px; line-height: 1.5; }}
            .action-box {{ background: rgba(245,158,11,0.1); border: 1px solid #f59e0b; color: #fef3c7; padding: 16px; border-radius: 10px; line-height: 1.5; }}
            .footer {{ text-align: center; color: #64748b; font-size: 12px; margin-top: 30px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 15px; }}
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1 class="title">🦅 GriffinOps AI SRE Copilot</h1>
              <span class="badge">Pre-Mortem Outage Hazard</span>
            </div>
            
            <div class="countdown">
              ⏳ Predicted Time-to-Failure: {audit_report.get('forecasted_time_to_failure_human')}
            </div>
            
            <div class="section">
              <div class="section-title">Root Cause Diagnosis (PyTorch TCN & RCAEval)</div>
              <div class="grid">
                <div><span class="label">Target Microservice</span><span class="value">{rca.get('service')}</span></div>
                <div><span class="label">Primary Metric Anomaly</span><span class="value">{rca.get('primary_metric')}</span></div>
                <div><span class="label">Forecasted Z-Score</span><span class="value">+{rca.get('max_z_score_deviation')} σ</span></div>
                <div><span class="label">Causal Confidence</span><span class="value">{int(rca.get('causal_confidence_score', 0.9) * 100)}%</span></div>
              </div>
            </div>
            
            <div class="section">
              <div class="section-title">Correlated CI/CD Deployment Commit</div>
              <div class="code-box">
                Commit: {commit.get('commit_id')}<br/>
                Author: {commit.get('author')}<br/>
                Message: {commit.get('message')}<br/>
                Files: {", ".join(commit.get('changed_files', []))}
              </div>
            </div>
            
            <div class="section">
              <div class="section-title">Actionable SRE Remediation Suggestion</div>
              <div class="action-box">
                <strong>Recommended Fix for Developer:</strong><br/>
                {audit_report.get('suggested_action')}
              </div>
            </div>
            
            <div class="footer">
              Report ID: {report_id} &bull; Generated at {audit_report.get('generated_at')}<br/>
              GriffinOps Autonomous AI SRE Copilot &bull; SIES GST AI & Data Science
            </div>
          </div>
        </body>
        </html>
        """
        
        filename = f"alert_{report_id}_{int(time.time())}.html"
        filepath = os.path.join(self.email_preview_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_body)

        # 1. Dispatch via Brevo API (Sendinblue free tier 300/day)
        if self.brevo_api_key:
            try:
                brevo_url = "https://api.brevo.com/v3/smtp/email"
                headers = {"api-key": self.brevo_api_key, "Content-Type": "application/json"}
                payload = {
                    "sender": {"name": "GriffinOps AI SRE Alert", "email": "alerts@griffinops.io"},
                    "to": [{"email": recipient_email}],
                    "subject": subject,
                    "htmlContent": html_body
                }
                resp = requests.post(brevo_url, json=payload, headers=headers, timeout=4.0)
                if resp.status_code in [200, 201]:
                    return {"status": "DELIVERED", "recipient": recipient_email, "provider": "BREVO_API", "preview_path": filepath}
            except Exception:
                pass

        # 2. Dispatch via Resend API (Free 3,000/month)
        if self.resend_api_key:
            try:
                resend_url = "https://api.resend.com/emails"
                headers = {"Authorization": f"Bearer {self.resend_api_key}", "Content-Type": "application/json"}
                payload = {
                    "from": "alerts@griffinops.io",
                    "to": [recipient_email],
                    "subject": subject,
                    "html": html_body
                }
                resp = requests.post(resend_url, json=payload, headers=headers, timeout=4.0)
                if resp.status_code in [200, 201]:
                    return {"status": "DELIVERED", "recipient": recipient_email, "provider": "RESEND_API", "preview_path": filepath}
            except Exception:
                pass

        # 3. Dispatch via SMTP Server / Gmail SMTP
        if self.smtp_host and self.smtp_user and self.smtp_pass:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = self.smtp_user
                msg["To"] = recipient_email
                msg.attach(MIMEText(html_body, "html"))
                
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.smtp_user, self.smtp_pass)
                    server.sendmail(self.smtp_user, recipient_email, msg.as_string())
                    
                return {"status": "DELIVERED", "recipient": recipient_email, "provider": "SMTP_SERVER", "preview_path": filepath}
            except Exception as e:
                pass

        return {
            "status": "DISPATCHED_TO_PREVIEW",
            "recipient": recipient_email,
            "provider": "LOCAL_HTML_PREVIEW",
            "message": f"Email alert formatted and rendered to local preview: {filepath}",
            "preview_path": filepath
        }
