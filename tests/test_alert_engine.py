"""
Unit and Integration Tests for WEDJAT-X Intelligent Medical Alert Engine (Phase 6)
NASA Space Apps Challenge - Astronaut Health Monitoring Prototype
"""

from __future__ import annotations

import json
import numpy as np
import pandas as pd
import pytest

from intelligence.alert_engine import (
    ALL_ALERT_STATES,
    ALL_LIFECYCLE_STATUSES,
    ALL_PRIORITIES,
    LIFECYCLE_ACTIVE,
    LIFECYCLE_NEW,
    LIFECYCLE_PERSISTENT,
    LIFECYCLE_RESOLVED,
    PATH_NASA_LABORATORY,
    PATH_WEARABLE_TELEMETRY,
    PRIORITY_HIGH,
    PRIORITY_INFO,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    PRIORITY_NOMINAL,
    STATE_ATTENTION,
    STATE_INSUFFICIENT_DATA,
    STATE_NORMAL,
    STATE_REVIEW,
    AlertEngineConfig,
    AlertRecord,
    IntelligentAlertEngine,
)
from intelligence.interpretation import (
    WORKFLOW_INSUFFICIENT_DATA,
    WORKFLOW_NO_ADDITIONAL_REVIEW,
    WORKFLOW_REQUEST_MEDICAL_REVIEW,
    WORKFLOW_REVIEW_MEASUREMENT,
    WORKFLOW_VERIFY_SENSOR,
)
from intelligence.synthetic_sensors import (
    SCENARIO_MOTION_ARTIFACT,
    SCENARIO_NORMAL,
    SCENARIO_SENSOR_DISCONNECT,
    SENSOR_ACCELEROMETER,
    SENSOR_HEART_RATE,
    SENSOR_SPO2,
    SyntheticSensorConfig,
    SyntheticSensorGenerator,
)


@pytest.fixture
def alert_engine() -> IntelligentAlertEngine:
    """Fixture providing a freshly initialized IntelligentAlertEngine."""
    return IntelligentAlertEngine(AlertEngineConfig(persistence_consecutive_threshold=3))


def test_normal_wearable_observation(alert_engine: IntelligentAlertEngine) -> None:
    """Verify that nominal physiological signals result in STATE_NORMAL and PRIORITY_NOMINAL."""
    gen = SyntheticSensorGenerator(SyntheticSensorConfig(duration_seconds=20, random_seed=42, scenario=SCENARIO_NORMAL))
    df = gen.generate_heart_rate()

    alerts = alert_engine.evaluate_sensor_stream(df, sensor_type=SENSOR_HEART_RATE, subject_id="Astro_01")
    assert len(alerts) == len(df)

    # All samples in clean nominal stream should be NORMAL
    states = [a.alert_state for a in alerts]
    assert all(s == STATE_NORMAL for s in states)
    assert all(a.alert_priority == PRIORITY_NOMINAL for a in alerts)
    assert all(WORKFLOW_NO_ADDITIONAL_REVIEW in a.recommended_workflow_actions for a in alerts)


def test_missing_data_insufficient_state(alert_engine: IntelligentAlertEngine) -> None:
    """Verify that missing/NaN measurements trigger STATE_INSUFFICIENT_DATA with INFO priority."""
    record = alert_engine.evaluate_observation({
        "subject_id": "Astro_01",
        "measurement_name": "heart_rate",
        "signal_value": np.nan,
        "is_synthetic": True,
        "data_source": PATH_WEARABLE_TELEMETRY,
    })

    assert record.alert_state == STATE_INSUFFICIENT_DATA
    assert record.alert_priority == PRIORITY_INFO
    assert WORKFLOW_INSUFFICIENT_DATA in record.recommended_workflow_actions
    assert "missing or unrecorded" in record.explanation.lower()


def test_unreliable_sensor_triggers_insufficient_data(alert_engine: IntelligentAlertEngine) -> None:
    """Verify that a disconnected or degraded sensor stream triggers INSUFFICIENT_DATA."""
    gen = SyntheticSensorGenerator(SyntheticSensorConfig(duration_seconds=20, random_seed=42, scenario=SCENARIO_SENSOR_DISCONNECT))
    df = gen.generate_heart_rate()

    alerts = alert_engine.evaluate_sensor_stream(df, sensor_type=SENSOR_HEART_RATE, subject_id="Astro_01")
    # Disconnection period should have INSUFFICIENT_DATA
    disc_alerts = [a for a in alerts if a.alert_state == STATE_INSUFFICIENT_DATA]
    assert len(disc_alerts) > 0
    for a in disc_alerts:
        assert a.alert_priority == PRIORITY_INFO
        assert any("UNRELIABLE" in s or "unrecorded" in s for s in a.supporting_evidence)


