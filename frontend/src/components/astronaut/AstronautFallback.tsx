import React from 'react';
import { Activity, Heart, Wind, ShieldAlert, Radio } from 'lucide-react';
import { ReliabilityCategory } from '../../types';

interface AstronautFallbackProps {
  heartRate?: number | null;
  spo2?: number | null;
  activityLevel?: string | null;
  sensorReliability?: ReliabilityCategory | string | null;
  isSynthetic?: boolean;
}

export const AstronautFallback: React.FC<AstronautFallbackProps> = ({
  heartRate,
  spo2,
  activityLevel,
  sensorReliability,
  isSynthetic = false,
}) => {
  return (
    <div className="relative w-full h-[520px] rounded-xl bg-space-950 border border-cyan-500/20 overflow-hidden flex flex-col items-center justify-center p-6 telemetry-grid">
      {/* Background Holographic Radar Rings */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-20">
        <div className="w-[380px] h-[380px] rounded-full border border-cyan-400 animate-spin" style={{ animationDuration: '40s' }} />
        <div className="absolute w-[260px] h-[260px] rounded-full border border-dashed border-cyan-300 animate-spin" style={{ animationDirection: 'reverse', animationDuration: '25s' }} />
        <div className="absolute w-[140px] h-[140px] rounded-full border border-cyan-500/40" />
      </div>

      {/* Vertical Cyan Scanning Line */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="w-full h-1 bg-gradient-to-r from-transparent via-cyan-400 to-transparent opacity-75 shadow-[0_0_15px_#00f0ff] animate-scanline" />
      </div>

      {/* Top Banner */}
      <div className="absolute top-4 left-4 right-4 flex items-center justify-between z-10">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono font-semibold tracking-widest text-cyan-400">
            HOLOGRAPHIC BIOMETRIC AVATAR
          </span>
          {isSynthetic && (
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-950/80 border border-amber-500/40 text-amber-300">
              SYNTHETIC TELEMETRY
            </span>
          )}
        </div>
        <div className="text-[10px] font-mono text-slate-400 flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>VITAL SCANNER ACTIVE</span>
        </div>
      </div>

      {/* Central SVG Astronaut Silhouette with Anatomical Hologram Nodes */}
      <div className="relative w-64 h-96 my-auto flex items-center justify-center">
        <svg
          viewBox="0 0 200 320"
          className="w-full h-full text-cyan-500/30 drop-shadow-[0_0_20px_rgba(0,240,255,0.3)]"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Astronaut Suit Blueprint Geometry */}
          {/* Helmet */}
          <ellipse cx="100" cy="50" rx="32" ry="34" stroke="#00f0ff" strokeWidth="2.5" fill="rgba(0,240,255,0.05)" />
          {/* Visor */}
          <path d="M 78 45 Q 100 32 122 45 Q 124 64 100 68 Q 76 64 78 45 Z" fill="rgba(0,240,255,0.2)" stroke="#22d3ee" strokeWidth="2" />
          {/* Neck collar */}
          <rect x="80" y="82" width="40" height="10" rx="3" stroke="#00f0ff" strokeWidth="2" fill="rgba(17,34,64,0.6)" />
          {/* Torso */}
          <path d="M 62 92 L 138 92 L 146 170 L 54 170 Z" stroke="#00f0ff" strokeWidth="2.5" fill="rgba(13,27,42,0.6)" />
          {/* Chest Pack (DCM) */}
          <rect x="76" y="105" width="48" height="42" rx="4" stroke="#22d3ee" strokeWidth="2" fill="rgba(0,240,255,0.15)" />
          <circle cx="90" cy="122" r="5" stroke="#fbbf24" strokeWidth="1.5" fill="none" />
          <line x1="102" y1="120" x2="116" y2="120" stroke="#00f0ff" strokeWidth="2" />
          <line x1="102" y1="126" x2="114" y2="126" stroke="#00f0ff" strokeWidth="2" />
          {/* Shoulders & Arms */}
          <circle cx="56" cy="100" r="12" stroke="#00f0ff" strokeWidth="2" fill="rgba(0,240,255,0.05)" />
          <circle cx="144" cy="100" r="12" stroke="#00f0ff" strokeWidth="2" fill="rgba(0,240,255,0.05)" />
          <path d="M 48 108 L 38 160 L 48 190" stroke="#00f0ff" strokeWidth="3" strokeLinecap="round" />
          <path d="M 152 108 L 162 160 L 152 190" stroke="#00f0ff" strokeWidth="3" strokeLinecap="round" />
          {/* Waist belt */}
          <rect x="66" y="170" width="68" height="12" rx="3" stroke="#00f0ff" strokeWidth="2" fill="rgba(0,240,255,0.1)" />
          {/* Legs */}
          <path d="M 72 182 L 68 250 L 64 300" stroke="#00f0ff" strokeWidth="3.5" strokeLinecap="round" />
          <path d="M 128 182 L 132 250 L 136 300" stroke="#00f0ff" strokeWidth="3.5" strokeLinecap="round" />
          {/* Boots */}
          <path d="M 52 300 L 76 300 L 78 310 L 48 310 Z" stroke="#00f0ff" strokeWidth="2" fill="rgba(0,240,255,0.2)" />
          <path d="M 124 300 L 148 300 L 152 310 L 122 310 Z" stroke="#00f0ff" strokeWidth="2" fill="rgba(0,240,255,0.2)" />
        </svg>

        {/* Anatomical Vital Indicator Pins */}
        {/* Heart Node Pin */}
        <div className="absolute top-[38%] left-[45%] -translate-x-1/2 -translate-y-1/2 z-20 group">
          <div className="relative flex items-center justify-center">
            <span className="animate-ping absolute inline-flex h-6 w-6 rounded-full bg-rose-400 opacity-75" />
            <span className="relative inline-flex items-center justify-center w-5 h-5 rounded-full bg-rose-950 border border-rose-500 shadow-[0_0_12px_#f43f5e]">
              <Heart className="w-2.5 h-2.5 text-rose-400 fill-rose-400 animate-pulse" />
            </span>
          </div>
        </div>

        {/* Pulmonary / SpO2 Node Pin */}
        <div className="absolute top-[46%] left-[55%] -translate-x-1/2 -translate-y-1/2 z-20 group">
          <div className="relative flex items-center justify-center">
            <span className="animate-ping absolute inline-flex h-6 w-6 rounded-full bg-cyan-400 opacity-75" style={{ animationDelay: '0.4s' }} />
            <span className="relative inline-flex items-center justify-center w-5 h-5 rounded-full bg-cyan-950 border border-cyan-400 shadow-[0_0_12px_#00f0ff]">
              <Wind className="w-2.5 h-2.5 text-cyan-300" />
            </span>
          </div>
        </div>
      </div>

      {/* Floating Holographic Telemetry Cards around Astronaut */}
      <div className="absolute bottom-4 left-4 right-4 grid grid-cols-2 md:grid-cols-4 gap-3 z-10">
        {heartRate !== null && heartRate !== undefined && <div className="p-2.5 rounded bg-space-900/90 border border-rose-500/30 backdrop-blur-md">
          <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase text-rose-400">
            <Heart className="w-3 h-3 text-rose-400" />
            <span>PULSE RATE</span>
          </div>
          <div className="text-xl font-bold font-mono text-rose-100 mt-0.5">
            {heartRate !== null && heartRate !== undefined ? `${heartRate} BPM` : 'Unavailable'}
          </div>
          <div className="text-[10px] text-slate-400 font-mono">Cardiac Channel</div>
        </div>}

        {spo2 !== null && spo2 !== undefined && <div className="p-2.5 rounded bg-space-900/90 border border-cyan-500/30 backdrop-blur-md">
          <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase text-cyan-400">
            <Wind className="w-3 h-3 text-cyan-400" />
            <span>SpO₂ SATURATION</span>
          </div>
          <div className="text-xl font-bold font-mono text-cyan-100 mt-0.5">
            {spo2 !== null && spo2 !== undefined ? `${spo2}%` : 'Unavailable'}
          </div>
          <div className="text-[10px] text-slate-400 font-mono">Photoplethysmography</div>
        </div>}

        {activityLevel !== null && activityLevel !== undefined && <div className="p-2.5 rounded bg-space-900/90 border border-amber-500/30 backdrop-blur-md">
          <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase text-amber-400">
            <Activity className="w-3 h-3 text-amber-400" />
            <span>ACTIVITY MONITOR</span>
          </div>
          <div className="text-xl font-bold font-mono text-amber-100 mt-0.5">
            {activityLevel ?? 'Unavailable'}
          </div>
          <div className="text-[10px] text-slate-400 font-mono">Tri-axial Accelerometry</div>
        </div>}

        {sensorReliability !== null && sensorReliability !== undefined && <div className="p-2.5 rounded bg-space-900/90 border border-emerald-500/30 backdrop-blur-md">
          <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase text-emerald-400">
            <Radio className="w-3 h-3 text-emerald-400" />
            <span>SENSOR RELIABILITY</span>
          </div>
          <div className="text-xl font-bold font-mono text-emerald-100 mt-0.5">
            {sensorReliability ? String(sensorReliability).replace('_', ' ') : 'UNAVAILABLE'}
          </div>
          <div className="text-[10px] text-slate-400 font-mono">Hampel / Cross-Check</div>
        </div>}
      </div>
    </div>
  );
};
