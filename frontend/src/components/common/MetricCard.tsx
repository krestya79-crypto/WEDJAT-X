import React from 'react';
import { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  label: string;
  value: string | number | null | undefined;
  unit?: string;
  subtitle?: string;
  icon?: LucideIcon;
  variant?: 'cyan' | 'gold' | 'alert' | 'normal' | 'slate';
  badge?: string;
  trend?: 'up' | 'down' | 'stable';
  trendText?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  unit,
  subtitle,
  icon: Icon,
  variant = 'cyan',
  badge,
  trend,
  trendText,
}) => {
  const isAvailable = value !== null && value !== undefined && value !== 'Unavailable';
  const displayValue = isAvailable ? value : '—';

  const variantStyles = {
    cyan: {
      border: 'border-cyan-500/20 hover:border-cyan-400/50',
      glow: 'shadow-[0_4px_20px_rgba(0,240,255,0.08)]',
      kicker: 'text-cyan-400',
      valueColor: 'text-cyan-100',
      bracket: 'hud-bracket',
    },
    gold: {
      border: 'border-amber-500/25 hover:border-amber-400/60',
      glow: 'shadow-[0_4px_20px_rgba(251,191,36,0.1)]',
      kicker: 'text-amber-400',
      valueColor: 'text-amber-100',
      bracket: 'hud-bracket hud-bracket-gold',
    },
    alert: {
      border: 'border-rose-500/30 hover:border-rose-400/70',
      glow: 'shadow-[0_4px_20px_rgba(239,68,68,0.15)]',
      kicker: 'text-rose-400',
      valueColor: 'text-rose-100',
      bracket: 'hud-bracket',
    },
    normal: {
      border: 'border-emerald-500/25 hover:border-emerald-400/60',
      glow: 'shadow-[0_4px_20px_rgba(16,185,129,0.1)]',
      kicker: 'text-emerald-400',
      valueColor: 'text-emerald-100',
      bracket: 'hud-bracket',
    },
    slate: {
      border: 'border-slate-700/60 hover:border-slate-600',
      glow: '',
      kicker: 'text-slate-400',
      valueColor: 'text-slate-200',
      bracket: 'hud-bracket',
    },
  }[variant];

  return (
    <div
      className={`relative p-4 rounded-lg bg-space-900/80 backdrop-blur-md border ${variantStyles.border} ${variantStyles.glow} ${variantStyles.bracket} transition-all duration-300 group`}
    >
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className={`text-[10px] font-mono uppercase tracking-widest ${variantStyles.kicker}`}>
          {label}
        </span>
        <div className="flex items-center gap-1.5">
          {badge && (
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-space-800 border border-slate-700 text-slate-400">
              {badge}
            </span>
          )}
          {Icon && <Icon className={`w-3.5 h-3.5 ${variantStyles.kicker} opacity-70 group-hover:opacity-100 transition-opacity`} />}
        </div>
      </div>

      <div className="flex items-baseline gap-1.5">
        <span className={`text-2xl font-bold font-mono tracking-tight ${variantStyles.valueColor}`}>
          {displayValue}
        </span>
        {unit && isAvailable && (
          <span className="text-xs font-mono text-slate-400 font-medium">
            {unit}
          </span>
        )}
      </div>

      {(subtitle || trendText) && (
        <div className="mt-2 pt-1.5 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400 font-sans">
          <span>{subtitle}</span>
          {trendText && (
            <span className={`font-mono text-[10px] ${trend === 'up' ? 'text-amber-400' : trend === 'down' ? 'text-sky-400' : 'text-slate-400'}`}>
              {trendText}
            </span>
          )}
        </div>
      )}
    </div>
  );
};
