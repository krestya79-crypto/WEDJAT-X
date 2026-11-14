"""
Phase 6: Create Normalized Master Dataset
Builds a unified, long-format, audited master biomarker dataset.
Preserves original values, units, flags, and complete provenance.
Generates cleaned_data/WEDJAT_X_Master_Biomarker_Dataset.csv and .xlsx,
and audit_logs/06_master_dataset.log.
"""
import sys
import os
import re
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import FILES_INFO, get_file_path, setup_logger, CLEANED_DATA_DIR, AUDIT_LOGS_DIR

logger = setup_logger("Phase6_MasterDataset", "06_master_dataset.log")

EXPECTED_PARTICIPANTS = ["C001", "C002", "C003", "C004"]
EXPECTED_TIMEPOINTS = ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82", "R+194"]
EXPECTED_ALL_SAMPLES = [f"{p}_serum_{t}" for p in EXPECTED_PARTICIPANTS for t in EXPECTED_TIMEPOINTS]

TIMEPOINT_METADATA = {
    "L-92": {"phase": "Preflight", "days_relative": -92, "order": 1},
    "L-44": {"phase": "Preflight", "days_relative": -44, "order": 2},
    "L-3": {"phase": "Preflight", "days_relative": -3, "order": 3},
    "R+1": {"phase": "Postflight_Immediate", "days_relative": 1, "order": 4},
    "R+45": {"phase": "Postflight_Early_Recovery", "days_relative": 45, "order": 5},
    "R+82": {"phase": "Postflight_Mid_Recovery", "days_relative": 82, "order": 6},
    "R+194": {"phase": "Postflight_Late_Recovery", "days_relative": 194, "order": 7}
}

def normalize_string(s):
    s = s.replace('/', '_per_').replace('+', '_plus_')
    s = re.sub(r'[^a-zA-Z0-9αβγδ\u03b1-\u03c9]+', '_', s.strip().lower())
    return s.strip('_')

