"""
WEDJAT-X Phase 7 — Comprehensive Backend Integration Tests
Tests full integration across all intelligence engines, pipelines, orchestrator, and data managers.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from application.exceptions import (
    ProvenanceViolationError,
    SchemaMismatchError,
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
)
from intelligence.synthetic_sensors import (
    SCENARIO_MOTION_ARTIFACT,
    SCENARIO_NOISE,
    SCENARIO_NORMAL,
    SCENARIO_SENSOR_DISCONNECT,
    SENSOR_ACCELEROMETER,
    SENSOR_HEART_RATE,
    SENSOR_SPO2,
    SyntheticSensorConfig,
    SyntheticSensorGenerator,
)


@pytest.fixture
def system(tmp_path) -> WEDJATXSystem:
    instance = WEDJATXSystem()
    instance.storage = SQLiteStore(tmp_path / "wedjatx.sqlite3")
    return instance


def test_full_nasa_workflow_all_participants(system: WEDJATXSystem) -> None:
    """Verify system.process_all_nasa_participants executes across all 4 Inspiration4 astronauts."""
    master_path = Path("cleaned_data/WEDJAT_X_Master_Biomarker_Dataset.csv")
    if not master_path.exists():
        pytest.skip("Master dataset not found.")

    crew_results = system.process_all_nasa_participants(master_dataset_path=master_path)

    assert len(crew_results) == 4
    for pid in ["C001", "C002", "C003", "C004"]:
        assert pid in crew_results
        res = crew_results[pid]
        assert res.source_type == SourceType.NASA_LAB.value
        assert res.subject_id == pid
        assert res.is_synthetic is False
        assert res.processing_status in [ProcessingStatus.SUCCESS.value, ProcessingStatus.PARTIAL_SUCCESS.value]
        assert "RESEARCH DECISION-SUPPORT PROTOTYPE ONLY" in res.disclaimer
        # JSON serializable check
        j_str = res.to_json()
        assert pid in j_str


def test_full_synthetic_wearable_scenarios(system: WEDJATXSystem) -> None:
    """Verify system evaluates different physiological scenarios deterministically."""
    scenarios = [SCENARIO_NORMAL, SCENARIO_NOISE, SCENARIO_SENSOR_DISCONNECT]

    for sc in scenarios:
        gen = SyntheticSensorGenerator(SyntheticSensorConfig(duration_seconds=15, random_seed=42, scenario=sc))
        df = gen.generate_heart_rate()

        res = system.process(
            data=df,
            source_type=SourceType.SYNTHETIC_WEARABLE.value,
            subject_id=f"Astro_{sc}",
            is_synthetic=True,
        )

        assert res.source_type == SourceType.SYNTHETIC_WEARABLE.value
        assert res.is_synthetic is True
        assert res.processing_status == ProcessingStatus.SUCCESS.value
        assert res.sensor_trust_analysis.get("quality_score") is not None


def test_strict_provenance_separation_bidirectional(system: WEDJATXSystem) -> None:
    """Verify cross-pipeline contamination is strictly prevented in both directions."""
    # Direction 1: Synthetic data sent to NASA Lab pipeline -> Must fail
    gen = SyntheticSensorGenerator(SyntheticSensorConfig(duration_seconds=10, random_seed=42))
    df_synth = gen.generate_heart_rate()

    with pytest.raises(ProvenanceViolationError):
        system.process(data=df_synth, source_type=SourceType.NASA_LAB.value, is_synthetic=True)

    # Direction 2: NASA Lab data sent to Synthetic Wearable pipeline -> Must fail
    master_path = Path("cleaned_data/WEDJAT_X_Master_Biomarker_Dataset.csv")
    if master_path.exists():
        df_nasa = pd.read_csv(master_path, nrows=20)
        with pytest.raises((ProvenanceViolationError, SchemaMismatchError)):
            system.process(data=df_nasa, source_type=SourceType.SYNTHETIC_WEARABLE.value, is_synthetic=False)


def test_no_false_normal_on_processing_failure(system: WEDJATXSystem) -> None:
    """CRITICAL REGULATORY SAFETY TEST: If an engine fails, result must never be labeled NORMAL."""
    res = system.result_manager.create_failure_result(
        source_type=SourceType.NASA_LAB.value,
        error_message="Simulated analytical crash in matrix inversion",
        subject_id="C001",
    )

    assert res.processing_status == ProcessingStatus.FAILED.value
    assert res.alert_summary.get("highest_operational_state") != "NORMAL"
    assert "FAILED" in res.alert_summary.get("highest_operational_state")
    assert len(res.errors) > 0


def test_missing_values_handled_gracefully(system: WEDJATXSystem) -> None:
    """Verify that NaNs and missing values in telemetry streams do not cause unhandled crashes."""
    times = pd.date_range("2026-01-01 00:00:00", periods=10, freq="1s")
    vals = [70.0, np.nan, np.nan, 71.0, 72.0, np.nan, 71.5, 70.0, 71.0, 70.5]
    df = pd.DataFrame({
        "timestamp": times,
        "sensor_type": SENSOR_HEART_RATE,
        "signal_value": vals,
        "scenario": "MISSING_TEST",
        "signal_status": "VALID",
        "is_synthetic": True,
    })

    res = system.process(
        data=df,
        source_type=SourceType.SYNTHETIC_WEARABLE.value,
        subject_id="Astro_Missing",
        is_synthetic=True,
    )

    assert res.processing_status == ProcessingStatus.SUCCESS.value
    assert res.data_quality.get("missing_rate") > 0.0


def test_non_clinical_guardrail_enforcement(system: WEDJATXSystem) -> None:
    """Verify that neither alerts nor summaries use forbidden clinical diagnostic language."""
    gen = SyntheticSensorGenerator(SyntheticSensorConfig(duration_seconds=15, random_seed=42, scenario=SCENARIO_NOISE))
    df = gen.generate_heart_rate()

    res = system.process(
        data=df,
        source_type=SourceType.SYNTHETIC_WEARABLE.value,
        subject_id="Astro_Guardrail",
        is_synthetic=True,
    )

    # Inspect generated operational explanations and reports (excluding disclaimers that disclaim clinical status)
    texts_to_check = [
        res.ground_medical_report.get("executive_summary", ""),
        res.astronaut_summary.get("message", ""),
        res.astronaut_summary.get("headline", ""),
    ]
    for a in res.alert_summary.get("active_alerts", []):
        texts_to_check.append(a.get("explanation", ""))
        texts_to_check.extend(a.get("supporting_evidence", []))
        texts_to_check.extend(a.get("recommended_workflow_actions", []))

    full_text = " ".join(texts_to_check).lower()
    forbidden = ["diagnose", "pathology", "prescribe", "medication", "infarction", "disease"]
    for word in forbidden:
        assert word not in full_text, f"Forbidden diagnostic word '{word}' found in generated explanations!"
