"""
Tests for Longitudinal Trajectory & Recovery Modeling Engine (intelligence/trajectory.py)
NASA Space Apps Challenge - WEDJAT-X Prototype
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from intelligence.trajectory import (
    LongitudinalTrajectoryEngine,
    classify_trend,
    classify_recovery_trajectory,
    calculate_baseline_distance,
    map_panel_to_category,
    RECOVERY_APPROACHING,
    RECOVERY_MOVING_AWAY,
    RECOVERY_STABLE,
    RECOVERY_FLUCTUATING,
    RECOVERY_INSUFFICIENT,
    TREND_INCREASING,
    TREND_DECREASING,
    TREND_STABLE,
    TREND_FLUCTUATING,
    TREND_INSUFFICIENT,
    PANEL_CATEGORY_MAP,
)
from intelligence.baseline import BaselineEngine, DISCLAIMER_TEXT

DATASET_PATH = Path("cleaned_data/WEDJAT_X_Master_Biomarker_Dataset.csv")


# ============================================================================
# Unit Tests: Trend Classification
# ============================================================================

def test_trend_increasing():
    """Values monotonically moving upward must be classified as INCREASING."""
    vals = [10.0, 20.0, 30.0, 45.0]
    assert classify_trend(vals) == TREND_INCREASING


def test_trend_decreasing():
    """Values monotonically moving downward must be classified as DECREASING."""
    vals = [50.0, 35.0, 20.0, 8.0]
    assert classify_trend(vals) == TREND_DECREASING


def test_trend_stable():
    """Values with minimal fluctuation within tolerance must be classified as STABLE."""
    vals = [100.0, 100.5, 99.8, 100.2]
    assert classify_trend(vals) == TREND_STABLE


def test_trend_fluctuating():
    """Values changing direction repeatedly must be classified as FLUCTUATING."""
    vals = [10.0, 50.0, 15.0, 60.0]
    assert classify_trend(vals) == TREND_FLUCTUATING


def test_trend_missing_timepoints():
    """Missing timepoints (NaNs) must be omitted without interpolation or inventing values."""
    vals = [10.0, np.nan, 30.0, np.nan, 50.0]
    # Clean sequence: [10, 30, 50] -> Increasing
    assert classify_trend(vals) == TREND_INCREASING


def test_trend_insufficient_data():
    """Sequences with fewer than 2 valid observations must return INSUFFICIENT_DATA."""
    assert classify_trend([42.0]) == TREND_INSUFFICIENT
    assert classify_trend([np.nan, 42.0, np.nan]) == TREND_INSUFFICIENT
    assert classify_trend([]) == TREND_INSUFFICIENT


# ============================================================================
# Unit Tests: Postflight Recovery Trajectory Classification
# ============================================================================

def test_recovery_approaching_baseline_from_above():
    """
    Biomarker acutely elevated at R+1 returning toward baseline across recovery:
    Baseline = 10, Postflight = [100, 50, 25, 12] (Distances: 90 -> 40 -> 15 -> 2).
    """
    base_med = 10.0
    post_vals = [100.0, 50.0, 25.0, 12.0]
    assert classify_recovery_trajectory(base_med, post_vals) == RECOVERY_APPROACHING


def test_recovery_approaching_baseline_from_below():
    """
    Biomarker acutely suppressed at R+1 returning toward baseline across recovery:
    Baseline = 100, Postflight = [10, 40, 75, 98] (Distances: 90 -> 60 -> 25 -> 2).
    """
    base_med = 100.0
    post_vals = [10.0, 40.0, 75.0, 98.0]
    assert classify_recovery_trajectory(base_med, post_vals) == RECOVERY_APPROACHING


def test_recovery_moving_away_from_baseline():
    """
    Biomarker departing increasingly further from baseline over postflight:
    Baseline = 10, Postflight = [12, 25, 50, 100] (Distances: 2 -> 15 -> 40 -> 90).
    """
    base_med = 10.0
    post_vals = [12.0, 25.0, 50.0, 100.0]
    assert classify_recovery_trajectory(base_med, post_vals) == RECOVERY_MOVING_AWAY


def test_recovery_stable():
    """
    Biomarker remaining within baseline variability across all postflight points:
    Baseline = 50, Postflight = [51.0, 49.5, 50.2, 50.8] (MAD = 5.0).
    """
    base_med = 50.0
    post_vals = [51.0, 49.5, 50.2, 50.8]
    assert classify_recovery_trajectory(base_med, post_vals, baseline_mad=5.0) == RECOVERY_STABLE


def test_recovery_fluctuating():
    """
    Biomarker distance oscillating non-monotonically:
    Baseline = 10, Postflight = [60, 15, 70, 12] (Distances: 50 -> 5 -> 60 -> 2).
    """
    base_med = 10.0
    post_vals = [60.0, 15.0, 70.0, 12.0]
    assert classify_recovery_trajectory(base_med, post_vals) == RECOVERY_FLUCTUATING


def test_recovery_missing_timepoints_handled_safely():
    """
    Missing intermediate timepoints should not prevent recovery classification:
    Baseline = 10, Postflight = [100.0, np.nan, 25.0, 12.0] (Distances: 90 -> 15 -> 2).
    """
    base_med = 10.0
    post_vals = [100.0, np.nan, 25.0, 12.0]
    assert classify_recovery_trajectory(base_med, post_vals) == RECOVERY_APPROACHING


def test_recovery_zero_baseline():
    """
    Baseline = 0.0 handled safely without division by zero:
    Postflight = [50, 30, 10, 1] (Distances: 50 -> 30 -> 10 -> 1).
    """
    base_med = 0.0
    post_vals = [50.0, 30.0, 10.0, 1.0]
    assert classify_recovery_trajectory(base_med, post_vals) == RECOVERY_APPROACHING

    # Exactly zero throughout
    assert classify_recovery_trajectory(0.0, [0.0, 0.0, 0.0, 0.0]) == RECOVERY_STABLE


def test_recovery_insufficient_baseline_data():
    """If baseline is missing (NaN), recovery classification must be INSUFFICIENT_DATA."""
    assert classify_recovery_trajectory(np.nan, [10.0, 20.0, 30.0, 40.0]) == RECOVERY_INSUFFICIENT


def test_recovery_insufficient_postflight_data():
    """If fewer than 2 postflight points are available, must return INSUFFICIENT_DATA."""
    assert classify_recovery_trajectory(10.0, [np.nan, 25.0, np.nan, np.nan]) == RECOVERY_INSUFFICIENT


# ============================================================================
# Unit Tests: Distance and Panel Mapping
# ============================================================================

def test_calculate_baseline_distance():
    """Distance is absolute difference: |value - baseline|."""
    assert calculate_baseline_distance(120.0, 100.0) == pytest.approx(20.0)
    assert calculate_baseline_distance(80.0, 100.0) == pytest.approx(20.0)
    assert np.isnan(calculate_baseline_distance(np.nan, 100.0))
    assert np.isnan(calculate_baseline_distance(120.0, np.nan))


def test_map_panel_to_category():
    """Panels must map correctly to Cardiovascular, Immune, or Metabolic."""
    assert map_panel_to_category("Cardiovascular EvePanel") == "Cardiovascular"
    assert map_panel_to_category("Immune EvePanel") == "Immune"
    assert map_panel_to_category("Immune AlamarPanel") == "Immune"
    assert map_panel_to_category("Comprehensive Metabolic Panel (CMP)") == "Metabolic"
    assert map_panel_to_category("Nonexistent Panel") == "Other"


# ============================================================================
# Integration Tests: Real OSD-575 Dataset Execution
# ============================================================================

def test_engine_analyze_participant_real_data():
    """Verify trajectory modeling for astronaut C001 on the master dataset."""
    engine = LongitudinalTrajectoryEngine(data_source=DATASET_PATH)
    res_c001 = engine.analyze_participant("C001")

    assert len(res_c001) == 302
    assert "Postflight_Recovery_Class" in res_c001.columns
    assert "Overall_Trend" in res_c001.columns
    assert "Trajectory_Explanation" in res_c001.columns
    assert "Scientific_Notice" in res_c001.columns
    assert DISCLAIMER_TEXT in res_c001["Scientific_Notice"].iloc[0]

    # Verify panel categories present
    cats = set(res_c001["Biomarker_Category"].unique())
    assert {"Cardiovascular", "Immune", "Metabolic"}.issubset(cats)

    # Check that CRP has acute elevation returning toward baseline
    crp_row = res_c001[res_c001["Biomarker_Name"] == "CRP"].iloc[0]
    assert crp_row["R+1_Value"] > crp_row["Baseline_Median"]
    assert len(crp_row["Trajectory_Explanation"]) > 20


def test_engine_panel_summary_real_data():
    """Verify panel-level summary generation."""
    engine = LongitudinalTrajectoryEngine(data_source=DATASET_PATH)
    df_all = engine.analyze_all_participants()
    assert len(df_all) == 1208  # 4 astronauts * 302 biomarkers

    panel_sum = engine.generate_panel_summary(df_all)
    assert len(panel_sum) > 0
    assert "Percent_Of_Panel" in panel_sum.columns

    # Verify all 3 physiological systems are present
    assert set(panel_sum["Biomarker_Category"].unique()) == {"Cardiovascular", "Immune", "Metabolic"}


def test_engine_comparative_summary_real_data():
    """Verify descriptive astronaut comparative summary."""
    engine = LongitudinalTrajectoryEngine(data_source=DATASET_PATH)
    df_all = engine.analyze_all_participants()
    comp_df = engine.generate_comparative_summary(df_all)

    assert len(comp_df) == 4
    assert sorted(comp_df["Participant_ID"].tolist()) == ["C001", "C002", "C003", "C004"]
    assert (comp_df["Total_Biomarkers"] == 302).all()
    assert "Approaching_Baseline_Pct" in comp_df.columns
    assert "Insufficient_Data_Pct" in comp_df.columns

    # C003 should have non-zero insufficient data due to unassayed samples in AlamarPanel
    c003_row = comp_df[comp_df["Participant_ID"] == "C003"].iloc[0]
    assert c003_row["Total_Biomarkers"] == 302
