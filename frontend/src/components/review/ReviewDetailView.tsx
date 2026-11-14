import React, { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, ChevronDown, FileText, History, RefreshCw, ShieldAlert } from 'lucide-react';
import { api } from '../../services/api';
import { AlertEvidence, ProcessingResultData } from '../../types';
import { StatusBadge } from '../common/StatusBadge';

interface ReviewDetail {
  request_id: string;
  alert: AlertEvidence & Record<string, any>;
  analysis: (ProcessingResultData & Record<string, any>) | null;
}

const display = (value: unknown) => value === null || value === undefined || value === '' ? 'Unavailable' : String(value);
const JsonEvidence: React.FC<{ title: string; value: unknown }> = ({ title, value }) => (
  <details className="rounded-lg border border-slate-800 bg-space-950/70 p-3">
    <summary className="cursor-pointer text-xs font-mono text-cyan-200">{title}<ChevronDown className="inline ml-2 h-3 w-3" /></summary>
    <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-words text-[11px] text-slate-300">{value == null ? 'INSUFFICIENT EVIDENCE' : JSON.stringify(value, null, 2)}</pre>
  </details>
);

export const ReviewDetailView: React.FC<{ alertId: string; onBack: () => void }> = ({ alertId, onBack }) => {
  const [detail, setDetail] = useState<ReviewDetail | null>(null);
  const [error, setError] = useState<'not-found' | 'connection' | null>(null);
  const [history, setHistory] = useState<any[] | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [showAnalysis, setShowAnalysis] = useState(false);
  const [showAudit, setShowAudit] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    api.getAlertDetail(alertId, controller.signal)
      .then((result) => { if (!controller.signal.aborted) setDetail(result); })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return;
        const message = cause instanceof Error ? cause.message : String(cause);
        setError(/404|not found/i.test(message) ? 'not-found' : 'connection');
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [alertId]);

  const alert = detail?.alert;
  const result = detail?.analysis;
  const nasa = alert?.source_type === 'NASA_LAB' || (alert && !alert.is_synthetic);
  const measurements = result?.measurements || [];
  const current = alert?.measurement_value;
  const baseline = alert?.baseline_context?.median ?? alert?.statistical_evidence?.baseline_median;
  const difference = typeof current === 'number' && typeof baseline === 'number' ? current - baseline : null;
  const percentDifference = difference !== null && baseline !== 0 ? (difference / Math.abs(baseline)) * 100 : null;
  const trust = result?.sensor_trust?.sensors || result?.sensor_trust || {};
  const contributing = alert?.contributing_engines || [];
  const impact = useMemo(() => {
    if (alert?.is_synthetic && result?.data_quality?.quality_score === 0) return 'DATA QUALITY CONCERN';
    if (typeof current !== 'number' || typeof baseline !== 'number') return 'INSUFFICIENT EVIDENCE';
    if (alert?.alert_state === 'NORMAL') return 'NO SIGNIFICANT DEVIATION DETECTED';
    return difference! > 0 ? 'ELEVATED RELATIVE TO BASELINE' : difference! < 0 ? 'DECREASED RELATIVE TO BASELINE' : 'NO SIGNIFICANT DEVIATION DETECTED';
  }, [alert, result, current, baseline, difference]);

  const loadBiomarkerHistory = async () => {
    if (!alert || !nasa) { setHistoryError('Biomarker history is only available for NASA laboratory cases.'); return; }
    const participant = alert.subject_id || result?.subject_id || result?.astronaut_id;
    if (!participant || !alert.measurement_name) { setHistoryError('INSUFFICIENT EVIDENCE: participant or biomarker identifier is missing.'); return; }
    try {
      const response = await api.getParticipantData(participant, alert.measurement_name);
      setHistory(response.records || []);
      setHistoryError(null);
    } catch (cause) { setHistoryError(cause instanceof Error ? cause.message : String(cause)); }
  };

  if (loading) return <main className="m-6 rounded-xl border border-cyan-500/20 bg-space-900 p-8 text-cyan-200">Loading stored alert evidence…</main>;
  if (error || !detail) return <main className="m-6 space-y-5 rounded-xl border border-rose-500/30 bg-space-900 p-8"><h1 className="text-xl font-mono text-rose-300">{error === 'not-found' ? 'ALERT NOT FOUND' : 'CONNECTION ERROR'}</h1><p className="text-sm text-slate-300">{error === 'not-found' ? `No stored alert exists for ${alertId}.` : 'Could not retrieve this alert and its associated analysis.'}</p><button onClick={onBack} className="rounded border border-cyan-500/40 px-4 py-2 text-sm text-cyan-200"><ArrowLeft className="mr-2 inline h-4 w-4"/>Back to Alert Center</button></main>;
  if (!detail.analysis) return <main className="m-6 space-y-5 rounded-xl border border-amber-500/30 bg-space-900 p-8"><h1 className="text-xl font-mono text-amber-200">INSUFFICIENT EVIDENCE</h1><p className="text-sm text-slate-300">This stored alert has no associated analysis result.</p><button onClick={onBack} className="rounded border border-cyan-500/40 px-4 py-2 text-sm text-cyan-200"><ArrowLeft className="mr-2 inline h-4 w-4"/>Back to Alert Center</button></main>;

  const sourceLabel = nasa ? 'NASA LABORATORY · OSD-575' : 'SYNTHETIC SIMULATION · WEARABLE TEST DATA';
  return <main className="space-y-5 p-4 lg:p-6">
    <div className="flex flex-wrap items-center justify-between gap-3"><button onClick={onBack} className="rounded border border-cyan-500/30 bg-space-900 px-3 py-2 text-xs font-mono text-cyan-200"><ArrowLeft className="mr-2 inline h-4 w-4"/>Back to Alert Center</button><span className={`rounded border px-3 py-1 text-[10px] font-mono ${nasa ? 'border-cyan-500/40 text-cyan-200' : 'border-amber-500/50 text-amber-200'}`}>{sourceLabel}</span></div>
    <section className="rounded-xl border border-cyan-500/25 bg-space-900/90 p-5">
      <div className="flex items-start justify-between gap-4"><div><p className="text-[10px] font-mono tracking-widest text-cyan-400">MEDICAL DECISION SUPPORT · CASE REVIEW</p><h1 className="mt-1 text-xl font-bold text-slate-100">{alert.biomarker_or_sensor || alert.measurement_name || 'Alert review'}</h1></div><StatusBadge status={alert.alert_state} size="md"/></div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{[['Astronaut / Subject ID', alert.subject_id || result?.astronaut_id || result?.subject_id], ['Alert ID', alert.alert_id], ['Timestamp', alert.timestamp], ['Lifecycle state', alert.lifecycle_status || alert.alert_state], ['Source type', alert.source_type], ['Review reason', alert.explanation], ['Processing status', result?.processing_status], ['Analysis request', detail.request_id]].map(([label, value])=><div key={label} className="rounded bg-space-950 p-3"><div className="text-[10px] uppercase text-slate-500">{label}</div><div className="mt-1 break-words text-xs text-slate-200">{display(value)}</div></div>)}</div>
      {!nasa && <div className="mt-4 rounded border border-amber-500/40 bg-amber-950/30 p-3 text-xs font-mono text-amber-200">SYNTHETIC SIMULATION — not astronaut or clinical telemetry.</div>}
    </section>

    <section className="rounded-xl border border-cyan-500/20 bg-space-900/80 p-5"><h2 className="font-mono text-sm font-bold tracking-wider text-cyan-200">{nasa ? 'BIOMARKER EVIDENCE' : 'WEARABLE EVIDENCE'}</h2>
      {nasa ? <><div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{[['Measured value', current, alert.measurement_unit], ['Baseline', baseline, alert.measurement_unit], ['Absolute difference', difference === null ? null : Math.abs(difference), alert.measurement_unit], ['Difference from baseline', percentDifference === null ? null : `${percentDifference.toFixed(2)}%`], ['Mission milestone', alert.current_timepoint || alert.timepoint], ['Missing data', alert.data_quality_status || (current == null ? 'Measurement unavailable' : 'No missing value flagged')]].map(([label,value,unit])=><div key={String(label)} className="rounded bg-space-950 p-3"><div className="text-[10px] text-slate-500">{label}</div><div className="mt-1 text-sm text-slate-100">{display(value)} {unit ? String(unit) : ''}</div></div>)}</div>
      <div className="mt-4 grid gap-3 md:grid-cols-2"><JsonEvidence title="Statistical anomaly evidence" value={alert.statistical_evidence}/><JsonEvidence title="Bayesian evidence" value={alert.bayesian_evidence}/><JsonEvidence title="Longitudinal trajectory" value={result?.trajectory_summary}/><JsonEvidence title="Available previous measurements" value={measurements.filter((m:any)=>m.biomarker_name===alert.measurement_name || m.Biomarker_Name===alert.measurement_name)}/></div></>
      : <><div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{[['Heart rate', measurements.find((m:any)=>m.sensor_type==='heart_rate')?.signal_value, 'BPM'], ['SpO2', measurements.find((m:any)=>m.sensor_type==='spo2')?.signal_value, '%'], ['Activity', measurements.find((m:any)=>m.sensor_type==='activity')?.signal_value, ''], ['Sensor trust', Object.values(trust)[0]?.quality_score, '/100'], ['Processing state', result?.processing_status, ''], ['Synthetic provenance', result?.is_synthetic === true ? 'CONFIRMED' : null, '']].map(([label,value,unit])=><div key={String(label)} className="rounded bg-space-950 p-3"><div className="text-[10px] text-slate-500">{label}</div><div className="mt-1 text-sm text-slate-100">{display(value)} {unit ? String(unit) : ''}</div></div>)}</div><div className="mt-4 grid gap-3 md:grid-cols-2"><JsonEvidence title="Sensor quality, noise, missingness and continuity" value={trust}/><JsonEvidence title="Motion artifact evidence" value={alert.motion_artifact_evidence}/><JsonEvidence title="Statistical anomaly evidence" value={alert.statistical_evidence}/><JsonEvidence title="Bayesian evidence" value={alert.bayesian_evidence}/></div></>}
    </section>

    <section className="rounded-xl border border-amber-500/30 bg-space-900/90 p-5"><h2 className="flex items-center gap-2 font-mono text-sm font-bold tracking-wider text-amber-200"><ShieldAlert className="h-4 w-4"/>POTENTIAL HEALTH SIGNIFICANCE</h2><p className="mt-3 text-sm font-semibold text-amber-100">{impact}</p><p className="mt-2 text-xs leading-relaxed text-slate-300">Direction relative to baseline is descriptive only. Persistence: {typeof alert.consecutive_occurrences === 'number' && alert.consecutive_occurrences > 1 ? `repeated across ${alert.consecutive_occurrences} occurrences` : 'one observation; persistence cannot be established'}. Independent indicators: {contributing.length ? contributing.join(', ') : 'not available'}. Data quality: {Object.keys(trust).length ? 'trust evidence available; inspect details' : 'evidence unavailable or incomplete'}.</p><p className="mt-3 text-xs text-slate-400">A mathematical deviation is not a diagnosis. No clinical impact is asserted without validated clinical reference ranges and qualified medical interpretation.</p></section>

    <section className="rounded-xl border border-cyan-500/20 bg-space-900/80 p-5"><h2 className="font-mono text-sm font-bold text-cyan-200">WHY DID THE SYSTEM FLAG THIS CASE?</h2><p className="mt-2 text-sm text-slate-300">{display(alert.explanation)}</p><div className="mt-3 grid gap-3 md:grid-cols-2"><JsonEvidence title="Statistical engine result" value={alert.statistical_evidence}/><JsonEvidence title="Bayesian engine result" value={alert.bayesian_evidence}/><JsonEvidence title="Sensor trust result" value={alert.sensor_quality_evidence || (nasa ? null : trust)}/><JsonEvidence title="Motion artifact cross-check" value={alert.motion_artifact_evidence}/><JsonEvidence title="Alert fusion decision" value={{state:alert.alert_state,priority:alert.alert_priority,engines:contributing}}/><JsonEvidence title="Exact REVIEW reason" value={alert.explanation}/></div></section>

    <section className="rounded-xl border border-emerald-500/20 bg-space-900/80 p-5"><h2 className="font-mono text-sm font-bold text-emerald-200">RECOMMENDED HUMAN REVIEW</h2><ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-slate-300"><li>Review the underlying measurements and their source.</li><li>Verify data quality and check missing measurements.</li><li>Compare observations with this individual's baseline.</li><li>Review related statistical, Bayesian, trajectory, and sensor evidence.</li><li>Refer the case to qualified medical personnel; no autonomous decision or treatment is provided.</li></ul></section>

    <section className="flex flex-wrap gap-2"><button onClick={()=>setShowAnalysis(!showAnalysis)} className="rounded border border-cyan-500/40 px-3 py-2 text-xs text-cyan-200"><FileText className="mr-1 inline h-4 w-4"/>View complete analysis</button><button onClick={loadBiomarkerHistory} disabled={!nasa} className="rounded border border-cyan-500/40 px-3 py-2 text-xs text-cyan-200 disabled:opacity-40"><History className="mr-1 inline h-4 w-4"/>View biomarker history</button><button onClick={()=>setShowAudit(!showAudit)} className="rounded border border-slate-600 px-3 py-2 text-xs text-slate-200">View audit information</button></section>
    {historyError && <p className="text-xs text-amber-200">{historyError}</p>}{history !== null && <section className="rounded-xl border border-slate-700 bg-space-900 p-4">{history.length === 0 ? <p className="text-xs text-slate-400">No previous biomarker measurements are available.</p> : history.map((item,i)=><div key={i} className="border-b border-slate-800 py-2 text-xs text-slate-200">{display(item.Timepoint)} · {display(item.Measurement_Value)} {display(item.Measurement_Unit)}</div>)}</section>}{showAnalysis && <section className="rounded-xl border border-slate-700 bg-space-900 p-4"><h3 className="mb-2 font-mono text-xs text-cyan-200">COMPLETE STORED ANALYSIS</h3><pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words text-xs text-slate-300">{JSON.stringify(result,null,2)}</pre></section>}{showAudit && <JsonEvidence title="Stored audit metadata" value={{request_id:detail.request_id,timestamp:result.timestamp,source_type:result.source_type,processing_status:result.processing_status,audit_metadata:result.audit_metadata}}/>}
  </main>;
};
