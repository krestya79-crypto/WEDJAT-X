import React, { useState, useEffect, useMemo } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  CheckCircle2,
  AlertTriangle,
  Info,
  Calendar,
} from 'lucide-react';
import { CrewMember, BiomarkerCatalog, DiscreteBiomarkerRecord, BaselineInfo } from '../../types';
import { api } from '../../services/api';
import { MetricCard } from '../common/MetricCard';
import { StatusBadge } from '../common/StatusBadge';

interface TrajectoryViewProps {
  crewList: CrewMember[];
  selectedCrew: string;
  onSelectCrew: (crewId: string) => void;
}

const ALL_MILESTONES = ['L-92', 'L-44', 'L-3', 'R+1', 'R+45', 'R+82', 'R+194'];

export const TrajectoryView: React.FC<TrajectoryViewProps> = ({
  crewList,
  selectedCrew,
  onSelectCrew,
}) => {
  const [catalog, setCatalog] = useState<BiomarkerCatalog | null>(null);
  const [catalogError, setCatalogError] = useState<{ participant: string; message: string } | null>(null);
  const [selectedBiomarker, setSelectedBiomarker] = useState<string>('');
  const [records, setRecords] = useState<DiscreteBiomarkerRecord[]>([]);
  const [baselineInfo, setBaselineInfo] = useState<BaselineInfo | null>(null);
  const [loadedKey, setLoadedKey] = useState<string | null>(null);
  const [dataStatus, setDataStatus] = useState<'idle' | 'loading' | 'loaded' | 'empty' | 'error'>('idle');
  const [dataError, setDataError] = useState<string | null>(null);
  const [statusKey, setStatusKey] = useState<string | null>(null);
  const currentCatalog = catalog?.participant_id === selectedCrew ? catalog : null;

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
        setSelectedBiomarker((current) => cat.biomarkers.includes(current) ? current : cat.biomarkers[0] || '');
      } catch (e) {
        if (!controller.signal.aborted) {
          console.error('Failed to load catalog:', e);
          setCatalogError({ participant: selectedCrew, message: e instanceof Error ? e.message : String(e) });
        }
      }
    }
    loadCatalog();
    return () => controller.abort();
  }, [selectedCrew]);

  useEffect(() => {
    const controller = new AbortController();
    setRecords([]);
    setBaselineInfo(null);
    setLoadedKey(null);
    setDataError(null);
    const requestKey = `${selectedCrew}|${selectedBiomarker}`;
    setStatusKey(requestKey);
    async function loadData() {
      if (!selectedCrew || !selectedBiomarker) {
        setDataStatus('empty');
        return;
      }
      setDataStatus('loading');
      try {
        const res = await api.getParticipantData(selectedCrew, selectedBiomarker, undefined, controller.signal);
        if (res.participant_id !== selectedCrew) {
          throw new Error(`Measurement participant mismatch: requested ${selectedCrew}, received ${res.participant_id}`);
        }
        const participantRecords = res.records || [];
        if (participantRecords.some((record) => record.Participant_ID !== selectedCrew)) {
          throw new Error(`API returned records outside selected participant ${selectedCrew}`);
        }
        setRecords(participantRecords);
        setBaselineInfo(res.baseline_info || null);
        setLoadedKey(`${selectedCrew}|${selectedBiomarker}`);
        setDataStatus(participantRecords.length ? 'loaded' : 'empty');
      } catch (e) {
        if (!controller.signal.aborted) {
          console.error('Failed to load trajectory data:', e);
          setDataError(e instanceof Error ? e.message : String(e));
          setDataStatus('error');
        }
      }
    }
    loadData();
    return () => controller.abort();
  }, [selectedCrew, selectedBiomarker]);

  const selectedDataKey = `${selectedCrew}|${selectedBiomarker}`;
  const visibleDataStatus = statusKey === selectedDataKey ? dataStatus : 'loading';
  const dataReady = loadedKey === selectedDataKey;
  const displayedRecords = dataReady ? records : [];
  const displayedBaseline = dataReady ? baselineInfo : null;

  const milestoneMap = useMemo(() => {
    const map = new Map<string, DiscreteBiomarkerRecord>();
    displayedRecords.forEach((r) => map.set(r.Timepoint, r));
    return map;
  }, [displayedRecords]);

  // Compute descriptive trend
  const postflightRecords = displayedRecords.filter((r) => r.Timepoint.startsWith('R+'));
  const preflightBaseline = displayedBaseline?.baseline_median ?? null;

  let descriptiveTrend = 'INSUFFICIENT_DATA';
  const validPostflightRecords = postflightRecords.filter((r) => r.Measurement_Value !== null && Number.isFinite(r.Measurement_Value));
  const validRecords = displayedRecords.filter((r) => r.Measurement_Value !== null && Number.isFinite(r.Measurement_Value));
  if (validPostflightRecords.length >= 2 && preflightBaseline !== null) {
    const vals = validPostflightRecords.map((r) => r.Measurement_Value as number);
    const firstPost = vals[0];
    const lastPost = vals[vals.length - 1];
    if (Math.abs(lastPost - preflightBaseline) < Math.abs(firstPost - preflightBaseline) * 0.8) {
      descriptiveTrend = 'APPROACHING_BASELINE';
    } else if (lastPost > firstPost * 1.1) {
      descriptiveTrend = 'ELEVATING';
    } else if (lastPost < firstPost * 0.9) {
      descriptiveTrend = 'DECLINING';
    } else {
      descriptiveTrend = 'FLUCTUATING';
    }
  }

  return (
    <div className="space-y-6">
      {/* Scientific Regulatory Guardrail */}
      <div className="p-4 rounded-xl bg-space-900/90 border border-cyan-500/20 backdrop-blur-md flex items-start gap-3">
        <Info className="w-5 h-5 text-cyan-400 mt-0.5 shrink-0" />
        <div className="text-xs text-slate-300 font-sans leading-relaxed">
          <strong className="text-cyan-300 font-mono uppercase tracking-wider block mb-0.5">
            Longitudinal Trajectory Mathematical Notice:
          </strong>
          Trajectory metrics describe mathematical distance to the individual's personal preflight baseline across discrete mission milestones.
          They <strong className="text-cyan-200">must not be characterized as clinical cure or physiological recovery</strong>.
        </div>
      </div>

      {/* Selectors Bar */}
      <div className="p-4 rounded-xl bg-space-900/80 border border-cyan-500/20 backdrop-blur-md flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div>
            <label className="text-[10px] font-mono uppercase text-slate-400 block mb-1">
              Participant:
            </label>
            <select
              value={selectedCrew}
              onChange={(e) => onSelectCrew(e.target.value)}
              className="px-3 py-1.5 rounded-lg bg-space-950 border border-cyan-500/30 text-xs font-mono text-cyan-200 focus:outline-none"
            >
              {crewList.map((c) => (
                <option key={c.participant_id} value={c.participant_id}>
                  {c.participant_id} · {c.role}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-[10px] font-mono uppercase text-slate-400 block mb-1">
              Biomarker:
            </label>
            <select
              value={selectedBiomarker}
              disabled={!currentCatalog}
              onChange={(e) => setSelectedBiomarker(e.target.value)}
              className="px-3 py-1.5 rounded-lg bg-space-950 border border-cyan-500/30 text-xs font-mono text-slate-200 focus:outline-none"
            >
              {currentCatalog?.biomarkers?.slice(0, 50).map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>
          </div>
        </div>

        <StatusBadge status={descriptiveTrend} size="md" />
      </div>

      {!currentCatalog && catalogError?.participant !== selectedCrew && <div role="status" className="rounded border border-cyan-500/30 bg-space-900 px-4 py-3 text-xs font-mono text-cyan-200">Loading biomarker catalog for {selectedCrew}…</div>}
      {!currentCatalog && catalogError?.participant === selectedCrew && <div role="alert" className="rounded border border-rose-500/40 bg-rose-950/40 px-4 py-3 text-xs font-mono text-rose-200">Could not load biomarker catalog for {selectedCrew}: {catalogError.message}</div>}
      {visibleDataStatus === 'loading' && <div role="status" className="rounded border border-cyan-500/30 bg-space-900 px-4 py-3 text-xs font-mono text-cyan-200">Loading NASA trajectory for {selectedCrew}…</div>}
      {visibleDataStatus === 'error' && <div role="alert" className="rounded border border-rose-500/40 bg-rose-950/40 px-4 py-3 text-xs font-mono text-rose-200">Could not load trajectory for {selectedCrew}: {dataError || 'Unknown request error'}</div>}
      {visibleDataStatus === 'empty' && dataReady && <div role="status" className="rounded border border-amber-500/40 bg-amber-950/30 px-4 py-3 text-xs font-mono text-amber-100">NO MEASUREMENT AVAILABLE — no {selectedBiomarker} records for {selectedCrew}.</div>}
      {visibleDataStatus === 'loaded' && dataReady && validRecords.length === 0 && <div role="status" className="rounded border border-amber-500/40 bg-amber-950/30 px-4 py-3 text-xs font-mono text-amber-100">NO MEASUREMENT AVAILABLE — records exist for {selectedCrew}, but all selected values are missing.</div>}

      {/* Trajectory Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard
          label="PREFLIGHT BASELINE MEDIAN"
          value={visibleDataStatus === 'loading' ? 'Loading…' : displayedBaseline ? displayedBaseline.baseline_median.toFixed(2) : 'NO MEASUREMENT AVAILABLE'}
          unit={displayedBaseline?.measurement_unit}
          subtitle="Reference baseline point"
          variant="cyan"
        />
        <MetricCard
          label="DESCRIPTIVE TRAJECTORY"
          value={descriptiveTrend.replace('_', ' ')}
          subtitle="Relative to preflight reference"
          variant="gold"
        />
        <MetricCard
          label="POSTFLIGHT MILESTONES"
          value={visibleDataStatus === 'loading' ? 'Loading…' : validPostflightRecords.length}
          unit="/ 4 Observed"
          subtitle="R+1, R+45, R+82, R+194"
          variant="normal"
        />
        <MetricCard
          label="L-92..L-3 SAMPLES"
          value={displayedBaseline?.preflight_samples ?? 'NO MEASUREMENT AVAILABLE'}
          subtitle="Personal baseline collection"
          variant="slate"
        />
      </div>

      {/* Milestone Sequential Cards */}
      <div className="p-4 rounded-xl bg-space-900/80 border border-cyan-500/20 backdrop-blur-md space-y-4">
        <h3 className="text-xs font-mono uppercase tracking-widest text-cyan-300 font-bold">
          CHRONOLOGICAL MISSION MILESTONE OBSERVATIONS
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-7 gap-2.5">
          {ALL_MILESTONES.map((m) => {
            const rec = milestoneMap.get(m);
            const val = rec?.Measurement_Value;
            const isPreflight = m.startsWith('L');
            const delta = val !== null && val !== undefined ? val - preflightBaseline : null;

            return (
              <div
                key={m}
                className={`p-3 rounded-lg border text-center transition-all ${
                  rec
                    ? isPreflight
                      ? 'bg-space-950/80 border-sky-500/30'
                      : 'bg-space-950/80 border-amber-500/30'
                    : 'bg-space-950/40 border-slate-800/60 opacity-60'
                }`}
              >
                <div className="text-[10px] font-mono font-bold text-slate-400">
                  {m}
                </div>
                <div className="text-[9px] font-mono text-slate-500 uppercase">
                  {isPreflight ? 'Preflight' : 'Postflight'}
                </div>

                <div className="text-base font-bold font-mono text-slate-100 my-1.5">
                  {val !== null && val !== undefined ? val.toFixed(1) : 'NO MEASUREMENT AVAILABLE'}
                </div>

                <div className="text-[10px] font-mono">
                  {delta !== null ? (
                    <span className={delta > 0 ? 'text-amber-400' : 'text-sky-400'}>
                      {delta > 0 ? `+${delta.toFixed(1)}` : delta.toFixed(1)}
                    </span>
                  ) : (
                    <span className="text-slate-600">Missing</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
