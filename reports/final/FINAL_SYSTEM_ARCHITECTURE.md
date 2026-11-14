# WEDJAT-X Final Backend Architecture

## Runtime

`WEDJATXSystem` in `application/orchestrator.py` is the public gateway. It validates source type and provenance, dispatches to one isolated pipeline, standardizes results, and stores completed analyses using the stdlib SQLite implementation in `application/storage.py`.

## Isolated data paths

- **NASA_LAB:** audited OSD-575 discrete biomarker rows → input validation → participant baseline → robust anomaly evidence → exploratory Bayesian evidence → longitudinal trajectory → scientific interpretation → explainable alert aggregation.
- **SYNTHETIC_WEARABLE:** explicitly synthetic timestamped sensor rows → per-sensor trust and feature extraction → statistical and Bayesian stream evidence → secondary Isolation Forest context → optional accelerometer motion cross-check → alert aggregation.

The pipelines do not feed data into each other. Wearable results are synthetic by definition and carry `is_synthetic=true`. NASA laboratory data is never represented as continuous telemetry. The result schema includes a request ID, timestamp, source and provenance, status, evidence summaries, warnings/errors, and audit metadata; serialization converts NumPy/pandas values and non-finite values safely to JSON.

## Local persistence and frontend

SQLite initializes at `<base_dir>/wedjatx.sqlite3`; tables hold processing sessions, alert records, and sensor-trust summaries. JSON payloads are gzip-compressed in SQLite and decompressed transparently on retrieval. Retrieval is parameterized and remains offline. Streamlit should call `application.service` for a shared default instance, or instantiate `WEDJATXSystem(base_dir=...)` for an isolated data directory.

## Scientific and operational limits

OSD-575 reflects discrete lab assays for four Inspiration4 participants. It does not support population-level or clinical generalization. Synthetic sensor streams are algorithm test signals, not observed astronaut telemetry. Outputs are research decision support, not diagnosis, treatment, or autonomous medical decisions; authorized human medical review remains the final authority.
