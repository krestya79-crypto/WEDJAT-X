"""
WEDJAT-X Sensor Trust & Signal Quality Engine
NASA Space Apps Challenge - Astronaut Health Monitoring Prototype

This module provides objective, evidence-based reliability assessment and signal-quality
scoring for wearable physiological sensors (Heart Rate, SpO2, Accelerometer).

It evaluates missingness, disconnections, high-frequency noise, transient spikes (Hampel filter),
timestamp continuity, gradual calibration drift, and accelerometer motion cross-checks.

IMPORTANT SCIENTIFIC & ETHICAL NOTICE:
--------------------------------------
Sensor quality scores and reliability categories are mathematical evaluations of signal integrity
and stream stability. They DO NOT represent clinical risk categories or medical evaluations.
Measurements affected by artifacts are flagged for operational review but NEVER silently discarded.
Synthetic test streams are explicitly identified via `is_synthetic = True`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger("WEDJAT_X.SensorTrust")

# Reliability Categories
RELIABILITY_HIGH = "HIGH_RELIABILITY"
RELIABILITY_MODERATE = "MODERATE_RELIABILITY"
RELIABILITY_LOW = "LOW_RELIABILITY"
RELIABILITY_UNRELIABLE = "UNRELIABLE"
RELIABILITY_INSUFFICIENT = "INSUFFICIENT_DATA"

# Standard Sensor Types
SENSOR_HEART_RATE = "heart_rate"
SENSOR_SPO2 = "spo2"
SENSOR_ACCELEROMETER = "accelerometer"
SUPPORTED_SENSORS: List[str] = [SENSOR_HEART_RATE, SENSOR_SPO2, SENSOR_ACCELEROMETER]

# Default Scoring Weights (Sum must equal 1.0)
DEFAULT_WEIGHTS: Dict[str, float] = {
    "missing": 0.25,
    "disconnection": 0.25,
    "noise": 0.20,
    "spikes": 0.15,
    "continuity": 0.10,
    "drift": 0.05,
}

# Empirical Noise Baseline Scale Thresholds (nominal residual MAD)
NOMINAL_NOISE_THRESHOLDS: Dict[str, float] = {
    SENSOR_HEART_RATE: 2.0,      # bpm
    SENSOR_SPO2: 0.5,            # %
    SENSOR_ACCELEROMETER: 0.10,  # g
    "default": 1.0,
}

# Drift Magnitude Thresholds
NOMINAL_DRIFT_THRESHOLDS: Dict[str, float] = {
    SENSOR_HEART_RATE: 10.0,     # bpm shift
    SENSOR_SPO2: 3.0,            # % shift
    SENSOR_ACCELEROMETER: 0.25,  # g shift
    "default": 5.0,
}


@dataclass
class SensorTrustConfig:
    """
    Configuration parameters and penalty weights for the Sensor Trust Engine.

    Attributes
    ----------
    weights : dict of str -> float
        Relative importance of quality dimensions (missing, disconnection, noise,
        spikes, continuity, drift). Must sum to 1.0.
    hampel_k : int
        Half-width of the Hampel filter outlier window (total window = 2*k + 1). Default is 3.
    hampel_threshold : float
        Sigma multiplier for Hampel outlier threshold. Default is 3.0.
    noise_window : int
        Rolling median window size for residual noise estimation. Default is 5.
    drift_min_duration_s : float
        Minimum stream duration in seconds required to evaluate baseline drift. Default is 10.0s.
    drift_thresholds : dict of str -> float
        Sensor-specific thresholds beyond which gradual change is flagged as drift.
    motion_accel_threshold : float
        Accelerometer deviation magnitude (from 1.0g) indicating physical motion. Default is 0.4g.
    motion_time_window_s : float
        Time window in seconds to link optical artifacts with motion jolts. Default is 2.0s.
    """
    weights: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    hampel_k: int = 3
    hampel_threshold: float = 3.0
    noise_window: int = 5
    drift_min_duration_s: float = 10.0
    drift_thresholds: Dict[str, float] = field(default_factory=lambda: dict(NOMINAL_DRIFT_THRESHOLDS))
    motion_accel_threshold: float = 0.4
    motion_time_window_s: float = 2.0

    def __post_init__(self) -> None:
        # Validate weights
        total_w = sum(self.weights.values())
        if not np.isclose(total_w, 1.0, atol=1e-3):
            raise ValueError(f"Sensor trust weights must sum to 1.0, got sum={total_w:.4f}: {self.weights}")
        for k, v in self.weights.items():
            if v < 0:
                raise ValueError(f"Weight '{k}' must be non-negative, got {v}")
        if self.hampel_k < 1:
            raise ValueError(f"hampel_k must be >= 1, got {self.hampel_k}")
        if self.hampel_threshold <= 0:
            raise ValueError(f"hampel_threshold must be positive, got {self.hampel_threshold}")


def apply_hampel_filter(
    values: Sequence[float],
    k: int = 3,
    t_threshold: float = 3.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Apply Hampel filter for robust outlier and spike detection.

    For each sample i, computes median and MAD in window [i-k, i+k].
    If |x_i - median| > t_threshold * (1.4826 * MAD), sample is flagged as an outlier.

    Parameters
    ----------
    values : Sequence[float]
        Numeric array of sensor readings.
    k : int, default=3
        Window half-width.
    t_threshold : float, default=3.0
        Outlier threshold multiplier.

    Returns
    -------
    is_outlier : np.ndarray of bool
        Boolean mask indicating detected spikes/outliers.
    residuals : np.ndarray of float
        Absolute deviation from local median.
    """
    arr = np.asarray(values, dtype=float)
    n = len(arr)
    is_outlier = np.zeros(n, dtype=bool)
    residuals = np.zeros(n, dtype=float)

    if n < (2 * k + 1):
        return is_outlier, residuals

    for i in range(n):
        idx_start = max(0, i - k)
        idx_end = min(n, i + k + 1)
        window = arr[idx_start:idx_end]
        valid_win = window[~np.isnan(window)]

        if len(valid_win) < 3 or np.isnan(arr[i]):
            continue

        med = np.median(valid_win)
        mad = np.median(np.abs(valid_win - med))
        scale = 1.4826 * mad
        dev = abs(arr[i] - med)
        residuals[i] = dev

        if scale > 1e-9:
            if dev > (t_threshold * scale):
                is_outlier[i] = True
        else:
            # When local MAD is zero, any deviation larger than threshold * 1e-3 is an outlier
            if dev > 1e-3:
                is_outlier[i] = True

    return is_outlier, residuals


