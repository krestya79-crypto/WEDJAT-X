import React, { useEffect, useState } from 'react';
import {
  History,
  Database,
  Calendar,
  CheckCircle2,
  FileCode,
  Copy,
  Check,
  ChevronRight,
  ExternalLink,
} from 'lucide-react';
import { ProcessingResultData } from '../../types';
import { StatusBadge } from '../common/StatusBadge';
import { MetricCard } from '../common/MetricCard';

interface HistoryViewProps {
  history: ProcessingResultData[];
  analysisCount: number | null;
  showSyntheticFeatures?: boolean;
}

export const HistoryView: React.FC<HistoryViewProps> = ({
  history,
  analysisCount,
  showSyntheticFeatures = true,
}) => {
  const [selectedSession, setSelectedSession] = useState<ProcessingResultData | null>(
    history[0] || null
  );
  const [copied, setCopied] = useState<boolean>(false);

  useEffect(() => {
    setSelectedSession((current) => history.find((item) => item.request_id === current?.request_id) || history[0] || null);
  }, [history]);

  const handleCopyJson = () => {
    if (!selectedSession) return;
    navigator.clipboard.writeText(JSON.stringify(selectedSession, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const nasaCount = history.filter((h) => !h.is_synthetic).length;
  const synthCount = history.filter((h) => h.is_synthetic).length;

  return (
    <div className="space-y-6">
      {/* Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard
          label="PERSISTED SESSIONS"
          value={analysisCount ?? 'Unavailable'}
          subtitle="Saved in wedjatx.sqlite3"
          variant="cyan"
        />
        <MetricCard
          label="NASA OSD-575 SESSIONS"
          value={nasaCount}
          subtitle="Among loaded recent sessions"
          variant="normal"
        />
        {showSyntheticFeatures && <MetricCard
          label="SYNTHETIC STREAM RUNS"
          value={synthCount}
          subtitle="Among loaded recent sessions"
          variant="gold"
        />}
        <MetricCard
          label="OFFLINE PERSISTENCE"
          value="SQLite"
          subtitle="Local offline ACID storage"
          variant="slate"
        />
      </div>

      {/* Main Two-Column Layout: Session List & JSON Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Sessions List */}
        <div className="lg:col-span-7 space-y-3">
          <h3 className="text-xs font-mono uppercase tracking-widest text-cyan-300 font-bold flex items-center gap-2">
            <History className="w-4 h-4 text-cyan-400" />
            <span>SQLite Offline Analysis Audit Log</span>
          </h3>

          <div className="p-3 rounded-xl bg-space-900/80 border border-cyan-500/20 backdrop-blur-md overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="py-2 px-3">Timestamp</th>
                  <th className="py-2 px-3">Source Pathway</th>
                  <th className="py-2 px-3">Subject</th>
                  <th className="py-2 px-3">Status</th>
                  <th className="py-2 px-3 text-right">View</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {history.map((session) => {
                  const isSelected = selectedSession?.request_id === session.request_id;
                  return (
                    <tr
                      key={session.request_id || Math.random()}
                      onClick={() => setSelectedSession(session)}
                      className={`cursor-pointer transition-colors ${
                        isSelected
                          ? 'bg-cyan-950/70 text-cyan-200'
                          : 'hover:bg-space-800/50 text-slate-300'
                      }`}
                    >
                      <td className="py-2.5 px-3 font-mono text-[11px] text-slate-400">
                        {session.timestamp?.slice(0, 19).replace('T', ' ') || 'Unavailable'}
                      </td>
                      <td className="py-2.5 px-3">
                        <span
                          className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                            session.is_synthetic
                              ? 'bg-amber-950/60 text-amber-300 border border-amber-500/30'
                              : 'bg-cyan-950/60 text-cyan-300 border border-cyan-500/30'
                          }`}
                        >
                          {session.is_synthetic ? 'SYNTHETIC' : 'NASA LAB'}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-semibold text-slate-200">
                        {session.astronaut_id || session.subject_id || '—'}
                      </td>
                      <td className="py-2.5 px-3">
                        <StatusBadge status={session.processing_status} size="sm" />
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <ChevronRight className={`w-4 h-4 inline-block ${isSelected ? 'text-cyan-400' : 'text-slate-600'}`} />
                      </td>
                    </tr>
                  );
                })}

                {history.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-slate-500">
                      No analysis sessions found in local SQLite database.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column: Full JSON Inspector */}
        <div className="lg:col-span-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-mono uppercase tracking-widest text-cyan-300 font-bold flex items-center gap-2">
              <FileCode className="w-4 h-4 text-cyan-400" />
              <span>Full Audit Payload</span>
            </h3>

            {selectedSession && (
              <button
                onClick={handleCopyJson}
                className="px-2.5 py-1 text-xs font-mono rounded bg-space-800 hover:bg-space-700 text-slate-300 border border-slate-700 transition-colors flex items-center gap-1.5"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied' : 'Copy JSON'}</span>
              </button>
            )}
          </div>

          <div className="p-4 rounded-xl bg-space-950 border border-cyan-500/20 max-h-[560px] overflow-y-auto telemetry-grid">
            {selectedSession ? (
              <div className="space-y-3 text-xs font-mono">
                <div className="p-2.5 rounded bg-space-900 border border-slate-800 space-y-1">
                  <div className="text-slate-400">Request ID: <span className="text-cyan-300">{selectedSession.request_id}</span></div>
                  <div className="text-slate-400">Timestamp: <span className="text-slate-200">{selectedSession.timestamp}</span></div>
                  <div className="text-slate-400">Status: <span className="text-emerald-300">{selectedSession.processing_status}</span></div>
                  <div className="text-slate-400">Subject: <span className="text-slate-200">{selectedSession.astronaut_id || selectedSession.subject_id}</span></div>
                </div>

                <div className="text-slate-400 font-bold uppercase text-[10px] tracking-wider pt-2">
                  Complete Raw Payload:
                </div>
                <pre className="p-3 rounded bg-space-900/90 text-slate-300 overflow-x-auto text-[11px] leading-relaxed border border-slate-800">
                  {JSON.stringify(selectedSession, null, 2)}
                </pre>
              </div>
            ) : (
              <div className="p-12 text-center text-slate-500 text-xs font-mono">
                Select a session on the left to inspect its complete verification audit JSON.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
