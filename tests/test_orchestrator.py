"""
WEDJAT-X Phase 7 — Unit & Functional Tests for Central Orchestrator
Tests WEDJATXSystem initialization, routing, status, and batch execution.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from application.exceptions import (
    ProvenanceViolationError,
    SchemaMismatchError,
    UnsupportedSourceError,
    ValidationError,
)
from application.orchestrator import WEDJATXSystem
from application.storage import SQLiteStore
from application.schemas import (
    NON_CLINICAL_DISCLAIMER,
    ProcessingResult,
    ProcessingStatus,
    SourceType,
    SystemOperationalState,
    SystemStatus,
)
from intelligence.synthetic_sensors import (
    SCENARIO_NORMAL,
    SENSOR_HEART_RATE,
    SyntheticSensorConfig,
    SyntheticSensorGenerator,
)


@pytest.fixture
def system(tmp_path) -> WEDJATXSystem:
    """Fixture providing an initialized WEDJATXSystem."""
    instance = WEDJATXSystem()
    instance.storage = SQLiteStore(tmp_path / "wedjatx.sqlite3")
    return instance


def test_system_initialization(system: WEDJATXSystem) -> None:
    """Verify clean initialization of WEDJATXSystem and analytical engines."""
    assert system.backend_version == "1.0.0"
    assert system.current_processing_state == "IDLE"
    assert len(system.initialization_errors) == 0

    # Check that core engines are registered
    assert system.initialized_engines.get("baseline_engine") is True
    assert system.initialized_engines.get("anomaly_detector") is True
    assert system.initialized_engines.get("trajectory_engine") is True
    assert system.initialized_engines.get("synthetic_generator") is True
    assert system.initialized_engines.get("sensor_trust_engine") is True
    assert system.initialized_engines.get("interpretation_engine") is True
    assert system.initialized_engines.get("alert_engine") is True


def test_get_system_status(system: WEDJATXSystem) -> None:
    """Verify get_system_status returns comprehensive operational metadata."""
    status: SystemStatus = system.get_system_status()

    assert status.system == "WEDJAT-X"
    assert status.system_version == "1.0"
    assert status.status == SystemOperationalState.READY.value
    assert status.current_processing_state == "IDLE"
    assert SourceType.NASA_LAB.value in status.supported_data_sources
    assert SourceType.SYNTHETIC_WEARABLE.value in status.supported_data_sources
    assert status.engine_availability["baseline_engine"] == "AVAILABLE"
    assert status.model_availability["bayesian_student_t"] == "AVAILABLE"
    assert "RESEARCH DECISION-SUPPORT PROTOTYPE ONLY" in status.disclaimer


def test_failed_engine_marks_system_degraded(system: WEDJATXSystem) -> None:
    """A failed initialized component must never leave the orchestrator READY."""
    system.initialized_engines["alert_engine"] = False
    status = system.get_system_status()
    assert status.status == SystemOperationalState.DEGRADED.value
    assert status.status != SystemOperationalState.READY.value


def test_process_nasa_lab_biomarkers(system: WEDJATXSystem) -> None:
    """Verify system.process correctly coordinates PIPELINE A for NASA OSD-575."""
    master_path = Path("cleaned_data/WEDJAT_X_Master_Biomarker_Dataset.csv")
    if not master_path.exists():
        pytest.skip("Master dataset not found in local workspace.")

    result: ProcessingResult = system.process(
        data=master_path,
        source_type=SourceType.NASA_LAB.value,
        subject_id="C001",
    )

    assert result.system == "WEDJAT-X"
    assert result.source_type == SourceType.NASA_LAB.value
    assert result.subject_id == "C001"
    assert result.is_synthetic is False
    assert result.processing_status in [ProcessingStatus.SUCCESS.value, ProcessingStatus.PARTIAL_SUCCESS.value]
    assert len(result.measurements) > 0
    assert len(result.baseline_analysis) > 0
    assert "alert_summary" in result.to_dict()
    assert result.alert_summary.get("highest_operational_state") in ["NORMAL", "REVIEW", "ATTENTION", "INSUFFICIENT_DATA"]
    assert "total_pipeline_seconds" in result.execution_metrics


def test_process_synthetic_wearable_stream(system: WEDJATXSystem) -> None:
    """Verify system.process correctly coordinates PIPELINE B for synthetic telemetry."""
    gen = SyntheticSensorGenerator(SyntheticSensorConfig(duration_seconds=15, random_seed=42, scenario=SCENARIO_NORMAL))
    df = gen.generate_heart_rate()

    result: ProcessingResult = system.process(
        data=df,
        source_type=SourceType.SYNTHETIC_WEARABLE.value,
        subject_id="Crew_Alpha",
        is_synthetic=True,
    )

    assert result.source_type == SourceType.SYNTHETIC_WEARABLE.value
    assert result.subject_id == "Crew_Alpha"
    assert result.is_synthetic is True
    assert result.processing_status == ProcessingStatus.SUCCESS.value
    assert len(result.measurements) > 0
    assert result.sensor_trust_analysis.get("quality_score") is not None
    assert result.alert_summary.get("highest_operational_state") == "NORMAL"


def test_unsupported_source_type_rejected(system: WEDJATXSystem) -> None:
    """Verify that an invalid source_type raises UnsupportedSourceError."""
    with pytest.raises(UnsupportedSourceError) as exc_info:
        system.process(data=[{"test": 1}], source_type="UNKNOWN_TELEMETRY")
    assert "Unsupported data source" in str(exc_info.value)


def test_provenance_violation_rejection(system: WEDJATXSystem) -> None:
    """Verify that synthetic data routed to NASA pipeline raises ProvenanceViolationError."""
    gen = SyntheticSensorGenerator(SyntheticSensorConfig(duration_seconds=10, random_seed=123))
    df = gen.generate_heart_rate()

    with pytest.raises(ProvenanceViolationError):
        system.process(
            data=df,
            source_type=SourceType.NASA_LAB.value,
            is_synthetic=True,
        )


def test_batch_processing_and_isolation(system: WEDJATXSystem) -> None:
    """Verify batch processing operates on distinct recordings without cross-talk."""
    gen1 = SyntheticSensorGenerator(SyntheticSensorConfig(duration_seconds=10, random_seed=101, scenario=SCENARIO_NORMAL))
    gen2 = SyntheticSensorGenerator(SyntheticSensorConfig(duration_seconds=10, random_seed=202, scenario=SCENARIO_NORMAL))

    stream1 = gen1.generate_heart_rate()
    stream2 = gen2.generate_heart_rate()

    batch_results = system.process_batch(
        items=[stream1, stream2],
        source_type=SourceType.SYNTHETIC_WEARABLE.value,
        subject_ids=["Astro_01", "Astro_02"],
        is_synthetic=True,
    )

    assert len(batch_results) == 2
    assert batch_results[0].subject_id == "Astro_01"
    assert batch_results[1].subject_id == "Astro_02"
    assert batch_results[0].processing_id != batch_results[1].processing_id


def test_deterministic_reproducibility(system: WEDJATXSystem) -> None:
    """Verify identical inputs yield identical alert and analytical classifications."""
    gen = SyntheticSensorGenerator(SyntheticSensorConfig(duration_seconds=10, random_seed=999, scenario=SCENARIO_NORMAL))
    df = gen.generate_heart_rate()

    res1 = system.process(data=df.copy(), source_type=SourceType.SYNTHETIC_WEARABLE.value, subject_id="Astro_Rep", is_synthetic=True)
    res2 = system.process(data=df.copy(), source_type=SourceType.SYNTHETIC_WEARABLE.value, subject_id="Astro_Rep", is_synthetic=True)

    assert res1.alert_summary["highest_operational_state"] == res2.alert_summary["highest_operational_state"]
    assert res1.sensor_trust_analysis["quality_score"] == res2.sensor_trust_analysis["quality_score"]
