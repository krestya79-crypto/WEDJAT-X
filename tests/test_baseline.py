"""
Tests for Baseline Engine (intelligence/baseline.py)
NASA Space Apps Challenge - WEDJAT-X Prototype
"""

import math
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from intelligence.baseline import (
    BaselineEngine,
    calculate_mad,
    calculate_absolute_change,
    calculate_percent_change,
    load_master_dataset,
    DISCLAIMER_TEXT,
    DEFAULT_PREFLIGHT_TIMEPOINTS,
)

DATASET_PATH = Path("cleaned_data/WEDJAT_X_Master_Biomarker_Dataset.csv")


# ============================================================================
# Unit Tests: Mathematical Helper Functions
# ============================================================================

def test_calculate_mad_basic():
    """Test raw MAD on a symmetric known array: [10, 20, 30]."""
    # Median is 20, absolute deviations: [10, 0, 10], median deviation: 10
    vals = [10.0, 20.0, 30.0]
    mad = calculate_mad(vals, scale=1.0)
    assert mad == pytest.approx(10.0)


def test_calculate_mad_scaled():
    """Test MAD with normal consistency multiplier (1.4826)."""
    vals = [10.0, 20.0, 30.0]
    mad = calculate_mad(vals, scale=1.4826)
    assert mad == pytest.approx(14.826)


def test_calculate_mad_even_length():
    """Test MAD on an even-length sequence: [1, 2, 3, 4]."""
    # Median is 2.5. Deviations: [1.5, 0.5, 0.5, 1.5]. Sorted: [0.5, 0.5, 1.5, 1.5]. Median dev: 1.0
    vals = [1.0, 2.0, 3.0, 4.0]
    assert calculate_mad(vals) == pytest.approx(1.0)


def test_calculate_mad_identical_values():
    """Identical values must yield MAD = 0.0."""
    vals = [5.0, 5.0, 5.0, 5.0]
    assert calculate_mad(vals) == 0.0


def test_calculate_mad_single_value():
    """Single observation cannot estimate dispersion, returns 0.0."""
    assert calculate_mad([42.0]) == 0.0


def test_calculate_mad_with_nans():
    """NaN values must be safely omitted."""
    vals = [np.nan, 10.0, np.nan, 20.0, 30.0]
    assert calculate_mad(vals) == pytest.approx(10.0)


def test_calculate_mad_empty():
    """Empty or all-NaN arrays should return np.nan."""
    assert np.isnan(calculate_mad([]))
    assert np.isnan(calculate_mad([np.nan, np.nan]))


def test_calculate_absolute_change():
    """Test absolute change: value - baseline."""
    assert calculate_absolute_change(150.0, 100.0) == pytest.approx(50.0)
    assert calculate_absolute_change(40.0, 100.0) == pytest.approx(-60.0)
    assert np.isnan(calculate_absolute_change(np.nan, 100.0))
    assert np.isnan(calculate_absolute_change(150.0, np.nan))


def test_calculate_percent_change_linear():
    """Test linear percentage change calculation."""
    # 50% elevation
    assert calculate_percent_change(150.0, 100.0) == pytest.approx(50.0)
    # 50% suppression
    assert calculate_percent_change(50.0, 100.0) == pytest.approx(-50.0)
    # Zero baseline handling
    assert calculate_percent_change(0.0, 0.0) == 0.0
    assert np.isnan(calculate_percent_change(50.0, 0.0))
    # NaN handling
    assert np.isnan(calculate_percent_change(np.nan, 100.0))
    assert np.isnan(calculate_percent_change(100.0, np.nan))


def test_calculate_percent_change_log_scale():
    """Test percentage fold-change calculation for log2 NPQ units."""
    # Delta of +1.0 in log2 corresponds to 2^1 = 2x fold-change (+100%)
    pct_up = calculate_percent_change(3.0, 2.0, is_log_scale=True)
    assert pct_up == pytest.approx(100.0)

    # Delta of -1.0 in log2 corresponds to 2^-1 = 0.5x fold-change (-50%)
    pct_down = calculate_percent_change(1.0, 2.0, is_log_scale=True)
    assert pct_down == pytest.approx(-50.0)


