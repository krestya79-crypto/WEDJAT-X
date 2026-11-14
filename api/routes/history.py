"""History route: Processing audit logs and analysis session persistence."""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from application.service import get_analysis_history
from api.utils import sanitize_for_json

router = APIRouter(tags=["History"])


@router.get("/history")
def get_history(
    limit: int = Query(default=50, ge=1, le=200, description="Max history sessions to retrieve"),
    source_type: Optional[str] = Query(default=None, description="Filter: NASA_LAB or SYNTHETIC_WEARABLE"),
    summary: bool = Query(default=False, description="Return compact session summaries for dashboard polling"),
):
    """Retrieve chronologically ordered analysis history sessions from SQLite persistence."""
    history = get_analysis_history(limit=max(limit * 2, 50))
    filtered = []
    for item in history:
        if not isinstance(item, dict):
            continue
        if source_type:
            item_source = item.get("source_type") or ("SYNTHETIC_WEARABLE" if item.get("is_synthetic") else "NASA_LAB")
            if item_source.upper() != source_type.upper():
                continue
        if summary:
            measurements = item.get("measurements") or []
            item = {
                "request_id": item.get("request_id"),
                "timestamp": item.get("timestamp"),
                "source_type": item.get("source_type"),
                "subject_id": item.get("subject_id") or item.get("astronaut_id"),
                "is_synthetic": item.get("is_synthetic"),
                "processing_status": item.get("processing_status"),
                "disclaimer": item.get("disclaimer", ""),
                "measurement_count": len(measurements),
                "alert": item.get("alert"),
                "warnings": item.get("warnings", []),
                "errors": item.get("errors", []),
            }
        filtered.append(item)
        if len(filtered) >= limit:
            break

    return JSONResponse(content=sanitize_for_json(filtered))


@router.get("/history/{request_id}")
def get_history_by_id(request_id: str):
    """Retrieve a single persisted analysis session by its unique request ID."""
    history = get_analysis_history(limit=200)
    for item in history:
        if isinstance(item, dict) and item.get("request_id") == request_id:
            return JSONResponse(content=sanitize_for_json(item))
    raise HTTPException(status_code=404, detail=f"Analysis session '{request_id}' not found.")
