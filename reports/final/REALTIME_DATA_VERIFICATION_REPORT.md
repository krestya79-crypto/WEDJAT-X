# WEDJAT-X Real-Time Data Verification Report

Verification date: 2026-11-14

## Result

**Frontend/backend integration: PASS for the implemented polling dashboard.** The app does not provide continuous hardware telemetry ingestion; see the explicit limitation below.

## Checks and evidence

| Check | Result | Evidence |
|---|---|---|
| Frontend production build | PASS | `npm run build` completed (`tsc` and Vite production build). |
| Complete Python suite | PASS | `pytest -q`: **181 passed, 0 failed, 0 skipped**. One upstream Starlette/httpx deprecation warning was reported. |
| API-focused tests | PASS | `pytest -q tests/test_api.py`: **13 tests** included in the complete passing suite; focused run also completed. |
| Documented clean startup | PASS | `python run_fullstack.py` started FastAPI at `http://127.0.0.1:8000`; Vite dev server started at `http://127.0.0.1:3000` and proxied API requests successfully. Both root page and health/participants/scenarios/metrics requests returned HTTP 200. |
| NASA pipeline | PASS | Public `POST /api/analysis/nasa` returned `SUCCESS`, `source_type=NASA_LAB`, `is_synthetic=false`. |
| Synthetic wearable pipeline | PASS | Public `POST /api/analysis/wearable` returned `SUCCESS`, `source_type=SYNTHETIC_WEARABLE`, `is_synthetic=true`; sensor-level trust was present. |
| Analysis counter | PASS | A valid public wearable analysis increased persisted `analysis_count` by exactly one (174 to 175 in the final live check). |
| Quality issue and trust | PASS | `sensor_disconnect_scenario.csv` produced a successful synthetic analysis with `is_synthetic=true`; all three sensor scores decreased into `MODERATE_RELIABILITY` (77.0, 78.2, and 78.4). |
| Alerts and history after restart | PASS | After stopping and restarting the API process, `/api/history`, `/api/alerts`, and `/api/metrics` returned persisted session/alert/trust data from SQLite. The latest trust record remained marked synthetic. |
| Alert state accuracy | PASS | The latest-run active count excludes NORMAL and INSUFFICIENT_DATA records; a regression test covers the all-normal case. Historical active records are reported separately. |
| Missing values and payload size | PASS | Existing missing-data tests pass. Dashboard history polling requests compact summaries with measurement counts; full detail remains available from the session history endpoint. |
| Git and machine paths | PASS | SQLite files, `frontend/node_modules`, and `frontend/dist` are ignored. The dashboard adapter resolves project data paths relative to the module, not a developer-specific absolute path. |

## Feature status

- **Static:** Mission-control presentation and labels; not presented as measurements.
- **Dynamic:** NASA data, stored synthetic scenarios, analysis outcomes, alert data, sensor trust, persisted session totals, and engine status.
- **Real-time:** Five-second polling of backend state with overlap protection, abort on unmount, last-success timestamps, and stale/error reporting.
- **Not implemented:** Streaming data capture from a physical wearable or NASA live feed. Synthetic telemetry is selected from stored scenario CSVs and analyzed when requested.

## Remaining blockers

No blocker prevents running the integrated dashboard against the current backend. Continuous live-device/live-spacecraft telemetry ingestion remains unimplemented and must be treated as a separate feature before describing the product as a live hardware monitoring system.

## Finding classification

- **PASS:** Local frontend/backend integration and the implemented polling behavior.
- **WARNING:** Continuous physical device/spacecraft ingestion is not implemented. Archived visualization logs retain absolute development-machine paths; runtime source uses project-relative paths or `WEDJAT_EXTERNAL_DOWNLOAD_DIR`.
- **CRITICAL:** None found for the verified local startup and analysis flows.

## Final test count

**181 passed, 0 failed, 0 skipped**, plus one upstream Starlette/httpx deprecation warning.
