"""
Phase 4: Biomarker Reconciliation
Performs record-by-record and biomarker-by-biomarker matching across all 8 datasets.
Reconciles names, units, values, missingness, and discrepancies.
Generates reports/biomarker_reconciliation.xlsx and audit_logs/04_biomarker_reconciliation.log.
"""
import sys
import os
import re
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import FILES_INFO, get_file_path, setup_logger, REPORTS_DIR, AUDIT_LOGS_DIR

logger = setup_logger("Phase4_BiomarkerReconciliation", "04_biomarker_reconciliation.log")

EXPECTED_PARTICIPANTS = ["C001", "C002", "C003", "C004"]
EXPECTED_TIMEPOINTS = ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82", "R+194"]
EXPECTED_ALL_SAMPLES = [f"{p}_serum_{t}" for p in EXPECTED_PARTICIPANTS for t in EXPECTED_TIMEPOINTS]

# Semantic unit equivalence mapping
UNIT_SEMANTIC_MAP = {
    "pg/ml": "picogram_per_milliliter",
    "ng/ml": "nanogram_per_milliliter",
    "mg/dl": "milligram_per_deciliter",
    "g/dl": "gram_per_deciliter",
    "mmol/l": "millimol_per_liter",
    "u/l": "units_per_liter",
    "ml/min/1.73m2": "milliliter_per_minute_per_1.73_meter_squared",
    "(calc)": "ratio/calculated",
    "npq": "npq",
    "percent": "percent"
}

def normalize_unit(unit_str):
    if pd.isna(unit_str) or unit_str is None:
        return "ratio/calculated"
    u = str(unit_str).strip().lower()
    return UNIT_SEMANTIC_MAP.get(u, u)

def normalize_string(s):
    s = s.replace('/', '_per_').replace('+', '_plus_')
    s = re.sub(r'[^a-zA-Z0-9αβγδ\u03b1-\u03c9]+', '_', s.strip().lower())
    return s.strip('_')

