"""
WEDJAT-X — Single Command Full-Stack Launcher.
Starts the FastAPI backend service and serves the production React frontend.
"""
import os
import sys
import webbrowser
from pathlib import Path
import uvicorn

ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"

def main():
    print("=" * 70)
    print("WEDJAT-X — AEROSPACE MEDICAL MISSION CONTROL")
    print("Guarding Life Beyond Earth, When Every Heartbeat Matters.")
    print("=" * 70)

    if not FRONTEND_DIST.exists():
        print("[WARNING] Frontend production build not found at frontend/dist.")
        print("[INFO] Building frontend now...")
        os.system("cd frontend && npm run build")

    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")

    print(f"\n[MISSION CONTROL] Web Application: http://{host}:{port}")
    print(f"[MISSION CONTROL] API Documentation: http://{host}:{port}/docs")
    print(f"[MISSION CONTROL] Health Endpoint:   http://{host}:{port}/api/health")
    print("\nPress Ctrl+C to terminate mission control.\n")

    # Optionally open browser
    try:
        if "--open" in sys.argv:
            webbrowser.open(f"http://{host}:{port}")
    except Exception:
        pass

    uvicorn.run("api.main:app", host=host, port=port, reload=False)

if __name__ == "__main__":
    main()
