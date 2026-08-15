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
from griffinops.dummy_app.app import DummyECommerceApp
from griffinops.alerts.watchdog import BackgroundAlertWatchdog
from griffinops.reports.pdf_generator import PDFReportGenerator
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
routes.dummy_app = DummyECommerceApp()
routes.pdf_generator = PDFReportGenerator()

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

# Include REST routers
app.include_router(routes.router)
app.include_router(routes.dummy_router)

# Mount static frontend SRE Dashboard
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

# Mount Standalone Dummy Store App (`/store`)
dummy_store_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dummy_store")
if os.path.exists(dummy_store_dir):
    app.mount("/store/static", StaticFiles(directory=dummy_store_dir), name="store_static")

@app.get("/store")
def serve_dummy_store():
    store_index = os.path.join(dummy_store_dir, "index.html")
    if os.path.exists(store_index):
        return FileResponse(store_index)
    return {"message": "Dummy Store UI under construction."}

@app.get("/")
def serve_dashboard():
    index_file = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "GriffinOps Enterprise API running. Open /api/v1/health or dashboard UI."}