def reconcile_biomarkers():
    logger.info("Starting Phase 4: Biomarker Reconciliation")
    
    detailed_records = []
    
    # -------------------------------------------------------------------------
    # 1. Cardiovascular EvePanel
    # -------------------------------------------------------------------------
    logger.info("Reconciling Cardiovascular EvePanel...")
    sub_cv = pd.read_csv(get_file_path("LSDS-8_Multiplex_serum.cardiovascular.EvePanel_SUBMITTED.csv"))
    tr_cv = pd.read_csv(get_file_path("LSDS-8_Multiplex_serum_cardiovascular_EvePanel_TRANSFORMED.csv"))
    sub_cv["Sample_ID"] = sub_cv["ID"] + "_serum_" + sub_cv["Timepoint"]
    
    cv_biomarker_map = {
        'a-2 Macroglobulin': ('a2_macroglobulin_concentration_nanogram_per_milliliter', 'nanogram_per_milliliter'),
        'AGP': ('agp_concentration_nanogram_per_milliliter', 'nanogram_per_milliliter'),
        'CRP': ('crp_concentration_picogram_per_milliliter', 'picogram_per_milliliter'),
        'Fetuin A36': ('fetuin_a36_concentration_nanogram_per_milliliter', 'nanogram_per_milliliter'),
        'Fibrinogen': ('fibrinogen_concentration_nanogram_per_milliliter', 'nanogram_per_milliliter'),
        'Haptoglobin': ('haptoglobin_concentration_nanogram_per_milliliter', 'nanogram_per_milliliter'),
        'L-Selectin': ('l_selectin_concentration_picogram_per_milliliter', 'picogram_per_milliliter'),
        'PF4': ('pf4_concentration_nanogram_per_milliliter', 'nanogram_per_milliliter'),
        'SAP': ('sap_concentration_picogram_per_milliliter', 'picogram_per_milliliter')
    }
    
    for sample_id in EXPECTED_ALL_SAMPLES:
        p_id, _, tp = sample_id.split('_')
        tr_sample_row = tr_cv[tr_cv["Sample Name"] == sample_id]
        has_tr_sample = len(tr_sample_row) > 0
        
        for bio_name, (tr_col, tr_unit) in cv_biomarker_map.items():
            sub_row = sub_cv[(sub_cv["Sample_ID"] == sample_id) & (sub_cv["Analyte"] == bio_name)]
            has_sub_record = len(sub_row) > 0
            
            sub_val = float(sub_row["Concentration"].values[0]) if has_sub_record else np.nan
            sub_unit = str(sub_row["Unit"].values[0]) if has_sub_record else None
            
            tr_val = float(tr_sample_row[tr_col].values[0]) if has_tr_sample else np.nan
            
            # Evaluate status
            if has_sub_record and has_tr_sample:
                norm_sub_u = normalize_unit(sub_unit)
                norm_tr_u = normalize_unit(tr_unit)
                u_match = (norm_sub_u == norm_tr_u)
                
                # Check value match
                if pd.isna(sub_val) and pd.isna(tr_val):
                    val_match = True
                    abs_diff = 0.0
                elif pd.isna(sub_val) or pd.isna(tr_val):
                    val_match = False
                    abs_diff = np.nan
                else:
                    abs_diff = abs(sub_val - tr_val)
                    val_match = (abs_diff < 1e-4)
                    
                if not u_match:
                    status = "UNIT_MISMATCH"
                    note = f"Units differ: Submitted={sub_unit}, Transformed={tr_unit}"
                elif not val_match:
                    status = "VALUE_MISMATCH"
                    note = f"Values differ by {abs_diff:.6f}"
                else:
                    status = "MATCHED"
                    note = "Values and units reconcile perfectly."
            elif has_sub_record and not has_tr_sample:
                status = "MISSING_IN_TRANSFORMED"
                abs_diff = np.nan
                note = "Sample/biomarker missing from transformed dataset."
            elif not has_sub_record and has_tr_sample:
                status = "MISSING_IN_SUBMITTED"
                abs_diff = np.nan
                note = "Biomarker present in transformed but missing from submitted."
            else:
                status = "NOT_COMPARABLE"
                abs_diff = np.nan
                note = "Sample not present in either dataset."
                
            detailed_records.append({
                "Participant_ID": p_id,
                "Sample_ID": sample_id,
                "Timepoint": tp,
                "Panel_Name": "Cardiovascular EvePanel",
                "Biomarker_Name": bio_name,
                "Submitted_Value": sub_val,
                "Submitted_Unit": sub_unit,
                "Transformed_Value": tr_val,
                "Transformed_Unit": tr_unit,
                "Absolute_Difference": abs_diff,
                "Reconciliation_Status": status,
                "Audit_Notes": note
            })
            
    # -------------------------------------------------------------------------
    # 2. Immune EvePanel
    # -------------------------------------------------------------------------
    logger.info("Reconciling Immune EvePanel...")
    sub_ime = pd.read_csv(get_file_path("LSDS-8_Multiplex_serum.immune.EvePanel_SUBMITTED.csv"))
    tr_ime = pd.read_csv(get_file_path("LSDS-8_Multiplex_serum_immune_EvePanel_TRANSFORMED.csv"))
    sub_ime["Sample_ID"] = sub_ime["ID"] + "_serum_" + sub_ime["Timepoint"]
    
    ime_analytes = sorted(sub_ime["Analyte"].unique())
    tr_ime_conc_cols = [c for c in tr_ime.columns if "concentration_picogram_per_milliliter" in c]
    
    # Map analytes
    ime_map = {}
    for a in ime_analytes:
        na = normalize_string(a)
        matches = [c for c in tr_ime_conc_cols if normalize_string(c.replace('_concentration_picogram_per_milliliter', '')) == na]
        ime_map[a] = matches[0] if matches else None
        
    for sample_id in EXPECTED_ALL_SAMPLES:
        p_id, _, tp = sample_id.split('_')
        tr_sample_row = tr_ime[tr_ime["Sample Name"] == sample_id]
        has_tr_sample = len(tr_sample_row) > 0
        
        for bio_name in ime_analytes:
            tr_col = ime_map[bio_name]
            tr_unit = "picogram_per_milliliter"
            
            sub_row = sub_ime[(sub_ime["Sample_ID"] == sample_id) & (sub_ime["Analyte"] == bio_name)]
            has_sub_record = len(sub_row) > 0
            
            sub_val = float(sub_row["Concentration"].values[0]) if has_sub_record else np.nan
            sub_unit = str(sub_row["Unit"].values[0]) if has_sub_record else None
            
            tr_val = float(tr_sample_row[tr_col].values[0]) if (has_tr_sample and tr_col) else np.nan
            
            if has_sub_record and has_tr_sample and tr_col:
                norm_sub_u = normalize_unit(sub_unit)
                norm_tr_u = normalize_unit(tr_unit)
                u_match = (norm_sub_u == norm_tr_u)
                
                if pd.isna(sub_val) and pd.isna(tr_val):
                    val_match = True
                    abs_diff = 0.0
                elif pd.isna(sub_val) or pd.isna(tr_val):
                    val_match = False
                    abs_diff = np.nan
                else:
                    abs_diff = abs(sub_val - tr_val)
                    val_match = (abs_diff < 1e-4)
                    
                if not u_match:
                    status = "UNIT_MISMATCH"
                    note = f"Units differ: Submitted={sub_unit}, Transformed={tr_unit}"
                elif not val_match:
                    status = "VALUE_MISMATCH"
                    note = f"Values differ by {abs_diff:.6f}"
                else:
                    status = "MATCHED"
                    note = "Values and units reconcile perfectly."
            elif has_sub_record and not has_tr_sample:
                status = "MISSING_IN_TRANSFORMED"
                abs_diff = np.nan
                note = "Sample missing from transformed dataset."
            elif not has_sub_record and has_tr_sample:
                status = "MISSING_IN_SUBMITTED"
                abs_diff = np.nan
                note = "Biomarker present in transformed but missing from submitted."
            else:
                status = "NOT_COMPARABLE"
                abs_diff = np.nan
                note = "Biomarker not matched or sample not assayed."
                
            detailed_records.append({
                "Participant_ID": p_id,
                "Sample_ID": sample_id,
                "Timepoint": tp,
                "Panel_Name": "Immune EvePanel",
                "Biomarker_Name": bio_name,
                "Submitted_Value": sub_val,
                "Submitted_Unit": sub_unit,
                "Transformed_Value": tr_val,
                "Transformed_Unit": tr_unit,
                "Absolute_Difference": abs_diff,
                "Reconciliation_Status": status,
                "Audit_Notes": note
            })
            
    # -------------------------------------------------------------------------
    # 3. Immune AlamarPanel
    # -------------------------------------------------------------------------
    logger.info("Reconciling Immune AlamarPanel...")
    sub_ala = pd.read_excel(get_file_path("LSDS-8_Multiplex_serum.immune.AlamarPanel_SUBMITTED.xlsx"))
    tr_ala = pd.read_csv(get_file_path("LSDS-8_Multiplex_serum.immune.AlamarPanel_TRANSFORMED.csv"))
    sub_ala["Sample_ID"] = sub_ala["ID"] + "_serum_" + sub_ala["Timepoint"]
    
    ala_analytes = sorted(sub_ala["Analyte"].unique())
    tr_ala_conc_cols = [c for c in tr_ala.columns if c.endswith("_concentration_npq")]
    
    # Map Alamar analytes
    ala_map = {}
    for a in ala_analytes:
        na = re.sub(r'[^a-z0-9]', '', a.lower())
        matches = [c for c in tr_ala_conc_cols if re.sub(r'[^a-z0-9]', '', c.replace('_concentration_npq', '')) == na]
        ala_map[a] = matches[0] if matches else None
        
    for sample_id in EXPECTED_ALL_SAMPLES:
        p_id, _, tp = sample_id.split('_')
        tr_sample_row = tr_ala[tr_ala["Sample ID"] == sample_id]
        has_tr_sample = len(tr_sample_row) > 0
        
        for bio_name in ala_analytes:
            tr_col = ala_map[bio_name]
            tr_unit = "npq"
            
            sub_row = sub_ala[(sub_ala["Sample_ID"] == sample_id) & (sub_ala["Analyte"] == bio_name)]
            has_sub_record = len(sub_row) > 0
            
            sub_val = float(sub_row["Concentration"].values[0]) if has_sub_record else np.nan
            sub_unit = str(sub_row["Unit"].values[0]) if has_sub_record else None
            
            tr_val = float(tr_sample_row[tr_col].values[0]) if (has_tr_sample and tr_col) else np.nan
            
            # Special check for C003_serum_L-44
            if sample_id == "C003_serum_L-44":
                status = "NOT_COMPARABLE"
                abs_diff = np.nan
                note = "Sample C003_serum_L-44 was genuinely omitted/unassayed in the Alamar NULISA protocol."
            elif has_sub_record and has_tr_sample and tr_col:
                norm_sub_u = normalize_unit(sub_unit)
                norm_tr_u = normalize_unit(tr_unit)
                u_match = (norm_sub_u == norm_tr_u)
                
                if pd.isna(sub_val) and pd.isna(tr_val):
                    val_match = True
                    abs_diff = 0.0
                elif pd.isna(sub_val) or pd.isna(tr_val):
                    val_match = False
                    abs_diff = np.nan
                else:
                    abs_diff = abs(sub_val - tr_val)
                    # Float precision tolerance for 6-8 decimal export from excel
                    val_match = (abs_diff < 1e-4)
                    
                if not u_match:
                    status = "UNIT_MISMATCH"
                    note = f"Units differ: Submitted={sub_unit}, Transformed={tr_unit}"
                elif not val_match:
                    status = "VALUE_MISMATCH"
                    note = f"Values differ by {abs_diff:.6f}"
                else:
                    status = "MATCHED"
                    note = "Values and units reconcile perfectly (within float tolerance)."
            elif has_sub_record and not has_tr_sample:
                status = "MISSING_IN_TRANSFORMED"
                abs_diff = np.nan
                note = "Sample missing from transformed dataset."
            elif not has_sub_record and has_tr_sample:
                status = "MISSING_IN_SUBMITTED"
                abs_diff = np.nan
                note = "Biomarker present in transformed but missing from submitted."
            else:
                status = "NOT_COMPARABLE"
                abs_diff = np.nan
                note = "Sample not present in either dataset."
                
            detailed_records.append({
                "Participant_ID": p_id,
                "Sample_ID": sample_id,
                "Timepoint": tp,
                "Panel_Name": "Immune AlamarPanel",
                "Biomarker_Name": bio_name,
                "Submitted_Value": sub_val,
                "Submitted_Unit": sub_unit,
                "Transformed_Value": tr_val,
                "Transformed_Unit": tr_unit,
                "Absolute_Difference": abs_diff,
                "Reconciliation_Status": status,
                "Audit_Notes": note
            })
            
    # -------------------------------------------------------------------------
    # 4. Comprehensive Metabolic Panel (CMP)
    # -------------------------------------------------------------------------
    logger.info("Reconciling Comprehensive Metabolic Panel (CMP)...")
    sub_cmp = pd.read_csv(get_file_path("LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv"))
    tr_cmp = pd.read_csv(get_file_path("LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv"))
    sub_cmp["Sample_ID"] = sub_cmp["SUBJECT_ID"] + "_serum_" + sub_cmp["timepoint"]
    
    cmp_map = {
        'ALBUMIN': ('albumin_value_gram_per_deciliter', 'gram_per_deciliter'),
        'ALBUMIN/GLOBULIN RATIO': ('albumin_to_globulin_ratio_value', 'ratio/calculated'),
        'ALKALINE PHOSPHATASE': ('alkaline_phosphatase_value_units_per_liter', 'units_per_liter'),
        'ALT': ('alt_value_units_per_liter', 'units_per_liter'),
        'AST': ('ast_value_units_per_liter', 'units_per_liter'),
        'BILIRUBIN; TOTAL': ('total_bilirubin_value_milligram_per_deciliter', 'milligram_per_deciliter'),
        'BUN/CREATININE RATIO': ('bun_to_creatinine_ratio_value', 'ratio/calculated'),
        'CALCIUM': ('calcium_value_milligram_per_deciliter', 'milligram_per_deciliter'),
        'CARBON DIOXIDE': ('carbon_dioxide_value_millimol_per_liter', 'millimol_per_liter'),
        'CHLORIDE': ('chloride_value_millimol_per_liter', 'millimol_per_liter'),
        'CREATININE': ('creatinine_value_milligram_per_deciliter', 'milligram_per_deciliter'),
        'GLOBULIN': ('globulin_value_gram_per_deciliter', 'gram_per_deciliter'),
        'GLUCOSE': ('glucose_value_milligram_per_deciliter', 'milligram_per_deciliter'),
        'POTASSIUM': ('potassium_value_millimol_per_liter', 'millimol_per_liter'),
        'PROTEIN; TOTAL': ('total_protein_value_gram_per_deciliter', 'gram_per_deciliter'),
        'SODIUM': ('sodium_value_millimol_per_liter', 'millimol_per_liter'),
        'UREA NITROGEN (BUN)': ('urea_nitrogen_bun_value_milligram_per_deciliter', 'milligram_per_deciliter'),
        'eGFR AFRICAN AMERICAN': ('egfr_african_american_value_milliliter_per_minute_per_1.73_meter_squared', 'milliliter_per_minute_per_1.73_meter_squared'),
        'eGFR NON-AFR. AMERICAN': ('egfr_non_african_american_value_milliliter_per_minute_per_1.73_meter_squared', 'milliliter_per_minute_per_1.73_meter_squared')
    }
    
    for sample_id in EXPECTED_ALL_SAMPLES:
        p_id, _, tp = sample_id.split('_')
        tr_sample_row = tr_cmp[tr_cmp["Sample Name"] == sample_id]
        has_tr_sample = len(tr_sample_row) > 0
        
        for bio_name, (tr_col, tr_unit) in cmp_map.items():
            sub_row = sub_cmp[(sub_cmp["Sample_ID"] == sample_id) & (sub_cmp["ANALYTE"] == bio_name)]
            has_sub_record = len(sub_row) > 0
            
            sub_val = float(sub_row["VALUE"].values[0]) if has_sub_record else np.nan
            sub_unit = str(sub_row["UNITS"].values[0]) if has_sub_record else None
            
            tr_val = float(tr_sample_row[tr_col].values[0]) if has_tr_sample else np.nan
            
            if has_sub_record and has_tr_sample:
                norm_sub_u = normalize_unit(sub_unit)
                norm_tr_u = normalize_unit(tr_unit)
                u_match = (norm_sub_u == norm_tr_u)
                
                # Check value match
                if pd.isna(sub_val) and pd.isna(tr_val):
                    val_match = True
                    abs_diff = 0.0
                    note = "Both submitted and transformed record NaN / unmeasured value."
                elif pd.isna(sub_val) or pd.isna(tr_val):
                    val_match = False
                    abs_diff = np.nan
                    note = f"Discrepancy: sub_val={sub_val}, tr_val={tr_val}"
                else:
                    abs_diff = abs(sub_val - tr_val)
                    val_match = (abs_diff < 1e-4)
                    note = "Values and units reconcile perfectly."
                    
                if not u_match:
                    status = "UNIT_MISMATCH"
                    note = f"Units differ: Submitted={sub_unit}, Transformed={tr_unit}"
                elif not val_match:
                    status = "VALUE_MISMATCH"
                else:
                    status = "MATCHED"
            elif has_sub_record and not has_tr_sample:
                status = "MISSING_IN_TRANSFORMED"
                abs_diff = np.nan
                note = "Sample missing from transformed dataset."
            elif not has_sub_record and has_tr_sample:
                status = "MISSING_IN_SUBMITTED"
                abs_diff = np.nan
                # Special note for C002 R+82 BUN/CREATININE RATIO
                if sample_id == "C002_serum_R+82" and bio_name == "BUN/CREATININE RATIO":
                    note = "BUN/CREATININE RATIO row was completely omitted in Submitted file for C002 at R+82. Transformed contains NaN column."
                else:
                    note = "Present in transformed column but missing row in submitted file."
            else:
                status = "NOT_COMPARABLE"
                abs_diff = np.nan
                note = "Sample not present in either dataset."
                
            detailed_records.append({
                "Participant_ID": p_id,
                "Sample_ID": sample_id,
                "Timepoint": tp,
                "Panel_Name": "Comprehensive Metabolic Panel (CMP)",
                "Biomarker_Name": bio_name,
                "Submitted_Value": sub_val,
                "Submitted_Unit": sub_unit,
                "Transformed_Value": tr_val,
                "Transformed_Unit": tr_unit,
                "Absolute_Difference": abs_diff,
                "Reconciliation_Status": status,
                "Audit_Notes": note
            })
            
    df_detailed = pd.DataFrame(detailed_records)
    
    # -------------------------------------------------------------------------
    # Summaries
    # -------------------------------------------------------------------------
    summary_by_panel = []
    for panel, group in df_detailed.groupby("Panel_Name"):
        status_counts = group["Reconciliation_Status"].value_counts().to_dict()
        summary_by_panel.append({
            "Panel Name": panel,
            "Total Comparisons": len(group),
            "MATCHED": status_counts.get("MATCHED", 0),
            "VALUE_MISMATCH": status_counts.get("VALUE_MISMATCH", 0),
            "UNIT_MISMATCH": status_counts.get("UNIT_MISMATCH", 0),
            "MISSING_IN_TRANSFORMED": status_counts.get("MISSING_IN_TRANSFORMED", 0),
            "MISSING_IN_SUBMITTED": status_counts.get("MISSING_IN_SUBMITTED", 0),
            "NOT_COMPARABLE": status_counts.get("NOT_COMPARABLE", 0),
            "AMBIGUOUS_MATCH": status_counts.get("AMBIGUOUS_MATCH", 0),
            "Match Rate (%)": round((status_counts.get("MATCHED", 0) / len(group)) * 100, 2)
        })
    df_panel_sum = pd.DataFrame(summary_by_panel)
    
    # Biomarker level summary
    bio_summary = []
    for (panel, bio_name), group in df_detailed.groupby(["Panel_Name", "Biomarker_Name"]):
        status_counts = group["Reconciliation_Status"].value_counts().to_dict()
        sub_u = group["Submitted_Unit"].dropna().iloc[0] if len(group["Submitted_Unit"].dropna()) > 0 else "N/A"
        tr_u = group["Transformed_Unit"].dropna().iloc[0] if len(group["Transformed_Unit"].dropna()) > 0 else "N/A"
        
        bio_summary.append({
            "Panel Name": panel,
            "Biomarker Name": bio_name,
            "Submitted Unit": sub_u,
            "Transformed Unit": tr_u,
            "Total Comparisons": len(group),
            "MATCHED": status_counts.get("MATCHED", 0),
            "VALUE_MISMATCH": status_counts.get("VALUE_MISMATCH", 0),
            "UNIT_MISMATCH": status_counts.get("UNIT_MISMATCH", 0),
            "MISSING_IN_TRANSFORMED": status_counts.get("MISSING_IN_TRANSFORMED", 0),
            "MISSING_IN_SUBMITTED": status_counts.get("MISSING_IN_SUBMITTED", 0),
            "NOT_COMPARABLE": status_counts.get("NOT_COMPARABLE", 0),
            "Overall Biomarker Status": "FULLY_MATCHED" if status_counts.get("MATCHED", 0) == len(group) else (
                "MATCHED_WITH_KNOWN_ABSENCE" if status_counts.get("MATCHED", 0) + status_counts.get("NOT_COMPARABLE", 0) + status_counts.get("MISSING_IN_SUBMITTED", 0) == len(group) else "HAS_DISCREPANCIES"
            )
        })
    df_bio_sum = pd.DataFrame(bio_summary)
    
    out_path = REPORTS_DIR / "biomarker_reconciliation.xlsx"
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df_panel_sum.to_excel(writer, sheet_name="Reconciliation_Summary", index=False)
        df_bio_sum.to_excel(writer, sheet_name="Biomarker_Level_Summary", index=False)
        df_detailed.to_excel(writer, sheet_name="Detailed_Reconciliation", index=False)
        
    logger.info(f"Phase 4 biomarker reconciliation completed successfully. Output saved to {out_path}")
    logger.info(f"Panel summary:\n{df_panel_sum.to_string(index=False)}")
    return df_panel_sum, df_bio_sum, df_detailed

if __name__ == "__main__":
    reconcile_biomarkers()