def test_motion_artifact_downgrades_to_review(alert_engine: IntelligentAlertEngine) -> None:
    """
    CRITICAL MOTION REJECTION TEST:
    A high optical spike coinciding with accelerometer movement must be classified as REVIEW, NOT ATTENTION.
    """
    times = pd.date_range("2026-01-01 00:00:00", periods=15, freq="1s")
    # Base heart rate is 70 bpm, index 10 has a large spike (+50 bpm)
    hr_vals = np.full(15, 70.0)
    hr_vals[10] = 135.0
    hr_df = pd.DataFrame({
        "timestamp": times,
        "sensor_type": SENSOR_HEART_RATE,
        "signal_value": hr_vals,
        "scenario": "TEST",
        "signal_status": "VALID",
        "is_synthetic": True,
    })

    # Accelerometer shows high physical movement at index 10 (3.5g magnitude)
    accel_vals = np.full(15, 1.0)
    accel_vals[10] = 3.5
    accel_df = pd.DataFrame({
        "timestamp": times,
        "sensor_type": SENSOR_ACCELEROMETER,
        "signal_value": accel_vals,
        "scenario": "TEST",
        "signal_status": "VALID",
        "is_synthetic": True,
    })

    alerts = alert_engine.evaluate_sensor_stream(
        hr_df, sensor_type=SENSOR_HEART_RATE, accel_df=accel_df, subject_id="Astro_01"
    )

    spike_alert = alerts[10]
    # Must be REVIEW, not ATTENTION, because accelerometer detected motion
    assert spike_alert.alert_state == STATE_REVIEW
    assert spike_alert.motion_artifact_evidence["motion_correlated"] is True
    assert "motion artifact suspected" in spike_alert.explanation.lower()
    assert WORKFLOW_VERIFY_SENSOR in spike_alert.recommended_workflow_actions


def test_multi_engine_agreement_triggers_attention(alert_engine: IntelligentAlertEngine) -> None:
    """
    CONCORDANCE TEST:
    Significant Robust Z-score (Z > 3.0) + Bayesian confirmation (p < 0.01) + clean sensor
    MUST trigger STATE_ATTENTION and PRIORITY_HIGH.
    """
    times = pd.date_range("2026-01-01 00:00:00", periods=20, freq="1s")
    # Clean resting stream ~72 bpm, at index 15 a physiological spike of 125 bpm occurs without motion
    hr_vals = np.full(20, 72.0)
    hr_vals[15] = 125.0
    hr_df = pd.DataFrame({
        "timestamp": times,
        "sensor_type": SENSOR_HEART_RATE,
        "signal_value": hr_vals,
        "scenario": "TEST",
        "signal_status": "VALID",
        "is_synthetic": True,
    })

    # Accelerometer stationary (1.0g)
    accel_df = pd.DataFrame({
        "timestamp": times,
        "sensor_type": SENSOR_ACCELEROMETER,
        "signal_value": np.full(20, 1.0),
        "scenario": "TEST",
        "signal_status": "VALID",
        "is_synthetic": True,
    })

    alerts = alert_engine.evaluate_sensor_stream(
        hr_df, sensor_type=SENSOR_HEART_RATE, accel_df=accel_df, subject_id="Astro_01"
    )

    alert_15 = alerts[15]
    assert alert_15.alert_state == STATE_ATTENTION
    assert alert_15.alert_priority == PRIORITY_HIGH
    assert WORKFLOW_REQUEST_MEDICAL_REVIEW in alert_15.recommended_workflow_actions
    assert any("Concordance" in s for s in alert_15.supporting_evidence)


def test_isolation_forest_secondary_context_does_not_trigger_standalone_alert(alert_engine: IntelligentAlertEngine) -> None:
    """
    CRITICAL SAFETY CONSTRAINT:
    Isolation Forest must NOT independently trigger operational alerts when primary statistical
    and Bayesian engines indicate nominal range.
    """
    # Simulate decision fusion directly where IsoForest flags an anomaly but Statistical & Bayesian are nominal
    state, priority, supporting, conflicting, workflow = alert_engine._fuse_evidence(
        value=74.0,
        stat_result={"is_anomaly": False, "is_moderate": False, "robust_z": 0.5},
        bayes_result={"is_anomaly": False, "p_value": 0.40},
        iso_result={"is_anomaly": True, "anomaly_score": 0.85},
        sensor_trust={"reliability_category": "HIGH_RELIABILITY", "quality_score": 95.0},
        motion_result={"motion_correlated": False},
        baseline_info={"median": 72.0, "mad": 1.5, "sample_count": 30},
        trajectory_info={"recovery_class": "NOT_APPLICABLE"},
        is_wearable=True,
    )

    assert state == STATE_NORMAL
    assert priority == PRIORITY_NOMINAL
    assert any("Secondary Isolation Forest" in s for s in supporting)
    assert any("operational policy prevents standalone ML alert" in c for c in conflicting)


