"""Analysis routes: NASA laboratory biomarker processing and synthetic wearable telemetry analysis."""
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
import pandas as pd

from application.service import (
    analyze_nasa_sample,
    analyze_wearable_stream,
    get_latest_analysis,
)
from application.exceptions import WedjatXError, ValidationError, UnsupportedSourceError
from api.schemas import NasaAnalysisRequest, WearableAnalysisRequest
from api.utils import (
    get_nasa_dataframe,
    sanitize_for_json,
    SYNTHETIC_DIR,
    NASA_DATA_PATH,
)

router = APIRouter(tags=["Analysis"])

TIMEPOINT_ORDER = ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82", "R+194"]


@router.post("/analysis/nasa")
def run_nasa_analysis(request: NasaAnalysisRequest):
    """
    Execute NASA OSD-575 discrete laboratory biomarker analysis.
    Uses personal preflight baselines across 7 mission collection milestones.
    """
    participant_id = (request.participant_id or "C001").strip().upper()
    metadata = dict(request.metadata or {})
    metadata["astronaut_id"] = participant_id
    metadata["source_file"] = NASA_DATA_PATH.name
    metadata["provenance"] = "NASA OSD-575 Audited Master Dataset"

    try:
        if request.data:
            df = pd.DataFrame(request.data)
        else:
            if not NASA_DATA_PATH.exists():
                raise HTTPException(status_code=404, detail="NASA Master Dataset file not found.")
            df = get_nasa_dataframe()

        result = analyze_nasa_sample(df, metadata=metadata)
        result_dict = result.to_dict() if hasattr(result, "to_dict") else result
        return JSONResponse(content=sanitize_for_json(result_dict))

    except (WedjatXError, ValidationError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"NASA analysis error: {str(e)}")


