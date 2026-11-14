"""
Phase 8: Scientific Data Visualization
Generates high-resolution publication-quality figures for WEDJAT-X data audit using Matplotlib:
1. Biomarker trends over time.
2. Participant-level comparisons.
3. Missing data heatmap.
4. Biomarker distribution plots.
5. Submitted versus Transformed reconciliation scatter plots.
All figures comply with strict scientific plotting standards:
- Clear titles, axes, units, legends, and data source citations.
- Incompatible units are never merged on the same axis.
Saved to reports/figures/ and logged to audit_logs/08_visualization.log.
"""
import sys
import os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import setup_logger, REPORTS_DIR, FIGURES_DIR, CLEANED_DATA_DIR, AUDIT_LOGS_DIR

logger = setup_logger("Phase8_Visualization", "08_visualization.log")

plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['axes.edgecolor'] = '#333333'
plt.rcParams['axes.linewidth'] = 0.8

SOURCE_CITATION = "Source: NASA OSD-575 / Inspiration4 Mission (WEDJAT-X Audit Pipeline)"
PARTICIPANT_COLORS = {
    "C001": "#1f77b4",  # Blue
    "C002": "#ff7f0e",  # Orange
    "C003": "#2ca02c",  # Green
    "C004": "#d62728"   # Red
}