def test_alert_persistence_lifecycle(alert_engine: IntelligentAlertEngine) -> None:
    """Verify alert transitions: NEW -> ACTIVE -> PERSISTENT -> RESOLVED."""
    times = pd.date_range("2026-01-01 00:00:00", periods=6, freq="1s")
    # Reading stays elevated at 110 bpm across indices 1, 2, 3, 4 (threshold=3 consecutive)
    hr_vals = [72.0, 110.0, 110.0, 110.0, 110.0, 72.0]
    hr_df = pd.DataFrame({
        "timestamp": times,
        "sensor_type": SENSOR_HEART_RATE,
        "signal_value": hr_vals,
        "scenario": "TEST",
        "signal_status": "VALID",
        "is_synthetic": True,
    })

    alerts = alert_engine.evaluate_sensor_stream(
        hr_df,
        sensor_type=SENSOR_HEART_RATE,
        baseline_stats={"median": 72.0, "mad": 2.0, "sample_count": 30},
        subject_id="Astro_02",
    )

    assert alerts[0].lifecycle_status == LIFECYCLE_RESOLVED  # Baseline normal
    assert alerts[1].lifecycle_status == LIFECYCLE_NEW       # 1st detection
    assert alerts[2].lifecycle_status == LIFECYCLE_ACTIVE    # 2nd consecutive
    assert alerts[3].lifecycle_status == LIFECYCLE_PERSISTENT  # 3rd consecutive -> PERSISTENT
    assert alerts[4].lifecycle_status == LIFECYCLE_PERSISTENT  # 4th consecutive -> PERSISTENT
    assert alerts[5].lifecycle_status == LIFECYCLE_RESOLVED  # Back to normal -> RESOLVED


def test_discrete_nasa_biomarker_evaluation(alert_engine: IntelligentAlertEngine) -> None:
    """Verify Path B discrete NASA biomarker assay evaluation."""
    alert = alert_engine.evaluate_biomarker_observation(
        participant_id="C001",
        biomarker_name="TNF-alpha",
        current_value=18.5,
        current_timepoint="R+1",
        unit="pg/mL",
        panel_name="Immune",
        baseline_median=6.0,
        baseline_mad=1.2,
        preflight_sample_count=3,
        preflight_values=[5.8, 6.0, 6.2],
    )

    assert alert.data_source == PATH_NASA_LABORATORY
    assert alert.is_synthetic is False
    assert alert.alert_state == STATE_ATTENTION
    assert alert.alert_priority == PRIORITY_HIGH
    assert alert.statistical_evidence["robust_z"] > 3.0
    assert alert.bayesian_evidence["p_value"] < 0.01


def test_insufficient_preflight_baseline_biomarker(alert_engine: IntelligentAlertEngine) -> None:
    """Verify that a biomarker with n < 2 preflight samples triggers INSUFFICIENT_DATA."""
    alert = alert_engine.evaluate_biomarker_observation(
        participant_id="C002",
        biomarker_name="Novel_Marker",
        current_value=45.0,
        current_timepoint="R+1",
        unit="ng/mL",
        baseline_median=None,
        baseline_mad=None,
        preflight_sample_count=1,
    )

    assert alert.alert_state == STATE_INSUFFICIENT_DATA
    assert alert.alert_priority == PRIORITY_INFO
    assert WORKFLOW_INSUFFICIENT_DATA in alert.recommended_workflow_actions


