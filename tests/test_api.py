"""Comprehensive API tests for WEDJAT-X FastAPI adapter."""
import pytest
from fastapi.testclient import TestClient
from api.main import app
from application import service
from application.storage import SQLiteStore


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    system = service._system()
    original_storage = system.storage
    system.storage = SQLiteStore(tmp_path_factory.mktemp("api-db") / "wedjatx.sqlite3")
    try:
        with TestClient(app) as c:
            yield c
    finally:
        system.storage = original_storage


def test_root_endpoint(client: TestClient):
    response = client.get("/api")
    assert response.status_code == 200
    data = response.json()
    assert data["system"] == "WEDJAT-X"
    assert data["status"] == "OPERATIONAL"
    assert "disclaimer" in data

    # Verify frontend static root serves 200
    root_res = client.get("/")
    assert root_res.status_code == 200


def test_health_endpoint(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["system"] == "WEDJAT-X"
    assert data["backend_version"] == "1.0.0"
    assert "timestamp" in data


def test_system_status_endpoint(client: TestClient):
    response = client.get("/api/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["system"] == "WEDJAT-X"
    assert "status" in data
    assert "initialized_engines" in data
    assert "supported_data_sources" in data


def test_dashboard_metrics_endpoint(client: TestClient):
    response = client.get("/api/metrics")
    assert response.status_code == 200
    metrics = response.json()
    assert isinstance(metrics["analysis_count"], int)
    assert isinstance(metrics["active_alert_count"], int)
    assert isinstance(metrics["persisted_active_alert_count"], int)
    trust = metrics["latest_sensor_trust"]
    assert trust is None or trust["is_synthetic"] is True


def test_nasa_participants_endpoint(client: TestClient):
    response = client.get("/api/nasa/participants")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    pids = [p["participant_id"] for p in data]
    assert "C001" in pids
    assert "C002" in pids
    assert "C003" in pids
    assert "C004" in pids


def test_nasa_biomarkers_endpoint(client: TestClient):
    response = client.get("/api/nasa/biomarkers?participant_id=C001")
    assert response.status_code == 200
    data = response.json()
    assert "total_biomarkers" in data
    assert "panels" in data
    assert "timepoints" in data
    assert len(data["biomarkers"]) > 0


def test_nasa_participant_data_endpoint(client: TestClient):
    response = client.get("/api/nasa/participant-data?participant_id=C001&biomarker_name=ALT")
    assert response.status_code == 200
    data = response.json()
    assert data["participant_id"] == "C001"
    assert data["biomarker_name"] == "ALT"
    assert "records" in data
    assert data["record_count"] > 0
    assert data["baseline_info"] is not None


def test_nasa_queries_are_isolated_by_selected_participant(client: TestClient):
    participant_values = {}
    for participant_id in ("C001", "C002", "C003", "C004"):
        catalog = client.get(
            "/api/nasa/biomarkers",
            params={"participant_id": participant_id.lower()},
        )
        assert catalog.status_code == 200
        assert catalog.json()["participant_id"] == participant_id

        response = client.get(
            "/api/nasa/participant-data",
            params={
                "participant_id": participant_id.lower(),
                "biomarker_name": "ALT",
                "panel_name": "Comprehensive Metabolic Panel (CMP)",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["participant_id"] == participant_id
        assert data["record_count"] == 7
        assert {record["Participant_ID"] for record in data["records"]} == {participant_id}
        participant_values[participant_id] = [
            record["Measurement_Value"] for record in data["records"]
        ]

    assert len({tuple(values) for values in participant_values.values()}) == 4

    empty = client.get(
        "/api/nasa/participant-data",
        params={"participant_id": "C999", "biomarker_name": "ALT"},
    )
    assert empty.status_code == 200
    assert empty.json()["participant_id"] == "C999"
    assert empty.json()["records"] == []


def test_scenarios_endpoints(client: TestClient):
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 6

    # Test single scenario fetch
    detail_res = client.get("/api/scenarios/normal_scenario.csv")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["filename"] == "normal_scenario.csv"
    assert detail["is_synthetic"] is True
    assert len(detail["records"]) > 0


def test_wearable_analysis_endpoint(client: TestClient):
    payload = {
        "scenario_name": "normal_scenario.csv",
        "subject_id": "TEST_ASTRONAUT",
    }
    response = client.post("/api/analysis/wearable", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_synthetic"] is True
    assert data["source_type"] == "SYNTHETIC_WEARABLE"
    assert data["processing_status"] == "SUCCESS"
    assert "sensor_trust" in data


def test_nasa_analysis_endpoint(client: TestClient):
    payload = {
        "participant_id": "C001",
    }
    response = client.post("/api/analysis/nasa", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_synthetic"] is False
    assert data["source_type"] == "NASA_LAB"
    assert data["processing_status"] == "SUCCESS"
    assert data["astronaut_id"] == "C001"


def test_alerts_endpoint(client: TestClient):
    response = client.get("/api/alerts?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_history_endpoint(client: TestClient):
    response = client.get("/api/history?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_latest_analysis_endpoint(client: TestClient):
    response = client.get("/api/analysis/latest")
    assert response.status_code == 200
