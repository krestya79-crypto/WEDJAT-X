"""
WEDJAT-X Scientific Interpretation Engine
NASA Space Apps Challenge - Astronaut Health Monitoring Prototype

This module translates sensor trust findings, personalized baseline deviations,
statistical anomaly detections, and longitudinal trajectories into evidence-based,
scientifically conservative decision-support reports.

It produces two distinct report formats:
1. Ground Medical Team Briefing: Professional, quantitative, evidence-traceable 7-section report.
2. Astronaut Crew Summary: Clear, concise, non-alarming, non-prescriptive, jargon-free summary.

IMPORTANT SCIENTIFIC & ETHICAL NOTICE:
--------------------------------------
This software is NOT a certified diagnostic medical device. It does NOT diagnose diseases,
predict pathologies, or recommend medications, therapies, or clinical interventions.
All recommendations are strictly operational workflow actions (e.g. REVIEW_MEASUREMENT,
VERIFY_SENSOR_SIGNAL) for aerospace medical operations.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd

from intelligence.baseline import DISCLAIMER_TEXT
from intelligence.anomaly import ETHICAL_MEDICAL_DISCLAIMER, AnomalyResult
from intelligence.sensor_trust import (
    RELIABILITY_HIGH,
    RELIABILITY_MODERATE,
    RELIABILITY_LOW,
    RELIABILITY_UNRELIABLE,
    RELIABILITY_INSUFFICIENT,
)

logger = logging.getLogger("WEDJAT_X.ScientificInterpretation")

# Allowed Operational Workflow Flags (strictly non-prescriptive)
WORKFLOW_REVIEW_MEASUREMENT = "REVIEW_MEASUREMENT"
WORKFLOW_VERIFY_SENSOR = "VERIFY_SENSOR_SIGNAL"
WORKFLOW_REPEAT_MEASUREMENT = "REPEAT_MEASUREMENT_IF_OPERATIONALLY_APPROPRIATE"
WORKFLOW_REQUEST_MEDICAL_REVIEW = "REQUEST_MEDICAL_REVIEW"
WORKFLOW_INSUFFICIENT_DATA = "INSUFFICIENT_DATA_FOR_INTERPRETATION"
WORKFLOW_NO_ADDITIONAL_REVIEW = "NO_ADDITIONAL_REVIEW_FLAGGED"

PERMITTED_WORKFLOW_FLAGS: List[str] = [
    WORKFLOW_REVIEW_MEASUREMENT,
    WORKFLOW_VERIFY_SENSOR,
    WORKFLOW_REPEAT_MEASUREMENT,
    WORKFLOW_REQUEST_MEDICAL_REVIEW,
    WORKFLOW_INSUFFICIENT_DATA,
    WORKFLOW_NO_ADDITIONAL_REVIEW,
]

# Interpretation Evidentiary Status
STATUS_SUPPORTED = "SUPPORTED"
STATUS_LIMITED = "LIMITED"
STATUS_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ScientificInterpreter:
    """
    Translates analytical outputs into professional, evidence-based interpretation reports
    for aerospace flight surgeons and astronaut crew members.
    """

    def __init__(self, disclaimer: Optional[str] = None) -> None:
        """Initialize interpreter with non-clinical disclaimer."""
        self.disclaimer = disclaimer or DISCLAIMER_TEXT

    # =========================================================================
    # 1. Component Interpreters
    # =========================================================================

    def interpret_sensor_quality(
        self,
        trust_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Interpret sensor trust findings into evidentiary statements.

        Parameters
        ----------
        trust_result : dict
            Output from SensorTrustEngine.evaluate_sensor().

        Returns
        -------
        dict
            Interpreted sensor reliability metrics and observations.
        """
        sensor = trust_result.get("sensor_type", "Unknown")
        score = trust_result.get("quality_score")
        category = trust_result.get("reliability_category", RELIABILITY_INSUFFICIENT)
        issues = trust_result.get("detected_issues", [])
        is_synth = trust_result.get("is_synthetic", False)

        is_reliable = category in [RELIABILITY_HIGH, RELIABILITY_MODERATE]

        statements: List[str] = []
        if is_synth:
            statements.append("Source: Synthetic test stream (software test pattern).")
        else:
            statements.append("Source: Sensor telemetry stream.")

        if category == RELIABILITY_HIGH:
            statements.append(f"Sensor signal quality is high ({score:.1f}/100.0) with minimal noise and intact continuity.")
        elif category == RELIABILITY_MODERATE:
            statements.append(f"Sensor signal quality is acceptable ({score:.1f}/100.0) but minor noise or intermittent dropouts were noted.")
        elif category == RELIABILITY_LOW:
            statements.append(f"Sensor signal quality is degraded ({score:.1f}/100.0). Measurement reliability is reduced.")
        elif category == RELIABILITY_UNRELIABLE:
            statements.append(f"Sensor signal is unreliable ({score:.1f}/100.0) due to severe artifacts, disconnects, or packet loss.")
        else:
            statements.append("Insufficient data available to evaluate sensor signal trust.")

        if trust_result.get("motion_overlap_count", 0) > 0:
            statements.append(
                f"Motion artifact correlation: {trust_result['motion_overlap_count']} optical artifacts "
                f"({trust_result['motion_overlap_pct']:.1f}%) coincide with accelerometer activity."
            )

        return {
            "sensor_type": sensor,
            "quality_score": score,
            "reliability_category": category,
            "is_reliable": is_reliable,
            "missing_data_rate": trust_result.get("missing_rate"),
            "disconnection_rate": trust_result.get("disconnection_rate"),
            "noise_metric": trust_result.get("noise_metric"),
            "spike_count": trust_result.get("spike_count", 0),
            "drift_detected": trust_result.get("drift_detected", False),
            "timestamp_gap_count": trust_result.get("timestamp_gap_count", 0),
            "motion_interference": trust_result.get("motion_overlap_count", 0) > 0,
            "interpretation_statements": statements,
            "detected_issues": issues,
            "is_synthetic": is_synth,
        }

    def interpret_baseline(
        self,
        biomarker_name: str,
        current_value: Optional[float],
        baseline_median: Optional[float],
        baseline_mad: Optional[float],
        n_baseline: int,
        unit: str = "",
        participant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate a single measurement against individual preflight baseline.

        Parameters
        ----------
        biomarker_name : str
            Biomarker or sensor signal name.
        current_value : float or None
            Observed measurement value.
        baseline_median : float or None
            Preflight median baseline.
        baseline_mad : float or None
            Preflight MAD.
        n_baseline : int
            Number of preflight research samples.
        unit : str, default=''
            Measurement unit.
        participant_id : str, optional
            Astronaut identifier.

        Returns
        -------
        dict
            Baseline comparison dictionary.
        """
        p_str = f"Participant {participant_id} | " if participant_id else ""

        if current_value is None or pd.isna(current_value):
            return {
                "biomarker_name": biomarker_name,
                "current_measurement": None,
                "unit": unit,
                "personalized_baseline_median": baseline_median,
                "absolute_difference": None,
                "percentage_difference": None,
                "direction_of_change": "UNDEFINED",
                "baseline_sample_count": n_baseline,
                "summary": f"{p_str}{biomarker_name}: Measurement value is missing.",
            }

        if baseline_median is None or pd.isna(baseline_median) or n_baseline == 0:
            return {
                "biomarker_name": biomarker_name,
                "current_measurement": current_value,
                "unit": unit,
                "personalized_baseline_median": None,
                "absolute_difference": None,
                "percentage_difference": None,
                "direction_of_change": "UNDEFINED",
                "baseline_sample_count": n_baseline,
                "summary": f"{p_str}{biomarker_name}: Observed {current_value:.4g} {unit}, but no preflight baseline is available (n=0).",
            }

        delta = current_value - baseline_median
        if baseline_median != 0:
            pct_change = (delta / abs(baseline_median)) * 100.0
            pct_str = f"{pct_change:+.1f}%"
        else:
            pct_change = 0.0 if delta == 0 else None
            pct_str = "undefined (zero baseline)"

        if np.isclose(delta, 0.0, atol=1e-7):
            direction = "UNCHANGED"
        elif delta > 0:
            direction = "ELEVATED"
        else:
            direction = "SUPPRESSED"

        summary = (
            f"{p_str}{biomarker_name}: Observed {current_value:.4g} {unit} vs Baseline median {baseline_median:.4g} {unit} "
            f"(Delta: {delta:+.4g} {unit}, {pct_str}; n={n_baseline} preflight samples)."
        )

        return {
            "biomarker_name": biomarker_name,
            "current_measurement": current_value,
            "unit": unit,
            "personalized_baseline_median": baseline_median,
            "absolute_difference": delta,
            "percentage_difference": pct_change,
            "direction_of_change": direction,
            "baseline_sample_count": n_baseline,
            "summary": summary,
        }

    def interpret_anomaly(
        self,
        anomaly_result: Union[Dict[str, Any], AnomalyResult],
    ) -> Dict[str, Any]:
        """
        Translate anomaly detector output into statistical interpretation.

        Parameters
        ----------
        anomaly_result : dict or AnomalyResult
            Output from AnomalyDetector.evaluate_observation().

        Returns
        -------
        dict
            Statistical interpretation block.
        """
        res = anomaly_result.to_dict() if isinstance(anomaly_result, AnomalyResult) else dict(anomaly_result)

        flag = res.get("anomaly_flag", "NOMINAL")
        z = res.get("robust_z_score")
        base_mad = res.get("baseline_mad")
        threshold = 3.0

        is_anomaly = flag in ["SIGNIFICANT_ELEVATION", "SIGNIFICANT_SUPPRESSION", "STATISTICAL_ELEVATION", "STATISTICAL_SUPPRESSION"]
        is_moderate = flag in ["MODERATE_ELEVATION", "MODERATE_SUPPRESSION"]

        if z is not None and not pd.isna(z):
            z_str = f"{z:+.2f}"
            threshold_exceeded = bool(abs(z) >= threshold)
        else:
            z_str = "N/A"
            threshold_exceeded = False

        statements = [
            f"Detection method: Boris Iglewicz & Hoaglin Modified Z-score (Scale factor 1.4826).",
            f"Threshold: +/-{threshold:.1f}. Robust Z-score: {z_str}.",
            f"Statistical classification: {flag}.",
        ]

        if is_anomaly:
            statements.append("Statistical deviation exceeds significant threshold. Physiological response departure noted.")
        elif is_moderate:
            statements.append("Moderate statistical departure observed within secondary monitoring bounds.")
        elif flag == "NOMINAL":
            statements.append("Observation falls within expected personalized baseline dispersion.")

        return {
            "robust_z_score": z,
            "baseline_mad": base_mad,
            "detection_method": "Boris Iglewicz & Hoaglin Robust Z-score (MAD x 1.4826)",
            "threshold_used": threshold,
            "threshold_exceeded": threshold_exceeded,
            "statistical_flag": flag,
            "is_anomaly": is_anomaly,
            "is_moderate_deviation": is_moderate,
            "statements": statements,
        }

    def interpret_trajectory(
        self,
        trajectory_row: Union[Dict[str, Any], pd.Series],
    ) -> Dict[str, Any]:
        """
        Interpret longitudinal trajectory and recovery dynamics.

        Parameters
        ----------
        trajectory_row : dict or pd.Series
            Trajectory summary row from LongitudinalTrajectoryEngine.

        Returns
        -------
        dict
            Longitudinal interpretation block.
        """
        row = dict(trajectory_row)

        rec_class = str(row.get("Postflight_Recovery_Class", "INSUFFICIENT_DATA"))
        overall_trend = str(row.get("Overall_Trend", "INSUFFICIENT_DATA"))
        biomarker = str(row.get("Biomarker_Name", "Unknown"))
        panel = str(row.get("Panel_Name", "Unknown"))

        warnings: List[str] = []
        if rec_class == "INSUFFICIENT_DATA":
            warnings.append("Insufficient longitudinal timepoints available to establish postflight trajectory.")

        fluctuation_info = "Nominal trajectory stability."
        if rec_class == "FLUCTUATING" or overall_trend == "FLUCTUATING":
            fluctuation_info = "Multi-phase non-monotonic fluctuation observed across postflight recovery timepoints."

        # Reconstruct previous measurements
        prev_measurements = []
        for tp in ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82", "R+194"]:
            val_key = f"{tp}_Value"
            if val_key in row and row[val_key] is not None and not pd.isna(row[val_key]):
                prev_measurements.append({"timepoint": tp, "value": float(row[val_key])})

        return {
            "biomarker_name": biomarker,
            "panel_name": panel,
            "trajectory_status": rec_class,
            "overall_trend": overall_trend,
            "fluctuation_information": fluctuation_info,
            "previous_measurements": prev_measurements,
            "insufficient_timepoint_warnings": warnings,
            "explanation": str(row.get("Trajectory_Explanation", "")),
        }

    # =========================================================================
    # 2. Ground Medical Team Report Generator
    # =========================================================================

    def generate_ground_report(
        self,
        observation: Dict[str, Any],
        baseline_comparison: Optional[Dict[str, Any]] = None,
        statistical_interpretation: Optional[Dict[str, Any]] = None,
        longitudinal_interpretation: Optional[Dict[str, Any]] = None,
        sensor_quality: Optional[Dict[str, Any]] = None,
        data_limitations: Optional[List[str]] = None,
        is_synthetic: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate a professional 7-section Ground Medical Team evidence report.

        Parameters
        ----------
        observation : dict
            Observation details (name, value, unit, timestamp/timepoint, participant_id).
        baseline_comparison : dict, optional
            Output from interpret_baseline().
        statistical_interpretation : dict, optional
            Output from interpret_anomaly().
        longitudinal_interpretation : dict, optional
            Output from interpret_trajectory().
        sensor_quality : dict, optional
            Output from interpret_sensor_quality().
        data_limitations : list of str, optional
            Known limitations or missing data points.
        is_synthetic : bool, default=False
            Whether the underlying data is synthetic test stream.

        Returns
        -------
        dict
            Complete Ground Medical Team report dictionary conforming to Part 6 schema.
        """
        base_comp = baseline_comparison or {}
        stat_interp = statistical_interpretation or {}
        long_interp = longitudinal_interpretation or {}
        sens_qual = sensor_quality or {}
        limitations = list(data_limitations or [])

        # Gather evidence items
        evidence: List[str] = []

        if observation.get("value") is not None and not pd.isna(observation.get("value")):
            evidence.append(
                f"Observed value: {observation['value']} {observation.get('unit', '')} "
                f"at {observation.get('timestamp_or_timepoint', 'N/A')}."
            )
        else:
            evidence.append("Observed measurement value is missing or unrecorded.")

        if base_comp.get("personalized_baseline_median") is not None:
            pct_val = base_comp.get("percentage_difference")
            pct_str = f" ({pct_val:+.1f}%)" if pct_val is not None and not pd.isna(pct_val) else ""
            evidence.append(
                f"Personalized preflight baseline: {base_comp['personalized_baseline_median']} "
                f"(n={base_comp.get('baseline_sample_count', 0)} samples). "
                f"Direction: {base_comp.get('direction_of_change', 'N/A')}{pct_str}."
            )
        else:
            limitations.append("Personalized preflight baseline is unavailable.")

        if stat_interp.get("robust_z_score") is not None:
            evidence.append(
                f"Robust Z-score: {stat_interp['robust_z_score']:+.2f} "
                f"(Threshold: {stat_interp.get('threshold_used', 3.0)}). "
                f"Flag: {stat_interp.get('statistical_flag', 'NOMINAL')}."
            )

        if long_interp.get("trajectory_status"):
            evidence.append(
                f"Longitudinal trajectory class: {long_interp['trajectory_status']} "
                f"(Overall Trend: {long_interp.get('overall_trend', 'N/A')})."
            )

        if sens_qual.get("quality_score") is not None:
            evidence.append(
                f"Sensor quality score: {sens_qual['quality_score']:.1f}/100.0 "
                f"({sens_qual.get('reliability_category', 'N/A')})."
            )
            if sens_qual.get("motion_interference"):
                evidence.append("Temporal overlap observed between optical signal artifacts and accelerometer motion.")

        # Determine non-prescriptive recommended review actions
        workflow_actions: List[str] = self._determine_workflow_actions(
            observation=observation,
            base_comp=base_comp,
            stat_interp=stat_interp,
            long_interp=long_interp,
            sens_qual=sens_qual,
        )

        # Determine evidentiary status
        if observation.get("value") is None or pd.isna(observation.get("value")):
            status = STATUS_INSUFFICIENT_DATA
        elif sens_qual.get("reliability_category") in [RELIABILITY_UNRELIABLE, RELIABILITY_INSUFFICIENT]:
            status = STATUS_INSUFFICIENT_DATA
        elif base_comp.get("baseline_sample_count", 0) < 2 or stat_interp.get("robust_z_score") is None:
            status = STATUS_LIMITED
        else:
            status = STATUS_SUPPORTED

        report = {
            "report_type": "GROUND_MEDICAL",
            "observation": observation,
            "baseline_comparison": base_comp,
            "statistical_interpretation": stat_interp,
            "longitudinal_interpretation": long_interp,
            "signal_quality": sens_qual,
            "evidence": evidence,
            "data_limitations": limitations,
            "recommended_review_action": workflow_actions,
            "interpretation_status": status,
            "is_synthetic": is_synthetic,
            "disclaimer": self.disclaimer,
        }
        return report

    # =========================================================================
    # 3. Astronaut-Friendly Report Generator
    # =========================================================================

    def generate_astronaut_report(
        self,
        observation: Dict[str, Any],
        baseline_comparison: Optional[Dict[str, Any]] = None,
        statistical_interpretation: Optional[Dict[str, Any]] = None,
        longitudinal_interpretation: Optional[Dict[str, Any]] = None,
        sensor_quality: Optional[Dict[str, Any]] = None,
        is_synthetic: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate clear, concise, non-alarming briefing for an astronaut crew member.

        Parameters
        ----------
        observation : dict
            Observation metadata.
        baseline_comparison : dict, optional
            Baseline comparison dict.
        statistical_interpretation : dict, optional
            Anomaly result dict.
        longitudinal_interpretation : dict, optional
            Trajectory dict.
        sensor_quality : dict, optional
            Sensor trust dict.
        is_synthetic : bool, default=False
            Whether data is synthetic test stream.

        Returns
        -------
        dict
            Crew-facing report dictionary with plain-language summary and actionable steps.
        """
        base_comp = baseline_comparison or {}
        stat_interp = statistical_interpretation or {}
        long_interp = longitudinal_interpretation or {}
        sens_qual = sensor_quality or {}

        name = observation.get("name", "Monitoring Signal")
        val = observation.get("value")
        unit = observation.get("unit", "")
        direction = base_comp.get("direction_of_change", "UNCHANGED")
        rel_cat = sens_qual.get("reliability_category", RELIABILITY_HIGH)
        traj = long_interp.get("trajectory_status", "STABLE")

        synth_prefix = "[SYNTHETIC TEST SIMULATION] " if is_synthetic else ""

        # What the system observed
        if val is None or pd.isna(val):
            observed_summary = f"{synth_prefix}A measurement for {name} is currently missing or unrecorded."
        else:
            observed_summary = f"{synth_prefix}Your current {name} reading is {val:.4g} {unit}."

        # Sensor reliability
        if rel_cat == RELIABILITY_HIGH:
            sensor_status_msg = "The sensor signal is clear and reliable."
            verify_suggested = False
        elif rel_cat == RELIABILITY_MODERATE:
            sensor_status_msg = "The sensor signal is acceptable, with occasional minor noise or brief gaps."
            verify_suggested = False
        elif rel_cat in [RELIABILITY_LOW, RELIABILITY_UNRELIABLE]:
            sensor_status_msg = "The sensor signal is degraded or irregular. Sensor contact may be loose."
            verify_suggested = True
        else:
            sensor_status_msg = "Sensor signal quality could not be determined."
            verify_suggested = True

        # Baseline comparison
        if base_comp.get("personalized_baseline_median") is None:
            baseline_msg = "A preflight reference baseline is not yet established for comparison."
        elif direction == "ELEVATED":
            baseline_msg = f"This reading is higher than your preflight reference baseline."
        elif direction == "SUPPRESSED":
            baseline_msg = f"This reading is lower than your preflight reference baseline."
        else:
            baseline_msg = "This reading aligns closely with your preflight reference baseline."

        # Trajectory & pattern
        if traj == "APPROACHING_BASELINE":
            pattern_msg = "The overall trend shows a steady return toward your baseline reference."
        elif traj == "MOVING_AWAY_FROM_BASELINE":
            pattern_msg = "The overall trend shows a gradual change away from your baseline reference."
        elif traj == "FLUCTUATING":
            pattern_msg = "The readings have shown natural variations over recent check-ins."
        else:
            pattern_msg = "The readings have remained consistent over recent check-ins."

        # Motion context
        if sens_qual.get("motion_interference"):
            motion_msg = "Some signal irregularities coincided with physical movement, which can naturally alter sensor contact."
        else:
            motion_msg = ""

        # Contact medical team guidance
        is_significant_anomaly = stat_interp.get("is_anomaly", False)
        if is_significant_anomaly and rel_cat == RELIABILITY_HIGH:
            contact_team = True
            action_guidance = (
                "A notable statistical shift was observed. Please verify sensor placement and check in with "
                "your mission medical team during the next routine communications window as per standard protocol."
            )
        elif verify_suggested:
            contact_team = False
            action_guidance = (
                "Please verify that your sensor is snugly positioned and clean. No medical action is required."
            )
        else:
            contact_team = False
            action_guidance = "Everything looks nominal. Continue standard mission monitoring procedures."

        # Plain language crew narrative
        narrative_parts = [observed_summary, sensor_status_msg, baseline_msg, pattern_msg]
        if motion_msg:
            narrative_parts.append(motion_msg)
        narrative_parts.append(action_guidance)
        crew_narrative = " ".join(narrative_parts)

        return {
            "report_type": "ASTRONAUT_FRIENDLY",
            "biomarker_or_sensor": name,
            "crew_narrative": crew_narrative,
            "signal_appears_reliable": rel_cat in [RELIABILITY_HIGH, RELIABILITY_MODERATE],
            "differs_from_baseline": direction in ["ELEVATED", "SUPPRESSED"],
            "pattern_description": pattern_msg,
            "sensor_verification_suggested": verify_suggested,
            "contact_medical_team_suggested": contact_team,
            "action_guidance": action_guidance,
            "is_synthetic": is_synthetic,
            "notice": (
                "Research decision-support output only. Not a medical diagnosis. "
                "Always adhere to mission flight surgeon instructions."
            ),
        }

    # =========================================================================
    # 4. Integrated Interpretation Generator (Part 6 Schema)
    # =========================================================================

    def generate_integrated_interpretation(
        self,
        observation: Dict[str, Any],
        baseline_comparison: Optional[Dict[str, Any]] = None,
        statistical_interpretation: Optional[Dict[str, Any]] = None,
        longitudinal_interpretation: Optional[Dict[str, Any]] = None,
        sensor_quality: Optional[Dict[str, Any]] = None,
        data_limitations: Optional[List[str]] = None,
        is_synthetic: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate complete integrated interpretation JSON-serializable output conforming
        strictly to the Part 6 schema.
        """
        return self.generate_ground_report(
            observation=observation,
            baseline_comparison=baseline_comparison,
            statistical_interpretation=statistical_interpretation,
            longitudinal_interpretation=longitudinal_interpretation,
            sensor_quality=sensor_quality,
            data_limitations=data_limitations,
            is_synthetic=is_synthetic,
        )

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _determine_workflow_actions(
        self,
        observation: Dict[str, Any],
        base_comp: Dict[str, Any],
        stat_interp: Dict[str, Any],
        long_interp: Dict[str, Any],
        sens_qual: Dict[str, Any],
    ) -> List[str]:
        """Determine non-prescriptive operational workflow flags."""
        actions: List[str] = []

        val = observation.get("value")
        rel_cat = sens_qual.get("reliability_category")
        is_anomaly = stat_interp.get("is_anomaly", False)
        is_mod = stat_interp.get("is_moderate_deviation", False)
        traj = long_interp.get("trajectory_status")

        # Missing or disconnected data
        if val is None or pd.isna(val) or rel_cat == RELIABILITY_INSUFFICIENT:
            actions.append(WORKFLOW_INSUFFICIENT_DATA)
            if sens_qual.get("disconnection_rate", 0) > 0:
                actions.append(WORKFLOW_VERIFY_SENSOR)
            return actions

        # Unreliable or low-quality sensor
        if rel_cat in [RELIABILITY_UNRELIABLE, RELIABILITY_LOW] or sens_qual.get("motion_interference"):
            actions.append(WORKFLOW_VERIFY_SENSOR)
            actions.append(WORKFLOW_REVIEW_MEASUREMENT)
            return actions

        # Statistically significant anomaly in high/moderate reliability stream
        if is_anomaly:
            actions.append(WORKFLOW_REQUEST_MEDICAL_REVIEW)
            actions.append(WORKFLOW_REVIEW_MEASUREMENT)
            actions.append(WORKFLOW_REPEAT_MEASUREMENT)
            return actions

        # Moderate deviation or non-stable trajectory
        if is_mod or traj in ["MOVING_AWAY_FROM_BASELINE", "FLUCTUATING"]:
            actions.append(WORKFLOW_REVIEW_MEASUREMENT)
            return actions

        # Nominal and stable
        actions.append(WORKFLOW_NO_ADDITIONAL_REVIEW)
        return actions
