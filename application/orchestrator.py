"""
WEDJAT-X Phase 7 — Central Orchestration Engine (WEDJATXSystem)
Single entry-point for data ingestion, pipeline routing, AI coordination, and reporting.

Regulatory Safety Rule:
WEDJAT-X is an exploratory biomedical engineering and medical decision-support
system for the NASA Space Apps Challenge. It does NOT provide clinical diagnoses,
disease predictions, or treatment prescriptions.
"""

from datetime import datetime, timezone
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Union
import pandas as pd

from application.data_manager import DataManager
from application.exceptions import (
    DataRoutingError,
    ProvenanceViolationError,
    SchemaMismatchError,
    UnsupportedSourceError,
    ValidationError,
    WedjatXError,
)
from application.pipeline import NasaLabPipeline, SyntheticWearablePipeline
from application.result_manager import ResultManager
from application.storage import SQLiteStore
from application.schemas import (
    NON_CLINICAL_DISCLAIMER,
    ProcessingRequest,
    ProcessingResult,
    ProcessingStatus,
    SourceType,
    SystemOperationalState,
    SystemStatus,
)
from application.validators import validate_source_type
from application.validators import validate_nasa_lab_data, validate_synthetic_wearable_data
from intelligence.alert_engine import AlertEngineConfig, IntelligentAlertEngine
from intelligence.anomaly import AnomalyDetector
from intelligence.baseline import BaselineEngine
from intelligence.interpretation import ScientificInterpreter
from intelligence.sensor_trust import SensorTrustConfig, SensorTrustEngine
from intelligence.synthetic_sensors import SyntheticSensorGenerator
from intelligence.trajectory import LongitudinalTrajectoryEngine

logger = logging.getLogger("WEDJAT_X.System")


