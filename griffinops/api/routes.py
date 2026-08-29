import os
import time
from fastapi import APIRouter, HTTPException, Header, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict

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
    endpoint: Optional[str] = "/api/v1/checkout"
    sla_latency_ms: Optional[float] = 200.0
    sla_tier: Optional[str] = "Payment ($850/min)"
    environment: Optional[str] = "production"
    target_url: Optional[str] = "https://httpbin.org/get"

class IngestTelemetryRequest(BaseModel):
    api_key: str
    latency_ms: float
    status_code: int = 200
    payload_bytes: int = 256
    endpoint: str = "/api/v1/resource"

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
    return real_website_monitor.ping_all_sites()

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
    "assigned_services_count": 6
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
        "assigned_services_count": 6,
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
    
    # Save credentials into .env for persistence across restarts
    env_path = os.path.join(os.getcwd(), ".env")
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip()
    
    if req.smtp_host: env_vars["SMTP_HOST"] = req.smtp_host
    if req.smtp_port: env_vars["SMTP_PORT"] = str(req.smtp_port)
    if req.smtp_user: env_vars["SMTP_USER"] = req.smtp_user
    if req.smtp_pass: env_vars["SMTP_PASS"] = req.smtp_pass
    if req.brevo_api_key: env_vars["BREVO_API_KEY"] = req.brevo_api_key
    if req.resend_api_key: env_vars["RESEND_API_KEY"] = req.resend_api_key

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("# GriffinOps Environment Configuration\n")
        for k, v in env_vars.items():
            f.write(f"{k}={v}\n")

    return {
        "status": "SUCCESS",
        "message": "Email server credentials updated and saved to .env file!",
        "config": notifier.get_config_status() if notifier else {}
    }

# --- API KEY MANAGEMENT & MONITORED APIS ---
@router.get("/keys")
def list_api_keys():
    return api_key_manager.list_api_keys()

@router.post("/keys/create")
def create_api_key(req: CreateAPIKeyRequest):
    new_key = api_key_manager.generate_api_key(
        name=req.name,
        environment=req.environment or "production",
        endpoint=req.endpoint or "/api/v1/checkout",
        sla_latency_ms=req.sla_latency_ms or 200.0,
        sla_tier=req.sla_tier or "Payment ($850/min)",
        target_url=req.target_url or "https://httpbin.org/get"
    )
    if req.target_url and real_website_monitor:
        real_website_monitor.add_monitored_site(name=req.name, url=req.target_url, site_type="User API Key Target")
    return new_key

@router.post("/telemetry/ingest")
def ingest_telemetry_sdk_ping(req: IngestTelemetryRequest):
    info = api_key_manager.validate_api_key(req.api_key)
    if not info:
        raise HTTPException(status_code=401, detail="Invalid or revoked X-GriffinOps-API-Key.")
    
    # Store live SDK telemetry ping
    target_url = info.get("target_url", f"https://hosted-app.internal{req.endpoint}")
    if real_website_monitor:
        if target_url not in real_website_monitor.history:
            real_website_monitor.add_monitored_site(name=info["name"], url=target_url, site_type="SDK Telemetry Stream")
        
        now = time.time()
        dp = {
            "timestamp": now,
            "latency_ms": req.latency_ms,
            "status_code": req.status_code,
            "payload_bytes": req.payload_bytes,
            "error_rate": 0.0 if req.status_code < 400 else 1.0,
            "cpu_percent": round(min(100.0, req.latency_ms / 20.0), 2),
            "memory_percent": 45.0
        }
        real_website_monitor.history[target_url].append(dp)
    
    return {"status": "INGESTED", "api_key": req.api_key, "recorded_latency_ms": req.latency_ms}

@router.delete("/keys/{key_id}")
def revoke_api_key(key_id: str):
    success = api_key_manager.revoke_api_key(key_id)
    if not success:
        raise HTTPException(status_code=404, detail="API key ID not found.")
    return {"status": "REVOKED", "key_id": key_id}

@router.get("/monitored-apis")
def get_monitored_apis():
    return api_key_manager.get_monitored_apis()

