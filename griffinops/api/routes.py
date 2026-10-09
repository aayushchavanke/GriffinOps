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
from griffinops.db.storage import storage

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

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email: str
    reset_code: str
    new_password: str

class ProfileUpdateRequest(BaseModel):
    name: str
    email: str
    organization: str
    developer_emails: List[str]
    email_alerts_enabled: bool
    slack_webhook_url: Optional[str] = None

class CreateAPIKeyRequest(BaseModel):
    name: str
    target_url: Optional[str] = None
    endpoint: Optional[str] = None
    sla_latency_ms: Optional[float] = 200.0
    sla_tier: Optional[str] = "Standard"
    environment: Optional[str] = "production"

class IngestTelemetryRequest(BaseModel):
    api_key: Optional[str] = None
    latency_ms: float
    status_code: int = 200
    payload_bytes: int = 256
    endpoint: Optional[str] = None
    # Real system metrics captured via psutil on the sender's machine.
    # Optional — JS SDK and cURL clients omit these; backend falls back to formula/constant.
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None

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

class SlackTestRequest(BaseModel):
    slack_webhook_url: Optional[str] = None

class ReportDownloadRequest(BaseModel):
    format: str = "pdf"          # "pdf" or "docx"
    report_id: Optional[str] = None
    api_endpoint: Optional[str] = None

def _filter_sites_for_endpoint(api_endpoint: Optional[str]) -> Optional[list]:
    """Returns filtered sites list or None (meaning no filter)."""
    if not api_endpoint:
        return None
    if not real_website_monitor or not real_website_monitor.sites:
        return []
    target = api_endpoint.strip()
    target_clean = target.rstrip("/")
    matches = []
    for site in real_website_monitor.sites:
        name = site.get("name", "")
        slug = name.lower().replace(" ", "-").replace("&", "and").replace("/", "-")
        url = site.get("url", "")
        url_clean = url.rstrip("/")
        if (url == target
                or url_clean == target_clean
                or name.lower() == target.lower()
                or slug == target.lower()):
            matches.append(site)
    return matches

# --- REAL LIVE WEBSITE MONITORING ROUTES ---
@router.get("/real-monitor/live")
def get_real_website_telemetry(api_endpoint: Optional[str] = None):
    # Ensure all active keys in api_key_manager are registered in real_website_monitor
    if real_website_monitor and api_key_manager:
        for k in api_key_manager.list_api_keys():
            if k.get("status") == "ACTIVE" and k.get("name") != "Cloud Target Web Application" and k.get("api_key") != "gop_live_demo01":
                target = k.get("target_url") or k.get("endpoint") or f"https://{k['name'].lower().replace(' ', '-')}.internal"
                real_website_monitor.add_monitored_site(
                    name=k["name"],
                    url=target,
                    site_type="Live Web App (SDK)",
                    api_key=k["api_key"]
                )
    all_metrics = real_website_monitor.get_live_site_metrics()
    if not api_endpoint:
        return all_metrics
    filtered_sites = _filter_sites_for_endpoint(api_endpoint)
    if filtered_sites is None:
        return all_metrics
    allowed_urls = {s["url"] for s in filtered_sites}
    return {url: data for url, data in all_metrics.items() if url in allowed_urls}

@router.post("/real-monitor/add-site")
@router.post("/real-monitor/targets")
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
        if res and "user" in res and "email" in res["user"]:
            u_email = res["user"]["email"]
            USER_PROFILE_STATE["email"] = u_email
            if watchdog:
                current_emails = watchdog.registered_developer_emails
                if not current_emails or current_emails == ["sre-lead@company.com"]:
                    watchdog.registered_developer_emails = [u_email]
                    USER_PROFILE_STATE["developer_emails"] = [u_email]
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

@router.post("/auth/forgot-password")
def forgot_password(req: ForgotPasswordRequest):
    try:
        res = supabase_auth.forgot_password(req.email)
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/auth/reset-password")
def reset_password(req: ResetPasswordRequest):
    try:
        res = supabase_auth.reset_password(req.email, req.reset_code, req.new_password)
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
    "assigned_services_count": 0,
    "slack_webhook_url": os.getenv("SLACK_WEBHOOK_URL", "")
}

