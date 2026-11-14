/**
 * WEDJAT-X API Client
 * Provides robust HTTP communication with the Python FastAPI backend,
 * complete with structured error handling, provenance metadata, and offline resilience.
 */

import {
  SystemStatusData,
  CrewMember,
  BiomarkerCatalog,
  DiscreteBiomarkerRecord,
  BaselineInfo,
  SyntheticScenarioSummary,
  SyntheticTelemetryRecord,
  ProcessingResultData,
  AlertEvidence,
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorBody.detail || errorBody.message || `API error ${res.status}`);
  }
  return res.json();
}

export const api = {
  async getMetrics(signal?: AbortSignal): Promise<{ analysis_count: number; active_alert_count: number; alert_record_count: number; latest_sensor_trust: unknown }> {
    const res = await fetch(`${API_BASE}/api/metrics`, { signal });
    return handleResponse(res);
  },
  async getHealth(): Promise<{ status: string; system: string; backend_version: string }> {
    const res = await fetch(`${API_BASE}/api/health`);
    return handleResponse(res);
  },

  async getSystemStatus(signal?: AbortSignal): Promise<SystemStatusData> {
    const res = await fetch(`${API_BASE}/api/system/status`, { signal });
    return handleResponse(res);
  },

  async getCrewParticipants(signal?: AbortSignal): Promise<CrewMember[]> {
    const res = await fetch(`${API_BASE}/api/nasa/participants`, { signal });
    return handleResponse(res);
  },

  async getBiomarkers(participantId?: string, panelName?: string, signal?: AbortSignal): Promise<BiomarkerCatalog> {
    const params = new URLSearchParams();
    if (participantId) params.append('participant_id', participantId);
    if (panelName) params.append('panel_name', panelName);
    const res = await fetch(`${API_BASE}/api/nasa/biomarkers?${params.toString()}`, { signal });
    return handleResponse(res);
  },

  async getParticipantData(
    participantId: string,
    biomarkerName?: string,
    panelName?: string,
    signal?: AbortSignal
  ): Promise<{
    participant_id: string;
    biomarker_name?: string;
    record_count: number;
    baseline_info?: BaselineInfo;
    records: DiscreteBiomarkerRecord[];
  }> {
    const params = new URLSearchParams({ participant_id: participantId });
    if (biomarkerName) params.append('biomarker_name', biomarkerName);
    if (panelName) params.append('panel_name', panelName);
    const res = await fetch(`${API_BASE}/api/nasa/participant-data?${params.toString()}`, { signal });
    return handleResponse(res);
  },

  async getScenarios(signal?: AbortSignal): Promise<SyntheticScenarioSummary[]> {
    const res = await fetch(`${API_BASE}/api/scenarios`, { signal });
    return handleResponse(res);
  },

  async getScenarioData(name: string, signal?: AbortSignal): Promise<{
    filename: string;
    total_samples: number;
    is_synthetic: boolean;
    records: SyntheticTelemetryRecord[];
  }> {
    const res = await fetch(`${API_BASE}/api/scenarios/${encodeURIComponent(name)}`, { signal });
    return handleResponse(res);
  },

  async runNasaAnalysis(participantId: string): Promise<ProcessingResultData> {
    const res = await fetch(`${API_BASE}/api/analysis/nasa`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ participant_id: participantId }),
    });
    return handleResponse(res);
  },

  async runWearableAnalysis(scenarioName: string, subjectId = 'SYNTHETIC_ASTRONAUT'): Promise<ProcessingResultData> {
    const res = await fetch(`${API_BASE}/api/analysis/wearable`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_name: scenarioName, subject_id: subjectId }),
    });
    return handleResponse(res);
  },

  async getRecentAlerts(limit = 50, sourceType?: string, state?: string, signal?: AbortSignal): Promise<AlertEvidence[]> {
    const params = new URLSearchParams({ limit: limit.toString() });
    if (sourceType) params.append('source_type', sourceType);
    if (state) params.append('state', state);
    const res = await fetch(`${API_BASE}/api/alerts?${params.toString()}`, { signal });
    return handleResponse(res);
  },

  async getAlertDetail(alertId: string, signal?: AbortSignal): Promise<{ request_id: string; alert: AlertEvidence & Record<string, any>; analysis: ProcessingResultData }> {
    const res = await fetch(`${API_BASE}/api/alerts/${encodeURIComponent(alertId)}`, { signal });
    return handleResponse(res);
  },

  async getHistory(limit = 50, sourceType?: string, signal?: AbortSignal): Promise<ProcessingResultData[]> {
    const params = new URLSearchParams({ limit: limit.toString() });
    params.append('summary', 'true');
    if (sourceType) params.append('source_type', sourceType);
    const res = await fetch(`${API_BASE}/api/history?${params.toString()}`, { signal });
    return handleResponse(res);
  },

  async getLatestAnalysis(signal?: AbortSignal, sourceType?: string): Promise<ProcessingResultData | null> {
    const params = new URLSearchParams();
    if (sourceType) params.set('source_type', sourceType);
    const suffix = params.size ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/api/analysis/latest${suffix}`, { signal });
    return handleResponse(res);
  },
};
