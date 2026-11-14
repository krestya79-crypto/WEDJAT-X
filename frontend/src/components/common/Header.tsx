import React, { useEffect, useState } from 'react';
import { Activity, Clock, Shield, Bell, RefreshCw, Radio } from 'lucide-react';
import { SystemStatusData, CrewMember } from '../../types';
import { StatusBadge } from './StatusBadge';

interface HeaderProps {
  systemStatus: SystemStatusData | null;
  activeAlertCount: number | null;
  selectedCrew: string;
  onSelectCrew: (crewId: string) => void;
  crewList: CrewMember[];
  isRefreshing: boolean;
  onRefresh: () => void;
  isConnected: boolean;
  connectionError?: string | null;
  lastUpdated?: Date | null;
}

export const Header: React.FC<HeaderProps> = ({
  systemStatus,
  activeAlertCount,
  selectedCrew,
  onSelectCrew,
  crewList,
  isRefreshing,
  onRefresh,
  isConnected,
  connectionError,
  lastUpdated,
}) => {
  const [currentTimeUtc, setCurrentTimeUtc] = useState<string>('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTimeUtc(now.toUTCString().replace('GMT', 'UTC'));
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="sticky top-0 z-40 w-full bg-space-950/90 backdrop-blur-xl border-b border-cyan-500/20 px-4 lg:px-6 py-2.5">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        {/* Left: Brand Identity with Eye of Horus crest */}
        <div className="flex items-center gap-3">
          <div className="relative flex items-center justify-center w-10 h-10 rounded-lg bg-gradient-to-br from-space-800 to-space-950 border border-cyan-400/40 shadow-glow-cyan">
            {/* Eye of Horus / Wedjat stylized geometric crest */}
            <svg
              className="w-6 h-6 text-cyan-400"
              viewBox="0 0 100 100"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <polygon points="50,15 90,50 50,85 10,50" stroke="#00f0ff" strokeWidth="6" fill="rgba(0, 240, 255, 0.08)" />
              <path d="M 25 50 Q 50 25 75 50 Q 50 75 25 50" stroke="#00f0ff" strokeWidth="5" fill="none" />
              <circle cx="50" cy="50" r="10" fill="#fbbf24" stroke="#00f0ff" strokeWidth="2" />
              <line x1="50" y1="60" x2="50" y2="78" stroke="#fbbf24" strokeWidth="4" strokeLinecap="round" />
              <path d="M 50 78 Q 40 85 30 75" stroke="#fbbf24" strokeWidth="3" fill="none" strokeLinecap="round" />
            </svg>
            <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-cyan-500"></span>
            </span>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="text-xl font-bold font-display tracking-widest text-cyan-50">
                WEDJAT<span className="text-cyan-400">-X</span>
              </span>
              <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-cyan-950/60 border border-cyan-500/30 text-cyan-300">
                MED-OPS v1.0
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-sans tracking-wide hidden sm:block">
              Guarding Life Beyond Earth, When Every Heartbeat Matters.
            </p>
          </div>
        </div>

        {/* Center: Crew Selector Matrix */}
        <div className="flex items-center gap-1.5 overflow-x-auto py-1">
          <span className="text-[10px] font-mono uppercase text-slate-400 mr-1 hidden sm:inline">
            CREW:
          </span>
          {crewList.map((crew) => {
            const isSelected = selectedCrew === crew.participant_id;
            return (
              <button
                key={crew.participant_id}
                onClick={() => onSelectCrew(crew.participant_id)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono transition-all duration-200 border ${
                  isSelected
                    ? 'bg-cyan-950/80 border-cyan-400 text-cyan-200 shadow-[0_0_12px_rgba(0,240,255,0.25)]'
                    : 'bg-space-900/60 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-300'
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${isSelected ? 'bg-cyan-400' : 'bg-slate-600'}`} />
                <span>{crew.participant_id}</span>
                {crew.callsign && <span className="text-[9px] opacity-60 hidden md:inline">({crew.callsign})</span>}
              </button>
            );
          })}
        </div>

        {/* Right: Telemetry Time, Connection & Refresh Actions */}
        <div className="flex items-center gap-3">
          {/* Mission UTC Clock */}
          <div className="hidden xl:flex items-center gap-1.5 px-3 py-1 rounded bg-space-900 border border-slate-800 text-slate-300 text-xs font-mono">
            <Clock className="w-3.5 h-3.5 text-cyan-400" />
            <span>{currentTimeUtc || 'SYNCING UTC...'}</span>
          </div>

          {/* Connection status pill */}
          <div
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-mono border ${
              isConnected
                ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300'
                : 'bg-amber-950/40 border-amber-500/40 text-amber-300'
            }`}
          >
            <Radio className={`w-3 h-3 ${isConnected ? 'text-emerald-400 animate-pulse' : 'text-amber-400'}`} />
            <span>{isConnected ? 'API CONNECTED' : lastUpdated ? 'STALE DATA' : 'API UNAVAILABLE'}</span>
          </div>
          <span className="hidden 2xl:inline text-[10px] font-mono text-slate-500" title={connectionError || undefined}>
            {lastUpdated ? `UPDATED ${lastUpdated.toLocaleTimeString()}` : connectionError ? 'NO BACKEND DATA' : 'CONNECTING'}
          </span>

          {/* System Status Badge */}
          {systemStatus && (
            <StatusBadge status={systemStatus.status} size="sm" />
          )}

          {/* Active Alerts Pill */}
          <div className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs font-mono border ${
            activeAlertCount > 0
              ? 'bg-amber-950/60 border-amber-500/50 text-amber-300 shadow-[0_0_12px_rgba(245,158,11,0.2)]'
              : 'bg-space-900 border-slate-800 text-slate-400'
          }`}>
            <Bell className={`w-3.5 h-3.5 ${activeAlertCount > 0 ? 'text-amber-400 animate-bounce' : 'text-slate-500'}`} />
            <span title="Flagged alerts in the latest analysis only">{activeAlertCount ?? '—'} LATEST RUN ALERTS</span>
          </div>

          {/* Refresh Button */}
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="p-1.5 rounded-lg bg-space-900 border border-cyan-500/30 text-cyan-400 hover:bg-cyan-950 hover:text-cyan-200 transition-colors disabled:opacity-50"
            title="Refresh dashboard data"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>
    </header>
  );
};
