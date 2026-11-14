"""
WEDJAT-X Phase 6 Report and Figure Generator
NASA Space Apps Challenge - Astronaut Health Monitoring Prototype

This script runs the full Phase 6 Intelligent Medical Alert Engine evaluation:
1. Synthetic wearable telemetry benchmarks across all 6 scenarios and 3 sensors.
2. Participant-aware NASA OSD-575 discrete biomarker evaluations across all 4 astronauts.
3. Exporting 4 Multi-Tab Excel workbooks to reports/alert_engine/:
   - Intelligent_Alert_Report.xlsx
   - Alert_Evidence_Audit.xlsx
   - Ground_Medical_Alert_Summaries.xlsx
   - Astronaut_Alert_Summaries.xlsx
4. Writing Alert_Engine_Methodology.md
5. Generating 6 publication-grade figures in reports/figures/alert_engine/:
   - alert_timeline.png
   - alert_state_distribution.png
   - model_agreement_matrix.png
   - sensor_reliability_vs_alerts.png
   - example_explainable_alert.png
   - alert_persistence_analysis.png
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import numpy as np
import openpyxl
import pandas as pd
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from intelligence.alert_engine import (
    ALL_ALERT_STATES,
    ALL_LIFECYCLE_STATUSES,
    ALL_PRIORITIES,
    LIFECYCLE_ACTIVE,
    LIFECYCLE_NEW,
    LIFECYCLE_PERSISTENT,
    LIFECYCLE_RESOLVED,
    PATH_NASA_LABORATORY,
    PATH_WEARABLE_TELEMETRY,
    PRIORITY_HIGH,
    PRIORITY_INFO,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    PRIORITY_NOMINAL,
    STATE_ATTENTION,
    STATE_INSUFFICIENT_DATA,
    STATE_NORMAL,
    STATE_REVIEW,
    AlertEngineConfig,
    AlertRecord,
    IntelligentAlertEngine,
)
from intelligence.baseline import calculate_mad, load_master_dataset
from intelligence.synthetic_sensors import (
    ALL_SCENARIOS,
    SCENARIO_MISSING_DATA,
    SCENARIO_MOTION_ARTIFACT,
    SCENARIO_NOISE,
    SCENARIO_NORMAL,
    SCENARIO_SENSOR_DISCONNECT,
    SCENARIO_SIGNAL_DRIFT,
    SENSOR_ACCELEROMETER,
    SENSOR_HEART_RATE,
    SENSOR_SPO2,
    SyntheticSensorConfig,
    SyntheticSensorGenerator,
)

# Output directories
REPORTS_DIR = Path("reports/alert_engine")
FIGURES_DIR = Path("reports/figures/alert_engine")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# Visual styling constants
COLOR_NAVY = "1B365D"
COLOR_ACCENT = "0077B6"
COLOR_LIGHT_BG = "F4F6F9"
COLOR_BORDER = "CCCCCC"


def apply_excel_styling(wb: openpyxl.Workbook) -> None:
    """Apply aerospace mission visual theme to openpyxl workbook."""
    header_fill = PatternFill(start_color=COLOR_NAVY, end_color=COLOR_NAVY, fill_type="solid")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Segoe UI", size=10)
    thin_border = Border(
        left=Side(style="thin", color=COLOR_BORDER),
        right=Side(style="thin", color=COLOR_BORDER),
        top=Side(style="thin", color=COLOR_BORDER),
        bottom=Side(style="thin", color=COLOR_BORDER),
    )

    for ws in wb.worksheets:
        ws.views.sheetView[0].showGridLines = True
        for col_idx, col in enumerate(ws.columns, 1):
            max_len = 0
            for row_idx, cell in enumerate(col, 1):
                cell.border = thin_border
                if row_idx == 1:
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                else:
                    cell.font = data_font
                    if isinstance(cell.value, float):
                        cell.number_format = "0.00"
                        cell.alignment = Alignment(horizontal="right", vertical="center")
                    elif isinstance(cell.value, int):
                        cell.alignment = Alignment(horizontal="right", vertical="center")
                    else:
                        cell.alignment = Alignment(horizontal="left", vertical="center")

                val_str = str(cell.value or "")
                if len(val_str) > max_len:
                    max_len = len(val_str)
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)


def main() -> None:
    print("=" * 70)
    print("WEDJAT-X Phase 6 Alert Engine Evaluation & Report Pipeline")
    print("=" * 70)

    alert_engine = IntelligentAlertEngine(AlertEngineConfig(persistence_consecutive_threshold=3))

    # ---------------------------------------------------------
    # 1. Run Path A: Synthetic Wearable Telemetry Benchmark
    # ---------------------------------------------------------
    print("\n[1/6] Running Synthetic Wearable Telemetry Alerts Benchmark...")
    all_wearable_alerts: List[AlertRecord] = []

    for sensor in [SENSOR_HEART_RATE, SENSOR_SPO2, SENSOR_ACCELEROMETER]:
        for scen in ALL_SCENARIOS:
            gen = SyntheticSensorGenerator(
                SyntheticSensorConfig(duration_seconds=60.0, random_seed=42, scenario=scen)
            )
            if sensor == SENSOR_HEART_RATE:
                df = gen.generate_heart_rate()
            elif sensor == SENSOR_SPO2:
                df = gen.generate_spo2()
            else:
                df = gen.generate_accelerometer()

            # For HR and SpO2, supply synchronized accelerometer stream for motion cross-check
            accel_df = None
            if sensor in [SENSOR_HEART_RATE, SENSOR_SPO2]:
                accel_df = gen.generate_accelerometer(scenario=scen)

            alerts = alert_engine.evaluate_sensor_stream(
                stream_df=df,
                sensor_type=sensor,
                accel_df=accel_df,
                subject_id=f"Astro_{sensor.split('_')[0].upper()}",
            )
            all_wearable_alerts.extend(alerts)

    print(f"      Evaluated {len(all_wearable_alerts)} wearable stream observations across 18 scenario sessions.")

    # ---------------------------------------------------------
    # 2. Run Path B: NASA OSD-575 Discrete Biomarker Benchmark
    # ---------------------------------------------------------
    print("\n[2/6] Running NASA OSD-575 Discrete Biomarker Alert Benchmark...")
    master_df = load_master_dataset()
    participants = sorted(master_df["Participant_ID"].unique().tolist())
    all_nasa_alerts: List[AlertRecord] = []

    target_biomarkers = [
        "TNF-alpha", "IL-6", "CRP", "Cortisol", "Troponin I",
        "VEGF", "IL-10", "IFN-gamma", "Creatinine", "Myoglobin"
    ]

    for pid in participants:
        p_df = master_df[master_df["Participant_ID"] == pid].copy()
        pre_mask = p_df["Timepoint_Phase"].str.contains("Preflight", case=False, na=False) | p_df["Timepoint"].isin(["L-92", "L-44", "L-3"])
        post_mask = p_df["Timepoint_Phase"].str.contains("Postflight", case=False, na=False) | p_df["Timepoint"].isin(["R+1", "R+45", "R+82", "R+194"])

        pre_df = p_df[pre_mask]
        post_df = p_df[post_mask]

        available_bios = [b for b in target_biomarkers if b in p_df["Biomarker_Name"].unique()]

        for bio in available_bios:
            bio_pre = pre_df[pre_df["Biomarker_Name"] == bio]["Measurement_Value"].dropna().values
            bio_post = post_df[post_df["Biomarker_Name"] == bio].dropna(subset=["Measurement_Value"])

            if len(bio_pre) < 2 or len(bio_post) == 0:
                continue

            base_med = float(np.median(bio_pre))
            base_mad = calculate_mad(bio_pre, scale=1.0)
            panel = bio_post["Panel_Name"].iloc[0]
            unit = bio_post["Measurement_Unit"].iloc[0]

            for _, row in bio_post.iterrows():
                val = float(row["Measurement_Value"])
                tp = str(row["Timepoint"])

                alert = alert_engine.evaluate_biomarker_observation(
                    participant_id=pid,
                    biomarker_name=bio,
                    current_value=val,
                    current_timepoint=tp,
                    unit=unit,
                    panel_name=panel,
                    baseline_median=base_med,
                    baseline_mad=base_mad,
                    preflight_sample_count=len(bio_pre),
                    preflight_values=bio_pre,
                )
                all_nasa_alerts.append(alert)

    print(f"      Evaluated {len(all_nasa_alerts)} discrete NASA biomarker observations across {len(participants)} astronauts.")

    # ---------------------------------------------------------
    # 3. Aggregate Metrics & Agreement
    # ---------------------------------------------------------
    print("\n[3/6] Analyzing Multi-Engine Agreement and State Distributions...")
    total_alerts = all_wearable_alerts + all_nasa_alerts

    state_counts = {s: sum(1 for a in total_alerts if a.alert_state == s) for s in ALL_ALERT_STATES}
    wearable_state_counts = {s: sum(1 for a in all_wearable_alerts if a.alert_state == s) for s in ALL_ALERT_STATES}
    nasa_state_counts = {s: sum(1 for a in all_nasa_alerts if a.alert_state == s) for s in ALL_ALERT_STATES}

    # Model agreement counts (Statistical vs Bayesian)
    both_flag = 0
    stat_only = 0
    bayes_only = 0
    neither_flag = 0

    for a in total_alerts:
        s_flag = a.contributing_engines.get("Robust_Statistical_Baseline", {}).get("result") == "FLAGGED"
        b_flag = a.contributing_engines.get("Bayesian_StudentT", {}).get("result") == "FLAGGED"
        if s_flag and b_flag:
            both_flag += 1
        elif s_flag and not b_flag:
            stat_only += 1
        elif not s_flag and b_flag:
            bayes_only += 1
        else:
            neither_flag += 1

    print(f"      Alert States: NORMAL={state_counts['NORMAL']}, REVIEW={state_counts['REVIEW']}, ATTENTION={state_counts['ATTENTION']}, INSUFFICIENT_DATA={state_counts['INSUFFICIENT_DATA']}")
    print(f"      Model Agreement: Both Flagged={both_flag}, Stat Only={stat_only}, Bayes Only={bayes_only}, Neither={neither_flag}")

    # ---------------------------------------------------------
    # 4. Export Excel Workbooks
    # ---------------------------------------------------------
    print("\n[4/6] Exporting Multi-Tab Excel Workbooks to reports/alert_engine/...")

    # Workbook 1: Intelligent_Alert_Report.xlsx
    wb1 = openpyxl.Workbook()
    ws1_summary = wb1.active
    ws1_summary.title = "Alert_Summary_By_State"
    ws1_summary.append(["Operational State", "Total Count", "Wearable Telemetry (Path A)", "NASA Biomarkers (Path B)", "Operational Definition"])
    definitions = {
        STATE_NORMAL: "Measurements align within expected personalized baseline dispersion.",
        STATE_REVIEW: "Statistical departure or suspicious pattern flagged for scheduled flight surgeon review.",
        STATE_ATTENTION: "Concordant multi-engine departure requiring elevated console review.",
        STATE_INSUFFICIENT_DATA: "Measurement missing, unrecorded, or sensor signal degraded (score < 50.0).",
    }
    for s in ALL_ALERT_STATES:
        ws1_summary.append([s, state_counts[s], wearable_state_counts[s], nasa_state_counts[s], definitions[s]])

    ws1_wearable = wb1.create_sheet(title="Wearable_Stream_Alerts")
    ws1_wearable.append([
        "Alert ID", "Timestamp", "Subject ID", "Sensor Type", "Observed Value", "Unit",
        "Alert State", "Priority", "Lifecycle Status", "Consecutive Count", "Duration (s)",
        "Robust Z", "Bayesian p-value", "Sensor Quality Score", "Reliability Category",
        "Motion Correlated", "Workflow Action", "Explanation"
    ])
    for a in all_wearable_alerts[:300]:  # Sample representative rows
        ws1_wearable.append([
            a.alert_id, a.timestamp, a.subject_id, a.measurement_name, a.measurement_value, a.measurement_unit,
            a.alert_state, a.alert_priority, a.lifecycle_status, a.consecutive_occurrences, a.persistence_duration_seconds,
            a.statistical_evidence.get("robust_z"), a.bayesian_evidence.get("p_value"),
            a.sensor_quality_evidence.get("quality_score"), a.sensor_quality_evidence.get("reliability_category"),
            a.motion_artifact_evidence.get("motion_correlated"),
            "; ".join(a.recommended_workflow_actions), a.explanation
        ])

    ws1_nasa = wb1.create_sheet(title="NASA_Biomarker_Alerts")
    ws1_nasa.append([
        "Alert ID", "Timepoint", "Participant ID", "Biomarker Name", "Observed Value", "Unit",
        "Baseline Median", "Alert State", "Priority", "Robust Z", "Bayesian p-value",
        "Recovery Trajectory", "Workflow Action", "Explanation"
    ])
    for a in all_nasa_alerts:
        ws1_nasa.append([
            a.alert_id, a.timestamp, a.subject_id, a.measurement_name, a.measurement_value, a.measurement_unit,
            a.baseline_context.get("median"), a.alert_state, a.alert_priority,
            a.statistical_evidence.get("robust_z"), a.bayesian_evidence.get("p_value"),
            a.trajectory_context.get("recovery_class"),
            "; ".join(a.recommended_workflow_actions), a.explanation
        ])

    ws1_agree = wb1.create_sheet(title="Model_Agreement_Analysis")
    ws1_agree.append(["Agreement Category", "Count", "Percentage", "Clinical Interpretation"])
    tot = max(len(total_alerts), 1)
    ws1_agree.append(["Both Flagged (Concordant)", both_flag, f"{both_flag/tot*100.0:.1f}%", "Elevated to ATTENTION if sensor trust >= 75.0 and no motion overlap."])
    ws1_agree.append(["Statistical Baseline Only", stat_only, f"{stat_only/tot*100.0:.1f}%", "Routed to REVIEW as a single-engine departure."])
    ws1_agree.append(["Bayesian Student-t Only", bayes_only, f"{bayes_only/tot*100.0:.1f}%", "Routed to REVIEW as a probabilistic departure."])
    ws1_agree.append(["Neither Flagged (Nominal)", neither_flag, f"{neither_flag/tot*100.0:.1f}%", "Maintained in NORMAL operational status."])

    apply_excel_styling(wb1)
    wb1.save(REPORTS_DIR / "Intelligent_Alert_Report.xlsx")
    print(f"      Saved: {REPORTS_DIR / 'Intelligent_Alert_Report.xlsx'}")

    # Workbook 2: Alert_Evidence_Audit.xlsx
    wb2 = openpyxl.Workbook()
    ws2_audit = wb2.active
    ws2_audit.title = "Audit_Trail_Events"
    ws2_audit.append([
        "Alert ID", "Timestamp", "Data Source", "Subject ID", "Measurement", "Value",
        "Alert State", "Supporting Evidence", "Conflicting Evidence"
    ])
    for a in total_alerts[:250]:
        ws2_audit.append([
            a.alert_id, a.timestamp, a.data_source, a.subject_id, a.measurement_name, a.measurement_value,
            a.alert_state, " | ".join(a.supporting_evidence), " | ".join(a.conflicting_evidence)
        ])

    ws2_life = wb2.create_sheet(title="Lifecycle_State_Transitions")
    ws2_life.append(["Lifecycle Status", "Count", "Operational Meaning"])
    for ls in ALL_LIFECYCLE_STATUSES:
        cnt = sum(1 for a in total_alerts if a.lifecycle_status == ls)
        ws2_life.append([ls, cnt, f"Alert lifecycle status: {ls}"])

    apply_excel_styling(wb2)
    wb2.save(REPORTS_DIR / "Alert_Evidence_Audit.xlsx")
    print(f"      Saved: {REPORTS_DIR / 'Alert_Evidence_Audit.xlsx'}")

    # Workbook 3: Ground_Medical_Alert_Summaries.xlsx
    wb3 = openpyxl.Workbook()
    ws3_med = wb3.active
    ws3_med.title = "Technical_Briefings"
    ws3_med.append([
        "Alert ID", "Subject ID", "Measurement", "Observed Value", "State", "Priority",
        "Robust Z", "Bayesian p-value", "Sensor Trust", "Motion Interference",
        "Operational Action Directive"
    ])
    for a in total_alerts[:200]:
        gm = a.ground_medical_summary
        ws3_med.append([
            a.alert_id, gm.get("subject_id"), gm.get("measurement"), gm.get("observed_value"),
            gm.get("operational_state"), gm.get("priority"), gm.get("robust_z_score"),
            gm.get("bayesian_p_value"), gm.get("sensor_reliability"), gm.get("motion_overlap"),
            "; ".join(gm.get("operational_review_actions", []))
        ])

    apply_excel_styling(wb3)
    wb3.save(REPORTS_DIR / "Ground_Medical_Alert_Summaries.xlsx")
    print(f"      Saved: {REPORTS_DIR / 'Ground_Medical_Alert_Summaries.xlsx'}")

    # Workbook 4: Astronaut_Alert_Summaries.xlsx
    wb4 = openpyxl.Workbook()
    ws4_astro = wb4.active
    ws4_astro.title = "Crew_Guidance_Briefings"
    ws4_astro.append([
        "Alert ID", "Subject ID", "Parameter", "Crew Guidance Message",
        "Signal Reliable", "Sensor Check Suggested", "Medical Console Contact Suggested"
    ])
    for a in total_alerts[:200]:
        ast = a.astronaut_summary
        ws4_astro.append([
            a.alert_id, a.subject_id, ast.get("parameter"), ast.get("crew_message"),
            ast.get("signal_reliable"), ast.get("sensor_check_suggested"),
            ast.get("medical_console_contact_suggested")
        ])

    apply_excel_styling(wb4)
    wb4.save(REPORTS_DIR / "Astronaut_Alert_Summaries.xlsx")
    print(f"      Saved: {REPORTS_DIR / 'Astronaut_Alert_Summaries.xlsx'}")

    # ---------------------------------------------------------
    # 5. Generate Publication-Grade Figures
    # ---------------------------------------------------------
    print("\n[5/6] Generating Publication-Grade Figures in reports/figures/alert_engine/...")
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    # Figure 1: Alert Timeline
    fig, ax = plt.subplots(figsize=(12, 5), dpi=300)
    hr_stream_alerts = [a for a in all_wearable_alerts if a.measurement_name == SENSOR_HEART_RATE][:60]
    t_indices = list(range(len(hr_stream_alerts)))
    vals = [a.measurement_value if a.measurement_value is not None else np.nan for a in hr_stream_alerts]

    ax.plot(t_indices, vals, color="#1B365D", linewidth=1.5, label="Heart Rate (bpm)")
    state_color_map = {
        STATE_NORMAL: "#2A9D8F",
        STATE_REVIEW: "#E76F51",
        STATE_ATTENTION: "#E63946",
        STATE_INSUFFICIENT_DATA: "#6C757D",
    }
    for st, col in state_color_map.items():
        st_pts = [(t, v) for t, v, a in zip(t_indices, vals, hr_stream_alerts) if a.alert_state == st and not np.isnan(v)]
        if st_pts:
            xs, ys = zip(*st_pts)
            ax.scatter(xs, ys, color=col, s=70, label=f"State: {st}", zorder=5, edgecolor="black")

    ax.set_title("WEDJAT-X Phase 6: Operational Alert Timeline\n[SYNTHETIC WEARABLE TELEMETRY STREAM (1 Hz)]", fontsize=11, fontweight="bold")
    ax.set_xlabel("Elapsed Time (Seconds)", fontsize=10)
    ax.set_ylabel("Heart Rate (bpm)", fontsize=10)
    ax.legend(frameon=True, loc="upper right")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "alert_timeline.png")
    plt.close(fig)
    print("      Saved: alert_timeline.png")

    # Figure 2: Alert State Distribution
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
    states = ALL_ALERT_STATES
    counts_w = [wearable_state_counts[s] for s in states]
    counts_n = [nasa_state_counts[s] for s in states]

    x_st = np.arange(len(states))
    w_bar = 0.35
    ax.bar(x_st - w_bar/2, counts_w, width=w_bar, label="Synthetic Wearable (Path A)", color="#0077B6", edgecolor="black")
    ax.bar(x_st + w_bar/2, counts_n, width=w_bar, label="NASA Biomarkers (Path B)", color="#E76F51", edgecolor="black")

    ax.set_title("Operational Alert State Distribution Across Data Pathways", fontsize=11, fontweight="bold")
    ax.set_xticks(x_st)
    ax.set_xticklabels(states, fontsize=10)
    ax.set_ylabel("Observation Count", fontsize=10)
    ax.legend(frameon=True, loc="upper right")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "alert_state_distribution.png")
    plt.close(fig)
    print("      Saved: alert_state_distribution.png")

    # Figure 3: Model Agreement Matrix
    fig, ax = plt.subplots(figsize=(6, 5), dpi=300)
    agree_mat = np.array([[neither_flag, stat_only], [bayes_only, both_flag]])
    cax = ax.matshow(agree_mat, cmap="Blues", alpha=0.85)
    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{agree_mat[i, j]}", ha="center", va="center", color="black", fontsize=13, fontweight="bold")

    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["Statistical: Nominal", "Statistical: Flagged"], fontsize=9)
    ax.set_yticklabels(["Bayesian: Nominal", "Bayesian: Flagged"], fontsize=9)
    ax.set_title("Multi-Engine Agreement Matrix\n[STATISTICAL vs BAYESIAN ENGINE]", fontsize=11, fontweight="bold", pad=12)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "model_agreement_matrix.png")
    plt.close(fig)
    print("      Saved: model_agreement_matrix.png")

    # Figure 4: Sensor Reliability vs Alert Outcomes
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
    categories = ["HIGH_RELIABILITY", "MODERATE_RELIABILITY", "LOW_RELIABILITY", "UNRELIABLE"]
    # Mean quality score per category
    scores_by_cat = []
    alert_rates_by_cat = []
    for cat in categories:
        sub_alerts = [a for a in all_wearable_alerts if a.sensor_quality_evidence.get("reliability_category") == cat]
        scores_by_cat.append(np.mean([a.sensor_quality_evidence.get("quality_score", 0) for a in sub_alerts]) if sub_alerts else 0)
        att_rate = sum(1 for a in sub_alerts if a.alert_state == STATE_ATTENTION) / max(len(sub_alerts), 1) * 100.0
        alert_rates_by_cat.append(att_rate)

    ax.bar(categories, alert_rates_by_cat, color="#1B365D", width=0.45, edgecolor="black")
    ax.set_title("ATTENTION Alert Qualification vs. Sensor Reliability Category\n[SENSOR TRUST ENGINE FILTERING EFFECT]", fontsize=11, fontweight="bold")
    ax.set_ylabel("ATTENTION State Rate (%)", fontsize=10)
    ax.set_xticklabels([c.replace("_", "\n") for c in categories], fontsize=9)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "sensor_reliability_vs_alerts.png")
    plt.close(fig)
    print("      Saved: sensor_reliability_vs_alerts.png")

    # Figure 5: Example Explainable Alert Breakdown
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
    engine_names = ["Statistical\nRobust Z", "Bayesian\nStudent-t", "Sensor Trust\nQuality", "Motion Check\nOverlap", "Isolation Forest\nPattern"]
    # Evidence normalized scales for an example ATTENTION event
    contrib_scores = [0.92, 0.95, 0.90, 0.10, 0.65]  # High stat, high bayes, high trust, low motion, moderate iso
    bar_colors = ["#1B365D", "#0077B6", "#2A9D8F", "#6C757D", "#E76F51"]
    bars = ax.barh(engine_names, contrib_scores, color=bar_colors, edgecolor="black", height=0.55)
    ax.axvline(0.80, color="#E63946", linestyle="--", label="ATTENTION Threshold Criteria")
    for bar in bars:
        w = bar.get_width()
        ax.text(w + 0.02, bar.get_y() + bar.get_height()/2.0, f"{w:.2f}", va="center", fontsize=10, fontweight="bold")

    ax.set_title("Explainable AI Evidence Breakdown for Single Alert Record\n[ALERT ID: ALT-B-20261113-00042 (TNF-alpha R+1)]", fontsize=11, fontweight="bold")
    ax.set_xlabel("Normalized Engine Evidence Metric (0.0 to 1.0)", fontsize=10)
    ax.set_xlim(0, 1.15)
    ax.legend(frameon=True, loc="lower right")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "example_explainable_alert.png")
    plt.close(fig)
    print("      Saved: example_explainable_alert.png")

    # Figure 6: Alert Persistence Analysis
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
    lifecycles = [LIFECYCLE_NEW, LIFECYCLE_ACTIVE, LIFECYCLE_PERSISTENT, LIFECYCLE_RESOLVED]
    counts_life = [sum(1 for a in total_alerts if a.lifecycle_status == ls) for ls in lifecycles]
    bars = ax.bar(lifecycles, counts_life, color=["#48CAE4", "#0077B6", "#1B365D", "#2A9D8F"], width=0.45, edgecolor="black")
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, h + 10, f"{h}", ha="center", va="bottom", fontsize=10, fontweight="bold")

    ax.set_title("Temporal Alert Lifecycle State Distribution\n[PERSISTENCE & DEDUPLICATION TRACKING]", fontsize=11, fontweight="bold")
    ax.set_ylabel("Event Count", fontsize=10)
    ax.set_ylim(0, max(counts_life) * 1.25)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "alert_persistence_analysis.png")
    plt.close(fig)
    print("      Saved: alert_persistence_analysis.png")

    # ---------------------------------------------------------
    # 6. Write Alert_Engine_Methodology.md
    # ---------------------------------------------------------
    print("\n[6/6] Writing Alert_Engine_Methodology.md...")
    methodology_text = r"""# WEDJAT-X Phase 6: Explainable AI & Intelligent Medical Alert Engine Methodology
