"""
WEDJAT-X Intelligent Medical Alert Engine
NASA Space Apps Challenge - Astronaut Health Monitoring Prototype

This module provides a unified, explainable, evidence-based alert decision-support system
integrating all WEDJAT-X intelligence engines:
1. Robust Statistical Anomaly Detection (primary deviation detector)
2. Bayesian Student-t Predictive Engine (probabilistic uncertainty characterization)
3. Isolation Forest (secondary multivariate pattern & drift context)
4. Sensor Trust Engine (signal quality, missingness, disconnection scoring)
5. Accelerometer Motion Cross-Checking (motion-induced artifact identification)
6. Personalized Baseline Engine (preflight median & MAD)
7. Longitudinal Recovery Trajectory Engine (postflight temporal convergence)
8. Scientific Interpretation Engine (dual-audience technical & plain-language translation)

CRITICAL ETHICAL & SCIENTIFIC NOTICE:
--------------------------------------
This software is an exploratory research prototype for computational decision support.
It is NOT a certified medical device and NEVER generates clinical diagnoses, disease
predictions, treatment instructions, or autonomous medical interventions.
All alerts represent operational workflow classifications (NORMAL, REVIEW, ATTENTION,
INSUFFICIENT_DATA) for human flight surgeons and ground medical teams.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

from intelligence.anomaly import (
    DEFAULT_ANOMALY_THRESHOLD,
    DEFAULT_MAD_SCALE_FACTOR,
    DEFAULT_MODERATE_THRESHOLD,
    AnomalyDetector,
    calculate_robust_z_score,
)
from intelligence.baseline import BaselineEngine, calculate_mad
from intelligence.features import (
    STANDARD_SENSOR_FEATURES,
    FeatureConfig,
    extract_motion_features,
    extract_window_features,
    prepare_model_matrix,
)
from intelligence.interpretation import (
    PERMITTED_WORKFLOW_FLAGS,
    STATUS_INSUFFICIENT_DATA,
    STATUS_LIMITED,
    STATUS_SUPPORTED,
    WORKFLOW_INSUFFICIENT_DATA,
    WORKFLOW_NO_ADDITIONAL_REVIEW,
    WORKFLOW_REPEAT_MEASUREMENT,
    WORKFLOW_REQUEST_MEDICAL_REVIEW,
    WORKFLOW_REVIEW_MEASUREMENT,
    WORKFLOW_VERIFY_SENSOR,
    ScientificInterpreter,
)
from intelligence.model_evaluation import (
    BayesianAnomalyDetector,
    IsolationForestDetector,
    StatisticalBaselineDetector,
)
from intelligence.sensor_trust import (
    NOMINAL_DRIFT_THRESHOLDS,
    RELIABILITY_HIGH,
    RELIABILITY_INSUFFICIENT,
    RELIABILITY_LOW,
    RELIABILITY_MODERATE,
    RELIABILITY_UNRELIABLE,
    SENSOR_ACCELEROMETER,
    SENSOR_HEART_RATE,
    SENSOR_SPO2,
    SensorTrustConfig,
    SensorTrustEngine,
)
from intelligence.trajectory import (
    RECOVERY_APPROACHING,
    RECOVERY_FLUCTUATING,
    RECOVERY_INSUFFICIENT,
    RECOVERY_MOVING_AWAY,
    RECOVERY_STABLE,
    classify_recovery_trajectory,
)

logger = logging.getLogger("WEDJAT_X.AlertEngine")

# Operational Alert States
STATE_NORMAL = "NORMAL"
STATE_REVIEW = "REVIEW"
STATE_ATTENTION = "ATTENTION"
STATE_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
ALL_ALERT_STATES: List[str] = [STATE_NORMAL, STATE_REVIEW, STATE_ATTENTION, STATE_INSUFFICIENT_DATA]

# Alert Priorities
PRIORITY_NOMINAL = "NOMINAL"
PRIORITY_LOW = "LOW"
PRIORITY_MEDIUM = "MEDIUM"
PRIORITY_HIGH = "HIGH"
PRIORITY_INFO = "INFO"
ALL_PRIORITIES: List[str] = [PRIORITY_NOMINAL, PRIORITY_LOW, PRIORITY_MEDIUM, PRIORITY_HIGH, PRIORITY_INFO]

# Alert Lifecycle Statuses
LIFECYCLE_NEW = "NEW"
LIFECYCLE_ACTIVE = "ACTIVE"
LIFECYCLE_PERSISTENT = "PERSISTENT"
LIFECYCLE_RESOLVED = "RESOLVED"
LIFECYCLE_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
ALL_LIFECYCLE_STATUSES: List[str] = [
    LIFECYCLE_NEW,
    LIFECYCLE_ACTIVE,
    LIFECYCLE_PERSISTENT,
    LIFECYCLE_RESOLVED,
    LIFECYCLE_INSUFFICIENT_EVIDENCE,
]

# Data Pathways
PATH_WEARABLE_TELEMETRY = "Synthetic_Wearable_Telemetry"
PATH_NASA_LABORATORY = "NASA_OSD575_Laboratory_Assay"

# Mandatory Biomedical Disclaimer
NON_CLINICAL_DISCLAIMER: str = (
    "RESEARCH DECISION-SUPPORT PROTOTYPE ONLY: The operational alerts generated herein reflect "
    "mathematical deviations and multi-engine statistical concordance. They DO NOT constitute "
    "medical diagnoses, disease predictions, clinical impairment, or treatment prescriptions. "
    "All medical evaluations must be conducted by certified flight surgeons."
)


@dataclass
class AlertEngineConfig:
    """
    Configuration parameters for multi-engine decision fusion and alert classification.
    """
    stat_threshold: float = DEFAULT_ANOMALY_THRESHOLD  # 3.0
    stat_moderate_threshold: float = DEFAULT_MODERATE_THRESHOLD  # 2.0
    stat_mad_scale: float = DEFAULT_MAD_SCALE_FACTOR  # 1.4826
    bayes_p_threshold: float = 0.01
    bayes_moderate_p_threshold: float = 0.05
    iso_contamination: float = 0.05
    sensor_trust_min_score: float = 75.0  # Min score for ATTENTION qualification
    sensor_trust_unreliable_score: float = 50.0  # Threshold for UNRELIABLE
    persistence_consecutive_threshold: int = 3
    persistence_duration_seconds: float = 10.0
    motion_accel_threshold: float = 0.4
    feature_window_size: int = 10
    feature_min_periods: int = 3


@dataclass
class AlertRecord:
    """
    Standardized, fully explainable alert record conforming to Phase 6 requirements.
    """
    alert_id: str
    timestamp: str
    subject_id: str
    data_source: str
    measurement_name: str
    measurement_value: Optional[float]
    measurement_unit: str
    alert_state: str
    alert_priority: str
    lifecycle_status: str
    consecutive_occurrences: int
    persistence_duration_seconds: float
    first_detected_timestamp: str
    last_detected_timestamp: str
    contributing_engines: Dict[str, Dict[str, Any]]
    statistical_evidence: Dict[str, Any]
    bayesian_evidence: Dict[str, Any]
    isolation_forest_evidence: Dict[str, Any]
    sensor_quality_evidence: Dict[str, Any]
    motion_artifact_evidence: Dict[str, Any]
    baseline_context: Dict[str, Any]
    trajectory_context: Dict[str, Any]
    supporting_evidence: List[str]
    conflicting_evidence: List[str]
    explanation: str
    ground_medical_summary: Dict[str, Any]
    astronaut_summary: Dict[str, Any]
    recommended_workflow_actions: List[str]
    data_limitations: List[str]
    interpretation_status: str
    is_synthetic: bool
    disclaimer: str = NON_CLINICAL_DISCLAIMER

    def to_dict(self) -> Dict[str, Any]:
        """Convert alert record to serializable dictionary."""
        d = asdict(self)
        # Ensure NaN values in floats are converted safely for JSON
        def clean_val(v: Any) -> Any:
            if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
                return None
            if isinstance(v, dict):
                return {k: clean_val(val) for k, val in v.items()}
            if isinstance(v, list):
                return [clean_val(item) for item in v]
            if isinstance(v, (pd.Timestamp, datetime)):
                return str(v)
            return v
        return clean_val(d)

    def to_json(self, indent: int = 2) -> str:
        """Export alert record as formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class IntegratedStateSummary:
    """
    Aggregated operational status across all monitored parameters for a crew member.
    """
    subject_id: str
    timestamp: str
    data_source: str
    highest_operational_state: str
    highest_priority: str
    active_alert_count: int
    normal_count: int
    review_count: int
    attention_count: int
    insufficient_data_count: int
    active_alerts: List[Dict[str, Any]]
    operational_guidance: str
    is_synthetic: bool
    disclaimer: str = NON_CLINICAL_DISCLAIMER

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class IntelligentAlertEngine:
    """
    Coordinated Multi-Engine Explainable Alert Decision-Support System.
    """

    def __init__(self, config: Optional[AlertEngineConfig] = None) -> None:
        """
        Initialize the Intelligent Alert Engine with all underlying analytical modules.
        """
        self.config = config or AlertEngineConfig()
        self.sensor_trust_engine = SensorTrustEngine(
            SensorTrustConfig(
                motion_accel_threshold=self.config.motion_accel_threshold,
            )
        )
        self.scientific_interpreter = ScientificInterpreter(disclaimer=NON_CLINICAL_DISCLAIMER)

        # State tracking registries for alert lifecycle management
        self.active_alerts: Dict[str, AlertRecord] = {}
        self.alert_history: List[AlertRecord] = []
        self._alert_counter: int = 0

    def _generate_alert_id(self, prefix: str = "ALT") -> str:
        """Generate a reproducible, chronological unique alert identifier."""
        self._alert_counter += 1
        return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{self._alert_counter:05d}"

    # =========================================================================
    # 1. Decision Fusion Logic
    # =========================================================================

    def _fuse_evidence(
        self,
        value: Optional[float],
        stat_result: Dict[str, Any],
        bayes_result: Dict[str, Any],
        iso_result: Dict[str, Any],
        sensor_trust: Dict[str, Any],
        motion_result: Dict[str, Any],
        baseline_info: Dict[str, Any],
        trajectory_info: Dict[str, Any],
        is_wearable: bool,
    ) -> Tuple[str, str, List[str], List[str], List[str]]:
        """
        Multi-engine evidence-based decision fusion mechanism.

        Returns
        -------
        Tuple[alert_state, alert_priority, supporting_evidence, conflicting_evidence, workflow_actions]
        """
        supporting: List[str] = []
        conflicting: List[str] = []
        workflow_actions: List[str] = []

        # 1. Missing or unrecorded data
        if value is None or pd.isna(value):
            return (
                STATE_INSUFFICIENT_DATA,
                PRIORITY_INFO,
                ["Observed measurement value is missing or unrecorded."],
                [],
                [WORKFLOW_INSUFFICIENT_DATA],
            )

        # 2. Check sensor reliability (for wearable streams)
        rel_cat = sensor_trust.get("reliability_category", RELIABILITY_HIGH)
        qual_score = sensor_trust.get("quality_score")
        if is_wearable:
            if rel_cat in [RELIABILITY_UNRELIABLE, RELIABILITY_INSUFFICIENT]:
                supporting.append(
                    f"Sensor trust engine evaluated signal as UNRELIABLE (Quality Score: {qual_score}/100.0)."
                )
                if sensor_trust.get("missing_rate", 0) > 0.30:
                    supporting.append(f"Severe packet loss / dropout rate ({sensor_trust['missing_rate']*100.0:.1f}%).")
                if sensor_trust.get("disconnection_rate", 0) > 0.20:
                    supporting.append("Sensor disconnection event detected.")
                return (
                    STATE_INSUFFICIENT_DATA,
                    PRIORITY_INFO,
                    supporting,
                    [],
                    [WORKFLOW_VERIFY_SENSOR, WORKFLOW_REPEAT_MEASUREMENT],
                )

        # 3. Check baseline sufficiency
        base_count = baseline_info.get("sample_count", 0)
        if base_count < 2 and baseline_info.get("median") is None:
            return (
                STATE_INSUFFICIENT_DATA,
                PRIORITY_INFO,
                ["Insufficient baseline measurements (n < 2). Reference range not established."],
                [],
                [WORKFLOW_INSUFFICIENT_DATA],
            )

        # 4. Extract engine outputs
        stat_flag = stat_result.get("is_anomaly", False)
        stat_moderate = stat_result.get("is_moderate", False)
        stat_z = stat_result.get("robust_z")

        bayes_flag = bayes_result.get("is_anomaly", False)
        bayes_p = bayes_result.get("p_value")

        iso_flag = iso_result.get("is_anomaly", False)
        iso_score = iso_result.get("anomaly_score")

        is_motion = motion_result.get("motion_correlated", False)

        # Evidence compilation
        if stat_z is not None and not np.isnan(stat_z):
            if abs(stat_z) >= self.config.stat_threshold:
                supporting.append(f"Primary Statistical Engine: Significant Robust Z-score = {stat_z:+.2f} (Threshold: +/-{self.config.stat_threshold:.1f}).")
            elif abs(stat_z) >= self.config.stat_moderate_threshold:
                supporting.append(f"Primary Statistical Engine: Moderate Robust Z-score = {stat_z:+.2f} (Threshold: +/-{self.config.stat_moderate_threshold:.1f}).")
            else:
                conflicting.append(f"Primary Statistical Engine: Measurement is within nominal baseline dispersion (Z = {stat_z:+.2f}).")

        if bayes_p is not None and not np.isnan(bayes_p):
            if bayes_p < self.config.bayes_p_threshold:
                supporting.append(f"Bayesian Student-t Engine: Strong tail probability deviation (p = {bayes_p:.4e} < {self.config.bayes_p_threshold}).")
            elif bayes_p < self.config.bayes_moderate_p_threshold:
                supporting.append(f"Bayesian Student-t Engine: Moderate tail deviation (p = {bayes_p:.4e} < {self.config.bayes_moderate_p_threshold}).")
            else:
                conflicting.append(f"Bayesian Student-t Engine: High posterior predictive likelihood (p = {bayes_p:.3f} >= {self.config.bayes_moderate_p_threshold}).")

        if iso_flag:
            supporting.append(f"Secondary Isolation Forest: Multidimensional feature deviation detected (Score = {iso_score:.3f}).")
        else:
            if iso_score is not None:
                conflicting.append(f"Secondary Isolation Forest: Feature space aligned with inlier distribution (Score = {iso_score:.3f}).")

        # 5. Motion Artifact Override (Crucial for reducing false alarms)
        if is_wearable and is_motion:
            supporting.append("Accelerometer Cross-Check: Concurrent physical movement detected (|a - 1g| > 0.4g).")
            # If an anomaly was detected, motion correlation explains it
            if stat_flag or bayes_flag:
                supporting.append("Decision Fusion: Optical signal shift temporally coincides with dynamic movement; likely motion artifact.")
                return (
                    STATE_REVIEW,
                    PRIORITY_LOW,
                    supporting,
                    conflicting,
                    [WORKFLOW_VERIFY_SENSOR, WORKFLOW_REVIEW_MEASUREMENT],
                )

        # 6. Degraded Sensor Quality Downgrade
        if is_wearable and rel_cat == RELIABILITY_LOW:
            supporting.append(f"Sensor trust quality is degraded ({qual_score}/100.0). Measurement reliability reduced.")
            if stat_flag or bayes_flag:
                return (
                    STATE_REVIEW,
                    PRIORITY_LOW,
                    supporting,
                    conflicting,
                    [WORKFLOW_VERIFY_SENSOR, WORKFLOW_REVIEW_MEASUREMENT],
                )

        # 7. Multi-Engine Agreement -> ATTENTION
        # Agreement between Primary Statistical Baseline AND Bayesian Student-t
        if stat_flag and bayes_flag:
            supporting.append("Concordance: Both Primary Statistical Engine and Bayesian Student-t Engine confirm significant deviation.")
            traj_class = trajectory_info.get("recovery_class")
            if traj_class == RECOVERY_APPROACHING:
                supporting.append("Longitudinal Trajectory Context: Trajectory demonstrates active convergence toward preflight baseline.")
            elif traj_class in [RECOVERY_MOVING_AWAY, RECOVERY_FLUCTUATING]:
                supporting.append(f"Longitudinal Trajectory Context: Trajectory status is {traj_class}.")

            workflow_actions = [WORKFLOW_REQUEST_MEDICAL_REVIEW, WORKFLOW_REVIEW_MEASUREMENT]
            return (
                STATE_ATTENTION,
                PRIORITY_HIGH,
                supporting,
                conflicting,
                workflow_actions,
            )

        # 8. Single-Engine Significant Deviation or Moderate Multi-Engine Shift -> REVIEW
        bayes_moderate = (bayes_p is not None and bayes_p < self.config.bayes_moderate_p_threshold)
        if stat_flag or bayes_flag or (stat_moderate and bayes_moderate):
            workflow_actions = [WORKFLOW_REVIEW_MEASUREMENT]
            priority = PRIORITY_MEDIUM if (stat_flag or bayes_flag) else PRIORITY_LOW
            return (
                STATE_REVIEW,
                priority,
                supporting,
                conflicting,
                workflow_actions,
            )

        # 9. Isolation Forest Only (Secondary ML Context)
        # CRITICAL RULE: Isolation Forest MUST NOT independently trigger operational alerts!
        if iso_flag and not stat_flag and not bayes_flag and not stat_moderate:
            supporting.append("Secondary Isolation Forest flagged feature deviation, but primary statistical & Bayesian engines are nominal.")
            conflicting.append("Isolation Forest lacks statistical concordance; operational policy prevents standalone ML alert triggering.")
            return (
                STATE_NORMAL,
                PRIORITY_NOMINAL,
                supporting,
                conflicting,
                [WORKFLOW_NO_ADDITIONAL_REVIEW],
            )

        # 10. Nominal State
        return (
            STATE_NORMAL,
            PRIORITY_NOMINAL,
            supporting,
            conflicting,
            [WORKFLOW_NO_ADDITIONAL_REVIEW],
        )

    # =========================================================================
    # 2. Lifecycle & Deduplication Tracking
    # =========================================================================

    def _update_alert_lifecycle(
        self,
        subject_id: str,
        measurement_name: str,
        alert_state: str,
        timestamp_str: str,
    ) -> Tuple[str, int, float, str]:
        """
        Manage alert persistence, state transitions, and deduplication.

        Returns
        -------
        Tuple[lifecycle_status, consecutive_occurrences, persistence_duration_s, first_detected_timestamp]
        """
        key = f"{subject_id}::{measurement_name}"
        prev_alert = self.active_alerts.get(key)

        is_alert_state = alert_state in [STATE_REVIEW, STATE_ATTENTION]

        if prev_alert is None:
            if is_alert_state:
                lifecycle = LIFECYCLE_NEW
                consecutive = 1
                duration = 0.0
                first_ts = timestamp_str
            else:
                lifecycle = LIFECYCLE_RESOLVED
                consecutive = 0
                duration = 0.0
                first_ts = timestamp_str
        else:
            prev_is_alert = prev_alert.alert_state in [STATE_REVIEW, STATE_ATTENTION]
            first_ts = prev_alert.first_detected_timestamp

            if is_alert_state:
                if prev_is_alert:
                    consecutive = prev_alert.consecutive_occurrences + 1
                    # Duration estimation
                    try:
                        t0 = pd.to_datetime(first_ts)
                        t1 = pd.to_datetime(timestamp_str)
                        duration = max(0.0, float((t1 - t0).total_seconds()))
                    except Exception:
                        duration = float(consecutive * 1.0)

                    if consecutive >= self.config.persistence_consecutive_threshold or duration >= self.config.persistence_duration_seconds:
                        lifecycle = LIFECYCLE_PERSISTENT
                    else:
                        lifecycle = LIFECYCLE_ACTIVE
                else:
                    lifecycle = LIFECYCLE_NEW
                    consecutive = 1
                    duration = 0.0
                    first_ts = timestamp_str
            else:
                # Alert resolved or returned to normal / insufficient
                if alert_state == STATE_INSUFFICIENT_DATA:
                    lifecycle = LIFECYCLE_INSUFFICIENT_EVIDENCE
                else:
                    lifecycle = LIFECYCLE_RESOLVED
                consecutive = 0
                duration = 0.0

        return lifecycle, consecutive, duration, first_ts

    # =========================================================================
    # 3. Path A: Wearable Telemetry Evaluator
    # =========================================================================

    def evaluate_sensor_stream(
        self,
        stream_df: pd.DataFrame,
        sensor_type: str,
        accel_df: Optional[pd.DataFrame] = None,
        baseline_stats: Optional[Dict[str, float]] = None,
        subject_id: str = "Synthetic_Astronaut",
    ) -> List[AlertRecord]:
        """
        Evaluate a continuous wearable sensor telemetry stream.

        Parameters
        ----------
        stream_df : pd.DataFrame
            Wearable telemetry DataFrame conforming to standard schema.
        sensor_type : str
            Sensor identifier ('heart_rate', 'spo2', 'accelerometer').
        accel_df : pd.DataFrame, optional
            Synchronized accelerometer stream for motion cross-checking.
        baseline_stats : dict, optional
            Reference baseline median and MAD. If None, estimated from stream.
        subject_id : str
            Subject identifier.

        Returns
        -------
        List[AlertRecord]
            Chronological list of evaluated alert records.
        """
        if stream_df.empty:
            return []

        df = stream_df.copy().sort_values(by="timestamp").reset_index(drop=True)
        is_synthetic = bool(df["is_synthetic"].iloc[0]) if "is_synthetic" in df.columns else True

        # 1. Run Sensor Trust Engine on the stream
        if accel_df is not None and not accel_df.empty:
            trust_input_df = pd.concat([df, accel_df], ignore_index=True)
        else:
            trust_input_df = df

        if len(df) >= 2:
            trust_result = self.sensor_trust_engine.evaluate_sensor(
                trust_input_df, sensor_type=sensor_type
            )
        else:
            # Single sample stream or placeholder
            is_valid_pt = not pd.isna(df["signal_value"].iloc[0])
            trust_result = {
                "sensor_type": sensor_type,
                "quality_score": 100.0 if is_valid_pt else 0.0,
                "reliability_category": RELIABILITY_HIGH if is_valid_pt else RELIABILITY_UNRELIABLE,
                "missing_rate": 0.0 if is_valid_pt else 1.0,
                "disconnection_rate": 0.0,
                "spike_count": 0,
                "drift_detected": False,
                "detected_issues": [] if is_valid_pt else ["Single observation missing/unrecorded."],
                "is_synthetic": is_synthetic,
            }

        # 2. Extract Causal Window Features
        feat_cfg = FeatureConfig(
            window_size=self.config.feature_window_size,
            min_periods=self.config.feature_min_periods,
        )
        feat_df = extract_window_features(df, config=feat_cfg)
        if accel_df is not None and not accel_df.empty:
            feat_df = extract_motion_features(feat_df, accel_df, config=feat_cfg)

        # 3. Baseline estimation
        vals_clean = df["signal_value"].dropna().values
        stat_detector = None
        bayes_detector = None

        if baseline_stats is not None:
            base_med = float(baseline_stats.get("median", float(np.median(vals_clean)) if len(vals_clean) else 70.0))
            base_mad = float(baseline_stats.get("mad", calculate_mad(vals_clean, scale=1.0) if len(vals_clean) else 1.0))
            base_count = int(baseline_stats.get("sample_count", len(vals_clean)))

            stat_detector = StatisticalBaselineDetector(
                threshold=self.config.stat_threshold,
                moderate_threshold=self.config.stat_moderate_threshold,
                scale_factor=self.config.stat_mad_scale,
            )
            stat_detector.baseline_median = base_med
            stat_detector.baseline_mad = base_mad
            stat_detector.train_count = base_count

            bayes_detector = BayesianAnomalyDetector(
                probability_threshold=self.config.bayes_p_threshold
            )
            bayes_detector.mu_n = base_med
            bayes_detector.pred_scale = max(base_mad * self.config.stat_mad_scale, 0.5)
            bayes_detector.df = float(max(base_count * 2, 4.0))
            bayes_detector.is_fitted = True
        else:
            # Use calibration / initial segment as baseline reference
            init_n = min(len(vals_clean), 30)
            base_med = float(np.median(vals_clean[:init_n])) if init_n > 0 else 70.0
            raw_mad = calculate_mad(vals_clean[:init_n], scale=1.0) if init_n > 0 else 1.0
            min_floor = 1.5 if sensor_type == SENSOR_HEART_RATE else (0.5 if sensor_type == SENSOR_SPO2 else 0.1)
            base_mad = max(raw_mad, min_floor)
            base_count = init_n

            if len(vals_clean) >= 2:
                try:
                    stat_detector = StatisticalBaselineDetector(
                        threshold=self.config.stat_threshold,
                        moderate_threshold=self.config.stat_moderate_threshold,
                        scale_factor=self.config.stat_mad_scale,
                    )
                    stat_detector.baseline_median = base_med
                    stat_detector.baseline_mad = base_mad
                    stat_detector.train_count = base_count

                    bayes_detector = BayesianAnomalyDetector(
                        probability_threshold=self.config.bayes_p_threshold
                    )
                    bayes_detector.mu_n = base_med
                    bayes_detector.pred_scale = max(base_mad * self.config.stat_mad_scale, 0.5)
                    bayes_detector.df = float(max(base_count * 2, 4.0))
                    bayes_detector.is_fitted = True
                except Exception as e:
                    logger.debug("Baseline fitting skipped: %s", e)

        # Fit Isolation Forest on causal features
        _, X_mat, valid_feat_idx = prepare_model_matrix(
            feat_df, feature_cols=STANDARD_SENSOR_FEATURES, drop_na_rows=True
        )
        iso_detector = None
        if len(X_mat) >= 10:
            try:
                iso_detector = IsolationForestDetector(
                    contamination=self.config.iso_contamination,
                    random_state=42,
                    feature_cols=STANDARD_SENSOR_FEATURES,
                ).fit(X_mat)
            except Exception as e:
                logger.debug("Isolation Forest fit failed: %s", e)

        # 4. Step-by-step stream evaluation
        alerts: List[AlertRecord] = []

        for idx, row in df.iterrows():
            ts_str = str(row["timestamp"])
            val = row["signal_value"]

            # Statistical check
            if pd.isna(val) or stat_detector is None:
                stat_res = {"is_anomaly": False, "is_moderate": False, "robust_z": np.nan}
                bayes_res = {"is_anomaly": False, "p_value": np.nan}
                iso_res = {"is_anomaly": False, "anomaly_score": 0.0}
            else:
                s_flags, s_scores = stat_detector.predict([val])
                z_val = calculate_robust_z_score(
                    val, base_med, base_mad, scale_factor=self.config.stat_mad_scale
                )
                stat_res = {
                    "is_anomaly": bool(s_flags[0] == 1),
                    "is_moderate": bool(abs(z_val) >= self.config.stat_moderate_threshold) if not np.isnan(z_val) else False,
                    "robust_z": float(z_val) if not np.isnan(z_val) else np.nan,
                }

                # Bayesian check
                b_flags, b_scores, b_pvals = bayes_detector.predict([val])
                bayes_res = {
                    "is_anomaly": bool(b_flags[0] == 1),
                    "p_value": float(b_pvals[0]),
                    "anomaly_score": float(b_scores[0]),
                }

                # Isolation Forest check
                if iso_detector is not None and idx in valid_feat_idx:
                    pos = list(valid_feat_idx).index(idx)
                    x_sample = X_mat[pos : pos + 1]
                    i_flags, i_scores = iso_detector.predict(x_sample)
                    iso_res = {
                        "is_anomaly": bool(i_flags[0] == 1),
                        "anomaly_score": float(i_scores[0]),
                    }
                else:
                    iso_res = {"is_anomaly": False, "anomaly_score": 0.0}

            # Motion check
            is_motion = False
            motion_mag = 0.0
            if "accel_deviation" in feat_df.columns:
                motion_mag = float(feat_df.iloc[idx]["accel_deviation"])
                is_motion = motion_mag > self.config.motion_accel_threshold

            motion_res = {
                "motion_correlated": is_motion,
                "accel_deviation_g": motion_mag,
            }

            baseline_info = {
                "median": base_med,
                "mad": base_mad,
                "sample_count": base_count,
            }

            trajectory_info = {
                "recovery_class": "NOT_APPLICABLE_REALTIME_STREAM",
                "trend": "STREAMING",
            }

            # Decision Fusion
            state, priority, supporting, conflicting, workflow = self._fuse_evidence(
                value=val,
                stat_result=stat_res,
                bayes_result=bayes_res,
                iso_result=iso_res,
                sensor_trust=trust_result,
                motion_result=motion_res,
                baseline_info=baseline_info,
                trajectory_info=trajectory_info,
                is_wearable=True,
            )

            # Lifecycle Tracking
            lifecycle, consec, duration_s, first_ts = self._update_alert_lifecycle(
                subject_id=subject_id,
                measurement_name=sensor_type,
                alert_state=state,
                timestamp_str=ts_str,
            )

            # Construct Human-Readable Explanation
            explanation = self._build_stream_explanation(
                state=state,
                sensor_type=sensor_type,
                val=val,
                z=stat_res.get("robust_z"),
                bayes_p=bayes_res.get("p_value"),
                is_motion=is_motion,
                trust_result=trust_result,
                lifecycle=lifecycle,
                duration_s=duration_s,
            )

            # Generate Dual-Audience Summaries
            ground_sum, astro_sum = self._generate_dual_summaries(
                subject_id=subject_id,
                name=sensor_type,
                val=val,
                unit=self._get_unit(sensor_type),
                state=state,
                priority=priority,
                base_med=base_med,
                stat_z=stat_res.get("robust_z"),
                bayes_p=bayes_res.get("p_value"),
                trust_result=trust_result,
                is_motion=is_motion,
                supporting=supporting,
                conflicting=conflicting,
                workflow=workflow,
                is_synthetic=is_synthetic,
            )

            record = AlertRecord(
                alert_id=self._generate_alert_id(prefix="ALT-W"),
                timestamp=ts_str,
                subject_id=subject_id,
                data_source=PATH_WEARABLE_TELEMETRY,
                measurement_name=sensor_type,
                measurement_value=float(val) if val is not None and not pd.isna(val) else None,
                measurement_unit=self._get_unit(sensor_type),
                alert_state=state,
                alert_priority=priority,
                lifecycle_status=lifecycle,
                consecutive_occurrences=consec,
                persistence_duration_seconds=duration_s,
                first_detected_timestamp=first_ts,
                last_detected_timestamp=ts_str,
                contributing_engines={
                    "Robust_Statistical_Baseline": {
                        "result": "FLAGGED" if stat_res.get("is_anomaly") else "NOMINAL",
                        "robust_z": stat_res.get("robust_z"),
                        "threshold": self.config.stat_threshold,
                        "role": "Primary Deviation Detector",
                        "included": True,
                    },
                    "Bayesian_StudentT": {
                        "result": "FLAGGED" if bayes_res.get("is_anomaly") else "NOMINAL",
                        "tail_p_value": bayes_res.get("p_value"),
                        "threshold": self.config.bayes_p_threshold,
                        "role": "Probabilistic Uncertainty Characterization",
                        "included": True,
                    },
                    "Isolation_Forest": {
                        "result": "FLAGGED" if iso_res.get("is_anomaly") else "NOMINAL",
                        "anomaly_score": iso_res.get("anomaly_score"),
                        "role": "Secondary Multivariate Pattern Analysis (Non-Triggering)",
                        "included": bool(iso_detector is not None),
                    },
                    "Sensor_Trust": {
                        "reliability_category": trust_result.get("reliability_category"),
                        "quality_score": trust_result.get("quality_score"),
                        "role": "Signal Trust & Integrity Filter",
                        "included": True,
                    },
                    "Motion_Cross_Check": {
                        "motion_correlated": is_motion,
                        "role": "Physical Movement Artifact Filter",
                        "included": accel_df is not None,
                    },
                },
                statistical_evidence=stat_res,
                bayesian_evidence=bayes_res,
                isolation_forest_evidence=iso_res,
                sensor_quality_evidence=trust_result,
                motion_artifact_evidence=motion_res,
                baseline_context=baseline_info,
                trajectory_context=trajectory_info,
                supporting_evidence=supporting,
                conflicting_evidence=conflicting,
                explanation=explanation,
                ground_medical_summary=ground_sum,
                astronaut_summary=astro_sum,
                recommended_workflow_actions=workflow,
                data_limitations=[
                    "Synthetic wearable test patterns; not actual astronaut telemetry.",
                    "Pre-flight wearable calibration window used as statistical reference.",
                ],
                interpretation_status=STATUS_SUPPORTED if state != STATE_INSUFFICIENT_DATA else STATUS_INSUFFICIENT_DATA,
                is_synthetic=is_synthetic,
            )

            # Update active alert cache
            key = f"{subject_id}::{sensor_type}"
            if state in [STATE_REVIEW, STATE_ATTENTION]:
                self.active_alerts[key] = record
            elif key in self.active_alerts and state == STATE_NORMAL:
                del self.active_alerts[key]

            self.alert_history.append(record)
            alerts.append(record)

        return alerts

    # =========================================================================
    # 4. Path B: Discrete NASA Laboratory Biomarker Evaluator
    # =========================================================================

    def evaluate_biomarker_observation(
        self,
        participant_id: str,
        biomarker_name: str,
        current_value: Optional[float],
        current_timepoint: str,
        unit: str = "",
        panel_name: str = "Unknown",
        baseline_median: Optional[float] = None,
        baseline_mad: Optional[float] = None,
        preflight_sample_count: int = 0,
        trajectory_history: Optional[List[Dict[str, Any]]] = None,
        preflight_values: Optional[Sequence[float]] = None,
    ) -> AlertRecord:
        """
        Evaluate a single discrete benchtop laboratory biomarker observation (NASA OSD-575).

        Parameters
        ----------
        participant_id : str
            Astronaut identifier (e.g. 'C001').
        biomarker_name : str
            Biomarker name.
        current_value : float or None
            Observed assay measurement.
        current_timepoint : str
            Mission timepoint (e.g. 'R+1', 'R+45').
        unit : str
            Measurement unit.
        panel_name : str
            Assay panel name.
        baseline_median : float, optional
            Preflight baseline median.
        baseline_mad : float, optional
            Preflight baseline MAD.
        preflight_sample_count : int
            Number of valid preflight samples.
        trajectory_history : list of dict, optional
            Historical postflight observations for trajectory analysis.
        preflight_values : sequence of float, optional
            Raw preflight values for Bayesian model fitting.

        Returns
        -------
        AlertRecord
            Evaluated alert decision record.
        """
        is_synthetic = False

        # 1. Statistical Baseline Evaluation
        stat_z = np.nan
        stat_is_anomaly = False
        stat_is_moderate = False

        if current_value is not None and baseline_median is not None and baseline_mad is not None:
            stat_z = calculate_robust_z_score(
                value=current_value,
                baseline_median=baseline_median,
                baseline_mad=baseline_mad,
                scale_factor=self.config.stat_mad_scale,
            )
            if not np.isnan(stat_z):
                stat_is_anomaly = bool(abs(stat_z) >= self.config.stat_threshold)
                stat_is_moderate = bool(abs(stat_z) >= self.config.stat_moderate_threshold)

        stat_res = {
            "is_anomaly": stat_is_anomaly,
            "is_moderate": stat_is_moderate,
            "robust_z": float(stat_z) if not np.isnan(stat_z) else None,
            "threshold": self.config.stat_threshold,
        }

        # 2. Bayesian Student-t Evaluation (if preflight measurements available)
        bayes_res = {"is_anomaly": False, "p_value": None, "anomaly_score": None}
        if preflight_values is not None and len(preflight_values) >= 2 and current_value is not None:
            try:
                b_det = BayesianAnomalyDetector(
                    probability_threshold=self.config.bayes_p_threshold
                ).fit(preflight_values)
                _, b_scores, b_pvals = b_det.predict([current_value])
                bayes_res = {
                    "is_anomaly": bool(b_pvals[0] < self.config.bayes_p_threshold),
                    "p_value": float(b_pvals[0]),
                    "anomaly_score": float(b_scores[0]),
                    "degrees_of_freedom": b_det.df,
                }
            except Exception as e:
                logger.debug("Bayesian fitting skipped: %s", e)

        # 3. Trajectory Context
        traj_class = "INSUFFICIENT_DATA"
        overall_trend = "INSUFFICIENT_DATA"
        if trajectory_history and baseline_median is not None:
            # Build mini series to classify trajectory
            times = [h["timepoint"] for h in trajectory_history] + [current_timepoint]
            vals = [h["value"] for h in trajectory_history] + [current_value]
            traj_df = pd.DataFrame({"timepoint": times, "value": vals})
            traj_class = classify_recovery_trajectory(traj_df, baseline_value=baseline_median)

        trajectory_info = {
            "recovery_class": traj_class,
            "overall_trend": overall_trend,
            "timepoint": current_timepoint,
        }

        baseline_info = {
            "median": baseline_median,
            "mad": baseline_mad,
            "sample_count": preflight_sample_count,
        }

        # Quality context: Discrete laboratory benchtop assays do not use wearable sensor trust
        sensor_trust_dummy = {
            "reliability_category": RELIABILITY_HIGH,
            "quality_score": 100.0,
            "is_synthetic": False,
        }

        motion_dummy = {
            "motion_correlated": False,
            "note": "Not applicable to discrete benchtop assays.",
        }

        iso_dummy = {
            "is_anomaly": False,
            "anomaly_score": None,
            "note": "Isolation Forest not applied to individual discrete 1D benchtop samples.",
        }

        # Decision Fusion
        state, priority, supporting, conflicting, workflow = self._fuse_evidence(
            value=current_value,
            stat_result=stat_res,
            bayes_result=bayes_res,
            iso_result=iso_dummy,
            sensor_trust=sensor_trust_dummy,
            motion_result=motion_dummy,
            baseline_info=baseline_info,
            trajectory_info=trajectory_info,
            is_wearable=False,
        )

        # Lifecycle Tracking
        lifecycle, consec, duration_s, first_ts = self._update_alert_lifecycle(
            subject_id=participant_id,
            measurement_name=biomarker_name,
            alert_state=state,
            timestamp_str=current_timepoint,
        )

        # Build Explanation
        explanation = self._build_biomarker_explanation(
            state=state,
            participant_id=participant_id,
            biomarker_name=biomarker_name,
            panel_name=panel_name,
            current_value=current_value,
            unit=unit,
            timepoint=current_timepoint,
            z=stat_res.get("robust_z"),
            bayes_p=bayes_res.get("p_value"),
            traj_class=traj_class,
            preflight_count=preflight_sample_count,
        )

        # Dual-Audience Summaries
        ground_sum, astro_sum = self._generate_dual_summaries(
            subject_id=participant_id,
            name=biomarker_name,
            val=current_value,
            unit=unit,
            state=state,
            priority=priority,
            base_med=baseline_median,
            stat_z=stat_res.get("robust_z"),
            bayes_p=bayes_res.get("p_value"),
            trust_result=sensor_trust_dummy,
            is_motion=False,
            supporting=supporting,
            conflicting=conflicting,
            workflow=workflow,
            is_synthetic=False,
        )

        record = AlertRecord(
            alert_id=self._generate_alert_id(prefix="ALT-B"),
            timestamp=current_timepoint,
            subject_id=participant_id,
            data_source=PATH_NASA_LABORATORY,
            measurement_name=biomarker_name,
            measurement_value=float(current_value) if current_value is not None and not pd.isna(current_value) else None,
            measurement_unit=unit,
            alert_state=state,
            alert_priority=priority,
            lifecycle_status=lifecycle,
            consecutive_occurrences=consec,
            persistence_duration_seconds=duration_s,
            first_detected_timestamp=first_ts,
            last_detected_timestamp=current_timepoint,
            contributing_engines={
                "Robust_Statistical_Baseline": {
                    "result": "FLAGGED" if stat_is_anomaly else "NOMINAL",
                    "robust_z": stat_res.get("robust_z"),
                    "threshold": self.config.stat_threshold,
                    "role": "Primary Biomarker Deviation Detector",
                    "included": True,
                },
                "Bayesian_StudentT": {
                    "result": "FLAGGED" if bayes_res.get("is_anomaly") else "NOMINAL",
                    "tail_p_value": bayes_res.get("p_value"),
                    "threshold": self.config.bayes_p_threshold,
                    "role": "Probabilistic Uncertainty Characterization",
                    "included": bayes_res.get("p_value") is not None,
                },
                "Longitudinal_Trajectory": {
                    "recovery_class": traj_class,
                    "role": "Postflight Homeostatic Trend Classification",
                    "included": bool(trajectory_history),
                },
            },
            statistical_evidence=stat_res,
            bayesian_evidence=bayes_res,
            isolation_forest_evidence=iso_dummy,
            sensor_quality_evidence={"note": "NASA OSD-575 discrete benchtop laboratory assay."},
            motion_artifact_evidence={"note": "Not applicable to discrete laboratory assays."},
            baseline_context=baseline_info,
            trajectory_context=trajectory_info,
            supporting_evidence=supporting,
            conflicting_evidence=conflicting,
            explanation=explanation,
            ground_medical_summary=ground_sum,
            astronaut_summary=astro_sum,
            recommended_workflow_actions=workflow,
            data_limitations=[
                "NASA OSD-575 Inspiration4 mission sample size is N=4 astronauts.",
                "Discrete benchtop laboratory measurements, NOT continuous telemetry.",
                "Pre-flight baseline derived from 2 to 3 preflight research timepoints.",
            ],
            interpretation_status=STATUS_SUPPORTED if state != STATE_INSUFFICIENT_DATA else STATUS_INSUFFICIENT_DATA,
            is_synthetic=False,
        )

        key = f"{participant_id}::{biomarker_name}"
        if state in [STATE_REVIEW, STATE_ATTENTION]:
            self.active_alerts[key] = record
        elif key in self.active_alerts and state == STATE_NORMAL:
            del self.active_alerts[key]

        self.alert_history.append(record)
        return record

    # =========================================================================
    # 5. Generic Dispatcher: evaluate_observation
    # =========================================================================

    def evaluate_observation(self, observation_data: Dict[str, Any]) -> AlertRecord:
        """
        Unified observation evaluation dispatcher routing to Path A or Path B.

        Parameters
        ----------
        observation_data : dict
            Observation metadata dictionary.

        Returns
        -------
        AlertRecord
            Evaluated alert record.
        """
        is_synth = observation_data.get("is_synthetic", False)
        source = observation_data.get("data_source", "")

        if is_synth or "wearable" in source.lower() or observation_data.get("sensor_type") in [SENSOR_HEART_RATE, SENSOR_SPO2, SENSOR_ACCELEROMETER]:
            # Wearable single point evaluation
            s_type = observation_data.get("sensor_type") or observation_data.get("measurement_name", "heart_rate")
            val = observation_data.get("signal_value") or observation_data.get("measurement_value")
            ts = observation_data.get("timestamp", datetime.now(timezone.utc).isoformat())
            df_single = pd.DataFrame({
                "timestamp": [pd.to_datetime(ts)],
                "sensor_type": [s_type],
                "signal_value": [val],
                "scenario": [observation_data.get("scenario", "NORMAL")],
                "signal_status": [observation_data.get("signal_status", "VALID")],
                "is_synthetic": [True],
            })
            records = self.evaluate_sensor_stream(
                stream_df=df_single,
                sensor_type=s_type,
                subject_id=observation_data.get("subject_id", "Synthetic_Subject"),
            )
            return records[0]
        else:
            # Discrete laboratory biomarker evaluation
            return self.evaluate_biomarker_observation(
                participant_id=observation_data.get("subject_id") or observation_data.get("participant_id", "C001"),
                biomarker_name=observation_data.get("measurement_name") or observation_data.get("biomarker_name", "Unknown"),
                current_value=observation_data.get("measurement_value") or observation_data.get("value"),
                current_timepoint=observation_data.get("timepoint") or observation_data.get("timestamp", "R+1"),
                unit=observation_data.get("unit") or observation_data.get("measurement_unit", ""),
                panel_name=observation_data.get("panel_name", "General"),
                baseline_median=observation_data.get("baseline_median"),
                baseline_mad=observation_data.get("baseline_mad"),
                preflight_sample_count=observation_data.get("preflight_sample_count", 3),
            )

    # =========================================================================
    # 6. Integrated State Evaluation
    # =========================================================================

    def evaluate_integrated_state(
        self,
        subject_id: str,
        alerts: Optional[List[AlertRecord]] = None,
    ) -> IntegratedStateSummary:
        """
        Aggregate active alerts across all monitoring streams to produce an overall mission overview.

        Parameters
        ----------
        subject_id : str
            Crew member / subject identifier.
        alerts : list of AlertRecord, optional
            List of alerts to aggregate. If None, uses active alerts from internal registry.

        Returns
        -------
        IntegratedStateSummary
            Aggregated state summary.
        """
        target_alerts = alerts if alerts is not None else [
            a for a in self.active_alerts.values() if a.subject_id == subject_id
        ]

        normal_cnt = sum(1 for a in target_alerts if a.alert_state == STATE_NORMAL)
        review_cnt = sum(1 for a in target_alerts if a.alert_state == STATE_REVIEW)
        att_cnt = sum(1 for a in target_alerts if a.alert_state == STATE_ATTENTION)
        insufficient_cnt = sum(1 for a in target_alerts if a.alert_state == STATE_INSUFFICIENT_DATA)

        # Determine highest operational state
        if att_cnt > 0:
            highest_state = STATE_ATTENTION
            highest_pri = PRIORITY_HIGH
            guidance = (
                f"ATTENTION: {att_cnt} parameter(s) demonstrate concordant multi-engine statistical departure. "
                "Flight surgeon console review requested per standard mission protocol."
            )
        elif review_cnt > 0:
            highest_state = STATE_REVIEW
            highest_pri = PRIORITY_MEDIUM
            guidance = (
                f"REVIEW: {review_cnt} parameter(s) flagged for routine inspection. Verify sensor signal "
                "and cross-check with flight surgeon console during next communications window."
            )
        elif insufficient_cnt > 0:
            highest_state = STATE_INSUFFICIENT_DATA
            highest_pri = PRIORITY_INFO
            guidance = (
                f"INSUFFICIENT DATA: {insufficient_cnt} stream(s) unrecorded or degraded. Check sensor fit "
                "and telemetry packet transmission."
            )
        else:
            highest_state = STATE_NORMAL
            highest_pri = PRIORITY_NOMINAL
            guidance = "NOMINAL: All active monitoring streams align within expected baseline bounds."

        is_synth = any(a.is_synthetic for a in target_alerts) if target_alerts else True

        return IntegratedStateSummary(
            subject_id=subject_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data_source=PATH_WEARABLE_TELEMETRY if is_synth else PATH_NASA_LABORATORY,
            highest_operational_state=highest_state,
            highest_priority=highest_pri,
            active_alert_count=review_cnt + att_cnt,
            normal_count=normal_cnt,
            review_count=review_cnt,
            attention_count=att_cnt,
            insufficient_data_count=insufficient_cnt,
            active_alerts=[
                a.to_dict() for a in target_alerts
                if a.alert_state in {STATE_REVIEW, STATE_ATTENTION}
            ],
            operational_guidance=guidance,
            is_synthetic=is_synth,
        )

    # =========================================================================
    # 7. Alert History & Audit Logging
    # =========================================================================

    def generate_alert_history(
        self,
        filter_by_state: Optional[str] = None,
        filter_by_subject: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve complete, auditable alert history with optional filtering.

        Parameters
        ----------
        filter_by_state : str, optional
            Filter by alert state ('NORMAL', 'REVIEW', 'ATTENTION', 'INSUFFICIENT_DATA').
        filter_by_subject : str, optional
            Filter by astronaut / subject ID.

        Returns
        -------
        List[Dict[str, Any]]
            JSON-serializable historical alert records.
        """
        recs = self.alert_history
        if filter_by_state:
            recs = [r for r in recs if r.alert_state == filter_by_state]
        if filter_by_subject:
            recs = [r for r in recs if r.subject_id == filter_by_subject]

        return [r.to_dict() for r in recs]

    # =========================================================================
    # 8. Helper & Explanation Builders
    # =========================================================================

    def _get_unit(self, name: str) -> str:
        units = {
            SENSOR_HEART_RATE: "bpm",
            SENSOR_SPO2: "%",
            SENSOR_ACCELEROMETER: "g",
        }
        return units.get(name, "")

    def _build_stream_explanation(
        self,
        state: str,
        sensor_type: str,
        val: Optional[float],
        z: Optional[float],
        bayes_p: Optional[float],
        is_motion: bool,
        trust_result: Dict[str, Any],
        lifecycle: str,
        duration_s: float,
    ) -> str:
        if val is None or pd.isna(val):
            return f"INSUFFICIENT_DATA: {sensor_type.replace('_', ' ').title()} stream reading was missing or unrecorded."

        rel_cat = trust_result.get("reliability_category", "HIGH_RELIABILITY")
        score = trust_result.get("quality_score", 100.0)

        parts = [f"{state}: {sensor_type.replace('_', ' ').title()} reading is {val:.1f} {self._get_unit(sensor_type)}."]

        if z is not None and not np.isnan(z):
            parts.append(f"Robust Z-score deviation: {z:+.2f} (Threshold: ±{self.config.stat_threshold:.1f}).")

        if bayes_p is not None and not np.isnan(bayes_p):
            parts.append(f"Bayesian predictive tail probability: p = {bayes_p:.4e}.")

        if is_motion:
            parts.append("Accelerometer detected concurrent movement (|a - 1g| > 0.4g); optical motion artifact suspected.")

        if rel_cat != RELIABILITY_HIGH:
            parts.append(f"Sensor trust indicates {rel_cat} ({score:.1f}/100.0).")

        if lifecycle in [LIFECYCLE_ACTIVE, LIFECYCLE_PERSISTENT]:
            parts.append(f"Alert lifecycle status: {lifecycle} (Duration: {duration_s:.1f}s).")

        return " ".join(parts)

    def _build_biomarker_explanation(
        self,
        state: str,
        participant_id: str,
        biomarker_name: str,
        panel_name: str,
        current_value: Optional[float],
        unit: str,
        timepoint: str,
        z: Optional[float],
        bayes_p: Optional[float],
        traj_class: str,
        preflight_count: int,
    ) -> str:
        if current_value is None or pd.isna(current_value):
            return f"INSUFFICIENT_DATA: {biomarker_name} measurement at {timepoint} was unrecorded or missing."

        parts = [
            f"{state}: Astronaut {participant_id} {biomarker_name} ({panel_name}) measured {current_value} {unit} at {timepoint}."
        ]

        if z is not None and not np.isnan(z):
            parts.append(f"Robust Z-score deviation from preflight baseline: {z:+.2f} (Threshold: ±{self.config.stat_threshold:.1f}).")

        if bayes_p is not None and not np.isnan(bayes_p):
            parts.append(f"Bayesian posterior predictive tail probability: p = {bayes_p:.4e}.")

        if traj_class != "INSUFFICIENT_DATA":
            parts.append(f"Postflight longitudinal trajectory: {traj_class}.")

        parts.append(f"Baseline established on {preflight_count} preflight research samples.")
        return " ".join(parts)

    def _generate_dual_summaries(
        self,
        subject_id: str,
        name: str,
        val: Optional[float],
        unit: str,
        state: str,
        priority: str,
        base_med: Optional[float],
        stat_z: Optional[float],
        bayes_p: Optional[float],
        trust_result: Dict[str, Any],
        is_motion: bool,
        supporting: List[str],
        conflicting: List[str],
        workflow: List[str],
        is_synthetic: bool,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        # Ground Medical Briefing
        ground_sum = {
            "format": "GROUND_MEDICAL_TECHNICAL",
            "subject_id": subject_id,
            "measurement": name,
            "observed_value": val,
            "unit": unit,
            "operational_state": state,
            "priority": priority,
            "baseline_median": base_med,
            "robust_z_score": stat_z,
            "bayesian_p_value": bayes_p,
            "sensor_reliability": trust_result.get("reliability_category", "N/A"),
            "motion_overlap": is_motion,
            "supporting_evidence": supporting,
            "conflicting_evidence": conflicting,
            "operational_review_actions": workflow,
            "is_synthetic": is_synthetic,
        }

        # Astronaut Summary (Calm, Plain Language, Zero Medical Diagnosis)
        if val is None or pd.isna(val):
            crew_msg = f"A reading for {name.replace('_', ' ')} is currently missing or unrecorded."
        elif state == STATE_NORMAL:
            crew_msg = f"Your current {name.replace('_', ' ')} reading is {val:.1f} {unit}, which aligns closely with your baseline reference range."
        elif state == STATE_REVIEW:
            if is_motion:
                crew_msg = f"Your {name.replace('_', ' ')} reading showed a brief shift that coincided with physical movement. Please verify that your sensor is snugly positioned."
            else:
                crew_msg = f"Your {name.replace('_', ' ')} reading differed slightly from your baseline. Ground medical console has logged this for standard mission review."
        elif state == STATE_ATTENTION:
            crew_msg = f"A distinct departure from your baseline was recorded for {name.replace('_', ' ')}. Please check in with your flight surgeon during the next scheduled communications pass."
        else:
            crew_msg = f"Sensor signal for {name.replace('_', ' ')} could not be verified. Please check that the sensor is securely attached."

        astronaut_sum = {
            "format": "ASTRONAUT_CREW_GUIDANCE",
            "parameter": name.replace("_", " ").title(),
            "crew_message": crew_msg,
            "signal_reliable": trust_result.get("reliability_category") in [RELIABILITY_HIGH, RELIABILITY_MODERATE],
            "sensor_check_suggested": is_motion or trust_result.get("reliability_category") not in [RELIABILITY_HIGH, RELIABILITY_MODERATE],
            "medical_console_contact_suggested": state == STATE_ATTENTION,
            "is_synthetic": is_synthetic,
        }

        return ground_sum, astronaut_sum
