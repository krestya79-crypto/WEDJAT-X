import React, { useState, useEffect, useMemo } from 'react';
import {
  Dna,
  Database,
  TrendingUp,
  AlertCircle,
  CheckCircle2,
  Zap,
  HelpCircle,
  FileText,
} from 'lucide-react';
import {
  CrewMember,
  BiomarkerCatalog,
  DiscreteBiomarkerRecord,
  BaselineInfo,
  ProcessingResultData,
} from '../../types';
import { api } from '../../services/api';
import { MetricCard } from '../common/MetricCard';
import { StatusBadge } from '../common/StatusBadge';
import { DisclaimerBanner } from '../common/DisclaimerBanner';

interface BiomarkerLabViewProps {
  crewList: CrewMember[];
  selectedCrew: string;
  onSelectCrew: (crewId: string) => void;
  onRunNasaAnalysis: (crewId: string) => Promise<ProcessingResultData | null>;
  isAnalyzing: boolean;
}

const ALL_MILESTONES = ['L-92', 'L-44', 'L-3', 'R+1', 'R+45', 'R+82', 'R+194'];

export const BiomarkerLabView: React.FC<BiomarkerLabViewProps> = ({
  crewList,
  selectedCrew,
  onSelectCrew,
  onRunNasaAnalysis,
  isAnalyzing,
}) => {
  const [catalog, setCatalog] = useState<BiomarkerCatalog | null>(null);
  const [catalogError, setCatalogError] = useState<{ participant: string; message: string } | null>(null);
  const [selectedPanel, setSelectedPanel] = useState<string>('Comprehensive Metabolic Panel (CMP)');
  const [selectedBiomarker, setSelectedBiomarker] = useState<string>('ALT');
  const [records, setRecords] = useState<DiscreteBiomarkerRecord[]>([]);
  const [baselineInfo, setBaselineInfo] = useState<BaselineInfo | null>(null);
  const [dataStatus, setDataStatus] = useState<'idle' | 'loading' | 'loaded' | 'empty' | 'error'>('idle');
  const [dataError, setDataError] = useState<string | null>(null);
  const [loadedKey, setLoadedKey] = useState<string | null>(null);
  const [statusKey, setStatusKey] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<ProcessingResultData | null>(null);
  const currentCatalog = catalog?.participant_id === selectedCrew ? catalog : null;

  // Load biomarker catalog for this participant
  useEffect(() => {
    const controller = new AbortController();
    setCatalog(null);
    setCatalogError(null);
    async function loadCatalog() {
      try {
        const cat = await api.getBiomarkers(selectedCrew, undefined, controller.signal);
        if (cat.participant_id && cat.participant_id !== selectedCrew) {
          throw new Error(`Biomarker catalog participant mismatch: requested ${selectedCrew}, received ${cat.participant_id}`);
        }
        setCatalog(cat);
        if (cat.panels && cat.panels.length > 0 && !cat.panels.includes(selectedPanel)) {
          setSelectedPanel(cat.panels[0]);
        }
      } catch (e) {
        if (!controller.signal.aborted) {
          console.error('Failed to load biomarker catalog:', e);
          setCatalogError({ participant: selectedCrew, message: e instanceof Error ? e.message : String(e) });
        }
      }
    }
    loadCatalog();
    return () => controller.abort();
  }, [selectedCrew]);

  // Update selected biomarker if not in current panel
  useEffect(() => {
    if (currentCatalog?.by_panel && currentCatalog.by_panel[selectedPanel]) {
      const biomarkersInPanel = currentCatalog.by_panel[selectedPanel];
      if (!biomarkersInPanel.includes(selectedBiomarker) && biomarkersInPanel.length > 0) {
        setSelectedBiomarker(biomarkersInPanel[0]);
      }
    }
  }, [selectedPanel, currentCatalog]);

  // Fetch actual discrete measurements for participant & biomarker
  useEffect(() => {
    const controller = new AbortController();
    setRecords([]);
    setBaselineInfo(null);
    setLoadedKey(null);
    setDataError(null);
    const requestKey = `${selectedCrew}|${selectedPanel}|${selectedBiomarker}`;
    setStatusKey(requestKey);
    async function loadData() {
      if (!selectedCrew || !selectedBiomarker) {
        setDataStatus('empty');
        return;
      }
      setDataStatus('loading');
      try {
        const res = await api.getParticipantData(selectedCrew, selectedBiomarker, selectedPanel, controller.signal);
        if (res.participant_id !== selectedCrew) {
          throw new Error(`Measurement participant mismatch: requested ${selectedCrew}, received ${res.participant_id}`);
        }
        const participantRecords = res.records || [];
        if (participantRecords.some((record) => record.Participant_ID !== selectedCrew)) {
          throw new Error(`API returned records outside selected participant ${selectedCrew}`);
        }
        setRecords(participantRecords);
        setBaselineInfo(res.baseline_info || null);
        setLoadedKey(`${selectedCrew}|${selectedPanel}|${selectedBiomarker}`);
        setDataStatus(participantRecords.length ? 'loaded' : 'empty');
      } catch (e) {
        if (!controller.signal.aborted) {
          console.error('Failed to load participant biomarker data:', e);
          setDataError(e instanceof Error ? e.message : String(e));
          setDataStatus('error');
        }
      }
    }
    loadData();
    return () => controller.abort();
  }, [selectedCrew, selectedBiomarker, selectedPanel]);

  const selectedDataKey = `${selectedCrew}|${selectedPanel}|${selectedBiomarker}`;
  const visibleDataStatus = statusKey === selectedDataKey ? dataStatus : 'loading';
  const dataReady = loadedKey === selectedDataKey;
  const displayedRecords = dataReady ? records : [];
  const displayedBaseline = dataReady ? baselineInfo : null;

  const handleRunAnalysis = async () => {
    const res = await onRunNasaAnalysis(selectedCrew);
    if (res) {
      setAnalysisResult(res);
    }
  };

  // Build milestone aligned observations
  const milestoneMap = useMemo(() => {
    const map = new Map<string, DiscreteBiomarkerRecord>();
    displayedRecords.forEach((r) => map.set(r.Timepoint, r));
    return map;
  }, [displayedRecords]);

  // Scientific SVG Chart calculation
  const chartWidth = 720;
  const chartHeight = 240;
  const padding = { top: 30, right: 30, bottom: 45, left: 60 };
  const innerW = chartWidth - padding.left - padding.right;
  const innerH = chartHeight - padding.top - padding.bottom;

  const validValues = displayedRecords
    .map((r) => r.Measurement_Value)
    .filter((v): v is number => v !== null && v !== undefined && !isNaN(v));

  const baselineMedian = displayedBaseline?.baseline_median ?? null;
  const baselineMad = displayedBaseline?.baseline_mad ?? null;

  const upperBand = baselineMedian !== null && baselineMad !== null ? baselineMedian + 2.5 * baselineMad : null;
  const lowerBand = baselineMedian !== null && baselineMad !== null ? Math.max(0, baselineMedian - 2.5 * baselineMad) : null;

  const axisValues = [...validValues, ...(lowerBand === null ? [] : [lowerBand]), ...(upperBand === null ? [] : [upperBand])];
  const minVal = axisValues.length ? Math.min(...axisValues) : 0;
  const maxVal = axisValues.length ? Math.max(...axisValues) * 1.15 || 1 : 1;
  const measuredMilestoneCount = new Set(displayedRecords.filter((r) => r.Measurement_Value !== null && Number.isFinite(r.Measurement_Value)).map((r) => r.Timepoint)).size;

  const getY = (val: number) => {
    const clamped = Math.max(minVal, Math.min(maxVal, val));
    return padding.top + innerH - ((clamped - minVal) / (maxVal - minVal)) * innerH;
  };

  return (
    <div className="space-y-6">
      {/* Explicit Scientific Provenance Label */}
      <div className="p-4 rounded-xl bg-cyan-950/40 border border-cyan-400/40 shadow-glow-cyan flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-cyan-500/20 text-cyan-400">
            <Database className="w-5 h-5" />
          </div>
          <div>
            <div className="text-sm font-bold font-mono tracking-widest text-cyan-200 uppercase">
              NASA OSD-575 — DISCRETE LABORATORY DATA
            </div>
            <div className="text-xs text-slate-300 font-sans mt-0.5">
              Retrospective laboratory assays for the four Inspiration4 commercial astronauts across seven collection milestones (L-92 through R+194). These are discrete venipuncture assays, NOT continuous wearable signals.
            </div>
          </div>
        </div>
        <span className="text-xs font-mono px-3 py-1 rounded bg-cyan-950 border border-cyan-400 text-cyan-300 shrink-0">
          OSD-575 AUDITED DATASET
        </span>
      </div>

      {/* Control Filters Toolbar */}
      <div className="p-4 rounded-xl bg-space-900/80 border border-cyan-500/20 backdrop-blur-md grid grid-cols-1 sm:grid-cols-3 gap-3">
        {/* Crew Selector */}
        <div>
          <label className="text-[10px] font-mono uppercase text-slate-400 block mb-1">
            Participant / Astronaut:
          </label>
          <select
            value={selectedCrew}
            onChange={(e) => onSelectCrew(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-space-950 border border-cyan-500/30 text-xs font-mono text-cyan-200 focus:outline-none focus:border-cyan-400"
          >
            {crewList.map((c) => (
              <option key={c.participant_id} value={c.participant_id}>
                {c.participant_id} · {c.role} ({c.callsign})
              </option>
            ))}
          </select>
        </div>

        {/* Panel Selector */}
        <div>
          <label className="text-[10px] font-mono uppercase text-slate-400 block mb-1">
            Biomarker Assay Panel:
          </label>
          <select
            value={selectedPanel}
            disabled={!currentCatalog}
            onChange={(e) => setSelectedPanel(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-space-950 border border-cyan-500/30 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-400"
          >
            {currentCatalog?.panels.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>

        {/* Biomarker Selector */}
        <div>
          <label className="text-[10px] font-mono uppercase text-slate-400 block mb-1">
            Specific Biomarker:
          </label>
          <select
            value={selectedBiomarker}
            disabled={!currentCatalog}
            onChange={(e) => setSelectedBiomarker(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-space-950 border border-cyan-500/30 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-400"
          >
            {currentCatalog?.by_panel[selectedPanel]?.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
        </div>
      </div>

      {!currentCatalog && catalogError?.participant !== selectedCrew && <div role="status" className="rounded border border-cyan-500/30 bg-space-900 px-4 py-3 text-xs font-mono text-cyan-200">Loading biomarker catalog for {selectedCrew}…</div>}
      {!currentCatalog && catalogError?.participant === selectedCrew && <div role="alert" className="rounded border border-rose-500/40 bg-rose-950/40 px-4 py-3 text-xs font-mono text-rose-200">Could not load biomarker catalog for {selectedCrew}: {catalogError.message}</div>}
      {visibleDataStatus === 'loading' && <div role="status" className="rounded border border-cyan-500/30 bg-space-900 px-4 py-3 text-xs font-mono text-cyan-200">Loading NASA measurements for {selectedCrew}…</div>}
      {visibleDataStatus === 'error' && <div role="alert" className="rounded border border-rose-500/40 bg-rose-950/40 px-4 py-3 text-xs font-mono text-rose-200">Could not load measurements for {selectedCrew}: {dataError || 'Unknown request error'}</div>}
      {visibleDataStatus === 'empty' && dataReady && <div role="status" className="rounded border border-amber-500/40 bg-amber-950/30 px-4 py-3 text-xs font-mono text-amber-100">NO MEASUREMENT AVAILABLE — no {selectedBiomarker} records for {selectedCrew} in {selectedPanel}.</div>}
      {visibleDataStatus === 'loaded' && dataReady && validValues.length === 0 && <div role="status" className="rounded border border-amber-500/40 bg-amber-950/30 px-4 py-3 text-xs font-mono text-amber-100">NO MEASUREMENT AVAILABLE — records exist for {selectedCrew}, but every selected value is missing.</div>}

      {/* Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard
          label="PREFLIGHT BASELINE MEDIAN"
          value={visibleDataStatus === 'loading' ? 'Loading…' : displayedBaseline ? displayedBaseline.baseline_median.toFixed(2) : 'NO MEASUREMENT AVAILABLE'}
          unit={displayedBaseline?.measurement_unit}
          subtitle={`${displayedBaseline?.preflight_samples ?? 'Unavailable'} preflight samples (L-92..L-3)`}
          variant="cyan"
        />
        <MetricCard
          label="ROBUST DISPERSION (MAD)"
          value={displayedBaseline ? displayedBaseline.baseline_mad.toFixed(3) : 'NO MEASUREMENT AVAILABLE'}
          subtitle="Median Absolute Deviation × 1.4826"
          variant="gold"
        />
        <MetricCard
          label="OBSERVED MILESTONES"
          value={visibleDataStatus === 'loading' ? 'Loading…' : measuredMilestoneCount}
          unit="/ 7 Milestones"
          subtitle="Discrete venipuncture collection"
          variant="normal"
        />
        <MetricCard
          label="MISSING MILESTONES"
          value={visibleDataStatus === 'loading' ? 'Loading…' : ALL_MILESTONES.length - measuredMilestoneCount}
          subtitle="Truthful missing-data representation"
          variant={visibleDataStatus === 'loading' || ALL_MILESTONES.length - measuredMilestoneCount > 0 ? 'alert' : 'normal'}
        />
      </div>

      {/* Interactive Scientific Biomarker Chart */}
      <div className="p-4 rounded-xl bg-space-900/80 border border-cyan-500/20 backdrop-blur-md space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-xs font-mono uppercase tracking-widest text-cyan-300 font-bold">
              LONGITUDINAL MILESTONE TRAJECTORY · {selectedBiomarker}
            </h3>
            <span className="text-[11px] text-slate-400 font-sans">
              Solid line represents personal preflight median. Cyan dashed band indicates ±2.5 MAD robust anomaly envelope.
            </span>
          </div>

          <button
            onClick={handleRunAnalysis}
            disabled={isAnalyzing}
            className="px-3 py-1.5 rounded-lg bg-cyan-950 hover:bg-cyan-900 border border-cyan-400/50 text-cyan-200 text-xs font-mono uppercase transition-colors flex items-center gap-1.5 self-start sm:self-auto disabled:opacity-50"
          >
            <Zap className="w-3.5 h-3.5 text-cyan-400" />
            <span>{isAnalyzing ? 'Evaluating...' : 'Run NASA Pipeline'}</span>
          </button>
        </div>

        {/* SVG Chart */}
        <div className="w-full overflow-x-auto">
          <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="w-full min-w-[600px] h-60">
            {/* Grid & Axis Lines */}
            <line x1={padding.left} y1={padding.top} x2={chartWidth - padding.right} y2={padding.top} stroke="#1e293b" strokeDasharray="3 3" />
            <line x1={padding.left} y1={padding.top + innerH / 2} x2={chartWidth - padding.right} y2={padding.top + innerH / 2} stroke="#1e293b" strokeDasharray="3 3" />
            <line x1={padding.left} y1={padding.top + innerH} x2={chartWidth - padding.right} y2={padding.top + innerH} stroke="#334155" />

            {/* Baseline MAD Envelope Band */}
            {displayedBaseline && upperBand !== null && lowerBand !== null && (
              <rect
                x={padding.left}
                y={getY(upperBand)}
                width={innerW}
                height={Math.max(2, getY(lowerBand) - getY(upperBand))}
                fill="rgba(0, 240, 255, 0.05)"
                stroke="rgba(0, 240, 255, 0.3)"
                strokeDasharray="4 4"
              />
            )}

            {/* Personal Preflight Median Line */}
            {displayedBaseline && (
              <line
                x1={padding.left}
                y1={getY(baselineMedian)}
                x2={chartWidth - padding.right}
                y2={getY(baselineMedian)}
                stroke="#00f0ff"
                strokeWidth="1.5"
                strokeDasharray="6 3"
              />
            )}

            {/* Milestone Vertical Tick Guides and Labels */}
            {ALL_MILESTONES.map((m, idx) => {
              const x = padding.left + (idx / (ALL_MILESTONES.length - 1)) * innerW;
              const isPreflight = m.startsWith('L');
              return (
                <g key={m}>
                  <line x1={x} y1={padding.top} x2={x} y2={padding.top + innerH} stroke="#1e293b" strokeDasharray="2 2" />
                  <text
                    x={x}
                    y={padding.top + innerH + 18}
                    fill={isPreflight ? '#38bdf8' : '#fbbf24'}
                    fontSize="10"
                    fontFamily="monospace"
                    textAnchor="middle"
                    fontWeight="bold"
                  >
                    {m}
                  </text>
                  <text
                    x={x}
                    y={padding.top + innerH + 30}
                    fill="#64748b"
                    fontSize="8"
                    fontFamily="sans-serif"
                    textAnchor="middle"
                  >
                    {isPreflight ? 'PRE' : 'POST'}
                  </text>
                </g>
              );
            })}

            {/* Connecting Line for observed points */}
            {(() => {
              const observedPoints: { x: number; y: number }[] = [];
              ALL_MILESTONES.forEach((m, idx) => {
                const rec = milestoneMap.get(m);
                if (rec && rec.Measurement_Value !== null && !isNaN(rec.Measurement_Value)) {
                  const x = padding.left + (idx / (ALL_MILESTONES.length - 1)) * innerW;
                  const y = getY(rec.Measurement_Value);
                  observedPoints.push({ x, y });
                }
              });

              if (observedPoints.length < 2) return null;
              const pathStr = observedPoints.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
              return <path d={pathStr} fill="none" stroke="#e2e8f0" strokeWidth="2" strokeDasharray="4 2" opacity="0.6" />;
            })()}

            {/* Discrete Venipuncture Observation Dots or Missing Labels */}
            {ALL_MILESTONES.map((m, idx) => {
              const x = padding.left + (idx / (ALL_MILESTONES.length - 1)) * innerW;
              const rec = milestoneMap.get(m);

              if (rec && rec.Measurement_Value !== null && !isNaN(rec.Measurement_Value)) {
                const y = getY(rec.Measurement_Value);
                const isOutlier =
                  upperBand !== null && lowerBand !== null && (rec.Measurement_Value > upperBand || rec.Measurement_Value < lowerBand);

                return (
                  <g key={m}>
                    <circle
                      cx={x}
                      cy={y}
                      r="6"
                      fill={isOutlier ? '#f43f5e' : '#00f0ff'}
                      stroke="#030712"
                      strokeWidth="2"
                      className="transition-all"
                    />
                    <text
                      x={x}
                      y={y - 10}
                      fill={isOutlier ? '#f43f5e' : '#e2e8f0'}
                      fontSize="10"
                      fontFamily="monospace"
                      textAnchor="middle"
                      fontWeight="bold"
                    >
                      {rec.Measurement_Value.toFixed(1)}
                    </text>
                  </g>
                );
              }

              // Missing milestone indicator
              return (
                <g key={m}>
                  <circle cx={x} cy={padding.top + innerH / 2} r="3" fill="#475569" stroke="#1e293b" />
                  <text
                    x={x}
                    y={padding.top + innerH / 2 - 8}
                    fill="#64748b"
                    fontSize="9"
                    fontFamily="monospace"
                    textAnchor="middle"
                  >
                    NO MEASUREMENT AVAILABLE
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>

      {/* Discrete Milestone Table */}
      <div className="p-4 rounded-xl bg-space-900/80 border border-cyan-500/20 backdrop-blur-md space-y-3">
        <h3 className="text-xs font-mono uppercase tracking-widest text-cyan-300 font-bold">
          DISCRETE VENIPUNCTURE ASSAY AUDIT TRAIL
        </h3>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400">
                <th className="py-2 px-3">Milestone</th>
                <th className="py-2 px-3">Mission Phase</th>
                <th className="py-2 px-3">Measured Value</th>
                <th className="py-2 px-3">Preflight Median</th>
                <th className="py-2 px-3">Robust Z-Score</th>
                <th className="py-2 px-3">Statistical Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {ALL_MILESTONES.map((m) => {
                const rec = milestoneMap.get(m);
                const val = rec?.Measurement_Value;
                const isObserved = val !== null && val !== undefined && !isNaN(val);
                const robustZ = isObserved && displayedBaseline && displayedBaseline.baseline_mad > 0
                  ? (val - displayedBaseline.baseline_median) / displayedBaseline.baseline_mad
                  : null;

                return (
                  <tr key={m} className="hover:bg-space-800/50 transition-colors">
                    <td className="py-2 px-3 font-bold text-cyan-300">{m}</td>
                    <td className="py-2 px-3 text-slate-400">
                      {m.startsWith('L') ? 'Preflight Baseline' : 'Postflight Return'}
                    </td>
                    <td className="py-2 px-3">
                      {isObserved ? (
                        <span className="font-semibold text-slate-100">
                          {val.toFixed(2)} {rec.Measurement_Unit}
                        </span>
                      ) : (
                        <span className="text-slate-500 italic">NO MEASUREMENT AVAILABLE</span>
                      )}
                    </td>
                    <td className="py-2 px-3 text-slate-400">
                      {displayedBaseline ? `${displayedBaseline.baseline_median.toFixed(2)} ${displayedBaseline.measurement_unit}` : 'NO MEASUREMENT AVAILABLE'}
                    </td>
                    <td className="py-2 px-3">
                      {robustZ !== null ? (
                        <span className={Math.abs(robustZ) > 2.5 ? 'text-rose-400 font-bold' : 'text-slate-300'}>
                          {robustZ > 0 ? `+${robustZ.toFixed(2)}` : robustZ.toFixed(2)}
                        </span>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>
                    <td className="py-2 px-3">
                      {isObserved ? (
                        robustZ !== null && Math.abs(robustZ) > 2.5 ? (
                          <StatusBadge status="ATTENTION" size="sm" />
                        ) : (
                          <StatusBadge status="NORMAL" size="sm" />
                        )
                      ) : (
                        <StatusBadge status="INSUFFICIENT_DATA" size="sm" />
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