def test_integrated_state_aggregation(alert_engine: IntelligentAlertEngine) -> None:
    """Verify aggregation across multiple parameters for a subject."""
    # Add a REVIEW alert and an ATTENTION alert
    a1 = alert_engine.evaluate_biomarker_observation(
        participant_id="C003",
        biomarker_name="IL-6",
        current_value=25.0,
        current_timepoint="R+1",
        unit="pg/mL",
        baseline_median=2.0,
        baseline_mad=0.5,
        preflight_sample_count=3,
        preflight_values=[1.8, 2.0, 2.2],
    )
    a2 = alert_engine.evaluate_biomarker_observation(
        participant_id="C003",
        biomarker_name="Cortisol",
        current_value=15.5,
        current_timepoint="R+1",
        unit="ug/dL",
        baseline_median=12.0,
        baseline_mad=1.0,
        preflight_sample_count=3,
        preflight_values=[11.5, 12.0, 12.5],
    )

    summary = alert_engine.evaluate_integrated_state(subject_id="C003", alerts=[a1, a2])
    assert summary.subject_id == "C003"
    assert summary.highest_operational_state == STATE_ATTENTION
    assert summary.highest_priority == PRIORITY_HIGH
    assert summary.active_alert_count == 2
    assert summary.attention_count == 1
    assert summary.review_count == 1


def test_normal_records_do_not_inflate_active_alert_count(alert_engine: IntelligentAlertEngine) -> None:
    normal = alert_engine.evaluate_biomarker_observation(
        participant_id="C001",
        biomarker_name="Glucose",
        current_value=12.0,
        current_timepoint="R+1",
        unit="mg/dL",
        baseline_median=12.0,
        baseline_mad=1.0,
        preflight_sample_count=3,
        preflight_values=[11.0, 12.0, 13.0],
    )
    assert normal.alert_state == STATE_NORMAL

    summary = alert_engine.evaluate_integrated_state(subject_id="C001", alerts=[normal])
    assert summary.highest_operational_state == STATE_NORMAL
    assert summary.normal_count == 1
    assert summary.active_alert_count == 0
    assert summary.active_alerts == []


def test_alert_record_json_serialization(alert_engine: IntelligentAlertEngine) -> None:
    """Verify that AlertRecord serializes cleanly to JSON without NaN errors."""
    alert = alert_engine.evaluate_observation({
        "subject_id": "Astro_03",
        "measurement_name": "spo2",
        "signal_value": 94.0,
        "is_synthetic": True,
        "data_source": PATH_WEARABLE_TELEMETRY,
    })

    d = alert.to_dict()
    assert isinstance(d, dict)

    json_str = alert.to_json(indent=2)
    assert isinstance(json_str, str)
    assert "ALT-W" in json_str

    parsed = json.loads(json_str)
    assert parsed["alert_id"] == alert.alert_id


def test_non_clinical_disclaimer_and_no_medical_diagnosis(alert_engine: IntelligentAlertEngine) -> None:
    """
    REGULATORY SAFETY GUARDRAIL:
    All alerts must include the mandatory non-clinical disclaimer and NEVER use diagnostic terms.
    """
    alert = alert_engine.evaluate_biomarker_observation(
        participant_id="C004",
        biomarker_name="Troponin",
        current_value=5.0,
        current_timepoint="R+1",
        unit="ng/mL",
        baseline_median=0.5,
        baseline_mad=0.1,
        preflight_sample_count=3,
        preflight_values=[0.4, 0.5, 0.6],
    )

    assert "RESEARCH DECISION-SUPPORT PROTOTYPE ONLY" in alert.disclaimer
    # Must never claim disease diagnosis or treatment
    forbidden_terms = ["diagnose", "diagnosis", "pathology", "prescribe", "administer medication", "infarction", "disease"]
    expl_lower = alert.explanation.lower()
    for term in forbidden_terms:
        assert term not in expl_lower, f"Forbidden medical diagnostic term '{term}' found in alert explanation!"


def test_duplicate_alert_prevention(alert_engine: IntelligentAlertEngine) -> None:
    """Verify that multiple consecutive anomalous readings update the same active alert rather than duplicating."""
    times = pd.date_range("2026-01-01 00:00:00", periods=5, freq="1s")
    hr_vals = [115.0, 116.0, 114.0, 115.5, 115.0]
    hr_df = pd.DataFrame({
        "timestamp": times,
        "sensor_type": SENSOR_HEART_RATE,
        "signal_value": hr_vals,
        "scenario": "TEST",
        "signal_status": "VALID",
        "is_synthetic": True,
    })

    alerts = alert_engine.evaluate_sensor_stream(
        hr_df,
        sensor_type=SENSOR_HEART_RATE,
        baseline_stats={"median": 70.0, "mad": 1.5, "sample_count": 30},
        subject_id="Astro_Dedup",
    )

    # Active alerts registry should contain exactly ONE entry for Astro_Dedup::heart_rate
    key = "Astro_Dedup::heart_rate"
    assert key in alert_engine.active_alerts
    active = alert_engine.active_alerts[key]
    assert active.consecutive_occurrences == 5
    assert active.lifecycle_status == LIFECYCLE_PERSISTENT


