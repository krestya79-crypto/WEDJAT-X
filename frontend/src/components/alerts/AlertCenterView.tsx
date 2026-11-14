import React, { useState } from 'react';
import {
  Bell,
  AlertTriangle,
  ShieldAlert,
  CheckCircle2,
  Info,
  Filter,
  UserCheck,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { AlertEvidence, AlertState, SourceType } from '../../types';
import { StatusBadge } from '../common/StatusBadge';
import { MetricCard } from '../common/MetricCard';

interface AlertCenterViewProps {
  alerts: AlertEvidence[];
  onRefreshAlerts?: () => void;
  onOpenReview: (alertId: string) => void;
  showSyntheticFeatures?: boolean;
}

export const AlertCenterView: React.FC<AlertCenterViewProps> = ({
  alerts,
  onOpenReview,
  showSyntheticFeatures = true,
}) => {
  const [sourceFilter, setSourceFilter] = useState<string>('ALL');
  const [stateFilter, setStateFilter] = useState<string>('ALL');
  const [expandedAlertId, setExpandedAlertId] = useState<string | null>(null);

  const filteredAlerts = alerts.filter((a) => {
    if (sourceFilter === 'NASA_LAB' && a.is_synthetic) return false;
    if (sourceFilter === 'SYNTHETIC_WEARABLE' && !a.is_synthetic) return false;
    if (stateFilter !== 'ALL' && a.alert_state !== stateFilter) return false;
    return true;
  });

  const countAttention = alerts.filter((a) => a.alert_state === 'ATTENTION').length;
  const countReview = alerts.filter((a) => a.alert_state === 'REVIEW').length;
  const countNormal = alerts.filter((a) => a.alert_state === 'NORMAL').length;
  const countInsufficient = alerts.filter((a) => a.alert_state === 'INSUFFICIENT_DATA').length;

  return (
    <div className="space-y-6">
      {/* Flight Surgeon Advisory Notice */}
      <div className="p-4 rounded-xl bg-amber-950/40 border border-amber-500/40 shadow-[0_0_20px_rgba(245,158,11,0.15)] flex items-start gap-3">
        <ShieldAlert className="w-5 h-5 text-amber-400 mt-0.5 shrink-0" />
        <div className="text-xs text-slate-300 font-sans leading-relaxed">
          <strong className="text-amber-300 font-mono uppercase tracking-wider block mb-0.5">
            Aerospace Medical Mission Decision Support Console:
          </strong>
          Alert states reflect mathematical and statistical threshold deviations (Robust Z, Bayesian Student-t, Sensor Trust degradation).
          They represent operational triage priorities, <strong className="text-amber-200">never autonomous clinical diagnoses or treatment prescriptions</strong>.
          Authorized flight surgeon evaluation remains authoritative.
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard
          label="ATTENTION REQUIRED"
          value={countAttention}
          subtitle="Multi-engine statistical agreement"
          variant={countAttention > 0 ? 'alert' : 'normal'}
        />
        <MetricCard
          label="UNDER REVIEW"
          value={countReview}
          subtitle="Single-engine or motion-downgraded"
          variant="cyan"
        />
        <MetricCard
          label="NOMINAL OBSERVATIONS"
          value={countNormal}
          subtitle="Within personal baseline envelope"
          variant="normal"
        />
        <MetricCard
          label="INSUFFICIENT DATA"
          value={countInsufficient}
          subtitle="Sensor dropout or missing milestone"
          variant="slate"
        />
      </div>
      <p className="-mt-4 text-[10px] font-mono text-slate-500">These state totals summarize the {alerts.length} most recent records returned, not the lifetime SQLite alert event count.</p>

      {/* Filter Toolbar */}
      <div className="p-3.5 rounded-xl bg-space-900/80 border border-cyan-500/20 backdrop-blur-md flex flex-wrap items-center justify-between gap-3">
        {/* Source Filter */}
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-mono uppercase text-slate-400 mr-1">Source:</span>
          {(showSyntheticFeatures ? ['ALL', 'NASA_LAB', 'SYNTHETIC_WEARABLE'] : ['ALL', 'NASA_LAB']).map((src) => (
            <button
              key={src}
              onClick={() => setSourceFilter(src)}
              className={`px-2.5 py-1 text-xs font-mono rounded transition-colors ${
                sourceFilter === src
                  ? 'bg-cyan-950 border border-cyan-400 text-cyan-200'
                  : 'bg-space-950 border border-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              {src === 'ALL' ? 'All Sources' : src === 'NASA_LAB' ? 'NASA OSD-575' : 'Synthetic Stream'}
            </button>
          ))}
        </div>

        {/* State Filter */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[10px] font-mono uppercase text-slate-400 mr-1">State:</span>
          {['ALL', 'ATTENTION', 'REVIEW', 'NORMAL', 'INSUFFICIENT_DATA'].map((st) => (
            <button
              key={st}
              onClick={() => setStateFilter(st)}
              className={`px-2.5 py-1 text-xs font-mono rounded transition-colors ${
                stateFilter === st
                  ? 'bg-cyan-950 border border-cyan-400 text-cyan-200'
                  : 'bg-space-950 border border-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              {st.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Alert Evidence Cards List */}
      <div className="space-y-3">
        {filteredAlerts.map((alert, idx) => {
          const alertKey = alert.alert_id || `alert-${idx}`;
          const isExpanded = expandedAlertId === alertKey;

          return (
            <div
              key={alertKey}
              className={`p-4 rounded-xl border transition-all ${
                alert.alert_state === 'ATTENTION'
                  ? 'bg-space-900/90 border-amber-500/50 shadow-[0_0_15px_rgba(245,158,11,0.15)]'
                  : alert.alert_state === 'REVIEW'
                  ? 'bg-space-900/80 border-cyan-500/30'
                  : 'bg-space-900/60 border-slate-800'
              }`}
            >
              <div
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 cursor-pointer"
                onClick={() => setExpandedAlertId(isExpanded ? null : alertKey)}
              >
                <div className="flex items-center gap-3">
                  <StatusBadge status={alert.alert_state} size="sm" />
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold font-mono text-slate-100">
                        {alert.biomarker_or_sensor || (alert as any).measurement_name || 'Unavailable'}
                      </span>
                      <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                        alert.is_synthetic
                          ? 'bg-amber-950/60 text-amber-300 border border-amber-500/30'
                          : 'bg-cyan-950/60 text-cyan-300 border border-cyan-500/30'
                      }`}>
                        {alert.is_synthetic ? 'SYNTHETIC WEARABLE' : 'NASA OSD-575 LAB'}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 font-sans mt-0.5">
                      {alert.trigger_reason || alert.explanation || 'No explanation provided by the analysis.'}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3 self-end sm:self-center">
                  {alert.alert_state === 'REVIEW' && alert.alert_id && <button onClick={(event) => { event.stopPropagation(); onOpenReview(alert.alert_id!); }} className="rounded border border-amber-500/50 bg-amber-950/40 px-2 py-1 text-[10px] font-mono text-amber-200">REVIEW</button>}
                  <span className="text-[11px] font-mono text-slate-500">
                    {alert.timestamp || 'Recorded in SQLite'}
                  </span>
                  {isExpanded ? (
                    <ChevronUp className="w-4 h-4 text-cyan-400" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-slate-500" />
                  )}
                </div>
              </div>

              {/* Expanded Detailed Scientific Evidence & Flight Surgeon Guidance */}
              {isExpanded && (
                <div className="mt-4 pt-3 border-t border-slate-800/80 space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs font-mono">
                    {/* Statistical Evidence */}
                    <div className="p-3 rounded-lg bg-space-950 border border-slate-800 space-y-1.5">
                      <div className="text-[10px] uppercase text-cyan-400 font-bold">
                        Robust Statistical Evidence
                      </div>
                      <div className="flex justify-between text-slate-300">
                        <span>Robust Z-Score:</span>
                        <span className="font-bold text-cyan-200">
                          {alert.statistical_evidence?.robust_z !== undefined
                            ? alert.statistical_evidence.robust_z > 0
                              ? `+${alert.statistical_evidence.robust_z.toFixed(2)}`
                              : alert.statistical_evidence.robust_z.toFixed(2)
                            : '—'}
                        </span>
                      </div>
                      <div className="flex justify-between text-slate-300">
                        <span>Measured Value:</span>
                        <span>{alert.statistical_evidence?.measured_value ?? '—'}</span>
                      </div>
                      <div className="flex justify-between text-slate-300">
                        <span>Baseline Median:</span>
                        <span>{alert.statistical_evidence?.baseline_median ?? '—'}</span>
                      </div>
                    </div>

                    {/* Sensor Reliability / Quality Context */}
                    <div className="p-3 rounded-lg bg-space-950 border border-slate-800 space-y-1.5">
                      <div className="text-[10px] uppercase text-cyan-400 font-bold">
                        Sensor Trust & Motion
                      </div>
                      <div className="flex justify-between text-slate-300">
                        <span>Quality Score:</span>
                        <span className="font-bold text-emerald-300">
                          {alert.sensor_trust_context?.quality_score !== undefined
                            ? `${alert.sensor_trust_context.quality_score.toFixed(1)} / 100`
                            : 'Unavailable'}
                        </span>
                      </div>
                      <div className="flex justify-between text-slate-300">
                        <span>Motion Downgrade:</span>
                        <span>{alert.sensor_trust_context?.motion_downgrade ? 'Flagged (Downgraded)' : 'None'}</span>
                      </div>
                      <div className="flex justify-between text-slate-300">
                        <span>Reliability State:</span>
                        <span>{alert.sensor_trust_context?.reliability || 'Unavailable'}</span>
                      </div>
                    </div>

                    {/* Flight Surgeon Action Checklist */}
                    <div className="p-3 rounded-lg bg-space-950 border border-slate-800 space-y-1.5">
                      <div className="text-[10px] uppercase text-amber-400 font-bold flex items-center gap-1">
                        <UserCheck className="w-3.5 h-3.5 text-amber-400" />
                        <span>Surgeon Review Guidance</span>
                      </div>
                      <p className="text-[11px] text-slate-400 font-sans leading-normal">
                        {alert.human_review_guidance ||
                          'No review guidance was provided by the analysis.'}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {filteredAlerts.length === 0 && (
          <div className="p-12 text-center rounded-xl bg-space-900/40 border border-slate-800 text-slate-500 font-mono text-xs">
            No alerts matching the selected filter criteria.
          </div>
        )}
      </div>
    </div>
  );
};