# ============================================================================
# Dataset Loading & Validation Tests
# ============================================================================

def test_load_master_dataset_success():
    """Verify loading validated master dataset."""
    df = load_master_dataset(DATASET_PATH, only_validated=False)
    assert len(df) == 8456
    assert "Participant_ID" in df.columns
    assert "Measurement_Value" in df.columns
    assert sorted(df["Participant_ID"].unique().tolist()) == ["C001", "C002", "C003", "C004"]


def test_load_master_dataset_only_validated():
    """Verify filtering to VALIDATED_MATCH rows."""
    df_val = load_master_dataset(DATASET_PATH, only_validated=True)
    assert len(df_val) == 8230
    assert (df_val["Validation_Status"] == "VALIDATED_MATCH").all()


def test_load_master_dataset_file_not_found():
    """Loading from a non-existent path must raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_master_dataset("invalid/path/to/nonexistent.csv")


def test_load_master_dataset_missing_columns(tmp_path):
    """Loading a CSV missing required columns must raise ValueError."""
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("ColA,ColB\n1,2\n")
    with pytest.raises(ValueError, match="Dataset missing required columns"):
        load_master_dataset(bad_csv)


# ============================================================================
# BaselineEngine: Participant Selection & Validation Tests
# ============================================================================

def test_baseline_engine_participants():
    """BaselineEngine must detect all 4 astronauts."""
    engine = BaselineEngine(DATASET_PATH)
    assert engine.available_participants == ["C001", "C002", "C003", "C004"]


def test_baseline_engine_invalid_participant():
    """Selecting an invalid participant must raise ValueError."""
    engine = BaselineEngine(DATASET_PATH)
    with pytest.raises(ValueError, match="Participant 'UNKNOWN' not found"):
        engine.select_participant = engine.validate_participant("UNKNOWN")


def test_baseline_engine_get_participant_data():
    """Participant subset must only contain that participant's records."""
    engine = BaselineEngine(DATASET_PATH)
    p_data = engine.get_participant_data("C001")
    assert (p_data["Participant_ID"] == "C001").all()
    assert len(p_data) == 2114  # 302 biomarkers * 7 timepoints


# ============================================================================
# BaselineEngine: Synthetic Edge Cases
# ============================================================================

