"""
Tests for Synthetic Wearable Sensor Stream Generator (intelligence/synthetic_sensors.py)
NASA Space Apps Challenge - WEDJAT-X Prototype
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from intelligence.synthetic_sensors import (
    SyntheticSensorConfig,
    SyntheticSensorGenerator,
    generate_normal_scenario,
    generate_motion_artifact_scenario,
    generate_noise_scenario,
    generate_missing_data_scenario,
    generate_sensor_disconnect_scenario,
    generate_signal_drift_scenario,
    save_synthetic_dataset,
    SENSOR_HEART_RATE,
    SENSOR_SPO2,
    SENSOR_ACCELEROMETER,
    ALL_SENSOR_TYPES,
    STATUS_VALID,
    STATUS_ARTIFACT,
    STATUS_MISSING,
    STATUS_DISCONNECTED,
    STATUS_DRIFT,
    SCENARIO_NORMAL,
    SCENARIO_MOTION_ARTIFACT,
    SCENARIO_NOISE,
    SCENARIO_MISSING_DATA,
    SCENARIO_SENSOR_DISCONNECT,
    SCENARIO_SIGNAL_DRIFT,
    ALL_SCENARIOS,
    OUTPUT_SCHEMA_COLUMNS,
)


# ============================================================================
# Unit Tests: Output Schema & Column Verification
# ============================================================================

def test_output_schema():
    """Verify generated dataset contains exact required columns and correct types."""
    df = generate_normal_scenario(sampling_rate_hz=1.0, duration_seconds=10.0, random_seed=42)

    assert list(df.columns) == OUTPUT_SCHEMA_COLUMNS
    assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
    assert pd.api.types.is_string_dtype(df["sensor_type"]) or pd.api.types.is_object_dtype(df["sensor_type"])
    assert pd.api.types.is_float_dtype(df["signal_value"])
    assert pd.api.types.is_string_dtype(df["scenario"]) or pd.api.types.is_object_dtype(df["scenario"])
    assert pd.api.types.is_string_dtype(df["signal_status"]) or pd.api.types.is_object_dtype(df["signal_status"])
    assert pd.api.types.is_bool_dtype(df["is_synthetic"])


# ============================================================================
# Unit Tests: Deterministic Random Seed
# ============================================================================

def test_deterministic_random_seed():
    """Identical seeds must produce identical data; differing seeds must diverge."""
    cfg1 = SyntheticSensorConfig(sampling_rate_hz=2.0, duration_seconds=15.0, random_seed=12345)
    cfg2 = SyntheticSensorConfig(sampling_rate_hz=2.0, duration_seconds=15.0, random_seed=12345)
    cfg3 = SyntheticSensorConfig(sampling_rate_hz=2.0, duration_seconds=15.0, random_seed=99999)

    df1 = SyntheticSensorGenerator(cfg1).generate_normal_scenario()
    df2 = SyntheticSensorGenerator(cfg2).generate_normal_scenario()
    df3 = SyntheticSensorGenerator(cfg3).generate_normal_scenario()

    pd.testing.assert_frame_equal(df1, df2)
    assert not df1["signal_value"].equals(df3["signal_value"])


# ============================================================================
# Unit Tests: Sampling Frequency & Timing Grid
# ============================================================================

def test_correct_sampling_frequency():
    """Verify number of samples and exact timestamp intervals for configured frequencies."""
    sampling_rate = 5.0  # 5 Hz -> dt = 0.2s
    duration = 4.0      # 4 seconds -> 20 points per sensor
    cfg = SyntheticSensorConfig(sampling_rate_hz=sampling_rate, duration_seconds=duration, random_seed=42)
    gen = SyntheticSensorGenerator(cfg)

    hr_df = gen.generate_heart_rate()
    assert len(hr_df) == 20

    time_diffs = hr_df["timestamp"].diff().dropna()
    expected_dt = pd.to_timedelta(0.2, unit="s")
    for dt in time_diffs:
        assert dt == expected_dt

    multi_df = gen.generate_normal_scenario()
    assert len(multi_df) == 20 * 3  # 3 sensors


# ============================================================================
# Unit Tests: Scenario Labels
# ============================================================================

def test_correct_scenario_labels():
    """Verify that every generator embeds the correct ground-truth scenario label."""
    gen = SyntheticSensorGenerator(SyntheticSensorConfig(duration_seconds=5.0, random_seed=42))

    scenarios = [
        (SCENARIO_NORMAL, gen.generate_normal_scenario),
        (SCENARIO_MOTION_ARTIFACT, gen.generate_motion_artifact_scenario),
        (SCENARIO_NOISE, gen.generate_noise_scenario),
        (SCENARIO_MISSING_DATA, gen.generate_missing_data_scenario),
        (SCENARIO_SENSOR_DISCONNECT, gen.generate_sensor_disconnect_scenario),
        (SCENARIO_SIGNAL_DRIFT, gen.generate_signal_drift_scenario),
    ]

    for expected_label, func in scenarios:
        df = func()
        assert (df["scenario"] == expected_label).all()


# ============================================================================
# Unit Tests: Missing Value Handling
# ============================================================================

def test_missing_value_handling():
    """
    Missing values must be NaN (not zero), labeled STATUS_MISSING,
    and distinct from valid values.
    """
    df_missing = generate_missing_data_scenario(
        sampling_rate_hz=2.0, duration_seconds=20.0, missing_prob=0.25, random_seed=42
    )

    missing_rows = df_missing[df_missing["signal_status"] == STATUS_MISSING]
    assert len(missing_rows) > 0
    # Must be NaN, never 0.0
    assert missing_rows["signal_value"].isna().all()

    # Valid rows must not be NaN
    valid_rows = df_missing[df_missing["signal_status"] == STATUS_VALID]
    assert len(valid_rows) > 0
    assert valid_rows["signal_value"].notna().all()


# ============================================================================
# Unit Tests: Sensor Disconnection Handling
# ============================================================================

def test_disconnection_handling():
    """
    Sensor disconnection must mark readings as DISCONNECTED with NaN values
    while strictly preserving continuous timestamps without dropping rows.
    """
    duration = 20.0
    sampling_rate = 2.0
    total_expected_points = int(duration * sampling_rate) * 3

    df_disc = generate_sensor_disconnect_scenario(
        sampling_rate_hz=sampling_rate, duration_seconds=duration, random_seed=42
    )

    assert len(df_disc) == total_expected_points

    disc_rows = df_disc[df_disc["signal_status"] == STATUS_DISCONNECTED]
    assert len(disc_rows) > 0
    assert disc_rows["signal_value"].isna().all()

    # Check timestamps for heart_rate sensor remain strictly uniform across disconnection
    hr_df = df_disc[df_disc["sensor_type"] == SENSOR_HEART_RATE].reset_index(drop=True)
    dt_series = hr_df["timestamp"].diff().dropna()
    expected_dt = pd.to_timedelta(0.5, unit="s")
    for dt in dt_series:
        assert dt == expected_dt


# ============================================================================
# Unit Tests: Signal Drift Behavior
# ============================================================================

def test_signal_drift_behavior():
    """Verify that signal drift scenario alters the baseline monotonically over time."""
    drift_mag = 20.0
    cfg = SyntheticSensorConfig(
        sampling_rate_hz=1.0, duration_seconds=30.0, drift_magnitude=drift_mag, random_seed=42
    )
    gen = SyntheticSensorGenerator(cfg)
    hr_df = gen.generate_heart_rate(scenario=SCENARIO_SIGNAL_DRIFT)

    assert (hr_df["signal_status"] == STATUS_DRIFT).all()

    # Initial vs late values
    initial_mean = hr_df["signal_value"].head(5).mean()
    late_mean = hr_df["signal_value"].tail(5).mean()

    # Late mean should be higher by approximately drift_mag
    assert late_mean > initial_mean + 10.0


# ============================================================================
# Unit Tests: Independent Sensor Generation
# ============================================================================

def test_independent_sensor_generation():
    """Sensors must be independently generatable with correct type labels."""
    cfg = SyntheticSensorConfig(sampling_rate_hz=1.0, duration_seconds=10.0, random_seed=42)
    gen = SyntheticSensorGenerator(cfg)

    df_hr = gen.generate_heart_rate()
    assert (df_hr["sensor_type"] == SENSOR_HEART_RATE).all()
    assert len(df_hr) == 10

    df_spo2 = gen.generate_spo2()
    assert (df_spo2["sensor_type"] == SENSOR_SPO2).all()
    assert len(df_spo2) == 10

    df_accel = gen.generate_accelerometer()
    assert (df_accel["sensor_type"] == SENSOR_ACCELEROMETER).all()
    assert len(df_accel) == 10


# ============================================================================
# Unit Tests: Synthetic Labeling & Non-Clinical Integrity
# ============================================================================

def test_synthetic_data_labeling_and_integrity():
    """All generated rows must be marked is_synthetic=True and use recognized types."""
    df = generate_motion_artifact_scenario(sampling_rate_hz=2.0, duration_seconds=10.0, random_seed=42)

    assert (df["is_synthetic"] == True).all()
    assert set(df["sensor_type"].unique()).issubset(set(ALL_SENSOR_TYPES))
    assert set(df["signal_status"].unique()).issubset({
        STATUS_VALID, STATUS_ARTIFACT, STATUS_MISSING, STATUS_DISCONNECTED, STATUS_DRIFT
    })


# ============================================================================
# Unit Tests: Configuration Validation & File Persistence
# ============================================================================

def test_config_validation():
    """Invalid configuration values must raise ValueError."""
    with pytest.raises(ValueError, match="sampling_rate_hz must be positive"):
        SyntheticSensorConfig(sampling_rate_hz=-1.0)

    with pytest.raises(ValueError, match="duration_seconds must be positive"):
        SyntheticSensorConfig(duration_seconds=0.0)

    gen = SyntheticSensorGenerator()
    with pytest.raises(ValueError, match="Unknown scenario"):
        gen.generate_scenario("INVALID_SCENARIO")


def test_save_synthetic_dataset(tmp_path):
    """Verify CSV persistence of synthetic datasets."""
    df = generate_normal_scenario(sampling_rate_hz=1.0, duration_seconds=5.0)
    saved_file = save_synthetic_dataset(df, filename="test_stream.csv", output_dir=tmp_path)

    assert saved_file.exists()
    reloaded = pd.read_csv(saved_file)
    assert len(reloaded) == len(df)
    assert list(reloaded.columns) == OUTPUT_SCHEMA_COLUMNS