@router.post("/analysis/wearable")
def run_wearable_analysis(request: WearableAnalysisRequest):
    """
    Execute synthetic wearable physiological telemetry stream analysis.
    Requires is_synthetic=True provenance. Evaluates sensor trust, motion artifacts, and alerts.
    """
    metadata = dict(request.metadata or {})
    scenario_name = request.scenario_name or "normal_scenario.csv"
    metadata["scenario"] = scenario_name
    metadata["is_synthetic"] = True
    metadata["subject_id"] = request.subject_id or "SYNTHETIC_ASTRONAUT"

    try:
        if request.data:
            df = pd.DataFrame(request.data)
            if "is_synthetic" not in df.columns:
                df["is_synthetic"] = True
            else:
                df["is_synthetic"] = True
        else:
            scenario_path = SYNTHETIC_DIR / scenario_name
            if not scenario_path.exists():
                raise HTTPException(status_code=404, detail=f"Scenario file '{scenario_name}' not found.")
            df = pd.read_csv(scenario_path)
            df["is_synthetic"] = True

        result = analyze_wearable_stream(df, metadata=metadata)
        result_dict = result.to_dict() if hasattr(result, "to_dict") else result
        return JSONResponse(content=sanitize_for_json(result_dict))

    except (WedjatXError, ValidationError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Wearable analysis error: {str(e)}")


@router.get("/analysis/latest")
def get_latest_result(source_type: Optional[str] = Query(default=None)):
    """Retrieve the most recently saved analysis result from SQLite offline persistence."""
    result = get_latest_analysis(source_type=source_type)
    if not result:
        return JSONResponse(content=None)
    return JSONResponse(content=sanitize_for_json(result))


@router.get("/nasa/participants")
def get_nasa_participants():
    """Retrieve catalog of NASA Inspiration4 participants and summary profile counts."""
    df = get_nasa_dataframe()
    participants = sorted(df["Participant_ID"].dropna().unique().tolist())
    catalog = []
    for pid in participants:
        sub = df[df["Participant_ID"] == pid]
        catalog.append({
            "participant_id": pid,
            "display_name": f"Participant {pid}",
            "role": "OSD-575 study participant",
            "callsign": "",
            "mission": "Inspiration4 (OSD-575)",
            "total_observations": len(sub),
            "total_biomarkers": sub["Biomarker_Name"].nunique(),
            "panels": sorted(sub["Panel_Name"].dropna().unique().tolist()),
            "timepoints": [tp for tp in TIMEPOINT_ORDER if tp in set(sub["Timepoint"].dropna())],
        })
    return JSONResponse(content=sanitize_for_json(catalog))


@router.get("/nasa/biomarkers")
def get_nasa_biomarkers(
    participant_id: Optional[str] = Query(default=None),
    panel_name: Optional[str] = Query(default=None),
):
    """Retrieve unique biomarker list and metadata grouped by panel and participant."""
    df = get_nasa_dataframe()
    if participant_id:
        participant_id = participant_id.strip().upper()
        # Always filter the shared master table before deriving this participant's catalog.
        # The cached object is the source table only; no participant result is cached.
        df = df.loc[df["Participant_ID"].astype(str).str.upper() == participant_id]
    if panel_name:
        df = df[df["Panel_Name"] == panel_name]

    grouped = {}
    for panel in sorted(df["Panel_Name"].dropna().unique()):
        p_df = df[df["Panel_Name"] == panel]
        b_list = sorted(p_df["Biomarker_Name"].dropna().unique().tolist())
        grouped[panel] = b_list

    all_biomarkers = sorted(df["Biomarker_Name"].dropna().unique().tolist())
    all_timepoints = sorted(df["Timepoint"].dropna().unique().tolist())
    all_panels = sorted(df["Panel_Name"].dropna().unique().tolist())

    return JSONResponse(content=sanitize_for_json({
        "participant_id": participant_id,
        "total_biomarkers": len(all_biomarkers),
        "panels": all_panels,
        "timepoints": all_timepoints,
        "by_panel": grouped,
        "biomarkers": all_biomarkers,
    }))


@router.get("/nasa/participant-data")
def get_nasa_participant_data(
    participant_id: str = Query(..., description="Participant ID: C001, C002, C003, or C004"),
    biomarker_name: Optional[str] = Query(default=None, description="Specific biomarker name"),
    panel_name: Optional[str] = Query(default=None, description="Optional panel filter"),
):
    """
    Query discrete NASA OSD-575 laboratory assay observations for a participant.
    Computes preflight baseline median and MAD for selected biomarker if provided.
    """
    participant_id = participant_id.strip().upper()
    df = get_nasa_dataframe()
    # Filter by the selected participant first. Empty/unknown IDs stay empty; never fall back
    # to the complete dataset or another participant's records.
    sub = df.loc[df["Participant_ID"].astype(str).str.upper() == participant_id]

    if panel_name:
        sub = sub[sub["Panel_Name"] == panel_name]
    if biomarker_name:
        sub = sub[sub["Biomarker_Name"] == biomarker_name]

    records = sub.sort_values(by=["Timepoint_Order", "Timepoint"]).to_dict(orient="records")

    baseline_info = None
    if biomarker_name:
        preflight = sub[sub["Timepoint_Phase"].astype(str).str.upper() == "PREFLIGHT"]
        vals = preflight["Measurement_Value"].dropna().tolist()
        if vals:
            median_val = float(pd.Series(vals).median())
            mad_val = float((pd.Series(vals) - median_val).abs().median() * 1.4826)
            baseline_info = {
                "biomarker_name": biomarker_name,
                "preflight_samples": len(vals),
                "baseline_median": median_val,
                "baseline_mad": mad_val,
                "measurement_unit": str(sub["Measurement_Unit"].iloc[0]) if len(sub) > 0 and pd.notna(sub["Measurement_Unit"].iloc[0]) else "",
            }

    return JSONResponse(content=sanitize_for_json({
        "participant_id": participant_id,
        "biomarker_name": biomarker_name,
        "record_count": len(records),
        "baseline_info": baseline_info,
        "records": records,
    }))


@router.get("/scenarios")
def list_scenarios():
    """List available local synthetic wearable sensor scenarios."""
    if not SYNTHETIC_DIR.exists():
        return JSONResponse(content=[])

    files = sorted(SYNTHETIC_DIR.glob("*_scenario.csv"))
    scenarios = []
    descriptions = {
        "normal_scenario.csv": "Baseline continuous multi-sensor telemetry under nominal spacecraft conditions.",
        "missing_data_scenario.csv": "Simulated telemetry with intentional data dropouts and missing measurement gaps.",
        "motion_artifact_scenario.csv": "Kinetic exercise interference detected via concurrent accelerometer cross-checking.",
        "noise_scenario.csv": "High-frequency electromagnetic and physiological interference across sensor channels.",
        "sensor_disconnect_scenario.csv": "Complete sensor lead detachment and signal loss evaluation.",
        "signal_drift_scenario.csv": "Slow sensor calibration drift and photoplethysmography baseline displacement.",
    }

    for f in files:
        df = pd.read_csv(f)
        scenarios.append({
            "filename": f.name,
            "scenario_name": f.name.replace("_scenario.csv", "").replace("_", " ").title(),
            "description": descriptions.get(f.name, "Synthetic physiological test scenario."),
            "total_samples": len(df),
            "sensor_types": sorted(df["sensor_type"].dropna().unique().tolist()) if "sensor_type" in df.columns else [],
            "missing_count": int(df["signal_value"].isna().sum()) if "signal_value" in df.columns else 0,
            "is_synthetic": True,
        })

    return JSONResponse(content=sanitize_for_json(scenarios))


@router.get("/scenarios/{name}")
def get_scenario_data(name: str):
    """Retrieve time-series records for a specific synthetic wearable scenario."""
    clean_name = Path(name).name
    path = SYNTHETIC_DIR / clean_name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Scenario '{name}' not found.")

    df = pd.read_csv(path)
    records = df.to_dict(orient="records")
    return JSONResponse(content=sanitize_for_json({
        "filename": clean_name,
        "total_samples": len(records),
        "is_synthetic": True,
        "records": records,
    }))