def test_calculate_baseline_synthetic_edge_cases():
    """Test baseline engine with mock dataset containing all edge cases."""
    mock_data = pd.DataFrame([
        # Case 1: Nominal baseline (3 distinct preflight points)
        {"Participant_ID": "P1", "Sample_ID": "S1", "Timepoint": "L-92", "Timepoint_Phase": "Preflight",
         "Biomarker_Name": "BM_NOMINAL", "Measurement_Value": 10.0, "Measurement_Unit": "pg/ml",
         "Panel_Name": "PanelA", "Platform_Technology": "TechA", "Validation_Status": "VALIDATED_MATCH"},
        {"Participant_ID": "P1", "Sample_ID": "S2", "Timepoint": "L-44", "Timepoint_Phase": "Preflight",
         "Biomarker_Name": "BM_NOMINAL", "Measurement_Value": 20.0, "Measurement_Unit": "pg/ml",
         "Panel_Name": "PanelA", "Platform_Technology": "TechA", "Validation_Status": "VALIDATED_MATCH"},
        {"Participant_ID": "P1", "Sample_ID": "S3", "Timepoint": "L-3", "Timepoint_Phase": "Preflight",
         "Biomarker_Name": "BM_NOMINAL", "Measurement_Value": 30.0, "Measurement_Unit": "pg/ml",
         "Panel_Name": "PanelA", "Platform_Technology": "TechA", "Validation_Status": "VALIDATED_MATCH"},

        # Case 2: Zero MAD (all preflight identical)
        {"Participant_ID": "P1", "Sample_ID": "S1", "Timepoint": "L-92", "Timepoint_Phase": "Preflight",
         "Biomarker_Name": "BM_ZERO_MAD", "Measurement_Value": 5.0, "Measurement_Unit": "pg/ml",
         "Panel_Name": "PanelA", "Platform_Technology": "TechA", "Validation_Status": "VALIDATED_MATCH"},
        {"Participant_ID": "P1", "Sample_ID": "S2", "Timepoint": "L-44", "Timepoint_Phase": "Preflight",
         "Biomarker_Name": "BM_ZERO_MAD", "Measurement_Value": 5.0, "Measurement_Unit": "pg/ml",
         "Panel_Name": "PanelA", "Platform_Technology": "TechA", "Validation_Status": "VALIDATED_MATCH"},
        {"Participant_ID": "P1", "Sample_ID": "S3", "Timepoint": "L-3", "Timepoint_Phase": "Preflight",
         "Biomarker_Name": "BM_ZERO_MAD", "Measurement_Value": 5.0, "Measurement_Unit": "pg/ml",
         "Panel_Name": "PanelA", "Platform_Technology": "TechA", "Validation_Status": "VALIDATED_MATCH"},

        # Case 3: Single preflight sample
        {"Participant_ID": "P1", "Sample_ID": "S1", "Timepoint": "L-92", "Timepoint_Phase": "Preflight",
         "Biomarker_Name": "BM_SINGLE", "Measurement_Value": 12.0, "Measurement_Unit": "pg/ml",
         "Panel_Name": "PanelA", "Platform_Technology": "TechA", "Validation_Status": "VALIDATED_MATCH"},
        {"Participant_ID": "P1", "Sample_ID": "S2", "Timepoint": "L-44", "Timepoint_Phase": "Preflight",
         "Biomarker_Name": "BM_SINGLE", "Measurement_Value": np.nan, "Measurement_Unit": "pg/ml",
         "Panel_Name": "PanelA", "Platform_Technology": "TechA", "Validation_Status": "REPORTED_MISSING"},
        {"Participant_ID": "P1", "Sample_ID": "S3", "Timepoint": "L-3", "Timepoint_Phase": "Preflight",
         "Biomarker_Name": "BM_SINGLE", "Measurement_Value": np.nan, "Measurement_Unit": "pg/ml",
         "Panel_Name": "PanelA", "Platform_Technology": "TechA", "Validation_Status": "REPORTED_MISSING"},

        # Case 4: No preflight samples (all missing)
        {"Participant_ID": "P1", "Sample_ID": "S1", "Timepoint": "L-92", "Timepoint_Phase": "Preflight",
         "Biomarker_Name": "BM_EMPTY", "Measurement_Value": np.nan, "Measurement_Unit": "pg/ml",
         "Panel_Name": "PanelA", "Platform_Technology": "TechA", "Validation_Status": "REPORTED_MISSING"},
        {"Participant_ID": "P1", "Sample_ID": "S2", "Timepoint": "L-44", "Timepoint_Phase": "Preflight",
         "Biomarker_Name": "BM_EMPTY", "Measurement_Value": np.nan, "Measurement_Unit": "pg/ml",
         "Panel_Name": "PanelA", "Platform_Technology": "TechA", "Validation_Status": "REPORTED_MISSING"},
        {"Participant_ID": "P1", "Sample_ID": "S3", "Timepoint": "L-3", "Timepoint_Phase": "Preflight",
         "Biomarker_Name": "BM_EMPTY", "Measurement_Value": np.nan, "Measurement_Unit": "pg/ml",
         "Panel_Name": "PanelA", "Platform_Technology": "TechA", "Validation_Status": "REPORTED_MISSING"},
    ])

    engine = BaselineEngine(mock_data)
    baselines = engine.calculate_baseline("P1")

    # Check BM_NOMINAL
    b_nom = baselines[baselines["Biomarker_Name"] == "BM_NOMINAL"].iloc[0]
    assert b_nom["Baseline_Median"] == pytest.approx(20.0)
    assert b_nom["Baseline_MAD"] == pytest.approx(10.0)
    assert b_nom["Preflight_Sample_Count"] == 3
    assert b_nom["Baseline_Status"] == "VALID_BASELINE"

    # Check BM_ZERO_MAD
    b_zero = baselines[baselines["Biomarker_Name"] == "BM_ZERO_MAD"].iloc[0]
    assert b_zero["Baseline_Median"] == pytest.approx(5.0)
    assert b_zero["Baseline_MAD"] == 0.0
    assert b_zero["Preflight_Sample_Count"] == 3
    assert b_zero["Baseline_Status"] == "ZERO_MAD"

    # Check BM_SINGLE
    b_single = baselines[baselines["Biomarker_Name"] == "BM_SINGLE"].iloc[0]
    assert b_single["Baseline_Median"] == pytest.approx(12.0)
    assert b_single["Preflight_Sample_Count"] == 1
    assert b_single["Baseline_Status"] == "SINGLE_PREFLIGHT_SAMPLE"

    # Check BM_EMPTY
    b_empty = baselines[baselines["Biomarker_Name"] == "BM_EMPTY"].iloc[0]
    assert np.isnan(b_empty["Baseline_Median"])
    assert np.isnan(b_empty["Baseline_MAD"])
    assert b_empty["Preflight_Sample_Count"] == 0
    assert b_empty["Baseline_Status"] == "INSUFFICIENT_BASELINE"


