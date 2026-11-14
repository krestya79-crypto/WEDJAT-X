# WEDJAT-X Scientific Interpretation & Sensor Trust Methodology

**Offline-First Astronaut Health Monitoring & Decision-Support System**  
*NASA Space Apps Challenge Prototype*

---

## 1. Executive Summary & Biomedical Purpose

The **WEDJAT-X Sensor Trust & Scientific Interpretation Engine** is an evidence-based clinical-data-science system designed for aerospace health monitoring. It addresses a fundamental challenge in aerospace medicine: **bridging raw physiological signals with operational decision-making while maintaining rigorous scientific humility**.

The engine operates on two complementary operational tiers:
1. **Sensor Trust Engine**: Scientifically evaluates wearable sensor telemetry reliability, stream stability, and artifact interference before any diagnostic inference can be contemplated.
2. **Scientific Interpretation Engine**: Translates complex multivariate biomedical findings (baselines, robust Z-scores, longitudinal trajectories, and signal fidelity) into dual-audience decision support:
   - **Ground Medical Team**: Quantitative, evidence-traceable, 7-section briefings for flight surgeons and biomedical engineers.
   - **Astronaut Crew**: Calm, concise, non-alarming, actionable summaries in plain language.

---

## 2. Core Scientific Principles & Separation of Data Sources

### A. The Five-Tier Diagnostic Hierarchy
To prevent cognitive errors and premature clinical closure, WEDJAT-X strictly enforces five epistemological tiers:

1. **MEASUREMENT**: An unadjusted, directly observed benchtop assay concentration or digital sensor reading.
2. **SIGNAL QUALITY ISSUE**: A technical telemetry impediment (e.g. motion artifact, packet loss, optical uncoupling) affecting data reliability.
3. **STATISTICAL DEVIATION**: A mathematical departure from an individualized preflight baseline ($|Z| \ge 3.0$) or reference dispersion.
4. **LONGITUDINAL TREND**: An overarching dynamic trajectory across spaceflight and recovery phases (e.g. `APPROACHING_BASELINE`, `FLUCTUATING`).
5. **CLINICAL SIGNIFICANCE**: A medical judgment requiring human flight surgeon evaluation in the context of crew operational constraints, countermeasure status, and multi-system pathology.

> [!IMPORTANT]
> - A statistical anomaly is **NOT** a medical pathology or disease.
> - A sensor-quality alert is **NOT** a physiological emergency.
> - A mathematical trajectory toward baseline is **NOT** clinical recovery.
> - Missing data is **NOT** a normal measurement.

### B. Absolute Segregation of Real and Synthetic Data
- **NASA OSD-575 Inspiration4 Data**: Represents discrete, laboratory benchtop biochemical assay measurements from venipuncture biospecimens across 7 timepoints ($N=4$ astronauts). It is **not** wearable telemetry.
- **Synthetic Sensor Telemetry**: Software-generated test patterns designed to benchmark real-time signal processing and fault detection. Every synthetic row is explicitly tagged with `is_synthetic = True`.
- **Zero-Merge Policy**: Real laboratory assay records and synthetic sensor streams are **never** combined or presented as concurrent measurements from the same biospecimen.

---

## 3. Sensor Trust Engine: Scoring & Artifact Detection Methodology

The Sensor Trust Engine calculates a composite, bounded reliability score from **0.0 to 100.0** across six orthogonal dimensions of signal integrity:

$$\text{Quality Score} = \sum_{k=1}^{6} w_k \cdot S_k$$

### A. Scoring Weights & Dimensions
| Quality Dimension | Weight ($w_k$) | Measurement Focus | Normalization & Mathematical Penalty |
| :--- | :---: | :--- | :--- |
| **Missing Data** | **25%** | Intermittent packet loss & dropout rate ($R_{missing}$) | $S_{missing} = \max(0, 1 - 2.0 \cdot R_{missing}) \times 100$ |
| **Disconnection** | **25%** | Sensor uncoupling / lead-off rate ($R_{disc}$) | $S_{disc} = \max(0, 1 - 2.5 \cdot R_{disc}) \times 100$ |
| **Noise Metric** | **20%** | High-frequency residual MAD above physiological trend | $S_{noise} = \max(0, 1 - P_{noise}) \times 100$ |
| **Spikes & Artifacts**| **15%** | Hampel filter 3-sigma outliers & motion spikes | $S_{spikes} = \max(0, 1 - 4.0 \cdot R_{spike}) \times 100$ |
| **Timing Continuity** | **10%** | Sampling gaps ($>1.5\Delta t$) and duplicate timestamps | $S_{cont} = \max(0, 1 - 5.0 \cdot R_{gap}) \times 100$ |
| **Signal Drift** | **5%** | Monotonic baseline drift exceeding physical threshold | $S_{drift} = 0.0 \text{ (if drift)} \text{ else } 100.0$ |

### B. Mathematical Formulations

#### 1. Hampel Outlier Detector
For each measurement $x_i$ within sliding window $[i-k, i+k]$:
$$m_i = \text{median}(x_{i-k}, \dots, x_{i+k})$$
$$S_i = 1.4826 \times \text{median}(|x_{i-k} - m_i|, \dots, |x_{i+k} - m_i|)$$
$$\text{Outlier Flag} = |x_i - m_i| > 3.0 \times S_i$$
Measurements flagged by Hampel filtering are recorded in quality logs but **never deleted** from the telemetry stream.