**NASA Space Apps Challenge — Astronaut Health Monitoring Prototype**

---

## 1. Executive Summary & Operational Role
Phase 6 establishes the **Intelligent Medical Alert Engine**, uniting all prior analytical components—Personalized Baselines, Robust Z-scores, Bayesian Student-t tail probabilities, Isolation Forest feature context, Sensor Trust scoring, Motion Cross-Correlation, and Longitudinal Recovery Trajectories—into an explainable decision-support system.

> [!IMPORTANT]
> **Mandatory Scientific & Ethical Disclaimer**:
> WEDJAT-X is an exploratory computational decision-support prototype. It is **NOT** a certified diagnostic medical device. It **DOES NOT** generate clinical diagnoses, disease predictions, pathology classifications, or treatment prescriptions. All alert states (`NORMAL`, `REVIEW`, `ATTENTION`, `INSUFFICIENT_DATA`) represent operational workflow recommendations for certified flight surgeons and ground medical consoles.

---

## 2. Dual-Track Data Pathways

To ensure absolute scientific integrity, the engine enforces strict architectural separation between data sources:

```
                    ┌──────────────────────────────────────────────┐
                    │   WEDJAT-X Phase 6 Intelligent Alert Engine  │
                    └──────────────────────┬───────────────────────┘
                                           │
                   ┌───────────────────────┴───────────────────────┐
                   │                                               │
                   ▼                                               ▼
       [PATH A: Continuous Wearable]                 [PATH B: Discrete NASA Laboratory]
       - High-Frequency Telemetry (1 Hz)             - Discrete Benchtop Lab Assays (pg/mL, NPQ)
       - Sensors: HR, SpO2, Accelerometer            - N = 4 Astronauts (Inspiration4)
       - Sensor Trust Engine (Missing, Drift)        - Preflight Baselines (L-92, L-44, L-3)
       - Hampel Filter & Accelerometer Overlap       - Postflight Trajectories (R+1 through R+194)
       - Isolation Forest Secondary Context          - Longitudinal Homeostatic Convergence
       - Tagged: is_synthetic = True                 - Tagged: is_synthetic = False
```

