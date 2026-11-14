"""Alerts route: Intelligent biomedical alert center and operational risk management."""
from typing import List, Optional
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from application.service import get_recent_alerts, get_alert_detail
from api.utils import sanitize_for_json

router = APIRouter(tags=["Alerts"])


@router.get("/alerts")
def get_alerts(
    limit: int = Query(default=50, ge=1, le=200, description="Max alerts to retrieve"),
    source_type: Optional[str] = Query(default=None, description="Filter: NASA_LAB or SYNTHETIC_WEARABLE"),
    state: Optional[str] = Query(default=None, description="Filter: NORMAL, REVIEW, ATTENTION, INSUFFICIENT_DATA"),
):
    """
    Retrieve explainable alerts from SQLite persistence.
    Supports filtering by source pathway and operational alert state.
    """
    raw_alerts = get_recent_alerts(limit=max(limit * 2, 50))

    filtered = []
    for item in raw_alerts:
        if not isinstance(item, dict):
            continue
        # Check source filter
        if source_type:
            item_source = item.get("source_type") or ("SYNTHETIC_WEARABLE" if item.get("is_synthetic") else "NASA_LAB")
            if item_source.upper() != source_type.upper():
                continue
        # Check state filter
        if state:
            alert_state = str(item.get("alert_state") or item.get("operational_state") or "").upper()
            if alert_state != state.upper():
                continue

        stats = item.get("statistical_evidence") or {}
        sensor = item.get("sensor_quality_evidence") or {}
        motion = item.get("motion_artifact_evidence") or {}
        item = {
            **item,
            "source_type": item.get("source_type") or ("SYNTHETIC_WEARABLE" if item.get("is_synthetic") else "NASA_LAB"),
            "biomarker_or_sensor": item.get("measurement_name") or "Unavailable",
            "trigger_reason": item.get("explanation"),
            "statistical_evidence": {
                **stats,
                "baseline_median": (item.get("baseline_context") or {}).get("median"),
                "measured_value": item.get("measurement_value"),
                "mad": (item.get("baseline_context") or {}).get("mad"),
            },
            "sensor_trust_context": {
                "quality_score": sensor.get("quality_score"),
                "reliability": sensor.get("reliability_category"),
                "motion_downgrade": bool(motion.get("motion_correlated")),
            },
            "human_review_guidance": "; ".join(item.get("recommended_workflow_actions") or []),
        }

        filtered.append(item)
        if len(filtered) >= limit:
            break

    return JSONResponse(content=sanitize_for_json(filtered))


@router.get("/alerts/{alert_id}")
def get_alert_detail_by_id(alert_id: str):
    record = get_alert_detail(alert_id)
    if not record:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Alert not found")
    return JSONResponse(content=sanitize_for_json(record))
