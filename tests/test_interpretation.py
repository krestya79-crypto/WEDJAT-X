"""
Tests for Scientific Interpretation Engine (intelligence/interpretation.py)
NASA Space Apps Challenge - WEDJAT-X Prototype
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from intelligence.interpretation import (
    ScientificInterpreter,
    WORKFLOW_REVIEW_MEASUREMENT,
    WORKFLOW_VERIFY_SENSOR,
    WORKFLOW_REPEAT_MEASUREMENT,
    WORKFLOW_REQUEST_MEDICAL_REVIEW,
    WORKFLOW_INSUFFICIENT_DATA,
    WORKFLOW_NO_ADDITIONAL_REVIEW,
    PERMITTED_WORKFLOW_FLAGS,
    STATUS_SUPPORTED,
    STATUS_LIMITED,
    STATUS_INSUFFICIENT_DATA,
)
from intelligence.sensor_trust import (
    RELIABILITY_HIGH,
    RELIABILITY_LOW,
    RELIABILITY_UNRELIABLE,
    RELIABILITY_INSUFFICIENT,
)
from intelligence.anomaly import AnomalyResult, ETHICAL_MEDICAL_DISCLAIMER
from intelligence.baseline import DISCLAIMER_TEXT


# ============================================================================
# Unit Tests: Baseline Interpretation
# ============================================================================

def test_interpret_baseline_normal():
    """Verify normal baseline interpretation when measurement aligns with median."""
    interp = ScientificInterpreter()
    res = interp.interpret_baseline(
        biomarker_name="GLUCOSE",
        current_value=90.0,
        baseline_median=90.0,
        baseline_mad=5.0,
        n_baseline=3,
        unit="mg/dL",
        participant_id="C001",
    )

    assert res["direction_of_change"] == "UNCHANGED"
    assert res["absolute_difference"] == pytest.approx(0.0)
    assert res["percentage_difference"] == pytest.approx(0.0)
    assert "GLUCOSE" in res["summary"]
    assert "C001" in res["summary"]


def test_interpret_baseline_elevated_and_suppressed():
    """Verify direction of change and percentage calculations for elevations & suppressions."""
    interp = ScientificInterpreter()

    # Elevated
    res_up = interp.interpret_baseline(
        biomarker_name="CRP",
        current_value=12.0,
        baseline_median=6.0,
        baseline_mad=1.5,
        n_baseline=3,
        unit="mg/L",
    )
    assert res_up["direction_of_change"] == "ELEVATED"
    assert res_up["percentage_difference"] == pytest.approx(100.0)

    # Suppressed
    res_down = interp.interpret_baseline(
        biomarker_name="ALBUMIN",
        current_value=3.0,
        baseline_median=4.0,
        baseline_mad=0.2,
        n_baseline=3,
        unit="g/dL",
    )
    assert res_down["direction_of_change"] == "SUPPRESSED"
    assert res_down["percentage_difference"] == pytest.approx(-25.0)


def test_interpret_baseline_missing():
    """If baseline is missing (n=0 or NaN), summary must indicate baseline is unavailable."""
    interp = ScientificInterpreter()
    res = interp.interpret_baseline(
        biomarker_name="BUN/CREATININE RATIO",
        current_value=15.0,
        baseline_median=np.nan,
        baseline_mad=np.nan,
        n_baseline=0,
        unit="ratio",
    )
    assert res["direction_of_change"] == "UNDEFINED"
    assert res["personalized_baseline_median"] is None
    assert "no preflight baseline is available" in res["summary"]


def test_interpret_baseline_zero_mad():
    """Identical preflight readings (MAD=0.0) must be handled safely."""
    interp = ScientificInterpreter()
    res = interp.interpret_baseline(
        biomarker_name="TEST_BM",
        current_value=12.0,
        baseline_median=10.0,
        baseline_mad=0.0,
        n_baseline=3,
        unit="ng/ml",
    )
    assert res["direction_of_change"] == "ELEVATED"
    assert res["absolute_difference"] == pytest.approx(2.0)


# ============================================================================
# Unit Tests: Statistical Anomaly Interpretation
# ============================================================================

def test_interpret_anomaly_nominal():
    """Nominal anomaly result must not flag threshold exceeded."""
    interp = ScientificInterpreter()
    res = interp.interpret_anomaly({
        "anomaly_flag": "NOMINAL",
        "robust_z_score": 0.5,
        "baseline_mad": 2.0,
    })
    assert res["is_anomaly"] == False
    assert res["threshold_exceeded"] == False
    assert "NOMINAL" in res["statistical_flag"]


def test_interpret_anomaly_significant_spike():
    """Significant elevation must flag threshold exceeded and anomaly status."""
    interp = ScientificInterpreter()
    res = interp.interpret_anomaly({
        "anomaly_flag": "SIGNIFICANT_ELEVATION",
        "robust_z_score": 3.45,
        "baseline_mad": 2.0,
    })
    assert res["is_anomaly"] == True
    assert res["threshold_exceeded"] == True
    assert "significant threshold" in res["statements"][-1].lower()


# ============================================================================
# Unit Tests: Trajectory Interpretation
# ============================================================================

def test_interpret_trajectory_fluctuating():
    """Fluctuating trajectory must note multi-phase recovery dynamics."""
    interp = ScientificInterpreter()
    res = interp.interpret_trajectory({
        "Biomarker_Name": "IL-6",
        "Panel_Name": "Immune EvePanel",
        "Postflight_Recovery_Class": "FLUCTUATING",
        "Overall_Trend": "FLUCTUATING",
        "L-92_Value": 2.0,
        "R+1_Value": 15.0,
        "R+194_Value": 4.0,
    })
    assert res["trajectory_status"] == "FLUCTUATING"
    assert "multi-phase" in res["fluctuation_information"].lower()
    assert len(res["previous_measurements"]) == 3


def test_interpret_trajectory_insufficient_timepoints():
    """Missing longitudinal points must emit insufficient timepoint warning."""
    interp = ScientificInterpreter()
    res = interp.interpret_trajectory({
        "Biomarker_Name": "BUN",
        "Panel_Name": "CMP",
        "Postflight_Recovery_Class": "INSUFFICIENT_DATA",
    })
    assert res["trajectory_status"] == "INSUFFICIENT_DATA"
    assert len(res["insufficient_timepoint_warnings"]) > 0


# ============================================================================
# Unit Tests: Ground Medical Report Completeness (All 7 Sections)
# ============================================================================

def test_ground_report_structure_completeness():
    """Ground medical report must contain all 7 specified sections and valid workflow flags."""
    interp = ScientificInterpreter()

    obs = {"name": "CRP", "value": 10.6, "unit": "mg/L", "timestamp_or_timepoint": "R+1", "participant_id": "C001"}
    base = interp.interpret_baseline("CRP", 10.6, 5.1, 1.5, 3, "mg/L", "C001")
    stat = interp.interpret_anomaly({"anomaly_flag": "SIGNIFICANT_ELEVATION", "robust_z_score": 3.2, "baseline_mad": 1.5})
    traj = interp.interpret_trajectory({"Biomarker_Name": "CRP", "Postflight_Recovery_Class": "APPROACHING_BASELINE"})
    qual = {"quality_score": 95.0, "reliability_category": RELIABILITY_HIGH}

    report = interp.generate_ground_report(
        observation=obs,
        baseline_comparison=base,
        statistical_interpretation=stat,
        longitudinal_interpretation=traj,
        sensor_quality=qual,
        is_synthetic=False,
    )

    # 7 Sections check
    assert "observation" in report
    assert "baseline_comparison" in report
    assert "statistical_interpretation" in report
    assert "longitudinal_interpretation" in report
    assert "signal_quality" in report
    assert "evidence" in report
    assert "recommended_review_action" in report

    # Schema & workflow check
    assert report["report_type"] == "GROUND_MEDICAL"
    assert report["interpretation_status"] == STATUS_SUPPORTED
    assert len(report["evidence"]) >= 3

    # All workflow actions must be within allowed non-prescriptive flags
    for action in report["recommended_review_action"]:
        assert action in PERMITTED_WORKFLOW_FLAGS

    # Because CRP has significant anomaly with high reliability, review should be requested
    assert WORKFLOW_REQUEST_MEDICAL_REVIEW in report["recommended_review_action"]


# ============================================================================
# Unit Tests: Astronaut Report Clarity & Tone
# ============================================================================

def test_astronaut_report_clarity():
    """Astronaut report must use clear language, avoid medical alarm, and provide calm guidance."""
    interp = ScientificInterpreter()

    obs = {"name": "Heart Rate", "value": 110.0, "unit": "bpm"}
    base = {"direction_of_change": "ELEVATED", "personalized_baseline_median": 70.0}
    stat = {"is_anomaly": True}
    traj = {"trajectory_status": "APPROACHING_BASELINE"}
    qual = {"reliability_category": RELIABILITY_HIGH, "motion_interference": True}

    crew_rep = interp.generate_astronaut_report(
        observation=obs,
        baseline_comparison=base,
        statistical_interpretation=stat,
        longitudinal_interpretation=traj,
        sensor_quality=qual,
        is_synthetic=True,
    )

    assert crew_rep["report_type"] == "ASTRONAUT_FRIENDLY"
    assert crew_rep["biomarker_or_sensor"] == "Heart Rate"
    assert crew_rep["differs_from_baseline"] == True
    assert crew_rep["is_synthetic"] == True

    narrative = crew_rep["crew_narrative"]
    assert len(narrative) > 50

    # Must mention motion context
    assert "movement" in narrative.lower() or "motion" in narrative.lower()

    # Must contain calm action guidance
    assert "procedure" in narrative.lower() or "verify" in narrative.lower()


# ============================================================================
# Unit Tests: Strict Scientific & Non-Clinical Integrity
# ============================================================================

def test_no_clinical_diagnoses_or_prescriptions():
    """Reports must never contain disease diagnoses or prescription recommendations."""
    interp = ScientificInterpreter()

    obs = {"name": "Troponin_I", "value": 500.0, "unit": "pg/ml"}
    base = {"direction_of_change": "ELEVATED", "personalized_baseline_median": 10.0}
    stat = {"is_anomaly": True}

    report = interp.generate_ground_report(obs, base, stat)

    # Convert entire report to lowercase text
    rep_text = json.dumps(report).lower()

    forbidden_clinical_words = [
        "myocardial infarction",
        "heart attack",
        "prescribe",
        "administer",
        "treat with",
        "diagnosed with",
        "pathology confirmed",
        "disease detected",
    ]

    for word in forbidden_clinical_words:
        assert word not in rep_text, f"Forbidden clinical term '{word}' found in report!"


def test_json_serialization():
    """Integrated report must be 100% JSON serializable without custom encoders."""
    interp = ScientificInterpreter()
    report = interp.generate_integrated_interpretation(
        observation={"name": "SpO2", "value": 97.5, "unit": "%", "timestamp_or_timepoint": "2026-01-01"},
        is_synthetic=True,
    )

    json_str = json.dumps(report)
    assert len(json_str) > 0
    reloaded = json.loads(json_str)
    assert reloaded["report_type"] == "GROUND_MEDICAL"
    assert reloaded["is_synthetic"] == True


def test_unreliable_sensor_workflow():
    """Unreliable sensor signals must trigger VERIFY_SENSOR_SIGNAL workflow flag."""
    interp = ScientificInterpreter()
    obs = {"name": "heart_rate", "value": 85.0, "unit": "bpm"}
    qual = {"quality_score": 42.0, "reliability_category": RELIABILITY_UNRELIABLE}

    report = interp.generate_ground_report(observation=obs, sensor_quality=qual)
    assert WORKFLOW_VERIFY_SENSOR in report["recommended_review_action"]


def test_missing_data_workflow():
    """Missing or disconnected data must trigger INSUFFICIENT_DATA_FOR_INTERPRETATION."""
    interp = ScientificInterpreter()
    obs = {"name": "heart_rate", "value": np.nan, "unit": "bpm"}
    qual = {"reliability_category": RELIABILITY_INSUFFICIENT, "disconnection_rate": 1.0}

    report = interp.generate_ground_report(observation=obs, sensor_quality=qual)
    assert WORKFLOW_INSUFFICIENT_DATA in report["recommended_review_action"]
    assert report["interpretation_status"] == STATUS_INSUFFICIENT_DATA
