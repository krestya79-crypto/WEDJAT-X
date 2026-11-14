"""
WEDJAT-X Phase 7 — Data Validators & Routing Guardrails
Enforces strict schema validation, timestamp verification, and strict data source separation.

CRITICAL ARCHITECTURAL RULE:
Never combine NASA laboratory measurements and synthetic wearable telemetry as if
they were collected simultaneously. Maintain strict data provenance separation.
"""

from typing import Any, Dict, List, Optional, Set, Union
import numpy as np
import pandas as pd

from application.exceptions import (
    DataRoutingError,
    ProvenanceViolationError,
    SchemaMismatchError,
    UnsupportedSourceError,
    ValidationError,
)
from application.schemas import SourceType
from intelligence.synthetic_sensors import (
    SENSOR_ACCELEROMETER,
    SENSOR_HEART_RATE,
    SENSOR_SPO2,
)

# Core required columns for NASA Laboratory Biomarkers
REQUIRED_NASA_LAB_COLS: Set[str] = {
    "Participant_ID",
    "Timepoint",
    "Biomarker_Name",
    "Measurement_Value",
}

# Accepted column aliases for NASA Lab Data
NASA_LAB_ALIASES: Dict[str, str] = {
    "participant_id": "Participant_ID",
    "subject_id": "Participant_ID",
    "astronaut_id": "Participant_ID",
    "timepoint": "Timepoint",
    "time_point": "Timepoint",
    "biomarker": "Biomarker_Name",
    "biomarker_name": "Biomarker_Name",
    "analyte": "Biomarker_Name",
    "measurement_value": "Measurement_Value",
    "value": "Measurement_Value",
    "signal_value": "Measurement_Value",
    "measurement_unit": "Measurement_Unit",
    "unit": "Measurement_Unit",
    "panel_name": "Panel_Name",
    "panel": "Panel_Name",
}

# Accepted timepoints for NASA OSD-575 Inspiration4
VALID_NASA_TIMEPOINTS: Set[str] = {
    "L-92", "L-44", "L-3",
    "R+1", "R+45", "R+82", "R+194"
}
VALID_NASA_PARTICIPANTS: Set[str] = {"C001", "C002", "C003", "C004"}

# Core required columns for Synthetic Wearable Telemetry
REQUIRED_WEARABLE_COLS: Set[str] = {
    "timestamp",
    "sensor_type",
    "signal_value",
}

VALID_SENSOR_TYPES: Set[str] = {
    SENSOR_HEART_RATE,
    SENSOR_SPO2,
    SENSOR_ACCELEROMETER,
    "heart_rate",
    "spo2",
    "accelerometer",
    "hr",
}


def validate_source_type(source_type: str) -> SourceType:
    """
    Validate that source_type is a supported WEDJAT-X data source.

    Parameters
    ----------
    source_type : str
        Source identifier ('NASA_LAB' or 'SYNTHETIC_WEARABLE').

    Returns
    -------
    SourceType
        Standardized SourceType enum.

    Raises
    ------
    UnsupportedSourceError
        If source_type is not supported.
    """
    if not isinstance(source_type, str):
        raise UnsupportedSourceError(
            f"source_type must be a string, got {type(source_type).__name__}."
        )

    norm = source_type.strip().upper()
    try:
        return SourceType(norm)
    except ValueError:
        raise UnsupportedSourceError(
            f"Unsupported data source '{source_type}'. "
            f"Supported sources: {[s.value for s in SourceType]}."
        )