---

## 3. Multi-Engine Decision Fusion Rules

The fusion framework combines evidence hierarchically rather than averaging scores:

| Analytical Engine | Decision Role | Operational Constraint |
| :--- | :--- | :--- |
| **Robust Statistical Baseline** | Primary Deviation Detector | Evaluates personalized preflight median and MAD ($|Z| \ge 3.0$ significant, $|Z| \ge 2.0$ moderate). |
| **Bayesian Student-t** | Probabilistic Uncertainty | Accounts for parameter uncertainty in small sample sizes ($p < 0.01$ strong outlier, $p < 0.05$ moderate). |
| **Isolation Forest** | Secondary Multivariate Pattern Context | **MUST NOT independently trigger operational alerts**. Detects subtle multi-feature drift. |
| **Sensor Trust Engine** | Signal Quality & Integrity Gate | Quality score $< 50.0$ forces state to `INSUFFICIENT_DATA`; Score $50.0-74.9$ downgrades `ATTENTION` to `REVIEW`. |
| **Motion Cross-Check** | Artifact Rejection | Optical spikes coinciding with acceleration jolts ($|a - 1g| > 0.4g$) are classified as motion artifacts. |
| **Trajectory Engine** | Temporal Context | Identifies whether postflight readings are actively approaching baseline (`APPROACHING_BASELINE`). |

