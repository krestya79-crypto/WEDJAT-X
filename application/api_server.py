"""Small stdlib HTTP adapter for the Vite dashboard; all analysis uses application.service."""
from __future__ import annotations

import json
import logging
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, unquote, urlparse

import pandas as pd

from application.exceptions import WedjatXError
from application.schemas import json_safe
from application.service import (
    analyze_nasa_sample,
    analyze_wearable_stream,
    get_alert_count,
    get_analysis_count,
    get_analysis_history,
    get_latest_analysis,
    get_latest_sensor_trust,
    get_recent_alerts,
    get_system_status,
)

LOGGER = logging.getLogger("WEDJAT_X.API")
ROOT = Path(__file__).resolve().parents[1]
NASA_DATA = ROOT / "cleaned_data" / "WEDJAT_X_Master_Biomarker_Dataset.csv"
SCENARIO_DIR = ROOT / "synthetic_data"
TIMEPOINT_ORDER = ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82", "R+194"]


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def _alert_for_frontend(item: dict[str, Any]) -> dict[str, Any]:
    synthetic = item.get("is_synthetic") is True
    stats = item.get("statistical_evidence") or {}
    sensor = item.get("sensor_quality_evidence") or {}
    motion = item.get("motion_artifact_evidence") or {}
    return {
        **item,
        "source_type": "SYNTHETIC_WEARABLE" if synthetic else "NASA_LAB",
        "biomarker_or_sensor": item.get("measurement_name") or "Unavailable",
        "trigger_reason": item.get("explanation"),
        "statistical_evidence": {
            "robust_z": stats.get("robust_z"),
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


class DashboardAPI:
    """Endpoint implementation that can also be called directly by integration tests."""

    def __init__(self, root: Path = ROOT) -> None:
        self.root = Path(root)
        self.nasa_path = self.root / "cleaned_data" / "WEDJAT_X_Master_Biomarker_Dataset.csv"
        self.scenario_dir = self.root / "synthetic_data"

    def health(self) -> dict[str, Any]:
        status = get_system_status()
        return {"status": status["status"], "system": status["system"], "backend_version": status["backend_version"]}

    def system_status(self) -> dict[str, Any]:
        return {**get_system_status(), "analysis_count": get_analysis_count(),
                "active_alert_count": self.latest_active_alert_count(),
                "latest_sensor_trust": get_latest_sensor_trust()}

    def latest_active_alert_count(self) -> int:
        latest = get_latest_analysis() or {}
        alerts = (latest.get("alert") or {}).get("active_alerts") or []
        return sum(1 for alert in alerts if alert.get("alert_state") in {"ATTENTION", "REVIEW", "CRITICAL"})

    def participants(self) -> list[dict[str, Any]]:
        if not self.nasa_path.is_file():
            raise FileNotFoundError("The audited NASA OSD-575 master dataset is unavailable.")
        frame = pd.read_csv(self.nasa_path)
        result = []
        for participant in sorted(frame["Participant_ID"].dropna().astype(str).unique()):
            subset = frame[frame["Participant_ID"].astype(str) == participant]
            result.append({
                "participant_id": participant,
                "display_name": f"Participant {participant}",
                "role": "OSD-575 study participant",
                "callsign": "",
                "mission": "Inspiration4 (OSD-575)",
                "total_observations": int(len(subset)),
                "total_biomarkers": int(subset["Biomarker_Name"].nunique()),
                "panels": sorted(subset["Panel_Name"].dropna().astype(str).unique().tolist()),
                "timepoints": [tp for tp in TIMEPOINT_ORDER if tp in set(subset["Timepoint"].dropna())],
            })
        return result

    def biomarkers(self, participant: Optional[str] = None, panel: Optional[str] = None) -> dict[str, Any]:
        frame = pd.read_csv(self.nasa_path)
        if participant:
            frame = frame[frame["Participant_ID"].astype(str) == participant]
        if panel:
            frame = frame[frame["Panel_Name"].astype(str) == panel]
        by_panel = {str(name): sorted(group["Biomarker_Name"].dropna().astype(str).unique().tolist())
                    for name, group in frame.groupby("Panel_Name", dropna=True)}
        return {"total_biomarkers": int(frame["Biomarker_Name"].nunique()),
                "panels": sorted(by_panel), "timepoints": [tp for tp in TIMEPOINT_ORDER if tp in set(frame["Timepoint"].dropna())],
                "by_panel": by_panel, "biomarkers": sorted(frame["Biomarker_Name"].dropna().astype(str).unique().tolist())}

    def participant_data(self, participant: str, biomarker: Optional[str] = None,
                         panel: Optional[str] = None) -> dict[str, Any]:
        if participant not in {p["participant_id"] for p in self.participants()}:
            raise ValueError("Participant ID is not available in the NASA OSD-575 dataset.")
        frame = pd.read_csv(self.nasa_path)
        frame = frame[frame["Participant_ID"].astype(str) == participant]
        if biomarker:
            frame = frame[frame["Biomarker_Name"].astype(str) == biomarker]
        if panel:
            frame = frame[frame["Panel_Name"].astype(str) == panel]
        baseline_info = None
        if biomarker:
            from intelligence.baseline import BaselineEngine
            baseline_frame = BaselineEngine(data_source=pd.read_csv(self.nasa_path)).calculate_baseline(participant)
            match = baseline_frame[baseline_frame["Biomarker_Name"].astype(str) == biomarker]
            if panel and "Panel_Name" in match:
                match = match[match["Panel_Name"].astype(str) == panel]
            if not match.empty:
                row = match.iloc[0]
                median, mad = row.get("Baseline_Median"), row.get("Baseline_MAD")
                baseline_info = {
                    "biomarker_name": biomarker,
                    "preflight_samples": int(row.get("Preflight_Sample_Count", 0)),
                    "baseline_median": None if pd.isna(median) else float(median),
                    "baseline_mad": None if pd.isna(mad) else float(mad),
                    "measurement_unit": str(row.get("Measurement_Unit", "")),
                }
        return {"participant_id": participant, "biomarker_name": biomarker,
                "record_count": int(len(frame)), "baseline_info": baseline_info,
                "records": _records(frame)}

    def scenarios(self) -> list[dict[str, Any]]:
        output = []
        for path in sorted(self.scenario_dir.glob("*_scenario.csv")):
            frame = pd.read_csv(path)
            scenario = str(frame["scenario"].dropna().iloc[0]) if "scenario" in frame and frame["scenario"].notna().any() else path.stem
            output.append({"filename": path.name, "scenario_name": scenario,
                           "description": f"Locally stored synthetic {scenario.lower().replace('_',' ')} test scenario.",
                           "total_samples": int(len(frame)),
                           "sensor_types": sorted(frame["sensor_type"].dropna().astype(str).unique().tolist()),
                           "missing_count": int(frame["signal_value"].isna().sum()), "is_synthetic": True})
        return output

    def scenario_data(self, name: str) -> dict[str, Any]:
        if Path(name).name != name or not name.endswith("_scenario.csv"):
            raise ValueError("Unknown synthetic scenario filename.")
        path = self.scenario_dir / name
        if not path.is_file():
            raise FileNotFoundError("Synthetic scenario was not found.")
        frame = pd.read_csv(path)
        if "is_synthetic" not in frame or not frame["is_synthetic"].map(lambda x: isinstance(x, (bool,)) and x or str(x).lower() == "true").all():
            raise ValueError("Scenario file is missing explicit synthetic provenance.")
        return {"filename": name, "total_samples": int(len(frame)), "is_synthetic": True,
                "records": _records(frame)}

    def run_nasa(self, participant: str) -> dict[str, Any]:
        available = {p["participant_id"] for p in self.participants()}
        if participant not in available:
            raise ValueError("Participant ID is not available in the NASA OSD-575 dataset.")
        result = analyze_nasa_sample(pd.read_csv(self.nasa_path), metadata={"astronaut_id": participant, "source_file": self.nasa_path.name})
        return result.to_dict()

    def run_wearable(self, scenario: str, subject_id: str = "SYNTHETIC_ASTRONAUT") -> dict[str, Any]:
        data = self.scenario_data(scenario)
        result = analyze_wearable_stream(pd.DataFrame(data["records"]), metadata={"subject_id": subject_id, "scenario": scenario})
        return result.to_dict()

    def alerts(self, limit: int = 50, source_type: Optional[str] = None,
               state: Optional[str] = None) -> list[dict[str, Any]]:
        raw = get_recent_alerts(max(0, min(limit, 500)))
        mapped = [_alert_for_frontend(item) for item in raw]
        if source_type:
            mapped = [item for item in mapped if item["source_type"] == source_type]
        if state:
            mapped = [item for item in mapped if item["alert_state"] == state]
        return mapped

    def history(self, limit: int = 50, source_type: Optional[str] = None,
                summary: bool = False) -> list[dict[str, Any]]:
        rows = get_analysis_history(max(0, min(limit, 200)))
        selected = [row for row in rows if not source_type or row.get("source_type") == source_type]
        if not summary:
            return selected
        return [{"request_id": row.get("request_id"), "timestamp": row.get("timestamp"),
                 "source_type": row.get("source_type"), "subject_id": row.get("subject_id") or row.get("astronaut_id"),
                 "is_synthetic": row.get("is_synthetic"), "processing_status": row.get("processing_status"),
                 "disclaimer": row.get("disclaimer", ""), "measurement_count": len(row.get("measurements") or []),
                 "alert": row.get("alert"), "warnings": row.get("warnings", []), "errors": row.get("errors", [])}
                for row in selected]


def make_handler(api: DashboardAPI):
    class Handler(BaseHTTPRequestHandler):
        server_version = "WEDJATXLocalAPI/1.0"

        def log_message(self, fmt: str, *args: Any) -> None:
            LOGGER.info("%s - %s", self.address_string(), fmt % args)

        def _send(self, payload: Any, status: int = 200) -> None:
            body = json.dumps(json_safe(payload), allow_nan=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:
            self._send({}, 204)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            try:
                routes = {
                    "/api/health": api.health,
                    "/api/system/status": api.system_status,
                    "/api/nasa/participants": api.participants,
                    "/api/scenarios": api.scenarios,
                    "/api/analysis/latest": get_latest_analysis,
                }
                if parsed.path in routes:
                    return self._send(routes[parsed.path]())
                if parsed.path == "/api/metrics":
                    return self._send({"analysis_count": get_analysis_count(),
                                       "active_alert_count": api.latest_active_alert_count(),
                                       "persisted_active_alert_count": get_alert_count(active_only=True),
                                       "alert_record_count": get_alert_count(),
                                       "latest_sensor_trust": get_latest_sensor_trust()})
                if parsed.path == "/api/nasa/biomarkers":
                    return self._send(api.biomarkers(query.get("participant_id", [None])[0], query.get("panel_name", [None])[0]))
                if parsed.path == "/api/nasa/participant-data":
                    participant = query.get("participant_id", [None])[0]
                    if not participant: return self._send({"detail": "participant_id is required"}, 400)
                    return self._send(api.participant_data(participant, query.get("biomarker_name", [None])[0], query.get("panel_name", [None])[0]))
                match = re.fullmatch(r"/api/scenarios/([^/]+)", parsed.path)
                if match:
                    return self._send(api.scenario_data(unquote(match.group(1))))
                if parsed.path == "/api/alerts":
                    return self._send(api.alerts(int(query.get("limit", [50])[0]), query.get("source_type", [None])[0], query.get("state", [None])[0]))
                if parsed.path == "/api/history":
                    return self._send(api.history(int(query.get("limit", [50])[0]), query.get("source_type", [None])[0],
                                                  query.get("summary", ["false"])[0].lower() == "true"))
                return self._send({"detail": "Endpoint not found"}, 404)
            except (ValueError, FileNotFoundError, WedjatXError) as exc:
                return self._send({"detail": str(exc)}, 400)
            except Exception as exc:
                LOGGER.exception("GET %s failed", self.path)
                return self._send({"detail": f"Backend request failed: {exc}"}, 500)

        def do_POST(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 1_000_000:
                    return self._send({"detail": "Request body is empty or exceeds 1 MB"}, 413)
                body = json.loads(self.rfile.read(length))
                if self.path == "/api/analysis/nasa":
                    result = api.run_nasa(str(body.get("participant_id", "")))
                elif self.path == "/api/analysis/wearable":
                    result = api.run_wearable(str(body.get("scenario_name", "")), str(body.get("subject_id", "SYNTHETIC_ASTRONAUT")))
                else:
                    return self._send({"detail": "Endpoint not found"}, 404)
                return self._send(result)
            except (ValueError, FileNotFoundError, WedjatXError, json.JSONDecodeError) as exc:
                return self._send({"detail": str(exc)}, 400)
            except Exception as exc:
                LOGGER.exception("POST %s failed", self.path)
                return self._send({"detail": f"Analysis failed: {exc}"}, 500)

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    logging.basicConfig(level=logging.INFO)
    server = ThreadingHTTPServer((host, port), make_handler(DashboardAPI()))
    LOGGER.info("WEDJAT-X dashboard API listening at http://%s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Shutting down WEDJAT-X dashboard API")
    finally:
        server.server_close()


if __name__ == "__main__":
    serve()
