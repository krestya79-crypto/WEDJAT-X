"""Full API verification script — runs uvicorn in a thread and checks all endpoints."""
import uvicorn, threading, time, urllib.request, json, sys

def run_server():
    uvicorn.run("api.main:app", host="127.0.0.1", port=8001, log_level="warning")

t = threading.Thread(target=run_server, daemon=True)
t.start()
print("Starting server...", flush=True)
time.sleep(6)
print("Server ready — running checks\n", flush=True)

BASE = "http://127.0.0.1:8001"
passed = 0
failed = 0

def check_get(path, label=None):
    global passed, failed
    label = label or path
    try:
        req = urllib.request.Request(BASE + path, method="GET")
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read())
            if isinstance(data, list):
                desc = f"list({len(data)} items)"
            else:
                desc = f"keys={list(data.keys())[:5]}"
            print(f"  OK   {label:<35} {desc}")
            passed += 1
            return data
    except Exception as e:
        print(f"  FAIL {label:<35} {e}")
        failed += 1
        return None

def check_post(path, body, label=None):
    global passed, failed
    label = label or path
    try:
        payload = json.dumps(body).encode()
        req = urllib.request.Request(
            BASE + path, data=payload,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=35) as r:
            data = json.loads(r.read())
            alert = data.get("alert_state", data.get("status", "?"))
            synth = data.get("is_synthetic", "?")
            print(f"  OK   {label:<35} alert_state={alert}, is_synthetic={synth}")
            passed += 1
            return data
    except Exception as e:
        print(f"  FAIL {label:<35} {e}")
        failed += 1
        return None

print("=== GET ENDPOINTS ===")
check_get("/api/health",              "GET /api/health")
check_get("/api/system/status",       "GET /api/system/status")
check_get("/api/alerts",              "GET /api/alerts")
check_get("/api/history",             "GET /api/history")
check_get("/api/analysis/latest",     "GET /api/analysis/latest")
check_get("/api/nasa/participants",   "GET /api/nasa/participants")
check_get("/api/nasa/biomarkers",     "GET /api/nasa/biomarkers")
check_get("/api/scenarios",           "GET /api/scenarios")

print("\n=== POST ENDPOINTS ===")
check_post("/api/analysis/nasa",
           {"participant_id": "C001", "time_point": "L+30"},
           "POST /api/analysis/nasa (C001 L+30)")

check_post("/api/analysis/wearable",
           {"scenario": "normal_baseline"},
           "POST /api/analysis/wearable (normal_baseline)")

print(f"\n=== RESULT: {passed} passed, {failed} failed ===")
sys.exit(0 if failed == 0 else 1)
