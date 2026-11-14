# Dashboard Polling Disappearance — Root Cause and Fix

Date: 2026-11-14

## Root cause

`frontend/src/App.tsx` (the old poll at line 64 and unconditional state replacement at line 85) used the unfiltered `/api/analysis/latest` endpoint and replaced `latestResult` whenever it returned a result. That endpoint selected the most recently persisted analysis across both sources. When a NASA lab analysis was newer, it replaced the synthetic wearable result. The NASA payload had no `heart_rate`/`spo2` sensor measurements and no wearable trust data, so the astronaut panel rendered Pulse Rate and SpO2 as `Unavailable` and reliability as unavailable/null. NASA participant data remained visible because it comes from separate participant/catalog state.

The fix is at `frontend/src/App.tsx:64-99`, `api/routes/analysis.py:94`, `application/service.py:38`, and `application/storage.py:105`.

This was reproduced against the running API: the unfiltered latest response was `NASA_LAB`, `is_synthetic=false`, with biomarker-shaped measurements and no sensor trust. The metrics API still contained a persisted synthetic trust record. Querying `GET /api/analysis/latest?source_type=SYNTHETIC_WEARABLE` returned a synthetic record with heart rate 71.56, SpO2 97.91, and `HIGH_RELIABILITY`.

## Fixes

- `api/routes/analysis.py` accepts `source_type` for latest-analysis requests.
- `application/service.py` and `application/storage.py` select the latest matching source directly in SQLite, so NASA results cannot replace wearable telemetry.
- `frontend/src/App.tsx` polls only the synthetic wearable result for astronaut values and updates that state only for synthetic results. NASA analysis does not overwrite wearable values.
- Polling merges sensor measurements by type, retains previous valid values when a newer response omits a channel or returns an incomplete trust object, and rejects older result timestamps. Poll calls remain single-flight; unmount aborts them.
- Persisted sensor trust is maintained independently of the general latest analysis and only accepts synthetic trust records. Synthetic provenance remains visible with the astronaut telemetry.
- A failed poll leaves displayed data intact and sets the existing connection/stale indicator; reconnecting resumes polling automatically.

## Verification

- Seven API reads over at least 30 seconds returned the same synthetic request and values: heart rate 71.56, SpO2 97.91, reliability `HIGH_RELIABILITY`.
- With the backend stopped, the proxied API request failed as expected while the frontend root remained HTTP 200. After restarting the backend, the synthetic result and values returned automatically.
- `npm run build`: passed.
- `pytest -q tests/test_storage.py tests/test_api.py`: 15 passed, 0 failed.
- API root and frontend root both returned HTTP 200 after recovery.

Browser developer tools were not available in this execution environment, so no browser console was inspected. The backend disconnect/recovery and proxy requests were verified directly; the application retains values and surfaces its connection error through the React polling state.
