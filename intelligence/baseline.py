"""
WEDJAT-X Personalized Baseline Engine
NASA Space Apps Challenge - Astronaut Health Monitoring Prototype

This module implements the Personalized Baseline Engine for NASA OSD-575 study data.
It calculates individualized biomarker baselines from available preflight research
samples (L-92, L-44, L-3) using robust statistics (Median and Median Absolute Deviation).

IMPORTANT SCIENTIFIC & ETHICAL NOTICE:
--------------------------------------
This software is an exploratory research prototype for aerospace physiology data analysis.
Measurements are benchtop laboratory assay values (OSD-575 / Inspiration4 mission), NOT
real-time continuous telemetry. The baselines and relative changes computed here are
purely statistical reference metrics. They DO NOT constitute medical baselines, clinical
diagnoses, or evidence of clinical impairment or pathology.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd

logger = logging.getLogger("WEDJAT_X.BaselineEngine")

# Standard preflight timepoints for NASA OSD-575
DEFAULT_PREFLIGHT_TIMEPOINTS: List[str] = ["L-92", "L-44", "L-3"]

# Default relative location of the validated master dataset
DEFAULT_DATASET_REL_PATH: str = "cleaned_data/WEDJAT_X_Master_Biomarker_Dataset.csv"

# Mandatory biomedical research disclaimer
DISCLAIMER_TEXT: str = (
    "EXPLORATORY RESEARCH ONLY: The baseline metrics and relative changes reported herein "
    "are statistical reference values derived from preflight research samples (L-92, L-44, L-3). "
    "They do NOT constitute clinically validated medical baselines, and observed biomarker shifts "
    "must NOT be interpreted as medical diagnoses, pathology, or clinical impairment."
)


def calculate_mad(
    values: Sequence[float] | pd.Series | np.ndarray,
    scale: float = 1.0,
) -> float:
    """
    Calculate the Median Absolute Deviation (MAD) of a numeric sequence.

    Formula:
        MAD = median(|X - median(X)|) * scale

    Parameters
    ----------
    values : Sequence[float] | pd.Series | np.ndarray
        Array or sequence of numeric observations. NaNs are dropped.
    scale : float, default=1.0
        Optional scaling factor. Set to 1.4826 to estimate the standard deviation
        under the assumption of a normal distribution. Defaults to 1.0 (unscaled raw MAD).

    Returns
    -------
    float
        Median Absolute Deviation. Returns np.nan if sequence is empty.
        Returns 0.0 if all values are identical or if sample size is 1.
    """
    arr = np.asarray(values, dtype=float)
    clean_arr = arr[~np.isnan(arr)]
    if len(clean_arr) == 0:
        return np.nan
    if len(clean_arr) == 1:
        return 0.0

    med = np.median(clean_arr)
    abs_deviations = np.abs(clean_arr - med)
    mad_val = float(np.median(abs_deviations))
    return float(mad_val * scale)


def calculate_absolute_change(
    value: float,
    baseline: float,
) -> float:
    """
    Calculate absolute delta from baseline: value - baseline.

    Parameters
    ----------
    value : float
        Observed measurement value.
    baseline : float
        Reference baseline value (typically preflight median).

    Returns
    -------
    float
        Absolute difference (value - baseline), or np.nan if either input is missing.
    """
    if pd.isna(value) or pd.isna(baseline):
        return np.nan
    return float(value - baseline)


def calculate_percent_change(
    value: float,
    baseline: float,
    is_log_scale: bool = False,
) -> float:
    """
    Calculate percentage change from baseline.

    For linear scale:
        ((value - baseline) / |baseline|) * 100.0

    For log2 scale (e.g., NPQ Normalized Protein Quantification):
        Since value and baseline are already in log2 scale:
        Linear fold change = 2^(value - baseline)
        Percentage fold change = (2^(value - baseline) - 1) * 100.0

    Parameters
    ----------
    value : float
        Observed measurement value.
    baseline : float
        Reference baseline value (typically preflight median).
    is_log_scale : bool, default=False
        Whether the measurements are already on a log2 scale (e.g. NPQ).

    Returns
    -------
    float
        Percentage change, or np.nan if inputs are invalid or baseline is zero.
    """
    if pd.isna(value) or pd.isna(baseline):
        return np.nan

    delta = value - baseline

    if is_log_scale:
        try:
            return float((np.power(2.0, delta) - 1.0) * 100.0)
        except (OverflowError, FloatingPointError):
            return np.nan

    if baseline == 0:
        if value == 0:
            return 0.0
        return np.nan

    return float((delta / abs(baseline)) * 100.0)


def load_master_dataset(
    filepath: Optional[str | Path] = None,
    only_validated: bool = False,
) -> pd.DataFrame:
    """
    Load and validate the master biomarker dataset.

    Parameters
    ----------
    filepath : str or Path, optional
        Path to WEDJAT_X_Master_Biomarker_Dataset.csv. If None, resolves
        automatically from workspace or package root.
    only_validated : bool, default=False
        If True, filters dataset to records with Validation_Status == 'VALIDATED_MATCH'.
        If False, loads all records and preserves quality status flags.

    Returns
    -------
    pd.DataFrame
        Loaded and verified biomarker dataset.

    Raises
    ------
    FileNotFoundError
        If the dataset file does not exist.
    ValueError
        If required columns are missing from the dataset.
    """
    if filepath is None:
        # Search relative to current working directory and module directory
        candidates = [
            Path(DEFAULT_DATASET_REL_PATH),
            Path.cwd() / DEFAULT_DATASET_REL_PATH,
            Path(__file__).resolve().parent.parent / DEFAULT_DATASET_REL_PATH,
        ]
        resolved_path = None
        for candidate in candidates:
            if candidate.exists():
                resolved_path = candidate
                break
        if resolved_path is None:
            raise FileNotFoundError(
                f"Master dataset not found. Checked: {[str(c) for c in candidates]}"
            )
    else:
        resolved_path = Path(filepath)
        if not resolved_path.exists():
            raise FileNotFoundError(f"Master dataset not found at: {resolved_path}")

    logger.info("Loading master dataset from: %s", resolved_path)
    df = pd.read_csv(resolved_path, low_memory=False)

    required_cols = {
        "Participant_ID",
        "Sample_ID",
        "Timepoint",
        "Timepoint_Phase",
        "Biomarker_Name",
        "Measurement_Value",
        "Measurement_Unit",
        "Panel_Name",
        "Validation_Status",
    }
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        raise ValueError(f"Dataset missing required columns: {sorted(list(missing_cols))}")

    # Ensure numeric conversion for Measurement_Value
    df["Measurement_Value"] = pd.to_numeric(df["Measurement_Value"], errors="coerce")

    if only_validated:
        initial_len = len(df)
        df = df[df["Validation_Status"] == "VALIDATED_MATCH"].copy()
        logger.info(
            "Filtered dataset to %d validated records (excluded %d unvalidated/missing).",
            len(df),
            initial_len - len(df),
        )

    return df


class BaselineEngine:
    """
    Personalized Baseline Engine for individual astronaut biomarker profiles.

    Computes robust personalized preflight baselines (median, MAD) and longitudinal
    deviations across mission phases for any selected astronaut.
    """

    def __init__(
        self,
        data_source: Optional[Union[str, Path, pd.DataFrame]] = None,
        preflight_timepoints: Optional[List[str]] = None,
    ) -> None:
        """
        Initialize the Baseline Engine.

        Parameters
        ----------
        data_source : str, Path, or pd.DataFrame, optional
            Path to the master dataset CSV or a pre-loaded pandas DataFrame.
            If None, loads from cleaned_data/WEDJAT_X_Master_Biomarker_Dataset.csv.
        preflight_timepoints : list of str, optional
            Preflight timepoints used to establish baseline. Defaults to ['L-92', 'L-44', 'L-3'].
        """
        if isinstance(data_source, pd.DataFrame):
            self.df = data_source.copy()
            # Ensure Measurement_Value is numeric
            self.df["Measurement_Value"] = pd.to_numeric(
                self.df["Measurement_Value"], errors="coerce"
            )
        else:
            self.df = load_master_dataset(filepath=data_source, only_validated=False)

        self.preflight_timepoints = list(
            preflight_timepoints or DEFAULT_PREFLIGHT_TIMEPOINTS
        )
        self._available_participants = sorted(
            [str(p) for p in self.df["Participant_ID"].dropna().unique()]
        )

    @property
    def available_participants(self) -> List[str]:
        """List of all participant IDs present in the dataset."""
        return list(self._available_participants)

    def validate_participant(self, participant_id: str) -> None:
        """
        Validate that the requested participant exists in the dataset.

        Parameters
        ----------
        participant_id : str
            Participant ID (e.g. 'C001', 'C002', 'C003', 'C004').

        Raises
        ------
        ValueError
            If participant_id is not in the dataset.
        """
        if participant_id not in self._available_participants:
            raise ValueError(
                f"Participant '{participant_id}' not found. "
                f"Available participants: {self._available_participants}"
            )

    def get_participant_data(
        self,
        participant_id: str,
        only_validated: bool = False,
    ) -> pd.DataFrame:
        """
        Extract all records for a specific astronaut.

        Parameters
        ----------
        participant_id : str
            Astronaut identifier.
        only_validated : bool, default=False
            Whether to restrict to records with Validation_Status == 'VALIDATED_MATCH'.

        Returns
        -------
        pd.DataFrame
            Subset of data for the chosen participant.
        """
        self.validate_participant(participant_id)
        sub = self.df[self.df["Participant_ID"] == participant_id].copy()
        if only_validated:
            sub = sub[sub["Validation_Status"] == "VALIDATED_MATCH"].copy()
        return sub

    def calculate_baseline(
        self,
        participant_id: str,
        min_preflight_samples: int = 1,
    ) -> pd.DataFrame:
        """
        Calculate the personalized baseline for each biomarker for a selected astronaut.

        Uses available preflight measurements (L-92, L-44, L-3).
        Computes median, MAD, mean, standard deviation, and sample availability.

        Parameters
        ----------
        participant_id : str
            Target astronaut ID (e.g. 'C001').
        min_preflight_samples : int, default=1
            Minimum valid preflight measurements required for an active baseline.

        Returns
        -------
        pd.DataFrame
            Summary DataFrame containing baseline parameters for each biomarker:
            - Participant_ID
            - Panel_Name
            - Biomarker_Name
            - Measurement_Unit
            - Platform_Technology
            - Preflight_Sample_Count
            - Preflight_Timepoints_Available
            - Preflight_Timepoints_Missing
            - Baseline_Median
            - Baseline_MAD
            - Baseline_Mean
            - Baseline_Std
            - Baseline_Min
            - Baseline_Max
            - Baseline_Status
            - Scientific_Notice
        """
        self.validate_participant(participant_id)
        pdata = self.get_participant_data(participant_id, only_validated=False)

        # Group by panel and biomarker (handling potential biomarker duplicates across panels)
        group_cols = ["Panel_Name", "Biomarker_Name"]
        grouped = pdata.groupby(group_cols, sort=True)

        baseline_records: List[Dict[str, Union[str, float, int]]] = []

        for (panel_name, biomarker_name), group in grouped:
            unit = str(group["Measurement_Unit"].iloc[0])
            platform = str(group["Platform_Technology"].iloc[0])

            # Filter to preflight timepoints with valid numeric measurements
            pre_rows = group[group["Timepoint"].isin(self.preflight_timepoints)]
            valid_pre = pre_rows[
                pre_rows["Measurement_Value"].notna()
                & (pre_rows["Validation_Status"] == "VALIDATED_MATCH")
            ]

            available_tps = sorted(list(valid_pre["Timepoint"].unique()))
            missing_tps = sorted(list(set(self.preflight_timepoints) - set(available_tps)))

            values = valid_pre["Measurement_Value"].values
            n_samples = len(values)

            if n_samples < min_preflight_samples or n_samples == 0:
                baseline_median = np.nan
                baseline_mad = np.nan
                baseline_mean = np.nan
                baseline_std = np.nan
                baseline_min = np.nan
                baseline_max = np.nan
                status = "INSUFFICIENT_BASELINE"
            else:
                baseline_median = float(np.median(values))
                baseline_mad = float(calculate_mad(values, scale=1.0))
                baseline_mean = float(np.mean(values))
                baseline_std = float(np.std(values, ddof=1)) if n_samples > 1 else np.nan
                baseline_min = float(np.min(values))
                baseline_max = float(np.max(values))

                if n_samples == 1:
                    status = "SINGLE_PREFLIGHT_SAMPLE"
                elif baseline_mad == 0.0:
                    status = "ZERO_MAD"
                else:
                    status = "VALID_BASELINE"

            baseline_records.append({
                "Participant_ID": participant_id,
                "Panel_Name": panel_name,
                "Biomarker_Name": biomarker_name,
                "Measurement_Unit": unit,
                "Platform_Technology": platform,
                "Preflight_Sample_Count": n_samples,
                "Preflight_Timepoints_Available": ", ".join(available_tps) if available_tps else "None",
                "Preflight_Timepoints_Missing": ", ".join(missing_tps) if missing_tps else "None",
                "Baseline_Median": baseline_median,
                "Baseline_MAD": baseline_mad,
                "Baseline_Mean": baseline_mean,
                "Baseline_Std": baseline_std,
                "Baseline_Min": baseline_min,
                "Baseline_Max": baseline_max,
                "Baseline_Status": status,
                "Scientific_Notice": DISCLAIMER_TEXT,
            })

        df_baselines = pd.DataFrame(baseline_records)
        return df_baselines

    def calculate_longitudinal_changes(
        self,
        participant_id: str,
    ) -> pd.DataFrame:
        """
        Calculate absolute and percentage changes from preflight baseline for all
        timepoints of a selected astronaut.

        Parameters
        ----------
        participant_id : str
            Target astronaut ID.

        Returns
        -------
        pd.DataFrame
            Longitudinal records augmented with:
            - Baseline_Median
            - Baseline_MAD
            - Baseline_Status
            - Preflight_Sample_Count
            - Absolute_Change_From_Baseline
            - Percent_Change_From_Baseline
            - Fold_Change_Linear_Percent (for log-scale assays)
            - Scientific_Notice
        """
        self.validate_participant(participant_id)
        pdata = self.get_participant_data(participant_id, only_validated=False)
        baselines = self.calculate_baseline(participant_id)

        # Merge baselines onto participant longitudinal measurements
        merge_keys = ["Participant_ID", "Panel_Name", "Biomarker_Name"]
        merged = pd.merge(pdata, baselines, on=merge_keys, how="left", suffixes=("", "_base"))

        abs_changes: List[float] = []
        pct_changes: List[float] = []
        linear_fold_changes: List[float] = []

        for _, row in merged.iterrows():
            val = row["Measurement_Value"]
            base_med = row["Baseline_Median"]
            unit = str(row.get("Measurement_Unit", ""))
            is_log = "NPQ" in unit.upper()

            if pd.isna(val) or pd.isna(base_med):
                abs_changes.append(np.nan)
                pct_changes.append(np.nan)
                linear_fold_changes.append(np.nan)
            else:
                abs_c = calculate_absolute_change(val, base_med)
                pct_c = calculate_percent_change(val, base_med, is_log_scale=is_log)

                abs_changes.append(abs_c)
                pct_changes.append(pct_c)

                if is_log:
                    # In log2 NPQ: fold change linear percentage
                    linear_fold_changes.append(pct_c)
                else:
                    linear_fold_changes.append(np.nan)

        merged["Absolute_Change_From_Baseline"] = abs_changes
        merged["Percent_Change_From_Baseline"] = pct_changes
        merged["Fold_Change_Linear_Percent"] = linear_fold_changes
        merged["Scientific_Notice"] = DISCLAIMER_TEXT

        # Sort by Timepoint_Order if available
        if "Timepoint_Order" in merged.columns:
            merged = merged.sort_values(["Timepoint_Order", "Panel_Name", "Biomarker_Name"])

        return merged.reset_index(drop=True)
