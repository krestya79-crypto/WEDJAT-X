"""
Phase 7: Individual Baseline Analysis
Explores each participant's biomarker longitudinal trajectories relative to preflight baseline.
Calculates absolute changes, percentage changes, and flight response dynamics.
Adheres strictly to biomedical ethics: does not claim clinical diagnoses.
Generates reports/baseline_analysis.xlsx and audit_logs/07_baseline_analysis.log.
"""
import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import get_file_path, setup_logger, REPORTS_DIR, CLEANED_DATA_DIR, AUDIT_LOGS_DIR

logger = setup_logger("Phase7_BaselineAnalysis", "07_baseline_analysis.log")

EXPECTED_PARTICIPANTS = ["C001", "C002", "C003", "C004"]

DISCLAIMER_TEXT = (
    "EXPLORATORY RESEARCH ONLY: The baseline metrics and relative changes reported herein "
    "are statistical reference values derived from preflight research samples (L-92, L-44, L-3). "
    "They do NOT constitute clinically validated medical baselines, and observed biomarker shifts "
    "must NOT be interpreted as medical diagnoses, pathology, or clinical impairment."
)

def run_baseline_analysis():
    logger.info("Starting Phase 7: Individual Baseline Analysis")
    
    master_path = CLEANED_DATA_DIR / "WEDJAT_X_Master_Biomarker_Dataset.csv"
    if not master_path.exists():
        raise FileNotFoundError(f"Master dataset not found at {master_path}. Run Phase 6 first.")
        
    df_master = pd.read_csv(master_path)
    
    # Filter to validated measurements
    valid_data = df_master[df_master["Validation_Status"] == "VALIDATED_MATCH"].copy()
    valid_data["Measurement_Value"] = pd.to_numeric(valid_data["Measurement_Value"], errors="coerce")
    
    baseline_records = []
    longitudinal_trajectory_records = []
    participant_summary_records = []
    
    # Preflight timepoints
    preflight_tps = ["L-92", "L-44", "L-3"]
    postflight_tps = ["R+1", "R+45", "R+82", "R+194"]
    
    grouped = valid_data.groupby(["Participant_ID", "Panel_Name", "Biomarker_Name"])
    
    for (participant, panel, biomarker), group in grouped:
        unit = group["Measurement_Unit"].iloc[0]
        tech = group["Platform_Technology"].iloc[0]
        
        # Sort by timepoint order
        group = group.sort_values("Timepoint_Order")
        
        # Available timepoints
        avail_tps = set(group["Timepoint"])
        all_expected_tps = set(preflight_tps + postflight_tps)
        missing_tps = sorted(list(all_expected_tps - avail_tps))
        
        # Preflight measurements
        pre_group = group[group["Timepoint"].isin(preflight_tps)]
        earliest_row = pre_group.sort_values("Timepoint_Order").head(1)
        
        if len(earliest_row) > 0:
            earliest_tp = earliest_row["Timepoint"].values[0]
            earliest_val = earliest_row["Measurement_Value"].values[0]
        else:
            earliest_tp = "None"
            earliest_val = np.nan
            
        pre_vals = pre_group["Measurement_Value"].dropna()
        preflight_mean = pre_vals.mean() if len(pre_vals) > 0 else np.nan
        preflight_std = pre_vals.std() if len(pre_vals) > 1 else np.nan
        preflight_cv = (preflight_std / preflight_mean * 100) if (pd.notna(preflight_mean) and preflight_mean != 0 and pd.notna(preflight_std)) else np.nan
        
        # Postflight measurements
        r1_row = group[group["Timepoint"] == "R+1"]
        r1_val = r1_row["Measurement_Value"].values[0] if len(r1_row) > 0 else np.nan
        
        r45_row = group[group["Timepoint"] == "R+45"]
        r45_val = r45_row["Measurement_Value"].values[0] if len(r45_row) > 0 else np.nan
        
        r82_row = group[group["Timepoint"] == "R+82"]
        r82_val = r82_row["Measurement_Value"].values[0] if len(r82_row) > 0 else np.nan
        
        r194_row = group[group["Timepoint"] == "R+194"]
        r194_val = r194_row["Measurement_Value"].values[0] if len(r194_row) > 0 else np.nan
        
        # Acute flight delta (R+1 vs Preflight Mean)
        acute_abs_delta = (r1_val - preflight_mean) if (pd.notna(r1_val) and pd.notna(preflight_mean)) else np.nan
        
        # Percent change
        is_log_scale = ("NPQ" in str(unit).upper())
        if pd.notna(acute_abs_delta) and pd.notna(preflight_mean) and preflight_mean != 0:
            if is_log_scale:
                # In log2 NPQ, difference is already log2 fold-change
                acute_pct_change = (2 ** acute_abs_delta - 1) * 100
                delta_interpretation = f"log2(FC)={acute_abs_delta:.3f} (~{acute_pct_change:+.1f}% linear fold change)"
            else:
                acute_pct_change = (acute_abs_delta / abs(preflight_mean)) * 100
                delta_interpretation = f"{acute_pct_change:+.1f}% linear change"
        else:
            acute_pct_change = np.nan
            delta_interpretation = "Cannot calculate (missing or zero baseline)"
            
        # Recovery trajectory classification
        if pd.isna(acute_abs_delta):
            trajectory = "INCOMPLETE_DATA"
        elif abs(acute_abs_delta) < (0.15 * abs(preflight_mean) if pd.notna(preflight_mean) and preflight_mean != 0 else 0.5):
            trajectory = "STABLE_ACROSS_FLIGHT"
        elif acute_abs_delta > 0:
            # Elevated at R+1
            if pd.notna(r194_val) and pd.notna(preflight_mean) and abs(r194_val - preflight_mean) <= abs(acute_abs_delta * 0.5):
                trajectory = "ACUTE_ELEVATION_WITH_RECOVERY"
            else:
                trajectory = "SUSTAINED_POSTFLIGHT_ELEVATION"
        else:
            # Depressed at R+1
            if pd.notna(r194_val) and pd.notna(preflight_mean) and abs(r194_val - preflight_mean) <= abs(acute_abs_delta * 0.5):
                trajectory = "ACUTE_SUPPRESSION_WITH_RECOVERY"
            else:
                trajectory = "SUSTAINED_POSTFLIGHT_SUPPRESSION"
                
        baseline_records.append({
            "Participant_ID": participant,
            "Panel_Name": panel,
            "Biomarker_Name": biomarker,
            "Measurement_Unit": unit,
            "Platform_Technology": tech,
            "Earliest_Available_Timepoint": earliest_tp,
            "Earliest_Available_Value": earliest_val,
            "Preflight_Mean_Baseline": round(preflight_mean, 4) if pd.notna(preflight_mean) else np.nan,
            "Preflight_Std": round(preflight_std, 4) if pd.notna(preflight_std) else np.nan,
            "Preflight_CV_Percent": round(preflight_cv, 2) if pd.notna(preflight_cv) else np.nan,
            "R+1_Value": r1_val,
            "Acute_Flight_Delta_Abs": round(acute_abs_delta, 4) if pd.notna(acute_abs_delta) else np.nan,
            "Acute_Flight_Percent_Change": round(acute_pct_change, 2) if pd.notna(acute_pct_change) else np.nan,
            "Delta_Metric_Interpretation": delta_interpretation,
            "Late_Recovery_R+194_Value": r194_val,
            "Longitudinal_Trajectory_Class": trajectory,
            "Missing_Timepoints": ", ".join(missing_tps) if missing_tps else "None",
            "Scientific_Notice": "Research exploratory baseline only; not a clinical baseline."
        })
        
        # Longitudinal detailed records (per timepoint)
        for _, row in group.iterrows():
            tp = row["Timepoint"]
            v = row["Measurement_Value"]
            abs_change = (v - preflight_mean) if (pd.notna(v) and pd.notna(preflight_mean)) else np.nan
            pct_change = ((abs_change / abs(preflight_mean)) * 100) if (pd.notna(abs_change) and pd.notna(preflight_mean) and preflight_mean != 0) else np.nan
            
            longitudinal_trajectory_records.append({
                "Participant_ID": participant,
                "Sample_ID": row["Sample_ID"],
                "Timepoint": tp,
                "Timepoint_Phase": row["Timepoint_Phase"],
                "Days_Relative_To_Return": row["Days_Relative_To_Return"],
                "Panel_Name": panel,
                "Biomarker_Name": biomarker,
                "Measurement_Value": v,
                "Measurement_Unit": unit,
                "Preflight_Baseline_Mean": round(preflight_mean, 4) if pd.notna(preflight_mean) else np.nan,
                "Absolute_Change_From_Baseline": round(abs_change, 4) if pd.notna(abs_change) else np.nan,
                "Percent_Change_From_Baseline": round(pct_change, 2) if pd.notna(pct_change) else np.nan,
                "Validation_Status": row["Validation_Status"]
            })
            
    df_baseline = pd.DataFrame(baseline_records)
    df_long = pd.DataFrame(longitudinal_trajectory_records)
    
    # Participant Summary Table
    part_summary = []
    for participant in EXPECTED_PARTICIPANTS:
        p_base = df_baseline[df_baseline["Participant_ID"] == participant]
        traj_counts = p_base["Longitudinal_Trajectory_Class"].value_counts().to_dict()
        part_summary.append({
            "Participant_ID": participant,
            "Total Biomarkers Assayed": len(p_base),
            "Stable Across Flight Count": traj_counts.get("STABLE_ACROSS_FLIGHT", 0),
            "Acute Elevation with Recovery": traj_counts.get("ACUTE_ELEVATION_WITH_RECOVERY", 0),
            "Acute Suppression with Recovery": traj_counts.get("ACUTE_SUPPRESSION_WITH_RECOVERY", 0),
            "Sustained Postflight Elevation": traj_counts.get("SUSTAINED_POSTFLIGHT_ELEVATION", 0),
            "Sustained Postflight Suppression": traj_counts.get("SUSTAINED_POSTFLIGHT_SUPPRESSION", 0),
            "Incomplete / Missing Postflight Data": traj_counts.get("INCOMPLETE_DATA", 0)
        })
    df_part_sum = pd.DataFrame(part_summary)
    
    # Disclaimer sheet
    df_disclaimer = pd.DataFrame([
        {"Notice": DISCLAIMER_TEXT, "Project": "WEDJAT-X", "Study": "NASA OSD-575 / Inspiration4 Mission"}
    ])
    
    out_path = REPORTS_DIR / "baseline_analysis.xlsx"
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df_disclaimer.to_excel(writer, sheet_name="Scientific_Disclaimer", index=False)
        df_part_sum.to_excel(writer, sheet_name="Participant_Summary", index=False)
        df_baseline.to_excel(writer, sheet_name="Biomarker_Baseline_Shifts", index=False)
        df_long.to_excel(writer, sheet_name="Longitudinal_Trajectory_Values", index=False)
        
    logger.info(f"Phase 7 baseline analysis completed successfully. Saved to: {out_path}")
    return df_baseline, df_part_sum, df_long

if __name__ == "__main__":
    run_baseline_analysis()
