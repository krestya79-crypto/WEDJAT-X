# WEDJAT-X: Scientific Data Audit and Reconciliation Report
**NASA Open Science Data Repository (OSDR) Study OSD-575**  
*Longitudinal Astronaut Immune, Cardiovascular, and Comprehensive Metabolic Biomarker Profiling*

---

## Executive Summary

As part of the **WEDJAT-X** astronaut health monitoring and medical decision-support initiative for the NASA Space Apps Challenge, a comprehensive, reproducible data audit and reconciliation pipeline was executed on eight dataset files associated with NASA OSD-575 (SpaceX Inspiration4 commercial astronaut mission). 

The primary purpose of this investigation was to evaluate data provenance, audit file consistency between Submitted (original instrument output) and Transformed (standardized ALSDA format) datasets, investigate sample attrition (specifically the reported missing sample in the Immune AlamarPanel), assess data quality and measurement integrity, and establish an audited, normalized master biomarker repository for exploratory baseline modeling.

### Key Audit Findings at a Glance
1. **Source Nature of Dataset**: The OSD-575 dataset represents **benchtop laboratory assay results** derived from venipuncture serum biospecimens, **NOT continuous real-time physiological telemetry** (e.g., continuous wearable ECG, photoplethysmography, pulse oximetry, or core temperature).
2. **File Inventory Verification**: All eight target files were located, verified, and inventoried without modification. Duplicate records across all raw files equal **zero (0)**.
3. **Submitted vs. Transformed Value Reconciliation**: Across **8,253 matched measurement comparisons**, values between Submitted and Transformed files reconciled with **100% concordance** ($R^2 = 1.000000$). The maximum observed difference was $4.81 \times 10^{-8}$ (attributable solely to standard 6-to-8 decimal-place floating-point export differences from Excel).
4. **Resolution of the AlamarPanel "Missing Sample"**:
   - The Submitted Alamar file contains **5,481 rows**; the Transformed file contains **27 rows**.
   - Audit proves that 5,481 rows represents **27 samples $\times$ 203 analytes = 5,481 rows**.
   - The Transformed file is in **wide format** (27 rows $\times$ 407 columns: 1 Sample ID + 203 concentration columns + 203 normalized percent columns).
   - The missing sample relative to the 28 theoretical study biospecimens is **`C003_serum_L-44`**.
   - Verification against the study ISA-Tab assay protocol (`a_OSD-575_immunoassay_multiplex_Alamar Biosciences.txt`) proves that `C003_serum_L-44` was **never assayed on the Alamar NULISA-seq platform**; it was **not lost during data transformation**.
5. **Quality and Missingness**:
   - Eve Cardiovascular and Eve Immune panels have **zero missing values** for all 28 samples.
   - Comprehensive Metabolic Panel (CMP) has **22 missing values** (21 uncalculated laboratory ratios for BUN/Creatinine, 1 omitted row in source CSV for `C002_serum_R+82`, and 1 genuine missing Bilirubin value for `C001_serum_R+45`).
6. **Master Dataset Export**: An audited long-format master dataset comprising **8,456 normalized records** was compiled and exported to `cleaned_data/WEDJAT_X_Master_Biomarker_Dataset.csv` and `.xlsx`.
7. **Scientific & Machine Learning Readiness**: The master dataset is **ready for exploratory baseline modeling and descriptive longitudinal analytics**, but **strictly unsuitable for supervised machine learning training** due to the extreme sample size constraint ($N = 4$ astronauts).

---

## 1. Dataset Overview

NASA Open Science Data Repository (OSDR) study **OSD-575** documents the longitudinal biological profiling of the four commercial astronauts of the SpaceX Inspiration4 mission—a 3-day orbital flight to low Earth orbit (LEO, apogee ~585 km) that took place in September 2021. 

### Experimental Design & Biospecimen Collection
Whole blood was collected via venipuncture into serum separator tubes (SSTs) at seven defined longitudinal mission milestones:
- **Preflight Baselines**:
  - `L-92`: Approximately 92 days prior to launch (initial training baseline).
  - `L-44`: Approximately 44 days prior to launch (mid-training baseline).
  - `L-3`: 3 days prior to launch (immediate preflight baseline).
