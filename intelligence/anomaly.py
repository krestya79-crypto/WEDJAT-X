"""
WEDJAT-X Exploratory Anomaly Detection Engine
NASA Space Apps Challenge - Astronaut Health Monitoring Prototype

This module implements exploratory statistical anomaly detection for astronaut biomarkers
using personalized baselines and Robust Z-scores (Median & Median Absolute Deviation).

IMPORTANT SCIENTIFIC & ETHICAL NOTICE:
--------------------------------------
This system performs exploratory statistical analysis on benchtop laboratory assay data
(NASA OSD-575 / Inspiration4 mission). It is NOT real-time telemetry and does NOT provide
medical diagnoses, clinical risk assessments, or pathology classification. Statistical
outliers represent physiological departures from individual preflight reference values,
which in aerospace medicine reflect complex microgravity adaptations and splashdown
stress dynamics rather than clinical disease.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd

logger = logging.getLogger("WEDJAT_X.AnomalyDetector")

# Mandatory biomedical research disclaimer
ETHICAL_MEDICAL_DISCLAIMER: str = (
    "EXPLORATORY RESEARCH ONLY: Statistical anomalies reported herein reflect mathematical "
    "deviations from individual preflight research baselines (L-92, L-44, L-3). "
    "They do NOT constitute medical diagnoses, pathology, clinical impairment, or health conditions."
)

# Standard normal consistency multiplier for MAD
DEFAULT_MAD_SCALE_FACTOR: float = 1.4826

# Standard Boris Iglewicz & Hoaglin modified z-score threshold
DEFAULT_ANOMALY_THRESHOLD: float = 3.0
DEFAULT_MODERATE_THRESHOLD: float = 2.0


def calculate_robust_z_score(
    value: float,
    baseline_median: float,
    baseline_mad: float,
    scale_factor: float = DEFAULT_MAD_SCALE_FACTOR,
) -> float:
    """
    Compute Robust Z-score (Modified Z-score) using median and MAD.

    Formula:
        Robust Z-score = (value - baseline_median) / (baseline_mad * scale_factor)

    Parameters
    ----------
    value : float
        Observed measurement value.
    baseline_median : float
        Preflight baseline median.
    baseline_mad : float
        Preflight baseline Median Absolute Deviation (MAD).
    scale_factor : float, default=1.4826
        Normal consistency scale factor. Use 1.4826 for standard normal consistency,
        or 1.0 for unscaled raw MAD.

    Returns
    -------
    float
        Robust Z-score, or np.nan if inputs are invalid or MAD is zero with non-zero delta.
    """
    if pd.isna(value) or pd.isna(baseline_median) or pd.isna(baseline_mad):
        return np.nan

    delta = value - baseline_median
    denominator = baseline_mad * scale_factor

    if denominator <= 0.0 or np.isclose(denominator, 0.0):
        # When preflight dispersion is zero:
        if np.isclose(delta, 0.0):
            return 0.0
        # If delta is non-zero but MAD is zero, Z-score is mathematically undefined
        return np.nan

    return float(delta / denominator)


def generate_explanation(
    participant_id: str,
    biomarker_name: str,
    panel_name: str,
    timepoint: str,
    value: Optional[float],
    unit: str,
    baseline_median: Optional[float],
    baseline_mad: Optional[float],
    preflight_count: int,
    robust_z: Optional[float],
    flag: str,
    threshold: float,
    days_relative_to_return: Optional[int] = None,
) -> str:
    """
    Generate a transparent, detailed scientific explanation for an evaluation record
    incorporating all underlying values and non-clinical ethics disclaimers.

    Parameters
    ----------
    participant_id : str
        Astronaut identifier (e.g. 'C001').
    biomarker_name : str
        Name of biomarker (e.g. 'CRP').
    panel_name : str
        Assay panel name.
    timepoint : str
        Sampling timepoint (e.g. 'R+1').
    value : float or None
        Observed measurement value.
    unit : str
        Measurement unit (e.g. 'pg/ml').
    baseline_median : float or None
        Preflight baseline median.
    baseline_mad : float or None
        Preflight baseline MAD.
    preflight_count : int
        Number of valid preflight samples.
    robust_z : float or None
        Computed Robust Z-score.
    flag : str
        Exploratory anomaly flag.
    threshold : float
        Robust Z-score threshold used.
    days_relative_to_return : int, optional
        Mission timeline reference in days.

    Returns
    -------
    str
        Human-readable scientific explanation.
    """
    tp_str = f"{timepoint}"
    if days_relative_to_return is not None and not pd.isna(days_relative_to_return):
        tp_str += f" (Day {int(days_relative_to_return):+d})"

    prefix = (
        f"Participant {participant_id} | Biomarker '{biomarker_name}' ({panel_name}) "
        f"at Timepoint {tp_str}:"
    )

    if flag == "MISSING_MEASUREMENT" or pd.isna(value):
        return (
            f"{prefix} Measurement value is missing (unassayed sample or reported missing). "
            f"No statistical anomaly evaluation possible. Flag: {flag}. "
            f"NOTICE: {ETHICAL_MEDICAL_DISCLAIMER}"
        )

    if flag == "INSUFFICIENT_BASELINE" or pd.isna(baseline_median) or preflight_count == 0:
        return (
            f"{prefix} Observed value is {value:.4g} {unit}, but insufficient preflight baseline "
            f"measurements are available (n={preflight_count} preflight samples). "
            f"Baseline median and MAD cannot be established. Flag: {flag}. "
            f"NOTICE: {ETHICAL_MEDICAL_DISCLAIMER}"
        )

    delta = value - baseline_median
    if baseline_median != 0:
        pct = (delta / abs(baseline_median)) * 100.0
        pct_str = f"{pct:+.2f}%"
    else:
        pct_str = "undefined (zero baseline)"

    if flag == "ZERO_BASELINE_DISPERSION":
        return (
            f"{prefix} Observed value is {value:.4g} {unit} (preflight median: {baseline_median:.4g} {unit}, "
            f"delta: {delta:+.4g} {unit}, {pct_str}). However, preflight MAD is 0.0 across n={preflight_count} "
            f"samples (identical preflight readings). Dispersion-based Robust Z-score is undefined. "
            f"Flag: {flag}. NOTICE: {ETHICAL_MEDICAL_DISCLAIMER}"
        )

    z_str = f"{robust_z:+.2f}" if robust_z is not None and not pd.isna(robust_z) else "N/A"
    mad_str = f"{baseline_mad:.4g}" if baseline_mad is not None and not pd.isna(baseline_mad) else "N/A"

    if flag == "NOMINAL":
        return (
            f"{prefix} Observed value {value:.4g} {unit} is within nominal preflight variation "
            f"(Baseline median: {baseline_median:.4g} {unit}, MAD: {mad_str} {unit}, n={preflight_count}). "
            f"Delta: {delta:+.4g} {unit} ({pct_str}), Robust Z-score: {z_str} (within threshold +/-{threshold:.1f}). "
            f"Flag: {flag}. NOTICE: {ETHICAL_MEDICAL_DISCLAIMER}"
        )

    # Elevation or Suppression
    direction = "elevation" if (robust_z is not None and robust_z > 0) else "suppression"
    return (
        f"{prefix} Statistical {direction} detected. "
        f"Observed value: {value:.4g} {unit} vs Baseline median: {baseline_median:.4g} {unit} "
        f"(Preflight MAD: {mad_str} {unit}, n={preflight_count}). "
        f"Absolute delta: {delta:+.4g} {unit} ({pct_str}). "
        f"Robust Z-score: {z_str} exceeds threshold (+/-{threshold:.1f}). "
        f"Flag: {flag}. NOTICE: {ETHICAL_MEDICAL_DISCLAIMER}"
    )


@dataclass
class AnomalyResult:
    """Structure holding anomaly detection output for a single biomarker observation."""
    participant_id: str
    biomarker_name: str
    panel_name: str
    timepoint: str
    observed_value: Optional[float]
    measurement_unit: str
    baseline_median: Optional[float]
    baseline_mad: Optional[float]
    preflight_sample_count: int
    absolute_change: Optional[float]
    percent_change: Optional[float]
    robust_z_score: Optional[float]
    anomaly_flag: str
    explanation: str
    scientific_disclaimer: str = ETHICAL_MEDICAL_DISCLAIMER

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary representation."""
        return asdict(self)