# ============================================================================
# BaselineEngine: Integration Tests on Real OSD-575 Dataset
# ============================================================================

def test_calculate_baseline_real_dataset_all_participants():
    """Verify baseline calculation across all four astronauts in the master dataset."""
    engine = BaselineEngine(DATASET_PATH)

    for part_id in ["C001", "C002", "C003", "C004"]:
        baselines = engine.calculate_baseline(part_id)
        assert len(baselines) == 302
        assert "Scientific_Notice" in baselines.columns
        assert DISCLAIMER_TEXT in baselines["Scientific_Notice"].iloc[0]

        # Check known edge cases:
        # C003 has Immune AlamarPanel with L-44 unassayed (preflight count should be 2 for those biomarkers)
        if part_id == "C003":
            alamar_base = baselines[baselines["Panel_Name"] == "Immune AlamarPanel"]
            assert (alamar_base["Preflight_Sample_Count"] == 2).all()

        # C002 and C004 have BUN/CREATININE RATIO missing across all preflight samples
        if part_id in ["C002", "C004"]:
            bun_row = baselines[baselines["Biomarker_Name"] == "BUN/CREATININE RATIO"]
            assert len(bun_row) == 1
            assert bun_row["Preflight_Sample_Count"].iloc[0] == 0
            assert bun_row["Baseline_Status"].iloc[0] == "INSUFFICIENT_BASELINE"


def test_calculate_longitudinal_changes_real_dataset():
    """Verify longitudinal deltas relative to baseline on real astronaut data."""
    engine = BaselineEngine(DATASET_PATH)
    longitudinal = engine.calculate_longitudinal_changes("C001")

    assert len(longitudinal) == 2114
    assert "Absolute_Change_From_Baseline" in longitudinal.columns
    assert "Percent_Change_From_Baseline" in longitudinal.columns
    assert "Fold_Change_Linear_Percent" in longitudinal.columns

    # Preflight measurements: absolute changes around preflight median should be modest
    preflight_rows = longitudinal[longitudinal["Timepoint"].isin(["L-92", "L-44", "L-3"])]
    valid_pre_deltas = preflight_rows["Absolute_Change_From_Baseline"].dropna()
    assert len(valid_pre_deltas) > 0

    # Verify R+1 CRP acute elevation in C001
    crp_r1 = longitudinal[(longitudinal["Biomarker_Name"] == "CRP") & (longitudinal["Timepoint"] == "R+1")]
    assert len(crp_r1) == 1
    crp_r1_row = crp_r1.iloc[0]
    # At R+1, CRP in C001 was 10,637,600 vs preflight median 5,131,700
    assert crp_r1_row["Measurement_Value"] == pytest.approx(10637600.0)
    assert crp_r1_row["Baseline_Median"] == pytest.approx(5131700.0)
    assert crp_r1_row["Absolute_Change_From_Baseline"] == pytest.approx(5505900.0)
    assert crp_r1_row["Percent_Change_From_Baseline"] > 100.0