# Hydrate profile state from persistent SQLite on startup
_persisted_profile = storage.load_profile()
if _persisted_profile:
    for k in ["name", "email", "role", "organization", "email_alerts_enabled", "developer_emails", "slack_webhook_url"]:
        if k in _persisted_profile and _persisted_profile[k] is not None:
            USER_PROFILE_STATE[k] = _persisted_profile[k]

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
        "slack_webhook_url": notifier.slack_webhook_url if notifier else USER_PROFILE_STATE.get("slack_webhook_url", ""),
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
    clean_emails = [e.strip() for e in req.developer_emails if e.strip() and "@" in e]
    if clean_emails:
        USER_PROFILE_STATE["developer_emails"] = clean_emails
        USER_PROFILE_STATE["email"] = clean_emails[0]
    elif req.email and "@" in req.email:
        USER_PROFILE_STATE["email"] = req.email.strip()
        USER_PROFILE_STATE["developer_emails"] = [req.email.strip()]
    USER_PROFILE_STATE["email_alerts_enabled"] = req.email_alerts_enabled
    if req.slack_webhook_url is not None:
        clean_url = req.slack_webhook_url.strip()
        USER_PROFILE_STATE["slack_webhook_url"] = clean_url
        if notifier:
            notifier.slack_webhook_url = clean_url or None
    if watchdog:
        watchdog.registered_developer_emails = USER_PROFILE_STATE["developer_emails"]
    storage.save_profile(USER_PROFILE_STATE)
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
        storage.save_profile(USER_PROFILE_STATE, email_config=req.dict())
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
def ingest_telemetry_sdk_ping(
    req: IngestTelemetryRequest,
    x_griffinops_api_key: Optional[str] = Header(None, alias="X-GriffinOps-API-Key")
):
    effective_api_key = x_griffinops_api_key or req.api_key
    if not effective_api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Please provide the 'X-GriffinOps-API-Key' header."
        )

    info = api_key_manager.validate_api_key(effective_api_key)
    if not info:
        # If key exists in real_website_monitor, accept it
        matching_site = next((s for s in real_website_monitor.sites if s.get("api_key") == effective_api_key), None)
        if not matching_site:
            raise HTTPException(status_code=401, detail="Invalid or revoked X-GriffinOps-API-Key.")
        site_name = matching_site["name"]
        target_url = matching_site["url"]
    else:
        site_name = info["name"]
        target_url = info.get("target_url") or info.get("endpoint") or f"https://{site_name.lower().replace(' ', '-')}.internal"
    if real_website_monitor:
        real_website_monitor.record_telemetry(
            url=target_url,
            latency_ms=req.latency_ms,
            status_code=req.status_code,
            payload_bytes=req.payload_bytes,
            api_key=effective_api_key,
            site_name=site_name,
            cpu_percent=req.cpu_percent,
            memory_percent=req.memory_percent
        )
        if info:
            info["latest_latency_ms"] = req.latency_ms
            storage.mark_api_key_dirty(effective_api_key, info["requests_total"], req.latency_ms)

    alert_info = None
    if (req.latency_ms >= 200.0 or req.status_code >= 400) and watchdog:
        report = watchdog._evaluate_and_dispatch(force_trigger=True)
        if report:
            latest_entry = watchdog.dispatch_log[0] if watchdog.dispatch_log else None
            preview_fn = os.path.basename(latest_entry["preview_path"]) if (latest_entry and latest_entry.get("preview_path")) else None
            alert_info = {
                "alert_dispatched": True,
                "report_id": report.get("report_id"),
                "severity": report.get("severity_level"),
                "recipients": watchdog.registered_developer_emails,
                "preview_filename": preview_fn,
                "preview_url": f"/api/v1/email-previews/{preview_fn}" if preview_fn else None
            }

    return {
        "status": "INGESTED",
        "api_key": effective_api_key,
        "recorded_latency_ms": req.latency_ms,
        "status_code": req.status_code,
        "site_name": site_name,
        "alert": alert_info
    }

