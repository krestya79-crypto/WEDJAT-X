"""WEDJAT-X FastAPI Adapter Main Application.
Unified REST Gateway bridging the mission-control React frontend and the core Python intelligence engine.
"""
from datetime import datetime, timezone
import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from api.routes.system import router as system_router
from api.routes.analysis import router as analysis_router
from api.routes.alerts import router as alerts_router
from api.routes.history import router as history_router
from application.schemas import NON_CLINICAL_DISCLAIMER

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("WEDJAT_X.API")

app = FastAPI(
    title="WEDJAT-X — Aerospace Medical Mission Control API",
    description=(
        "Next-generation aerospace medical decision-support backend for NASA Space Apps. "
        "Coordinates discrete NASA OSD-575 laboratory biomarker evaluation and synthetic wearable telemetry."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration allowing cross-origin requests from local dev and remote deployments
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers under /api
app.include_router(system_router, prefix="/api")
app.include_router(analysis_router, prefix="/api")
app.include_router(alerts_router, prefix="/api")
app.include_router(history_router, prefix="/api")


@app.get("/api")
def api_root():
    return {
        "system": "WEDJAT-X",
        "tagline": "Guarding Life Beyond Earth, When Every Heartbeat Matters.",
        "status": "OPERATIONAL",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "documentation": "/docs",
        "disclaimer": NON_CLINICAL_DISCLAIMER,
    }


# Serve React production build if available
FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if FRONTEND_DIST.exists():
    @app.get("/review/", include_in_schema=False)
    @app.get("/review/{alert_id}", include_in_schema=False)
    def review_spa(alert_id: str = ""):
        return FileResponse(FRONTEND_DIST / "index.html")

    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
else:
    @app.get("/")
    def fallback_root():
        return {
            "system": "WEDJAT-X",
            "tagline": "Guarding Life Beyond Earth, When Every Heartbeat Matters.",
            "status": "OPERATIONAL",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "documentation": "/docs",
            "frontend_status": "Build frontend via 'cd frontend && npm run build' to serve from root.",
            "disclaimer": NON_CLINICAL_DISCLAIMER,
        }


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled API error on path %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "path": request.url.path,
            "disclaimer": NON_CLINICAL_DISCLAIMER,
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
