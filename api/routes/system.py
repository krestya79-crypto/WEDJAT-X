"""System routes: Health check, operational status, and telemetry engines."""
from datetime import datetime, timezone
from fastapi import APIRouter
from application.service import get_system_status, get_analysis_count, get_alert_count, get_latest_sensor_trust, get_latest_analysis
from application.schemas import NON_CLINICAL_DISCLAIMER
from api.schemas import HealthResponse

router = APIRouter(tags=["System"])


def _latest_active_alert_count() -> int:
    """Count flagged entries in the newest analysis payload, not cumulative SQLite rows."""
    result = get_latest_analysis() or {}
    alert_summary = result.get("alert") or {}
    alerts = alert_summary.get("active_alerts") or []
    return sum(1 for alert in alerts if alert.get("alert_state") in {"ATTENTION", "REVIEW", "CRITICAL"})


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Return WEDJAT-X backend service health and operational heartbeat."""
    return HealthResponse(
        status="ok",
        system="WEDJAT-X",
        backend_version="1.0.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
        disclaimer=NON_CLINICAL_DISCLAIMER,
    )


@router.get("/system/status")
def system_status():
    """Return operational state, intelligence engine availability, and configuration."""
    status_dict = get_system_status()
    return {**status_dict, "analysis_count": get_analysis_count(),
            "active_alert_count": _latest_active_alert_count()}


@router.get("/metrics")
def dashboard_metrics():
    """Return persisted dashboard totals and the latest synthetic sensor trust record."""
    return {
        "analysis_count": get_analysis_count(),
        "active_alert_count": _latest_active_alert_count(),
        "persisted_active_alert_count": get_alert_count(active_only=True),
        "alert_record_count": get_alert_count(),
        "latest_sensor_trust": get_latest_sensor_trust(),
    }