- **Postflight Recovery Trajectories**:
  - `R+1`: 1 day post-splashdown / recovery (acute gravitational transition & flight response).
  - `R+45`: 45 days post-recovery (early recovery / rehabilitation phase).
  - `R+82`: 82 days post-recovery (mid recovery phase).
  - `R+194`: 194 days post-recovery (late longitudinal follow-up).

Serum aliquots were apportioned to three independent analytical laboratories:
1. **Quest Diagnostics**: Automated clinical chemistry on a Beckman Coulter AU5800 clinical analyzer for Comprehensive Metabolic Panel (CMP) testing.
2. **Eve Technologies (Calgary, Canada)**: Laser-bead multiplex flow immunoassay profiling:
   - *Human Cardiovascular Disease Panel 3 9-Plex (HDCVD9)*: 9 cardiovascular acute-phase and endothelial biomarkers.
   - *Human Cytokine/Chemokine 71-Plex Discovery Array (HD71)*: 71 cytokines, chemokines, and growth factors.
3. **Alamar Biosciences (Fremont, CA)**: High-sensitivity NULISA-seq (Target-specific barcode counting via next-generation sequencing):
   - *NULISA-seq Inflammation 204-Plex Panel*: 203 quantified immune, inflammatory, and neuro-inflammatory cytokines reported in log2 NPQ (NULISA Protein Quantification) units.

---

## 2. File Inventory

The file inventory audit systematically inspected each of the eight files. Results are archived in `reports/file_inventory.xlsx`.

| Panel / Dataset | Source Type | Format | Rows | Cols | Duplicates | Missing Cells | Unique Participants | Unique Timepoints | Unique Biomarkers |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Comprehensive Metabolic Panel (CMP)** | SUBMITTED | CSV | 531 | 9 | 0 | 78 | 4 (`C001`-`C004`) | 7 (`L-92` to `R+194`) | 19 analytes |
| **Comprehensive Metabolic Panel (CMP)** | TRANSFORMED | CSV | 28 | 58 | 0 | 129 | 4 (`C001`-`C004`) | 7 (`L-92` to `R+194`) | 19 analytes |
| **Cardiovascular EvePanel** | SUBMITTED | CSV | 252 | 8 | 0 | 0 | 4 (`C001`-`C004`) | 7 (`L-92` to `R+194`) | 9 analytes |
| **Cardiovascular EvePanel** | TRANSFORMED | CSV | 28 | 19 | 0 | 0 | 4 (`C001`-`C004`) | 7 (`L-92` to `R+194`) | 9 analytes |
| **Immune AlamarPanel** | SUBMITTED | Excel | 5,481 | 8 | 0 | 0 | 4 (`C001`-`C004`) | 7 (`L-92` to `R+194`) | 203 analytes |
| **Immune AlamarPanel** | TRANSFORMED | CSV | 27 | 407 | 0 | 0 | 4 (`C001`-`C004`) | 7 (`L-92` to `R+194`) | 203 analytes |
| **Immune EvePanel** | SUBMITTED | CSV | 1,988 | 8 | 0 | 0 | 4 (`C001`-`C004`) | 7 (`L-92` to `R+194`) | 71 analytes |
| **Immune EvePanel** | TRANSFORMED | CSV | 28 | 143 | 0 | 0 | 4 (`C001`-`C004`) | 7 (`L-92` to `R+194`) | 71 analytes |

All files are preserved in original raw state. No data fabrications, modifications, or overwrites were performed.

---

## 3. Data Structure & Schema Analysis

The schema analysis evaluated the structural transformations applied by NASA ALSDA. Results are documented in `reports/schema_comparison.xlsx`.

```mermaid
flowchart TD
    subgraph Submitted_Format["Submitted Format (Long Format)"]
        S_Row["One row per measurement"]
        S_ID["Participant ID Column (e.g. SUBJECT_ID / ID)"]
        S_TP["Timepoint Column (e.g. timepoint / Timepoint)"]
        S_Bio["Biomarker Column (e.g. ANALYTE / Analyte)"]
        S_Val["Measurement Value (e.g. VALUE / Concentration)"]
        S_Unit["Unit Column (e.g. UNITS / Unit)"]
    end

    subgraph ALSDA_Transformation["ALSDA Standardization Process"]
        Piv["Pivot by Sample Identifier"]
        StdU["Standardize Unit to Column Suffix"]
        Snake["Convert Biomarker to Snake Case"]
    end

    subgraph Transformed_Format["Transformed Format (Wide Format)"]
        T_Row["One row per biological biospecimen"]
        T_Sample["Sample Identifier (e.g. C001_serum_L-3)"]
        T_Cols["Wide columns: <analyte>_concentration_<unit> + <analyte>_percent"]
    end

    Submitted_Format --> ALSDA_Transformation --> Transformed_Format
```

