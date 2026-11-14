"""
Phase 1: File Inventory
Performs comprehensive inventory analysis of all 8 NASA OSD-575 dataset files.
Generates reports/file_inventory.xlsx and audit_logs/01_file_inventory.log.
"""
import sys
import os
import re
from pathlib import Path
import pandas as pd
import numpy as np

# Ensure scripts directory is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import FILES_INFO, get_file_path, setup_logger, REPORTS_DIR, AUDIT_LOGS_DIR

logger = setup_logger("Phase1_FileInventory", "01_file_inventory.log")

def extract_metadata_from_transformed(df: pd.DataFrame, sample_col: str, panel_name: str):
    """Extract participant IDs, timepoints, and biomarker names from wide transformed files."""
    sample_ids = df[sample_col].dropna().astype(str).tolist()
    participants = sorted(list(set([s.split('_')[0] for s in sample_ids if '_' in s])))
    timepoints = sorted(list(set([s.split('_')[-1] for s in sample_ids if '_' in s])))
    
    # Extract biomarker names based on panel
    cols = [c for c in df.columns if c != sample_col]
    biomarkers = set()
    
    if "CMP" in panel_name:
        for c in cols:
            if "_value" in c:
                b_name = c.split('_value')[0]
                biomarkers.add(b_name)
    elif "Alamar" in panel_name:
        for c in cols:
            if c.endswith("_concentration_npq"):
                b_name = c[:-len("_concentration_npq")]
                biomarkers.add(b_name)
    else:  # Eve panels
        for c in cols:
            if "_concentration_" in c:
                b_name = c.split('_concentration_')[0]
                biomarkers.add(b_name)
                
    return participants, timepoints, sorted(list(biomarkers))

def run_inventory():
    logger.info("Starting Phase 1: File Inventory Audit")
    
    inventory_summary = []
    column_details = []
    
    for file_meta in FILES_INFO:
        filename = file_meta["filename"]
        panel = file_meta["panel_name"]
        stype = file_meta["source_type"]
        fmt = file_meta["format"]
        
        logger.info(f"Auditing file: {filename} ({panel} - {stype})")
        file_path = get_file_path(filename)
        
        if fmt == "Excel":
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path)
            
        n_rows, n_cols = df.shape
        dup_rows = int(df.duplicated().sum())
        total_missing_cells = int(df.isna().sum().sum())
        
        # Determine participants, timepoints, biomarkers
        if stype == "SUBMITTED":
            # Detect ID column
            id_col = "SUBJECT_ID" if "SUBJECT_ID" in df.columns else "ID"
            time_col = "timepoint" if "timepoint" in df.columns else "Timepoint"
            analyte_col = "ANALYTE" if "ANALYTE" in df.columns else "Analyte"
            
            participants = sorted(df[id_col].dropna().astype(str).unique().tolist())
            timepoints = sorted(df[time_col].dropna().astype(str).unique().tolist())
            biomarkers = sorted(df[analyte_col].dropna().astype(str).unique().tolist())
        else:
            # Transformed (wide)
            sample_col = "Sample ID" if "Sample ID" in df.columns else "Sample Name"
            participants, timepoints, biomarkers = extract_metadata_from_transformed(df, sample_col, panel)
            
        logger.info(
            f"  -> Rows: {n_rows}, Cols: {n_cols}, Duplicates: {dup_rows}, "
            f"Participants: {len(participants)}, Timepoints: {len(timepoints)}, Biomarkers: {len(biomarkers)}"
        )
        
        inventory_summary.append({
            "File Name": filename,
            "Panel Name": panel,
            "Source Type": stype,
            "File Format": fmt,
            "Number of Rows": n_rows,
            "Number of Columns": n_cols,
            "Duplicate Rows": dup_rows,
            "Total Missing Cells": total_missing_cells,
            "Unique Participants Count": len(participants),
            "Unique Participants": ", ".join(participants),
            "Unique Timepoints Count": len(timepoints),
            "Unique Timepoints": ", ".join(timepoints),
            "Unique Biomarkers Count": len(biomarkers),
            "Sample Biomarkers (First 5)": ", ".join(biomarkers[:5])
        })
        
        for col in df.columns:
            missing_cnt = int(df[col].isna().sum())
            missing_pct = round((missing_cnt / n_rows) * 100, 2)
            dtype_str = str(df[col].dtype)
            n_unique = int(df[col].nunique(dropna=True))
            sample_vals = ", ".join(df[col].dropna().astype(str).unique()[:3])
            
            column_details.append({
                "File Name": filename,
                "Panel Name": panel,
                "Source Type": stype,
                "Column Name": col,
                "Data Type": dtype_str,
                "Missing Values Count": missing_cnt,
                "Missing Percentage (%)": missing_pct,
                "Unique Values Count": n_unique,
                "Sample Values": sample_vals
            })
            
    df_summary = pd.DataFrame(inventory_summary)
    df_columns = pd.DataFrame(column_details)
    
    out_path = REPORTS_DIR / "file_inventory.xlsx"
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df_summary.to_excel(writer, sheet_name="File_Inventory_Summary", index=False)
        df_columns.to_excel(writer, sheet_name="Column_Level_Inventory", index=False)
        
    logger.info(f"Phase 1 inventory completed successfully. Output saved to {out_path}")
    return df_summary, df_columns

if __name__ == "__main__":
    run_inventory()
