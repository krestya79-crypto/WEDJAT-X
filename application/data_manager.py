"""
WEDJAT-X Phase 7 — Offline Data Manager
Local offline file ingestion, batch reading, and structured report exports.

Requirements:
- Offline-first: Zero internet or cloud dependencies.
- Local filesystem I/O for CSV, JSON, and Excel formats.
- Safe serialization and export.
- Prepares schemas for future Phase 8 SQLite persistence layer.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import pandas as pd

from application.exceptions import ValidationError
from application.schemas import ProcessingResult, json_safe
from application.validators import validate_nasa_lab_data, validate_synthetic_wearable_data

logger = logging.getLogger("WEDJAT_X.DataManager")


class DataManager:
    """
    Offline Data Ingestion, Storage, and Export Coordinator.
    """

    def __init__(self, base_dir: Optional[Union[str, Path]] = None) -> None:
        """
        Initialize DataManager with base project directory.
        """
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        self.cleaned_data_dir = self.base_dir / "cleaned_data"
        self.synthetic_data_dir = self.base_dir / "synthetic_data"
        self.reports_dir = self.base_dir / "reports"

    # =========================================================================
    # 1. Local Ingestion
    # =========================================================================

    def load_dataset(
        self,
        filepath: Union[str, Path],
        file_format: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Load a dataset safely from local disk (CSV, JSON, or Excel).

        Parameters
        ----------
        filepath : str or Path
            Path to file.
        file_format : str, optional
            'csv', 'json', or 'excel'. If None, inferred from extension.

        Returns
        -------
        pd.DataFrame
            Loaded pandas DataFrame.
        """
        path = Path(filepath)
        if not path.is_absolute():
            path = self.base_dir / path

        if not path.exists():
            raise FileNotFoundError(f"Requested dataset file does not exist: {path}")

        fmt = (file_format or path.suffix.lower().lstrip(".")).lower()

        try:
            if fmt == "csv":
                return pd.read_csv(path)
            elif fmt == "json":
                # Can be json records or json object
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return pd.DataFrame(data)
                elif isinstance(data, dict):
                    # Check if dict of lists or single record
                    if any(isinstance(v, list) for v in data.values()):
                        return pd.DataFrame(data)
                    return pd.DataFrame([data])
                else:
                    raise ValidationError(f"Unsupported JSON structure in {path}")
            elif fmt in ["xlsx", "xls", "excel"]:
                return pd.read_excel(path)
            else:
                raise ValidationError(f"Unsupported file format: {fmt}")
        except Exception as e:
            if isinstance(e, (FileNotFoundError, ValidationError)):
                raise
            raise ValidationError(f"Failed to read file {path}: {e}")

    def load_master_nasa_dataset(
        self,
        filename: str = "WEDJAT_X_Master_Biomarker_Dataset.csv",
    ) -> pd.DataFrame:
        """
        Convenience loader for the validated NASA OSD-575 master dataset.
        """
        path = self.cleaned_data_dir / filename
        return self.load_nasa_dataset(path)

    def load_nasa_dataset(self, filepath: Union[str, Path]) -> pd.DataFrame:
        """Load and validate a discrete NASA laboratory dataset without mutating its file."""
        path = Path(filepath)
        if not path.is_absolute():
            path = self.base_dir / path
        dataframe = validate_nasa_lab_data(self.load_dataset(path))
        dataframe.attrs["source_type"] = "NASA_LAB"
        dataframe.attrs["source_path"] = str(path.resolve())
        return dataframe

    def load_synthetic_dataset(
        self,
        filepath: Union[str, Path],
        is_synthetic: Optional[bool] = None,
    ) -> pd.DataFrame:
        """Load a wearable dataset only when synthetic provenance is explicit and valid."""
        path = Path(filepath)
        if not path.is_absolute():
            path = self.base_dir / path
        dataframe = validate_synthetic_wearable_data(
            self.load_dataset(path),
            is_synthetic=is_synthetic,
        )
        dataframe.attrs["source_type"] = "SYNTHETIC_WEARABLE"
        dataframe.attrs["source_path"] = str(path.resolve())
        return dataframe

    def load_batch_files(
        self,
        file_paths: List[Union[str, Path]],
    ) -> Dict[str, pd.DataFrame]:
        """
        Load multiple datasets sequentially while maintaining individual dataset boundaries.

        Parameters
        ----------
        file_paths : list of paths
            List of file paths.

        Returns
        -------
        dict
            Mapping from filename/identifier to loaded DataFrame.
        """
        results: Dict[str, pd.DataFrame] = {}
        for fp in file_paths:
            p = Path(fp)
            key = p.stem
            try:
                results[key] = self.load_dataset(p)
            except Exception as e:
                logger.error("Failed loading batch item %s: %s", fp, e)
                raise
        return results

    # =========================================================================
    # 2. Local Offline Exports
    # =========================================================================

    def save_result_json(
        self,
        result: Union[ProcessingResult, Dict[str, Any]],
        output_path: Union[str, Path],
        indent: int = 2,
    ) -> Path:
        """
        Export processing result as standardized JSON file.
        """
        path = Path(output_path)
        if not path.is_absolute():
            path = self.base_dir / path

        path.parent.mkdir(parents=True, exist_ok=True)

        data = result.to_dict() if isinstance(result, ProcessingResult) else result
        data = json_safe(data)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, allow_nan=False)

        return path

    def save_batch_results(
        self,
        results: List[ProcessingResult],
        output_dir: Union[str, Path],
    ) -> List[Path]:
        """
        Save a batch of ProcessingResults into individual JSON files.
        """
        out_dir = Path(output_dir)
        if not out_dir.is_absolute():
            out_dir = self.base_dir / out_dir

        out_dir.mkdir(parents=True, exist_ok=True)
        paths: List[Path] = []

        for res in results:
            fname = f"{res.processing_id}_{res.subject_id or 'subject'}.json"
            p = out_dir / fname
            self.save_result_json(res, p)
            paths.append(p)

        return paths

    def export_summary_to_excel(
        self,
        results: List[ProcessingResult],
        output_path: Union[str, Path],
    ) -> Path:
        """
        Export a multi-sheet analytical summary of processing results to Excel.
        """
        path = Path(output_path)
        if not path.is_absolute():
            path = self.base_dir / path

        path.parent.mkdir(parents=True, exist_ok=True)

        # Overview Sheet
        overview_rows = []
        for r in results:
            alert_sum = r.alert_summary or {}
            overview_rows.append({
                "Processing_ID": r.processing_id,
                "Timestamp": r.timestamp,
                "Source_Type": r.source_type,
                "Subject_ID": r.subject_id,
                "Processing_Status": r.processing_status,
                "Is_Synthetic": r.is_synthetic,
                "Total_Measurements": len(r.measurements),
                "Highest_Alert_State": alert_sum.get("highest_operational_state", "NONE"),
                "Active_Alerts": alert_sum.get("active_alert_count", 0),
                "Attention_Count": alert_sum.get("attention_count", 0),
                "Review_Count": alert_sum.get("review_count", 0),
                "Normal_Count": alert_sum.get("normal_count", 0),
                "Duration_Seconds": r.execution_metrics.get("duration_seconds", 0.0),
            })
        overview_df = pd.DataFrame(overview_rows)

        # Detailed Alerts Sheet
        alert_rows = []
        for r in results:
            alert_sum = r.alert_summary or {}
            for a in alert_sum.get("active_alerts", []):
                alert_rows.append({
                    "Processing_ID": r.processing_id,
                    "Subject_ID": r.subject_id,
                    "Measurement_Name": a.get("measurement_name"),
                    "Alert_State": a.get("alert_state"),
                    "Alert_Priority": a.get("alert_priority"),
                    "Lifecycle_Status": a.get("lifecycle_status"),
                    "Explanation": a.get("explanation"),
                })
        alerts_df = pd.DataFrame(alert_rows) if alert_rows else pd.DataFrame([{"Notice": "No active alerts"}])

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            overview_df.to_excel(writer, sheet_name="Execution_Summary", index=False)
            alerts_df.to_excel(writer, sheet_name="Active_Alerts", index=False)

        return path

    def export_results_csv(
        self,
        results: List[ProcessingResult],
        output_path: Union[str, Path],
    ) -> Path:
        """Export one summary row per result, preserving nested evidence as JSON text."""
        path = Path(output_path)
        if not path.is_absolute():
            path = self.base_dir / path
        path.parent.mkdir(parents=True, exist_ok=True)

        rows = []
        for result in results:
            data = result.to_dict()
            rows.append({
                "request_id": data["request_id"],
                "timestamp": data["timestamp"],
                "source_type": data["source_type"],
                "is_synthetic": data["is_synthetic"],
                "processing_status": data["processing_status"],
                "astronaut_id": data["astronaut_id"],
                "data_summary": json.dumps(data["data_summary"], allow_nan=False),
                "baseline_summary": json.dumps(data["baseline_summary"], allow_nan=False),
                "anomaly_evidence": json.dumps(data["anomaly_evidence"], allow_nan=False),
                "alert": json.dumps(data["alert"], allow_nan=False),
                "warnings": json.dumps(data["warnings"], allow_nan=False),
                "errors": json.dumps(data["errors"], allow_nan=False),
            })
        pd.DataFrame(rows).to_csv(path, index=False)
        return path
