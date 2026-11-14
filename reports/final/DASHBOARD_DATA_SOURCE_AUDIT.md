# WEDJAT-X Dashboard Data Source Audit

Audit date: 2026-11-14

## Findings

| Area | Result | Source and behavior |
|---|---|---|
| NASA participants and counts | PASS | Loaded from the OSD-575 master CSV through `/api/nasa/participants`; no fabricated per-person assay totals or mission roles are supplied. |
| NASA biomarkers, baselines, and observations | PASS | Read from the master CSV and backend baseline engine. Missing assay values serialize as JSON `null`; the UI renders missing observations as missing. |
| Synthetic scenarios and telemetry charts | PASS | Scenario catalog and samples come from CSV files marked synthetic. Chart ranges are calculated from present samples; missing samples break the plotted line. |
| Analysis history total | PASS | Uses persisted SQLite session count from `/api/metrics`; recent list uses compact server summaries. |
| Alert count and records | PASS | Active count uses the latest persisted analysis; historical active alert records have a separate metric. Alert details remain retrievable and filterable by source and state. |
| Sensor trust | PASS | Uses the latest persisted synthetic trust record, including sensor-level scores, quality dimensions, source timestamp, and request ID. Missing trust shows unavailable. |
| System status and engine count | PASS | Status and initialized engine map are returned by the orchestrator. Missing API state renders unavailable, not READY. |
| Polling and stale data | PASS | Status, participants, alerts, latest result, scenarios, history, and metrics refresh every five seconds. Refreshes do not overlap; polling requests are aborted on unmount. Failed refreshes retain the last successful values and show stale/error state. |
| Build and dependencies | PASS | `npm run build` completes with the installed project dependencies; Python API modules compile. No dependency was added for the adapter. |
| SQLite Git exclusion | PASS | `.gitignore` excludes `*.db`, `*.sqlite`, and `*.sqlite3`. Frontend dependencies and build output are also excluded. |
| Machine-specific source paths | PASS | No absolute user-specific path remains in application/frontend source; the legacy external download path is now configurable with `WEDJAT_EXTERNAL_DOWNLOAD_DIR`. |

## Source classifications

- **Static:** Layout, labels, research disclaimer, and the known OSD-575 milestone labels.
- **Dynamic:** NASA observations, synthetic scenario files, processing outputs, persisted alert records, sensor trust, participant counts, and engine state.
- **Real-time polling:** Backend status and persisted dashboard data refresh on a five-second interval. The header shows the last successful update and reports stale or unavailable data on failures.
- **Not implemented:** Continuous acquisition from physical wearable hardware or live NASA telemetry. Synthetic data is selected from stored test scenarios and analyzed on request; the telemetry view is scenario playback rather than a continuously ingesting device stream.

## Remaining limitation

Continuous sensor ingestion and push updates (such as a WebSocket stream) are not implemented. The dashboard is integrated with the available persisted backend and stored synthetic scenarios; it should not be presented as receiving live spacecraft or wearable hardware measurements.

## Finding classification

- **PASS:** The implemented polling dashboard is connected to backend data and persisted results.
- **WARNING:** Continuous physical device or spacecraft data ingestion is not implemented. Archived visualization logs contain absolute paths from the development machine; application source no longer hardcodes those paths.
- **CRITICAL:** None found for the current local dashboard startup and analysis workflows.
