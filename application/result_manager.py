"""
WEDJAT-X Phase 7 — Unified Result Manager
Constructs, sanitizes, and formats structured ProcessingResult objects.

Regulatory Safety Rule:
WEDJAT-X reports are medical decision-support documents for flight surgeons
and mission controllers. They must never formulate medical diagnoses or
countermeasure prescriptions.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid
import numpy as np
import pandas as pd

from application.schemas import (
    NON_CLINICAL_DISCLAIMER,
    ProcessingResult,
    ProcessingStatus,
    SourceType,
    json_safe,
)

logger = logging.getLogger("WEDJAT_X.ResultManager")


class ResultManager:
    """
    Standardized Result Construction and Reporting Engine.
    """

    def __init__(self, system_name: str = "WEDJAT-X", system_version: str = "1.0") -> None:
        self.system_name = system_name
        self.system_version = system_version

    def create_result(
        self,
        source_type: str,
        subject_id: Optional[str] = None,
        is_synthetic: bool = False,
        processing_status: str = ProcessingStatus.SUCCESS.value,
        measurements: Optional[List[Dict[str, Any]]] = None,
        baseline_analysis: Optional[Dict[str, Any]] = None,
        anomaly_analysis: Optional[Dict[str, Any]] = None,
        bayesian_analysis: Optional[Dict[str, Any]] = None,
        isolation_forest_analysis: Optional[Dict[str, Any]] = None,
        trajectory_analysis: Optional[Dict[str, Any]] = None,
        sensor_trust_analysis: Optional[Dict[str, Any]] = None,
        alert_summary: Optional[Dict[str, Any]] = None,
        ground_medical_report: Optional[Dict[str, Any]] = None,
        astronaut_summary: Optional[Dict[str, Any]] = None,
        data_quality: Optional[Dict[str, Any]] = None,
        limitations: Optional[List[str]] = None,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        execution_metrics: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        data_summary: Optional[Dict[str, Any]] = None,
        interpretation: Optional[Dict[str, Any]] = None,
        confidence_or_evidence_summary: Optional[Dict[str, Any]] = None,
    ) -> ProcessingResult:
        """
        Build a typed, standardized ProcessingResult conforming strictly to Phase 7 Part 4.
        """
        proc_id = f"PRC-{uuid.uuid4().hex[:8].upper()}"
        ts_now = datetime.now(timezone.utc).isoformat()

        # Build baseline limitations list
        standard_limitations = [
            "Research decision-support prototype; not clinically validated or certified by FDA/ESA/NASA.",
            "All findings require verification by certified aerospace medical personnel (flight surgeons).",
        ]
        if source_type == SourceType.NASA_LAB.value or not is_synthetic:
            standard_limitations.extend([
                "Dataset reflects Inspiration4 discrete laboratory biospecimens (N=4); statistical power is limited.",
                "Measurements are retrospective wet-lab assays, not continuous wearable real-time telemetry.",
            ])
        else:
            standard_limitations.extend([
                "Telemetry stream consists of SYNTHETIC software test signals generated for algorithmic evaluation.",
                "Synthetic signals do not represent real human physiological dynamics under microgravity.",
            ])

        all_limitations = standard_limitations + (limitations or [])

        # Default reports if not supplied
        g_report = ground_medical_report or self._build_default_ground_report(
            source_type=source_type,
            subject_id=subject_id,
            alert_summary=alert_summary,
            trajectory_analysis=trajectory_analysis,
        )

        a_report = astronaut_summary or self._build_default_astronaut_summary(
            subject_id=subject_id,
            alert_summary=alert_summary,
        )

        result = ProcessingResult(
            system=self.system_name,
            system_version=self.system_version,
            processing_id=proc_id,
            request_id=proc_id,
            timestamp=ts_now,
            source_type=source_type,
            subject_id=subject_id,
            astronaut_id=subject_id,
            processing_status=processing_status,
            measurements=measurements or [],
            baseline_analysis=baseline_analysis or {},
            anomaly_analysis=anomaly_analysis or {},
            bayesian_analysis=bayesian_analysis or {},
            isolation_forest_analysis=isolation_forest_analysis or {},
            trajectory_analysis=trajectory_analysis or {},
            sensor_trust_analysis=sensor_trust_analysis or {},
            alert_summary=alert_summary or {},
            ground_medical_report=g_report,
            astronaut_summary=a_report,
            data_quality=data_quality or {},
            limitations=all_limitations,
            is_synthetic=is_synthetic,
            disclaimer=NON_CLINICAL_DISCLAIMER,
            errors=errors or [],
            warnings=warnings or [],
            execution_metrics=execution_metrics or {},
            data_summary=data_summary or data_quality or {},
            baseline_summary=baseline_analysis or {},
            anomaly_evidence={
                "statistical": anomaly_analysis or {},
                "bayesian": bayesian_analysis or {},
                "isolation_forest": isolation_forest_analysis or {},
            },
            sensor_trust=sensor_trust_analysis or None,
            trajectory_summary=trajectory_analysis or None,
            interpretation=interpretation or {},
            alert=alert_summary or {},
            confidence_or_evidence_summary=confidence_or_evidence_summary or {},
            audit_metadata=json_safe(metadata or {}),
        )
        return result

    def create_failure_result(
        self,
        source_type: str,
        error_message: str,
        subject_id: Optional[str] = None,
        is_synthetic: bool = False,
        errors: Optional[List[str]] = None,
        execution_metrics: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProcessingResult:
        """
        Build an explicit failure ProcessingResult.
        CRITICAL: Never report NORMAL when processing fails!
        """
        all_errors = [error_message] + (errors or [])
        return self.create_result(
            source_type=source_type,
            subject_id=subject_id,
            is_synthetic=is_synthetic,
            processing_status=ProcessingStatus.PROCESSING_ERROR.value,
            alert_summary={
                "highest_operational_state": "SYSTEM_PROCESSING_FAILED",
                "highest_priority": "NONE",
                "active_alert_count": 0,
                "operational_guidance": "Processing aborted due to unrecoverable backend error.",
            },
            ground_medical_report={
                "status": "PROCESSING_ERROR",
                "error_details": all_errors,
            },
            astronaut_summary={
                "headline": "System Status Notice",
                "message": "Telemetry or assay processing was interrupted. Engineering support notified.",
            },
            errors=all_errors,
            execution_metrics=execution_metrics or {},
            metadata=metadata,
        )

    @staticmethod
    def summarize_batch(results: List[ProcessingResult]) -> Dict[str, Any]:
        """Summarize status and source counts without collapsing individual errors."""
        statuses: Dict[str, int] = {}
        sources: Dict[str, int] = {}
        for result in results:
            statuses[result.processing_status] = statuses.get(result.processing_status, 0) + 1
            sources[result.source_type] = sources.get(result.source_type, 0) + 1
        return {
            "total": len(results),
            "statuses": statuses,
            "sources": sources,
            "error_count": sum(len(result.errors) for result in results),
            "warning_count": sum(len(result.warnings) for result in results),
        }

    def _build_default_ground_report(
        self,
        source_type: str,
        subject_id: Optional[str],
        alert_summary: Optional[Dict[str, Any]],
        trajectory_analysis: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate flight surgeon level technical report."""
        summary = alert_summary or {}
        high_state = summary.get("highest_operational_state", "INSUFFICIENT_DATA")
        active_count = summary.get("active_alert_count", 0)

        clinical_summary = (
            f"Automated multi-engine evaluation completed for subject '{subject_id or 'Unknown'}'. "
            f"Highest operational alert state: {high_state}. Active monitored deviations: {active_count}. "
            "Refer to individual biomarker and trajectory panels for statistical dispersion and Bayesian evidence."
        )

        return {
            "subject_id": subject_id,
            "overall_status": high_state,
            "executive_summary": clinical_summary,
            "active_alert_count": active_count,
            "trajectory_overview": trajectory_analysis.get("summary") if trajectory_analysis else None,
            "recommended_clinical_actions": [
                "Verify sensor placement and optical contact if wearable stream.",
                "Review longitudinal recovery trends before scheduling intervention.",
                "Correlate marked laboratory deviations with mission timeline events.",
            ],
            "disclaimer": NON_CLINICAL_DISCLAIMER,
        }

    def _build_default_astronaut_summary(
        self,
        subject_id: Optional[str],
        alert_summary: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate astronaut-facing calm, non-alarming operational summary."""
        summary = alert_summary or {}
        high_state = summary.get("highest_operational_state", "INSUFFICIENT_DATA")

        if high_state in ["ATTENTION", "REVIEW"]:
            headline = "Monitoring Notice: Routine Review"
            message = (
                "Ground medical support has received your latest telemetry and assay data. "
                "Minor physiological deviations consistent with mission phase adaptation were noted. "
                "No urgent operational action required at this time."
            )
            action = "Continue nominal mission flight plan and ensure wearable sensors remain firmly seated."
        elif high_state == "INSUFFICIENT_DATA":
            headline = "Sensor Check Notice"
            message = "Some readings were intermittently unrecorded or had degraded signal contact."
            action = "Please check sensor positioning, strap tension, and battery levels when convenient."
        elif high_state == "NORMAL":
            headline = "All Systems Nominal"
            message = "Physiological parameters and biomarker baselines are tracking stably within expected bounds."
            action = "No action required. Maintain nominal schedule."
        else:
            headline = "Processing Status Notice"
            message = "The available evidence does not support a normal-status summary. Human review remains authoritative."
            action = "Refer the processing status and evidence to the ground medical team."

        return {
            "headline": headline,
            "message": message,
            "recommended_action": action,
            "is_calm_tone": True,
        }