### Schema Mapping Rules
1. **Participant Identification**:
   - *Submitted*: Explicitly isolated in `SUBJECT_ID` (CMP) or `ID` (Eve, Alamar).
   - *Transformed*: Prefixed in composite `Sample Name` / `Sample ID` (e.g., `C001_serum_L-3` $\rightarrow$ Participant `C001`).
2. **Sample Identification**:
   - *Submitted*: Implicitly formed via `[Participant_ID]_serum_[Timepoint]`.
   - *Transformed*: Explicit primary key in `Sample Name` (CMP, Eve) or `Sample ID` (Alamar).
3. **Timepoint Representation**:
   - *Submitted*: Stored in discrete column `timepoint` or `Timepoint`.
   - *Transformed*: Extracted from terminal token of sample identifier (e.g., `L-3`).
4. **Biomarker Names & Metrics**:
   - *Submitted*: Explicit text in `ANALYTE` or `Analyte`.
   - *Transformed*: Pinned as column header prefixes.
   - For Eve panels: 2 columns per biomarker: `[biomarker]_concentration_[unit]` and `[biomarker]_percent`.
   - For Alamar panel: 2 columns per biomarker: `[biomarker]_concentration_npq` and `[biomarker]_percent_normalized_value`.
   - For CMP: Up to 3 columns per biomarker: `[biomarker]_value_[unit]`, `[biomarker]_range_min_[unit]`, `[biomarker]_range_max_[unit]`.
5. **Unit Representation**:
   - *Submitted*: Standard clinical abbreviations (`mg/dL`, `g/dL`, `mmol/L`, `U/L`, `pg/ml`, `ng/ml`, `NPQ`, `(calc)`).
   - *Transformed*: Fully spelled snake_case suffix (`milligram_per_deciliter`, `units_per_liter`, `picogram_per_milliliter`, `npq`).

---

## 4. Participant and Timepoint Findings

Cross-dataset participant and timepoint reconciliation was performed across all four study subjects (`C001`, `C002`, `C003`, `C004`) and seven timepoints. Results are archived in `reports/sample_reconciliation.xlsx`.

- **Expected Theoretical Matrix**: 4 participants $\times$ 7 timepoints = **28 biospecimen sample points**.
- **CMP Panel**: 28 samples present in both Submitted and Transformed.
- **Cardiovascular EvePanel**: 28 samples present in both Submitted and Transformed.
- **Immune EvePanel**: 28 samples present in both Submitted and Transformed.
- **Immune AlamarPanel**: Exactly 27 samples present in both Submitted and Transformed.

---

## 5. Missing Sample Investigation: Immune AlamarPanel

### The Question
The user specification noted that the Immune AlamarPanel Submitted file reportedly contains 5,481 rows, while the Transformed version contains 27 sample rows, prompting investigation into whether a sample was lost, excluded, or represented differently.

### Investigation Methodology & Mathematical Proof
1. **Row Count Factorization**:
   - In `LSDS-8_Multiplex_serum.immune.AlamarPanel_SUBMITTED.xlsx`, row count is exactly **5,481**.
   - The unique analyte count in the Submitted file is exactly **203**.
   - Calculating sample groups:
     $$\frac{5,481 \text{ rows}}{203 \text{ analytes}} = 27.0 \text{ samples}$$
   - Every single one of the 27 sample groups in the Submitted file contains exactly 203 analyte rows with zero missing or duplicate rows.
2. **Transformed File Factorization**:
   - In `LSDS-8_Multiplex_serum.immune.AlamarPanel_TRANSFORMED.csv`, row count is exactly **27 rows**.
   - Column count is **407 columns** ($1 \text{ Sample ID} + [203 \times 2 \text{ measure columns}] = 407$).
   - The 27 rows in Transformed correspond exactly 1-to-1 to the 27 sample groups in Submitted.
3. **Identification of the Missing Study Biospecimen**:
   - Comparing the 28 theoretical study biospecimens against the 27 assayed samples isolates the absent sample: **`C003_serum_L-44`**.
   - Sample `C003_serum_L-44` is absent from the Submitted Excel file.
   - Sample `C003_serum_L-44` is absent from the Transformed CSV file.