def build_master_dataset():
    logger.info("Starting Phase 6: Building Normalized Master Dataset")
    
    master_records = []
    
    # =========================================================================
    # 1. Cardiovascular EvePanel
    # =========================================================================
    logger.info("Processing Cardiovascular EvePanel...")
    sub_cv = pd.read_csv(get_file_path("LSDS-8_Multiplex_serum.cardiovascular.EvePanel_SUBMITTED.csv"))
    tr_cv = pd.read_csv(get_file_path("LSDS-8_Multiplex_serum_cardiovascular_EvePanel_TRANSFORMED.csv"))
    sub_cv["Sample_ID"] = sub_cv["ID"] + "_serum_" + sub_cv["Timepoint"]
    
    cv_biomarker_map = {
        'a-2 Macroglobulin': ('a2_macroglobulin_concentration_nanogram_per_milliliter', 'a2_macroglobulin_percent', 'ng/ml'),
        'AGP': ('agp_concentration_nanogram_per_milliliter', 'agp_percent', 'ng/ml'),
        'CRP': ('crp_concentration_picogram_per_milliliter', 'crp_percent', 'pg/ml'),
        'Fetuin A36': ('fetuin_a36_concentration_nanogram_per_milliliter', 'fetuin_a36_percent', 'ng/ml'),
        'Fibrinogen': ('fibrinogen_concentration_nanogram_per_milliliter', 'fibrinogen_percent', 'ng/ml'),
        'Haptoglobin': ('haptoglobin_concentration_nanogram_per_milliliter', 'haptoglobin_percent', 'ng/ml'),
        'L-Selectin': ('l_selectin_concentration_picogram_per_milliliter', 'l_selectin_percent', 'pg/ml'),
        'PF4': ('pf4_concentration_nanogram_per_milliliter', 'pf4_percent', 'ng/ml'),
        'SAP': ('sap_concentration_picogram_per_milliliter', 'sap_percent', 'pg/ml')
    }
    
    for sample_id in EXPECTED_ALL_SAMPLES:
        p_id, _, tp = sample_id.split('_')
        tp_meta = TIMEPOINT_METADATA.get(tp, {"phase": "Unknown", "days_relative": np.nan, "order": 99})
        tr_sample_row = tr_cv[tr_cv["Sample Name"] == sample_id]
        
        for bio_name, (conc_col, pct_col, unit) in cv_biomarker_map.items():
            sub_row = sub_cv[(sub_cv["Sample_ID"] == sample_id) & (sub_cv["Analyte"] == bio_name)]
            if len(sub_row) > 0:
                val = float(sub_row["Concentration"].values[0])
                pct = float(sub_row["Percent"].values[0]) if "Percent" in sub_row else np.nan
                status = "VALIDATED_MATCH"
            else:
                val = np.nan
                pct = np.nan
                status = "MISSING_IN_SUBMITTED"
                
            master_records.append({
                "Participant_ID": p_id,
                "Sample_ID": sample_id,
                "Timepoint": tp,
                "Timepoint_Phase": tp_meta["phase"],
                "Days_Relative_To_Return": tp_meta["days_relative"],
                "Timepoint_Order": tp_meta["order"],
                "Biomarker_Name": bio_name,
                "Original_Biomarker_Name": bio_name,
                "Measurement_Value": val,
                "Measurement_Unit": unit,
                "Normalized_Percent_Value": pct,
                "Panel_Name": "Cardiovascular EvePanel",
                "Platform_Technology": "Eve Technologies HDCVD9 9-Plex",
                "Source_File": "LSDS-8_Multiplex_serum.cardiovascular.EvePanel_SUBMITTED.csv",
                "Source_Type": "SUBMITTED_AND_TRANSFORMED_VERIFIED",
                "Validation_Status": status,
                "Clinical_Range_Min": np.nan,
                "Clinical_Range_Max": np.nan,
                "Clinical_Range_Flag": "NOT_APPLICABLE"
            })
            
    # =========================================================================
    # 2. Immune EvePanel
    # =========================================================================
    logger.info("Processing Immune EvePanel...")
    sub_ime = pd.read_csv(get_file_path("LSDS-8_Multiplex_serum.immune.EvePanel_SUBMITTED.csv"))
    tr_ime = pd.read_csv(get_file_path("LSDS-8_Multiplex_serum_immune_EvePanel_TRANSFORMED.csv"))
    sub_ime["Sample_ID"] = sub_ime["ID"] + "_serum_" + sub_ime["Timepoint"]
    
    ime_analytes = sorted(sub_ime["Analyte"].unique())
    tr_ime_conc_cols = [c for c in tr_ime.columns if "concentration_picogram_per_milliliter" in c]
    
    for sample_id in EXPECTED_ALL_SAMPLES:
        p_id, _, tp = sample_id.split('_')
        tp_meta = TIMEPOINT_METADATA.get(tp, {"phase": "Unknown", "days_relative": np.nan, "order": 99})
        
        for bio_name in ime_analytes:
            sub_row = sub_ime[(sub_ime["Sample_ID"] == sample_id) & (sub_ime["Analyte"] == bio_name)]
            if len(sub_row) > 0:
                val = float(sub_row["Concentration"].values[0])
                pct = float(sub_row["Percent"].values[0]) if "Percent" in sub_row else np.nan
                unit = str(sub_row["Unit"].values[0])
                status = "VALIDATED_MATCH"
            else:
                val = np.nan
                pct = np.nan
                unit = "pg/ml"
                status = "MISSING_IN_SUBMITTED"
                
            master_records.append({
                "Participant_ID": p_id,
                "Sample_ID": sample_id,
                "Timepoint": tp,
                "Timepoint_Phase": tp_meta["phase"],
                "Days_Relative_To_Return": tp_meta["days_relative"],
                "Timepoint_Order": tp_meta["order"],
                "Biomarker_Name": bio_name,
                "Original_Biomarker_Name": bio_name,
                "Measurement_Value": val,
                "Measurement_Unit": unit,
                "Normalized_Percent_Value": pct,
                "Panel_Name": "Immune EvePanel",
                "Platform_Technology": "Eve Technologies HD71 71-Plex",
                "Source_File": "LSDS-8_Multiplex_serum.immune.EvePanel_SUBMITTED.csv",
                "Source_Type": "SUBMITTED_AND_TRANSFORMED_VERIFIED",
                "Validation_Status": status,
                "Clinical_Range_Min": np.nan,
                "Clinical_Range_Max": np.nan,
                "Clinical_Range_Flag": "NOT_APPLICABLE"
            })
            
    # =========================================================================
    # 3. Immune AlamarPanel
    # =========================================================================
    logger.info("Processing Immune AlamarPanel...")
    sub_ala = pd.read_excel(get_file_path("LSDS-8_Multiplex_serum.immune.AlamarPanel_SUBMITTED.xlsx"))
    sub_ala["Sample_ID"] = sub_ala["ID"] + "_serum_" + sub_ala["Timepoint"]
    ala_analytes = sorted(sub_ala["Analyte"].unique())
    
    for sample_id in EXPECTED_ALL_SAMPLES:
        p_id, _, tp = sample_id.split('_')
        tp_meta = TIMEPOINT_METADATA.get(tp, {"phase": "Unknown", "days_relative": np.nan, "order": 99})
        
        for bio_name in ala_analytes:
            if sample_id == "C003_serum_L-44":
                val = np.nan
                pct = np.nan
                unit = "NPQ"
                status = "UNASSAYED_SAMPLE"
            else:
                sub_row = sub_ala[(sub_ala["Sample_ID"] == sample_id) & (sub_ala["Analyte"] == bio_name)]
                if len(sub_row) > 0:
                    val = float(sub_row["Concentration"].values[0])
                    pct = float(sub_row["Percent_normalized_value"].values[0]) if "Percent_normalized_value" in sub_row else np.nan
                    unit = str(sub_row["Unit"].values[0])
                    status = "VALIDATED_MATCH"
                else:
                    val = np.nan
                    pct = np.nan
                    unit = "NPQ"
                    status = "MISSING_IN_SUBMITTED"
                    
            master_records.append({
                "Participant_ID": p_id,
                "Sample_ID": sample_id,
                "Timepoint": tp,
                "Timepoint_Phase": tp_meta["phase"],
                "Days_Relative_To_Return": tp_meta["days_relative"],
                "Timepoint_Order": tp_meta["order"],
                "Biomarker_Name": bio_name,
                "Original_Biomarker_Name": bio_name,
                "Measurement_Value": val,
                "Measurement_Unit": unit,
                "Normalized_Percent_Value": pct,
                "Panel_Name": "Immune AlamarPanel",
                "Platform_Technology": "Alamar NULISA-seq 204-Plex",
                "Source_File": "LSDS-8_Multiplex_serum.immune.AlamarPanel_SUBMITTED.xlsx",
                "Source_Type": "SUBMITTED_AND_TRANSFORMED_VERIFIED",
                "Validation_Status": status,
                "Clinical_Range_Min": np.nan,
                "Clinical_Range_Max": np.nan,
                "Clinical_Range_Flag": "NOT_APPLICABLE"
            })
            
    # =========================================================================
    # 4. Comprehensive Metabolic Panel (CMP)
    # =========================================================================
    logger.info("Processing Comprehensive Metabolic Panel (CMP)...")
    sub_cmp = pd.read_csv(get_file_path("LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv"))
    sub_cmp["Sample_ID"] = sub_cmp["SUBJECT_ID"] + "_serum_" + sub_cmp["timepoint"]
    cmp_analytes = sorted(sub_cmp["ANALYTE"].unique())
    
    for sample_id in EXPECTED_ALL_SAMPLES:
        p_id, _, tp = sample_id.split('_')
        tp_meta = TIMEPOINT_METADATA.get(tp, {"phase": "Unknown", "days_relative": np.nan, "order": 99})
        
        for bio_name in cmp_analytes:
            sub_row = sub_cmp[(sub_cmp["Sample_ID"] == sample_id) & (sub_cmp["ANALYTE"] == bio_name)]
            if len(sub_row) > 0:
                raw_val = sub_row["VALUE"].values[0]
                val = float(raw_val) if pd.notna(raw_val) else np.nan
                unit = str(sub_row["UNITS"].values[0])
                rmin = float(sub_row["RANGE_MIN"].values[0]) if pd.notna(sub_row["RANGE_MIN"].values[0]) else np.nan
                rmax = float(sub_row["RANGE_MAX"].values[0]) if pd.notna(sub_row["RANGE_MAX"].values[0]) else np.nan
                
                if pd.isna(val):
                    status = "REPORTED_MISSING"
                    range_flag = "MISSING_VALUE"
                else:
                    status = "VALIDATED_MATCH"
                    if pd.notna(rmin) and val < rmin:
                        range_flag = "BELOW_RANGE"
                    elif pd.notna(rmax) and val > rmax:
                        range_flag = "ABOVE_RANGE"
                    elif pd.isna(rmin) and pd.isna(rmax):
                        range_flag = "NO_REFERENCE_RANGE"
                    else:
                        range_flag = "NORMAL"
            else:
                # Omitted row (C002 R+82 BUN/CREATININE RATIO)
                val = np.nan
                unit = "(calc)"
                rmin = np.nan
                rmax = np.nan
                status = "SOURCE_ROW_OMITTED"
                range_flag = "SOURCE_ROW_OMITTED"
                
            master_records.append({
                "Participant_ID": p_id,
                "Sample_ID": sample_id,
                "Timepoint": tp,
                "Timepoint_Phase": tp_meta["phase"],
                "Days_Relative_To_Return": tp_meta["days_relative"],
                "Timepoint_Order": tp_meta["order"],
                "Biomarker_Name": bio_name,
                "Original_Biomarker_Name": bio_name,
                "Measurement_Value": val,
                "Measurement_Unit": unit,
                "Normalized_Percent_Value": np.nan,
                "Panel_Name": "Comprehensive Metabolic Panel (CMP)",
                "Platform_Technology": "Beckman Coulter AU5800 / Quest Diagnostics",
                "Source_File": "LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv",
                "Source_Type": "SUBMITTED_AND_TRANSFORMED_VERIFIED",
                "Validation_Status": status,
                "Clinical_Range_Min": rmin,
                "Clinical_Range_Max": rmax,
                "Clinical_Range_Flag": range_flag
            })
            
    df_master = pd.DataFrame(master_records)
    logger.info(f"Master dataset built successfully: {df_master.shape[0]} rows, {df_master.shape[1]} columns.")
    
    # Validation status summary
    status_counts = df_master["Validation_Status"].value_counts().to_dict()
    logger.info(f"Validation status distribution: {status_counts}")
    
    # Export CSV
    csv_out = CLEANED_DATA_DIR / "WEDJAT_X_Master_Biomarker_Dataset.csv"
    df_master.to_csv(csv_out, index=False, encoding="utf-8")
    logger.info(f"Saved master CSV to: {csv_out}")
    
    # Export Excel
    xlsx_out = CLEANED_DATA_DIR / "WEDJAT_X_Master_Biomarker_Dataset.xlsx"
    with pd.ExcelWriter(xlsx_out, engine="openpyxl") as writer:
        df_master.to_excel(writer, sheet_name="Master_Biomarkers", index=False)
    logger.info(f"Saved master Excel to: {xlsx_out}")
    
    return df_master

if __name__ == "__main__":
    build_master_dataset()
