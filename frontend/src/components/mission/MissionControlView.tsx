import React from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Database,
  Flame,
  Radio,
  RefreshCw,
  ShieldAlert,
  User,
  Zap,
} from 'lucide-react';
import {
  SystemStatusData,
  CrewMember,
  ProcessingResultData,
  AlertEvidence,
} from '../../types';
import { MetricCard } from '../common/MetricCard';
import { StatusBadge } from '../common/StatusBadge';
import { DisclaimerBanner } from '../common/DisclaimerBanner';
import { AstronautViewer } from '../astronaut/AstronautViewer';

interface MissionControlViewProps {
  systemStatus: SystemStatusData | null;
  crewList: CrewMember[];
  selectedCrew: string;
  onSelectCrew: (crewId: string) => void;
  latestResult: ProcessingResultData | null;
  totalAlertCount: number | null;
  recentAlerts: AlertEvidence[];
  activeAlertCount: number | null;
  onRunNasaAnalysis: (crewId: string) => void;
  onRunWearableAnalysis: (scenario: string) => void;
  isAnalyzing: boolean;
  showSyntheticFeatures?: boolean;
  onNavigateTab: (tabId: any) => void;
  onOpenReview: (alertId: string) => void;
}

export const MissionControlView: React.FC<MissionControlViewProps> = ({
  systemStatus,
  crewList,
  selectedCrew,
  onSelectCrew,
  latestResult,
  totalAlertCount,
  recentAlerts,
  activeAlertCount: exactActiveAlertCount,
  onRunNasaAnalysis,
  onRunWearableAnalysis,
  isAnalyzing,
  showSyntheticFeatures = true,
  onNavigateTab,
  onOpenReview,
}) => {
  const activeAlertCount = exactActiveAlertCount;
  const activeAlerts = recentAlerts.filter(
    (a) => a.alert_state === 'ATTENTION' || a.alert_state === 'REVIEW' || a.alert_state === 'CRITICAL'
  );

  const currentCrew = crewList.find((c) => c.participant_id === selectedCrew) || crewList[0];

  return (
    <div className="space-y-6">
      {/* Top Disclaimer & Provenance Warning */}
      <DisclaimerBanner source={showSyntheticFeatures ? 'BOTH' : 'NASA_LAB'} />

      {/* Hero Mission Control Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard
          label="OPERATIONAL STATUS"
          value={systemStatus?.status || 'UNAVAILABLE'}
          subtitle="Core analytical modules"
          variant={systemStatus?.status === 'READY' ? 'normal' : 'alert'}
          badge="NASA OSD-575"
        />
        <MetricCard
          label="PERSISTED ALERT EVENTS"
          value={totalAlertCount ?? 'Unavailable'}
          subtitle={totalAlertCount === null ? 'Backend metric unavailable' : `${activeAlertCount ?? 'Unavailable'} flagged in latest analysis result`}
          variant={activeAlertCount === null ? 'slate' : activeAlertCount > 0 ? 'alert' : 'normal'}
        />
        <MetricCard
          label="ACTIVE SUBJECT"
          value={currentCrew?.participant_id || 'Unavailable'}
          unit={currentCrew?.role}
          subtitle={currentCrew?.mission || 'NASA OSD-575'}
          variant="cyan"
        />
        <MetricCard
          label="ANALYTICAL ENGINES"
          value={
            systemStatus?.initialized_engines
              ? Object.values(systemStatus.initialized_engines).filter(Boolean).length
              : '—'
          }
          unit="engines"
          subtitle="Baseline, Anomaly, Bayesian, Trust"
          variant="gold"
        />
      </div>

      {/* Main Grid: 3D Holographic Monitor & Crew Command Matrix */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: 3D Astronaut Centerpiece */}
        <div className="lg:col-span-7 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
              <h2 className="text-sm font-mono uppercase tracking-widest text-cyan-300">
                ASTRONAUT SPATIAL VIEW · LIVE VITALS UNAVAILABLE
              </h2>
            </div>
            <button
              onClick={() => onNavigateTab('astronaut')}
              className="text-xs font-mono text-cyan-400 hover:text-cyan-200 transition-colors"
            >
              Expand Spatial HUD →
            </button>
          </div>

          <AstronautViewer
            isSynthetic={false}
            participantId={selectedCrew}
            analysisResult={latestResult}
          />
        </div>

        {/* Right Column: Inspiration4 Crew Matrix & Quick Actions */}
        <div className="lg:col-span-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-mono uppercase tracking-widest text-cyan-300">
              NASA OSD-575 PARTICIPANTS
            </h2>
            <span className="text-[10px] font-mono text-slate-400">N={crewList.length || '—'} PARTICIPANTS</span>
          </div>

          <div className="space-y-2.5">
            {crewList.map((crew) => {
              const isSelected = selectedCrew === crew.participant_id;
              return (
                <div
                  key={crew.participant_id}
                  onClick={() => onSelectCrew(crew.participant_id)}
                  className={`p-3 rounded-lg border transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-cyan-950/70 border-cyan-400/80 shadow-[0_0_15px_rgba(0,240,255,0.15)]'
                      : 'bg-space-900/80 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <div className={`w-8 h-8 rounded flex items-center justify-center font-mono text-xs font-bold ${
                        isSelected ? 'bg-cyan-500 text-space-950 shadow-[0_0_10px_#00f0ff]' : 'bg-space-800 text-slate-300'
                      }`}>
                        {crew.participant_id}
                      </div>
                      <div>
                        <div className="text-xs font-semibold text-slate-200">
                          {crew.display_name}
                        </div>
                        <div className="text-[10px] font-mono text-slate-400">
                          {crew.role}
                        </div>
                      </div>
                    </div>

                    <div className="text-right">
                      <div className="text-[10px] font-mono text-cyan-400">
                        {crew.total_biomarkers} Biomarkers
                      </div>
                      <div className="text-[10px] font-mono text-slate-400">
                        {crew.total_observations} Assays
                      </div>
                    </div>
                  </div>

                  <div className="mt-2.5 pt-2 border-t border-slate-800/80 flex items-center justify-between">
                    <span className="text-[10px] font-mono text-slate-400">
                      Milestones: L-92 through R+194
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onRunNasaAnalysis(crew.participant_id);
                      }}
                      disabled={isAnalyzing}
                      className="px-2 py-1 text-[11px] font-mono rounded bg-cyan-950/80 hover:bg-cyan-900 border border-cyan-500/40 text-cyan-300 transition-colors flex items-center gap-1 disabled:opacity-50"
                    >
                      <Zap className="w-3 h-3 text-cyan-400" />
                      <span>{isAnalyzing && isSelected ? 'Analyzing...' : 'Run Pipeline'}</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {showSyntheticFeatures && (
            <div className="p-3.5 rounded-lg bg-space-900/90 border border-amber-500/30 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono uppercase text-amber-300 font-semibold flex items-center gap-1.5">
                  <Radio className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
                  <span>Simulate Sensor Telemetry</span>
                </span>
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-amber-950 border border-amber-500/40 text-amber-300">
                  SYNTHETIC ONLY
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-sans">
                Test flight surgeon alert routing and motion-artifact cancellation using realistic synthetic stress scenarios.
              </p>
              <div className="flex flex-wrap gap-2 pt-1">
                <button
                  onClick={() => onRunWearableAnalysis('normal_scenario.csv')}
                  disabled={isAnalyzing}
                  className="px-2.5 py-1 text-xs font-mono rounded bg-space-800 hover:bg-space-700 border border-slate-700 text-slate-300 transition-colors"
                >
                  Nominal
                </button>
                <button
                  onClick={() => onRunWearableAnalysis('motion_artifact_scenario.csv')}
                  disabled={isAnalyzing}
                  className="px-2.5 py-1 text-xs font-mono rounded bg-amber-950/60 hover:bg-amber-900 border border-amber-500/40 text-amber-300 transition-colors"
                >
                  Motion Artifact
                </button>
                <button
                  onClick={() => onRunWearableAnalysis('sensor_disconnect_scenario.csv')}
                  disabled={isAnalyzing}
                  className="px-2.5 py-1 text-xs font-mono rounded bg-rose-950/60 hover:bg-rose-900 border border-rose-500/40 text-rose-300 transition-colors"
                >
                  Lead Disconnect
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Section: Latest Processing Summary & Active Alerts Snapshot */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Latest Analysis Session Evidence */}
        <div className="p-4 rounded-xl bg-space-900/80 border border-cyan-500/20 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-cyan-400" />
              <h3 className="text-xs font-mono uppercase tracking-widest text-cyan-300">
                LATEST ANALYTICAL SESSION
              </h3>
            </div>
            {latestResult && (
              <span className="text-[10px] font-mono text-slate-400">
                REQ {latestResult.request_id?.slice(0, 8)}…
              </span>
            )}
          </div>

          {latestResult ? (
            <div className="space-y-2.5">
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-slate-400">Source Pathway:</span>
                <span className={`font-semibold ${latestResult.is_synthetic ? 'text-amber-400' : 'text-cyan-400'}`}>
                  {latestResult.is_synthetic ? 'SYNTHETIC WEARABLE' : 'NASA OSD-575 DISCRETE LAB'}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-slate-400">Operational Status:</span>
                <StatusBadge status={latestResult.processing_status} size="sm" />
              </div>
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-slate-400">Subject / Astronaut:</span>
                <span className="text-slate-200">{latestResult.astronaut_id || latestResult.subject_id || '—'}</span>
              </div>
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-slate-400">Execution Timestamp:</span>
                <span className="text-slate-400">{latestResult.timestamp}</span>
              </div>

              {latestResult.warnings && latestResult.warnings.length > 0 && (
                <div className="p-2 rounded bg-space-950 border border-amber-500/30 text-[10px] font-mono text-amber-300">
                  {latestResult.warnings[0]}
                </div>
              )}
            </div>
          ) : (
            <div className="p-6 text-center text-xs font-mono text-slate-500">
              No analysis session loaded yet. Run a participant or scenario analysis above.
            </div>
          )}
        </div>

        {/* Operational Alerts Snapshot */}
        <div className="p-4 rounded-xl bg-space-900/80 border border-cyan-500/20 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              <h3 className="text-xs font-mono uppercase tracking-widest text-amber-300">
                ACTIVE ALERTS SNAPSHOT
              </h3>
            </div>
            <button
              onClick={() => onNavigateTab('alerts')}
              className="text-xs font-mono text-cyan-400 hover:text-cyan-200"
            >
              View All ({recentAlerts.length}) →
            </button>
          </div>

          <div className="space-y-2">
            {activeAlerts.slice(0, 3).map((alert, idx) => (
              <div
                key={alert.alert_id || idx}
                className="p-2.5 rounded-lg bg-space-950/70 border border-slate-800 flex items-start justify-between gap-2"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={alert.alert_state} size="sm" />
                    <span className="text-xs font-mono font-semibold text-slate-200">
                      {alert.biomarker_or_sensor}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 font-sans mt-1 line-clamp-1">
                    {alert.trigger_reason || alert.explanation || 'Statistical deviation from personal baseline'}
                  </p>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1"><span className="text-[10px] font-mono text-slate-500">{alert.source_type}</span>{alert.alert_state === 'REVIEW' && alert.alert_id && <button onClick={()=>onOpenReview(alert.alert_id!)} className="text-[10px] font-mono text-amber-200 underline">Review</button>}</div>
              </div>
            ))}

            {activeAlerts.length === 0 && (
              <div className="p-6 text-center text-xs font-mono text-slate-500">
                No active alerts are present in the recent response.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
