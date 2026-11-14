"""
WEDJAT-X Configuration Module
Defines paths, file inventories, panel metadata, and logging utilities.
"""
import os
import sys
import logging
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_RAW_DIR = BASE_DIR / "data" / "raw"
EXTERNAL_DOWNLOAD_DIR = Path(
    os.environ.get("WEDJAT_EXTERNAL_DOWNLOAD_DIR", str(BASE_DIR / "data" / "external_downloads"))
).expanduser()
REPORTS_DIR = BASE_DIR / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
CLEANED_DATA_DIR = BASE_DIR / "cleaned_data"
AUDIT_LOGS_DIR = BASE_DIR / "audit_logs"
SCRIPTS_DIR = BASE_DIR / "scripts"

for d in [DATA_RAW_DIR, REPORTS_DIR, FIGURES_DIR, CLEANED_DATA_DIR, AUDIT_LOGS_DIR, SCRIPTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# File registry
FILES_INFO = [
    {
        "panel_name": "Comprehensive Metabolic Panel (CMP)",
        "source_type": "SUBMITTED",
        "filename": "LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv",
        "format": "CSV"
    },
    {
        "panel_name": "Comprehensive Metabolic Panel (CMP)",
        "source_type": "TRANSFORMED",
        "filename": "LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv",
        "format": "CSV"
    },
    {
        "panel_name": "Cardiovascular EvePanel",
        "source_type": "SUBMITTED",
        "filename": "LSDS-8_Multiplex_serum.cardiovascular.EvePanel_SUBMITTED.csv",
        "format": "CSV"
    },
    {
        "panel_name": "Cardiovascular EvePanel",
        "source_type": "TRANSFORMED",
        "filename": "LSDS-8_Multiplex_serum_cardiovascular_EvePanel_TRANSFORMED.csv",
        "format": "CSV"
    },
    {
        "panel_name": "Immune AlamarPanel",
        "source_type": "SUBMITTED",
        "filename": "LSDS-8_Multiplex_serum.immune.AlamarPanel_SUBMITTED.xlsx",
        "format": "Excel"
    },
    {
        "panel_name": "Immune AlamarPanel",
        "source_type": "TRANSFORMED",
        "filename": "LSDS-8_Multiplex_serum.immune.AlamarPanel_TRANSFORMED.csv",
        "format": "CSV"
    },
    {
        "panel_name": "Immune EvePanel",
        "source_type": "SUBMITTED",
        "filename": "LSDS-8_Multiplex_serum.immune.EvePanel_SUBMITTED.csv",
        "format": "CSV"
    },
    {
        "panel_name": "Immune EvePanel",
        "source_type": "TRANSFORMED",
        "filename": "LSDS-8_Multiplex_serum_immune_EvePanel_TRANSFORMED.csv",
        "format": "CSV"
    }
]

def get_file_path(filename: str) -> Path:
    """Locate file in data/raw or fallback to external download directory."""
    local_path = DATA_RAW_DIR / filename
    if local_path.exists():
        return local_path
    external_path = EXTERNAL_DOWNLOAD_DIR / filename
    if external_path.exists():
        return external_path
    raise FileNotFoundError(f"Source file not found: {filename}")

def setup_logger(name: str, log_filename: str = None) -> logging.Logger:
    """Configure a logger that writes to stdout and an audit log file."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
        
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Stream Handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    
    # File Handler
    if log_filename:
        log_path = AUDIT_LOGS_DIR / log_filename
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
    return logger
