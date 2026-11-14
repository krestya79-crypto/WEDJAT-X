import React, { useState } from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  Activity,
  Zap,
  Radio,
  Sliders,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';
import { SensorTrustDetail } from '../../types';
import { MetricCard } from '../common/MetricCard';
import { StatusBadge } from '../common/StatusBadge';

interface SensorTrustViewProps {
  trustData: { is_synthetic: boolean; timestamp: string; request_id: string; sensor_trust: Record<string, unknown> } | null;
}

export const SensorTrustView: React.FC<SensorTrustViewProps> = ({ trustData }) => {
  const [selectedSensor, setSelectedSensor] = useState<string>('heart_rate');

  const rawTrust = trustData?.sensor_trust;
  const trustRecord: Record<string, SensorTrustDetail> = trustData?.is_synthetic
    ? ('sensors' in (rawTrust || {}) ? (rawTrust.sensors || {}) as Record<string, SensorTrustDetail> : rawTrust as Record<string, SensorTrustDetail> || {})
    : {};

  const currentSensorTrust = trustRecord[selectedSensor] || Object.values(trustRecord)[0];

  const subScores = [
    {
      name: 'Missingness Metric',
      score: currentSensorTrust?.sub_scores?.missing,
      desc: 'Absence of data dropouts, null sensor packets, and telemetry transmission loss.',
    },
    {
      name: 'High-Frequency Noise',
      score: currentSensorTrust?.sub_scores?.noise,
      desc: 'Filtering of electromagnetic interference and high-frequency physiological jitter.',
    },
    {
      name: 'Sensor Lead Disconnection',
      score: currentSensorTrust?.sub_scores?.disconnection,
      desc: 'Verification of skin electrode impedance and physical sensor attachment continuity.',
    },
    {
      name: 'Spikes & Transient Artifacts',
      score: currentSensorTrust?.sub_scores?.spikes,
      desc: 'Hampel filter sliding window outlier rejection across local median deviations.',
    },
    {
      name: 'Motion Artifact Cross-Check',
      score: undefined,
      desc: 'Tri-axial accelerometer kinetic cross-validation against heart rate false alarms.',
    },
    {
      name: 'Timestamp Continuity',
      score: currentSensorTrust?.sub_scores?.continuity,
      desc: 'Monotonic sequence verification and sensor sampling clock jitter quantification.',
    },
    {
      name: 'Signal Drift & Baseline Wander',
      score: currentSensorTrust?.sub_scores?.drift,
      desc: 'Photoplethysmography sensor temperature drift and slow baseline displacement.',
    },
  ].filter((item) => typeof item.score === 'number');

  return (
    <div className="space-y-6">
      {!currentSensorTrust && <div className="p-8 rounded-xl border border-slate-800 bg-space-900 text-center text-sm text-slate-400">No persisted synthetic sensor trust result is available.</div>}
      {currentSensorTrust && trustData && <div className="text-[10px] font-mono text-slate-500">SYNTHETIC · REQUEST {trustData.request_id} · {new Date(trustData.timestamp).toLocaleString()}</div>}
      {/* Synthetic Stream Warning */}
      <div className="p-4 rounded-xl bg-amber-950/40 border border-amber-500/40 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0" />
          <div className="text-xs text-slate-300 font-sans">
            <strong className="text-amber-300 font-mono uppercase tracking-wider">
              Synthetic Telemetry Trust Scoring:
            </strong>{' '}
            Sensor trust reflects mathematical signal reliability and sensor hardware integrity, not astronaut clinical health.
          </div>
        </div>
        <span className="text-xs font-mono px-3 py-1 rounded bg-amber-950 border border-amber-500/40 text-amber-300 shrink-0">
          SIGNAL INTEGRITY
        </span>
      </div>

      {/* Sensor Channel Selector */}
      <div className="p-3.5 rounded-xl bg-space-900/80 border border-cyan-500/20 backdrop-blur-md flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono uppercase text-slate-400">Sensor Channel:</span>
          {Object.keys(trustRecord).map((s) => (
            <button
              key={s}
              onClick={() => setSelectedSensor(s)}
              className={`px-3 py-1.5 text-xs font-mono rounded transition-colors uppercase ${
                selectedSensor === s
                  ? 'bg-cyan-950 border border-cyan-400 text-cyan-200'
                  : 'bg-space-950 border border-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              {s.replace('_', ' ')}
            </button>
          ))}
        </div>

        <StatusBadge
          status={currentSensorTrust?.reliability_category || 'UNAVAILABLE'}
          size="md"
        />
      </div>

      {/* Main Gauge & Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Overall Quality Score Circular Gauge Card */}
        <div className="p-6 rounded-xl bg-space-900/80 border border-cyan-500/20 backdrop-blur-md flex flex-col items-center justify-center text-center space-y-3">
          <span className="text-xs font-mono uppercase text-slate-400 tracking-widest">
            OVERALL SIGNAL TRUST SCORE
          </span>

          <div className="relative flex items-center justify-center w-36 h-36">
            <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
              <circle
                cx="50"
                cy="50"
                r="40"
                fill="none"
                stroke="#1e293b"
                strokeWidth="8"
              />
              <circle
                cx="50"
                cy="50"
                r="40"
                fill="none"
                stroke="#00f0ff"
                strokeWidth="8"
                strokeDasharray={`${(currentSensorTrust?.quality_score ?? 0) * 2.51} 251`}
                strokeLinecap="round"
                className="transition-all duration-1000 ease-out shadow-[0_0_15px_#00f0ff]"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-3xl font-bold font-mono text-cyan-100">
                {currentSensorTrust?.quality_score != null ? currentSensorTrust.quality_score.toFixed(1) : '—'}
              </span>
              <span className="text-[10px] font-mono text-slate-400 uppercase">/ 100</span>
            </div>
          </div>

          <div className="text-xs font-mono text-slate-300">
            Category: <strong className="text-cyan-300">{currentSensorTrust?.reliability_category || 'Unavailable'}</strong>
          </div>
        </div>

        {/* Breakdown Summary Cards */}
        <div className="md:col-span-2 grid grid-cols-2 gap-3">
          <MetricCard
            label="DISCONNECTION RATE"
            value={currentSensorTrust?.disconnection_rate !== undefined ? `${(currentSensorTrust.disconnection_rate * 100).toFixed(1)}%` : 'Unavailable'}
            subtitle="Signal zero or impedance drop"
            variant="cyan"
          />
          <MetricCard
            label="HAMPEL SPIKES REJECTED"
            value={currentSensorTrust?.spike_count ?? 'Unavailable'}
            subtitle="Transient spikes suppressed"
            variant="gold"
          />
          <MetricCard
            label="TIMESTAMP CONTINUITY"
            value={currentSensorTrust?.timestamp_gap_count !== undefined ? `${currentSensorTrust.timestamp_gap_count} gaps` : 'Unavailable'}
            subtitle="Jitter and timing regularity"
            variant="normal"
          />
          <MetricCard
            label="MOTION CORRELATION"
            value={currentSensorTrust?.motion_overlap_pct !== undefined ? `${currentSensorTrust.motion_overlap_pct.toFixed(1)}%` : 'Unavailable'}
            subtitle="Concurrent accelerometer validation"
            variant="slate"
          />
        </div>
      </div>

      {/* Detailed Sub-Score Progress Breakdown */}
      <div className="p-4 rounded-xl bg-space-900/80 border border-cyan-500/20 backdrop-blur-md space-y-4">
        <h3 className="text-xs font-mono uppercase tracking-widest text-cyan-300 font-bold">
          ANALYTICAL SIGNAL TRUST DIMENSIONS
        </h3>

        <div className="space-y-3">
          {subScores.map((dim) => (
            <div key={dim.name} className="p-3 rounded-lg bg-space-950/70 border border-slate-800 space-y-1.5">
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-slate-200 font-semibold">{dim.name}</span>
                <span className="text-cyan-300 font-bold">{dim.score?.toFixed(1)} / 100</span>
              </div>
              <div className="w-full h-1.5 bg-space-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-cyan-500 to-cyan-300 rounded-full transition-all duration-700 shadow-[0_0_8px_#00f0ff]"
                  style={{ width: `${Math.min(100, Math.max(0, dim.score ?? 0))}%` }}
                />
              </div>
              <p className="text-[11px] text-slate-400 font-sans">
                {dim.desc}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
