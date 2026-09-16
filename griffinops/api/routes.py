import os
import time
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
import pandas as pd

from griffinops.auth.supabase_auth import SupabaseAuthEngine
from griffinops.telemetry.real_website_monitor import RealWebsiteMonitor
from griffinops.reports.docx_generator import DOCXReportGenerator

router = APIRouter(prefix="/api/v1", tags=["GriffinOps Enterprise API"])

# Singletons
telemetry_ingestor = None
normalizer = None
tcn_predictor = None
rca_engine = None
fault_simulator = None
notifier = None
api_key_manager = None
watchdog = None
pdf_generator = None
supabase_auth = SupabaseAuthEngine()
real_website_monitor = RealWebsiteMonitor()
docx_generator = DOCXReportGenerator()

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str

class ProfileUpdateRequest(BaseModel):
    name: str
    email: str
    organization: str
    developer_emails: List[str]
    email_alerts_enabled: bool

class CreateAPIKeyRequest(BaseModel):
    name: str
    target_url: Optional[str] = None
    endpoint: Optional[str] = None
    sla_latency_ms: Optional[float] = 200.0
    sla_tier: Optional[str] = "Standard"
    environment: Optional[str] = "production"

class IngestTelemetryRequest(BaseModel):
    api_key: str
    latency_ms: float
    status_code: int = 200
    payload_bytes: int = 256
    endpoint: Optional[str] = None

class TestPingRequest(BaseModel):
    api_key: str
    latency_ms: Optional[float] = 42.5
    status_code: Optional[int] = 200
    endpoint: Optional[str] = None

class AddRealSiteRequest(BaseModel):
    name: str
    url: str
    site_type: Optional[str] = "Live Web App"

class FaultInjectRequest(BaseModel):
    scenario_key: str

class EmailAlertRequest(BaseModel):
    recipient_email: str

# --- REAL LIVE WEBSITE MONITORING ROUTES ---
@router.get("/real-monitor/live")
def get_real_website_telemetry():
    return real_website_monitor.get_live_site_metrics()

@router.post("/real-monitor/add-site")
def add_real_website(req: AddRealSiteRequest):
    return real_website_monitor.add_monitored_site(name=req.name, url=req.url, site_type=req.site_type)

# --- MASTER DOCX DOCUMENTATION DOWNLOAD & DIAGRAMS ---
@router.get("/docs/architecture.docx")
@router.get("/docs/project-report.docx")
def download_docx_project_report():
    filepath = docx_generator.generate_docx()
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="GriffinOps_Master_Project_Report.docx"
    )

