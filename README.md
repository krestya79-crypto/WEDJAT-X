# WEDJAT-X — Aerospace Medical Mission Control

> *"Guarding Life Beyond Earth, When Every Heartbeat Matters."*

---

## 1. System Overview

**WEDJAT-X** is an autonomous, mission-grade aerospace medical monitoring and decision-support web application designed for long-duration human spaceflight (NASA Space Apps Challenge). 

It bridges retrospective **NASA OSD-575** laboratory venipuncture assays (Inspiration4 commercial crew, N=4) and continuous **synthetic physiological telemetry streams**, powering flight surgeons with explainable biomedical intelligence, robust dispersion analysis, and sensor trust quantification.

---

## 2. Core Architecture & Technology Stack

```
                              ┌──────────────────────────────────┐
                              │  WEDJAT-X MISSION CONTROL WEB    │
                              │  React 18 · TypeScript · Vite    │
                              │  Three.js / React Three Fiber    │
                              │  Tailwind CSS · Framer Motion    │
                              └────────────────┬─────────────────┘
                                               │
                                     HTTP / JSON REST API
                                               │
                              ┌────────────────▼─────────────────┐
                              │     FASTAPI ADAPTER GATEWAY      │
                              │       (/api/system, /analysis)   │
                              └────────────────┬─────────────────┘
                                               │
                       ┌───────────────────────┴───────────────────────┐
                       │                                               │
           ┌───────────▼───────────┐                       ┌───────────▼───────────┐
           │      PIPELINE A       │                       │      PIPELINE B       │
           │  NASA OSD-575 LAB     │                       │  SYNTHETIC WEARABLE   │
           │  • Discrete Assays    │                       │  • Simulated HR/SpO2  │
           │  • 4 Crew Members     │                       │  • Sensor Trust Engine│
           │  • 7 Milestones       │                       │  • Motion Filter (g)  │
           │  • Robust MAD / Z     │                       │  • Hampel Spikes      │
           └───────────┬───────────┘                       └───────────┬───────────┘
                       │                                               │
                       └───────────────────────┬───────────────────────┘
                                               │
                              ┌────────────────▼─────────────────┐
                              │    OFFLINE SQLITE PERSISTENCE    │
                              │          (wedjatx.sqlite3)       │
                              └──────────────────────────────────┘
```

### Frontend Architecture
- **Framework**: React 18 with TypeScript & Vite
- **3D Engine**: Three.js, `@react-three/fiber`, `@react-three/drei`
- **Styling**: Tailwind CSS with custom deep space palette, glassmorphism, HUD brackets, and animated laser scanning lines
- **Icons**: Lucide React
- **Telemetry Visuals**: Precision SVG time-series charts preserving missing-data gaps truthfully

### Backend Architecture
- **REST Adapter**: FastAPI 0.135+, Uvicorn, Pydantic v2
- **Data Pipelines**: Independent analytical pipelines for NASA Laboratory assays and Synthetic Wearables
- **AI / Intelligence Engines**:
  - `BaselineEngine`: Personal preflight baseline median and MAD ($1.4826 \times \text{MAD}$)
  - `AnomalyDetector`: Robust Z-score evaluation, single and multi-threshold modes
  - `SensorTrustEngine`: 7-dimensional signal quality scoring and Hampel filter outlier rejection
  - `LongitudinalTrajectoryEngine`: Directional trend classification across 7 mission milestones
  - `IntelligentAlertEngine`: Explainable triage lifecycle (NORMAL, REVIEW, ATTENTION, INSUFFICIENT_DATA)
- **Offline Persistence**: SQLite (`wedjatx.sqlite3`) with gzip JSON payload compression

---

## 3. Strict Scientific Guardrails

1. **NASA OSD-575 Discrete Laboratory Evidence**:
   - Represents discrete venipuncture assays across four Inspiration4 astronauts (C001, C002, C003, C004) across seven mission milestones (`L-92`, `L-44`, `L-3`, `R+1`, `R+45`, `R+82`, `R+194`).
   - Must never be confused with live continuous wearable signals.
   - Clinical or population-level generalizations are prohibited.

2. **Synthetic Wearable Streams**:
   - Explicitly marked with high-visibility `SYNTHETIC SIMULATION` banners.
   - Enforces `is_synthetic = True` provenance tag on every record.

3. **Missing Value Integrity**:
   - Missing readings are rendered as gaps; they are never interpolated as false valid numbers.
   - Processing failures never default to `NORMAL`.

4. **Non-Clinical Research Decision Support**:
   - WEDJAT-X is an exploratory prototype. It does **NOT** provide autonomous medical diagnosis, disease predictions, or prescriptions.
   - Authorized flight surgeons maintain authoritative decision authority.

---

## 4. Quick Start (Local Full-Stack)

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm

### One-Command Launch (Unified Full-Stack)
```powershell
python run_fullstack.py
```
This automatically compiles the React frontend if needed, starts the FastAPI service, and mounts the mission control application at `http://127.0.0.1:8000`.

---

## 5. Development Mode (Hot Reload)

### Terminal 1: Backend API
```powershell
uvicorn api.main:app --reload --port 8000
```
- API Endpoint: `http://127.0.0.1:8000/api`
- Swagger Documentation: `http://127.0.0.1:8000/docs`

### Terminal 2: React Vite Frontend
```powershell
cd frontend
npm install
npm run dev
```
- Frontend Dev Server: `http://localhost:3000` (automatically proxies `/api` to port 8000)

---

## 6. Production Deployment

### Frontend Deployment (Vercel)
The project is configured for Vercel with `vercel.json`:
1. Connect the repository to Vercel.
2. Set Environment Variable:
   - `VITE_API_BASE_URL`: URL of your deployed backend (e.g. `https://wedjat-x-api.onrender.com`).
3. Deploy! Vercel runs `cd frontend && npm install && npm run build` and serves `frontend/dist`.

### Backend Deployment (Render / Railway / Docker)
The repository includes `render.yaml` and a production `Dockerfile`:
1. Create a Web Service on Render linked to this repository.
2. Select runtime: **Python 3** (or Docker).
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
5. Health Check Path: `/api/health`

---

## 7. Verification & Test Suite

All 166 core tests and 12 API integration tests pass with 0 failures:

```powershell
# Run all tests (178 passing tests)
pytest -v

# Run API adapter tests
pytest tests/test_api.py -v
```

---

## 8. API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service health heartbeat and backend version |
| `GET` | `/api/system/status` | Operational status and engine availability |
| `GET` | `/api/nasa/participants` | Inspiration4 crew catalog (C001..C004) |
| `GET` | `/api/nasa/biomarkers` | Biomarkers catalog grouped by assay panel |
| `GET` | `/api/nasa/participant-data` | Discrete assay observations & baseline calculation |
| `GET` | `/api/scenarios` | Synthetic sensor scenario catalog |
| `GET` | `/api/scenarios/{name}` | Time-series data points for synthetic scenario |
| `POST` | `/api/analysis/nasa` | Execute NASA OSD-575 discrete biomarker pipeline |
| `POST` | `/api/analysis/wearable` | Execute synthetic wearable physiological analysis |
| `GET` | `/api/alerts` | Filtered list of explainable operational alerts |
| `GET` | `/api/history` | Chronological audit history from SQLite persistence |
| `GET` | `/api/analysis/latest` | Most recent analytical result payload |

---

*WEDJAT-X · NASA Space Apps Challenge · Guarding Life Beyond Earth.*
