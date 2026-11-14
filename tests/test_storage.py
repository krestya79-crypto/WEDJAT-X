import json

from application.orchestrator import WEDJATXSystem
from application.result_manager import ResultManager
from application.schemas import SourceType
from application.storage import SQLiteStore


def test_sqlite_persistence_and_retrieval(tmp_path):
    store = SQLiteStore(tmp_path / "offline" / "history.sqlite3")
    result = ResultManager().create_result(
        source_type=SourceType.SYNTHETIC_WEARABLE.value, subject_id="demo",
        is_synthetic=True,
        sensor_trust_analysis={"quality_score": 0.8},
        alert_summary={"active_alerts": [{"alert_id": "ALT-TEST-1", "alert_state": "REVIEW", "explanation": "test evidence"}]},
    )
    store.save_result(result)
    nasa_result = ResultManager().create_result(
        source_type=SourceType.NASA_LAB.value, subject_id="C001", is_synthetic=False,
    )
    store.save_result(nasa_result)
    assert store.latest()["request_id"] == nasa_result.request_id
    assert store.latest(source_type=SourceType.SYNTHETIC_WEARABLE)["request_id"] == result.request_id
    assert store.latest(source_type=SourceType.NASA_LAB)["request_id"] == nasa_result.request_id
    assert next(row for row in store.history() if row["request_id"] == result.request_id)["is_synthetic"] is True
    assert store.recent_alerts()[0]["explanation"] == "test evidence"
    detail = store.alert_detail("ALT-TEST-1")
    assert detail["request_id"] == result.request_id
    assert detail["analysis"]["request_id"] == result.request_id
    json.dumps(store.latest(), allow_nan=False)


def test_orchestrator_persists_completed_analysis(tmp_path):
    system = WEDJATXSystem(base_dir=tmp_path)
    # All-null payload is valid but yields explicit INSUFFICIENT_DATA, and still audits.
    import pandas as pd
    stream = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=4, freq="s"),
        "sensor_type": "heart_rate", "signal_value": [None] * 4,
        "is_synthetic": True,
    })
    result = system.process(stream, "SYNTHETIC_WEARABLE", is_synthetic=True)
    assert system.get_latest_analysis()["request_id"] == result.request_id
    assert system.get_analysis_history(5)
