"""
WEDJAT-X Longitudinal Trajectory & Recovery Modeling Engine
NASA Space Apps Challenge - Astronaut Health Monitoring Prototype

This module implements Phase 2: Longitudinal Recovery Trajectory Modeling for astronaut
biomarkers across preflight, spaceflight, and postflight timepoints (NASA OSD-575 study).

It classifies longitudinal response trends, tracks postflight distance dynamics relative
to personalized preflight baselines, generates panel-level physiological groupings
(Cardiovascular, Immune, Metabolic), and provides descriptive astronaut comparisons.

IMPORTANT SCIENTIFIC & ETHICAL NOTICE:
--------------------------------------
All trajectory labels (APPROACHING_BASELINE, MOVING_AWAY_FROM_BASELINE, STABLE,
FLUCTUATING, INSUFFICIENT_DATA) are exploratory mathematical descriptions of benchtop
laboratory assay values. They DO NOT constitute clinical recovery diagnoses, medical
evaluations, or proof of physiological pathology or cure.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

from intelligence.baseline import (
    BaselineEngine,
    calculate_absolute_change,
    calculate_percent_change,
    calculate_mad,
    load_master_dataset,
    DISCLAIMER_TEXT,
    DEFAULT_PREFLIGHT_TIMEPOINTS,
)

logger = logging.getLogger("WEDJAT_X.TrajectoryEngine")

# Standard NASA OSD-575 Mission Timepoints
PREFLIGHT_TIMEPOINTS: List[str] = ["L-92", "L-44", "L-3"]
POSTFLIGHT_TIMEPOINTS: List[str] = ["R+1", "R+45", "R+82", "R+194"]
ALL_TIMEPOINTS: List[str] = PREFLIGHT_TIMEPOINTS + POSTFLIGHT_TIMEPOINTS

TIMEPOINT_DAYS_MAP: Dict[str, int] = {
    "L-92": -92,
    "L-44": -44,
    "L-3": -3,
    "R+1": 1,
    "R+45": 45,
    "R+82": 82,
    "R+194": 194,
}

# Physiological System Panel Mapping based on OSD-575 assay metadata
PANEL_CATEGORY_MAP: Dict[str, str] = {
    "Cardiovascular EvePanel": "Cardiovascular",
    "Immune EvePanel": "Immune",
    "Immune AlamarPanel": "Immune",
    "Comprehensive Metabolic Panel (CMP)": "Metabolic",
}

# Trajectory Classifications
RECOVERY_APPROACHING = "APPROACHING_BASELINE"
RECOVERY_MOVING_AWAY = "MOVING_AWAY_FROM_BASELINE"
RECOVERY_STABLE = "STABLE"
RECOVERY_FLUCTUATING = "FLUCTUATING"
RECOVERY_INSUFFICIENT = "INSUFFICIENT_DATA"

TREND_INCREASING = "INCREASING"
TREND_DECREASING = "DECREASING"
TREND_STABLE = "STABLE"
TREND_FLUCTUATING = "FLUCTUATING"
TREND_INSUFFICIENT = "INSUFFICIENT_DATA"


def map_panel_to_category(panel_name: str) -> str:
    """
    Map an assay panel to its high-level physiological system category.

    Parameters
    ----------
    panel_name : str
        Assay panel name from dataset.

    Returns
    -------
    str
        'Cardiovascular', 'Immune', or 'Metabolic' (or 'Other').
    """
    return PANEL_CATEGORY_MAP.get(str(panel_name), "Other")


def calculate_baseline_distance(
    value: Optional[float],
    baseline_median: Optional[float],
) -> float:
    """
    Calculate Euclidean distance (absolute deviation) from baseline median: |value - baseline_median|.

    Parameters
    ----------
    value : float or None
        Measurement observation.
    baseline_median : float or None
        Preflight baseline reference median.

    Returns
    -------
    float
        Absolute distance, or np.nan if either input is missing.
    """
    if value is None or baseline_median is None or pd.isna(value) or pd.isna(baseline_median):
        return np.nan
    return float(abs(value - baseline_median))


def classify_trend(
    values: Sequence[Optional[float]],
    rel_tol: float = 0.05,
    abs_tol: float = 1e-6,
) -> str:
    """
    Identify increasing, decreasing, stable, or fluctuating trends across a chronologically
    ordered sequence of numeric observations. NaNs are omitted without interpolation.

    Parameters
    ----------
    values : Sequence[float or None]
        Ordered sequence of measurements.
    rel_tol : float, default=0.05
        Relative tolerance for stability (5% of scale).
    abs_tol : float, default=1e-6
        Absolute tolerance for zero-scale stability.

    Returns
    -------
    str
        One of TREND_INCREASING, TREND_DECREASING, TREND_STABLE, TREND_FLUCTUATING,
        or TREND_INSUFFICIENT.
    """
    arr = np.asarray([v for v in values if v is not None and not pd.isna(v)], dtype=float)
    if len(arr) < 2:
        return TREND_INSUFFICIENT

    span = float(np.max(arr) - np.min(arr))
    scale = max(float(np.median(np.abs(arr))), abs_tol)

    # Check stability
    if span <= abs_tol or (span / scale) <= rel_tol:
        return TREND_STABLE

    # Differences between consecutive valid points
    diffs = np.diff(arr)
    eps = max(scale * rel_tol * 0.25, abs_tol)

    is_non_decreasing = bool(np.all(diffs >= -eps))
    is_non_increasing = bool(np.all(diffs <= eps))
    has_meaningful_increase = bool(np.sum(diffs[diffs > eps]) > eps)
    has_meaningful_decrease = bool(np.sum(-diffs[diffs < -eps]) > eps)

    if is_non_decreasing and has_meaningful_increase:
        return TREND_INCREASING
    if is_non_increasing and has_meaningful_decrease:
        return TREND_DECREASING

    return TREND_FLUCTUATING


def classify_recovery_trajectory(
    baseline_median: Optional[float],
    postflight_values: Sequence[Optional[float]],
    baseline_mad: Optional[float] = None,
    rel_tol: float = 0.10,
    abs_tol: float = 1e-6,
) -> str:
    """
    Classify postflight trajectory relative to individual baseline as:
    APPROACHING_BASELINE, MOVING_AWAY_FROM_BASELINE, STABLE, FLUCTUATING, or INSUFFICIENT_DATA.

    Parameters
    ----------
    baseline_median : float or None
        Preflight baseline median.
    postflight_values : Sequence[float or None]
        Postflight measurements ordered chronologically: [R+1, R+45, R+82, R+194].
    baseline_mad : float, optional
        Preflight MAD, used to scale distance stability thresholds.
    rel_tol : float, default=0.10
        Relative tolerance (fraction of baseline or distance) for stability classification.
    abs_tol : float, default=1e-6
        Absolute tolerance threshold.

    Returns
    -------
    str
        One of RECOVERY_APPROACHING, RECOVERY_MOVING_AWAY, RECOVERY_STABLE,
        RECOVERY_FLUCTUATING, or RECOVERY_INSUFFICIENT.
    """
    if baseline_median is None or pd.isna(baseline_median):
        return RECOVERY_INSUFFICIENT

    clean_pairs: List[Tuple[int, float]] = []
    for idx, v in enumerate(postflight_values):
        if v is not None and not pd.isna(v):
            clean_pairs.append((idx, float(v)))

    if len(clean_pairs) < 2:
        return RECOVERY_INSUFFICIENT

    vals = np.array([p[1] for p in clean_pairs], dtype=float)
    distances = np.abs(vals - baseline_median)

    # Determine scale for tolerance
    base_scale = abs(baseline_median) if abs(baseline_median) > abs_tol else abs_tol
    if baseline_mad is not None and not pd.isna(baseline_mad) and baseline_mad > abs_tol:
        stability_threshold = max(1.5 * baseline_mad, base_scale * rel_tol)
    else:
        stability_threshold = max(base_scale * rel_tol, abs_tol)

    # If all postflight measurements remain within nominal baseline deviation:
    if np.all(distances <= stability_threshold):
        return RECOVERY_STABLE

    # Analyze changes in distance over postflight recovery
    d_initial = distances[0]
    d_final = distances[-1]
    net_change = d_final - d_initial

    dist_diffs = np.diff(distances)
    noise_tol = max(np.max(distances) * 0.15, abs_tol)

    is_predominantly_decreasing = bool(
        net_change < -noise_tol and np.all(dist_diffs <= noise_tol)
    )
    is_predominantly_increasing = bool(
        net_change > noise_tol and np.all(dist_diffs >= -noise_tol)
    )

    if is_predominantly_decreasing:
        return RECOVERY_APPROACHING
    if is_predominantly_increasing:
        return RECOVERY_MOVING_AWAY

    # Check if distance changes are flat throughout postflight
    if (np.max(distances) - np.min(distances)) <= noise_tol:
        return RECOVERY_STABLE

    return RECOVERY_FLUCTUATING


@dataclass
class TrajectorySummary:
    """Detailed summary of a biomarker's longitudinal trajectory."""
    participant_id: str
    biomarker_name: str
    panel_name: str
    category: str
    measurement_unit: str
    baseline_median: Optional[float]
    baseline_mad: Optional[float]
    preflight_sample_count: int
    r1_value: Optional[float]
    r45_value: Optional[float]
    r82_value: Optional[float]
    r194_value: Optional[float]
    r1_distance: Optional[float]
    r45_distance: Optional[float]
    r82_distance: Optional[float]
    r194_distance: Optional[float]
    postflight_recovery_class: str
    overall_trend: str
    trajectory_explanation: str
    scientific_notice: str = DISCLAIMER_TEXT

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class LongitudinalTrajectoryEngine:
    """
    Engine for longitudinal trajectory modeling and postflight recovery analysis.

    Reuses Phase 1 BaselineEngine to evaluate biomarker shifts across mission phases,
    detect recovery dynamics toward baseline, and summarize system-level patterns.
    """

    def __init__(
        self,
        baseline_engine: Optional[BaselineEngine] = None,
        data_source: Optional[Union[str, Path, pd.DataFrame]] = None,
    ) -> None:
        """
        Initialize the Trajectory Engine.

        Parameters
        ----------
        baseline_engine : BaselineEngine, optional
            Pre-configured BaselineEngine instance.
        data_source : str, Path, or pd.DataFrame, optional
            Path to master dataset or pre-loaded DataFrame if baseline_engine is None.
        """
        if baseline_engine is not None:
            self.baseline_engine = baseline_engine
        else:
            self.baseline_engine = BaselineEngine(data_source=data_source)

        self._available_participants = self.baseline_engine.available_participants

    @property
    def available_participants(self) -> List[str]:
        """Available astronauts in the dataset."""
        return list(self._available_participants)

    def analyze_participant(self, participant_id: str) -> pd.DataFrame:
        """
        Analyze longitudinal trajectories and postflight recovery for all biomarkers
        of a selected astronaut.

        Parameters
        ----------
        participant_id : str
            Astronaut ID (e.g. 'C001').

        Returns
        -------
        pd.DataFrame
            Summary DataFrame containing baseline parameters, timepoint observations,
            distances, recovery classification, overall trend, and explanations.
        """
        self.baseline_engine.validate_participant(participant_id)

        # Retrieve baselines and longitudinal records from Phase 1 BaselineEngine
        df_base = self.baseline_engine.calculate_baseline(participant_id)
        df_long = self.baseline_engine.calculate_longitudinal_changes(participant_id)

        # Pivot longitudinal measurements to access timepoints as columns
        pivoted_vals = df_long.pivot_table(
            index=["Panel_Name", "Biomarker_Name"],
            columns="Timepoint",
            values="Measurement_Value",
            aggfunc="first",
        ).reset_index()

        # Merge with baseline metadata
        merged = pd.merge(df_base, pivoted_vals, on=["Panel_Name", "Biomarker_Name"], how="left")

        records: List[Dict[str, Any]] = []

        for _, row in merged.iterrows():
            panel = str(row["Panel_Name"])
            biomarker = str(row["Biomarker_Name"])
            unit = str(row.get("Measurement_Unit", ""))
            cat = map_panel_to_category(panel)

            base_med = row.get("Baseline_Median")
            base_mad = row.get("Baseline_MAD")
            n_pre = int(row.get("Preflight_Sample_Count", 0))

            # Timepoint measurements
            l92_val = row.get("L-92", np.nan)
            l44_val = row.get("L-44", np.nan)
            l3_val = row.get("L-3", np.nan)
            r1_val = row.get("R+1", np.nan)
            r45_val = row.get("R+45", np.nan)
            r82_val = row.get("R+82", np.nan)
            r194_val = row.get("R+194", np.nan)

            all_series = [l92_val, l44_val, l3_val, r1_val, r45_val, r82_val, r194_val]
            post_series = [r1_val, r45_val, r82_val, r194_val]

            # Distances from baseline
            r1_dist = calculate_baseline_distance(r1_val, base_med)
            r45_dist = calculate_baseline_distance(r45_val, base_med)
            r82_dist = calculate_baseline_distance(r82_val, base_med)
            r194_dist = calculate_baseline_distance(r194_val, base_med)

            # Classify overall trend across all available points
            overall_trend = classify_trend(all_series)

            # Classify postflight recovery trajectory
            rec_class = classify_recovery_trajectory(
                baseline_median=base_med,
                postflight_values=post_series,
                baseline_mad=base_mad,
            )

            # Generate scientific explanation
            explanation = self._build_trajectory_explanation(
                participant_id=participant_id,
                biomarker=biomarker,
                panel=panel,
                category=cat,
                unit=unit,
                base_med=base_med,
                base_mad=base_mad,
                n_pre=n_pre,
                r1_val=r1_val,
                r194_val=r194_val,
                r1_dist=r1_dist,
                r194_dist=r194_dist,
                rec_class=rec_class,
                overall_trend=overall_trend,
            )

            records.append({
                "Participant_ID": participant_id,
                "Biomarker_Name": biomarker,
                "Panel_Name": panel,
                "Biomarker_Category": cat,
                "Measurement_Unit": unit,
                "Baseline_Median": base_med,
                "Baseline_MAD": base_mad,
                "Preflight_Sample_Count": n_pre,
                "L-92_Value": l92_val,
                "L-44_Value": l44_val,
                "L-3_Value": l3_val,
                "R+1_Value": r1_val,
                "R+45_Value": r45_val,
                "R+82_Value": r82_val,
                "R+194_Value": r194_val,
                "R+1_Distance": r1_dist,
                "R+45_Distance": r45_dist,
                "R+82_Distance": r82_dist,
                "R+194_Distance": r194_dist,
                "Postflight_Recovery_Class": rec_class,
                "Overall_Trend": overall_trend,
                "Trajectory_Explanation": explanation,
                "Scientific_Notice": DISCLAIMER_TEXT,
            })

        df_res = pd.DataFrame(records)
        return df_res.sort_values(["Biomarker_Category", "Panel_Name", "Biomarker_Name"]).reset_index(drop=True)

    def analyze_all_participants(self) -> pd.DataFrame:
        """
        Execute trajectory modeling across all available astronauts in the study.

        Returns
        -------
        pd.DataFrame
            Concatenated DataFrame of all participant trajectories.
        """
        dfs = [self.analyze_participant(p) for p in self.available_participants]
        return pd.concat(dfs, ignore_index=True)

    def generate_panel_summary(
        self,
        df_trajectories: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Generate physiological panel-level summary of recovery trajectories.

        Parameters
        ----------
        df_trajectories : pd.DataFrame, optional
            Output of analyze_all_participants() or analyze_participant().

        Returns
        -------
        pd.DataFrame
            Summary table of counts and percentages per system panel.
        """
        if df_trajectories is None:
            df_trajectories = self.analyze_all_participants()

        grouped = (
            df_trajectories.groupby(
                ["Biomarker_Category", "Panel_Name", "Postflight_Recovery_Class"]
            )
            .size()
            .reset_index(name="Biomarker_Count")
        )

        # Compute percentage within each panel
        total_per_panel = grouped.groupby("Panel_Name")["Biomarker_Count"].transform("sum")
        grouped["Percent_Of_Panel"] = (grouped["Biomarker_Count"] / total_per_panel * 100.0).round(2)

        return grouped.sort_values(["Biomarker_Category", "Panel_Name", "Postflight_Recovery_Class"])

    def generate_comparative_summary(
        self,
        df_trajectories: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Generate descriptive comparative summary across all four astronaut participants.
        Shows sample completeness, missingness, and trajectory class proportions.

        Parameters
        ----------
        df_trajectories : pd.DataFrame, optional
            Output of analyze_all_participants().

        Returns
        -------
        pd.DataFrame
            Participant-level comparison matrix.
        """
        if df_trajectories is None:
            df_trajectories = self.analyze_all_participants()

        comp_records = []
        for p in sorted(df_trajectories["Participant_ID"].unique()):
            sub = df_trajectories[df_trajectories["Participant_ID"] == p]
            total_bms = len(sub)

            counts = sub["Postflight_Recovery_Class"].value_counts().to_dict()

            n_approaching = counts.get(RECOVERY_APPROACHING, 0)
            n_away = counts.get(RECOVERY_MOVING_AWAY, 0)
            n_stable = counts.get(RECOVERY_STABLE, 0)
            n_fluctuating = counts.get(RECOVERY_FLUCTUATING, 0)
            n_insufficient = counts.get(RECOVERY_INSUFFICIENT, 0)

            comp_records.append({
                "Participant_ID": p,
                "Total_Biomarkers": total_bms,
                "Approaching_Baseline_Count": n_approaching,
                "Approaching_Baseline_Pct": round(n_approaching / total_bms * 100.0, 2),
                "Moving_Away_Count": n_away,
                "Moving_Away_Pct": round(n_away / total_bms * 100.0, 2),
                "Stable_Count": n_stable,
                "Stable_Pct": round(n_stable / total_bms * 100.0, 2),
                "Fluctuating_Count": n_fluctuating,
                "Fluctuating_Pct": round(n_fluctuating / total_bms * 100.0, 2),
                "Insufficient_Data_Count": n_insufficient,
                "Insufficient_Data_Pct": round(n_insufficient / total_bms * 100.0, 2),
                "Scientific_Notice": (
                    "Descriptive comparative analysis only (N=4). "
                    "Population-level statistical inference is unsupported."
                ),
            })

        return pd.DataFrame(comp_records)

    def _build_trajectory_explanation(
        self,
        participant_id: str,
        biomarker: str,
        panel: str,
        category: str,
        unit: str,
        base_med: Optional[float],
        base_mad: Optional[float],
        n_pre: int,
        r1_val: Optional[float],
        r194_val: Optional[float],
        r1_dist: Optional[float],
        r194_dist: Optional[float],
        rec_class: str,
        overall_trend: str,
    ) -> str:
        """Build transparent human-readable explanation of trajectory findings."""
        hdr = f"Participant {participant_id} | {biomarker} ({panel} - {category}): "

        if rec_class == RECOVERY_INSUFFICIENT:
            return (
                f"{hdr}Insufficient baseline or postflight measurements to evaluate recovery trajectory. "
                f"Preflight samples: n={n_pre}. Class: {rec_class}. NOTICE: {DISCLAIMER_TEXT}"
            )

        med_str = f"{base_med:.4g} {unit}" if base_med is not None else "N/A"
        r1_str = f"{r1_val:.4g} {unit}" if r1_val is not None and not pd.isna(r1_val) else "Missing"
        r194_str = f"{r194_val:.4g} {unit}" if r194_val is not None and not pd.isna(r194_val) else "Missing"
        r1_d_str = f"{r1_dist:.4g} {unit}" if r1_dist is not None and not pd.isna(r1_dist) else "N/A"
        r194_d_str = f"{r194_dist:.4g} {unit}" if r194_dist is not None and not pd.isna(r194_dist) else "N/A"

        if rec_class == RECOVERY_STABLE:
            return (
                f"{hdr}Postflight measurements remain within nominal preflight variation throughout recovery "
                f"(Baseline median: {med_str}). Postflight distance at R+1: {r1_d_str}, at R+194: {r194_d_str}. "
                f"Trajectory: {rec_class}. Overall Trend: {overall_trend}. NOTICE: {DISCLAIMER_TEXT}"
            )

        if rec_class == RECOVERY_APPROACHING:
            return (
                f"{hdr}Biomarker demonstrates return toward preflight baseline across recovery. "
                f"Observed at R+1: {r1_str} (distance: {r1_d_str}), resolving toward R+194: {r194_str} "
                f"(distance: {r194_d_str}) relative to baseline median: {med_str}. "
                f"Trajectory: {rec_class}. Overall Trend: {overall_trend}. NOTICE: {DISCLAIMER_TEXT}"
            )

        if rec_class == RECOVERY_MOVING_AWAY:
            return (
                f"{hdr}Biomarker exhibits increasing departure from preflight baseline over postflight time. "
                f"Distance increased from {r1_d_str} (at R+1: {r1_str}) to {r194_d_str} (at R+194: {r194_str}) "
                f"relative to baseline median: {med_str}. "
                f"Trajectory: {rec_class}. Overall Trend: {overall_trend}. NOTICE: {DISCLAIMER_TEXT}"
            )

        # Fluctuating
        return (
            f"{hdr}Biomarker distance exhibits non-monotonic oscillation relative to baseline median {med_str}. "
            f"Distance at R+1: {r1_d_str}, at R+194: {r194_d_str}. "
            f"Trajectory: {rec_class}. Overall Trend: {overall_trend}. NOTICE: {DISCLAIMER_TEXT}"
        )

    def generate_visualizations(
        self,
        output_dir: Optional[Union[str, Path]] = None,
        df_trajectories: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Path]:
        """
        Generate trajectory plots using Plotly (interactive HTML) and Matplotlib (static figures).

        Parameters
        ----------
        output_dir : str or Path, optional
            Destination directory. Defaults to reports/figures/trajectory/.
        df_trajectories : pd.DataFrame, optional
            Trajectories DataFrame.

        Returns
        -------
        dict of str -> Path
            Paths of generated visualization files.
        """
        if output_dir is None:
            out_path = Path("reports/figures/trajectory")
        else:
            out_path = Path(output_dir)

        out_path.mkdir(parents=True, exist_ok=True)

        if df_trajectories is None:
            df_trajectories = self.analyze_all_participants()

        generated_files: Dict[str, Path] = {}

        # 1. Panel-Level Trend Summaries (Plotly interactive & Matplotlib static)
        panel_sum = self.generate_panel_summary(df_trajectories)
        html_panel = out_path / "panel_level_trend_summaries.html"
        png_panel = out_path / "panel_level_trend_summaries.png"

        import plotly.express as px
        import plotly.graph_objects as go
        import matplotlib.pyplot as plt

        # Plotly Panel Summary
        fig_panel = px.bar(
            panel_sum,
            x="Panel_Name",
            y="Biomarker_Count",
            color="Postflight_Recovery_Class",
            barmode="group",
            facet_col="Biomarker_Category",
            title="WEDJAT-X Exploratory Postflight Recovery Trajectories by Panel (N=4 Astronauts)",
            labels={"Biomarker_Count": "Number of Biomarkers", "Panel_Name": "Assay Panel"},
            color_discrete_map={
                RECOVERY_APPROACHING: "#2ecc71",
                RECOVERY_MOVING_AWAY: "#e74c3c",
                RECOVERY_STABLE: "#3498db",
                RECOVERY_FLUCTUATING: "#f39c12",
                RECOVERY_INSUFFICIENT: "#95a5a6",
            },
        )
        fig_panel.update_layout(template="plotly_white")
        fig_panel.write_html(str(html_panel))
        generated_files["panel_summary_html"] = html_panel

        # Matplotlib Panel Summary
        fig_m, ax_m = plt.subplots(figsize=(10, 6))
        pivot_panel = panel_sum.pivot_table(
            index="Panel_Name",
            columns="Postflight_Recovery_Class",
            values="Biomarker_Count",
            fill_value=0,
        )
        pivot_panel.plot(kind="bar", stacked=True, ax=ax_m, colormap="viridis")
        ax_m.set_title("Biomarker Postflight Recovery Classification by Panel")
        ax_m.set_ylabel("Count of Biomarkers")
        ax_m.set_xlabel("Assay Panel")
        plt.xticks(rotation=25, ha="right")
        plt.tight_layout()
        fig_m.savefig(str(png_panel), dpi=200)
        plt.close(fig_m)
        generated_files["panel_summary_png"] = png_panel

        # 2. Participant Comparison (Plotly interactive & Matplotlib static)
        comp_df = self.generate_comparative_summary(df_trajectories)
        html_comp = out_path / "participant_comparison.html"
        png_comp = out_path / "participant_comparison.png"

        fig_comp = px.bar(
            comp_df,
            x="Participant_ID",
            y=["Approaching_Baseline_Pct", "Moving_Away_Pct", "Stable_Pct", "Fluctuating_Pct", "Insufficient_Data_Pct"],
            title="Individual Astronaut Trajectory Proportions (Descriptive Comparison, N=4)",
            barmode="stack",
            labels={"value": "Percentage of Biomarkers (%)", "Participant_ID": "Astronaut"},
        )
        fig_comp.update_layout(template="plotly_white")
        fig_comp.write_html(str(html_comp))
        generated_files["participant_comparison_html"] = html_comp

        fig_cm, ax_cm = plt.subplots(figsize=(8, 5))
        comp_plot_data = comp_df.set_index("Participant_ID")[[
            "Approaching_Baseline_Pct", "Moving_Away_Pct", "Stable_Pct", "Fluctuating_Pct", "Insufficient_Data_Pct"
        ]]
        comp_plot_data.plot(kind="bar", stacked=True, ax=ax_cm, colormap="tab10")
        ax_cm.set_title("Astronaut Biomarker Recovery Profiles (Descriptive Comparison)")
        ax_cm.set_ylabel("Percentage (%)")
        ax_cm.set_xlabel("Astronaut ID")
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.tight_layout()
        fig_cm.savefig(str(png_comp), dpi=200)
        plt.close(fig_cm)
        generated_files["participant_comparison_png"] = png_comp

        # 3. Individual Biomarker Trajectory Plots with Preflight Baseline Reference Lines
        # Highlight key benchmarks: CRP (Cardiovascular/Immune), Fibrinogen, Glucose
        benchmark_biomarkers = ["CRP", "Fibrinogen", "GLUCOSE"]
        df_master = self.baseline_engine.df

        for bm in benchmark_biomarkers:
            bm_data = df_master[df_master["Biomarker_Name"] == bm].copy()
            if len(bm_data) == 0:
                continue

            bm_html = out_path / f"trajectory_{bm}.html"
            bm_png = out_path / f"trajectory_{bm}.png"

            # Plotly interactive
            fig_bm = go.Figure()
            colors = {"C001": "#e74c3c", "C002": "#3498db", "C003": "#2ecc71", "C004": "#9b59b6"}

            for p in self.available_participants:
                p_sub = bm_data[bm_data["Participant_ID"] == p].sort_values("Days_Relative_To_Return")
                if len(p_sub) == 0:
                    continue

                unit = p_sub["Measurement_Unit"].iloc[0]
                # Preflight baseline
                p_base = df_trajectories[(df_trajectories["Participant_ID"] == p) & (df_trajectories["Biomarker_Name"] == bm)]
                base_val = p_base["Baseline_Median"].values[0] if len(p_base) > 0 else np.nan

                # Trajectory curve
                fig_bm.add_trace(go.Scatter(
                    x=p_sub["Days_Relative_To_Return"],
                    y=p_sub["Measurement_Value"],
                    mode="lines+markers",
                    name=f"{p} (Observed)",
                    line=dict(color=colors.get(p, "#333333"), width=2),
                ))

                # Baseline reference line
                if not pd.isna(base_val):
                    fig_bm.add_trace(go.Scatter(
                        x=p_sub["Days_Relative_To_Return"],
                        y=[base_val] * len(p_sub),
                        mode="lines",
                        name=f"{p} Baseline ({base_val:.3g})",
                        line=dict(color=colors.get(p, "#333333"), dash="dash", width=1),
                    ))

            fig_bm.add_vrect(
                x0=0, x1=194,
                fillcolor="lightgrey", opacity=0.2,
                layer="below", line_width=0,
                annotation_text="Postflight Recovery Window",
            )

            fig_bm.update_layout(
                title=f"Longitudinal Trajectory: {bm} across Preflight & Postflight (All Astronauts)",
                xaxis_title="Mission Days Relative to Splashdown (Return = 0)",
                yaxis_title=f"Measurement Value ({unit})",
                template="plotly_white",
            )
            fig_bm.write_html(str(bm_html))
            generated_files[f"trajectory_{bm}_html"] = bm_html

            # Matplotlib static
            fig_stat, ax_stat = plt.subplots(figsize=(9, 5))
            for p in self.available_participants:
                p_sub = bm_data[bm_data["Participant_ID"] == p].sort_values("Days_Relative_To_Return")
                if len(p_sub) == 0:
                    continue
                p_base = df_trajectories[(df_trajectories["Participant_ID"] == p) & (df_trajectories["Biomarker_Name"] == bm)]
                base_val = p_base["Baseline_Median"].values[0] if len(p_base) > 0 else np.nan

                ax_stat.plot(
                    p_sub["Days_Relative_To_Return"],
                    p_sub["Measurement_Value"],
                    marker="o",
                    label=f"{p} Observed",
                    color=colors.get(p, "#333333"),
                )
                if not pd.isna(base_val):
                    ax_stat.axhline(base_val, linestyle="--", color=colors.get(p, "#333333"), alpha=0.5)

            ax_stat.axvspan(0, 194, color="lightgray", alpha=0.3, label="Postflight Recovery Window")
            ax_stat.set_title(f"Longitudinal Trajectory: {bm} (N=4 Astronauts)")
            ax_stat.set_xlabel("Days Relative to Splashdown")
            ax_stat.set_ylabel(f"Concentration ({unit})")
            ax_stat.legend(bbox_to_anchor=(1.02, 1), loc='upper left')
            plt.tight_layout()
            fig_stat.savefig(str(bm_png), dpi=200)
            plt.close(fig_stat)
            generated_files[f"trajectory_{bm}_png"] = bm_png

        logger.info("Generated %d visualization files in %s", len(generated_files), out_path)
        return generated_files

    def export_report(
        self,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Path:
        """
        Export comprehensive multi-tab Excel report of longitudinal trajectories.

        Parameters
        ----------
        output_path : str or Path, optional
            Destination excel path. Defaults to reports/trajectory_analysis.xlsx.

        Returns
        -------
        Path
            Path to the written workbook.
        """
        if output_path is None:
            resolved_path = Path("reports/trajectory_analysis.xlsx")
        else:
            resolved_path = Path(output_path)

        resolved_path.parent.mkdir(parents=True, exist_ok=True)

        df_trajectories = self.analyze_all_participants()
        df_panel_sum = self.generate_panel_summary(df_trajectories)
        df_comp = self.generate_comparative_summary(df_trajectories)

        # Methodology and Disclaimer Text
        methodology_df = pd.DataFrame([
            {"Parameter": "Study Dataset", "Description": "NASA OSD-575 (SpaceX Inspiration4 Mission)"},
            {"Parameter": "Sample Size", "Description": "N = 4 human astronaut participants (C001, C002, C003, C004)"},
            {"Parameter": "Assay Nature", "Description": "Benchtop biochemical laboratory assay data from serum biospecimens; not wearable telemetry."},
            {"Parameter": "Preflight Baseline", "Description": "Individual preflight median derived from L-92, L-44, and L-3 research samples."},
            {"Parameter": "Trajectory Classes", "Description": "APPROACHING_BASELINE, MOVING_AWAY_FROM_BASELINE, STABLE, FLUCTUATING, INSUFFICIENT_DATA."},
            {"Parameter": "Ethics Notice", "Description": DISCLAIMER_TEXT},
        ])

        with pd.ExcelWriter(resolved_path, engine="openpyxl") as writer:
            df_trajectories.to_excel(writer, sheet_name="All_Trajectories", index=False)
            df_panel_sum.to_excel(writer, sheet_name="Panel_Summaries", index=False)
            df_comp.to_excel(writer, sheet_name="Comparative_Summary", index=False)
            methodology_df.to_excel(writer, sheet_name="Methodology_Disclaimer", index=False)

        logger.info("Successfully exported trajectory analysis report to %s", resolved_path)
        return resolved_path
