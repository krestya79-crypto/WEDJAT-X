"""
Unit and Integration Tests for WEDJAT-X Feature Extraction Engine (Phase 5)
NASA Space Apps Challenge - Astronaut Health Monitoring Prototype
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from intelligence.features import (
    EXTENDED_MOTION_FEATURES,
    FEAT_ABS_FIRST_DIFF,
    FEAT_ACCEL_MAGNITUDE_DEV,
    FEAT_ACCEL_ROLLING_MAX,
    FEAT_DELTA_FROM_MEDIAN,
    FEAT_DT_DEVIATION,
    FEAT_FIRST_DIFF,
    FEAT_RAW_VALUE,
    FEAT_ROBUST_Z_LOCAL,
    FEAT_ROLLING_MAD,
    FEAT_ROLLING_MEDIAN,
    FEAT_ROLLING_STD,
    STANDARD_SENSOR_FEATURES,
    FeatureConfig,
    extract_motion_features,
    extract_signal_statistics,
    extract_window_features,
    prepare_model_matrix,
)


def test_feature_config_validation() -> None:
    """Verify FeatureConfig parameter boundaries."""
    cfg = FeatureConfig(window_size=10, min_periods=3)
    assert cfg.window_size == 10
    assert cfg.min_periods == 3

    with pytest.raises(ValueError, match="window_size must be >= 2"):
        FeatureConfig(window_size=1)

    with pytest.raises(ValueError, match="min_periods must be >= 1"):
        FeatureConfig(min_periods=0)

    with pytest.raises(ValueError, match="min_periods.*cannot exceed window_size"):
        FeatureConfig(window_size=5, min_periods=6)


def test_chronological_ordering_enforced() -> None:
    """Verify that input records are strictly sorted by timestamp."""
    timestamps = [
        pd.Timestamp("2026-01-01 00:00:02"),
        pd.Timestamp("2026-01-01 00:00:00"),
        pd.Timestamp("2026-01-01 00:00:01"),
    ]
    vals = [75.0, 70.0, 72.0]
    df = pd.DataFrame({"timestamp": timestamps, "signal_value": vals})

    out = extract_window_features(df, config=FeatureConfig(window_size=3, min_periods=1))
    assert list(out["timestamp"]) == sorted(timestamps)
    assert out.iloc[0]["signal_value"] == 70.0
    assert out.iloc[1]["signal_value"] == 72.0
    assert out.iloc[2]["signal_value"] == 75.0


def test_no_future_data_leakage() -> None:
    """
    CRITICAL CAUSALITY TEST:
    Modifying future observations at t >= k must NOT alter extracted features at t < k.
    """
    n = 30
    timestamps = pd.date_range("2026-01-01 00:00:00", periods=n, freq="1s")
    base_vals = np.sin(np.linspace(0, 10, n))

    df_original = pd.DataFrame({"timestamp": timestamps, "signal_value": base_vals})
    feats_original = extract_window_features(df_original, config=FeatureConfig(window_size=5, min_periods=2))

    # Create mutated DataFrame where future points (index >= 20) are wildly perturbed
    mutated_vals = np.copy(base_vals)
    mutated_vals[20:] += 500.0  # Massive spike in future
    df_mutated = pd.DataFrame({"timestamp": timestamps, "signal_value": mutated_vals})
    feats_mutated = extract_window_features(df_mutated, config=FeatureConfig(window_size=5, min_periods=2))

    # All features for indices 0..19 must be identical bit-for-bit
    for col in STANDARD_SENSOR_FEATURES:
        orig_slice = feats_original.iloc[:20][col].values
        mut_slice = feats_mutated.iloc[:20][col].values
        np.testing.assert_array_equal(
            np.nan_to_num(orig_slice, nan=-9999.0),
            np.nan_to_num(mut_slice, nan=-9999.0),
            err_msg=f"Future leakage detected in feature '{col}'!",
        )


def test_strictly_past_rolling_statistics() -> None:
    """Verify that rolling median and MAD at index t do NOT include x_t itself."""
    timestamps = pd.date_range("2026-01-01 00:00:00", periods=5, freq="1s")
    vals = [10.0, 10.0, 10.0, 10.0, 1000.0]  # Sudden massive spike at index 4
    df = pd.DataFrame({"timestamp": timestamps, "signal_value": vals})

    out = extract_window_features(df, config=FeatureConfig(window_size=4, min_periods=2))

    # At index 4, value is 1000.0. The past median over indices [0, 1, 2, 3] must be 10.0, NOT affected by 1000.0!
    assert out.iloc[4][FEAT_ROLLING_MEDIAN] == 10.0
    assert out.iloc[4][FEAT_DELTA_FROM_MEDIAN] == 990.0


def test_missing_data_not_replaced_with_zero() -> None:
    """Verify that missing sensor values (NaN) are preserved and never filled with 0.0."""
    timestamps = pd.date_range("2026-01-01 00:00:00", periods=5, freq="1s")
    vals = [72.0, np.nan, 74.0, np.nan, 73.0]
    df = pd.DataFrame({"timestamp": timestamps, "signal_value": vals})

    out = extract_window_features(df, config=FeatureConfig(window_size=3, min_periods=1))

    # Raw value NaNs must remain NaN
    assert np.isnan(out.iloc[1][FEAT_RAW_VALUE])
    assert np.isnan(out.iloc[3][FEAT_RAW_VALUE])
    assert out.iloc[1][FEAT_RAW_VALUE] != 0.0


def test_first_order_differences() -> None:
    """Verify first-order difference and absolute difference calculations."""
    timestamps = pd.date_range("2026-01-01 00:00:00", periods=4, freq="1s")
    vals = [100.0, 95.0, 95.0, 105.0]
    df = pd.DataFrame({"timestamp": timestamps, "signal_value": vals})

    out = extract_window_features(df)
    assert np.isnan(out.iloc[0][FEAT_FIRST_DIFF])
    assert out.iloc[1][FEAT_FIRST_DIFF] == -5.0
    assert out.iloc[1][FEAT_ABS_FIRST_DIFF] == 5.0
    assert out.iloc[2][FEAT_FIRST_DIFF] == 0.0
    assert out.iloc[3][FEAT_FIRST_DIFF] == 10.0


def test_motion_feature_synchronization() -> None:
    """Verify merging of accelerometer activity into target sensor stream."""
    times = pd.date_range("2026-01-01 00:00:00", periods=5, freq="1s")
    hr_df = pd.DataFrame({"timestamp": times, "signal_value": [70, 71, 72, 73, 74]})
    accel_df = pd.DataFrame({"timestamp": times, "signal_value": [1.0, 1.05, 2.5, 1.0, 1.0]})

    merged = extract_motion_features(hr_df, accel_df, config=FeatureConfig(motion_window_size=3))

    assert FEAT_ACCEL_MAGNITUDE_DEV in merged.columns
    assert FEAT_ACCEL_ROLLING_MAX in merged.columns
    # Index 2 has accel 2.5 -> deviation 1.5
    assert np.isclose(merged.iloc[2][FEAT_ACCEL_MAGNITUDE_DEV], 1.5)
    # Index 3 rolling max should retain 1.5
    assert np.isclose(merged.iloc[3][FEAT_ACCEL_ROLLING_MAX], 1.5)


def test_prepare_model_matrix_drop_na() -> None:
    """Verify matrix preparation drops incomplete initial window rows."""
    timestamps = pd.date_range("2026-01-01 00:00:00", periods=10, freq="1s")
    df = pd.DataFrame({"timestamp": timestamps, "signal_value": np.arange(10, dtype=float)})

    feats = extract_window_features(df, config=FeatureConfig(window_size=5, min_periods=3))
    clean_df, X, idx = prepare_model_matrix(feats, STANDARD_SENSOR_FEATURES, drop_na_rows=True)

    assert isinstance(X, np.ndarray)
    assert X.ndim == 2
    assert X.shape[1] == len(STANDARD_SENSOR_FEATURES)
    assert not np.isnan(X).any()
    assert len(clean_df) == len(X)
    assert len(X) <= 10


def test_extract_signal_statistics_basic() -> None:
    """Verify summary statistics calculation."""
    vals = [10.0, 12.0, 11.0, 10.5, 11.5]
    stats = extract_signal_statistics(vals)

    assert stats["count"] == 5
    assert np.isclose(stats["median"], 11.0)
    assert np.isclose(stats["mean"], 11.0)
    assert stats["min"] == 10.0
    assert stats["max"] == 12.0
    assert stats["mad"] > 0
