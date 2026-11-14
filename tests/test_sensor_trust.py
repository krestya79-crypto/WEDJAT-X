"""
Tests for Sensor Trust Engine (intelligence/sensor_trust.py)
NASA Space Apps Challenge - WEDJAT-X Prototype
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from intelligence.sensor_trust import (
    SensorTrustEngine,
    SensorTrustConfig,
    apply_hampel_filter,
    RELIABILITY_HIGH,
    RELIABILITY_MODERATE,
    RELIABILITY_LOW,
    RELIABILITY_UNRELIABLE,
    RELIABILITY_INSUFFICIENT,
    SENSOR_HEART_RATE,
    SENSOR_SPO2,
    SENSOR_ACCELEROMETER,
    DEFAULT_WEIGHTS,
)
from intelligence.synthetic_sensors import (
    generate_normal_scenario,
    generate_motion_artifact_scenario,
    generate_noise_scenario,
    generate_missing_data_scenario,
    generate_sensor_disconnect_scenario,
    generate_signal_drift_scenario,
    STATUS_DISCONNECTED,
    STATUS_MISSING,
    STATUS_ARTIFACT,
    STATUS_VALID,
)


# ============================================================================
# Unit Tests: Hampel Filter Outlier Detection
# ============================================================================

def test_hampel_filter_isolated_spike():
    """Hampel filter must detect prominent isolated spikes and preserve array length."""
    vals = [70.0, 71.0, 70.5, 140.0, 71.2, 70.8, 70.1]  # 140.0 is an extreme spike
    outliers, residuals = apply_hampel_filter(vals, k=2, t_threshold=3.0)

    assert len(outliers) == len(vals)
    assert outliers[3] == True
    assert outliers[0] == False
    assert residuals[3] > 60.0


def test_hampel_filter_flat_signal():
    """Hampel filter on flat signal without spikes must flag zero outliers."""
    vals = [98.0, 98.1, 98.0, 98.2, 98.0, 98.1, 98.0]
    outliers, _ = apply_hampel_filter(vals, k=2, t_threshold=3.0)
    assert not np.any(outliers)


# ============================================================================
# Unit Tests: Sensor Trust Engine - Clean & Benchmark Scenarios
# ============================================================================

def test_clean_synthetic_stream():
    """Clean nominal stream must achieve HIGH_RELIABILITY and score >= 90 (near 100)."""
    df = generate_normal_scenario(sampling_rate_hz=1.0, duration_seconds=30.0, random_seed=42)
    engine = SensorTrustEngine()

    res = engine.evaluate_sensor(df, SENSOR_HEART_RATE)

    assert res["sensor_type"] == SENSOR_HEART_RATE
    assert res["quality_score"] >= 90.0
    assert res["reliability_category"] == RELIABILITY_HIGH
    assert res["missing_rate"] == 0.0
    assert res["disconnection_rate"] == 0.0
    assert res["drift_detected"] == False
    assert res["is_synthetic"] == True


def test_missing_data_evaluation():
    """Missing data scenario must penalize score and correctly report missing rate."""
    df = generate_missing_data_scenario(
        sampling_rate_hz=1.0, duration_seconds=40.0, missing_prob=0.30, random_seed=42
    )
    engine = SensorTrustEngine()

    res = engine.evaluate_sensor(df, SENSOR_HEART_RATE)

    assert res["missing_rate"] > 0.15
    assert res["missing_sample_count"] > 0
    assert res["quality_score"] < 95.0
    assert any("dropout" in issue.lower() or "missing" in issue.lower() for issue in res["detected_issues"])


def test_sensor_disconnection_evaluation():
    """Disconnection scenario must identify disconnection periods, rate, and duration."""
    df = generate_sensor_disconnect_scenario(
        sampling_rate_hz=2.0, duration_seconds=30.0, random_seed=42
    )
    engine = SensorTrustEngine()

    res = engine.evaluate_sensor(df, SENSOR_SPO2)

    assert res["disconnected_sample_count"] > 0
    assert res["disconnection_rate"] > 0.20
    assert res["total_disconnection_duration_seconds"] > 5.0
    assert len(res["consecutive_disconnection_periods"]) >= 1
    assert res["quality_score"] < 85.0


def test_noise_evaluation():
    """Elevated noise scenario must be detected and lower the noise sub-score."""
    df_clean = generate_normal_scenario(sampling_rate_hz=1.0, duration_seconds=30.0, random_seed=42)
    df_noisy = generate_noise_scenario(
        sampling_rate_hz=1.0, duration_seconds=30.0, noise_intensity=0.50, random_seed=42
    )
    engine = SensorTrustEngine()

    res_clean = engine.evaluate_sensor(df_clean, SENSOR_HEART_RATE)
    res_noisy = engine.evaluate_sensor(df_noisy, SENSOR_HEART_RATE)

    assert res_noisy["noise_metric"] > res_clean["noise_metric"]
    assert res_noisy["sub_scores"]["noise"] <= res_clean["sub_scores"]["noise"]


def test_spikes_and_artifacts_evaluation():
    """Motion artifact scenario must detect spikes without deleting measurements."""
    df = generate_motion_artifact_scenario(
        sampling_rate_hz=2.0, duration_seconds=30.0, artifact_prob=0.10, random_seed=42
    )
    engine = SensorTrustEngine()

    n_initial_rows = len(df[df["sensor_type"] == SENSOR_HEART_RATE])
    res = engine.evaluate_sensor(df, SENSOR_HEART_RATE)
    n_post_eval_rows = len(df[df["sensor_type"] == SENSOR_HEART_RATE])

    # Must preserve all rows (never delete compromised measurements)
    assert n_initial_rows == n_post_eval_rows
    assert res["spike_count"] > 0


def test_signal_drift_detection():
    """Drift scenario must flag baseline calibration drift."""
    df = generate_signal_drift_scenario(
        sampling_rate_hz=1.0, duration_seconds=30.0, drift_magnitude=15.0, random_seed=42
    )
    engine = SensorTrustEngine()

    res = engine.evaluate_sensor(df, SENSOR_HEART_RATE)
    assert res["drift_detected"] == True
    assert res["sub_scores"]["drift"] == 0.0


# ============================================================================
# Unit Tests: Timestamp Continuity & Anomaly Handling
# ============================================================================

def test_timestamp_gaps():
    """Timestamp gaps (> 1.5*dt) must be flagged and penalized."""
    # Create artificial 5-second gap in 1 Hz data
    times = pd.date_range("2026-01-01 00:00:00", periods=10, freq="1s").tolist()
    times.append(pd.Timestamp("2026-01-01 00:00:15"))  # 6-second gap
    times.extend(pd.date_range("2026-01-01 00:00:16", periods=10, freq="1s").tolist())

    df = pd.DataFrame({
        "timestamp": times,
        "sensor_type": SENSOR_HEART_RATE,
        "signal_value": [72.0] * len(times),
        "scenario": "TEST_GAPS",
        "signal_status": STATUS_VALID,
        "is_synthetic": True,
    })

    engine = SensorTrustEngine()
    res = engine.evaluate_sensor(df, SENSOR_HEART_RATE)

    assert res["timestamp_gap_count"] >= 1


def test_duplicate_timestamps():
    """Duplicate timestamps (dt == 0) must be counted in timing metrics."""
    times = [
        pd.Timestamp("2026-01-01 00:00:00"),
        pd.Timestamp("2026-01-01 00:00:01"),
        pd.Timestamp("2026-01-01 00:00:01"),  # Duplicate
        pd.Timestamp("2026-01-01 00:00:02"),
    ]
    df = pd.DataFrame({
        "timestamp": times,
        "sensor_type": SENSOR_HEART_RATE,
        "signal_value": [70.0, 71.0, 71.0, 72.0],
        "scenario": "TEST_DUPS",
        "signal_status": STATUS_VALID,
        "is_synthetic": True,
    })

    engine = SensorTrustEngine()
    res = engine.evaluate_sensor(df, SENSOR_HEART_RATE)
    assert res["duplicate_timestamp_count"] == 1


# ============================================================================
# Unit Tests: Edge Cases & Validation
# ============================================================================

def test_insufficient_data():
    """Fewer than 2 samples must safely return INSUFFICIENT_DATA and NaN score."""
    df_single = pd.DataFrame({
        "timestamp": [pd.Timestamp("2026-01-01 00:00:00")],
        "sensor_type": [SENSOR_HEART_RATE],
        "signal_value": [72.0],
        "scenario": ["NORMAL"],
        "signal_status": [STATUS_VALID],
        "is_synthetic": [True],
    })

    engine = SensorTrustEngine()
    res = engine.evaluate_sensor(df_single, SENSOR_HEART_RATE)
    assert res["reliability_category"] == RELIABILITY_INSUFFICIENT
    assert np.isnan(res["quality_score"])

    res_empty = engine.evaluate_sensor(pd.DataFrame(), SENSOR_HEART_RATE)
    assert res_empty["reliability_category"] == RELIABILITY_INSUFFICIENT


def test_invalid_sensor_type():
    """Unsupported sensor type must raise ValueError."""
    engine = SensorTrustEngine()
    df = generate_normal_scenario(sampling_rate_hz=1.0, duration_seconds=10.0)
    with pytest.raises(ValueError, match="Unsupported sensor_type"):
        engine.evaluate_sensor(df, "INVALID_SENSOR_TYPE")


def test_score_boundaries_and_reproducibility():
    """Scores must strictly remain within [0.0, 100.0] and be deterministic."""
    df = generate_missing_data_scenario(sampling_rate_hz=1.0, duration_seconds=30.0, random_seed=42)
    engine = SensorTrustEngine()

    res1 = engine.evaluate_sensor(df, SENSOR_HEART_RATE)
    res2 = engine.evaluate_sensor(df, SENSOR_HEART_RATE)

    assert 0.0 <= res1["quality_score"] <= 100.0
    assert res1["quality_score"] == res2["quality_score"]


def test_configurable_weights():
    """Custom valid weights must be respected; invalid weights must raise ValueError."""
    # Valid custom weights prioritizing missing data
    custom_weights = {
        "missing": 0.50,
        "disconnection": 0.20,
        "noise": 0.10,
        "spikes": 0.10,
        "continuity": 0.05,
        "drift": 0.05,
    }
    cfg = SensorTrustConfig(weights=custom_weights)
    engine = SensorTrustEngine(cfg)

    df = generate_missing_data_scenario(sampling_rate_hz=1.0, duration_seconds=30.0, random_seed=42)
    res = engine.evaluate_sensor(df, SENSOR_HEART_RATE)
    assert res["weights_used"]["missing"] == 0.50

    # Invalid weights summing to 0.8
    with pytest.raises(ValueError, match="Sensor trust weights must sum to 1.0"):
        SensorTrustConfig(weights={"missing": 0.5, "noise": 0.3})


def test_motion_artifact_cross_check():
    """Motion artifact scenario with synchronized accelerometer must report overlap."""
    df = generate_motion_artifact_scenario(sampling_rate_hz=2.0, duration_seconds=30.0, artifact_prob=0.15, random_seed=42)
    engine = SensorTrustEngine()

    res = engine.evaluate_sensor(df, SENSOR_HEART_RATE)
    assert "motion_overlap_count" in res
    assert res["motion_overlap_count"] >= 0


def test_quality_timeline_generation():
    """Timeline method must return valid rolling time series of quality scores."""
    df = generate_normal_scenario(sampling_rate_hz=1.0, duration_seconds=30.0, random_seed=42)
    engine = SensorTrustEngine()

    timeline = engine.get_quality_timeline(df, SENSOR_HEART_RATE, window_size=10)

    assert len(timeline) > 0
    assert "timestamp" in timeline.columns
    assert "quality_score" in timeline.columns
    assert "reliability_category" in timeline.columns
    assert (timeline["quality_score"] >= 80.0).all()


def test_evaluate_all():
    """evaluate_all must evaluate all 3 present sensor types."""
    df = generate_normal_scenario(sampling_rate_hz=1.0, duration_seconds=10.0, random_seed=42)
    engine = SensorTrustEngine()

    all_res = engine.evaluate_all(df)
    assert set(all_res.keys()) == {SENSOR_HEART_RATE, SENSOR_SPO2, SENSOR_ACCELEROMETER}
    for st, r in all_res.items():
        assert r["quality_score"] >= 90.0