@router.get("/docs/diagrams/{filename}")
def get_diagram_file(filename: str):
    diagram_paths = docx_generator.generate_all_wireframe_diagrams()
    filepath = os.path.join(docx_generator.output_dir, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Diagram not found")
    return FileResponse(filepath, media_type="image/png")

# --- AUTHENTICATION & USER PROFILE ---
@router.post("/auth/login")
def login(req: LoginRequest):
    try:
        res = supabase_auth.login(req.email, req.password)
        return res
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

@router.post("/auth/register")
def register(req: RegisterRequest):
    try:
        res = supabase_auth.register(req.email, req.password, req.name)
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/auth/me")
def get_me(authorization: Optional[str] = Header(None)):
    user = supabase_auth.verify_token(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized session.")
    return user

class EmailConfigRequest(BaseModel):
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = 587
    smtp_user: Optional[str] = None
    smtp_pass: Optional[str] = None
    brevo_api_key: Optional[str] = None
    resend_api_key: Optional[str] = None

USER_PROFILE_STATE = {
    "user_id": "usr_admin001",
    "email": "sre-lead@company.com",
    "name": "SRE Lead Engineer",
    "role": "CHIEF SRE ARCHITECT",
    "organization": "SIES GST AI & Data Science Team",
    "email_alerts_enabled": True,
    "developer_emails": ["sre-lead@company.com"],
    "assigned_services_count": 0
}

@router.get("/user/profile")
def get_user_profile():
    email_status = notifier.get_config_status() if notifier else {}
    dev_emails = watchdog.registered_developer_emails if watchdog and watchdog.registered_developer_emails else USER_PROFILE_STATE["developer_emails"]
    primary_email = dev_emails[0] if dev_emails else USER_PROFILE_STATE["email"]
    return {
        "user_id": USER_PROFILE_STATE["user_id"],
        "email": primary_email,
        "name": USER_PROFILE_STATE["name"],
        "role": USER_PROFILE_STATE["role"],
        "organization": USER_PROFILE_STATE["organization"],
        "email_alerts_enabled": USER_PROFILE_STATE["email_alerts_enabled"],
        "developer_emails": dev_emails,
        "assigned_services_count": len(api_key_manager.keys) if api_key_manager else 0,
        "email_config": email_status
    }

@router.get("/email-previews/{filename}")
def serve_email_preview(filename: str):
    preview_dir = os.path.join(os.getcwd(), "email_previews")
    filepath = os.path.join(preview_dir, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Email preview file not found.")
    return FileResponse(filepath, media_type="text/html")

@router.put("/user/profile")
def update_user_profile(req: ProfileUpdateRequest):
    USER_PROFILE_STATE["name"] = req.name
    USER_PROFILE_STATE["organization"] = req.organization
    USER_PROFILE_STATE["developer_emails"] = req.developer_emails
    USER_PROFILE_STATE["email_alerts_enabled"] = req.email_alerts_enabled
    if req.developer_emails:
        USER_PROFILE_STATE["email"] = req.developer_emails[0]
    elif req.email:
        USER_PROFILE_STATE["email"] = req.email
    if watchdog:
        watchdog.registered_developer_emails = req.developer_emails
    return {"status": "SUCCESS", "message": "User recipient email & notification settings updated.", "profile": USER_PROFILE_STATE}

@router.get("/user/email-config")
def get_email_config():
    if not notifier:
        return {}
    return notifier.get_config_status()

@router.post("/user/email-config")
def update_email_config(req: EmailConfigRequest):
    if notifier:
        notifier.update_credentials(
            smtp_host=req.smtp_host,
            smtp_port=req.smtp_port or 587,
            smtp_user=req.smtp_user,
            smtp_pass=req.smtp_pass,
            brevo_api_key=req.brevo_api_key,
            resend_api_key=req.resend_api_key
        )
    return {
        "status": "SUCCESS",
        "message": "Email server credentials updated!",
        "config": notifier.get_config_status() if notifier else {}
    }

# --- API KEY MANAGEMENT & MONITORED APIS ---
@router.get("/keys")
def list_api_keys():
    return api_key_manager.list_api_keys()

@router.post("/keys/create")
def create_api_key(req: CreateAPIKeyRequest, authorization: Optional[str] = Header(None)):
    user = supabase_auth.verify_token(authorization) if authorization else None
    owner_email = user["email"] if user else "admin@griffinops.io"
    target_url = req.target_url or req.endpoint or f"https://{req.name.lower().replace(' ', '-')}.internal"

    new_key = api_key_manager.generate_api_key(
        name=req.name,
        target_url=target_url,
        owner_email=owner_email
    )
    if real_website_monitor:
        real_website_monitor.add_monitored_site(
            name=req.name,
            url=target_url,
            site_type="Live Web App (SDK)",
            api_key=new_key["api_key"]
        )
    return new_key

@router.post("/telemetry/ingest")
def ingest_telemetry_sdk_ping(req: IngestTelemetryRequest):
    info = api_key_manager.validate_api_key(req.api_key)
    if not info:
        # If key exists in real_website_monitor, accept it
        matching_site = next((s for s in real_website_monitor.sites if s.get("api_key") == req.api_key), None)
        if not matching_site:
            raise HTTPException(status_code=401, detail="Invalid or revoked X-GriffinOps-API-Key.")
        site_name = matching_site["name"]
        target_url = matching_site["url"]
    else:
        site_name = info["name"]
        target_url = info.get("target_url") or info.get("endpoint") or f"https://{site_name.lower().replace(' ', '-')}.internal"
        info["latest_latency_ms"] = req.latency_ms

    if real_website_monitor:
        real_website_monitor.record_telemetry(
            url=target_url,
            latency_ms=req.latency_ms,
            status_code=req.status_code,
            payload_bytes=req.payload_bytes,
            api_key=req.api_key,
            site_name=site_name
        )
    
    return {"status": "INGESTED", "api_key": req.api_key, "recorded_latency_ms": req.latency_ms}

@router.post("/telemetry/test-ping")
def send_test_telemetry_ping(req: TestPingRequest):
    """
    Interactive test helper: Ingests a real telemetry point for immediate developer verification.
    """
    return ingest_telemetry_sdk_ping(IngestTelemetryRequest(
        api_key=req.api_key,
        latency_ms=req.latency_ms or 42.5,
        status_code=req.status_code or 200,
        payload_bytes=2048,
        endpoint=req.endpoint or "/test/ping"
    ))

@router.delete("/keys/{key_id}")
def revoke_api_key(key_id: str):
    success = api_key_manager.revoke_api_key(key_id)
    if not success:
        raise HTTPException(status_code=404, detail="API key ID not found.")
    return {"status": "REVOKED", "key_id": key_id}

@router.get("/monitored-apis")
def get_monitored_apis():
    return api_key_manager.get_monitored_apis()

@router.get("/real-monitor/targets")
def get_real_website_targets():
    return real_website_monitor.sites

# --- AI ILLUSTRATIONS & API SUGGESTIONS ---
@router.get("/illustrations/details")
def get_api_illustrations(api_endpoint: Optional[str] = None):
    live_latency = 45.0
    live_status = 200
    payload_bytes = 256
    live_z = 0.3

    if real_website_monitor and real_website_monitor.history:
        for url, hist in real_website_monitor.history.items():
            if hist:
                latest = hist[-1]
                live_latency = latest.get("latency_ms", 45.0)
                live_status = latest.get("status_code", 200)
                payload_bytes = latest.get("payload_bytes", 256)
                break

    return rca_engine.get_api_illustrations_and_suggestions(
        api_endpoint=api_endpoint or "/api/v1/resource",
        live_latency_ms=live_latency,
        status_code=live_status,
        payload_bytes=payload_bytes,
        z_score=live_z
    )

# --- TELEMETRY & TCN PREDICTION ROUTES ---
@router.get("/health")
def get_health():
    services_count = len(real_website_monitor.sites) if real_website_monitor else 0
    return {
        "status": "ONLINE",
        "engine": "GriffinOps Enterprise AI SRE Copilot",
        "version": "2.5.0",
        "services_monitored": services_count,
        "supabase_auth": supabase_auth.is_supabase_configured,
        "watchdog_active": watchdog.is_running if watchdog else False
    }

@router.get("/telemetry/live")
def get_live_telemetry():
    telemetry = {}
    if real_website_monitor:
        real_tel = real_website_monitor.get_all_real_telemetry()
        for svc_name, df in real_tel.items():
            if not df.empty:
                telemetry[svc_name] = df.copy()

    if not telemetry:
        return {}

    z_scores = normalizer.compute_z_scores(telemetry) if telemetry else {}
    result = {}
    for svc, raw_df in telemetry.items():
        z_df = z_scores.get(svc, raw_df)
        result[svc] = {
            "timestamps": raw_df["timestamp"].tolist() if "timestamp" in raw_df.columns else [],
            "raw": {col: raw_df[col].tolist() for col in raw_df.columns if col != "timestamp"},
            "z_scores": {col: z_df[col].tolist() for col in z_df.columns if col != "timestamp"}
        }
    return result

@router.get("/forecast")
def get_tcn_forecast():
    telemetry = {}
    if real_website_monitor:
        real_tel = real_website_monitor.get_all_real_telemetry()
        for svc_name, df in real_tel.items():
            if not df.empty:
                telemetry[svc_name] = df.copy()

    if not telemetry:
        return {"services": {}}

    z_scores = normalizer.compute_z_scores(telemetry)
    min_len = min([len(df) for df in telemetry.values()])
    tensor, service_names = normalizer.to_tensor_format(z_scores, sequence_length=min(30, max(5, min_len)))
    if tensor is None or len(service_names) == 0:
        return {"services": {}}
    return tcn_predictor.predict(tensor, service_names=service_names)

@router.get("/topology")
def get_topology():
    if not real_website_monitor or not real_website_monitor.sites:
        if not api_key_manager or not api_key_manager.keys:
            return {"nodes": [], "edges": []}

    active_svcs = {}
    for site in real_website_monitor.sites:
        url = site.get("url", "")
        name = site.get("name", "Monitored Site")
        slug = name.lower().replace(" ", "-").replace("/", "-")
        lat = 35.0
        status_code = 200
        hist = real_website_monitor.history.get(url, [])
        if hist:
            latest = hist[-1]
            lat = latest.get("latency_ms", 35.0)
            status_code = latest.get("status_code", 200)

        is_anomaly = lat > 250.0 or status_code >= 400
        active_svcs[slug] = {
            "id": slug,
            "label": name,
            "status": "HAZARD" if is_anomaly else "HEALTHY",
            "anomaly_score": 3.8 if is_anomaly else 0.3,
            "latency_ms": lat,
            "type": site.get("type", "Live Target")
        }

    for k, info in api_key_manager.keys.items():
        if info.get("status") == "ACTIVE":
            slug = info.get("assigned_service", "custom-api")
            if slug not in active_svcs:
                lat = info.get("latest_latency_ms") or 35.0
                active_svcs[slug] = {
                    "id": slug,
                    "label": info.get("name", slug),
                    "status": "HEALTHY",
                    "anomaly_score": 0.2,
                    "latency_ms": lat,
                    "type": "API Service"
                }

    nodes = list(active_svcs.values())
    edges = []

    # Build edges between discovered nodes
    if len(nodes) >= 2:
        for i in range(len(nodes) - 1):
            src = nodes[i]["id"]
            tgt = nodes[i + 1]["id"]
            edges.append({
                "source": src,
                "target": tgt,
                "lag_ms": int(abs(nodes[i]["latency_ms"] - nodes[tgt_idx if (tgt_idx:=i+1) < len(nodes) else 0]["latency_ms"]) + 12)
            })

    return {"nodes": nodes, "edges": edges}

@router.get("/developer/dashboard")
def get_developer_dashboard(authorization: Optional[str] = Header(None)):
    user = supabase_auth.verify_token(authorization) if authorization else None
    user_email = user["email"] if user else "developer@company.com"

    all_keys = api_key_manager.list_api_keys()
    user_keys = [k for k in all_keys if k.get("status") == "ACTIVE"]
    monitored_apis = api_key_manager.get_monitored_apis()
    live_status = real_website_monitor.get_live_site_metrics()

    return {
        "status": "ONLINE",
        "developer": {
            "email": user_email,
            "supabase_auth": supabase_auth.is_supabase_configured,
            "active_api_keys_count": len(user_keys)
        },
        "developer_api_keys": user_keys,
        "monitored_apis": monitored_apis,
        "live_telemetry_status": live_status
    }

# --- FAULT SIMULATOR & AUDIT REPORT ROUTES ---
@router.get("/fault/scenarios")
def get_fault_scenarios():
    from griffinops.simulation.fault_simulator import FAULT_SCENARIOS
    return FAULT_SCENARIOS

@router.get("/fault/status")
def get_fault_status():
    return fault_simulator.get_status()

@router.post("/fault/inject")
def inject_fault(req: FaultInjectRequest):
    res = fault_simulator.inject_fault(req.scenario_key)
    if watchdog:
        watchdog.last_alert_time = 0
        watchdog._evaluate_and_dispatch()
    return res

@router.post("/fault/reset")
def reset_fault():
    res = fault_simulator.reset_fault()
    return res

@router.get("/telemetry/signoz/status")
def get_signoz_status():
    return telemetry_ingestor.check_signoz_status()

@router.get("/audit-reports/latest")
def get_latest_audit_report(algorithm: str = "composite"):
    active_fault = fault_simulator.get_status().get("fault") if fault_simulator else None
    telemetry = telemetry_ingestor.generate_synthetic_telemetry(sequence_length=60, active_fault=active_fault)
    
    if not telemetry:
        return {
            "report_id": "GO-RPT-NOMINAL",
            "system_status": "HEALTHY",
            "forecasted_time_to_failure_human": "HEALTHY (Nominal)",
            "message": "Awaiting active telemetry streams."
        }

    z_scores = normalizer.compute_z_scores(telemetry)
    tensor, service_names = normalizer.to_tensor_format(z_scores, sequence_length=30)
    
    tcn_results = tcn_predictor.predict(tensor, service_names=service_names)
    report = rca_engine.analyze_root_cause(tcn_results, z_scores, active_fault=active_fault, algorithm=algorithm)
    return report

@router.get("/audit-reports/{report_id}/pdf")
def download_pdf_report(report_id: str):
    report = get_latest_audit_report()
    report["report_id"] = report_id
    filepath = pdf_generator.generate_pdf_report(report)
    return FileResponse(filepath, media_type="application/pdf", filename=f"GriffinOps_Audit_Report_{report_id}.pdf")

@router.get("/watchdog/history")
def get_watchdog_history():
    return watchdog.get_dispatch_history() if watchdog else []

@router.post("/alerts/slack")
def trigger_slack_alert():
    report = get_latest_audit_report()
    return notifier.send_slack_alert(report)

@router.post("/alerts/email")
def trigger_email_alert(req: EmailAlertRequest):
    report = get_latest_audit_report()
    return notifier.send_email_notification(report, recipient_email=req.recipient_email)
