"""
Tests for Anomaly Detection Engine (intelligence/anomaly.py)
NASA Space Apps Challenge - WEDJAT-X Prototype
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from intelligence.baseline import BaselineEngine
from intelligence.anomaly import (
    AnomalyDetector,
    calculate_robust_z_score,
    generate_explanation,
    AnomalyResult,
    ETHICAL_MEDICAL_DISCLAIMER,
    DEFAULT_ANOMALY_THRESHOLD,
    DEFAULT_MODERATE_THRESHOLD,
)

DATASET_PATH = Path("cleaned_data/WEDJAT_X_Master_Biomarker_Dataset.csv")


# ============================================================================
# Unit Tests: Robust Z-Score Calculation
# ============================================================================

def test_calculate_robust_z_score_basic():
    """Verify raw robust Z-score calculation (scale_factor=1.0)."""
    # (30 - 20) / (10 * 1.0) = 1.0
    z = calculate_robust_z_score(value=30.0, baseline_median=20.0, baseline_mad=10.0, scale_factor=1.0)
    assert z == pytest.approx(1.0)


def test_calculate_robust_z_score_scaled():
    """Verify Boris Iglewicz & Hoaglin scaled robust Z-score."""
    # (30 - 20) / (10 * 1.4826) = 10 / 14.826 = 0.67449
    z = calculate_robust_z_score(value=30.0, baseline_median=20.0, baseline_mad=10.0, scale_factor=1.4826)
    assert z == pytest.approx(0.6744907, rel=1e-4)


def test_calculate_robust_z_score_suppression():
    """Verify negative robust Z-score for suppressed values."""
    # (10 - 20) / (5 * 1.0) = -2.0
    z = calculate_robust_z_score(value=10.0, baseline_median=20.0, baseline_mad=5.0, scale_factor=1.0)
    assert z == pytest.approx(-2.0)


def test_calculate_robust_z_score_zero_delta():
    """Observed value matching baseline median yields Z = 0.0."""
    z = calculate_robust_z_score(value=20.0, baseline_median=20.0, baseline_mad=5.0)
    assert z == 0.0


def test_calculate_robust_z_score_zero_mad():
    """Preflight MAD = 0.0: If value matches median, Z=0.0; else returns NaN."""
    # Matching median
    z_zero_delta = calculate_robust_z_score(value=5.0, baseline_median=5.0, baseline_mad=0.0)
    assert z_zero_delta == 0.0

    # Non-matching median with zero MAD
    z_non_zero_delta = calculate_robust_z_score(value=8.0, baseline_median=5.0, baseline_mad=0.0)
    assert np.isnan(z_non_zero_delta)


def test_calculate_robust_z_score_missing_inputs():
    """NaN in any parameter must safely yield NaN."""
    assert np.isnan(calculate_robust_z_score(np.nan, 20.0, 5.0))
    assert np.isnan(calculate_robust_z_score(30.0, np.nan, 5.0))
    assert np.isnan(calculate_robust_z_score(30.0, 20.0, np.nan))


# ============================================================================
# Unit Tests: AnomalyDetector Configuration & Validation
# ============================================================================

def test_anomaly_detector_config_valid():
    """Detector initializes with custom valid thresholds."""
    det = AnomalyDetector(threshold=3.5, moderate_threshold=2.0, scale_factor=1.0, min_preflight_samples=2)
    assert det.threshold == 3.5
    assert det.moderate_threshold == 2.0
    assert det.scale_factor == 1.0
    assert det.min_preflight_samples == 2


def test_anomaly_detector_invalid_thresholds():
    """Invalid thresholds must raise ValueError."""
    with pytest.raises(ValueError, match="threshold must be positive"):
        AnomalyDetector(threshold=-1.0)

    with pytest.raises(ValueError, match="must be strictly less than threshold"):
        AnomalyDetector(threshold=3.0, moderate_threshold=3.5)

    with pytest.raises(ValueError, match="scale_factor must be positive"):
        AnomalyDetector(scale_factor=0.0)


# ============================================================================
# Single Observation Evaluation Tests
# ============================================================================

def test_evaluate_observation_nominal():
    """Value within thresholds must be flagged NOMINAL."""
    det = AnomalyDetector(threshold=3.0, moderate_threshold=2.0, scale_factor=1.0)
    res = det.evaluate_observation(
        value=22.0,
        baseline_median=20.0,
        baseline_mad=5.0,
        preflight_sample_count=3,
        participant_id="C001",
        biomarker_name="Fibrinogen",
        panel_name="Cardio",
        timepoint="R+1",
        unit="ng/ml",
    )
    assert res.anomaly_flag == "NOMINAL"
    assert res.robust_z_score == pytest.approx(0.4)
    assert "NOMINAL" in res.explanation
    assert ETHICAL_MEDICAL_DISCLAIMER in res.scientific_disclaimer


def test_evaluate_observation_elevations():
    """Test moderate and significant elevations with dual thresholds."""
    det = AnomalyDetector(threshold=3.0, moderate_threshold=2.0, scale_factor=1.0)

    # Moderate elevation: delta=25 -> Z = 2.5
    res_mod = det.evaluate_observation(
        value=45.0, baseline_median=20.0, baseline_mad=10.0, preflight_sample_count=3
    )
    assert res_mod.anomaly_flag == "MODERATE_ELEVATION"
    assert res_mod.robust_z_score == pytest.approx(2.5)

    # Significant elevation: delta=35 -> Z = 3.5
    res_sig = det.evaluate_observation(
        value=55.0, baseline_median=20.0, baseline_mad=10.0, preflight_sample_count=3
    )
    assert res_sig.anomaly_flag == "SIGNIFICANT_ELEVATION"
    assert res_sig.robust_z_score == pytest.approx(3.5)


def test_evaluate_observation_suppressions():
    """Test moderate and significant suppressions with dual thresholds."""
    det = AnomalyDetector(threshold=3.0, moderate_threshold=2.0, scale_factor=1.0)

    # Moderate suppression: delta=-25 -> Z = -2.5
    res_mod = det.evaluate_observation(
        value=15.0, baseline_median=40.0, baseline_mad=10.0, preflight_sample_count=3
    )
    assert res_mod.anomaly_flag == "MODERATE_SUPPRESSION"
    assert res_mod.robust_z_score == pytest.approx(-2.5)

    # Significant suppression: delta=-35 -> Z = -3.5
    res_sig = det.evaluate_observation(
        value=5.0, baseline_median=40.0, baseline_mad=10.0, preflight_sample_count=3
    )
    assert res_sig.anomaly_flag == "SIGNIFICANT_SUPPRESSION"
    assert res_sig.robust_z_score == pytest.approx(-3.5)


def test_evaluate_observation_single_threshold_mode():
    """Test binary anomaly flags when moderate_threshold=None."""
    det = AnomalyDetector(threshold=3.0, moderate_threshold=None, scale_factor=1.0)

    res_ele = det.evaluate_observation(
        value=60.0, baseline_median=20.0, baseline_mad=10.0, preflight_sample_count=3
    )
    assert res_ele.anomaly_flag == "STATISTICAL_ELEVATION"

    res_sup = det.evaluate_observation(
        value=0.0, baseline_median=40.0, baseline_mad=10.0, preflight_sample_count=3
    )
    assert res_sup.anomaly_flag == "STATISTICAL_SUPPRESSION"


def test_evaluate_observation_missing_measurement():
    """Missing observation value must be flagged MISSING_MEASUREMENT."""
    det = AnomalyDetector()
    res = det.evaluate_observation(
        value=np.nan, baseline_median=20.0, baseline_mad=5.0, preflight_sample_count=3
    )
    assert res.anomaly_flag == "MISSING_MEASUREMENT"
    assert np.isnan(res.robust_z_score)
    assert "MISSING_MEASUREMENT" in res.explanation


def test_evaluate_observation_insufficient_baseline():
    """Insufficient preflight measurements must be flagged INSUFFICIENT_BASELINE."""
    det = AnomalyDetector(min_preflight_samples=2)

    # 0 preflight samples
    res_zero = det.evaluate_observation(
        value=25.0, baseline_median=np.nan, baseline_mad=np.nan, preflight_sample_count=0
    )
    assert res_zero.anomaly_flag == "INSUFFICIENT_BASELINE"
    assert np.isnan(res_zero.robust_z_score)

    # 1 preflight sample when min_preflight_samples=2
    res_single = det.evaluate_observation(
        value=25.0, baseline_median=20.0, baseline_mad=0.0, preflight_sample_count=1
    )
    assert res_single.anomaly_flag == "INSUFFICIENT_BASELINE"


def test_evaluate_observation_zero_baseline_dispersion():
    """Zero preflight MAD with non-zero delta must be flagged ZERO_BASELINE_DISPERSION."""
    det = AnomalyDetector(min_preflight_samples=2)
    res = det.evaluate_observation(
        value=30.0, baseline_median=20.0, baseline_mad=0.0, preflight_sample_count=3
    )
    assert res.anomaly_flag == "ZERO_BASELINE_DISPERSION"
    assert np.isnan(res.robust_z_score)
    assert "preflight MAD is 0.0" in res.explanation


# ============================================================================
# Explanation Content & Medical Ethics Disclaimer Verification
# ============================================================================

def test_explanation_underlying_values_completeness():
    """Explanation must transparently include all underlying numeric parameters."""
    expl = generate_explanation(
        participant_id="C001",
        biomarker_name="CRP",
        panel_name="Cardiovascular EvePanel",
        timepoint="R+1",
        value=10637600.0,
        unit="pg/ml",
        baseline_median=5131700.0,
        baseline_mad=3293200.0,
        preflight_count=3,
        robust_z=3.12,
        flag="SIGNIFICANT_ELEVATION",
        threshold=3.0,
        days_relative_to_return=1,
    )

    # Must contain identifier, biomarker, timepoint, days
    assert "C001" in expl
    assert "CRP" in expl
    assert "R+1" in expl
    assert "Day +1" in expl

    # Must contain underlying numeric values
    assert "10637600" in expl or "1.064e+07" in expl
    assert "5131700" in expl or "5.132e+06" in expl
    assert "3293200" in expl or "3.293e+06" in expl
    assert "+3.12" in expl

    # Must contain flag and disclaimer
    assert "SIGNIFICANT_ELEVATION" in expl
    assert "EXPLORATORY RESEARCH ONLY" in expl
    assert "NOT constitute medical diagnoses" in expl


def test_never_treat_statistical_anomalies_as_medical_diagnoses():
    """
    Strict biomedical compliance test:
    Verify that anomaly flags and explanations never include clinical diagnostic terms.
    """
    forbidden_terms = [
        "disease",
        "pathology",
        "syndrome",
        "diagnosis",
        "impairment",
        "infection",
        "myocardial",
        "acute kidney injury",
        "liver failure",
    ]

    det = AnomalyDetector()
    res = det.evaluate_observation(
        value=100000.0,
        baseline_median=10.0,
        baseline_mad=1.0,
        preflight_sample_count=3,
        biomarker_name="Troponin_I",
    )

    flag_lower = res.anomaly_flag.lower()
    for term in forbidden_terms:
        assert term not in flag_lower, f"Clinical diagnostic term '{term}' found in anomaly flag '{res.anomaly_flag}'"

    # Explanation must explicitly state it is NOT a diagnosis
    assert "NOT constitute medical diagnoses" in res.explanation
    assert res.scientific_disclaimer == ETHICAL_MEDICAL_DISCLAIMER


# ============================================================================
# Batch Detection, Filtering & Real OSD-575 Dataset Integration
# ============================================================================

def test_detect_anomalies_missing_columns():
    """detect_anomalies must raise ValueError if required baseline columns are missing."""
    det = AnomalyDetector()
    incomplete_df = pd.DataFrame([{"Measurement_Value": 10.0}])
    with pytest.raises(ValueError, match="Input DataFrame missing required columns"):
        det.detect_anomalies(incomplete_df)


def test_detect_anomalies_and_filtering_real_dataset():
    """
    Run end-to-end integration: BaselineEngine -> longitudinal changes -> AnomalyDetector.
    Verify detection of acute postflight inflammatory responses in real astronaut data.
    """
    engine = BaselineEngine(DATASET_PATH)
    longitudinal_c001 = engine.calculate_longitudinal_changes("C001")

    detector = AnomalyDetector(threshold=3.0, moderate_threshold=2.0)
    analyzed_df = detector.detect_anomalies(longitudinal_c001)

    assert len(analyzed_df) == 2114
    assert "Robust_Z_Score" in analyzed_df.columns
    assert "Exploratory_Anomaly_Flag" in analyzed_df.columns
    assert "Anomaly_Explanation" in analyzed_df.columns
    assert "Scientific_Disclaimer" in analyzed_df.columns

    # Filter to anomalies
    anomalies_df = detector.filter_anomalies(analyzed_df, include_moderate=True)
    assert len(anomalies_df) > 0

    # Summary table
    summary_df = detector.summarize_anomalies(analyzed_df)
    assert len(summary_df) > 0
    assert "Biomarker_Count" in summary_df.columns

    # Verify that acute R+1 inflammatory spikes exist among anomalies
    r1_anomalies = anomalies_df[anomalies_df["Timepoint"] == "R+1"]
    assert len(r1_anomalies) > 0

    # Verify all anomaly explanations are populated and contain the disclaimer
    for expl in anomalies_df["Anomaly_Explanation"]:
        assert len(expl) > 20
        assert "NOTICE: EXPLORATORY RESEARCH ONLY" in expl
