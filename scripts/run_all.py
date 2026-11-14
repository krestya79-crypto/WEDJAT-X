"""
WEDJAT-X Master Pipeline Runner
Executes Phase 1 through Phase 8 sequentially, verifying each step.
"""
import sys
import subprocess
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"

PHASE_SCRIPTS = [
    ("Phase 1: File Inventory", SCRIPTS_DIR / "01_file_inventory.py"),
    ("Phase 2: Schema Analysis", SCRIPTS_DIR / "02_schema_analysis.py"),
    ("Phase 3: Sample Reconciliation", SCRIPTS_DIR / "03_sample_reconciliation.py"),
    ("Phase 4: Biomarker Reconciliation", SCRIPTS_DIR / "04_biomarker_reconciliation.py"),
    ("Phase 5: Data Quality Assessment", SCRIPTS_DIR / "05_data_quality.py"),
    ("Phase 6: Master Dataset Creation", SCRIPTS_DIR / "06_master_dataset.py"),
    ("Phase 7: Individual Baseline Analysis", SCRIPTS_DIR / "07_baseline_analysis.py"),
    ("Phase 8: Scientific Visualization", SCRIPTS_DIR / "08_visualization.py")
]

def run_pipeline():
    print("=" * 80)
    print("WEDJAT-X: NASA OSD-575 AUDIT & RECONCILIATION PIPELINE")
    print("=" * 80)
    
    start_total = time.time()
    
    for phase_name, script_path in PHASE_SCRIPTS:
        print(f"\n>>> Running: {phase_name} ({script_path.name})")
        t0 = time.time()
        res = subprocess.run([sys.executable, str(script_path)], cwd=str(BASE_DIR))
        elapsed = time.time() - t0
        if res.returncode != 0:
            print(f"[ERROR] {phase_name} failed with exit code {res.returncode}")
            sys.exit(res.returncode)
        print(f"[SUCCESS] {phase_name} completed in {elapsed:.2f}s")
        
    total_elapsed = time.time() - start_total
    print("\n" + "=" * 80)
    print(f"ALL AUDIT PHASES COMPLETED SUCCESSFULLY IN {total_elapsed:.2f}s")
    print("=" * 80)

if __name__ == "__main__":
    run_pipeline()
