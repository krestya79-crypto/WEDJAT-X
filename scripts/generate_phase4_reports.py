"""
Script to generate Phase 4 Excel reports for Sensor Trust and Scientific Interpretation.
NASA Space Apps Challenge - WEDJAT-X Prototype
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from intelligence.synthetic_sensors import (
    SyntheticSensorConfig,
    SyntheticSensorGenerator,
    ALL_SCENARIOS,
    ALL_SENSOR_TYPES,
)
from intelligence.sensor_trust import (
    SensorTrustEngine,
    DEFAULT_WEIGHTS,
    NOMINAL_NOISE_THRESHOLDS,
    NOMINAL_DRIFT_THRESHOLDS,
)
from intelligence.interpretation import (
    ScientificInterpreter,
    PERMITTED_WORKFLOW_FLAGS,
)
from intelligence.baseline import BaselineEngine, DISCLAIMER_TEXT
from intelligence.anomaly import AnomalyDetector
from intelligence.trajectory import LongitudinalTrajectoryEngine

DATASET_PATH = Path("cleaned_data/WEDJAT_X_Master_Biomarker_Dataset.csv")
REPORTS_DIR = Path("reports")
SENSOR_TRUST_DIR = REPORTS_DIR / "sensor_trust"
INTERP_DIR = REPORTS_DIR / "interpretation"

SENSOR_TRUST_DIR.mkdir(parents=True, exist_ok=True)
INTERP_DIR.mkdir(parents=True, exist_ok=True)


def build_sensor_trust_report() -> Path:
    """Generate reports/sensor_trust/Sensor_Trust_Report.xlsx"""
    excel_path = SENSOR_TRUST_DIR / "Sensor_Trust_Report.xlsx"
    engine = SensorTrustEngine()
    gen = SyntheticSensorGenerator(SyntheticSensorConfig(duration_seconds=60.0, random_seed=42))

    eval_records = []
    subscore_records = []
    disc_records = []

    for scen in ALL_SCENARIOS:
        df_scen = gen.generate_scenario(scen)
        res_all = engine.evaluate_all(df_scen)

        for sensor, res in res_all.items():
            eval_records.append({
                "Scenario": scen,
                "Sensor_Type": sensor,
                "Quality_Score": res["quality_score"],
                "Reliability_Category": res["reliability_category"],
                "Missing_Rate_Pct": round(res["missing_rate"] * 100.0, 2),
                "Disconnection_Rate_Pct": round(res["disconnection_rate"] * 100.0, 2),
                "Noise_Metric": res["noise_metric"],
                "Spike_Count": res["spike_count"],
                "Drift_Detected": res["drift_detected"],
                "Timestamp_Gaps": res["timestamp_gap_count"],
                "Motion_Overlap_Pct": res["motion_overlap_pct"],
                "Detected_Issues": "; ".join(res["detected_issues"]) if res["detected_issues"] else "None",
                "Explanation": res["explanation"],
                "Is_Synthetic": res["is_synthetic"],
            })

            sub = res["sub_scores"]
            subscore_records.append({
                "Scenario": scen,
                "Sensor_Type": sensor,
                "Missing_Subscore": sub.get("missing", np.nan),
                "Disconnection_Subscore": sub.get("disconnection", np.nan),
                "Noise_Subscore": sub.get("noise", np.nan),
                "Spikes_Subscore": sub.get("spikes", np.nan),
                "Continuity_Subscore": sub.get("continuity", np.nan),
                "Drift_Subscore": sub.get("drift", np.nan),
                "Total_Composite_Score": res["quality_score"],
                "Reliability_Category": res["reliability_category"],
            })

            for p in res.get("consecutive_disconnection_periods", []):
                disc_records.append({
                    "Scenario": scen,
                    "Sensor_Type": sensor,
                    "Start_Time": str(p.get("start_time")),
                    "End_Time": str(p.get("end_time")),
                    "Sample_Count": p.get("sample_count"),
                    "Duration_Seconds": p.get("duration_seconds"),
                })

    methodology_records = [
        {"Parameter": "Missing Data Weight", "Value": f"{DEFAULT_WEIGHTS['missing']*100:.0f}%", "Description": "Penalizes intermittent packet dropouts without setting missing values to zero."},
        {"Parameter": "Disconnection Weight", "Value": f"{DEFAULT_WEIGHTS['disconnection']*100:.0f}%", "Description": "Penalizes persistent sensor uncoupling/lead-off while preserving timestamp grid."},
        {"Parameter": "Noise Weight", "Value": f"{DEFAULT_WEIGHTS['noise']*100:.0f}%", "Description": "Evaluates residual MAD against rolling physiological trend baseline."},
        {"Parameter": "Spikes/Artifacts Weight", "Value": f"{DEFAULT_WEIGHTS['spikes']*100:.0f}%", "Description": "Hampel filter (3-sigma local MAD) identifies transient spikes without deleting data."},
        {"Parameter": "Continuity Weight", "Value": f"{DEFAULT_WEIGHTS['continuity']*100:.0f}%", "Description": "Identifies timestamp gaps (>1.5x dt) and duplicate timestamps."},
        {"Parameter": "Signal Drift Weight", "Value": f"{DEFAULT_WEIGHTS['drift']*100:.0f}%", "Description": "Detects monotonic baseline shift between early and late stream segments."},
        {"Parameter": "HIGH_RELIABILITY", "Value": "Score >= 90", "Description": "Minimal noise, intact continuity, highly trustworthy signal."},
        {"Parameter": "MODERATE_RELIABILITY", "Value": "75 <= Score < 90", "Description": "Acceptable signal with minor noise or isolated dropouts."},
        {"Parameter": "LOW_RELIABILITY", "Value": "50 <= Score < 75", "Description": "Substantial degradation; operational signal verification advised."},
        {"Parameter": "UNRELIABLE", "Value": "Score < 50", "Description": "Severe degradation, packet loss, or disconnection; untrustworthy signal."},
        {"Parameter": "INSUFFICIENT_DATA", "Value": "N/A", "Description": "Fewer than 2-3 valid samples available for statistical trust estimation."},
    ]

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        pd.DataFrame(eval_records).to_excel(writer, sheet_name="Sensor_Evaluations", index=False)
        pd.DataFrame(subscore_records).to_excel(writer, sheet_name="Sub_Scores_Breakdown", index=False)
        pd.DataFrame(disc_records).to_excel(writer, sheet_name="Disconnection_Runs", index=False)
        pd.DataFrame(methodology_records).to_excel(writer, sheet_name="Scoring_Methodology", index=False)

    print("Created:", excel_path)
    return excel_path


def build_interpretation_reports():
    """Generate Ground_Medical_Reports.xlsx and Astronaut_Summaries.xlsx"""
    interp = ScientificInterpreter()
    base_engine = BaselineEngine(DATASET_PATH)
    anom_detector = AnomalyDetector()
    traj_engine = LongitudinalTrajectoryEngine(baseline_engine=base_engine)

    ground_path = INTERP_DIR / "Ground_Medical_Reports.xlsx"
    crew_path = INTERP_DIR / "Astronaut_Summaries.xlsx"

    # Representative NASA OSD-575 biomarkers across systems
    target_bms = ["CRP", "Fibrinogen", "GLUCOSE", "ALBUMIN", "BUN/CREATININE RATIO"]
    participants = ["C001", "C002", "C003", "C004"]
    postflight_tps = ["R+1", "R+45", "R+82", "R+194"]

    ground_records = []
    crew_records = []

    # 1. NASA Biomarker Interpretations
    for p in participants:
        p_long = base_engine.calculate_longitudinal_changes(p)
        p_anom = anom_detector.detect_anomalies(p_long)
        p_traj = traj_engine.analyze_participant(p)

        for bm in target_bms:
            bm_traj_rows = p_traj[p_traj["Biomarker_Name"] == bm]
            traj_row = bm_traj_rows.iloc[0].to_dict() if len(bm_traj_rows) > 0 else {}

            for tp in postflight_tps:
                row_match = p_anom[(p_anom["Biomarker_Name"] == bm) & (p_anom["Timepoint"] == tp)]
                if len(row_match) == 0:
                    continue
                row = row_match.iloc[0]

                val = row["Measurement_Value"]
                unit = str(row["Measurement_Unit"])
                base_med = row["Baseline_Median"]
                base_mad = row["Baseline_MAD"]
                n_base = int(row.get("Preflight_Sample_Count", 0)) if not pd.isna(row.get("Preflight_Sample_Count")) else 0
                z_score = row["Robust_Z_Score"]
                flag = row["Exploratory_Anomaly_Flag"]

                obs = {
                    "name": bm,
                    "value": float(val) if not pd.isna(val) else None,
                    "unit": unit,
                    "timestamp_or_timepoint": tp,
                    "participant_id": p,
                }
                base_res = interp.interpret_baseline(bm, val, base_med, base_mad, n_base, unit, p)
                stat_res = interp.interpret_anomaly({"anomaly_flag": flag, "robust_z_score": z_score, "baseline_mad": base_mad})
                traj_res = interp.interpret_trajectory(traj_row) if traj_row else {}

                ground_rep = interp.generate_ground_report(
                    observation=obs,
                    baseline_comparison=base_res,
                    statistical_interpretation=stat_res,
                    longitudinal_interpretation=traj_res,
                    sensor_quality=None,  # Lab assays do not have wearable sensor trust
                    data_limitations=["Benchtop serum assay data (OSD-575), not continuous wearable telemetry."],
                    is_synthetic=False,
                )

                crew_rep = interp.generate_astronaut_report(
                    observation=obs,
                    baseline_comparison=base_res,
                    statistical_interpretation=stat_res,
                    longitudinal_interpretation=traj_res,
                    sensor_quality=None,
                    is_synthetic=False,
                )

                ground_records.append({
                    "Participant_ID": p,
                    "Biomarker_Name": bm,
                    "Timepoint": tp,
                    "Observed_Value": ground_rep["observation"].get("value"),
                    "Unit": unit,
                    "Baseline_Median": ground_rep["baseline_comparison"].get("personalized_baseline_median"),
                    "Percent_Delta": ground_rep["baseline_comparison"].get("percentage_difference"),
                    "Direction": ground_rep["baseline_comparison"].get("direction_of_change"),
                    "Robust_Z_Score": ground_rep["statistical_interpretation"].get("robust_z_score"),
                    "Statistical_Flag": ground_rep["statistical_interpretation"].get("statistical_flag"),
                    "Trajectory_Status": ground_rep["longitudinal_interpretation"].get("trajectory_status"),
                    "Overall_Trend": ground_rep["longitudinal_interpretation"].get("overall_trend"),
                    "Evidentiary_Status": ground_rep["interpretation_status"],
                    "Recommended_Workflow_Actions": "; ".join(ground_rep["recommended_review_action"]),
                    "Evidence_Summary": " | ".join(ground_rep["evidence"]),
                    "Data_Limitations": " | ".join(ground_rep["data_limitations"]),
                    "Is_Synthetic": False,
                })

                crew_records.append({
                    "Participant_ID": p,
                    "Biomarker_Name": bm,
                    "Timepoint": tp,
                    "Crew_Narrative": crew_rep["crew_narrative"],
                    "Differs_From_Baseline": crew_rep["differs_from_baseline"],
                    "Pattern_Description": crew_rep["pattern_description"],
                    "Action_Guidance": crew_rep["action_guidance"],
                    "Is_Synthetic": False,
                })

    # 2. Synthetic Sensor Stream Interpretations
    gen = SyntheticSensorGenerator(SyntheticSensorConfig(duration_seconds=30.0, random_seed=42))
    trust_engine = SensorTrustEngine()

    for scen in ALL_SCENARIOS:
        df_scen = gen.generate_scenario(scen)
        res_all = trust_engine.evaluate_all(df_scen)

        for sensor, res in res_all.items():
            mean_val = float(df_scen[df_scen["sensor_type"] == sensor]["signal_value"].mean())
            unit = "bpm" if sensor == "heart_rate" else ("%" if sensor == "spo2" else "g")

            obs = {
                "name": f"Synthetic {sensor}",
                "value": round(mean_val, 2) if not pd.isna(mean_val) else None,
                "unit": unit,
                "timestamp_or_timepoint": "Stream Average (30s)",
                "participant_id": "SYNTH_SIM",
            }
            sens_qual = interp.interpret_sensor_quality(res)
            ground_rep = interp.generate_ground_report(
                observation=obs,
                sensor_quality=sens_qual,
                data_limitations=["Synthetic test simulation pattern; not real astronaut telemetry."],
                is_synthetic=True,
            )
            crew_rep = interp.generate_astronaut_report(
                observation=obs,
                sensor_quality=sens_qual,
                is_synthetic=True,
            )

            ground_records.append({
                "Participant_ID": "SYNTH_SIM",
                "Biomarker_Name": f"Synthetic_{sensor}",
                "Timepoint": scen,
                "Observed_Value": ground_rep["observation"].get("value"),
                "Unit": unit,
                "Baseline_Median": np.nan,
                "Percent_Delta": np.nan,
                "Direction": "N/A",
                "Robust_Z_Score": np.nan,
                "Statistical_Flag": "SYNTHETIC_EVAL",
                "Trajectory_Status": "N/A",
                "Overall_Trend": "N/A",
                "Evidentiary_Status": ground_rep["interpretation_status"],
                "Recommended_Workflow_Actions": "; ".join(ground_rep["recommended_review_action"]),
                "Evidence_Summary": " | ".join(ground_rep["evidence"]),
                "Data_Limitations": " | ".join(ground_rep["data_limitations"]),
                "Is_Synthetic": True,
            })

            crew_records.append({
                "Participant_ID": "SYNTH_SIM",
                "Biomarker_Name": f"Synthetic_{sensor}",
                "Timepoint": scen,
                "Crew_Narrative": crew_rep["crew_narrative"],
                "Differs_From_Baseline": False,
                "Pattern_Description": "Synthetic Stream Simulation",
                "Action_Guidance": crew_rep["action_guidance"],
                "Is_Synthetic": True,
            })

    workflow_definitions = [
        {"Workflow_Action": "REVIEW_MEASUREMENT", "Triggering_Condition": "Statistical anomaly detected, moderate deviation, or degraded sensor signal.", "Operational_Guidance": "Review raw signal trace and context during regular telemetry pass."},
        {"Workflow_Action": "VERIFY_SENSOR_SIGNAL", "Triggering_Condition": "Sensor signal reliability rated LOW or UNRELIABLE, or motion artifact overlap.", "Operational_Guidance": "Request astronaut or ground ops to verify sensor contact, lead snugness, and optical cleanliness."},
        {"Workflow_Action": "REPEAT_MEASUREMENT_IF_OPERATIONALLY_APPROPRIATE", "Triggering_Condition": "Significant statistical deviation observed in high-reliability stream.", "Operational_Guidance": "Schedule follow-up measurement at next mission opportunity to confirm physiological trend."},
        {"Workflow_Action": "REQUEST_MEDICAL_REVIEW", "Triggering_Condition": "Sustained significant statistical deviation with verified signal integrity.", "Operational_Guidance": "Flag observation for formal flight surgeon / biomedical engineer review."},
        {"Workflow_Action": "INSUFFICIENT_DATA_FOR_INTERPRETATION", "Triggering_Condition": "Measurement missing, sensor disconnected, or baseline unestablished.", "Operational_Guidance": "Cannot perform statistical decision support until valid telemetry is re-established."},
        {"Workflow_Action": "NO_ADDITIONAL_REVIEW_FLAGGED", "Triggering_Condition": "Measurement within nominal baseline dispersion with high sensor reliability.", "Operational_Guidance": "Maintain routine mission monitoring protocol."},
    ]

    with pd.ExcelWriter(ground_path, engine="openpyxl") as writer:
        pd.DataFrame(ground_records).to_excel(writer, sheet_name="Ground_Medical_Reports", index=False)
        pd.DataFrame(workflow_definitions).to_excel(writer, sheet_name="Workflow_Action_Catalog", index=False)

    with pd.ExcelWriter(crew_path, engine="openpyxl") as writer:
        pd.DataFrame(crew_records).to_excel(writer, sheet_name="Astronaut_Crew_Summaries", index=False)
        pd.DataFrame(workflow_definitions).to_excel(writer, sheet_name="Operational_Actions", index=False)

    print("Created:", ground_path)
    print("Created:", crew_path)


if __name__ == "__main__":
    build_sensor_trust_report()
    build_interpretation_reports()
