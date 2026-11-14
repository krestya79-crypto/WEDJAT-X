/**
 * WEDJAT-X TypeScript Schema Definitions
 * Strict types matching backend ProcessingResult, NASA OSD-575 assays, and synthetic streams.
 */

export type SourceType = 'NASA_LAB' | 'SYNTHETIC_WEARABLE';

export type AlertState = 'NORMAL' | 'REVIEW' | 'ATTENTION' | 'INSUFFICIENT_DATA' | 'CRITICAL';

export type SystemStatusType = 'READY' | 'DEGRADED' | 'ERROR';

export type ReliabilityCategory = 'OPTIMAL' | 'ACCEPTABLE' | 'DEGRADED' | 'UNRELIABLE' | 'HIGH_RELIABILITY' | 'MODERATE_RELIABILITY' | 'LOW_RELIABILITY' | 'INSUFFICIENT_DATA';

export interface SystemStatusData {
  system: string;
  system_version: string;
  status: SystemStatusType;
  initialized_engines: Record<string, boolean>;
  engine_availability: Record<string, string>;
  model_availability: Record<string, string>;
  configuration_summary: Record<string, any>;
  supported_data_sources: string[];
  backend_version: string;
  last_processing_timestamp: string | null;
  current_processing_state: string;
  initialization_errors: string[];
  disclaimer: string;
  analysis_count?: number;
  active_alert_count?: number;
}

export interface CrewMember {
  participant_id: string;
  display_name: string;
  role: string;
  callsign: string;
  mission: string;
  total_observations: number;
  total_biomarkers: number;
  panels: string[];
  timepoints: string[];
}

export interface BiomarkerCatalog {
  participant_id?: string | null;
  total_biomarkers: number;
  panels: string[];
  timepoints: string[];
  by_panel: Record<string, string[]>;
  biomarkers: string[];
}

export interface DiscreteBiomarkerRecord {
  Participant_ID: string;
  Sample_ID: string;
  Timepoint: string;
  Timepoint_Phase: string;
  Days_Relative_To_Return: number;
  Timepoint_Order: number;
  Biomarker_Name: string;
  Original_Biomarker_Name?: string;
  Measurement_Value: number | null;
  Measurement_Unit: string;
  Normalized_Percent_Value?: number | null;
  Panel_Name: string;
  Platform_Technology?: string;
  Source_File?: string;
  Source_Type?: string;
  Validation_Status?: string;
  Clinical_Range_Min?: number | null;
  Clinical_Range_Max?: number | null;
  Clinical_Range_Flag?: string | null;
}

export interface BaselineInfo {
  biomarker_name: string;
  preflight_samples: number;
  baseline_median: number;
  baseline_mad: number;
  measurement_unit: string;
}

export interface SyntheticScenarioSummary {
  filename: string;
  scenario_name: string;
  description: string;
  total_samples: number;
  sensor_types: string[];
  missing_count: number;
  is_synthetic: boolean;
}

export interface SyntheticTelemetryRecord {
  timestamp: string;
  sensor_type: 'heart_rate' | 'spo2' | 'accelerometer' | string;
  signal_value: number | null;
  scenario?: string;
  signal_status?: string;
  is_synthetic: boolean;
}

export interface SensorTrustDetail {
  quality_score: number | null;
  reliability_category: ReliabilityCategory;
  missing_rate?: number;
  noise_metric?: number;
  sub_scores?: Record<string, number>;
  disconnection_rate?: number;
  spike_count?: number;
  timestamp_gaps?: number;
  drift_detected?: boolean;
  motion_artifact_fraction?: number;
  motion_overlap_pct?: number;
  timestamp_gap_count?: number;
  missing_sample_count?: number;
}

export interface AlertEvidence {
  alert_id?: string;
  alert_state: AlertState;
  operational_state?: AlertState;
  timestamp: string;
  source_type: SourceType;
  is_synthetic: boolean;
  biomarker_or_sensor: string;
  trigger_reason?: string;
  statistical_evidence?: {
    robust_z?: number;
    baseline_median?: number;
    measured_value?: number;
    mad?: number;
  };
  bayesian_evidence?: {
    anomaly_probability?: number;
    student_t_score?: number;
  };
  sensor_trust_context?: {
    quality_score?: number;
    reliability?: string;
    motion_downgrade?: boolean;
  };
  human_review_guidance?: string;
  explanation?: string;
}

export interface ProcessingResultData {
  request_id: string;
  processing_id?: string;
  timestamp: string;
  source_type: SourceType;
  subject_id?: string;
  astronaut_id?: string;
  is_synthetic: boolean;
  processing_status: string;
  disclaimer: string;
  measurements?: any[];
  baseline_summary?: Record<string, any>;
  anomaly_evidence?: {
    statistical?: Record<string, any>;
    bayesian?: Record<string, any>;
    isolation_forest?: Record<string, any>;
  };
  sensor_trust?: Record<string, SensorTrustDetail> | null;
  trajectory_summary?: Record<string, any> | null;
  alert?: {
    highest_operational_state?: AlertState;
    active_alert_count?: number;
    active_alerts?: AlertEvidence[];
  };
  ground_medical_report?: Record<string, any>;
  astronaut_summary?: Record<string, any>;
  warnings?: string[];
  errors?: string[];
}