@router.post("/telemetry/test-ping")
def send_test_telemetry_ping(req: TestPingRequest):
    """
    Interactive test helper: Ingests an initial verification ping for the API key so the user can verify connectivity on the Overview dashboard.
    """
    info = api_key_manager.validate_api_key(req.api_key)
    target_url = req.endpoint
    site_name = None
    if info:
        target_url = target_url or info.get("target_url") or info.get("endpoint") or f"https://{info['name'].lower().replace(' ', '-')}.internal"
        site_name = info["name"]
    else:
        matching_site = next((s for s in real_website_monitor.sites if s.get("api_key") == req.api_key), None) if real_website_monitor else None
        if matching_site:
            target_url = target_url or matching_site["url"]
            site_name = matching_site["name"]
        else:
            target_url = target_url or "https://custom-service.internal"
            site_name = "Custom Service"
            
    lat = req.latency_ms if req.latency_ms is not None else 38.5
    status = req.status_code if req.status_code is not None else 200
    
    if real_website_monitor:
        real_website_monitor.record_telemetry(
            url=target_url,
            latency_ms=lat,
            status_code=status,
            payload_bytes=512,
            api_key=req.api_key,
            site_name=site_name
        )
    if info:
        info["latest_latency_ms"] = lat
        storage.mark_api_key_dirty(req.api_key, info["requests_total"], lat)
    return {"status": "SUCCESS", "message": f"Verification telemetry ingested for {site_name} ({lat:.1f}ms, HTTP {status})"}

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
def get_live_telemetry(api_endpoint: Optional[str] = None):
    telemetry = {}
    if real_website_monitor:
        real_tel = real_website_monitor.get_all_real_telemetry()
        if api_endpoint:
            filtered_sites = _filter_sites_for_endpoint(api_endpoint)
            allowed_slugs = {
                s["name"].lower().replace(" ", "-").replace("&", "and").replace("/", "-")
                for s in (filtered_sites or [])
            }
            real_tel = {k: v for k, v in real_tel.items() if k in allowed_slugs or k == api_endpoint}
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
def get_tcn_forecast(api_endpoint: Optional[str] = None):
    telemetry = {}
    if real_website_monitor:
        real_tel = real_website_monitor.get_all_real_telemetry()
        if api_endpoint:
            filtered_sites = _filter_sites_for_endpoint(api_endpoint)
            allowed_slugs = {
                s["name"].lower().replace(" ", "-").replace("&", "and").replace("/", "-")
                for s in (filtered_sites or [])
            }
            real_tel = {k: v for k, v in real_tel.items() if k in allowed_slugs or k == api_endpoint}
        for svc_name, df in real_tel.items():
            if not df.empty:
                telemetry[svc_name] = df.copy()

    if not telemetry:
        return {"status": "NO_DATA", "message": "No real telemetry ingested yet.", "services": {}}

    z_scores = normalizer.compute_z_scores(telemetry)
    min_len = min([len(df) for df in telemetry.values()])
    tensor, service_names = normalizer.to_tensor_format(z_scores, sequence_length=min(30, max(5, min_len)))
    if tensor is None or len(service_names) == 0:
        return {"status": "NO_DATA", "message": "No real telemetry ingested yet.", "services": {}}
    results = tcn_predictor.predict(tensor, service_names=service_names)
    if notifier:
        notifier.dispatch_slack_if_anomaly(results)
    return results