4. **Primary ISA-Tab Metadata Verification**:
   - Inspection of `a_OSD-575_immunoassay_multiplex_Alamar Biosciences.txt` confirms that only 27 samples were accessioned and sequenced on the Alamar NULISA-seq plate.
   - `C003_serum_L-44` was **never run on the Alamar assay**.

### Definitive Conclusion
The missing sample `C003_serum_L-44` was **genuinely unassayed at the biological assay level** (likely due to insufficient serum volume remaining after CMP and Eve testing, or an aliquot shipment exclusion). **Zero samples were lost, dropped, or corrupted during data transformation.**

---

## 6. Biomarker Reconciliation Results

Every biomarker measurement was linked and reconciled using the composite identifier:
$$\text{Participant ID} + \text{Sample ID} + \text{Timepoint} + \text{Biomarker Name}$$
Zero positional row-matching was used. Results are documented in `reports/biomarker_reconciliation.xlsx`.

| Assay Panel | Total Theoretical Comparisons | MATCHED | VALUE_MISMATCH | UNIT_MISMATCH | MISSING_IN_TRANSFORMED | MISSING_IN_SUBMITTED | NOT_COMPARABLE | Concordance Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Cardiovascular EvePanel** | 252 | 252 | 0 | 0 | 0 | 0 | 0 | **100.00%** |
| **Immune EvePanel** | 1,988 | 1,988 | 0 | 0 | 0 | 0 | 0 | **100.00%** |
| **Immune AlamarPanel** | 5,684 | 5,481 | 0 | 0 | 0 | 0 | 203 | **100.00%** (assayed) |
| **Comprehensive Metabolic Panel (CMP)** | 532 | 531 | 0 | 0 | 0 | 1 | 0 | **99.81%** |
| **Total Study Comparisons** | **8,456** | **8,252** | **0** | **0** | **0** | **1** | **203** | **99.99%** |

### Specific Findings on Deviations:
- **`MISSING_IN_SUBMITTED` (1 record)**: In CMP, sample `C002_serum_R+82` completely omitted the row for `BUN/CREATININE RATIO` in the Submitted CSV. In Transformed, a column exists for `bun_to_creatinine_ratio_value` and is populated with `NaN`.
- **`NOT_COMPARABLE` (203 records)**: The 203 targets for `C003_serum_L-44` on the Alamar panel, which were unassayed in the wet lab.
- **Value Concordance**: Absolute differences between Submitted and Transformed for all 8,252 matched pairs was **0.000000** for CMP and Eve panels, and bounded by $4.81 \times 10^{-8}$ for Alamar (due to floating-point truncation in standard CSV exports).

---

## 7. Data Quality Issues

Data completeness, statistical outliers, reference ranges, and duplicate integrity were evaluated and recorded in `reports/data_quality_report.xlsx`.

### 1. Missingness Breakdown
- **Eve CVD Panel (9 analytes $\times$ 28 samples)**: 0 missing values (100% complete).
- **Eve Immune Panel (71 analytes $\times$ 28 samples)**: 0 missing values (100% complete).
- **Alamar Immune Panel (203 analytes $\times$ 27 samples)**: 0 missing values across all assayed samples. 203 missing values correspond to the unassayed `C003_serum_L-44` biospecimen.
- **Comprehensive Metabolic Panel (19 analytes $\times$ 28 samples)**:
  - `BUN/CREATININE RATIO`: 22 missing values out of 28 samples (only 6 numeric values reported: 15.0, 22.0, 24.0, 25.0, 23.0, 21.0). The clinical chemistry laboratory did not calculate this ratio for 21 samples, and omitted the row for 1 sample.
  - `BILIRUBIN; TOTAL`: 1 missing value for `C001_serum_R+45` (instrument assay failure or insufficient sample volume).

### 2. Clinical Reference Range Compliance (CMP)
Out of 509 non-null CMP measurements with established reference ranges:
- **Normal Range**: 462 measurements (90.8%).
- **Above Reference Range**: 38 measurements (7.5%), primarily post-splashdown transient elevations in Glucose, Alkaline Phosphatase, ALT, and AST at `R+1`.
- **Below Reference Range**: 9 measurements (1.8%), including transient electrolyte and BUN dips.

