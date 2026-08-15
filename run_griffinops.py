import os
import sys
import uvicorn

def main():
    print("=" * 70)
    print(" 🦅 GriffinOps: Autonomous AI SRE Copilot Platform")
    print(" Predictive Observability, TCN Forecasting & Causal RCA")
    print(" SIES GST - AI & Data Science Team")
    print("=" * 70)
    
    # Ensure current directory is in PYTHONPATH
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
        
    print("\n[+] Starting GriffinOps FastAPI Intelligence API & SRE Dashboard...")
    print("[+] Dashboard Web App: http://localhost:8000")
    print("[+] OpenAPI Swagger Docs: http://localhost:8000/docs")
    print("[+] Press Ctrl+C to stop the server.\n")

    uvicorn.run(
        "griffinops.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    main()