@router.get("/topology")
def get_topology(api_endpoint: Optional[str] = None):
    if not real_website_monitor or not real_website_monitor.sites:
        if not api_key_manager or not api_key_manager.keys:
            return {"status": "NO_DATA", "message": "No real telemetry ingested yet.", "nodes": [], "edges": []}

    sites = real_website_monitor.sites
    if api_endpoint:
        filtered_sites = _filter_sites_for_endpoint(api_endpoint)
        sites = filtered_sites if filtered_sites is not None else []

    active_svcs = {}
    for site in sites:
        url = site.get("url", "")
        name = site.get("name", "Monitored Site")
        slug = name.lower().replace(" ", "-").replace("&", "and").replace("/", "-")
        hist = real_website_monitor.history.get(url, [])
        if not hist:
            # Skip nodes with zero real history (no fake 35ms placeholder)
            continue
        latest = hist[-1]
        lat = latest.get("latency_ms", 0.0)
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

    if not api_endpoint:
        for k, info in (api_key_manager.keys.items() if api_key_manager else []):
            if info.get("status") == "ACTIVE":
                slug = info.get("assigned_service", "custom-api")
                lat = info.get("latest_latency_ms")
                if slug not in active_svcs and lat is not None:
                    is_anomaly = lat > 250.0
                    active_svcs[slug] = {
                        "id": slug,
                        "label": info.get("name", slug),
                        "status": "HAZARD" if is_anomaly else "HEALTHY",
                        "anomaly_score": 3.8 if is_anomaly else 0.2,
                        "latency_ms": lat,
                        "type": "API Service"
                    }
    else:
        for k, info in (api_key_manager.keys.items() if api_key_manager else []):
            if info.get("status") == "ACTIVE":
                slug = info.get("assigned_service", "custom-api")
                name = info.get("name", slug)
                if slug == api_endpoint or name.lower() == api_endpoint.lower():
                    lat = info.get("latest_latency_ms")
                    if slug not in active_svcs and lat is not None:
                        is_anomaly = lat > 250.0
                        active_svcs[slug] = {
                            "id": slug,
                            "label": name,
                            "status": "HAZARD" if is_anomaly else "HEALTHY",
                            "anomaly_score": 3.8 if is_anomaly else 0.2,
                            "latency_ms": lat,
                            "type": "API Service"
                        }

    nodes = list(active_svcs.values())
    if not nodes:
        return {"status": "NO_DATA", "message": "No real telemetry ingested yet.", "nodes": [], "edges": []}

    edges = []
    # Real Causal Discovery: Only connect services if there is an explicit microservice dependency
    # or a statistically verified LagRCA cross-correlation (r >= 0.75) across concurrent telemetry
    try:
        from griffinops.rca.lag_rca import LagRCAEngine
        import pandas as pd

        # 1. Check explicit architecture topology from rca_engine if defined
        if rca_engine and hasattr(rca_engine, "topology") and rca_engine.topology:
            node_ids = {n["id"] for n in nodes}
            for src, targets in rca_engine.topology.items():
                if src in node_ids:
                    for tgt in targets:
                        if tgt in node_ids:
                            edges.append({
                                "source": src,
                                "target": tgt,
                                "lag_ms": 32
                            })

        # 2. Dynamic Spatio-Temporal Lag Correlation across real histories
        telemetry_dict = {}
        for node in nodes:
            node_id = node["id"]
            # Find matching site history
            matching_site = next((s for s in real_website_monitor.sites if s.get("name", "").lower().replace(" ", "-").replace("&", "and").replace("/", "-") == node_id or s.get("url") == node.get("url")), None)
            if matching_site:
                hist = real_website_monitor.history.get(matching_site["url"], [])
                if len(hist) >= 6:
                    telemetry_dict[node_id] = pd.DataFrame(hist)

        if len(telemetry_dict) >= 2:
            lag_engine = LagRCAEngine(max_lag_steps=10, sample_interval_sec=3.0)
            lag_scores, optimal_lags = lag_engine.compute_spatio_temporal_lag_correlation(telemetry_dict, primary_metric="latency_ms")
            for (u, v), score in lag_scores.items():
                if score >= 0.75: # Only strong, statistically proven correlation
                    if not any(e["source"] == u and e["target"] == v for e in edges):
                        lag_val = optimal_lags.get((u, v), 20)
                        edges.append({
                            "source": u,
                            "target": v,
                            "lag_ms": int(lag_val * 1000) if 0 < lag_val < 1.0 else int(lag_val if lag_val > 0 else 24)
                        })
    except Exception:
        pass

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
def get_latest_audit_report(algorithm: str = "composite", api_endpoint: Optional[str] = None):
    telemetry = {}
    if real_website_monitor:
        real_tel = real_website_monitor.get_all_real_telemetry()
        if api_endpoint:
            filtered_sites = _filter_sites_for_endpoint(api_endpoint)
            allowed_slugs = {
                s["name"].lower().replace(" ", "-").replace("&", "and").replace("/", "-")
                for s in (filtered_sites or [])
            }
            real_tel = {k: v for k, v in real_tel.items() if k in allowed_slugs or k == api_endpoint}
        for svc_name, df in real_tel.items():
            if not df.empty:
                telemetry[svc_name] = df.copy()

    if not telemetry:
        return {
            "status": "NO_DATA",
            "message": "No real telemetry received yet. Ingest SDK data to generate an audit report."
        }

    active_fault = fault_simulator.get_status().get("fault") if fault_simulator else None
    if active_fault:
        target = active_fault.get("target_service")
        if target and target in telemetry:
            df = telemetry[target]
            mult = active_fault.get("latency_multiplier", 3.5)
            df["latency_ms"] = df["latency_ms"] * mult
            if "cpu_spike_percent" in active_fault:
                df["cpu_percent"] = active_fault["cpu_spike_percent"]
            if "error_rate_spike" in active_fault:
                df["error_rate"] = active_fault["error_rate_spike"]

    z_scores = normalizer.compute_z_scores(telemetry)
    min_len = min([len(df) for df in telemetry.values()])
    tensor, service_names = normalizer.to_tensor_format(z_scores, sequence_length=min(30, max(5, min_len)))
    
    if tensor is None or len(service_names) == 0:
        return {
            "status": "NO_DATA",
            "message": "Insufficient telemetry history. Ingest more SDK data points."
        }

    tcn_results = tcn_predictor.predict(tensor, service_names=service_names)
    report = rca_engine.analyze_root_cause(tcn_results, z_scores, active_fault=active_fault, algorithm=algorithm)
    return report

