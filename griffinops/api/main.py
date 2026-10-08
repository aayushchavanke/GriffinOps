import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from griffinops.telemetry.ingestion import TelemetryIngestor
from griffinops.telemetry.normalizer import ZScoreNormalizer
from griffinops.models.tcn_forecaster import TCNPredictorEngine
from griffinops.rca.causal_engine import CausalRCAEngine
from griffinops.simulation.fault_simulator import FaultSimulatorManager
from griffinops.alerts.notifier import DualNotifier
from griffinops.api.keys import APIKeyManager
from griffinops.alerts.watchdog import BackgroundAlertWatchdog
from griffinops.reports.pdf_generator import PDFReportGenerator
from griffinops.db.storage import storage
import griffinops.api.routes as routes

app = FastAPI(
    title="GriffinOps Enterprise AI SRE Copilot & Developer Portal",
    description="Predictive AIOps Observability, PyTorch TCN Forecasting, RCA Causal Inference, and API Management",
    version="2.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize engine singletons
routes.telemetry_ingestor = TelemetryIngestor()
routes.normalizer = ZScoreNormalizer(window_size=30, epsilon=1e-5)
routes.tcn_predictor = TCNPredictorEngine()
routes.rca_engine = CausalRCAEngine()
routes.fault_simulator = FaultSimulatorManager()
routes.notifier = DualNotifier()
routes.api_key_manager = APIKeyManager()
routes.pdf_generator = PDFReportGenerator()

# Hydrate notifier with persisted credentials and Slack URL if available
_saved_profile = storage.load_profile()
if _saved_profile:
    if _saved_profile.get("slack_webhook_url"):
        routes.notifier.slack_webhook_url = _saved_profile["slack_webhook_url"]
    routes.notifier.update_credentials(
        smtp_host=_saved_profile.get("smtp_host"),
        smtp_port=_saved_profile.get("smtp_port") or 587,
        smtp_user=_saved_profile.get("smtp_user"),
        smtp_pass=_saved_profile.get("smtp_pass"),
        brevo_api_key=_saved_profile.get("brevo_api_key"),
        resend_api_key=_saved_profile.get("resend_api_key")
    )

# Initialize & start automated background watchdog daemon
routes.watchdog = BackgroundAlertWatchdog(
    telemetry_ingestor=routes.telemetry_ingestor,
    normalizer=routes.normalizer,
    tcn_predictor=routes.tcn_predictor,
    rca_engine=routes.rca_engine,
    fault_simulator=routes.fault_simulator,
    notifier=routes.notifier
)
routes.watchdog.start()

@app.on_event("startup")
def startup_event():
    storage.start_flusher()

@app.on_event("shutdown")
def shutdown_event():
    if routes.watchdog:
        routes.watchdog.stop()
    storage.shutdown()

# Include REST routers
app.include_router(routes.router)

# Mount static frontend SRE Dashboard
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/")
def serve_dashboard():
    index_file = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "GriffinOps Enterprise API running. Open /api/v1/health or dashboard UI."}

@app.get("/demo")
@app.get("/demo.html")
@app.get("/demo-site")
@app.get("/demo_website.html")
@app.get("/demo_site")
def serve_demo():
    demo_file = os.path.join(frontend_dir, "demo.html")
    if os.path.exists(demo_file):
        return FileResponse(demo_file)
    return {"message": "Demo target page"}