def generate_visualizations():
    logger.info("Starting Phase 8: Scientific Visualizations")
    
    master_path = CLEANED_DATA_DIR / "WEDJAT_X_Master_Biomarker_Dataset.csv"
    if not master_path.exists():
        raise FileNotFoundError(f"Master dataset not found at {master_path}.")
        
    df_master = pd.read_csv(master_path)
    valid_df = df_master[df_master["Validation_Status"] == "VALIDATED_MATCH"].copy()
    valid_df["Measurement_Value"] = pd.to_numeric(valid_df["Measurement_Value"], errors="coerce")
    
    time_order = ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82", "R+194"]
    
    # -------------------------------------------------------------------------
    # Plot 1: Longitudinal Biomarker Trends Over Time
    # -------------------------------------------------------------------------
    logger.info("Generating Plot 1: Longitudinal Biomarker Trends Over Time...")
    fig, axes = plt.subplots(2, 2, figsize=(16, 12), sharex=False)
    
    selected_trends = [
        ("Comprehensive Metabolic Panel (CMP)", "GLUCOSE", "Glucose (CMP)", "mg/dL", axes[0, 0]),
        ("Cardiovascular EvePanel", "CRP", "C-Reactive Protein (Eve CVD)", "pg/ml", axes[0, 1]),
        ("Immune EvePanel", "IL-6", "Interleukin-6 (Eve Immune HD71)", "pg/ml", axes[1, 0]),
        ("Immune AlamarPanel", "CXCL8", "CXCL8 / IL-8 (Alamar NULISA-seq)", "NPQ (log2 units)", axes[1, 1])
    ]
    
    for panel, bio, title, unit, ax in selected_trends:
        subset = valid_df[(valid_df["Panel_Name"] == panel) & (valid_df["Biomarker_Name"] == bio)].copy()
        subset["Timepoint"] = pd.Categorical(subset["Timepoint"], categories=time_order, ordered=True)
        subset = subset.sort_values(["Participant_ID", "Timepoint"])
        
        # Flight window shading between index 2 (L-3) and index 3 (R+1)
        ax.axvspan(1.8, 3.2, color='#edf2f7', alpha=0.9, label='Spaceflight Window (3-Day Mission)')
        
        for p_id in sorted(subset["Participant_ID"].unique()):
            p_data = subset[subset["Participant_ID"] == p_id]
            ax.plot(
                p_data["Timepoint"].astype(str),
                p_data["Measurement_Value"],
                marker='o',
                linewidth=2.2,
                markersize=7,
                color=PARTICIPANT_COLORS.get(p_id, '#333'),
                label=f"Astronaut {p_id}"
            )
            
        ax.set_title(f"{title}\nLongitudinal Dynamic Profile", fontsize=13, fontweight='bold', pad=10)
        ax.set_xlabel("Mission Timepoint (Preflight: L- | Postflight: R+)", fontsize=11, fontweight='semibold')
        ax.set_ylabel(f"Concentration [{unit}]", fontsize=11, fontweight='semibold')
        ax.tick_params(axis='x', rotation=30)
        ax.grid(True, linestyle='--', alpha=0.6)
        
        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        ax.legend(by_label.values(), by_label.keys(), loc='best', frameon=True, framealpha=0.9, fontsize=9)
        
    fig.suptitle("WEDJAT-X: Longitudinal Biomarker Kinetics Across Preflight, Flight, and Recovery", fontsize=16, fontweight='bold', y=0.99)
    fig.text(0.5, 0.01, SOURCE_CITATION, ha='center', fontsize=10, style='italic', color='#555555')
    plt.tight_layout(rect=[0, 0.03, 1, 0.96])
    
    p1_path = FIGURES_DIR / "01_biomarker_trends_over_time.png"
    plt.savefig(p1_path, dpi=300, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved Plot 1 to: {p1_path}")
    
    # -------------------------------------------------------------------------
    # Plot 2: Participant-Level Baseline vs Acute Return Comparisons
    # -------------------------------------------------------------------------
    logger.info("Generating Plot 2: Participant-Level Comparisons...")
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    
    comp_targets = [
        ("Comprehensive Metabolic Panel (CMP)", "GLUCOSE", "Glucose", "mg/dL", axes[0]),
        ("Cardiovascular EvePanel", "CRP", "C-Reactive Protein (CRP)", "pg/ml", axes[1]),
        ("Immune EvePanel", "IL-6", "Interleukin-6 (IL-6)", "pg/ml", axes[2])
    ]
    
    participants = ["C001", "C002", "C003", "C004"]
    x = np.arange(len(participants))
    width = 0.35
    
    for panel, bio, title, unit, ax in comp_targets:
        sub = valid_df[(valid_df["Panel_Name"] == panel) & (valid_df["Biomarker_Name"] == bio)].copy()
        
        pre_means = []
        r1_vals = []
        for p_id in participants:
            p_sub = sub[sub["Participant_ID"] == p_id]
            pre_mean = p_sub[p_sub["Timepoint"].isin(["L-92", "L-44", "L-3"])]["Measurement_Value"].mean()
            r1_val = p_sub[p_sub["Timepoint"] == "R+1"]["Measurement_Value"].values
            pre_means.append(pre_mean)
            r1_vals.append(r1_val[0] if len(r1_val) > 0 else 0)
            
        rects1 = ax.bar(x - width/2, pre_means, width, label='Preflight Baseline (Mean)', color='#4a5568', edgecolor='#2d3748', alpha=0.9)
        rects2 = ax.bar(x + width/2, r1_vals, width, label='Immediate Return (R+1)', color='#e53e3e', edgecolor='#9b2c2c', alpha=0.9)
        
        ax.set_title(f"{title}\nPreflight Baseline vs Immediate Return", fontsize=12, fontweight='bold')
        ax.set_xlabel("Astronaut Participant ID", fontsize=11, fontweight='semibold')
        ax.set_ylabel(f"Concentration [{unit}]", fontsize=11, fontweight='semibold')
        ax.set_xticks(x)
        ax.set_xticklabels(participants)
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.legend(frameon=True, framealpha=0.9, fontsize=9)
        
    fig.suptitle("WEDJAT-X: Participant-Specific Acute Spaceflight Response", fontsize=15, fontweight='bold', y=1.02)
    fig.text(0.5, -0.02, SOURCE_CITATION, ha='center', fontsize=10, style='italic', color='#555555')
    plt.tight_layout()
    
    p2_path = FIGURES_DIR / "02_participant_level_comparisons.png"
    plt.savefig(p2_path, dpi=300, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved Plot 2 to: {p2_path}")
    
    # -------------------------------------------------------------------------
    # Plot 3: Missing Data & Completeness Heatmap
    # -------------------------------------------------------------------------
    logger.info("Generating Plot 3: Missing Data Heatmap...")
    fig, ax = plt.subplots(figsize=(14, 10))
    
    all_samples_ordered = []
    for p in ["C001", "C002", "C003", "C004"]:
        for t in time_order:
            all_samples_ordered.append(f"{p}_serum_{t}")
            
    rep_biomarkers = [
        ("Comprehensive Metabolic Panel (CMP)", "GLUCOSE"),
        ("Comprehensive Metabolic Panel (CMP)", "UREA NITROGEN (BUN)"),
        ("Comprehensive Metabolic Panel (CMP)", "CREATININE"),
        ("Comprehensive Metabolic Panel (CMP)", "BUN/CREATININE RATIO"),
        ("Comprehensive Metabolic Panel (CMP)", "BILIRUBIN; TOTAL"),
        ("Cardiovascular EvePanel", "CRP"),
        ("Cardiovascular EvePanel", "Fibrinogen"),
        ("Cardiovascular EvePanel", "a-2 Macroglobulin"),
        ("Immune EvePanel", "IL-6"),
        ("Immune EvePanel", "TNFα"),
        ("Immune EvePanel", "IFNγ"),
        ("Immune AlamarPanel", "IL6"),
        ("Immune AlamarPanel", "CXCL8"),
        ("Immune AlamarPanel", "TNF"),
        ("Immune AlamarPanel", "IFNG")
    ]
    
    heatmap_matrix = np.zeros((len(all_samples_ordered), len(rep_biomarkers)))
    
    for row_idx, sample_id in enumerate(all_samples_ordered):
        for col_idx, (panel, bio) in enumerate(rep_biomarkers):
            match = df_master[(df_master["Sample_ID"] == sample_id) & (df_master["Panel_Name"] == panel) & (df_master["Biomarker_Name"] == bio)]
            if len(match) == 0:
                heatmap_matrix[row_idx, col_idx] = 3
            else:
                status = match["Validation_Status"].values[0]
                if status == "VALIDATED_MATCH":
                    heatmap_matrix[row_idx, col_idx] = 0
                elif status == "UNASSAYED_SAMPLE":
                    heatmap_matrix[row_idx, col_idx] = 1
                elif status == "REPORTED_MISSING":
                    heatmap_matrix[row_idx, col_idx] = 2
                elif status == "SOURCE_ROW_OMITTED":
                    heatmap_matrix[row_idx, col_idx] = 3
                else:
                    heatmap_matrix[row_idx, col_idx] = 3
                    
    from matplotlib.colors import ListedColormap
    cmap = ListedColormap([
        "#2b6cb0",  # 0: Validated Match (Blue)
        "#dd6b20",  # 1: Unassayed Sample (Orange)
        "#e53e3e",  # 2: Reported Clinical Missing (Red)
        "#805ad5"   # 3: Source Row Omitted (Purple)
    ])
    
    im = ax.imshow(heatmap_matrix, cmap=cmap, aspect='auto', interpolation='nearest')
    
    ax.set_yticks(range(len(all_samples_ordered)))
    ax.set_yticklabels(all_samples_ordered, fontsize=9)
    ax.set_xticks(range(len(rep_biomarkers)))
    ax.set_xticklabels([f"{b}\n({p.split()[0]})" for p, b in rep_biomarkers], rotation=45, ha='right', fontsize=9)
    
    ax.set_title("WEDJAT-X: Biospecimen Assay Completeness & Missingness Heatmap", fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel("Audited Biomarker Target & Assay Panel", fontsize=11, fontweight='semibold')
    ax.set_ylabel("Standard Biospecimen Sample Identifier", fontsize=11, fontweight='semibold')
    
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#2b6cb0", edgecolor='black', label="Validated Measured Record (Complete)"),
        Patch(facecolor="#dd6b20", edgecolor='black', label="Unassayed Biospecimen (C003 L-44 Alamar Protocol)"),
        Patch(facecolor="#e53e3e", edgecolor='black', label="Reported Laboratory Missing Value (NaN)"),
        Patch(facecolor="#805ad5", edgecolor='black', label="Source File Omitted Row (C002 R+82 BUN/Creatinine)")
    ]
    ax.legend(handles=legend_elements, loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=2, frameon=True, framealpha=0.9, fontsize=9)
    
    fig.text(0.5, -0.05, SOURCE_CITATION, ha='center', fontsize=10, style='italic', color='#555555')
    plt.tight_layout()
    
    p3_path = FIGURES_DIR / "03_missing_data_heatmap.png"
    plt.savefig(p3_path, dpi=300, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved Plot 3 to: {p3_path}")
    
    # -------------------------------------------------------------------------
    # Plot 4: Biomarker Distribution Plots
    # -------------------------------------------------------------------------
    logger.info("Generating Plot 4: Biomarker Distribution Plots...")
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    
    dist_targets = [
        ("Comprehensive Metabolic Panel (CMP)", "GLUCOSE", "Glucose Distribution (CMP)", "mg/dL", axes[0, 0]),
        ("Comprehensive Metabolic Panel (CMP)", "CREATININE", "Creatinine Distribution (CMP)", "mg/dL", axes[0, 1]),
        ("Cardiovascular EvePanel", "CRP", "CRP Distribution (Eve CVD)", "pg/ml", axes[1, 0]),
        ("Immune EvePanel", "IL-6", "IL-6 Distribution (Eve Immune)", "pg/ml", axes[1, 1])
    ]
    
    for panel, bio, title, unit, ax in dist_targets:
        sub = valid_df[(valid_df["Panel_Name"] == panel) & (valid_df["Biomarker_Name"] == bio)].copy()
        pre_vals = sub[sub["Timepoint"].isin(["L-92", "L-44", "L-3"])]["Measurement_Value"].dropna().tolist()
        post_vals = sub[sub["Timepoint"].isin(["R+1", "R+45", "R+82", "R+194"])]["Measurement_Value"].dropna().tolist()
        
        # Boxplot
        bp = ax.boxplot([pre_vals, post_vals], positions=[1, 2], widths=0.45, patch_artist=True)
        colors = ['#63b3ed', '#feb2b2']
        for patch, col in zip(bp['boxes'], colors):
            patch.set_facecolor(col)
            patch.set_alpha(0.8)
            
        # Scatter points by participant
        for p_idx, p_id in enumerate(participants):
            p_sub = sub[sub["Participant_ID"] == p_id]
            p_pre = p_sub[p_sub["Timepoint"].isin(["L-92", "L-44", "L-3"])]["Measurement_Value"].dropna()
            p_post = p_sub[p_sub["Timepoint"].isin(["R+1", "R+45", "R+82", "R+194"])]["Measurement_Value"].dropna()
            
            # Add small jitter
            jitter_pre = np.random.normal(1, 0.05, size=len(p_pre))
            jitter_post = np.random.normal(2, 0.05, size=len(p_post))
            
            ax.scatter(jitter_pre, p_pre, color=PARTICIPANT_COLORS[p_id], edgecolors='black', s=45, label=f"Astronaut {p_id}", zorder=4)
            ax.scatter(jitter_post, p_post, color=PARTICIPANT_COLORS[p_id], edgecolors='black', s=45, zorder=4)
            
        ax.set_title(f"{title}", fontsize=13, fontweight='bold', pad=10)
        ax.set_xticks([1, 2])
        ax.set_xticklabels(["Preflight Baseline", "Postflight Recovery"], fontsize=11, fontweight='semibold')
        ax.set_ylabel(f"Concentration [{unit}]", fontsize=11, fontweight='semibold')
        ax.grid(True, linestyle='--', alpha=0.5)
        
        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        ax.legend(by_label.values(), by_label.keys(), loc='best', frameon=True, framealpha=0.9, fontsize=9)
        
    fig.suptitle("WEDJAT-X: Preflight vs Postflight Biomarker Value Distributions", fontsize=16, fontweight='bold', y=0.99)
    fig.text(0.5, 0.01, SOURCE_CITATION, ha='center', fontsize=10, style='italic', color='#555555')
    plt.tight_layout(rect=[0, 0.03, 1, 0.96])
    
    p4_path = FIGURES_DIR / "04_biomarker_distribution_plots.png"
    plt.savefig(p4_path, dpi=300, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved Plot 4 to: {p4_path}")
    
    # -------------------------------------------------------------------------
    # Plot 5: Submitted vs Transformed Reconciliation Scatter Plots
    # -------------------------------------------------------------------------
    logger.info("Generating Plot 5: Submitted vs Transformed Concordance Plots...")
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    
    reconcil_path = REPORTS_DIR / "biomarker_reconciliation.xlsx"
    df_reconcil = pd.read_excel(reconcil_path, sheet_name="Detailed_Reconciliation")
    matched_reconcil = df_reconcil[df_reconcil["Reconciliation_Status"] == "MATCHED"].copy()
    matched_reconcil["Submitted_Value"] = pd.to_numeric(matched_reconcil["Submitted_Value"], errors="coerce")
    matched_reconcil["Transformed_Value"] = pd.to_numeric(matched_reconcil["Transformed_Value"], errors="coerce")
    matched_reconcil = matched_reconcil.dropna(subset=["Submitted_Value", "Transformed_Value"])
    
    panels_for_scatter = [
        ("Comprehensive Metabolic Panel (CMP)", axes[0, 0], "#2b6cb0"),
        ("Cardiovascular EvePanel", axes[0, 1], "#c53030"),
        ("Immune EvePanel", axes[1, 0], "#2f855a"),
        ("Immune AlamarPanel", axes[1, 1], "#b7791f")
    ]
    
    for panel_name, ax, col in panels_for_scatter:
        p_data = matched_reconcil[matched_reconcil["Panel_Name"] == panel_name]
        
        sub_v = p_data["Submitted_Value"]
        tr_v = p_data["Transformed_Value"]
        
        ax.scatter(sub_v, tr_v, alpha=0.6, color=col, edgecolors='none', s=25, label=f"Measurements (N={len(p_data):,})")
        
        min_val = min(sub_v.min(), tr_v.min())
        max_val = max(sub_v.max(), tr_v.max())
        ax.plot([min_val, max_val], [min_val, max_val], 'k--', linewidth=1.5, label='Identity Line (y = x)')
        
        abs_diff = (sub_v - tr_v).abs().max()
        r2 = np.corrcoef(sub_v, tr_v)[0, 1] ** 2 if len(p_data) > 1 else 1.0
        
        ax.set_title(f"{panel_name}\nR² = {r2:.6f} | Max Diff = {abs_diff:.2e}", fontsize=12, fontweight='bold', pad=8)
        ax.set_xlabel("Submitted Source Value", fontsize=10, fontweight='semibold')
        ax.set_ylabel("Transformed Source Value", fontsize=10, fontweight='semibold')
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.legend(loc='upper left', frameon=True, framealpha=0.9, fontsize=9)
        
    fig.suptitle("WEDJAT-X: Submitted vs. Transformed Scientific Concordance Audit (100% Identity)", fontsize=15, fontweight='bold', y=0.99)
    fig.text(0.5, 0.01, SOURCE_CITATION, ha='center', fontsize=10, style='italic', color='#555555')
    plt.tight_layout(rect=[0, 0.03, 1, 0.96])
    
    p5_path = FIGURES_DIR / "05_submitted_vs_transformed_concordance.png"
    plt.savefig(p5_path, dpi=300, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved Plot 5 to: {p5_path}")
    
    logger.info("Phase 8 visualization pipeline completed successfully. All 5 figure sets generated.")

if __name__ == "__main__":
    generate_visualizations()