@router.get("/audit-reports/{report_id}/pdf")
def download_pdf_report(report_id: str):
    report = get_latest_audit_report()
    if report.get("status") == "NO_DATA":
        raise HTTPException(status_code=400, detail="Cannot generate PDF: No real telemetry ingested yet.")
    report["report_id"] = report_id
    filepath = pdf_generator.generate_pdf_report(report)
    return FileResponse(filepath, media_type="application/pdf", filename=f"GriffinOps_Audit_Report_{report_id}.pdf")

# --- UNIFIED REPORT DOWNLOADS (PDF + DOCX) ---
@router.post("/reports/download")
def download_report(req: ReportDownloadRequest):
    """
    Generates a fresh audit report from current TCN/RCA state and streams it as a
    downloadable PDF or DOCX.  Body: { "format": "pdf"|"docx", "report_id": optional }.
    """
    report = get_latest_audit_report(api_endpoint=req.api_endpoint)
    if isinstance(report, dict) and report.get("status") == "NO_DATA":
        raise HTTPException(
            status_code=400,
            detail="Cannot generate report: No real telemetry ingested yet. Ingest SDK data first."
        )

    # Override report_id if the caller supplies one (e.g. the UI passes the cached id)
    if req.report_id:
        report["report_id"] = req.report_id

    fmt      = (req.format or "pdf").lower().strip()
    rid      = report.get("report_id", "LIVE")

    if fmt == "docx":
        filepath = docx_generator.generate_docx_audit_report(report)
        return FileResponse(
            filepath,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=f"GriffinOps_Audit_Report_{rid}.docx",
            headers={"Content-Disposition": f'attachment; filename="GriffinOps_Audit_Report_{rid}.docx"'}
        )
    else:  # default: pdf
        filepath = pdf_generator.generate_pdf_report(report)
        return FileResponse(
            filepath,
            media_type="application/pdf",
            filename=f"GriffinOps_Audit_Report_{rid}.pdf",
            headers={"Content-Disposition": f'attachment; filename="GriffinOps_Audit_Report_{rid}.pdf"'}
        )

@router.get("/watchdog/history")
def get_watchdog_history():
    return watchdog.get_dispatch_history() if watchdog else []

@router.post("/alerts/slack")
def trigger_slack_alert():
    report = get_latest_audit_report()
    return notifier.send_slack_alert(report)

@router.post("/alerts/slack/test")
def send_slack_test(req: Optional[SlackTestRequest] = None):
    target_url = req.slack_webhook_url if req else None
    return notifier.send_slack_test_alert(target_url=target_url)

@router.post("/alerts/email")
def trigger_email_alert(req: EmailAlertRequest):
    report = get_latest_audit_report()
    return notifier.send_email_notification(report, recipient_email=req.recipient_email)
