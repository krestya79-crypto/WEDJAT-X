"""
WEDJAT-X Phase 7 — Unit Tests for DataManager
Tests offline file ingestion, batch reading, and structured report exports.
"""

import json
from pathlib import Path
import tempfile
import numpy as np
import pandas as pd
import pytest

from application.data_manager import DataManager
from application.exceptions import ValidationError
from application.result_manager import ResultManager
from application.schemas import ProcessingResult, ProcessingStatus, SourceType


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def data_manager(temp_dir: Path) -> DataManager:
    return DataManager(base_dir=temp_dir)


def test_load_csv_dataset(data_manager: DataManager, temp_dir: Path) -> None:
    """Verify clean CSV ingestion."""
    csv_path = temp_dir / "sample.csv"
    df_orig = pd.DataFrame({"col_a": [1, 2, 3], "col_b": [4.0, 5.5, 6.0]})
    df_orig.to_csv(csv_path, index=False)

    df_loaded = data_manager.load_dataset(csv_path)
    assert len(df_loaded) == 3
    assert list(df_loaded.columns) == ["col_a", "col_b"]


def test_load_json_dataset(data_manager: DataManager, temp_dir: Path) -> None:
    """Verify clean JSON ingestion."""
    json_path = temp_dir / "sample.json"
    data = [{"sensor": "hr", "val": 70}, {"sensor": "hr", "val": 72}]
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    df_loaded = data_manager.load_dataset(json_path)
    assert len(df_loaded) == 2
    assert "val" in df_loaded.columns


def test_file_not_found(data_manager: DataManager, temp_dir: Path) -> None:
    """Verify non-existent files raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        data_manager.load_dataset(temp_dir / "nonexistent.csv")


def test_save_and_reload_result_json(data_manager: DataManager, temp_dir: Path) -> None:
    """Verify ProcessingResult serializes and saves to JSON without data corruption."""
    rm = ResultManager()
    res = rm.create_result(
        source_type=SourceType.SYNTHETIC_WEARABLE.value,
        subject_id="Astro_Test",
        is_synthetic=True,
        measurements=[{"val": 80.0}],
        alert_summary={"highest_operational_state": "NORMAL"},
    )

    out_file = temp_dir / "output" / "test_result.json"
    saved_path = data_manager.save_result_json(res, out_file)

    assert saved_path.exists()
    with open(saved_path, "r", encoding="utf-8") as f:
        reloaded = json.load(f)

    assert reloaded["system"] == "WEDJAT-X"
    assert reloaded["subject_id"] == "Astro_Test"
    assert reloaded["is_synthetic"] is True


def test_save_batch_results(data_manager: DataManager, temp_dir: Path) -> None:
    """Verify batch result saving writes individual files with unique IDs."""
    rm = ResultManager()
    r1 = rm.create_result(source_type=SourceType.NASA_LAB.value, subject_id="C001")
    r2 = rm.create_result(source_type=SourceType.NASA_LAB.value, subject_id="C002")

    batch_dir = temp_dir / "batch_out"
    saved_paths = data_manager.save_batch_results([r1, r2], output_dir=batch_dir)

    assert len(saved_paths) == 2
    assert all(p.exists() for p in saved_paths)


def test_export_summary_to_excel(data_manager: DataManager, temp_dir: Path) -> None:
    """Verify multi-sheet Excel export creates valid workbook."""
    rm = ResultManager()
    r1 = rm.create_result(
        source_type=SourceType.NASA_LAB.value,
        subject_id="C001",
        alert_summary={"highest_operational_state": "REVIEW", "active_alert_count": 1, "active_alerts": [{"measurement_name": "IL-6", "alert_state": "REVIEW"}]}
    )
    excel_path = temp_dir / "summary.xlsx"
    data_manager.export_summary_to_excel([r1], excel_path)

    assert excel_path.exists()
    with pd.ExcelFile(excel_path) as xl:
        assert "Execution_Summary" in xl.sheet_names
        assert "Active_Alerts" in xl.sheet_names
