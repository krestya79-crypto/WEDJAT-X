"""Offline demonstration of isolated NASA laboratory and synthetic pipelines."""
import json
from pathlib import Path

from application.orchestrator import WEDJATXSystem
from intelligence.synthetic_sensors import SyntheticSensorConfig, SyntheticSensorGenerator


def compact_alert(alert):
    """Keep console output readable while retaining representative evidence."""
    summary = dict(alert or {})
    active = summary.pop("active_alerts", [])
    summary["active_alert_examples"] = active[:2]
    summary["active_alerts_omitted_from_console"] = max(0, len(active) - 2)
    return summary


def main() -> int:
    root = Path(__file__).resolve().parent
    system = WEDJATXSystem(base_dir=root)
    nasa_path = root / "cleaned_data" / "WEDJAT_X_Master_Biomarker_Dataset.csv"
    if not nasa_path.exists():
        print(f"NASA_LAB demo unavailable: audited dataset not found at {nasa_path}")
        return 2

    print("=== NASA OSD-575 discrete laboratory data (actual dataset) ===")
    nasa = system.process(nasa_path, "NASA_LAB", metadata={"provenance": "NASA OSD-575 audited master dataset"})
    print(json.dumps({"source_type": nasa.source_type, "is_synthetic": nasa.is_synthetic,
                      "processing_status": nasa.processing_status, "astronaut_id": nasa.astronaut_id,
                      "data_summary": nasa.data_summary, "alert": compact_alert(nasa.alert),
                      "errors": nasa.errors, "warnings": nasa.warnings}, indent=2, allow_nan=False))

    print("=== SYNTHETIC_WEARABLE simulated telemetry (explicitly synthetic) ===")
    generator = SyntheticSensorGenerator(SyntheticSensorConfig(duration_seconds=30, random_seed=2026))
    stream = generator.generate_heart_rate()
    wearable = system.process(stream, "SYNTHETIC_WEARABLE", subject_id="DEMO_SYNTHETIC",
                              is_synthetic=True, metadata={"provenance": "local synthetic demo generation"})
    print(json.dumps({"source_type": wearable.source_type, "is_synthetic": wearable.is_synthetic,
                      "processing_status": wearable.processing_status, "sensor_trust": wearable.sensor_trust,
                      "alert": compact_alert(wearable.alert), "errors": wearable.errors,
                      "warnings": wearable.warnings}, indent=2, allow_nan=False))
    print(f"Offline SQLite history: {len(system.get_analysis_history())} saved analyses")
    return 0 if not nasa.errors and not wearable.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