# --- REAL LIVE WEBSITE MONITORING ROUTES ---
@router.post("/real-monitor/targets")
@router.post("/real-monitor/add-site")
def add_real_website_target(req: AddRealSiteRequest):
    site = real_website_monitor.add_monitored_site(name=req.name, url=req.url, site_type=req.site_type or "Live Web App")
    # Trigger immediate ping so metrics are available immediately
    if real_website_monitor:
        try:
            real_website_monitor.ping_all_sites()
        except Exception:
            pass
    return {"status": "ADDED", "target": site}

@router.get("/real-monitor/targets")
def get_real_website_targets():
    return real_website_monitor.sites

@router.get("/real-monitor/live")
def get_real_website_live_metrics():
    # Ensure default public target exists if empty
    if not real_website_monitor.sites:
        real_website_monitor.add_monitored_site(name="HTTPBin API Test", url="https://httpbin.org/get", site_type="Live API Endpoint")
        real_website_monitor.add_monitored_site(name="GitHub Web Service", url="https://github.com", site_type="Live Web Application")

    pings = real_website_monitor.ping_all_sites()
    
    # Build telemetry dataframes for real websites
    telemetry = {}
    for url, data in pings.items():
        site_name = data["name"].lower().replace(" ", "-")
        df = real_website_monitor.get_real_telemetry_dataframe(url)
        if not df.empty:
            telemetry[site_name] = df

    z_scores = normalizer.compute_z_scores(telemetry) if telemetry else {}
    tensor, service_names = normalizer.to_tensor_format(z_scores, sequence_length=30) if z_scores else (None, [])
    
    tcn_results = tcn_predictor.predict(tensor, service_names=service_names) if tensor is not None and len(service_names) > 0 else {"services": {}}
    rca_report = rca_engine.analyze_root_cause(tcn_results, z_scores) if z_scores else {}

    return {
        "status": "ONLINE",
        "timestamp": time.time(),
        "real_website_pings": pings,
        "z_scores_calculated": {svc: df.tail(1).to_dict(orient="records") for svc, df in z_scores.items()} if z_scores else {},
        "tcn_forecast": tcn_results,
        "rcaeval_analysis": rca_report
    }

# --- AI ILLUSTRATIONS & API SUGGESTIONS ---
@router.get("/illustrations/details")
def get_api_illustrations(api_endpoint: str = "https://httpbin.org/get"):
    live_latency = None
    live_status = 200
    payload_bytes = 256
    live_z = None

    # Check real website monitor history
    if real_website_monitor:
        for url, site in real_website_monitor.sites.items() if isinstance(real_website_monitor.sites, dict) else [(s["url"], s) for s in real_website_monitor.sites]:
            if url == api_endpoint or api_endpoint in url or site["name"].lower() in api_endpoint.lower():
                if url in real_website_monitor.history and real_website_monitor.history[url]:
                    latest = real_website_monitor.history[url][-1]
                    live_latency = latest.get("latency_ms")
                    live_status = latest.get("status_code", 200)
                    payload_bytes = latest.get("payload_bytes", 256)
                break

    # Check registered API keys
    if live_latency is None and api_key_manager:
        for k, info in api_key_manager.keys.items():
            if info.get("endpoint") == api_endpoint or info.get("assigned_service") in api_endpoint:
                live_latency = info.get("latest_latency_ms", 45.0)
                break

    if live_latency is None:
        live_latency = 48.0

    return rca_engine.get_api_illustrations_and_suggestions(
        api_endpoint=api_endpoint,
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
        "version": "2.3.0",
        "services_monitored": services_count,
        "supabase_auth": supabase_auth.is_supabase_configured,
        "watchdog_active": watchdog.is_running if watchdog else False
    }

