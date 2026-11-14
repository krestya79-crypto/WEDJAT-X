# Final Backend Usage

## Launch

From the repository root, use `python run_demo.py` to execute both isolated pipelines and print provenance, status, alerts, and trust data. The demo expects `cleaned_data/WEDJAT_X_Master_Biomarker_Dataset.csv` and exits clearly if it is absent.

## Streamlit calls

```python
from application.service import (
    analyze_nasa_sample, analyze_wearable_stream,
    get_system_status, get_recent_alerts, get_analysis_history,
    get_latest_analysis,
)

nasa_result = analyze_nasa_sample(
    "cleaned_data/WEDJAT_X_Master_Biomarker_Dataset.csv",
    metadata={"astronaut_id": "C001"},
)
wearable_result = analyze_wearable_stream(synthetic_dataframe)
payload = nasa_result.to_dict()  # JSON-ready dict
```

The wearable service function forces `is_synthetic=True`. Use `WEDJATXSystem(base_dir=project_path)` directly to control the SQLite location. The service interface uses the current working directory for its default database.

## Result and storage

Results provide `request_id`, `timestamp`, `source_type`, `is_synthetic`, `processing_status`, `data_summary`, `baseline_summary`, `anomaly_evidence`, nullable `sensor_trust` and `trajectory_summary`, `interpretation`, `alert`, `warnings`, `errors`, and `audit_metadata`. Processing states are `SUCCESS`, `PARTIAL_SUCCESS`, `INSUFFICIENT_DATA`, `VALIDATION_ERROR`, and `PROCESSING_ERROR`. Local history/alerts persist in `wedjatx.sqlite3` and are accessed through the service functions.

All execution is offline after Python dependencies and local data are available. NASA laboratory assays remain discrete; synthetic wearable signals are simulations and must not be described as NASA measurements. Human medical review is required.
