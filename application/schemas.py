"""
WEDJAT-X Phase 7 — Unified Schemas and Data Models
Standardized data contracts for backend orchestration, pipelines, and reporting.

Regulatory Notice:
WEDJAT-X is an exploratory biomedical engineering and decision-support prototype
for the NASA Space Apps Challenge. It does NOT provide clinical diagnosis, disease
prediction, or treatment recommendations.
"""

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
import json
import math
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd


NON_CLINICAL_DISCLAIMER: str = (
    "RESEARCH DECISION-SUPPORT PROTOTYPE ONLY: Not certified as a clinical diagnostic "
    "device or medical countermeasure delivery system. NASA OSD-575 data reflects discrete "
    "benchtop laboratory assays (N=4); continuous sensor streams are synthetic simulations. "
    "All outputs must be independently reviewed by authorized aerospace flight surgeons."
)


class SourceType(str, Enum):
    """Supported data source pathways."""
    NASA_LAB = "NASA_LAB"
    SYNTHETIC_WEARABLE = "SYNTHETIC_WEARABLE"


class ProcessingStatus(str, Enum):
    """Processing execution status states."""
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PROCESSING_ERROR = "PROCESSING_ERROR"
    # Legacy names remain aliases for the standardized status vocabulary.
    FAILED = "PROCESSING_ERROR"
    INVALID_DATA = "INVALID_DATA"


class SystemOperationalState(str, Enum):
    """System availability state."""
    READY = "READY"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"


@dataclass
class ProcessingRequest:
    """Standardized input request wrapping payload and routing metadata."""
    source_type: str
    data: Any
    subject_id: Optional[str] = None
    is_synthetic: Optional[bool] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemStatus:
    """
    Operational health and availability status of the WEDJAT-X backend.
    Distinguishes software/system availability from astronaut medical status.
    """
    system: str = "WEDJAT-X"
    system_version: str = "1.0"
    status: str = "READY"
    initialized_engines: Dict[str, bool] = field(default_factory=dict)
    engine_availability: Dict[str, str] = field(default_factory=dict)
    model_availability: Dict[str, str] = field(default_factory=dict)
    configuration_summary: Dict[str, Any] = field(default_factory=dict)
    supported_data_sources: List[str] = field(
        default_factory=lambda: [SourceType.NASA_LAB.value, SourceType.SYNTHETIC_WEARABLE.value]
    )
    backend_version: str = "1.0.0"
    last_processing_timestamp: Optional[str] = None
    current_processing_state: str = "IDLE"
    initialization_errors: List[str] = field(default_factory=list)
    disclaimer: str = NON_CLINICAL_DISCLAIMER

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class ProcessingResult:
    """
    Unified, typed, JSON-serializable analytical processing result.
    Conforms strictly to Phase 7 Part 4 specification.
    """
    system: str = "WEDJAT-X"
    system_version: str = "1.0"
    processing_id: str = ""
    timestamp: str = ""
    source_type: str = ""
    subject_id: Optional[str] = None
    processing_status: str = ProcessingStatus.SUCCESS.value
    measurements: List[Dict[str, Any]] = field(default_factory=list)
    baseline_analysis: Dict[str, Any] = field(default_factory=dict)
    anomaly_analysis: Dict[str, Any] = field(default_factory=dict)
    bayesian_analysis: Dict[str, Any] = field(default_factory=dict)
    isolation_forest_analysis: Dict[str, Any] = field(default_factory=dict)
    trajectory_analysis: Dict[str, Any] = field(default_factory=dict)
    sensor_trust_analysis: Dict[str, Any] = field(default_factory=dict)
    alert_summary: Dict[str, Any] = field(default_factory=dict)
    ground_medical_report: Dict[str, Any] = field(default_factory=dict)
    astronaut_summary: Dict[str, Any] = field(default_factory=dict)
    data_quality: Dict[str, Any] = field(default_factory=dict)
    limitations: List[str] = field(default_factory=list)
    is_synthetic: bool = False
    disclaimer: str = NON_CLINICAL_DISCLAIMER
    errors: List[str] = field(default_factory=list)
    execution_metrics: Dict[str, Any] = field(default_factory=dict)
    request_id: str = ""
    astronaut_id: Optional[str] = None
    data_summary: Dict[str, Any] = field(default_factory=dict)
    baseline_summary: Dict[str, Any] = field(default_factory=dict)
    anomaly_evidence: Dict[str, Any] = field(default_factory=dict)
    sensor_trust: Optional[Dict[str, Any]] = None
    trajectory_summary: Optional[Dict[str, Any]] = None
    interpretation: Dict[str, Any] = field(default_factory=dict)
    alert: Dict[str, Any] = field(default_factory=dict)
    confidence_or_evidence_summary: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    audit_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return legacy and unified response fields with non-finite values as JSON null."""
        d = asdict(self)
        d["request_id"] = self.request_id or self.processing_id
        d["astronaut_id"] = self.astronaut_id or (
            self.subject_id if self.source_type == SourceType.NASA_LAB.value else None
        )
        d["data_summary"] = self.data_summary or self.data_quality
        d["baseline_summary"] = self.baseline_summary or self.baseline_analysis
        d["anomaly_evidence"] = self.anomaly_evidence or {
            "statistical": self.anomaly_analysis,
            "bayesian": self.bayesian_analysis,
            "isolation_forest": self.isolation_forest_analysis,
        }
        d["sensor_trust"] = self.sensor_trust if self.sensor_trust is not None else (
            self.sensor_trust_analysis or None
        )
        d["trajectory_summary"] = self.trajectory_summary if self.trajectory_summary is not None else (
            self.trajectory_analysis or None
        )
        d["alert"] = self.alert or self.alert_summary
        return json_safe(d)

    def to_json(self, indent: int = 2) -> str:
        """Export result as formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent, allow_nan=False)


def json_safe(value: Any) -> Any:
    """Convert nested pandas/NumPy values to JSON primitives without replacing missing data."""
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, np.datetime64):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, np.ndarray):
        return [json_safe(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if isinstance(value, (str, int, bool)):
        return value
    if pd.isna(value):
        return None
    raise TypeError(f"Value of type {type(value).__name__} is not JSON serializable.")
