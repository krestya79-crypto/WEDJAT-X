"""
WEDJAT-X Phase 7 — Unit & Integration Tests for Analytical Pipelines
Tests NasaLabPipeline (Pipeline A) and SyntheticWearablePipeline (Pipeline B).
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from application.exceptions import (
    DataRoutingError,
    ProvenanceViolationError,
    SchemaMismatchError,
    ValidationError,
)
from application.pipeline import NasaLabPipeline, SyntheticWearablePipeline
from application.schemas import ProcessingStatus, SourceType
from intelligence.synthetic_sensors import (
    SCENARIO_MOTION_ARTIFACT,
    SCENARIO_NORMAL,
    SENSOR_ACCELEROMETER,
    SENSOR_HEART_RATE,
    SyntheticSensorConfig,
    SyntheticSensorGenerator,
)


@pytest.fixture
def nasa_pipeline() -> NasaLabPipeline:
    return NasaLabPipeline()


@pytest.fixture
def synthetic_pipeline() -> SyntheticWearablePipeline:
    return SyntheticWearablePipeline()


def test_nasa_pipeline_execution_real_data(nasa_pipeline: NasaLabPipeline) -> None:
    """Verify NasaLabPipeline end-to-end execution on Inspiration4 master dataset."""
    master_path = Path("cleaned_data/WEDJAT_X_Master_Biomarker_Dataset.csv")
    if not master_path.exists():
        pytest.skip("Master dataset not found.")

    df = pd.read_csv(master_path)
    # Test with participant C002
    result = nasa_pipeline.execute(data=df, subject_id="C002", is_synthetic=False)

    assert result.source_type == SourceType.NASA_LAB.value
    assert result.subject_id == "C002"
    assert result.is_synthetic is False
    assert result.processing_status in [ProcessingStatus.SUCCESS.value, ProcessingStatus.PARTIAL_SUCCESS.value]

    # Baseline analysis should contain calculated markers
    assert len(result.baseline_analysis) > 0
    # Trajectory analysis should contain postflight recovery trajectories
    assert len(result.trajectory_analysis) > 0
    # Ground medical report must be generated
    assert result.ground_medical_report.get("overall_status") is not None
    # Astronaut summary must be present and calm
    assert result.astronaut_summary.get("is_calm_tone") is True


def test_nasa_pipeline_rejection_of_synthetic_data(nasa_pipeline: NasaLabPipeline) -> None:
    """Enforce strict separation: NASA pipeline must refuse synthetic telemetry."""
    gen = SyntheticSensorGenerator(SyntheticSensorConfig(duration_seconds=10, random_seed=42))
    df = gen.generate_heart_rate()

    with pytest.raises(ProvenanceViolationError):
        nasa_pipeline.execute(data=df, is_synthetic=True)


def test_nasa_pipeline_rejection_of_missing_columns(nasa_pipeline: NasaLabPipeline) -> None:
    """Verify that incomplete schemas missing core columns are rejected."""
    bad_df = pd.DataFrame({
        "Participant_ID": ["C001", "C001"],
        "Biomarker_Name": ["IL-6", "TNF-alpha"],
        # Missing Timepoint and Measurement_Value
    })
    with pytest.raises(SchemaMismatchError) as exc_info:
        nasa_pipeline.execute(data=bad_df)
    assert "Missing required NASA laboratory columns" in str(exc_info.value)


def test_synthetic_pipeline_execution(synthetic_pipeline: SyntheticWearablePipeline) -> None:
    """Verify SyntheticWearablePipeline end-to-end execution on generated stream."""
    gen = SyntheticSensorGenerator(SyntheticSensorConfig(duration_seconds=20, random_seed=42, scenario=SCENARIO_NORMAL))
    df = gen.generate_heart_rate()

    result = synthetic_pipeline.execute(
        data=df,
        subject_id="Astro_Synth",
        is_synthetic=True,
    )

    assert result.source_type == SourceType.SYNTHETIC_WEARABLE.value
    assert result.subject_id == "Astro_Synth"
    assert result.is_synthetic is True
    assert result.processing_status == ProcessingStatus.SUCCESS.value
    assert result.sensor_trust_analysis.get("quality_score") is not None
    assert result.sensor_trust_analysis.get("reliability_category") in [
        "HIGH_RELIABILITY", "MODERATE_RELIABILITY", "LOW_RELIABILITY", "UNRELIABLE", "INSUFFICIENT_DATA"
    ]
    assert len(result.alert_summary.get("active_alerts", [])) >= 0


def test_synthetic_pipeline_motion_cross_check(synthetic_pipeline: SyntheticWearablePipeline) -> None:
    """Verify concurrent accelerometer stream is ingested and evaluated."""
    gen_hr = SyntheticSensorGenerator(SyntheticSensorConfig(duration_seconds=15, random_seed=55, scenario=SCENARIO_MOTION_ARTIFACT))
    gen_acc = SyntheticSensorGenerator(SyntheticSensorConfig(duration_seconds=15, random_seed=55, scenario=SCENARIO_MOTION_ARTIFACT))

    hr_df = gen_hr.generate_heart_rate()
    acc_df = gen_acc.generate_accelerometer()

    result = synthetic_pipeline.execute(
        data=hr_df,
        accel_data=acc_df,
        subject_id="Astro_Motion",
        is_synthetic=True,
    )

    assert result.processing_status == ProcessingStatus.SUCCESS.value
    assert result.sensor_trust_analysis is not None
    # Verify execution metrics logged
    assert "sensor_trust_seconds" in result.execution_metrics


def test_synthetic_pipeline_rejection_of_false_provenance(synthetic_pipeline: SyntheticWearablePipeline) -> None:
    """Enforce strict separation: Synthetic pipeline must reject is_synthetic=False."""
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=5, freq="1s"),
        "sensor_type": SENSOR_HEART_RATE,
        "signal_value": [70.0, 71.0, 72.0, 70.5, 71.2],
    })

    with pytest.raises(ProvenanceViolationError) as exc_info:
        synthetic_pipeline.execute(data=df, is_synthetic=False)
    assert "Provenance Violation" in str(exc_info.value)