#### 2. Robust Residual Noise Assessment
To prevent mistaking true physiological rhythms (respiratory sinus arrhythmia ~0.25 Hz, Traube-Hering vasomotor waves ~0.1 Hz) for noise:
$$r(t) = x(t) - \text{rolling\_median}_5(x(t))$$
$$\text{Noise Metric} = \text{MAD}(r(t)) = \text{median}(|r(t) - \text{median}(r(t))|)$$

#### 3. Motion Artifact Cross-Check
Where synchronized 3-axis accelerometer data is available, optical signal artifacts ($t_{opt}$) are matched against inertial acceleration jolts ($|a| - 1.0g > 0.4g$):
$$\text{Temporal Coincidence Window: } |t_{opt} - t_{accel}| \le 2.0\text{ seconds}$$
Overlapping events provide evidence of **physical motion interference**, eliminating false-alarm alarms regarding sensor failure or cardiac arrhythmia.

### C. Reliability Classifications
- **`HIGH_RELIABILITY` ($\ge 90.0$)**: Clean stream, minimal noise, intact continuity. Fully eligible for algorithmic decision support.
- **`MODERATE_RELIABILITY` ($75.0 - 89.9$)**: Acceptable stream with minor dropouts or baseline noise. Decision support supported with advisory notice.
- **`LOW_RELIABILITY` ($50.0 - 74.9$)**: Degraded signal. Statistical interpretations are restricted; sensor verification advised.
- **`UNRELIABLE` ($< 50.0$)**: Substantial data loss, disconnects, or severe artifacts. Downstream decision support inhibited.
- **`INSUFFICIENT_DATA`**: Fewer than 3 valid samples available.

---

## 4. Scientific Interpretation Engine Architecture

### A. Ground Medical Team Briefing (7-Section Architecture)
1. **Observation**: Parameter, measured concentration/value, unit, timestamp/mission phase, and subject ID.
2. **Baseline Comparison**: Individual preflight median ($\tilde{x}_{pre}$), absolute delta ($\Delta$), and linear percentage change ($\%\Delta$).
3. **Statistical Interpretation**: Robust Z-score ($Z = \frac{x - \tilde{x}}{1.4826 \cdot \text{MAD}}$), dispersion, and anomaly classification.
4. **Longitudinal Interpretation**: Previous mission trajectory, multi-phase fluctuation metrics, and postflight recovery classification.
5. **Sensor Quality**: Composite score, reliability category, missing/disconnection rates, and motion correlation.
6. **Evidence & Traceability**: Explicit mathematical derivations, rules triggered, and missing data limitations.
7. **Recommended Review Workflow**: Strictly operational, non-prescriptive action flags.

### B. Operational Workflow Action Catalog
All recommended actions are non-prescriptive operational workflow flags:

- **`REVIEW_MEASUREMENT`**: Triggered by moderate statistical deviation ($2.0 \le |Z| < 3.0$), non-stable trajectory, or minor sensor degradation. Flight surgeons review raw trace during normal telemetry passes.
- **`VERIFY_SENSOR_SIGNAL`**: Triggered by `LOW_RELIABILITY`, `UNRELIABLE`, or optical-motion artifact overlap. Request crew verify sensor contact, lead snugness, and optical sensor cleanliness.
- **`REPEAT_MEASUREMENT_IF_OPERATIONALLY_APPROPRIATE`**: Triggered by significant statistical deviation in high-reliability stream. Confirms physiological trend at next scheduled opportunity.
- **`REQUEST_MEDICAL_REVIEW`**: Triggered by sustained significant statistical departure ($|Z| \ge 3.0$) with verified signal integrity. Escalates observation for clinical flight surgeon evaluation.
- **`INSUFFICIENT_DATA_FOR_INTERPRETATION`**: Triggered by missing measurements, sensor disconnection, or unestablished preflight baseline.
- **`NO_ADDITIONAL_REVIEW_FLAGGED`**: Observation aligns with baseline dispersion and high signal quality. Routine monitoring maintained.

### C. Astronaut Crew Briefing Guidelines
- **Plain Language**: Technical acronyms (e.g. "MAD", "Robust Z-score") are omitted.
- **Calm, Transparent Framing**: Clear answers addressing whether the sensor is working, whether readings differ from their personal baseline, and what operational step is suggested.
- **No Medical Alarms**: Clear reminders that physical movement or microgravity fluid shifts commonly cause signal variations.
- **Standard Protocol**: Instructions always refer to standard mission medical team communication procedures.

---

## 5. Ethical & Regulatory Boundaries

1. **Non-Clinical Software**: WEDJAT-X is an exploratory prototype developed for the NASA Space Apps Challenge. It does not possess FDA 510(k), CE-mark, or clinical certification.
2. **No Automated Prescriptions**: Software must never suggest drug dosages, fluid boluses, or therapeutic interventions.
3. **Traceable Explanations**: Black-box machine learning models are omitted in favor of deterministic, evidence-traceable robust statistics.