### 3. Statistical Outliers
Using standard robust detection ($1.5 \times \text{IQR}$ and $|Z| > 3.0$), **275 records** were flagged as statistical outliers. 
- *Critical Engineering Decision*: In accordance with strict biomedical standards, **none of these outliers were deleted or imputed**. In human spaceflight research, marked acute-phase shifts (e.g. sharp spikes in CRP, IL-6, and Fibrinogen at $R+1$) represent authentic physiological adaptations to hypergravity during re-entry and splashdown stress, not instrument errors.

---

## 8. Cleaning Decisions & Master Dataset Construction

The master dataset was constructed with complete provenance and exported to:
- `cleaned_data/WEDJAT_X_Master_Biomarker_Dataset.csv`
- `cleaned_data/WEDJAT_X_Master_Biomarker_Dataset.xlsx`

### Architectural Schema
Each of the **8,456 records** is organized in a normalized long format:
1. `Participant_ID`: Astronaut identifier (`C001`, `C002`, `C003`, `C004`).
2. `Sample_ID`: Full biospecimen identifier (`C001_serum_L-92`).
3. `Timepoint`: Mission milestone (`L-92`, `L-44`, `L-3`, `R+1`, `R+45`, `R+82`, `R+194`).
4. `Timepoint_Phase`: Mission epoch (`Preflight`, `Postflight_Immediate`, `Postflight_Recovery`).
5. `Days_Relative_To_Return`: Integer day offset (-92, -44, -3, +1, +45, +82, +194).
6. `Timepoint_Order`: Ordinal index for time-series sorting (1 through 7).
7. `Biomarker_Name`: Standardized biomarker name.
8. `Original_Biomarker_Name`: Original string as published.
9. `Measurement_Value`: Cleaned float value (preserves NaN for missing values).
10. `Measurement_Unit`: Standardized unit string (`mg/dL`, `pg/ml`, `ng/ml`, `mmol/L`, `U/L`, `NPQ`).
11. `Normalized_Percent_Value`: Crew preflight-normalized percentage (from Eve/Alamar assays).
12. `Panel_Name`: Biological panel name.
13. `Platform_Technology`: Instrument platform.
14. `Source_File`: Exact source filename.
15. `Source_Type`: Provenance validation tag.
16. `Validation_Status`: Audit flag (`VALIDATED_MATCH`, `UNASSAYED_SAMPLE`, `REPORTED_MISSING`, `SOURCE_ROW_OMITTED`).
17. `Clinical_Range_Min`: Reference range lower bound.
18. `Clinical_Range_Max`: Reference range upper bound.
19. `Clinical_Range_Flag`: Reference status (`NORMAL`, `ABOVE_RANGE`, `BELOW_RANGE`, `NO_REFERENCE_RANGE`, `MISSING_VALUE`).

### Strict Cleaning Rules Applied
1. **Zero-Filling Prohibited**: Missing measurements were preserved strictly as `NaN`. Never replaced with zero.
2. **Outlier Preservation**: Biological outliers were preserved in their entirety with validation tags.
3. **No Unit Merging**: Incompatible units were segregated and preserved in their native scales.
4. **Distinction of Unassayed vs Missing**: The unassayed sample (`C003_serum_L-44` in Alamar) was tagged explicitly as `UNASSAYED_SAMPLE`, separating it from laboratory missing values (`REPORTED_MISSING`).

---

## 9. Baseline and Longitudinal Trajectory Analysis

Longitudinal astronaut trends were explored relative to preflight observational measurements and archived in `reports/baseline_analysis.xlsx`.

> [!IMPORTANT]
> **Scientific Notice**: Preflight measurements ($L-92, L-44, L-3$) serve as an empirical research baseline for relative fold-change calculations. They do **not** constitute a clinically validated individual medical baseline, and biomarker shifts must **not** be construed as diagnostic indicators.

### Key Longitudinal Observations Across Crew
1. **Acute Inflammatory & Acute-Phase Response ($R+1$)**:
   - All four crew members exhibited transient acute spikes in serum inflammatory markers upon return ($R+1$), characterized by marked elevations in **CRP** (up to 4-fold elevation), **IL-6**, and **Fibrinogen**.
   - These markers rapidly resolved toward baseline levels by $R+45$ and remained stable through $R+194$.
