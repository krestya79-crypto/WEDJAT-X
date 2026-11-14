# WEDJAT-X Phase 5: Machine Learning Model Evaluation & Validation Methodology
**NASA Space Apps Challenge — Astronaut Health Monitoring Prototype**

---

## 1. Executive Summary & Scientific Purpose
Phase 5 evaluated whether Machine Learning (ML) methods—specifically multidimensional **Isolation Forest** and a probabilistic **Bayesian Student-t Posterior Predictive Detector**—provide measurable improvements over the existing WEDJAT-X **Robust Statistical Baseline** (Median & MAD Robust Z-score).

> [!IMPORTANT]
> **Mandatory Scientific & Ethical Notice**:
> This software is an exploratory research prototype for computational evaluation. It is **NOT** a certified medical device and **DOES NOT** provide clinical diagnoses, disease risk predictions, or therapy recommendations.
> Synthetic wearable streams are strictly simulated test patterns (`is_synthetic = True`) and are never combined with benchtop NASA OSD-575 laboratory assays.

---

## 2. Phase 4 Quality Threshold Audit
During the Phase 4 audit, a transcription discrepancy was identified between the summary markdown text and the code:
- **Authoritative Implementation** in `intelligence/sensor_trust.py` (lines 337–344):
  - `HIGH_RELIABILITY`: Score >= 90.0
  - `MODERATE_RELIABILITY`: Score 75.0 to 89.9
  - `LOW_RELIABILITY`: Score 50.0 to 74.9
  - `UNRELIABLE`: Score < 50.0
  - `INSUFFICIENT_DATA`: Sample count < 3 and expected < 5.
- **Finding**: The Phase 4 summary report prose mentioned 85 / 70 / 50, whereas the code authoritatively enforces the specified **90.0 / 75.0 / 50.0** thresholds. The code implementation is authoritative and has been preserved without silent modification.
- **Problematic Interpretation Wording**: An example statement in the astronaut briefing noted *"No changes to your daily physical activity or rest schedule are recommended."* This phrasing verges on clinical operational prescription/reassurance. In Phase 5, all narrative explanations strictly adhere to operational communication protocols (e.g. `REVIEW_MEASUREMENT`, `VERIFY_SENSOR_SIGNAL`) without offering medical reassurance or activity prescriptions.

---

## 3. Two-Track Experimental Architecture

```
                  ┌──────────────────────────────────────────────┐
                  │    WEDJAT-X Phase 5 Model Evaluation Pipeline │
                  └──────────────────────┬───────────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 │                                               │
                 ▼                                               ▼
     [TRACK A: Synthetic Wearable]                   [TRACK B: NASA OSD-575 Assays]
     - Sensors: HR, SpO2, Accelerometer              - Discrete Benchtop Lab Assays
     - Scenarios: Normal, Motion, Drift, etc.        - N = 4 Astronauts (Inspiration4)
     - Independent Run-Level Train/Test Splitting     - Participant-Aware / Pre vs Post
     - Evaluated with Known Ground Truth             - Exploratory Consistency Evaluation
```

---

## 4. Evaluated Models

### Model 1: Robust Statistical Baseline (Reference)
- **Formula**: $Z = \frac{x - \text{median}_{\text{preflight}}}{1.4826 \times \text{MAD}_{\text{preflight}}}$
- **Threshold**: Standard $|Z| \ge 3.0$ (Significant Elevation/Suppression).
- **Properties**: Non-parametric, zero false alarms in clean nominal data, execution time < 0.1 ms.

### Model 2: Multidimensional Isolation Forest
- **Architecture**: 100 Isolation Trees with causal temporal features (past median, past MAD, first-order difference, local Z-score, sampling deviation).
- **Preprocessing**: RobustScaler fitted strictly on training recording.
- **Contamination**: Configured at $\nu = 0.05$.
- **Properties**: Captures joint multidimensional feature relationships; detects drift effectively.

### Model 3: Bayesian Student-t Anomaly Detector
- **Prior**: Normal-Inverse-Gamma conjugate prior ($\mu_0, \kappa_0, \alpha_0, \beta_0$).
- **Posterior Predictive**: $\tilde{x} \sim t_{2\alpha_n}\left(\mu_n, \frac{\beta_n(\kappa_n + 1)}{\alpha_n \kappa_n}\right)$
- **Degrees of Freedom**: $\nu = 2\alpha_n$. Heavier tails for small sample sizes naturally suppress false alarms.
- **Anomaly Decision**: Two-tailed $p$-value < 0.01.

---

## 5. Answers to Core Scientific Research Questions

| Question | Scientific Finding & Evidence |
| :--- | :--- |
| **1. Does ML improve detection?** | **Marginal Improvement in Specific Regimes**. Isolation Forest achieved high recall on complex drift patterns, while the Statistical Baseline achieved near-instantaneous, zero-false-alarm detection on transient motion artifacts. |
| **2. Does ML increase false alarms?** | **YES for Isolation Forest**. Due to the fixed contamination hyperparameter (0.05), Isolation Forest generated a ~5% false positive rate even on completely clean, nominal baseline streams. The Statistical Baseline and Bayesian Detector achieved 0.0% FPR on clean nominal streams. |
| **3. Does ML detect motion artifacts more effectively?** | **Equivalent or Slightly Lower**. The Statistical Baseline detected 100% of large transient motion spikes because spike amplitude substantially exceeded preflight MAD. Isolation Forest detected the artifacts but introduced adjacent false positives. |
| **4. Does ML identify drift?** | **YES**. Isolation Forest identified gradual downward/upward drift earlier than single-point statistical thresholding because rolling window variance and difference features accumulated evidence over time. |
| **5. Is performance stable across independent seeds?** | **YES**. Across 5 independent random seeds, the Statistical Baseline had zero F1 variance ($\text{Std} = 0.00$), Bayesian detector had $\text{Std} = 0.01$, and Isolation Forest had $\text{Std} = 0.03$. |
| **6. Does improvement justify ML complexity?** | **NO for General Alerting; TRADEOFF_OBSERVED**. The added computational overhead ($\sim 15\times$ execution time) and false alarm burden of Isolation Forest make it unsuitable as a primary alarm trigger. It is recommended only as a secondary offline diagnostic analyzer. |

---

## 6. Model Selection Verdict

- **Robust Statistical Baseline**: `SELECTION_IMPROVEMENT` (Confirmed Gold Standard for Operational Alerting).
- **Bayesian Student-t Detector**: `SELECTION_IMPROVEMENT` (Recommended for Small-Sample Biomarker Evaluation).
- **Isolation Forest**: `TRADEOFF_OBSERVED` (Useful for drift detection; prohibited from standalone alarm triggering due to baseline false alarm rate).

---

## 7. Deliverables & Artifact Inventory
- **Excel Reports**:
  - `reports/model_evaluation/Model_Performance_Comparison.xlsx`
  - `reports/model_evaluation/Synthetic_Experiment_Results.xlsx`
  - `reports/model_evaluation/NASA_Exploratory_Evaluation.xlsx`
- **High-Resolution Figures**:
  - `reports/figures/model_evaluation/model_performance_comparison.png`
  - `reports/figures/model_evaluation/precision_recall_comparison.png`
  - `reports/figures/model_evaluation/confusion_matrices.png`
  - `reports/figures/model_evaluation/false_positive_rate_comparison.png`
  - `reports/figures/model_evaluation/scenario_specific_performance.png`
  - `reports/figures/model_evaluation/detection_timeline_examples.png`
  - `reports/figures/model_evaluation/bayesian_predictive_anomaly.png`
  - `reports/figures/model_evaluation/feature_distribution_comparison.png`
