"""
WEDJAT-X Phase 7 — Analytical Pipelines
Independent, decoupled processing pipelines for NASA laboratory data and synthetic wearable telemetry.

CRITICAL ARCHITECTURAL CONSTRAINTS:
1. PIPELINE A (NASA_LAB): Discrete NASA OSD-575 biospecimen assays (N=4, L-92..R+194).
2. PIPELINE B (SYNTHETIC_WEARABLE): Continuous simulated physiological telemetry.
3. NEVER merge, concatenate, or cross-populate data between these two pipelines.
4. Maintain strict provenance: is_synthetic = False for NASA_LAB, True for SYNTHETIC_WEARABLE.
5. If an analytical component fails, report partial success/failure; NEVER fabricate normal values.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import numpy as np
import pandas as pd

from application.exceptions import (
    DataRoutingError,
    EngineExecutionError,
    ProvenanceViolationError,
    ValidationError,
)
from application.result_manager import ResultManager
from application.schemas import (
    ProcessingResult,
    ProcessingStatus,
    SourceType,
)
from application.validators import (
    validate_nasa_lab_data,
    validate_synthetic_wearable_data,
)
from intelligence.alert_engine import (
    IntelligentAlertEngine,
    AlertRecord,
    IntegratedStateSummary,
)
from intelligence.anomaly import AnomalyDetector
from intelligence.baseline import BaselineEngine
from intelligence.features import (
    FeatureConfig,
    STANDARD_SENSOR_FEATURES,
    extract_motion_features,
    extract_window_features,
    prepare_model_matrix,
)
from intelligence.interpretation import ScientificInterpreter
from intelligence.model_evaluation import (
    BayesianAnomalyDetector,
    IsolationForestDetector,
    NasaBiomarkerEvaluator,
    StatisticalBaselineDetector,
)
from intelligence.sensor_trust import SensorTrustEngine
from intelligence.synthetic_sensors import (
    SENSOR_ACCELEROMETER,
    SENSOR_HEART_RATE,
    SENSOR_SPO2,
)
from intelligence.trajectory import LongitudinalTrajectoryEngine

logger = logging.getLogger("WEDJAT_X.Pipeline")


class BasePipeline(ABC):
    """Abstract base class for WEDJAT-X processing pipelines."""

    def __init__(
        self,
        alert_engine: Optional[IntelligentAlertEngine] = None,
        result_manager: Optional[ResultManager] = None,
    ) -> None:
        self.alert_engine = alert_engine or IntelligentAlertEngine()
        self.result_manager = result_manager or ResultManager()

    @abstractmethod
    def execute(
        self,
        data: Any,
        subject_id: Optional[str] = None,
        is_synthetic: Optional[bool] = None,
        **kwargs: Any,
    ) -> ProcessingResult:
        """Execute the end-to-end processing pipeline."""
        pass


class NasaLabPipeline(BasePipeline):
    """
    PIPELINE A — Discrete NASA Laboratory Biomarker Assays (OSD-575).
    """

    def __init__(
        self,
        alert_engine: Optional[IntelligentAlertEngine] = None,
        result_manager: Optional[ResultManager] = None,
        baseline_engine: Optional[BaselineEngine] = None,
        anomaly_detector: Optional[AnomalyDetector] = None,
        trajectory_engine: Optional[LongitudinalTrajectoryEngine] = None,
    ) -> None:
        super().__init__(alert_engine=alert_engine, result_manager=result_manager)
        self.baseline_engine = baseline_engine or BaselineEngine()
        self.anomaly_detector = anomaly_detector or AnomalyDetector()
        self.trajectory_engine = trajectory_engine or LongitudinalTrajectoryEngine()
        self.interpreter = ScientificInterpreter()

    def execute(
        self,
        data: Any,
        subject_id: Optional[str] = None,
        is_synthetic: Optional[bool] = None,
        **kwargs: Any,
    ) -> ProcessingResult:
        """
        Execute Pipeline A for NASA OSD-575 laboratory biomarker assays.

        Steps:
        1. Dataset validation.
        2. Participant identification.
        3. Biomarker identification.
        4. Baseline analysis.
        5. Statistical anomaly detection.
        6. Bayesian predictive analysis where appropriate.
        7. Longitudinal trajectory analysis.
        8. Alert generation.
        9. Scientific interpretation.
        10. Structured result generation.
        """
        start_time = time.perf_counter()
        engine_metrics: Dict[str, float] = {}
        errors: List[str] = []

        # 1. Dataset validation
        try:
            val_start = time.perf_counter()
            df = validate_nasa_lab_data(data, is_synthetic=is_synthetic)
            engine_metrics["validation_seconds"] = time.perf_counter() - val_start
        except Exception as e:
            logger.error("NASA Lab data validation failed: %s", e)
            raise

        # 2. Participant identification
        available_participants = sorted(df["Participant_ID"].dropna().unique().tolist())
        if not available_participants:
            raise ValidationError("No valid Participant_ID found in NASA laboratory dataset.")
        if subject_id is not None and subject_id not in available_participants:
            raise ValidationError(
                f"Astronaut identifier '{subject_id}' is not present in the supplied NASA laboratory dataset."
            )

        target_participant = subject_id if subject_id is not None else available_participants[0]
        participant_df = df[df["Participant_ID"] == target_participant].copy()

        # 3. Biomarker identification
        biomarkers = sorted(participant_df["Biomarker_Name"].dropna().unique().tolist())

        # 4. Baseline analysis
        t0 = time.perf_counter()
        baseline_records: Dict[str, Any] = {}
        b_engine = None
        try:
            # Re-init baseline engine with current dataset
            b_engine = BaselineEngine(data_source=df)
            baselines_df = b_engine.calculate_baseline(target_participant)
            for _, b_row in baselines_df.iterrows():
                b_name = b_row["Biomarker_Name"]
                baseline_records[b_name] = {
                    "biomarker_name": b_name,
                    "baseline_median": b_row.get("Baseline_Median"),
                    "baseline_mad": b_row.get("Baseline_MAD"),
                    "preflight_sample_count": b_row.get("Preflight_Sample_Count"),
                    "baseline_status": b_row.get("Baseline_Status"),
                }
            engine_metrics["baseline_analysis_seconds"] = time.perf_counter() - t0
        except Exception as e:
            msg = f"Baseline analysis failed for {target_participant}: {e}"
            logger.warning(msg)
            errors.append(msg)
            baselines_df = pd.DataFrame()

        # 5. Statistical anomaly detection
        t0 = time.perf_counter()
        anomaly_records: Dict[str, Any] = {}
        try:
            if b_engine is not None and not baselines_df.empty:
                longitudinal_df = b_engine.calculate_longitudinal_changes(target_participant)
                anomalies_df = self.anomaly_detector.detect_anomalies(longitudinal_df)
                for _, a_row in anomalies_df.iterrows():
                    key = f"{a_row['Biomarker_Name']}::{a_row['Timepoint']}"
                    anomaly_records[key] = {
                        "biomarker_name": a_row["Biomarker_Name"],
                        "timepoint": a_row["Timepoint"],
                        "measurement_value": a_row.get("Measurement_Value"),
                        "robust_z": a_row.get("Robust_Z_Score"),
                        "is_anomaly": bool(a_row.get("Is_Anomaly", False)),
                        "anomaly_level": a_row.get("Anomaly_Level"),
                        "explanation": a_row.get("Anomaly_Explanation"),
                    }
            engine_metrics["anomaly_detection_seconds"] = time.perf_counter() - t0
        except Exception as e:
            msg = f"Statistical anomaly detection failed: {e}"
            logger.warning(msg)
            errors.append(msg)

        # 6. Longitudinal trajectory analysis
        t0 = time.perf_counter()
        trajectory_records: Dict[str, Any] = {}
        try:
            t_engine = LongitudinalTrajectoryEngine(baseline_engine=b_engine, data_source=df)
            traj_df = t_engine.analyze_participant(target_participant)
            for _, t_row in traj_df.iterrows():
                b_name = t_row["Biomarker_Name"]
                trajectory_records[b_name] = {
                    "biomarker_name": b_name,
                    "recovery_class": t_row.get("Recovery_Class"),
                    "overall_trend": t_row.get("Overall_Trend"),
                    "preflight_baseline_median": t_row.get("Baseline_Median"),
                    "trajectory_explanation": t_row.get("Explanation"),
                }
            engine_metrics["trajectory_analysis_seconds"] = time.perf_counter() - t0
        except Exception as e:
            msg = f"Longitudinal trajectory analysis failed: {e}"
            logger.warning(msg)
            errors.append(msg)

        # 7. Bayesian predictive analysis
        t0 = time.perf_counter()
        bayesian_records: Dict[str, Any] = {}
        try:
            # Run exploratory Bayesian model evaluation where preflight samples exist
            for b_name in biomarkers:
                b_info = baseline_records.get(b_name, {})
                med = b_info.get("baseline_median")
                mad = b_info.get("baseline_mad")
                cnt = b_info.get("preflight_sample_count", 0)
                if med is not None and not np.isnan(med) and cnt >= 2:
                    bayes = BayesianAnomalyDetector()
                    bayes.mu_n = float(med)
                    bayes.pred_scale = max(float(mad) * 1.4826 if mad and not np.isnan(mad) else 1.0, 0.5)
                    bayes.df = float(max(cnt * 2, 4.0))
                    bayes.is_fitted = True

                    # Evaluate postflight values
                    post_rows = participant_df[
                        (participant_df["Biomarker_Name"] == b_name) &
                        (participant_df["Timepoint"].str.startswith("R+"))
                    ]
                    for _, p_row in post_rows.iterrows():
                        pval = p_row["Measurement_Value"]
                        if pd.notna(pval):
                            _, b_scores, b_pvals = bayes.predict([pval])
                            tp_key = f"{b_name}::{p_row['Timepoint']}"
                            bayesian_records[tp_key] = {
                                "biomarker_name": b_name,
                                "timepoint": p_row["Timepoint"],
                                "p_value": float(b_pvals[0]),
                                "is_bayesian_anomaly": bool(b_pvals[0] < 0.05),
                            }
            engine_metrics["bayesian_analysis_seconds"] = time.perf_counter() - t0
        except Exception as e:
            msg = f"Bayesian predictive evaluation encountered issues: {e}"
            logger.warning(msg)
            errors.append(msg)

        # 8. Alert generation
        t0 = time.perf_counter()
        alerts: List[AlertRecord] = []
        try:
            # Evaluate postflight observations through IntelligentAlertEngine
            postflight_df = participant_df[participant_df["Timepoint"].str.startswith("R+")].copy()
            for _, row in postflight_df.iterrows():
                b_name = row["Biomarker_Name"]
                tp = row["Timepoint"]
                val = row["Measurement_Value"]
                unit = str(row.get("Measurement_Unit", ""))
                panel = str(row.get("Panel_Name", "General"))

                b_stat = baseline_records.get(b_name, {})
                traj_info = trajectory_records.get(b_name, {})

                alert_rec = self.alert_engine.evaluate_biomarker_observation(
                    participant_id=target_participant,
                    biomarker_name=b_name,
                    current_value=val,
                    current_timepoint=tp,
                    unit=unit,
                    panel_name=panel,
                    baseline_median=b_stat.get("baseline_median"),
                    baseline_mad=b_stat.get("baseline_mad"),
                    preflight_sample_count=b_stat.get("preflight_sample_count", 0),
                )
                alerts.append(alert_rec)

            engine_metrics["alert_generation_seconds"] = time.perf_counter() - t0
        except Exception as e:
            msg = f"Alert generation failed: {e}"
            logger.error(msg)
            errors.append(msg)

        # 9. Integrated state summary
        int_summary = self.alert_engine.evaluate_integrated_state(
            subject_id=target_participant, alerts=alerts
        )
        alert_summary_dict = int_summary.to_dict()
        # Lab assays have no wearable sensor to inspect; keep NASA guidance in
        # the domain of discrete assay evidence and human review.
        if alert_summary_dict.get("highest_operational_state") == "REVIEW":
            alert_summary_dict["operational_guidance"] = (
                "Review flagged discrete laboratory assay observations against source records and "
                "longitudinal context with an authorized flight surgeon."
            )

        missing_count = int(participant_df["Measurement_Value"].isna().sum())
        valid_count = int(participant_df["Measurement_Value"].notna().sum())
        warnings: List[str] = []
        if missing_count:
            warnings.append(
                f"{missing_count} of {len(participant_df)} discrete laboratory measurements are missing; "
                "missing values were preserved and not imputed."
            )
        if valid_count == 0:
            status = ProcessingStatus.INSUFFICIENT_DATA.value
            alert_summary_dict["highest_operational_state"] = "INSUFFICIENT_DATA"
            alert_summary_dict["operational_guidance"] = (
                "No valid laboratory measurements were available for evaluation; human review is required."
            )
        elif errors:
            status = ProcessingStatus.PARTIAL_SUCCESS.value if alerts else ProcessingStatus.PROCESSING_ERROR.value
            alert_summary_dict["highest_operational_state"] = "PROCESSING_ERROR"
            alert_summary_dict["operational_guidance"] = (
                "One or more analytical components failed; review the reported errors before interpreting results."
            )
        else:
            status = ProcessingStatus.SUCCESS.value

        interpretation_records: Dict[str, Any] = {}
        for biomarker_name in biomarkers:
            biomarker_rows = participant_df[participant_df["Biomarker_Name"] == biomarker_name]
            representative = biomarker_rows[biomarker_rows["Timepoint"].str.startswith("R+")].head(1)
            if representative.empty:
                representative = biomarker_rows.head(1)
            if representative.empty:
                continue
            row = representative.iloc[0]
            timepoint = str(row["Timepoint"])
            baseline = baseline_records.get(biomarker_name, {})
            anomaly = anomaly_records.get(f"{biomarker_name}::{timepoint}", {})
            trajectory = trajectory_records.get(biomarker_name, {})
            interpretation_records[biomarker_name] = {
                "baseline": self.interpreter.interpret_baseline(
                    biomarker_name=biomarker_name,
                    current_value=row["Measurement_Value"],
                    baseline_median=baseline.get("baseline_median"),
                    baseline_mad=baseline.get("baseline_mad"),
                    n_baseline=(
                        int(baseline["preflight_sample_count"])
                        if pd.notna(baseline.get("preflight_sample_count")) else 0
                    ),
                    unit=str(row.get("Measurement_Unit", "")),
                    participant_id=target_participant,
                ),
                "statistical_evidence": self.interpreter.interpret_anomaly({
                    "anomaly_flag": anomaly.get("anomaly_level", "INSUFFICIENT_DATA"),
                    "robust_z_score": anomaly.get("robust_z"),
                    "is_anomaly": anomaly.get("is_anomaly", False),
                }),
                "trajectory": self.interpreter.interpret_trajectory({
                    "Biomarker_Name": biomarker_name,
                    "Postflight_Recovery_Class": trajectory.get("recovery_class", "INSUFFICIENT_DATA"),
                    "Overall_Trend": trajectory.get("overall_trend", "INSUFFICIENT_DATA"),
                }),
            }

        # 10. Extract sample measurements for record
        measurements_sample = []
        for _, m_row in participant_df.head(50).iterrows():
            measurements_sample.append({
                "participant_id": target_participant,
                "biomarker_name": m_row["Biomarker_Name"],
                "timepoint": m_row["Timepoint"],
                "value": m_row["Measurement_Value"],
                "unit": m_row.get("Measurement_Unit"),
                "panel": m_row.get("Panel_Name"),
            })

        total_duration = time.perf_counter() - start_time
        engine_metrics["total_pipeline_seconds"] = total_duration

        return self.result_manager.create_result(
            source_type=SourceType.NASA_LAB.value,
            subject_id=target_participant,
            is_synthetic=False,
            processing_status=status,
            measurements=measurements_sample,
            baseline_analysis=baseline_records,
            anomaly_analysis=anomaly_records,
            bayesian_analysis=bayesian_records,
            isolation_forest_analysis={},  # Not applicable to discrete N=4 wet-lab assays
            trajectory_analysis=trajectory_records,
            sensor_trust_analysis={},      # Not applicable to laboratory biospecimens
            alert_summary=alert_summary_dict,
            data_quality={
                "total_observations": len(participant_df),
                "unique_biomarkers": len(biomarkers),
                "missing_values": missing_count,
                "valid_measurements": valid_count,
                "data_source": "NASA Open Science Data Repository (OSD-575)",
                "collection_type": "Venipuncture Serum Biospecimen Wet-Lab Assay",
            },
            errors=errors,
            warnings=warnings,
            execution_metrics=engine_metrics,
            metadata=kwargs.get("metadata"),
            interpretation={
                "evidence_scope": "Discrete OSD-575 laboratory milestones; not continuous telemetry.",
                "astronaut_interpretations": interpretation_records,
                "human_medical_review_required": True,
            },
            confidence_or_evidence_summary={
                "participant_count": len(available_participants),
                "population_generalization_supported": False,
                "evidence_note": "Four Inspiration4 participants do not support population-level or clinical generalization.",
            },
        )


class SyntheticWearablePipeline(BasePipeline):
    """
    PIPELINE B — Continuous Synthetic Wearable Sensor Telemetry.
    """

    def __init__(
        self,
        alert_engine: Optional[IntelligentAlertEngine] = None,
        result_manager: Optional[ResultManager] = None,
        sensor_trust_engine: Optional[SensorTrustEngine] = None,
    ) -> None:
        super().__init__(alert_engine=alert_engine, result_manager=result_manager)
        self.sensor_trust_engine = sensor_trust_engine or SensorTrustEngine()
        self.interpreter = ScientificInterpreter()

    def execute(
        self,
        data: Any,
        subject_id: Optional[str] = None,
        is_synthetic: Optional[bool] = None,
        accel_data: Optional[Any] = None,
        **kwargs: Any,
    ) -> ProcessingResult:
        """
        Execute Pipeline B for continuous synthetic wearable sensor telemetry.

        Steps:
        1. Schema validation.
        2. Timestamp validation.
        3. Feature extraction.
        4. Statistical anomaly detection.
        5. Bayesian predictive analysis.
        6. Isolation Forest secondary analysis.
        7. Sensor trust evaluation.
        8. Motion artifact cross-check.
        9. Alert generation.
        10. Scientific interpretation.
        """
        start_time = time.perf_counter()
        engine_metrics: Dict[str, float] = {}
        errors: List[str] = []

        # 1 & 2. Schema and Timestamp validation
        try:
            val_start = time.perf_counter()
            df = validate_synthetic_wearable_data(data, is_synthetic=is_synthetic)

            accel_df = None
            if accel_data is not None:
                accel_df = validate_synthetic_wearable_data(accel_data, is_synthetic=is_synthetic)
                if set(accel_df["sensor_type"].unique()) != {SENSOR_ACCELEROMETER}:
                    raise ValidationError(
                        "accel_data must contain only synthetic accelerometer records."
                    )

            engine_metrics["validation_seconds"] = time.perf_counter() - val_start
        except Exception as e:
            logger.error("Synthetic wearable data validation failed: %s", e)
            raise

        target_subject = subject_id or "Synthetic_Crew_Member"
        sensor_groups = {
            str(sensor): group.copy().reset_index(drop=True)
            for sensor, group in df.groupby("sensor_type", sort=True)
        }
        embedded_accel = sensor_groups.get(SENSOR_ACCELEROMETER)
        motion_data = accel_df if accel_df is not None else embedded_accel
        sensor_types = sorted(sensor_groups)
        primary_sensor = sensor_types[0] if len(sensor_types) == 1 else "multiple_sensors"

        # 3, 7. Feature extraction and trust scoring stay scoped to each sensor stream.
        t0 = time.perf_counter()
        trust_by_sensor: Dict[str, Dict[str, Any]] = {}
        feature_rows: Dict[str, int] = {}
        trust_duration = 0.0
        feature_duration = 0.0
        for sensor_type, sensor_df in sensor_groups.items():
            trust_t0 = time.perf_counter()
            try:
                trust_input = sensor_df
                if motion_data is not None and sensor_type != SENSOR_ACCELEROMETER:
                    trust_input = pd.concat([sensor_df, motion_data], ignore_index=True)
                trust_by_sensor[sensor_type] = self.sensor_trust_engine.evaluate_sensor(
                    trust_input, sensor_type=sensor_type
                )
            except Exception as e:
                msg = f"Sensor trust evaluation failed for {sensor_type}: {e}"
                logger.warning(msg)
                errors.append(msg)
            finally:
                trust_duration += time.perf_counter() - trust_t0

            feature_t0 = time.perf_counter()
            try:
                feat_cfg = FeatureConfig(window_size=10, min_periods=3)
                features = extract_window_features(sensor_df, config=feat_cfg)
                if motion_data is not None and sensor_type != SENSOR_ACCELEROMETER:
                    features = extract_motion_features(features, motion_data, config=feat_cfg)
                feature_rows[sensor_type] = len(features)
            except Exception as e:
                msg = f"Feature extraction failed for {sensor_type}: {e}"
                logger.warning(msg)
                errors.append(msg)
            finally:
                feature_duration += time.perf_counter() - feature_t0
        engine_metrics["sensor_trust_seconds"] = trust_duration
        engine_metrics["feature_extraction_seconds"] = feature_duration
        engine_metrics["sensor_trust_and_feature_seconds"] = time.perf_counter() - t0

        # 4, 5, 6, 8, 9. Alert evidence is evaluated independently per sensor stream.
        t0 = time.perf_counter()
        alerts: List[AlertRecord] = []
        for sensor_type, sensor_df in sensor_groups.items():
            try:
                alerts.extend(self.alert_engine.evaluate_sensor_stream(
                    stream_df=sensor_df,
                    sensor_type=sensor_type,
                    accel_df=motion_data if sensor_type != SENSOR_ACCELEROMETER else None,
                    subject_id=target_subject,
                ))
            except Exception as e:
                msg = f"Wearable telemetry stream evaluation failed for {sensor_type}: {e}"
                logger.error(msg)
                errors.append(msg)
        engine_metrics["multi_engine_alert_seconds"] = time.perf_counter() - t0

        # Extract Secondary Isolation Forest analysis summary
        iso_summary: Dict[str, Any] = {}
        if alerts:
            iso_flag_count = sum(
                1 for a in alerts if a.isolation_forest_evidence.get("is_anomaly", False)
            )
            iso_summary = {
                "algorithm": "IsolationForest (Contamination=0.05)",
                "evaluated_observations": len(alerts),
                "deviations_detected": iso_flag_count,
                "operational_role": "Secondary Multidimensional Pattern Context (Cannot trigger standalone alerts)",
            }

        # Integrated State Summary
        int_summary = self.alert_engine.evaluate_integrated_state(
            subject_id=target_subject, alerts=alerts
        )
        alert_summary_dict = int_summary.to_dict()

        valid_count = int(df["signal_value"].notna().sum())
        missing_count = int(df["signal_value"].isna().sum())
        warnings: List[str] = []
        if missing_count:
            warnings.append(
                f"{missing_count} of {len(df)} synthetic telemetry samples are missing; "
                "missing values were preserved and not imputed."
            )
        low_trust_sensors = [
            sensor for sensor, result in trust_by_sensor.items()
            if result.get("reliability_category") in ("LOW_RELIABILITY", "UNRELIABLE", "INSUFFICIENT_DATA")
        ]
        if low_trust_sensors:
            warnings.append(
                "Low or insufficient signal trust for sensor(s): "
                f"{', '.join(low_trust_sensors)}; corresponding readings must not be interpreted as normal."
            )

        if valid_count == 0:
            status = ProcessingStatus.INSUFFICIENT_DATA.value
            alert_summary_dict["highest_operational_state"] = "INSUFFICIENT_DATA"
            alert_summary_dict["operational_guidance"] = (
                "No valid synthetic telemetry values were available; human review is required."
            )
        elif errors:
            status = ProcessingStatus.PARTIAL_SUCCESS.value if alerts else ProcessingStatus.PROCESSING_ERROR.value
            alert_summary_dict["highest_operational_state"] = "PROCESSING_ERROR"
            alert_summary_dict["operational_guidance"] = (
                "One or more analytical components failed; review the reported errors before interpreting results."
            )
        else:
            status = ProcessingStatus.SUCCESS.value
            if low_trust_sensors and alert_summary_dict.get("highest_operational_state") == "NORMAL":
                alert_summary_dict["highest_operational_state"] = "INSUFFICIENT_DATA"
                alert_summary_dict["operational_guidance"] = (
                    "Sensor quality is insufficient for a normal-status summary; verify signal integrity and seek human review."
                )

        if len(sensor_types) == 1:
            trust_analysis: Dict[str, Any] = trust_by_sensor.get(sensor_types[0], {})
        else:
            trust_analysis = {
                "sensors": trust_by_sensor,
                "sensor_count": len(sensor_types),
            }

        # Sample measurements
        measurements_sample = []
        for _, s_row in df.head(50).iterrows():
            measurements_sample.append({
                "timestamp": str(s_row["timestamp"]),
                "sensor_type": s_row["sensor_type"],
                "signal_value": s_row["signal_value"],
                "scenario": s_row.get("scenario", "NORMAL"),
                "signal_status": s_row.get("signal_status", "VALID"),
            })

        total_duration = time.perf_counter() - start_time
        engine_metrics["total_pipeline_seconds"] = total_duration

        baselines_by_sensor: Dict[str, Any] = {}
        for sensor_type, sensor_df in sensor_groups.items():
            values = sensor_df["signal_value"].dropna()
            baselines_by_sensor[sensor_type] = {
                "reference_median": float(values.median()) if not values.empty else None,
                "valid_samples": int(values.size),
            }
        baseline_summary: Dict[str, Any] = (
            baselines_by_sensor[sensor_types[0]]
            if len(sensor_types) == 1 else {"sensors": baselines_by_sensor}
        )
        sampling_intervals = [
            group["timestamp"].sort_values().diff().dt.total_seconds().dropna()
            for _, group in df.groupby("sensor_type", sort=False)
        ]
        interval_values = (
            pd.concat(sampling_intervals)
            if sampling_intervals else pd.Series(dtype=float)
        )
        sampling_frequency = (
            float(1.0 / interval_values.median())
            if not interval_values.empty and interval_values.median() > 0 else None
        )
        interpretations = {
            sensor: self.interpreter.interpret_sensor_quality(result)
            for sensor, result in trust_by_sensor.items()
        }
        statistical_count = sum(
            1 for alert in alerts if alert.statistical_evidence.get("is_anomaly", False)
        )
        bayesian_count = sum(
            1 for alert in alerts if alert.bayesian_evidence.get("is_anomaly", False)
        )

        return self.result_manager.create_result(
            source_type=SourceType.SYNTHETIC_WEARABLE.value,
            subject_id=target_subject,
            is_synthetic=True,
            processing_status=status,
            measurements=measurements_sample,
            baseline_analysis=baseline_summary,
            anomaly_analysis={
                "statistical_anomalies_flagged": statistical_count,
            },
            bayesian_analysis={
                "bayesian_anomalies_flagged": bayesian_count,
            },
            isolation_forest_analysis=iso_summary,
            trajectory_analysis={},  # Not applicable to continuous short-duration sensor streams
            sensor_trust_analysis=trust_analysis,
            alert_summary=alert_summary_dict,
            data_quality={
                "total_stream_samples": len(df),
                "valid_samples": valid_count,
                "missing_samples": missing_count,
                "missing_rate": float(missing_count / len(df)) if len(df) else None,
                "disconnection_rate": float(
                    sum(result.get("disconnection_rate", 0.0) or 0.0 for result in trust_by_sensor.values())
                    / len(trust_by_sensor)
                ) if trust_by_sensor else None,
                "quality_score": (
                    trust_by_sensor[sensor_types[0]].get("quality_score")
                    if len(sensor_types) == 1 and sensor_types[0] in trust_by_sensor else None
                ),
                "sensor_reliability": (
                    trust_by_sensor[sensor_types[0]].get("reliability_category")
                    if len(sensor_types) == 1 and sensor_types[0] in trust_by_sensor else None
                ),
                "sampling_frequency_hz": sampling_frequency,
                "sensor_types": sensor_types,
                "feature_rows": feature_rows,
            },
            errors=errors,
            warnings=warnings,
            execution_metrics=engine_metrics,
            metadata=kwargs.get("metadata"),
            interpretation={
                "sensor_quality": interpretations,
                "human_medical_review_required": True,
            },
            confidence_or_evidence_summary={
                "statistical_anomalies_flagged": statistical_count,
                "bayesian_anomalies_flagged": bayesian_count,
                "isolation_forest_role": "Secondary context only; cannot trigger alerts alone.",
                "clinical_confidence_claimed": False,
            },
        )