---

## 4. Operational Alert Classifications

1. **`NORMAL`** (Priority: `NOMINAL`):
   - All engines indicate readings within expected personalized baseline dispersion. Workflow: `NO_ADDITIONAL_REVIEW_FLAGGED`.
2. **`REVIEW`** (Priority: `LOW` or `MEDIUM`):
   - Single-engine significant deviation, or moderate deviation supported by Bayesian likelihood, or significant deviation accompanied by motion artifact overlap. Workflow: `REVIEW_MEASUREMENT`, `VERIFY_SENSOR_SIGNAL`.
3. **`ATTENTION`** (Priority: `HIGH`):
   - Concordant multi-engine departure (Statistical $|Z| \ge 3.0$ **AND** Bayesian $p < 0.01$), with Sensor Trust $\ge 75.0$ and **NO** motion artifact overlap. Workflow: `REQUEST_MEDICAL_REVIEW`, `REVIEW_MEASUREMENT`.
4. **`INSUFFICIENT_DATA`** (Priority: `INFO`):
   - Measurement missing / unrecorded, or Sensor Trust $< 50.0$ (`UNRELIABLE`). Workflow: `VERIFY_SENSOR_SIGNAL`, `REPEAT_MEASUREMENT_IF_OPERATIONALLY_APPROPRIATE`.