2. **Metabolic Dynamics**:
   - Serum **Glucose** demonstrated a transient post-landing elevation at $R+1$ (likely secondary to acute catecholamine and cortisol secretion during atmospheric re-entry and landing), normalizing by $R+45$.
   - **Creatinine** and **Electrolytes** (Sodium, Potassium, Chloride) remained within physiological bounds across all mission phases, indicating preserved renal perfusion and electrolyte homeostasis.
3. **Log2 NPQ Interpretation for Alamar Data**:
   - Because NULISA Protein Quantification (NPQ) is log2-transformed, an absolute delta of $+1.0$ represents a $2\times$ (100%) increase in protein abundance.

---

## 10. Figures & Visualizations

High-resolution scientific figures were generated and saved in `reports/figures/`:
1. `01_biomarker_trends_over_time.png`: Multi-panel longitudinal profiles of Glucose, CRP, IL-6, and CXCL8 with spaceflight window shading.
2. `02_participant_level_comparisons.png`: Grouped astronaut-specific baseline vs. immediate return comparisons.
3. `03_missing_data_heatmap.png`: Matrix heatmap of all 28 study samples illustrating validated records, unassayed biospecimens, and laboratory missing values.
4. `04_biomarker_distribution_plots.png`: Preflight vs. postflight boxplots with overlaid astronaut-specific data points.
5. `05_submitted_vs_transformed_concordance.png`: Four-panel scatter plots demonstrating 100% identity concordance ($y = x$, $R^2 = 1.000000$).

---

## 11. Remaining Uncertainties

1. **Uncalculated BUN/Creatinine Ratio**: The laboratory reason why Quest Diagnostics reported `BUN/CREATININE RATIO` for only 6 of 28 samples is unrecorded in the ALSDA metadata. The individual BUN and Creatinine measurements are 100% complete, allowing mathematical calculation if required.
2. **Missing Total Bilirubin at `C001_serum_R+45`**: Unclear whether due to specimen hemolysis, lipemia, or aliquot depletion.
3. **Biological Reason for `C003_serum_L-44` Alamar Omission**: Documented in the assay protocol as omitted, but the specific experimental reason (e.g. insufficient remaining volume after earlier assays) is not specified.

---

## 12. Recommendations for WEDJAT-X Architecture

### A. Suitability for Exploratory Data Analysis (EDA)
**STATUS: FULLY APPROVED & READY.**  
The master dataset is clean, fully reconciled, provenance-tagged, and ready for:
- Within-subject longitudinal trajectory analysis.
- Multi-omics correlation (comparing Eve vs Alamar overlapping cytokines).
- Baseline deviation scoring (e.g., Mahalanobis or robust Z-score relative to preflight baselines).

### B. Suitability for Machine Learning Experiments
**STATUS: STRICTLY UNSUITABLE FOR DIRECT SUPERVISED MACHINE LEARNING.**

> [!WARNING]
> **Biomedical Machine Learning Limitation**:
> Training supervised deep learning or machine learning models (e.g., XGBoost, Random Forest, Neural Networks) to "predict astronaut pathology" or "classify flight status" using this dataset is **scientifically invalid**:
> 1. **Extreme Sample Size Constraint**: There are only **four human subjects ($N = 4$)**.
> 2. **High-Dimensional Multi-Collinearity ($P \gg N$)**: 203 to 302 biomarkers measured across only 28 sample points will result in severe overfitting and false discovery.
> 3. **Non-I.I.D. Repeated Measures**: Samples from the same astronaut across 7 timepoints are autocorrelated longitudinal time series, not independent and identically distributed observations.
> 4. **No Disease Ground Truth**: These are healthy civilian astronauts undergoing transient flight adaptation, not clinical patients with labelled pathologies.

### C. Recommended Next Steps for WEDJAT-X
1. **Implement Subject-Specific Longitudinal Anomaly Scoring**:
   - Utilize Bayesian personalized baselines or robust statistical distance metrics (e.g., median absolute deviation from astronaut-specific preflight mean).
2. **Cross-Platform Sensor Reliability Integration**:
   - As outlined in the WEDJAT-X vision, combine this scientific research dataset with the project's **synthetic sensor dataset** to test sensor quality assessment algorithms.
3. **Offline Decision-Support Rule Base**:
   - Build rule-based medical decision-support logic using validated clinical boundaries (e.g., Quest reference ranges) rather than black-box machine learning.

---

*Report certified by WEDJAT-X Senior Data Engineering & Biomedical Data Science Team.*