def validate_nasa_lab_data(
    data: Union[pd.DataFrame, List[Dict[str, Any]], Dict[str, Any]],
    is_synthetic: Optional[bool] = None,
) -> pd.DataFrame:
    """
    Validate NASA OSD-575 discrete laboratory biomarker data.

    Enforces:
    - Rejection of synthetic provenance tags.
    - Presence of required core columns (Participant_ID, Biomarker_Name, Timepoint, Measurement_Value).
    - Validation of valid Inspiration4 timepoint labels where applicable.
    - Prohibition of wearable continuous sensor schemas.

    Parameters
    ----------
    data : pd.DataFrame, list of dicts, or dict
        Input biomarker data.
    is_synthetic : bool, optional
        Explicit synthetic flag. Must be False or None.

    Returns
    -------
    pd.DataFrame
        Validated, normalized DataFrame with standardized column names.

    Raises
    ------
    ProvenanceViolationError
        If data is tagged or configured as synthetic.
    ValidationError / SchemaMismatchError
        If schema is invalid or required fields are missing.
    """
    if is_synthetic is True:
        raise ProvenanceViolationError(
            "Provenance Violation: NASA Laboratory pipeline cannot process synthetic data. "
            "NASA OSD-575 benchtop data is authentic biospecimen assay data."
        )

    # Convert dictionary or list to DataFrame
    if isinstance(data, dict):
        df = pd.DataFrame([data])
    elif isinstance(data, list):
        if not data:
            raise ValidationError("Input data list is empty.")
        df = pd.DataFrame(data)
    elif isinstance(data, pd.DataFrame):
        df = data.copy()
    else:
        raise ValidationError(
            f"Invalid input type '{type(data).__name__}'. Expected pd.DataFrame or List[dict]."
        )

    if df.empty:
        raise ValidationError("Input NASA biomarker dataset is empty.")

    # Check for misrouted or contradictory provenance before setting the normalized flag.
    if "is_synthetic" in df.columns:
        flags = df["is_synthetic"].dropna()
        if any(value is True or isinstance(value, np.bool_) and bool(value) for value in flags):
            raise ProvenanceViolationError(
                "Provenance Violation: Input records contain 'is_synthetic=True'. "
                "Synthetic data must be routed to PIPELINE B (SYNTHETIC_WEARABLE)."
            )
        if any(value not in (False, np.bool_(False)) for value in flags):
            raise ValidationError("NASA laboratory provenance must be boolean False.")

    # Detect if data looks like wearable telemetry rather than lab biomarkers
    if "sensor_type" in df.columns:
        raise SchemaMismatchError(
            "Data Routing Error: Input contains wearable sensor types ('sensor_type' column). "
            "Wearable telemetry must be processed via PIPELINE B."
        )

    # Standardize column names using aliases
    rename_dict = {}
    for col in df.columns:
        col_lower = str(col).strip().lower()
        if col_lower in NASA_LAB_ALIASES:
            rename_dict[col] = NASA_LAB_ALIASES[col_lower]
    df = df.rename(columns=rename_dict)

    # Verify required core columns
    missing = [c for c in REQUIRED_NASA_LAB_COLS if c not in df.columns]
    if missing:
        raise SchemaMismatchError(
            f"Missing required NASA laboratory columns: {missing}. "
            f"Present columns: {list(df.columns)}",
            missing_fields=missing,
        )

    # Required identifiers may not be absent. Missing numeric results remain missing.
    for column in ("Participant_ID", "Timepoint", "Biomarker_Name"):
        if df[column].isna().any() or df[column].astype(str).str.strip().eq("").any():
            raise ValidationError(f"NASA laboratory field '{column}' contains missing identifiers.")

    df["Participant_ID"] = df["Participant_ID"].astype(str).str.strip()
    invalid_participants = sorted(set(df["Participant_ID"]) - VALID_NASA_PARTICIPANTS)
    if invalid_participants:
        raise ValidationError(
            f"Unsupported NASA astronaut identifier(s): {invalid_participants}. "
            f"Expected one of {sorted(VALID_NASA_PARTICIPANTS)}."
        )

    df["Timepoint"] = df["Timepoint"].astype(str).str.strip()
    invalid_timepoints = sorted(set(df["Timepoint"]) - VALID_NASA_TIMEPOINTS)
    if invalid_timepoints:
        raise ValidationError(
            f"Invalid NASA OSD-575 milestone identifier(s): {invalid_timepoints}. "
            f"Expected one of {sorted(VALID_NASA_TIMEPOINTS)}."
        )
    df["Biomarker_Name"] = df["Biomarker_Name"].astype(str).str.strip()

    raw_values = df["Measurement_Value"].replace(r"^\s*$", np.nan, regex=True)
    numeric_values = pd.to_numeric(raw_values, errors="coerce")
    invalid_numeric = raw_values.notna() & numeric_values.isna()
    if invalid_numeric.any():
        examples = raw_values[invalid_numeric].astype(str).unique().tolist()[:5]
        raise ValidationError(f"NASA Measurement_Value contains non-numeric values: {examples}.")
    if np.isinf(numeric_values.dropna().to_numpy(dtype=float)).any():
        raise ValidationError("NASA Measurement_Value contains infinite values; provide finite numbers or missing values.")
    df["Measurement_Value"] = numeric_values

    # Ensure provenance tag is explicitly False
    df["is_synthetic"] = False

    return df


