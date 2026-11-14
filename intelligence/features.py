"""
WEDJAT-X Feature Extraction and Engineering Engine
NASA Space Apps Challenge - Astronaut Health Monitoring Prototype

This module provides deterministic, reproducible feature engineering routines for
wearable sensor telemetry and biomarker time-series data.

CRITICAL CAUSALITY & INTEGRITY REQUIREMENTS:
--------------------------------------------
1. Chronological order is strictly enforced.
2. Zero future-data leakage: all rolling statistics use only past and present observations
   (or strictly past observations when estimating baseline expectations).
3. Missing readings are NEVER silently replaced with zero.
4. Sensor identity, scenario metadata, and synthetic-data provenance are preserved.
5. Target anomaly labels are NEVER used as predictive features.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

from intelligence.baseline import calculate_mad

logger = logging.getLogger("WEDJAT_X.Features")

# Feature Column Names
FEAT_RAW_VALUE = "raw_value"
FEAT_ROLLING_MEDIAN = "rolling_median_past"
FEAT_ROLLING_MAD = "rolling_mad_past"
FEAT_DELTA_FROM_MEDIAN = "delta_from_median"
FEAT_ROBUST_Z_LOCAL = "robust_z_local"
FEAT_FIRST_DIFF = "first_order_diff"
FEAT_ABS_FIRST_DIFF = "abs_first_diff"
FEAT_ROLLING_STD = "rolling_std_past"
FEAT_DT_DEVIATION = "dt_deviation"
FEAT_ACCEL_MAGNITUDE_DEV = "accel_deviation"
FEAT_ACCEL_ROLLING_MAX = "accel_rolling_max"

STANDARD_SENSOR_FEATURES: List[str] = [
    FEAT_RAW_VALUE,
    FEAT_ROLLING_MEDIAN,
    FEAT_ROLLING_MAD,
    FEAT_DELTA_FROM_MEDIAN,
    FEAT_ROBUST_Z_LOCAL,
    FEAT_FIRST_DIFF,
    FEAT_ABS_FIRST_DIFF,
    FEAT_ROLLING_STD,
    FEAT_DT_DEVIATION,
]

EXTENDED_MOTION_FEATURES: List[str] = STANDARD_SENSOR_FEATURES + [
    FEAT_ACCEL_MAGNITUDE_DEV,
    FEAT_ACCEL_ROLLING_MAX,
]


@dataclass
class FeatureConfig:
    """
    Configuration parameters for feature extraction.

    Attributes
    ----------
    window_size : int
        Number of historical samples used in the backward rolling window. Default is 10.
    min_periods : int
        Minimum number of valid historical samples required to compute rolling statistics. Default is 3.
    mad_scale_factor : float
        Normal consistency scale factor for MAD. Default is 1.4826.
    nominal_dt_seconds : Optional[float]
        Expected sampling interval in seconds (1.0 / sampling_rate_hz). If None, inferred.
    motion_window_size : int
        Window size for accelerometer motion feature aggregation. Default is 5.
    include_motion_features : bool
        Whether to merge accelerometer motion features when accelerometer data is available.
    """
    window_size: int = 10
    min_periods: int = 3
    mad_scale_factor: float = 1.4826
    nominal_dt_seconds: Optional[float] = None
    motion_window_size: int = 5
    include_motion_features: bool = False

    def __post_init__(self) -> None:
        if self.window_size < 2:
            raise ValueError(f"window_size must be >= 2, got {self.window_size}")
        if self.min_periods < 1:
            raise ValueError(f"min_periods must be >= 1, got {self.min_periods}")
        if self.min_periods > self.window_size:
            raise ValueError(f"min_periods ({self.min_periods}) cannot exceed window_size ({self.window_size})")
        if self.mad_scale_factor <= 0:
            raise ValueError(f"mad_scale_factor must be positive, got {self.mad_scale_factor}")


def _rolling_mad_causal(series: pd.Series, window: int, min_periods: int, scale: float) -> pd.Series:
    """
    Compute strictly causal rolling MAD over past samples (shifted by 1 to exclude current point).

    Parameters
    ----------
    series : pd.Series
        Signal series.
    window : int
        Window length.
    min_periods : int
        Minimum valid observations.
    scale : float
        MAD scaling factor.

    Returns
    -------
    pd.Series
        Rolling MAD values aligned with original series index.
    """
    # Shift series by 1 so window contains only strictly past observations t-window .. t-1
    past_series = series.shift(1)

    def calc_mad_window(x: np.ndarray) -> float:
        valid = x[~np.isnan(x)]
        if len(valid) < min_periods:
            return np.nan
        med = np.median(valid)
        mad = np.median(np.abs(valid - med)) * scale
        return float(mad)

    # Use rolling apply with raw numpy array
    return past_series.rolling(window=window, min_periods=min_periods).apply(
        calc_mad_window, raw=True
    )


def extract_window_features(
    df: pd.DataFrame,
    config: Optional[FeatureConfig] = None,
    value_col: str = "signal_value",
    time_col: str = "timestamp",
) -> pd.DataFrame:
    """
    Extract causal, backward-looking window statistics for a single sensor time series.

    Parameters
    ----------
    df : pd.DataFrame
        Sensor stream containing timestamp and signal values.
    config : FeatureConfig, optional
        Extraction configuration.
    value_col : str, default='signal_value'
        Name of column containing measurement values.
    time_col : str, default='timestamp'
        Name of column containing timestamps.

    Returns
    -------
    pd.DataFrame
        DataFrame with original columns and appended feature columns.

    Raises
    ------
    ValueError
        If required columns are missing.
    """
    if value_col not in df.columns:
        raise ValueError(f"Missing required value column '{value_col}' in input DataFrame.")
    if time_col not in df.columns:
        raise ValueError(f"Missing required timestamp column '{time_col}' in input DataFrame.")

    cfg = config or FeatureConfig()
    out = df.copy()

    # Enforce strict chronological ordering
    out[time_col] = pd.to_datetime(out[time_col])
    out = out.sort_values(by=time_col).reset_index(drop=True)

    s = out[value_col].astype(float)

    # 1. Raw value
    out[FEAT_RAW_VALUE] = s

    # 2. Strictly past rolling median (shifted by 1 to prevent leakage of current observation)
    s_past = s.shift(1)
    out[FEAT_ROLLING_MEDIAN] = s_past.rolling(
        window=cfg.window_size, min_periods=cfg.min_periods
    ).median()

    # 3. Strictly past rolling MAD
    out[FEAT_ROLLING_MAD] = _rolling_mad_causal(
        s, window=cfg.window_size, min_periods=cfg.min_periods, scale=cfg.mad_scale_factor
    )

    # 4. Strictly past rolling standard deviation
    out[FEAT_ROLLING_STD] = s_past.rolling(
        window=cfg.window_size, min_periods=cfg.min_periods
    ).std()

    # 5. Delta from past median: x_t - median_{t-1}
    out[FEAT_DELTA_FROM_MEDIAN] = s - out[FEAT_ROLLING_MEDIAN]

    # 6. Local Robust Z-score: (x_t - median_{t-1}) / (1.4826 * MAD_{t-1})
    mad_denom = out[FEAT_ROLLING_MAD]
    z_scores = np.where(
        mad_denom > 1e-6,
        out[FEAT_DELTA_FROM_MEDIAN] / mad_denom,
        np.where(np.abs(out[FEAT_DELTA_FROM_MEDIAN]) < 1e-6, 0.0, np.nan)
    )
    out[FEAT_ROBUST_Z_LOCAL] = z_scores

    # 7. First-order difference: x_t - x_{t-1}
    out[FEAT_FIRST_DIFF] = s.diff(1)

    # 8. Absolute first-order difference: |x_t - x_{t-1}|
    out[FEAT_ABS_FIRST_DIFF] = out[FEAT_FIRST_DIFF].abs()

    # 9. Sampling interval deviation: dt - dt_nominal
    dt_series = out[time_col].diff().dt.total_seconds()
    if cfg.nominal_dt_seconds is not None:
        nominal_dt = cfg.nominal_dt_seconds
    else:
        valid_dts = dt_series.dropna()
        if len(valid_dts) > 0:
            median_dt = valid_dts.median()
            nominal_dt = float(median_dt) if pd.notna(median_dt) and median_dt > 0 else 1.0
        else:
            nominal_dt = 1.0

    # For first observation dt_deviation is 0.0
    out[FEAT_DT_DEVIATION] = (dt_series - nominal_dt).fillna(0.0)

    return out


def extract_motion_features(
    target_df: pd.DataFrame,
    accel_df: pd.DataFrame,
    config: Optional[FeatureConfig] = None,
    time_col: str = "timestamp",
    accel_val_col: str = "signal_value",
) -> pd.DataFrame:
    """
    Synchronize accelerometer activity and extract motion cross-features.

    Parameters
    ----------
    target_df : pd.DataFrame
        Target sensor DataFrame (e.g. Heart Rate or SpO2).
    accel_df : pd.DataFrame
        Accelerometer DataFrame.
    config : FeatureConfig, optional
        Extraction configuration.
    time_col : str, default='timestamp'
        Timestamp column name.
    accel_val_col : str, default='signal_value'
        Accelerometer value column name.

    Returns
    -------
    pd.DataFrame
        Target DataFrame augmented with accelerometer motion features.
    """
    cfg = config or FeatureConfig()
    t_df = target_df.copy()
    a_df = accel_df.copy()

    t_df[time_col] = pd.to_datetime(t_df[time_col])
    a_df[time_col] = pd.to_datetime(a_df[time_col])

    t_df = t_df.sort_values(by=time_col).reset_index(drop=True)
    a_df = a_df.sort_values(by=time_col).reset_index(drop=True)

    # Accelerometer deviation from 1.0g baseline
    a_val = a_df[accel_val_col].astype(float)
    a_df["accel_dev_raw"] = (a_val - 1.0).abs()

    # Merge as-of backwards (closest past accelerometer reading within 2 seconds)
    merged = pd.merge_asof(
        t_df,
        a_df[[time_col, "accel_dev_raw"]],
        on=time_col,
        direction="backward",
        tolerance=pd.Timedelta(seconds=2.0),
    )

    merged[FEAT_ACCEL_MAGNITUDE_DEV] = merged["accel_dev_raw"].fillna(0.0)

    # Accelerometer rolling max in past window
    merged[FEAT_ACCEL_ROLLING_MAX] = (
        merged[FEAT_ACCEL_MAGNITUDE_DEV]
        .rolling(window=cfg.motion_window_size, min_periods=1)
        .max()
    )

    merged = merged.drop(columns=["accel_dev_raw"], errors="ignore")
    return merged


def prepare_model_matrix(
    df: pd.DataFrame,
    feature_cols: Sequence[str],
    drop_na_rows: bool = True,
    fill_na_strategy: Optional[str] = None,
) -> Tuple[pd.DataFrame, np.ndarray, pd.Index]:
    """
    Prepare a numerical feature matrix for machine learning models.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with extracted features.
    feature_cols : Sequence[str]
        List of numerical feature column names to extract.
    drop_na_rows : bool, default=True
        Whether to filter out rows containing NaNs in feature_cols.
    fill_na_strategy : str, optional
        Optional fill strategy ('median', 'forward') if drop_na_rows is False.

    Returns
    -------
    Tuple[pd.DataFrame, np.ndarray, pd.Index]
        - Filtered/aligned DataFrame containing original metadata.
        - Numerical 2D NumPy array X of shape (n_samples, n_features).
        - Retained row indices in the original DataFrame.

    Raises
    ------
    ValueError
        If requested feature columns are missing or if resulting matrix is empty.
    """
    missing_cols = [c for c in feature_cols if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Requested feature columns not found in DataFrame: {missing_cols}")

    feat_df = df[list(feature_cols)].copy()

    if fill_na_strategy == "median":
        feat_df = feat_df.fillna(feat_df.median())
    elif fill_na_strategy == "forward":
        feat_df = feat_df.ffill().bfill()

    if drop_na_rows:
        valid_mask = ~feat_df.isna().any(axis=1)
        retained_indices = df.index[valid_mask]
        clean_df = df.loc[retained_indices].copy()
        X = feat_df.loc[retained_indices].to_numpy(dtype=np.float64)
    else:
        retained_indices = df.index
        clean_df = df.copy()
        X = feat_df.to_numpy(dtype=np.float64)

    return clean_df, X, retained_indices


def extract_signal_statistics(values: Sequence[float]) -> Dict[str, float]:
    """
    Calculate comprehensive summary statistics for a 1D signal array.

    Parameters
    ----------
    values : Sequence[float]
        Numeric array.

    Returns
    -------
    Dict[str, float]
        Dictionary with count, mean, median, std, mad, min, max, iqr, skewness.
    """
    arr = np.asarray(values, dtype=float)
    clean = arr[~np.isnan(arr)]
    if len(clean) == 0:
        return {
            "count": 0,
            "mean": np.nan,
            "median": np.nan,
            "std": np.nan,
            "mad": np.nan,
            "min": np.nan,
            "max": np.nan,
            "iqr": np.nan,
        }

    med = float(np.median(clean))
    q75, q25 = np.percentile(clean, [75, 25])
    return {
        "count": len(clean),
        "mean": float(np.mean(clean)),
        "median": med,
        "std": float(np.std(clean, ddof=1)) if len(clean) > 1 else 0.0,
        "mad": calculate_mad(clean, scale=1.4826),
        "min": float(np.min(clean)),
        "max": float(np.max(clean)),
        "iqr": float(q75 - q25),
    }