def test_alert_history_preservation_and_filtering(alert_engine: IntelligentAlertEngine) -> None:
    """Verify that all historical alert transitions are recorded and filterable."""
    a1 = alert_engine.evaluate_biomarker_observation(
        participant_id="C001",
        biomarker_name="CRP",
        current_value=12.0,
        current_timepoint="R+1",
        unit="mg/L",
        baseline_median=1.0,
        baseline_mad=0.2,
        preflight_sample_count=3,
        preflight_values=[0.9, 1.0, 1.1],
    )
    a2 = alert_engine.evaluate_biomarker_observation(
        participant_id="C002",
        biomarker_name="Albumin",
        current_value=4.5,
        current_timepoint="R+1",
        unit="g/dL",
        baseline_median=4.4,
        baseline_mad=0.1,
        preflight_sample_count=3,
        preflight_values=[4.3, 4.4, 4.5],
    )

    history = alert_engine.generate_alert_history()
    assert len(history) >= 2

    # Filter by subject
    c001_hist = alert_engine.generate_alert_history(filter_by_subject="C001")
    assert all(h["subject_id"] == "C001" for h in c001_hist)

    # Filter by state
    att_hist = alert_engine.generate_alert_history(filter_by_state=STATE_ATTENTION)
    assert all(h["alert_state"] == STATE_ATTENTION for h in att_hist)


def test_deterministic_behavior(alert_engine: IntelligentAlertEngine) -> None:
    """Verify that identical inputs produce identical AlertRecords."""
    engine1 = IntelligentAlertEngine()
    engine2 = IntelligentAlertEngine()

    gen = SyntheticSensorGenerator(SyntheticSensorConfig(duration_seconds=10, random_seed=777, scenario=SCENARIO_NORMAL))
    df = gen.generate_heart_rate()

    alerts1 = engine1.evaluate_sensor_stream(df, sensor_type=SENSOR_HEART_RATE, subject_id="Astro_Det")
    alerts2 = engine2.evaluate_sensor_stream(df, sensor_type=SENSOR_HEART_RATE, subject_id="Astro_Det")

    for a1, a2 in zip(alerts1, alerts2):
        assert a1.alert_state == a2.alert_state
        assert a1.alert_priority == a2.alert_priority
        assert a1.explanation == a2.explanation
        assert a1.recommended_workflow_actions == a2.recommended_workflow_actions


def test_data_pathway_strict_separation(alert_engine: IntelligentAlertEngine) -> None:
    """Verify that Wearable Telemetry and NASA Laboratory data pathways are strictly segregated."""
    # Path A: Wearable Telemetry
    alert_wearable = alert_engine.evaluate_observation({
        "subject_id": "Astro_Wearable",
        "measurement_name": "heart_rate",
        "signal_value": 75.0,
        "is_synthetic": True,
        "data_source": PATH_WEARABLE_TELEMETRY,
    })
    assert alert_wearable.is_synthetic is True
    assert alert_wearable.data_source == PATH_WEARABLE_TELEMETRY

    # Path B: NASA Laboratory
    alert_nasa = alert_engine.evaluate_biomarker_observation(
        participant_id="C001",
        biomarker_name="IL-6",
        current_value=15.0,
        current_timepoint="R+1",
        unit="pg/mL",
        baseline_median=2.0,
        baseline_mad=0.5,
        preflight_sample_count=3,
    )
    assert alert_nasa.is_synthetic is False
    assert alert_nasa.data_source == PATH_NASA_LABORATORY
    assert alert_nasa.data_source != alert_wearable.data_source


def test_astronaut_calm_non_alarming_summary(alert_engine: IntelligentAlertEngine) -> None:
    """Verify astronaut plain-language briefing is calm, supportive, and non-alarming."""
    alert = alert_engine.evaluate_biomarker_observation(
        participant_id="C001",
        biomarker_name="Cortisol",
        current_value=16.0,
        current_timepoint="R+1",
        unit="ug/dL",
        baseline_median=12.0,
        baseline_mad=1.0,
        preflight_sample_count=3,
        preflight_values=[11.5, 12.0, 12.5],
    )

    astro_sum = alert.astronaut_summary
    assert astro_sum["format"] == "ASTRONAUT_CREW_GUIDANCE"
    assert "crew_message" in astro_sum
    # Calm phrasing check
    msg = astro_sum["crew_message"].lower()
    assert "emergency" not in msg
    assert "danger" not in msg
    assert "critical failure" not in msg