class SensorTrustEngine:
    """
    Evaluates sensor reliability, signal stability, and telemetry fidelity.

    Produces transparent quality scores (0-100), reliability categories,
    and traceable sub-metric breakdowns without deleting compromised measurements.
    """

    def __init__(self, config: Optional[SensorTrustConfig] = None) -> None:
        """Initialize engine with optional custom configuration."""
        self.config = config or SensorTrustConfig()

    def evaluate_sensor(
        self,
        dataframe: pd.DataFrame,
        sensor_type: str,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive signal trust and quality evaluation for a specific sensor.

        Parameters
        ----------
        dataframe : pd.DataFrame
            Sensor telemetry stream conforming to schema:
            [timestamp, sensor_type, signal_value, scenario, signal_status, is_synthetic]
        sensor_type : str
            Target sensor ('heart_rate', 'spo2', 'accelerometer').

        Returns
        -------
        dict
            Comprehensive quality assessment dictionary containing quality_score,
            reliability_category, sub-metrics, detected issues, and explanations.
        """
        if sensor_type not in SUPPORTED_SENSORS:
            raise ValueError(
                f"Unsupported sensor_type '{sensor_type}'. Supported: {SUPPORTED_SENSORS}"
            )

        if dataframe is None or len(dataframe) == 0:
            return self._build_insufficient_result(sensor_type, "Empty or None dataframe provided.")

        sub = dataframe[dataframe["sensor_type"] == sensor_type].copy()
        if len(sub) == 0:
            return self._build_insufficient_result(sensor_type, f"No records found for sensor '{sensor_type}'.")

        # Parse and sort by timestamp
        sub["timestamp"] = pd.to_datetime(sub["timestamp"], errors="coerce")
        sub = sub.sort_values("timestamp").reset_index(drop=True)

        is_synthetic = bool(sub["is_synthetic"].iloc[0]) if "is_synthetic" in sub.columns else False

        # --- A & E. Timestamp Continuity & Expected Sample Count ---
        timestamps = sub["timestamp"].dropna()
        n_rows = len(sub)

        if len(timestamps) < 2:
            return self._build_insufficient_result(sensor_type, "Fewer than 2 timestamps available.")

        time_deltas = timestamps.diff().dropna().dt.total_seconds()
        pos_deltas = time_deltas[time_deltas > 0]
        dt_nominal = float(pos_deltas.median()) if len(pos_deltas) > 0 else 1.0

        t_min = timestamps.min()
        t_max = timestamps.max()
        duration_s = max(0.0, (t_max - t_min).total_seconds())

        expected_samples = max(n_rows, int(round(duration_s / dt_nominal)) + 1) if dt_nominal > 0 else n_rows

        dup_count = int((time_deltas == 0).sum())
        gap_count = int((time_deltas > (1.5 * dt_nominal)).sum())
        irregular_count = int(((time_deltas > 0) & (abs(time_deltas - dt_nominal) > (0.25 * dt_nominal))).sum())

        # --- A. Missing Data Analysis ---
        status_col = sub["signal_status"].astype(str) if "signal_status" in sub.columns else pd.Series(["VALID"] * n_rows)
        val_col = pd.to_numeric(sub["signal_value"], errors="coerce")

        is_disconnected = (status_col == "DISCONNECTED")
        is_missing = (status_col == "MISSING") | (val_col.isna() & (~is_disconnected))
        is_valid = val_col.notna() & (~is_disconnected)

        missing_count = int(is_missing.sum())
        missing_rate = float(missing_count / expected_samples) if expected_samples > 0 else 0.0
        valid_count = int(is_valid.sum())

        # --- B. Sensor Disconnection Analysis ---
        disc_count = int(is_disconnected.sum())
        disc_rate = float(disc_count / expected_samples) if expected_samples > 0 else 0.0

        disc_periods, total_disc_duration = self._analyze_disconnection_runs(sub, is_disconnected, dt_nominal)

        # --- C. Noise Analysis ---
        valid_vals = val_col[is_valid].values
        noise_metric, noise_penalty = self._analyze_noise(valid_vals, sensor_type)

        # --- D. Spikes and Artifacts Analysis ---
        spike_count, spike_rate = self._analyze_spikes_and_artifacts(sub, val_col, is_valid, status_col)

        # --- F. Signal Drift Analysis ---
        drift_detected, drift_magnitude = self._analyze_drift(sub, val_col, is_valid, duration_s, sensor_type)

        # --- G. Motion Artifact Cross-Check ---
        motion_overlap_count, motion_overlap_pct = self._cross_check_motion(dataframe, sub, is_valid, status_col)

        # --- Part 3. Quality Scoring & Issues Aggregation ---
        weights = self.config.weights
        detected_issues: List[str] = []

        # Sub-score: Missing (0 to 100)
        missing_penalty = min(1.0, missing_rate * 2.0)
        missing_subscore = max(0.0, 1.0 - missing_penalty) * 100.0
        if missing_rate > 0.05:
            detected_issues.append(f"Intermittent packet dropout rate: {missing_rate * 100.0:.1f}%")

        # Sub-score: Disconnection (0 to 100)
        disc_penalty = min(1.0, disc_rate * 2.5)
        disc_subscore = max(0.0, 1.0 - disc_penalty) * 100.0
        if disc_count > 0:
            detected_issues.append(f"Sensor disconnection fault: {disc_count} samples ({total_disc_duration:.1f}s)")

        # Sub-score: Noise (0 to 100)
        noise_subscore = max(0.0, 1.0 - noise_penalty) * 100.0
        if noise_penalty > 0.30:
            detected_issues.append(f"Elevated residual high-frequency noise: {noise_metric:.2f}")

        # Sub-score: Spikes (0 to 100)
        spike_penalty = min(1.0, spike_rate * 4.0)
        spike_subscore = max(0.0, 1.0 - spike_penalty) * 100.0
        if spike_count > 0:
            detected_issues.append(f"Transient spike/artifact occurrences: {spike_count} ({spike_rate * 100.0:.1f}%)")

        # Sub-score: Continuity (0 to 100)
        continuity_penalty = min(1.0, (gap_count * 2.0 + dup_count * 3.0 + irregular_count * 0.5) / max(expected_samples, 1) * 5.0)
        continuity_subscore = max(0.0, 1.0 - continuity_penalty) * 100.0
        if gap_count > 0 or dup_count > 0:
            detected_issues.append(f"Timestamp timing irregularities (Gaps: {gap_count}, Duplicates: {dup_count})")

        # Sub-score: Drift (0 to 100)
        drift_subscore = 0.0 if drift_detected else 100.0
        if drift_detected:
            detected_issues.append(f"Baseline calibration drift detected: {drift_magnitude:.2f} shift")

        # Composite Weighted Quality Score
        raw_score = (
            weights["missing"] * missing_subscore
            + weights["disconnection"] * disc_subscore
            + weights["noise"] * noise_subscore
            + weights["spikes"] * spike_subscore
            + weights["continuity"] * continuity_subscore
            + weights["drift"] * drift_subscore
        )
        quality_score = float(np.round(np.clip(raw_score, 0.0, 100.0), 1))

        # Reliability Category
        if valid_count < 3 and expected_samples < 5:
            reliability_category = RELIABILITY_INSUFFICIENT
            quality_score = np.nan
        elif quality_score >= 90.0:
            reliability_category = RELIABILITY_HIGH
        elif quality_score >= 75.0:
            reliability_category = RELIABILITY_MODERATE
        elif quality_score >= 50.0:
            reliability_category = RELIABILITY_LOW
        else:
            reliability_category = RELIABILITY_UNRELIABLE

        explanation = self._build_explanation(
            sensor_type=sensor_type,
            quality_score=quality_score,
            category=reliability_category,
            issues=detected_issues,
            valid_count=valid_count,
            expected_samples=expected_samples,
            is_synthetic=is_synthetic,
        )

        return {
            "sensor_type": sensor_type,
            "quality_score": quality_score,
            "reliability_category": reliability_category,
            "missing_rate": float(np.round(missing_rate, 4)),
            "disconnection_rate": float(np.round(disc_rate, 4)),
            "noise_metric": float(np.round(noise_metric, 4)),
            "spike_count": spike_count,
            "drift_detected": drift_detected,
            "timestamp_gap_count": gap_count,
            "detected_issues": detected_issues,
            "explanation": explanation,
            "is_synthetic": is_synthetic,
            # Traceable sub-metrics
            "total_expected_samples": expected_samples,
            "valid_sample_count": valid_count,
            "missing_sample_count": missing_count,
            "disconnected_sample_count": disc_count,
            "consecutive_disconnection_periods": disc_periods,
            "total_disconnection_duration_seconds": float(np.round(total_disc_duration, 2)),
            "duplicate_timestamp_count": dup_count,
            "irregular_timestamp_count": irregular_count,
            "motion_overlap_count": motion_overlap_count,
            "motion_overlap_pct": float(np.round(motion_overlap_pct, 2)),
            "sub_scores": {
                "missing": float(np.round(missing_subscore, 1)),
                "disconnection": float(np.round(disc_subscore, 1)),
                "noise": float(np.round(noise_subscore, 1)),
                "spikes": float(np.round(spike_subscore, 1)),
                "continuity": float(np.round(continuity_subscore, 1)),
                "drift": float(np.round(drift_subscore, 1)),
            },
            "weights_used": dict(weights),
        }

    def evaluate_all(self, dataframe: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
        """
        Evaluate all sensor types present in the provided dataframe.

        Parameters
        ----------
        dataframe : pd.DataFrame
            Multi-sensor telemetry dataframe.

        Returns
        -------
        dict of str -> dict
            Sensor type mapped to its comprehensive evaluation dictionary.
        """
        if dataframe is None or len(dataframe) == 0:
            return {}

        results: Dict[str, Dict[str, Any]] = {}
        present_sensors = dataframe["sensor_type"].unique()

        for st in present_sensors:
            if st in SUPPORTED_SENSORS:
                results[st] = self.evaluate_sensor(dataframe, st)

        return results

    def get_quality_timeline(
        self,
        dataframe: pd.DataFrame,
        sensor_type: str,
        window_size: Union[int, str] = 10,
    ) -> pd.DataFrame:
        """
        Compute rolling or tumbling quality scores over time to monitor signal degradation.

        Parameters
        ----------
        dataframe : pd.DataFrame
            Sensor telemetry stream.
        sensor_type : str
            Target sensor ('heart_rate', 'spo2', 'accelerometer').
        window_size : int, default=10
            Number of consecutive samples per evaluation window.

        Returns
        -------
        pd.DataFrame
            Timeline DataFrame containing timestamp, quality_score, reliability_category,
            and local issue counts.
        """
        if sensor_type not in SUPPORTED_SENSORS:
            raise ValueError(f"Unsupported sensor '{sensor_type}'. Supported: {SUPPORTED_SENSORS}")

        sub = dataframe[dataframe["sensor_type"] == sensor_type].copy()
        if len(sub) == 0:
            return pd.DataFrame(columns=["timestamp", "sensor_type", "quality_score", "reliability_category"])

        sub["timestamp"] = pd.to_datetime(sub["timestamp"], errors="coerce")
        sub = sub.sort_values("timestamp").reset_index(drop=True)

        n = len(sub)
        w_size = int(window_size) if isinstance(window_size, int) else 10
        w_size = max(3, min(w_size, n))

        records: List[Dict[str, Any]] = []

        for i in range(0, n, max(1, w_size // 2)):
            chunk = sub.iloc[i : min(n, i + w_size)]
            if len(chunk) < 3:
                continue

            center_time = chunk["timestamp"].iloc[len(chunk) // 2]
            eval_res = self.evaluate_sensor(chunk, sensor_type)

            records.append({
                "timestamp": center_time,
                "sensor_type": sensor_type,
                "quality_score": eval_res["quality_score"],
                "reliability_category": eval_res["reliability_category"],
                "missing_rate": eval_res["missing_rate"],
                "disconnection_rate": eval_res["disconnection_rate"],
                "noise_metric": eval_res["noise_metric"],
                "spike_count": eval_res["spike_count"],
                "is_synthetic": eval_res["is_synthetic"],
            })

        return pd.DataFrame(records)

    # --- Internal Analytical Helpers ---

    def _analyze_disconnection_runs(
        self,
        df: pd.DataFrame,
        is_disc: pd.Series,
        dt_nominal: float,
    ) -> Tuple[List[Dict[str, Any]], float]:
        """Detect contiguous periods of sensor disconnection."""
        periods: List[Dict[str, Any]] = []
        total_duration = 0.0

        disc_indices = np.where(is_disc.values)[0]
        if len(disc_indices) == 0:
            return periods, total_duration

        # Group contiguous runs
        runs = np.split(disc_indices, np.where(np.diff(disc_indices) != 1)[0] + 1)

        for run in runs:
            start_idx = run[0]
            end_idx = run[-1]
            t_start = df["timestamp"].iloc[start_idx]
            t_end = df["timestamp"].iloc[end_idx]
            sample_count = len(run)
            dur = max(sample_count * dt_nominal, (t_end - t_start).total_seconds())

            periods.append({
                "start_time": t_start,
                "end_time": t_end,
                "sample_count": sample_count,
                "duration_seconds": dur,
            })
            total_duration += dur

        return periods, total_duration

    def _analyze_noise(
        self,
        valid_vals: np.ndarray,
        sensor_type: str,
    ) -> Tuple[float, float]:
        """Compute residual MAD after removing physiological rolling trend."""
        if len(valid_vals) < 4:
            return 0.0, 0.0

        w = min(self.config.noise_window, len(valid_vals))
        # Compute rolling median residual
        series = pd.Series(valid_vals)
        rolling_med = series.rolling(window=w, center=True, min_periods=1).median().values
        residuals = np.abs(valid_vals - rolling_med)

        noise_mad = float(np.median(residuals))
        threshold = self.config.drift_thresholds.get(sensor_type, NOMINAL_NOISE_THRESHOLDS.get(sensor_type, 1.0))
        nominal_thresh = NOMINAL_NOISE_THRESHOLDS.get(sensor_type, 1.0)

        # Scale penalty from 0.0 to 1.0 relative to nominal threshold
        penalty = float(np.clip((noise_mad - nominal_thresh * 0.5) / (nominal_thresh * 2.0), 0.0, 1.0))
        return noise_mad, penalty

    def _analyze_spikes_and_artifacts(
        self,
        df: pd.DataFrame,
        val_col: pd.Series,
        is_valid: pd.Series,
        status_col: pd.Series,
    ) -> Tuple[int, float]:
        """Run Hampel outlier detector and aggregate artifact flags."""
        valid_indices = np.where(is_valid.values)[0]
        if len(valid_indices) < 5:
            return 0, 0.0

        valid_vals = val_col.iloc[valid_indices].values
        hampel_outliers, _ = apply_hampel_filter(
            valid_vals, k=self.config.hampel_k, t_threshold=self.config.hampel_threshold
        )

        explicit_artifacts = (status_col.iloc[valid_indices] == "ARTIFACT").values
        combined_spikes = hampel_outliers | explicit_artifacts

        spike_count = int(combined_spikes.sum())
        spike_rate = float(spike_count / len(valid_indices))
        return spike_count, spike_rate

    def _analyze_drift(
        self,
        df: pd.DataFrame,
        val_col: pd.Series,
        is_valid: pd.Series,
        duration_s: float,
        sensor_type: str,
    ) -> Tuple[bool, float]:
        """Detect baseline drift between early and late stream segments."""
        valid_vals = val_col[is_valid].values
        if len(valid_vals) < 10 or duration_s < self.config.drift_min_duration_s:
            return False, 0.0

        n_pts = len(valid_vals)
        k_pts = max(3, int(n_pts * 0.15))

        early_med = float(np.median(valid_vals[:k_pts]))
        late_med = float(np.median(valid_vals[-k_pts:]))
        magnitude = abs(late_med - early_med)

        threshold = self.config.drift_thresholds.get(sensor_type, NOMINAL_DRIFT_THRESHOLDS.get(sensor_type, 5.0))
        has_drift_label = ("DRIFT" in df["signal_status"].values)

        drift_detected = bool((magnitude >= threshold) or has_drift_label)
        return drift_detected, magnitude

    def _cross_check_motion(
        self,
        full_df: pd.DataFrame,
        sensor_sub: pd.DataFrame,
        is_valid: pd.Series,
        status_col: pd.Series,
    ) -> Tuple[int, float]:
        """Examine temporal synchronization between optical artifacts and accelerometer motion."""
        if "sensor_type" not in full_df.columns or SENSOR_ACCELEROMETER not in full_df["sensor_type"].values:
            return 0, 0.0

        accel_sub = full_df[full_df["sensor_type"] == SENSOR_ACCELEROMETER].copy()
        if len(accel_sub) == 0:
            return 0, 0.0

        accel_sub["timestamp"] = pd.to_datetime(accel_sub["timestamp"], errors="coerce")
        accel_vals = pd.to_numeric(accel_sub["signal_value"], errors="coerce")

        # Accel deviation from 1.0g or explicit artifact
        accel_motion_mask = (abs(accel_vals - 1.0) > self.config.motion_accel_threshold) | (accel_sub.get("signal_status") == "ARTIFACT")
        motion_times = accel_sub.loc[accel_motion_mask, "timestamp"].dropna().values

        if len(motion_times) == 0:
            return 0, 0.0

        # Optical artifact times
        artifact_mask = (status_col == "ARTIFACT")
        artifact_times = sensor_sub.loc[artifact_mask, "timestamp"].dropna().values
        n_artifacts = len(artifact_times)
        if n_artifacts == 0:
            return 0, 0.0

        overlap_count = 0
        w_ns = int(self.config.motion_time_window_s * 1e9)

        for a_time in artifact_times:
            # Check if any motion time is within window
            diffs = np.abs(motion_times - a_time)
            if np.any(diffs <= np.timedelta64(w_ns, "ns")):
                overlap_count += 1

        overlap_pct = (overlap_count / n_artifacts * 100.0) if n_artifacts > 0 else 0.0
        return overlap_count, overlap_pct

    def _build_insufficient_result(self, sensor_type: str, reason: str) -> Dict[str, Any]:
        """Construct fallback result structure for insufficient data."""
        return {
            "sensor_type": sensor_type,
            "quality_score": np.nan,
            "reliability_category": RELIABILITY_INSUFFICIENT,
            "missing_rate": np.nan,
            "disconnection_rate": np.nan,
            "noise_metric": np.nan,
            "spike_count": 0,
            "drift_detected": False,
            "timestamp_gap_count": 0,
            "detected_issues": [f"Insufficient data: {reason}"],
            "explanation": f"Sensor '{sensor_type}' quality evaluation impossible: {reason}",
            "is_synthetic": True,
            "total_expected_samples": 0,
            "valid_sample_count": 0,
            "missing_sample_count": 0,
            "disconnected_sample_count": 0,
            "consecutive_disconnection_periods": [],
            "total_disconnection_duration_seconds": 0.0,
            "duplicate_timestamp_count": 0,
            "irregular_timestamp_count": 0,
            "motion_overlap_count": 0,
            "motion_overlap_pct": 0.0,
            "sub_scores": {},
            "weights_used": dict(self.config.weights),
        }

    def _build_explanation(
        self,
        sensor_type: str,
        quality_score: float,
        category: str,
        issues: List[str],
        valid_count: int,
        expected_samples: int,
        is_synthetic: bool,
    ) -> str:
        """Construct clinical-data-science quality explanation."""
        synth_tag = "[SYNTHETIC TEST STREAM] " if is_synthetic else "[PHYSIOLOGICAL TELEMETRY] "
        prefix = f"{synth_tag}Sensor '{sensor_type}' evaluated as {category} (Score: {quality_score:.1f}/100.0)."

        if category == RELIABILITY_HIGH:
            return f"{prefix} Signal demonstrates excellent continuity, low noise, and minimal artifacts ({valid_count}/{expected_samples} valid points)."

        issue_str = "; ".join(issues) if issues else "Subtle signal degradation"
        return f"{prefix} Observed issues: {issue_str}. Signal integrity degraded ({valid_count}/{expected_samples} valid samples)."