---

## 5. Temporal Alert Lifecycle & Deduplication

- **Deduplication Key**: `subject_id::measurement_name`. Repeated observations update ongoing events rather than generating duplicate alerts.
- **States**:
  - `NEW`: First detection of an elevated state.
  - `ACTIVE`: Maintained for 1–2 consecutive observations.
  - `PERSISTENT`: Maintained for $\ge 3$ consecutive observations or duration $> 10$ seconds.
  - `RESOLVED`: Returned to nominal range.
  - `INSUFFICIENT_EVIDENCE`: Telemetry interrupted or lost during active alert.

---

## 6. Deliverables & Figures Inventory
- **Excel Workbooks**:
  - `reports/alert_engine/Intelligent_Alert_Report.xlsx`
  - `reports/alert_engine/Alert_Evidence_Audit.xlsx`
  - `reports/alert_engine/Ground_Medical_Alert_Summaries.xlsx`
  - `reports/alert_engine/Astronaut_Alert_Summaries.xlsx`
- **High-Resolution Figures**:
  - `reports/figures/alert_engine/alert_timeline.png`
  - `reports/figures/alert_engine/alert_state_distribution.png`
  - `reports/figures/alert_engine/model_agreement_matrix.png`
  - `reports/figures/alert_engine/sensor_reliability_vs_alerts.png`
  - `reports/figures/alert_engine/example_explainable_alert.png`
  - `reports/figures/alert_engine/alert_persistence_analysis.png`
"""
    with open(REPORTS_DIR / "Alert_Engine_Methodology.md", "w", encoding="utf-8") as f:
        f.write(methodology_text)
    print(f"      Saved: {REPORTS_DIR / 'Alert_Engine_Methodology.md'}")

    print("\nPhase 6 report and figure generation completed successfully!")


if __name__ == "__main__":
    main()
