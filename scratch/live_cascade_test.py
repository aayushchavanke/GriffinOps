import os
import sys
import time
import json
import urllib.request

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

base = "http://127.0.0.1:8000"

print("===============================================================")
print("[1/4] Generating API Key for Checkout Microservice...")
key_payload = {
    "name": "Checkout Microservice",
    "endpoint": "/api/v1/checkout",
    "sla_latency_ms": 200.0,
    "sla_tier": "Payment ($850/min)",
    "target_url": "https://httpbin.org/get"
}
key_req = urllib.request.Request(
    f"{base}/api/v1/keys/create",
    data=json.dumps(key_payload).encode(),
    headers={"Content-Type": "application/json"}
)
key_data = json.loads(urllib.request.urlopen(key_req).read())
api_key = key_data["api_key"]
print(f"[OK] API Key Generated: {api_key}")

print("\n[2/4] Streaming 3 Nominal Baseline Pings (Latency: 45ms - 75ms)...")
for i in range(3):
    lat = round(52.0 + (i * 8.5), 2)
    payload = {
        "api_key": api_key,
        "endpoint": "/api/v1/checkout",
        "latency_ms": lat,
        "status_code": 200,
        "payload_bytes": 2048
    }
    req = urllib.request.Request(
        f"{base}/api/v1/telemetry/ingest",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    res = json.loads(urllib.request.urlopen(req).read())
    print(f"   * Ping {i+1}: Latency = {lat}ms | HTTP 200 OK | Ingest Status = {res.get('status')}")
    time.sleep(1)

print("\n[3/4] INJECTING CASCADING LATENCY SPIKE (DB Connection Pool Starvation)...")
cascade_points = [480.0, 1180.0, 1950.0, 2750.0]
for idx, lat in enumerate(cascade_points):
    status_code = 500 if idx >= 2 else 200
    payload = {
        "api_key": api_key,
        "endpoint": "/api/v1/checkout",
        "latency_ms": lat,
        "status_code": status_code,
        "payload_bytes": 1024
    }
    req = urllib.request.Request(
        f"{base}/api/v1/telemetry/ingest",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    res = json.loads(urllib.request.urlopen(req).read())
    sigma_dev = round(lat / 52.0, 1)
    print(f"   [!] Cascade Wave {idx+1}: Latency = {lat}ms (+{sigma_dev}x baseline) | HTTP {status_code} | Ingested!")
    time.sleep(1)

print("\n[4/4] Querying GriffinOps PyTorch TCN Forecast & Multi-Agent RCA Report...")
time.sleep(1)
forecast_req = urllib.request.urlopen(f"{base}/api/v1/forecast")
forecast_res = json.loads(forecast_req.read())

rca_req = urllib.request.urlopen(f"{base}/api/v1/audit-reports/latest")
rca_res = json.loads(rca_req.read())

print("\n==================== LIVE PREDICTION & RCA RESULTS ====================")
print(f"• System Status:            {rca_res.get('system_status')}")
print(f"• Severity Level:           {rca_res.get('severity_level')}")
print(f"• Forecast Time-to-Failure: {rca_res.get('forecasted_time_to_failure_human')}")
print(f"• Financial Risk / Minute:  {rca_res.get('business_impact', {}).get('estimated_loss_per_minute')}")
print(f"• Business Impact Summary:  {rca_res.get('business_impact', {}).get('summary')}")
print(f"• Isolated Root Cause:      {rca_res.get('root_cause_analysis', {}).get('service')}")
print(f"• Breached Metric:          {rca_res.get('root_cause_analysis', {}).get('primary_metric')} (Z-Score: +{rca_res.get('root_cause_analysis', {}).get('max_z_score_deviation')}\u03c3)")
print(f"• Causal Confidence Score:  {round(rca_res.get('root_cause_analysis', {}).get('causal_confidence_score', 0) * 100, 1)}%")

multi_agent = rca_res.get("multi_agent_sre_trio", {})
if multi_agent:
    nav = multi_agent.get("navigator_agent", {})
    diag = multi_agent.get("diagnoser_agent", {})
    ver = multi_agent.get("verifier_agent", {})
    print(f"\n[Multi-Agent SRE Pipeline]")
    print(f"   1. Navigator Agent:  Traversed {nav.get('traversed_path')} (Blast Depth: {nav.get('blast_radius_depth')})")
    print(f"   2. Diagnoser Agent:  Isolated Culprit '{diag.get('isolated_culprit')}' | Metric Breach: {diag.get('primary_metric_breached')} ({diag.get('max_deviation_sigma')})")
    print(f"   3. Verifier Agent:   Status '{ver.get('status')}' - {ver.get('safety_check')}")

print(f"\n• Suggested Action:         {rca_res.get('suggested_action')}")
print(f"• Automated Rollback Cmd:   {rca_res.get('remediation_command')}")
print("==========================================================================")