def validate_synthetic_wearable_data(
    data: Union[pd.DataFrame, List[Dict[str, Any]], Dict[str, Any]],
    is_synthetic: Optional[bool] = None,
) -> pd.DataFrame:
    """
    Validate synthetic wearable sensor telemetry data.

    Enforces:
    - Explicit synthetic provenance (is_synthetic=True).
    - Presence of required core columns (timestamp, sensor_type, signal_value).
    - Valid timestamp ordering and parsing.
    - Prohibition of discrete NASA laboratory biomarker schemas.

    Parameters
    ----------
    data : pd.DataFrame, list of dicts, or dict
        Input wearable telemetry stream.
    is_synthetic : bool, optional
        Explicit synthetic flag. If provided as False, raises ProvenanceViolationError.

    Returns
    -------
    pd.DataFrame
        Validated, chronologically sorted DataFrame.

    Raises
    ------
    ProvenanceViolationError
        If data is claimed to be non-synthetic real astronaut telemetry.
    ValidationError / SchemaMismatchError
        If schema is invalid or required fields are missing.
    """
    if is_synthetic is False:
        raise ProvenanceViolationError(
            "Provenance Violation: Continuous wearable sensor telemetry in WEDJAT-X is strictly "
            "SYNTHETIC simulation test data. Never represent synthetic data as real astronaut telemetry."
        )

    # Convert to DataFrame
    if isinstance(data, dict):
        df = pd.DataFrame([data])
    elif isinstance(data, list):
        if not data:
            raise ValidationError("Input wearable telemetry list is empty.")
        df = pd.DataFrame(data)
    elif isinstance(data, pd.DataFrame):
        df = data.copy()
    else:
        raise ValidationError(
            f"Invalid input type '{type(data).__name__}'. Expected pd.DataFrame or List[dict]."
        )

    if df.empty:
        raise ValidationError("Input synthetic wearable stream is empty.")

    # Detect if data looks like NASA benchtop laboratory data
    lab_indicators = {"Biomarker_Name", "Timepoint", "Assay_Protocol", "Platform_Technology"}
    if len(lab_indicators.intersection(set(df.columns))) >= 2:
        raise SchemaMismatchError(
            "Data Routing Error: Input appears to be discrete NASA laboratory biomarker assays. "
            "NASA lab data must be processed via PIPELINE A (NASA_LAB)."
        )

    # Standardize common wearable aliases
    wearable_aliases = {
        "time": "timestamp",
        "datetime": "timestamp",
        "type": "sensor_type",
        "value": "signal_value",
        "measurement_value": "signal_value",
        "reading": "signal_value",
    }
    rename_dict = {}
    for col in df.columns:
        col_lower = str(col).strip().lower()
        if col_lower in wearable_aliases:
            rename_dict[col] = wearable_aliases[col_lower]
    df = df.rename(columns=rename_dict)

    # Verify required core columns
    missing = [c for c in REQUIRED_WEARABLE_COLS if c not in df.columns]
    if missing:
        raise SchemaMismatchError(
            f"Missing required synthetic wearable columns: {missing}. "
            f"Present columns: {list(df.columns)}",
            missing_fields=missing,
        )

    # Require explicit synthetic provenance, either on the request or on every record.
    if "is_synthetic" in df.columns:
        flags = df["is_synthetic"]
        if not flags.map(lambda value: isinstance(value, (bool, np.bool_)) and bool(value)).all():
            raise ProvenanceViolationError(
                "Provenance Violation: Every synthetic wearable record must carry is_synthetic=True."
            )
    elif is_synthetic is True:
        df["is_synthetic"] = True
    else:
        raise ProvenanceViolationError(
            "Synthetic wearable data requires explicit is_synthetic=True provenance "
            "on the request or every input record."
        )

    # Validate timestamps and preserve the original stream values while sorting chronologically.
    timestamps = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    if timestamps.isna().any():
        bad_rows = timestamps[timestamps.isna()].index.tolist()[:5]
        raise ValidationError(f"Wearable telemetry contains invalid timestamps at row(s) {bad_rows}.")
    df["timestamp"] = timestamps

    # Validate signal values
    raw_values = df["signal_value"].replace(r"^\s*$", np.nan, regex=True)
    numeric_values = pd.to_numeric(raw_values, errors="coerce")
    invalid_numeric = raw_values.notna() & numeric_values.isna()
    if invalid_numeric.any():
        examples = raw_values[invalid_numeric].astype(str).unique().tolist()[:5]
        raise ValidationError(f"Wearable signal_value contains non-numeric values: {examples}.")
    if np.isinf(numeric_values.dropna().to_numpy(dtype=float)).any():
        raise ValidationError("Wearable signal_value contains infinite values; provide finite numbers or missing values.")
    df["signal_value"] = numeric_values

    sensor_aliases = {
        "heart_rate": SENSOR_HEART_RATE,
        "hr": SENSOR_HEART_RATE,
        "spo2": SENSOR_SPO2,
        "accelerometer": SENSOR_ACCELEROMETER,
    }
    raw_sensor_types = df["sensor_type"].astype(str).str.strip().str.lower()
    invalid_sensors = sorted(set(raw_sensor_types[~raw_sensor_types.isin(sensor_aliases)].tolist()))
    if invalid_sensors:
        raise ValidationError(
            f"Unsupported wearable sensor name(s): {invalid_sensors}. "
            f"Supported sensors: {sorted(set(sensor_aliases.values()))}."
        )
    df["sensor_type"] = raw_sensor_types.map(sensor_aliases)

    # Chronologically sort stream
    df = df.sort_values(by="timestamp", kind="mergesort").reset_index(drop=True)

    # Ensure synthetic provenance is explicitly marked True
    df["is_synthetic"] = True

    return df
