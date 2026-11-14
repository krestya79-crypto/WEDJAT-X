import React from 'react';
import { AlertState, SystemStatusType } from '../../types';

interface StatusBadgeProps {
  status: AlertState | SystemStatusType | string;
  size?: 'sm' | 'md' | 'lg';
  showPulse?: boolean;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  size = 'md',
  showPulse = true,
}) => {
  const norm = String(status).toUpperCase();

  let bg = 'bg-slate-800/80 text-slate-300 border-slate-700';
  let dot = 'bg-slate-400';
  let glow = '';

  switch (norm) {
    case 'READY':
    case 'NORMAL':
    case 'OPTIMAL':
    case 'HIGH_RELIABILITY':
    case 'SUCCESS':
      bg = 'bg-emerald-950/70 text-emerald-300 border-emerald-500/40';
      dot = 'bg-emerald-400 shadow-[0_0_8px_#34d399]';
      glow = 'shadow-[0_0_12px_rgba(16,185,129,0.2)]';
      break;
    case 'REVIEW':
    case 'ACCEPTABLE':
    case 'MODERATE_RELIABILITY':
    case 'PARTIAL_SUCCESS':
      bg = 'bg-sky-950/70 text-sky-300 border-sky-500/40';
      dot = 'bg-sky-400 shadow-[0_0_8px_#38bdf8]';
      glow = 'shadow-[0_0_12px_rgba(56,189,248,0.2)]';
      break;
    case 'ATTENTION':
    case 'DEGRADED':
    case 'LOW_RELIABILITY':
      bg = 'bg-amber-950/70 text-amber-300 border-amber-500/50';
      dot = 'bg-amber-400 shadow-[0_0_8px_#fbbf24]';
      glow = 'shadow-[0_0_15px_rgba(245,158,11,0.25)]';
      break;
    case 'CRITICAL':
    case 'ERROR':
    case 'FAILED':
    case 'UNRELIABLE':
      bg = 'bg-rose-950/80 text-rose-300 border-rose-500/60';
      dot = 'bg-rose-500 shadow-[0_0_8px_#f43f5e]';
      glow = 'shadow-[0_0_16px_rgba(244,63,94,0.3)]';
      break;
    case 'INSUFFICIENT_DATA':
    case 'UNAVAILABLE':
      bg = 'bg-slate-900/80 text-slate-400 border-slate-700/60';
      dot = 'bg-slate-500';
      glow = '';
      break;
  }

  const sizeClasses = {
    sm: 'text-[10px] px-2 py-0.5 tracking-wider',
    md: 'text-xs px-2.5 py-1 tracking-widest',
    lg: 'text-sm px-3.5 py-1.5 tracking-widest font-semibold',
  }[size];

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-mono uppercase border rounded-full backdrop-blur-sm transition-all duration-300 ${sizeClasses} ${bg} ${glow}`}
    >
      <span className="relative flex h-2 w-2">
        {showPulse && norm !== 'INSUFFICIENT_DATA' && (
          <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${dot}`} />
        )}
        <span className={`relative inline-flex rounded-full h-2 w-2 ${dot}`} />
      </span>
      {norm.replace('_', ' ')}
    </span>
  );
};
