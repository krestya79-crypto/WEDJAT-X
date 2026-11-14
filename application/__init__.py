"""
WEDJAT-X Phase 7 — Unified Backend Integration Package
Offline-first astronaut health monitoring and medical decision-support prototype.

Components:
- WEDJATXSystem: Central orchestrator and public entry-point.
- NasaLabPipeline: Pipeline A for discrete NASA OSD-575 biospecimen assays.
- SyntheticWearablePipeline: Pipeline B for continuous synthetic sensor streams.
- DataManager: Offline data ingestion, batch loading, and report export.
- ResultManager: Standardized result formatting and non-clinical reporting.
- Schemas & Exceptions: Strongly typed data contracts and error hierarchies.
"""

from application.data_manager import DataManager
from application.exceptions import (
    DataRoutingError,
    EngineExecutionError,
    ProvenanceViolationError,
    SchemaMismatchError,
    UnsupportedSourceError,
    ValidationError,
    WedjatXError,
)
from application.orchestrator import WEDJATXSystem
from application.pipeline import BasePipeline, NasaLabPipeline, SyntheticWearablePipeline
from application.result_manager import ResultManager
from application.storage import SQLiteStore
from application.schemas import (
    NON_CLINICAL_DISCLAIMER,
    ProcessingRequest,
    ProcessingResult,
    ProcessingStatus,
    SourceType,
    SystemOperationalState,
    SystemStatus,
)
from application.validators import (
    validate_nasa_lab_data,
    validate_source_type,
    validate_synthetic_wearable_data,
)

__version__ = "1.0.0"
__author__ = "WEDJAT-X Team"

__all__ = [
    "WEDJATXSystem",
    "BasePipeline",
    "NasaLabPipeline",
    "SyntheticWearablePipeline",
    "DataManager",
    "ResultManager",
    "SQLiteStore",
    "ProcessingRequest",
    "ProcessingResult",
    "SystemStatus",
    "SourceType",
    "ProcessingStatus",
    "SystemOperationalState",
    "NON_CLINICAL_DISCLAIMER",
    "WedjatXError",
    "ValidationError",
    "SchemaMismatchError",
    "DataRoutingError",
    "UnsupportedSourceError",
    "ProvenanceViolationError",
    "EngineExecutionError",
    "validate_source_type",
    "validate_nasa_lab_data",
    "validate_synthetic_wearable_data",
]
