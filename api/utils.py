"""Utility functions for API data sanitization, caching, and dataset inspection."""
from pathlib import Path
from typing import Any, Dict, List, Optional
import math
import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
NASA_DATA_PATH = ROOT_DIR / "cleaned_data" / "WEDJAT_X_Master_Biomarker_Dataset.csv"
SYNTHETIC_DIR = ROOT_DIR / "synthetic_data"

_CACHED_NASA_DF: Optional[pd.DataFrame] = None


def get_nasa_dataframe() -> pd.DataFrame:
    """Load or return cached NASA OSD-575 master dataset."""
    global _CACHED_NASA_DF
    if _CACHED_NASA_DF is None:
        if not NASA_DATA_PATH.exists():
            raise FileNotFoundError(f"NASA Master Biomarker dataset not found at {NASA_DATA_PATH}")
        _CACHED_NASA_DF = pd.read_csv(NASA_DATA_PATH)
    return _CACHED_NASA_DF


def sanitize_for_json(obj: Any) -> Any:
    """Recursively convert NaN, Infinity, numpy types, and Path objects to JSON-compliant primitives."""
    if obj is None:
        return None
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (float, np.floating)):
        if math.isnan(obj) or math.isinf(obj) or np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (str, Path)):
        return str(obj)
    if isinstance(obj, dict):
        res = {}
        for k, v in obj.items():
            if str(k) == "is_synthetic":
                res[str(k)] = bool(v)
            else:
                res[str(k)] = sanitize_for_json(v)
        return res
    if isinstance(obj, (list, tuple, set, np.ndarray, pd.Series)):
        return [sanitize_for_json(item) for item in obj]
    if hasattr(obj, "to_dict"):
        return sanitize_for_json(obj.to_dict())
    return str(obj)
