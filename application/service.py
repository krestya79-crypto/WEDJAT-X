"""Stable functions intended for Streamlit or another thin frontend."""
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

from application.orchestrator import WEDJATXSystem

_SYSTEM: Optional[WEDJATXSystem] = None
_SYSTEM_LOCK = Lock()


def _system() -> WEDJATXSystem:
    global _SYSTEM
    if _SYSTEM is None:
        with _SYSTEM_LOCK:
            if _SYSTEM is None:
                _SYSTEM = WEDJATXSystem(base_dir=Path.cwd())
    return _SYSTEM


def analyze_nasa_sample(data: Any, metadata: Optional[Dict[str, Any]] = None):
    return _system().process(data, "NASA_LAB", metadata=metadata)


def analyze_wearable_stream(data: Any, metadata: Optional[Dict[str, Any]] = None):
    return _system().process(data, "SYNTHETIC_WEARABLE", metadata=metadata, is_synthetic=True)


def get_system_status():
    status = _system().get_system_status()
    return status.to_dict() if hasattr(status, "to_dict") else status


def get_recent_alerts(limit: int = 20):
    return _system().get_recent_alerts(limit)


def get_alert_detail(alert_id: str):
    return _system().storage.alert_detail(alert_id)


def get_analysis_history(limit: int = 50):
    return _system().get_analysis_history(limit)


def get_latest_analysis(source_type: Optional[str] = None):
    system = _system()
    return system.storage.latest(source_type=source_type)


def get_analysis_count() -> int:
    return _system().storage.analysis_count()


def get_alert_count(active_only: bool = False) -> int:
    return _system().storage.alert_count(active_only=active_only)


def get_latest_sensor_trust():
    return _system().storage.latest_sensor_trust()
