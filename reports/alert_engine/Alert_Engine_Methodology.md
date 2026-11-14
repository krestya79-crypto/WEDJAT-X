# WEDJAT-X Phase 6: Explainable AI & Intelligent Medical Alert Engine Methodology
**NASA Space Apps Challenge — Astronaut Health Monitoring Prototype**

---

## 1. Executive Summary & Operational Role
Phase 6 establishes the **Intelligent Medical Alert Engine**, uniting all prior analytical components—Personalized Baselines, Robust Z-scores, Bayesian Student-t tail probabilities, Isolation Forest feature context, Sensor Trust scoring, Motion Cross-Correlation, and Longitudinal Recovery Trajectories—into an explainable decision-support system.

> [!IMPORTANT]
> **Mandatory Scientific & Ethical Disclaimer**:
> WEDJAT-X is an exploratory computational decision-support prototype. It is **NOT** a certified diagnostic medical device. It **DOES NOT** generate clinical diagnoses, disease predictions, pathology classifications, or treatment prescriptions. All alert states (`NORMAL`, `REVIEW`, `ATTENTION`, `INSUFFICIENT_DATA`) represent operational workflow recommendations for certified flight surgeons and ground medical consoles.

---

## 2. Dual-Track Data Pathways

To ensure absolute scientific integrity, the engine enforces strict architectural separation between data sources:

```
                    ┌──────────────────────────────────────────────┐
                    │   WEDJAT-X Phase 6 Intelligent Alert Engine  │
                    └──────────────────────┬───────────────────────┘
                                           │
                   ┌───────────────────────┴───────────────────────┐
                   │                                               │
                   ▼                                               ▼
       [PATH A: Continuous Wearable]                 [PATH B: Discrete NASA Laboratory]
       - High-Frequency Telemetry (1 Hz)             - Discrete Benchtop Lab Assays (pg/mL, NPQ)
       - Sensors: HR, SpO2, Accelerometer            - N = 4 Astronauts (Inspiration4)
       - Sensor Trust Engine (Missing, Drift)        - Preflight Baselines (L-92, L-44, L-3)
       - Hampel Filter & Accelerometer Overlap       - Postflight Trajectories (R+1 through R+194)
       - Isolation Forest Secondary Context          - Longitudinal Homeostatic Convergence
       - Tagged: is_synthetic = True                 - Tagged: is_synthetic = False
```

---

## 3. Multi-Engine Decision Fusion Rules

The fusion framework combines evidence hierarchically rather than averaging scores:

| Analytical Engine | Decision Role | Operational Constraint |
| :--- | :--- | :--- |
| **Robust Statistical Baseline** | Primary Deviation Detector | Evaluates personalized preflight median and MAD ($|Z| \ge 3.0$ significant, $|Z| \ge 2.0$ moderate). |
| **Bayesian Student-t** | Probabilistic Uncertainty | Accounts for parameter uncertainty in small sample sizes ($p < 0.01$ strong outlier, $p < 0.05$ moderate). |
| **Isolation Forest** | Secondary Multivariate Pattern Context | **MUST NOT independently trigger operational alerts**. Detects subtle multi-feature drift. |
| **Sensor Trust Engine** | Signal Quality & Integrity Gate | Quality score $< 50.0$ forces state to `INSUFFICIENT_DATA`; Score $50.0-74.9$ downgrades `ATTENTION` to `REVIEW`. |
| **Motion Cross-Check** | Artifact Rejection | Optical spikes coinciding with acceleration jolts ($|a - 1g| > 0.4g$) are classified as motion artifacts. |
| **Trajectory Engine** | Temporal Context | Identifies whether postflight readings are actively approaching baseline (`APPROACHING_BASELINE`). |

---

## 4. Operational Alert Classifications

1. **`NORMAL`** (Priority: `NOMINAL`):
   - All engines indicate readings within expected personalized baseline dispersion. Workflow: `NO_ADDITIONAL_REVIEW_FLAGGED`.
2. **`REVIEW`** (Priority: `LOW` or `MEDIUM`):
   - Single-engine significant deviation, or moderate deviation supported by Bayesian likelihood, or significant deviation accompanied by motion artifact overlap. Workflow: `REVIEW_MEASUREMENT`, `VERIFY_SENSOR_SIGNAL`.
3. **`ATTENTION`** (Priority: `HIGH`):
   - Concordant multi-engine departure (Statistical $|Z| \ge 3.0$ **AND** Bayesian $p < 0.01$), with Sensor Trust $\ge 75.0$ and **NO** motion artifact overlap. Workflow: `REQUEST_MEDICAL_REVIEW`, `REVIEW_MEASUREMENT`.
4. **`INSUFFICIENT_DATA`** (Priority: `INFO`):
   - Measurement missing / unrecorded, or Sensor Trust $< 50.0$ (`UNRELIABLE`). Workflow: `VERIFY_SENSOR_SIGNAL`, `REPEAT_MEASUREMENT_IF_OPERATIONALLY_APPROPRIATE`.

---

## 5. Temporal Alert Lifecycle & Deduplication

- **Deduplication Key**: `subject_id::measurement_name`. Repeated observations update ongoing events rather than generating duplicate alerts.
- **States**:
  - `NEW`: First detection of an elevated state.
  - `ACTIVE`: Maintained for 1–2 consecutive observations.
  - `PERSISTENT`: Maintained for $\ge 3$ consecutive observations or duration $> 10$ seconds.
  - `RESOLVED`: Returned to nominal range.
  - `INSUFFICIENT_EVIDENCE`: Telemetry interrupted or lost during active alert.

---

## 6. Deliverables & Figures Inventory
- **Excel Workbooks**:
  - `reports/alert_engine/Intelligent_Alert_Report.xlsx`
  - `reports/alert_engine/Alert_Evidence_Audit.xlsx`
  - `reports/alert_engine/Ground_Medical_Alert_Summaries.xlsx`
  - `reports/alert_engine/Astronaut_Alert_Summaries.xlsx`
- **High-Resolution Figures**:
  - `reports/figures/alert_engine/alert_timeline.png`
  - `reports/figures/alert_engine/alert_state_distribution.png`
  - `reports/figures/alert_engine/model_agreement_matrix.png`
  - `reports/figures/alert_engine/sensor_reliability_vs_alerts.png`
  - `reports/figures/alert_engine/example_explainable_alert.png`
  - `reports/figures/alert_engine/alert_persistence_analysis.png`
