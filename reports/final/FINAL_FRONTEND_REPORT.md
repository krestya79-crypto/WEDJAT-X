# WEDJAT-X Frontend Delivery Report

**Status:** Implemented and verified  
**Launch:** `streamlit run streamlit_app.py` from the repository root

## Delivered

- Added `streamlit_app.py` and the `frontend/` package with reusable sidebar, header, astronaut illustration, metrics, telemetry, alert, biomarker, sensor-trust, and trajectory components.
- Added an offline CSS theme and locally stored SVG astronaut artwork. No external fonts, image URLs, React, or server API are used.
- Added eight navigable views: Mission Overview, Astronaut Monitoring, Analysis Console, Live Telemetry, NASA Biomarkers, Alert Center, Sensor Trust, and Recovery Trajectory.
- Added Plotly charts for actual OSD-575 milestone measurements and local synthetic sensor scenarios. Missing values remain gaps or display as unavailable.
- Added deliberate analysis actions using `application.service` for both NASA and synthetic data. Results are held in session state and saved by the backend; rerendering the app does not rerun analysis.
- Added filters for actual participant IDs, biomarker, source, alert state, and local synthetic scenario. CSV uploads are only routed as synthetic wearable input and remain subject to backend provenance validation.
- Updated README install dependencies and documented the Streamlit launch command.

## Scientific/source handling

NASA pages load the existing audited master CSV and label OSD-575 as discrete lab assays. Participant choices and biomarkers are derived from that dataset. No NASA measurements are fabricated. Wearable pages are marked **SYNTHETIC** throughout and use repository scenario CSVs or user-selected CSV input. The astronaut panel is an illustration and explicitly does not depict a connected live astronaut or live medical telemetry. Failed requests surface errors and do not produce a normal-state claim.

## Verification

- `python -m compileall -q frontend streamlit_app.py`: passed.
- Streamlit `AppTest`: all eight navigation views rendered without exceptions; the NASA and synthetic analysis buttons each completed using the backend services.
- Server command: `python -m streamlit run streamlit_app.py --server.headless true --server.port 8766 --browser.gatherUsageStats false`; HTTP app root and `/_stcore/health` both returned **200**, health body `ok`.
- Streamlit and Plotly were available in the execution environment. The normal launch command is `streamlit run streamlit_app.py`.

## Known limits

- The astronaut artwork is a responsive SVG illustration, not a 3D model or a real-time person-specific body visualization.
- Heart rate, SpO₂, and accelerometer values appear only when present in a synthetic analysis result. NASA laboratory records never populate wearable vitals; absent readings are labeled unavailable.
- The application has no live sensor transport. “Live Telemetry” visualizes selected local synthetic samples and stored analysis evidence.
- The page uses the standard Streamlit browser interface and adapts its layout for smaller screens; no separate frontend server is introduced.