class AnomalyDetector:
    """
    Exploratory Anomaly Detection Engine for Personalized Biomarker Trajectories.

    Evaluates observed biomarker measurements against personalized preflight baselines
    using Robust Z-scores with configurable sensitivity thresholds.
    """

    def __init__(
        self,
        threshold: float = DEFAULT_ANOMALY_THRESHOLD,
        moderate_threshold: Optional[float] = DEFAULT_MODERATE_THRESHOLD,
        scale_factor: float = DEFAULT_MAD_SCALE_FACTOR,
        min_preflight_samples: int = 2,
    ) -> None:
        """
        Initialize the Anomaly Detector.

        Parameters
        ----------
        threshold : float, default=3.0
            Primary threshold for significant statistical anomaly (Robust Z-score magnitude).
        moderate_threshold : float, optional, default=2.0
            Secondary threshold for moderate statistical shifts. If None, only binary
            (NOMINAL vs STATISTICAL_ELEVATION/SUPPRESSION) is applied.
        scale_factor : float, default=1.4826
            Normal consistency multiplier for MAD.
        min_preflight_samples : int, default=2
            Minimum preflight samples required to consider preflight dispersion valid.
        """
        if threshold <= 0:
            raise ValueError(f"threshold must be positive, got {threshold}")
        if moderate_threshold is not None and moderate_threshold <= 0:
            raise ValueError(f"moderate_threshold must be positive, got {moderate_threshold}")
        if moderate_threshold is not None and moderate_threshold >= threshold:
            raise ValueError(
                f"moderate_threshold ({moderate_threshold}) must be strictly less than "
                f"threshold ({threshold})"
            )
        if scale_factor <= 0:
            raise ValueError(f"scale_factor must be positive, got {scale_factor}")

        self.threshold = float(threshold)
        self.moderate_threshold = float(moderate_threshold) if moderate_threshold is not None else None
        self.scale_factor = float(scale_factor)
        self.min_preflight_samples = int(min_preflight_samples)

    def evaluate_observation(
        self,
        value: Optional[float],
        baseline_median: Optional[float],
        baseline_mad: Optional[float],
        preflight_sample_count: int,
        participant_id: str = "Unknown",
        biomarker_name: str = "Unknown",
        panel_name: str = "Unknown",
        timepoint: str = "Unknown",
        unit: str = "",
        days_relative_to_return: Optional[int] = None,
    ) -> AnomalyResult:
        """
        Evaluate a single biomarker observation and generate a complete AnomalyResult.

        Parameters
        ----------
        value : float or None
            Observed measurement value.
        baseline_median : float or None
            Preflight baseline median.
        baseline_mad : float or None
            Preflight baseline MAD.
        preflight_sample_count : int
            Number of preflight samples available.
        participant_id : str
            Astronaut identifier.
        biomarker_name : str
            Biomarker name.
        panel_name : str
            Panel name.
        timepoint : str
            Timepoint name.
        unit : str
            Measurement unit.
        days_relative_to_return : int, optional
            Days relative to mission return.

        Returns
        -------
        AnomalyResult
            Comprehensive anomaly result dataclass.
        """
        # 1. Missing measurement
        if value is None or pd.isna(value):
            flag = "MISSING_MEASUREMENT"
            z = np.nan
            abs_change = np.nan
            pct_change = np.nan
            expl = generate_explanation(
                participant_id, biomarker_name, panel_name, timepoint, value, unit,
                baseline_median, baseline_mad, preflight_sample_count, z, flag,
                self.threshold, days_relative_to_return,
            )
            return AnomalyResult(
                participant_id=participant_id,
                biomarker_name=biomarker_name,
                panel_name=panel_name,
                timepoint=timepoint,
                observed_value=None,
                measurement_unit=unit,
                baseline_median=baseline_median,
                baseline_mad=baseline_mad,
                preflight_sample_count=preflight_sample_count,
                absolute_change=abs_change,
                percent_change=pct_change,
                robust_z_score=z,
                anomaly_flag=flag,
                explanation=expl,
            )

        # 2. Insufficient baseline
        if (
            baseline_median is None
            or pd.isna(baseline_median)
            or preflight_sample_count < self.min_preflight_samples
        ):
            flag = "INSUFFICIENT_BASELINE"
            z = np.nan
            abs_change = (
                value - baseline_median
                if (baseline_median is not None and not pd.isna(baseline_median))
                else np.nan
            )
            pct_change = (
                ((value - baseline_median) / abs(baseline_median)) * 100.0
                if (baseline_median is not None and not pd.isna(baseline_median) and baseline_median != 0)
                else np.nan
            )
            expl = generate_explanation(
                participant_id, biomarker_name, panel_name, timepoint, value, unit,
                baseline_median, baseline_mad, preflight_sample_count, z, flag,
                self.threshold, days_relative_to_return,
            )
            return AnomalyResult(
                participant_id=participant_id,
                biomarker_name=biomarker_name,
                panel_name=panel_name,
                timepoint=timepoint,
                observed_value=value,
                measurement_unit=unit,
                baseline_median=baseline_median,
                baseline_mad=baseline_mad,
                preflight_sample_count=preflight_sample_count,
                absolute_change=abs_change,
                percent_change=pct_change,
                robust_z_score=z,
                anomaly_flag=flag,
                explanation=expl,
            )

        # Compute delta and percent change
        abs_change = float(value - baseline_median)
        if baseline_median != 0:
            pct_change = float((abs_change / abs(baseline_median)) * 100.0)
        else:
            pct_change = 0.0 if abs_change == 0 else np.nan

        # 3. Check baseline MAD dispersion
        if baseline_mad is None or pd.isna(baseline_mad) or np.isclose(baseline_mad, 0.0):
            if np.isclose(abs_change, 0.0):
                flag = "NOMINAL"
                z = 0.0
            else:
                flag = "ZERO_BASELINE_DISPERSION"
                z = np.nan
            expl = generate_explanation(
                participant_id, biomarker_name, panel_name, timepoint, value, unit,
                baseline_median, baseline_mad, preflight_sample_count, z, flag,
                self.threshold, days_relative_to_return,
            )
            return AnomalyResult(
                participant_id=participant_id,
                biomarker_name=biomarker_name,
                panel_name=panel_name,
                timepoint=timepoint,
                observed_value=value,
                measurement_unit=unit,
                baseline_median=baseline_median,
                baseline_mad=baseline_mad,
                preflight_sample_count=preflight_sample_count,
                absolute_change=abs_change,
                percent_change=pct_change,
                robust_z_score=z,
                anomaly_flag=flag,
                explanation=expl,
            )

        # 4. Standard Robust Z-score calculation
        z = calculate_robust_z_score(
            value=value,
            baseline_median=baseline_median,
            baseline_mad=baseline_mad,
            scale_factor=self.scale_factor,
        )

        # Determine flag
        if self.moderate_threshold is not None:
            if z >= self.threshold:
                flag = "SIGNIFICANT_ELEVATION"
            elif z >= self.moderate_threshold:
                flag = "MODERATE_ELEVATION"
            elif z <= -self.threshold:
                flag = "SIGNIFICANT_SUPPRESSION"
            elif z <= -self.moderate_threshold:
                flag = "MODERATE_SUPPRESSION"
            else:
                flag = "NOMINAL"
        else:
            if z >= self.threshold:
                flag = "STATISTICAL_ELEVATION"
            elif z <= -self.threshold:
                flag = "STATISTICAL_SUPPRESSION"
            else:
                flag = "NOMINAL"

        expl = generate_explanation(
            participant_id, biomarker_name, panel_name, timepoint, value, unit,
            baseline_median, baseline_mad, preflight_sample_count, z, flag,
            self.threshold, days_relative_to_return,
        )

        return AnomalyResult(
            participant_id=participant_id,
            biomarker_name=biomarker_name,
            panel_name=panel_name,
            timepoint=timepoint,
            observed_value=value,
            measurement_unit=unit,
            baseline_median=baseline_median,
            baseline_mad=baseline_mad,
            preflight_sample_count=preflight_sample_count,
            absolute_change=abs_change,
            percent_change=pct_change,
            robust_z_score=z,
            anomaly_flag=flag,
            explanation=expl,
        )

    def detect_anomalies(
        self,
        df_longitudinal: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Run exploratory anomaly detection on a DataFrame of longitudinal records.

        Parameters
        ----------
        df_longitudinal : pd.DataFrame
            DataFrame produced by BaselineEngine.calculate_longitudinal_changes(),
            containing Measurement_Value, Baseline_Median, Baseline_MAD, etc.

        Returns
        -------
        pd.DataFrame
            Enriched DataFrame with:
            - Robust_Z_Score
            - Exploratory_Anomaly_Flag
            - Anomaly_Explanation
            - Scientific_Disclaimer
        """
        df = df_longitudinal.copy()

        # Check required columns
        req = {"Measurement_Value", "Baseline_Median", "Baseline_MAD"}
        if not req.issubset(df.columns):
            raise ValueError(f"Input DataFrame missing required columns: {req - set(df.columns)}")

        z_scores: List[Optional[float]] = []
        flags: List[str] = []
        explanations: List[str] = []

        for _, row in df.iterrows():
            res = self.evaluate_observation(
                value=row.get("Measurement_Value"),
                baseline_median=row.get("Baseline_Median"),
                baseline_mad=row.get("Baseline_MAD"),
                preflight_sample_count=int(row.get("Preflight_Sample_Count", 0))
                if not pd.isna(row.get("Preflight_Sample_Count", 0)) else 0,
                participant_id=str(row.get("Participant_ID", "Unknown")),
                biomarker_name=str(row.get("Biomarker_Name", "Unknown")),
                panel_name=str(row.get("Panel_Name", "Unknown")),
                timepoint=str(row.get("Timepoint", "Unknown")),
                unit=str(row.get("Measurement_Unit", "")),
                days_relative_to_return=row.get("Days_Relative_To_Return"),
            )
            z_scores.append(res.robust_z_score)
            flags.append(res.anomaly_flag)
            explanations.append(res.explanation)

        df["Robust_Z_Score"] = z_scores
        df["Exploratory_Anomaly_Flag"] = flags
        df["Anomaly_Explanation"] = explanations
        df["Scientific_Disclaimer"] = ETHICAL_MEDICAL_DISCLAIMER

        return df

    def filter_anomalies(
        self,
        df_analyzed: pd.DataFrame,
        include_moderate: bool = True,
    ) -> pd.DataFrame:
        """
        Filter analyzed records to only those exhibiting statistical anomalies.

        Parameters
        ----------
        df_analyzed : pd.DataFrame
            DataFrame returned by detect_anomalies().
        include_moderate : bool, default=True
            Whether to include moderate elevations and suppressions.

        Returns
        -------
        pd.DataFrame
            Filtered DataFrame of anomalous records.
        """
        anomaly_flags = {
            "SIGNIFICANT_ELEVATION",
            "SIGNIFICANT_SUPPRESSION",
            "STATISTICAL_ELEVATION",
            "STATISTICAL_SUPPRESSION",
        }
        if include_moderate:
            anomaly_flags.update({"MODERATE_ELEVATION", "MODERATE_SUPPRESSION"})

        return df_analyzed[df_analyzed["Exploratory_Anomaly_Flag"].isin(anomaly_flags)].copy()

    def summarize_anomalies(
        self,
        df_analyzed: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Generate aggregate count summary of anomaly flags by Timepoint and Panel.

        Parameters
        ----------
        df_analyzed : pd.DataFrame
            DataFrame returned by detect_anomalies().

        Returns
        -------
        pd.DataFrame
            Pivot/summary table of flag distributions.
        """
        summary = (
            df_analyzed.groupby(
                ["Participant_ID", "Timepoint", "Panel_Name", "Exploratory_Anomaly_Flag"]
            )
            .size()
            .reset_index(name="Biomarker_Count")
        )
        return summary