@router.get("/telemetry/live")
def get_live_telemetry():
    telemetry = {}
    
    # 1. Collect real live network telemetry from RealWebsiteMonitor
    if real_website_monitor:
        real_website_monitor.ping_all_sites()
        real_tel = real_website_monitor.get_all_real_telemetry()
        for svc_name, df in real_tel.items():
            if not df.empty:
                telemetry[svc_name] = df.copy()

    # 2. Collect from SigNoz if available
    if not telemetry and telemetry_ingestor:
        signoz_data = telemetry_ingestor.fetch_signoz_metrics(int(time.time()) - 300, int(time.time()))
        if signoz_data:
            telemetry = signoz_data

    # 3. Apply active chaos fault if injected
    if fault_simulator:
        status = fault_simulator.get_status()
        if status.get("is_active"):
            fault = status.get("fault", {})
            target = fault.get("target_service")
            if target and target in telemetry:
                df = telemetry[target]
                mult = fault.get("latency_multiplier", 3.5)
                df["latency_ms"] = df["latency_ms"] * mult
                if "error_rate_spike" in fault:
                    df["error_rate"] = fault["error_rate_spike"]
            elif telemetry:
                first_k = list(telemetry.keys())[0]
                df = telemetry[first_k]
                mult = fault.get("latency_multiplier", 3.5)
                df["latency_ms"] = df["latency_ms"] * mult
                if "error_rate_spike" in fault:
                    df["error_rate"] = fault["error_rate_spike"]

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

    if fault_simulator:
        status = fault_simulator.get_status()
        if status.get("is_active"):
            fault = status.get("fault", {})
            target = fault.get("target_service")
            if target and target in telemetry:
                df = telemetry[target]
                mult = fault.get("latency_multiplier", 3.5)
                df["latency_ms"] = df["latency_ms"] * mult
                if "error_rate_spike" in fault:
                    df["error_rate"] = fault["error_rate_spike"]

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
    active_svcs = {}

    # 1. Discover from Real Website Monitor
    if real_website_monitor and real_website_monitor.sites:
        sites_list = real_website_monitor.sites if isinstance(real_website_monitor.sites, list) else list(real_website_monitor.sites.values())
        for site in sites_list:
            url = site.get("url", "")
            name = site.get("name", "Monitored Site")
            slug = name.lower().replace(" ", "-").replace("/", "-")
            lat = 40.0
            status_code = 200
            if url in real_website_monitor.history and real_website_monitor.history[url]:
                latest = real_website_monitor.history[url][-1]
                lat = latest.get("latency_ms", 40.0)
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

    # 2. Discover from API Key Manager
    if api_key_manager and api_key_manager.keys:
        for k, info in api_key_manager.keys.items():
            if info.get("status") == "ACTIVE":
                slug = info.get("assigned_service", "custom-api")
                if slug not in active_svcs:
                    lat = info.get("latest_latency_ms", 45.0)
                    active_svcs[slug] = {
                        "id": slug,
                        "label": info.get("name", slug),
                        "status": "HEALTHY",
                        "anomaly_score": 0.2,
                        "latency_ms": lat,
                        "type": "API Service"
                    }

    # Check if fault simulator injected a fault on any service
    if fault_simulator:
        status = fault_simulator.get_status()
        if status.get("is_active"):
            fault = status.get("fault", {})
            target = fault.get("target_service")
            if target and target in active_svcs:
                active_svcs[target]["status"] = "HAZARD"
                active_svcs[target]["anomaly_score"] = 4.2
            elif active_svcs:
                first_k = list(active_svcs.keys())[0]
                active_svcs[first_k]["status"] = "HAZARD"
                active_svcs[first_k]["anomaly_score"] = 4.2

    nodes = list(active_svcs.values())
    edges = []

    # Generate causal dependency edges dynamically
    if len(nodes) > 1:
        primary = nodes[0]["id"]
        for other in nodes[1:]:
            lag_val = round(abs(other.get("latency_ms", 50.0) - nodes[0].get("latency_ms", 30.0)) + 15.0, 1)
            edges.append({
                "source": primary,
                "target": other["id"],
                "lag_ms": int(lag_val)
            })

    return {"nodes": nodes, "edges": edges}

@router.get("/developer/dashboard")
def get_developer_dashboard(authorization: Optional[str] = Header(None)):
    user = supabase_auth.verify_token(authorization) if authorization else None
    user_email = user["email"] if user else "developer@company.com"

    all_keys = api_key_manager.list_api_keys()
    user_keys = [k for k in all_keys if k.get("status") == "ACTIVE"]

    monitored_apis = api_key_manager.get_monitored_apis()
    live_status = get_real_website_live_metrics() if real_website_monitor else {}

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
        watchdog.last_alert_time = 0 # Force zero cooldown so email dispatches immediately
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
