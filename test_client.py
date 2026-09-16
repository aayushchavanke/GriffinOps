"""
GriffinOps Quick Test Client
Tests API Key Generation and Telemetry Ingestion against the running GriffinOps server.

Run: python test_client.py
"""
import time
import requests

BASE_URL = "http://localhost:8000/api/v1"

def test_pipeline():
    print("=" * 60)
    print("🦅 GRIFFINOPS API TELEMETRY TEST RUNNER")
    print("=" * 60)

    # 1. Health check
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=2.0)
        print(f"[*] Server Health Check: HTTP {r.status_code} -> {r.json().get('status')}")
    except Exception as e:
        print(f"[!] Server not running at {BASE_URL}. Please start 'python app.py' first.")
        return

    # 2. Create API Key
    site_name = "E-Commerce Checkout App"
    print(f"[*] Generating API Key for '{site_name}'...")
    r = requests.post(f"{BASE_URL}/keys/create", json={"name": site_name})
    if r.status_code == 200:
        data = r.json()
        api_key = data["api_key"]
        print(f"[+] Successfully Created API Key: {api_key}")
        print(f"[+] 1-Line Embed SDK Script:")
        print(f"    {data['sdk_snippets']['html']}\n")
    else:
        print(f"[!] Error creating API key: {r.text}")
        return

    # 3. Stream Telemetry Points
    print(f"[*] Streaming 5 real-time telemetry points into GriffinOps...")
    for i in range(1, 6):
        latency = 32.0 + (i * 3.5)
        payload = {
            "api_key": api_key,
            "latency_ms": latency,
            "status_code": 200,
            "endpoint": "https://store.internal/checkout"
        }
        res = requests.post(f"{BASE_URL}/telemetry/ingest", json=payload)
        print(f"    Point {i}: Latency={latency:.1f}ms, Status=200 -> Ingested ({res.status_code})")
        time.sleep(0.3)

    # 4. Verify Live Metrics
    r = requests.get(f"{BASE_URL}/real-monitor/live")
    print(f"\n[+] Verified Live Telemetry in GriffinOps:")
    for url, info in r.json().items():
        latest = info.get("latest", {})
        print(f"    - {info.get('name')}: Latency={latest.get('latency_ms')}ms (HTTP {latest.get('status_code')})")

    print("\n[🎉] Test Complete! Open http://localhost:8000 to see your live dashboard.")

if __name__ == "__main__":
    test_pipeline()