class WEDJATXSystem:
    """
    Central Coordinator and Unified Gateway for the WEDJAT-X Architecture.
    """

    def __init__(
        self,
        base_dir: Optional[Union[str, Path]] = None,
        alert_config: Optional[AlertEngineConfig] = None,
        sensor_trust_config: Optional[SensorTrustConfig] = None,
        anomaly_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize the WEDJAT-X System and instantiate all core intelligence engines.
        """
        self.init_start_time = time.perf_counter()
        self.backend_version = "1.0.0"
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        self.last_processing_timestamp: Optional[str] = None
        self.current_processing_state: str = "IDLE"

        self.initialized_engines: Dict[str, bool] = {}
        self.initialization_errors: List[str] = []

        # 1. Initialize Managers
        self.data_manager = DataManager(base_dir=self.base_dir)
        self.result_manager = ResultManager()
        self.storage = SQLiteStore(self.base_dir / "wedjatx.sqlite3")

        # 2. Initialize Scientific & AI Modules safely
        self._init_engines(
            alert_config=alert_config,
            sensor_trust_config=sensor_trust_config,
            anomaly_config=anomaly_config,
        )

        # 3. Initialize Pipelines
        self.nasa_pipeline = NasaLabPipeline(
            alert_engine=self.alert_engine,
            result_manager=self.result_manager,
            baseline_engine=self.baseline_engine,
            anomaly_detector=self.anomaly_detector,
            trajectory_engine=self.trajectory_engine,
        )

        self.synthetic_pipeline = SyntheticWearablePipeline(
            alert_engine=self.alert_engine,
            result_manager=self.result_manager,
            sensor_trust_engine=self.sensor_trust_engine,
        )

        self.init_duration = time.perf_counter() - self.init_start_time
        logger.info("WEDJATXSystem initialized in %.3f seconds.", self.init_duration)

    def _init_engines(
        self,
        alert_config: Optional[AlertEngineConfig],
        sensor_trust_config: Optional[SensorTrustConfig],
        anomaly_config: Optional[Dict[str, Any]],
    ) -> None:
        """Instantiate and verify underlying analytical engines."""
        # Baseline Engine
        try:
            self.baseline_engine = BaselineEngine()
            self.initialized_engines["baseline_engine"] = True
        except Exception as e:
            self.initialized_engines["baseline_engine"] = False
            self.initialization_errors.append(f"baseline_engine failed to initialize: {e}")

        # Anomaly Detector
        try:
            self.anomaly_detector = AnomalyDetector(**(anomaly_config or {}))
            self.initialized_engines["anomaly_detector"] = True
        except Exception as e:
            self.initialized_engines["anomaly_detector"] = False
            self.initialization_errors.append(f"anomaly_detector failed to initialize: {e}")

        # Trajectory Engine
        try:
            self.trajectory_engine = LongitudinalTrajectoryEngine(baseline_engine=self.baseline_engine)
            self.initialized_engines["trajectory_engine"] = True
        except Exception as e:
            self.initialized_engines["trajectory_engine"] = False
            self.initialization_errors.append(f"trajectory_engine failed to initialize: {e}")

        # Synthetic Sensor Generator
        try:
            self.synthetic_generator = SyntheticSensorGenerator()
            self.initialized_engines["synthetic_generator"] = True
        except Exception as e:
            self.initialized_engines["synthetic_generator"] = False
            self.initialization_errors.append(f"synthetic_generator failed to initialize: {e}")

        # Sensor Trust Engine
        try:
            self.sensor_trust_engine = SensorTrustEngine(config=sensor_trust_config)
            self.initialized_engines["sensor_trust_engine"] = True
        except Exception as e:
            self.initialized_engines["sensor_trust_engine"] = False
            self.initialization_errors.append(f"sensor_trust_engine failed to initialize: {e}")

        # Interpretation Engine
        try:
            self.interpretation_engine = ScientificInterpreter()
            self.initialized_engines["interpretation_engine"] = True
        except Exception as e:
            self.initialized_engines["interpretation_engine"] = False
            self.initialization_errors.append(f"interpretation_engine failed to initialize: {e}")

        # Intelligent Alert Engine
        try:
            self.alert_engine = IntelligentAlertEngine(config=alert_config)
            self.initialized_engines["alert_engine"] = True
        except Exception as e:
            self.initialized_engines["alert_engine"] = False
            self.initialization_errors.append(f"alert_engine failed to initialize: {e}")

    # =========================================================================
    # Public Gateway Methods
    # =========================================================================

    def process(
        self,
        data: Any,
        source_type: str,
        metadata: Optional[Dict[str, Any]] = None,
        subject_id: Optional[str] = None,
        is_synthetic: Optional[bool] = None,
        accel_data: Optional[Any] = None,
        **kwargs: Any,
    ) -> ProcessingResult:
        """
        Process incoming health or telemetry data through the appropriate pipeline.

        Parameters
        ----------
        data : DataFrame, dict, list of dicts, or file path
            Incoming dataset payload.
        source_type : str
            Source identifier: 'NASA_LAB' or 'SYNTHETIC_WEARABLE'.
        subject_id : str, optional
            Astronaut or subject identifier.
        is_synthetic : bool, optional
            Explicit provenance flag.
        accel_data : DataFrame, optional
            Concurrent accelerometer data for wearable motion artifact rejection.

        Returns
        -------
        ProcessingResult
            Unified, typed, and structured analytical result.
        """
        start_t = time.perf_counter()
        self.current_processing_state = "PROCESSING"
        request_metadata = dict(metadata or {})
        subject_id = subject_id or request_metadata.get("astronaut_id") or request_metadata.get("subject_id")
        if is_synthetic is None and "is_synthetic" in request_metadata:
            is_synthetic = request_metadata["is_synthetic"]
        if accel_data is None:
            accel_data = request_metadata.get("accel_data")
        request_metadata.pop("accel_data", None)

        try:
            st = validate_source_type(source_type)
            # 1. If data is string/path, load through DataManager
            if isinstance(data, (str, Path)):
                data = self.data_manager.load_dataset(data)
            if isinstance(accel_data, (str, Path)):
                accel_data = self.data_manager.load_dataset(accel_data)

            # Validate at the gateway as well as within each pipeline, so all public
            # entry paths reject incompatible payloads before analytical work begins.
            data = self.validate_input(data, st.value, is_synthetic=is_synthetic)
            request_metadata["source_type"] = st.value
            request_metadata["input_kind"] = type(data).__name__

            # 3. Route to dedicated pipeline
            if st == SourceType.NASA_LAB:
                result = self.nasa_pipeline.execute(
                    data=data,
                    subject_id=subject_id,
                    is_synthetic=is_synthetic,
                    metadata=request_metadata,
                    **kwargs,
                )
            elif st == SourceType.SYNTHETIC_WEARABLE:
                result = self.synthetic_pipeline.execute(
                    data=data,
                    subject_id=subject_id,
                    is_synthetic=is_synthetic,
                    accel_data=accel_data,
                    metadata=request_metadata,
                    **kwargs,
                )
            else:
                raise UnsupportedSourceError(f"Unsupported source type: {source_type}")

            self.last_processing_timestamp = datetime.now(timezone.utc).isoformat()
            try:
                self.storage.save_result(result)
            except Exception as storage_error:
                message = f"SQLite persistence failed: {storage_error}"
                logger.exception(message)
                result.errors.append(message)
                result.warnings.append("Analysis completed in memory but could not be saved to local history.")
            return result

        except Exception as e:
            total_dur = time.perf_counter() - start_t
            logger.error("Processing error encountered: %s", e, exc_info=True)
            self.last_processing_timestamp = datetime.now(timezone.utc).isoformat()

            # If validation error, we re-raise or return FAILED result
            # For public API safety, if it's a known ValidationError/DataRoutingError, re-raise so callers can catch
            if isinstance(e, (ValidationError, DataRoutingError, SchemaMismatchError, ProvenanceViolationError, UnsupportedSourceError)):
                raise

            # Unhandled runtime exception -> return explicit FAILED result (NEVER NORMAL!)
            failure_result = self.result_manager.create_failure_result(
                source_type=str(source_type),
                error_message=str(e),
                subject_id=subject_id,
                is_synthetic=(
                    True if str(source_type).strip().upper() == SourceType.SYNTHETIC_WEARABLE.value
                    else bool(is_synthetic)
                ),
                execution_metrics={"total_pipeline_seconds": total_dur},
                metadata=request_metadata,
            )
            try:
                self.storage.save_result(failure_result)
            except Exception as storage_error:
                logger.exception("Could not persist processing failure result: %s", storage_error)
                failure_result.errors.append(f"SQLite persistence failed: {storage_error}")
            return failure_result
        finally:
            self.current_processing_state = "IDLE"

    def validate_input(
        self,
        data: Any,
        source_type: str,
        is_synthetic: Optional[bool] = None,
    ) -> pd.DataFrame:
        """Validate and normalize input against exactly one source-specific schema."""
        source = validate_source_type(source_type)
        if source == SourceType.NASA_LAB:
            return validate_nasa_lab_data(data, is_synthetic=is_synthetic)
        if source == SourceType.SYNTHETIC_WEARABLE:
            return validate_synthetic_wearable_data(data, is_synthetic=is_synthetic)
        raise UnsupportedSourceError(f"Unsupported source type: {source_type}")

    def get_system_status(self) -> SystemStatus:
        """
        Query system availability, engine states, and configuration metadata.
        """
        all_init = all(self.initialized_engines.values())
        any_init = any(self.initialized_engines.values())

        if all_init and not self.initialization_errors:
            status = SystemOperationalState.READY.value
        elif any_init:
            status = SystemOperationalState.DEGRADED.value
        else:
            status = SystemOperationalState.ERROR.value

        engine_avail = {k: "AVAILABLE" if v else "UNAVAILABLE" for k, v in self.initialized_engines.items()}
        model_avail = {
            "robust_statistics": "AVAILABLE",
            "bayesian_student_t": "AVAILABLE",
            "isolation_forest": "AVAILABLE",
            "hampel_filter": "AVAILABLE",
        }

        config_summary = {
            "offline_mode": True,
            "persistence_layer": "SQLite (local offline database)",
            "supported_nasa_panels": ["CMP", "Cardiovascular EvePanel", "Immune EvePanel", "Immune AlamarPanel"],
            "supported_sensors": ["heart_rate", "spo2", "accelerometer"],
        }

        return SystemStatus(
            system="WEDJAT-X",
            system_version="1.0",
            status=status,
            initialized_engines=self.initialized_engines,
            engine_availability=engine_avail,
            model_availability=model_avail,
            configuration_summary=config_summary,
            supported_data_sources=[SourceType.NASA_LAB.value, SourceType.SYNTHETIC_WEARABLE.value],
            backend_version=self.backend_version,
            last_processing_timestamp=self.last_processing_timestamp,
            current_processing_state=self.current_processing_state,
            initialization_errors=self.initialization_errors,
            disclaimer=NON_CLINICAL_DISCLAIMER,
        )

    def get_analysis_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.storage.history(limit)

    def get_recent_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.storage.recent_alerts(limit)

    def get_latest_analysis(self) -> Optional[Dict[str, Any]]:
        return self.storage.latest()

    # =========================================================================
    # Batch Processing Support
    # =========================================================================

    def process_batch(
        self,
        items: List[Any],
        source_type: str,
        subject_ids: Optional[List[str]] = None,
        is_synthetic: Optional[bool] = None,
        export_dir: Optional[Union[str, Path]] = None,
        **kwargs: Any,
    ) -> List[ProcessingResult]:
        """
        Process multiple records or files sequentially without data leakage.

        Parameters
        ----------
        items : list
            List of datasets, records, or file paths.
        source_type : str
            'NASA_LAB' or 'SYNTHETIC_WEARABLE'.
        subject_ids : list of str, optional
            List of subject identifiers aligned with items.
        is_synthetic : bool, optional
            Provenance flag.
        export_dir : str or Path, optional
            Optional directory where results will be exported as JSON files.

        Returns
        -------
        List[ProcessingResult]
            List of structured results.
        """
        results: List[ProcessingResult] = []
        for i, item in enumerate(items):
            sub_id = subject_ids[i] if subject_ids and i < len(subject_ids) else None
            try:
                res = self.process(
                    data=item,
                    source_type=source_type,
                    subject_id=sub_id,
                    is_synthetic=is_synthetic,
                    **kwargs,
                )
                results.append(res)
            except Exception as e:
                logger.error("Batch processing failed on item %d: %s", i, e)
                fail_res = self.result_manager.create_failure_result(
                    source_type=source_type,
                    error_message=f"Batch item {i} failed: {e}",
                    subject_id=sub_id,
                    is_synthetic=bool(is_synthetic),
                )
                results.append(fail_res)

        if export_dir is not None:
            self.data_manager.save_batch_results(results, output_dir=export_dir)

        return results

    def process_all_nasa_participants(
        self,
        master_dataset_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, ProcessingResult]:
        """
        Convenience batch executor for all 4 NASA Inspiration4 crew members (C001..C004).
        """
        path = master_dataset_path or (self.base_dir / "cleaned_data" / "WEDJAT_X_Master_Biomarker_Dataset.csv")
        df = self.data_manager.load_dataset(path)
        participants = sorted(df["Participant_ID"].dropna().unique().tolist())

        crew_results: Dict[str, ProcessingResult] = {}
        for p in participants:
            res = self.process(
                data=df,
                source_type=SourceType.NASA_LAB.value,
                subject_id=p,
                is_synthetic=False,
            )
            crew_results[p] = res

        return crew_results
