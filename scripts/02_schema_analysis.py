"""
Phase 2: Schema Analysis
Analyzes and compares schemas between Submitted and Transformed files across all 4 panels.
Generates reports/schema_comparison.xlsx and audit_logs/02_schema_analysis.log.
"""
import sys
import os
import re
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import FILES_INFO, get_file_path, setup_logger, REPORTS_DIR, AUDIT_LOGS_DIR

logger = setup_logger("Phase2_SchemaAnalysis", "02_schema_analysis.log")

def analyze_schemas():
    logger.info("Starting Phase 2: Schema Analysis")
    
    panels = [
        "Comprehensive Metabolic Panel (CMP)",
        "Cardiovascular EvePanel",
        "Immune AlamarPanel",
        "Immune EvePanel"
    ]
    
    schema_summary = []
    submitted_col_dict = []
    transformed_col_dict = []
    mapping_rules = []
    
    for panel in panels:
        sub_meta = [f for f in FILES_INFO if f["panel_name"] == panel and f["source_type"] == "SUBMITTED"][0]
        tr_meta = [f for f in FILES_INFO if f["panel_name"] == panel and f["source_type"] == "TRANSFORMED"][0]
        
        # Read files
        sub_path = get_file_path(sub_meta["filename"])
        tr_path = get_file_path(tr_meta["filename"])
        
        df_sub = pd.read_excel(sub_path) if sub_meta["format"] == "Excel" else pd.read_csv(sub_path)
        df_tr = pd.read_csv(tr_path)
        
        # Analyze Submitted
        sub_id_col = "SUBJECT_ID" if "SUBJECT_ID" in df_sub.columns else "ID"
        sub_time_col = "timepoint" if "timepoint" in df_sub.columns else "Timepoint"
        sub_analyte_col = "ANALYTE" if "ANALYTE" in df_sub.columns else "Analyte"
        sub_val_col = "VALUE" if "VALUE" in df_sub.columns else "Concentration"
        sub_unit_col = "UNITS" if "UNITS" in df_sub.columns else "Unit"
        
        # Analyze Transformed
        tr_sample_col = "Sample ID" if "Sample ID" in df_tr.columns else "Sample Name"
        
        # Transformed format analysis
        # In Transformed, each row is a Sample, columns are analytes -> WIDE format
        tr_measure_cols = [c for c in df_tr.columns if c != tr_sample_col]
        
        # Record summary for panel
        schema_summary.append({
            "Panel Name": panel,
            "Submitted File": sub_meta["filename"],
            "Transformed File": tr_meta["filename"],
            "Submitted Format": "LONG",
            "Transformed Format": "WIDE",
            "Submitted Rows": df_sub.shape[0],
            "Submitted Cols": df_sub.shape[1],
            "Transformed Rows": df_tr.shape[0],
            "Transformed Cols": df_tr.shape[1],
            "Submitted Participant ID Column": sub_id_col,
            "Transformed Participant ID Representation": f"Derived from '{tr_sample_col}' (prefix before '_serum_')",
            "Submitted Sample ID Representation": f"Implicit / Composite ('{sub_id_col}' + '_serum_' + '{sub_time_col}')",
            "Transformed Sample ID Column": tr_sample_col,
            "Submitted Timepoint Column": sub_time_col,
            "Transformed Timepoint Representation": f"Derived from '{tr_sample_col}' (suffix after '_serum_')",
            "Submitted Biomarker Name Column": sub_analyte_col,
            "Transformed Biomarker Name Representation": "Encoded in column header prefixes",
            "Submitted Measurement Value Column": sub_val_col,
            "Transformed Measurement Value Representation": "Dedicated column per biomarker (e.g. *_value_* or *_concentration_*)",
            "Submitted Unit Column": sub_unit_col,
            "Transformed Unit Representation": "Standardized suffix in column names",
            "Submitted Secondary Measures": "Percent / Range Min / Range Max" if "Percent" in df_sub.columns or "RANGE_MIN" in df_sub.columns else "None",
            "Transformed Secondary Measures": "Normalized percent / Range columns"
        })
        
        # Populate Submitted Column Dictionary
        for col in df_sub.columns:
            submitted_col_dict.append({
                "Panel Name": panel,
                "File Name": sub_meta["filename"],
                "Column Name": col,
                "Data Type": str(df_sub[col].dtype),
                "Role": "Participant ID" if col == sub_id_col else (
                    "Timepoint" if col == sub_time_col else (
                        "Biomarker Name" if col == sub_analyte_col else (
                            "Measurement Value" if col == sub_val_col else (
                                "Measurement Unit" if col == sub_unit_col else "Metadata / Reference"
                            )
                        )
                    )
                ),
                "Sample Values": ", ".join(df_sub[col].dropna().astype(str).unique()[:3])
            })
            
        # Populate Transformed Column Dictionary
        for col in df_tr.columns:
            if col == tr_sample_col:
                role = "Sample Identifier (Composite Participant + Timepoint)"
                b_name = "N/A"
                metric = "Sample Identifier"
                unit = "N/A"
            else:
                if "CMP" in panel:
                    if "_value" in col:
                        b_name = col.split('_value')[0]
                        metric = "Primary Measurement Value"
                        unit = col.split('_value_')[-1] if '_value_' in col else "ratio/calculated"
                    elif "_range_min" in col:
                        b_name = col.split('_range_min')[0]
                        metric = "Reference Range Minimum"
                        unit = col.split('_range_min_')[-1] if '_range_min_' in col else "ratio/calculated"
                    elif "_range_max" in col or "_max" in col:
                        b_name = col.split('_range_max')[0].split('_max')[0]
                        metric = "Reference Range Maximum"
                        unit = col.split('_range_max_')[-1] if '_range_max_' in col else "ratio/calculated"
                    else:
                        b_name = col
                        metric = "Other"
                        unit = "Unknown"
                elif "Alamar" in panel:
                    if col.endswith("_concentration_npq"):
                        b_name = col[:-len("_concentration_npq")]
                        metric = "Concentration (NPQ)"
                        unit = "npq"
                    elif col.endswith("_percent_normalized_value"):
                        b_name = col[:-len("_percent_normalized_value")]
                        metric = "Normalized Percentage"
                        unit = "percent"
                    else:
                        b_name = col
                        metric = "Other"
                        unit = "Unknown"
                else:  # Eve panels
                    if "_concentration_" in col:
                        b_name = col.split('_concentration_')[0]
                        metric = "Concentration"
                        unit = col.split('_concentration_')[-1]
                    elif col.endswith("_percent"):
                        b_name = col[:-len("_percent")]
                        metric = "Normalized Percentage"
                        unit = "percent"
                    else:
                        b_name = col
                        metric = "Other"
                        unit = "Unknown"
                        
            transformed_col_dict.append({
                "Panel Name": panel,
                "File Name": tr_meta["filename"],
                "Column Name": col,
                "Detected Biomarker": b_name,
                "Measurement Metric": metric,
                "Extracted Unit": unit,
                "Data Type": str(df_tr[col].dtype),
                "Missing Values Count": int(df_tr[col].isna().sum())
            })
            
        mapping_rules.append({
            "Panel Name": panel,
            "Submitted Pattern": f"Row-level record with {sub_analyte_col}, {sub_val_col}, {sub_unit_col}",
            "Transformed Pattern": f"Column-level pivot: '{tr_sample_col}' as index, analytes expanded into wide columns",
            "Identifier Mapping": f"Transformed '{tr_sample_col}' <=> Submitted ('{sub_id_col}' + '_serum_' + '{sub_time_col}')",
            "Measurement Mapping": f"Transformed '<analyte>_value_*' / '<analyte>_concentration_*' <=> Submitted '{sub_val_col}'",
            "Unit Transformation": f"Submitted abbreviations (e.g. mg/dL, pg/ml) expanded to full snake_case names in Transformed columns"
        })
        
    df_schema_summary = pd.DataFrame(schema_summary)
    df_sub_dict = pd.DataFrame(submitted_col_dict)
    df_tr_dict = pd.DataFrame(transformed_col_dict)
    df_map_rules = pd.DataFrame(mapping_rules)
    
    out_path = REPORTS_DIR / "schema_comparison.xlsx"
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df_schema_summary.to_excel(writer, sheet_name="Schema_Comparison_Summary", index=False)
        df_sub_dict.to_excel(writer, sheet_name="Submitted_Column_Dictionary", index=False)
        df_tr_dict.to_excel(writer, sheet_name="Transformed_Column_Dictionary", index=False)
        df_map_rules.to_excel(writer, sheet_name="Structural_Transformation_Rules", index=False)
        
    logger.info(f"Phase 2 schema comparison completed successfully. Output saved to {out_path}")
    return df_schema_summary, df_sub_dict, df_tr_dict

if __name__ == "__main__":
    analyze_schemas()
