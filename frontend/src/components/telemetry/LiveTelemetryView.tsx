import React, { useState, useEffect, useMemo } from 'react';
import {
  Activity,
  Heart,
  Wind,
  Radio,
  AlertTriangle,
  Play,
  RotateCcw,
  Zap,
  Info,
  CheckCircle2,
} from 'lucide-react';
import {
  SyntheticScenarioSummary,
  SyntheticTelemetryRecord,
  ProcessingResultData,
} from '../../types';
import { api } from '../../services/api';
import { MetricCard } from '../common/MetricCard';
import { StatusBadge } from '../common/StatusBadge';

interface LiveTelemetryViewProps {
  scenarios: SyntheticScenarioSummary[];
  onAnalyzeScenario: (scenarioName: string) => Promise<ProcessingResultData | null>;
  isAnalyzing: boolean;
}

// Crisp SVG Time-Series Chart Component with Missing-Data Gap Preservation
const TelemetryChart: React.FC<{
  title: string;
  data: { timestamp: string; value: number | null }[];
  unit: string;
  color: string;
  glowColor: string;
}> = ({ title, data, unit, color, glowColor }) => {
  const width = 640;
  const height = 150;
  const padding = { top: 15, right: 20, bottom: 25, left: 45 };

  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;
  const values = data.map((d) => d.value).filter((v): v is number => typeof v === 'number' && Number.isFinite(v));
  const dataMin = values.length ? Math.min(...values) : 0;
  const dataMax = values.length ? Math.max(...values) : 1;
  const rangePadding = dataMax === dataMin ? Math.max(Math.abs(dataMin) * 0.05, 1) : (dataMax - dataMin) * 0.1;
  const minVal = dataMin - rangePadding;
  const maxVal = dataMax + rangePadding;

  // Build segments separated by null/missing values
  const segments: { x: number; y: number }[][] = [];
  let currentSegment: { x: number; y: number }[] = [];

  data.forEach((d, idx) => {
    const x = padding.left + (idx / Math.max(1, data.length - 1)) * chartW;
    if (d.value === null || d.value === undefined || isNaN(d.value)) {
      if (currentSegment.length > 0) {
        segments.push(currentSegment);
        currentSegment = [];
      }
    } else {
      const clamped = Math.max(minVal, Math.min(maxVal, d.value));
      const y = padding.top + chartH - ((clamped - minVal) / (maxVal - minVal)) * chartH;
      currentSegment.push({ x, y });
    }
  });
  if (currentSegment.length > 0) segments.push(currentSegment);


  return (
    <div className="p-3.5 rounded-lg bg-space-950/80 border border-slate-800 space-y-2">
      <div className="flex items-center justify-between text-xs font-mono">
        <span className="text-slate-300 font-semibold">{title}</span>
        <span className="text-slate-400">Unit: {unit}</span>
      </div>

      <div className="relative w-full overflow-hidden">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-36">
          {/* Subtle Gridlines */}
          <line x1={padding.left} y1={padding.top} x2={width - padding.right} y2={padding.top} stroke="#1e293b" strokeDasharray="3 3" />
          <line x1={padding.left} y1={padding.top + chartH / 2} x2={width - padding.right} y2={padding.top + chartH / 2} stroke="#1e293b" strokeDasharray="3 3" />
          <line x1={padding.left} y1={padding.top + chartH} x2={width - padding.right} y2={padding.top + chartH} stroke="#1e293b" />


          {/* Value Axis Labels */}
          <text x={padding.left - 8} y={padding.top + 4} fill="#64748b" fontSize="10" fontFamily="monospace" textAnchor="end">{maxVal}</text>
          <text x={padding.left - 8} y={padding.top + chartH / 2 + 3} fill="#64748b" fontSize="10" fontFamily="monospace" textAnchor="end">{Math.round((maxVal + minVal) / 2)}</text>
          <text x={padding.left - 8} y={padding.top + chartH + 3} fill="#64748b" fontSize="10" fontFamily="monospace" textAnchor="end">{minVal}</text>

          {/* Data Lines (Respecting Missing Gaps) */}
          {segments.map((seg, sIdx) => {
            const pathData = seg.map((p, pIdx) => `${pIdx === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
            return (
              <g key={sIdx}>
                {/* Glow Filter Line */}
                <path d={pathData} fill="none" stroke={glowColor} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" opacity="0.4" />
                {/* Solid Precision Line */}
                <path d={pathData} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                {/* Data Points */}
                {seg.map((p, pIdx) => (
                  <circle key={pIdx} cx={p.x} cy={p.y} r="2" fill={color} />
                ))}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
};

export const LiveTelemetryView: React.FC<LiveTelemetryViewProps> = ({
  scenarios,
  onAnalyzeScenario,
  isAnalyzing,
}) => {
  const [selectedScenario, setSelectedScenario] = useState<string>('');
  const [records, setRecords] = useState<SyntheticTelemetryRecord[]>([]);
  const [isLoadingData, setIsLoadingData] = useState<boolean>(false);
  const [pipelineResult, setPipelineResult] = useState<ProcessingResultData | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [lastLoadedAt, setLastLoadedAt] = useState<Date | null>(null);

  useEffect(() => {
    if (!selectedScenario && scenarios.length) setSelectedScenario(scenarios[0].filename);
  }, [scenarios, selectedScenario]);

  useEffect(() => {
    const controller = new AbortController();
    async function loadData() {
      if (!selectedScenario) return;
      setIsLoadingData(true);
      setRecords([]);
      setPipelineResult(null);
      setLoadError(null);
      try {
        const res = await api.getScenarioData(selectedScenario, controller.signal);
        if (controller.signal.aborted) return;
        setRecords(res.records || []);
        setLastLoadedAt(new Date());
      } catch (e) {
        if (!controller.signal.aborted) {
          console.error('Failed to load scenario data:', e);
          setLoadError(e instanceof Error ? e.message : String(e));
        }
      } finally {
        if (!controller.signal.aborted) setIsLoadingData(false);
      }
    }
    loadData();
    return () => controller.abort();
  }, [selectedScenario]);

  const hrData = useMemo(() => {
    return records
      .filter((r) => r.sensor_type === 'heart_rate')
      .map((r) => ({ timestamp: r.timestamp, value: r.signal_value }));
  }, [records]);

  const spo2Data = useMemo(() => {
    return records
      .filter((r) => r.sensor_type === 'spo2')
      .map((r) => ({ timestamp: r.timestamp, value: r.signal_value }));
  }, [records]);

  const accelData = useMemo(() => {
    return records
      .filter((r) => r.sensor_type === 'accelerometer')
      .map((r) => ({ timestamp: r.timestamp, value: r.signal_value }));
  }, [records]);

  const handleRunAnalysis = async () => {
    const res = await onAnalyzeScenario(selectedScenario);
    if (res) {
      setPipelineResult(res);
    }
  };

  const missingCount = records.filter((r) => r.signal_value === null || isNaN(r.signal_value as any)).length;
  const currentScenarioMeta = scenarios.find((s) => s.filename === selectedScenario);
  const activePipelineAlerts = pipelineResult?.alert?.active_alerts?.filter(
    (alert) => ['ATTENTION', 'REVIEW', 'CRITICAL'].includes(alert.alert_state)
  );

  return (
    <div className="space-y-6">
      {/* MANDATORY SYNTHETIC SIMULATION PROVENANCE BANNER */}
      <div className="p-4 rounded-xl bg-amber-950/60 border-2 border-amber-500/80 shadow-[0_0_25px_rgba(245,158,11,0.25)] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-amber-500/20 text-amber-400">
            <Radio className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="text-sm font-bold font-mono tracking-widest text-amber-300 uppercase">
              SYNTHETIC SIMULATION — NOT NASA ASTRONAUT TELEMETRY
            </div>
            <div className="text-xs text-amber-200/80 font-sans mt-0.5">
              Stored finite test scenarios with verified <code className="bg-amber-950 px-1 py-0.5 rounded font-mono">is_synthetic=True</code> provenance. This is not a live feed and is not assigned to C001–C004; participant selection does not change this simulation. Missing values remain data dropouts.
            </div>
          </div>
        </div>
        <span className="text-xs font-mono font-semibold px-3 py-1 rounded bg-amber-900/80 border border-amber-400 text-amber-200 shrink-0">
          SYNTHETIC TEST STREAM
        </span>
      </div>

      {/* Scenario Selector & Controls Bar */}
      <div className="p-4 rounded-xl bg-space-900/80 border border-cyan-500/20 backdrop-blur-md flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <label className="text-xs font-mono text-cyan-300 uppercase tracking-wider">
            Select Simulation Scenario:
          </label>
          <select
            value={selectedScenario}
            onChange={(e) => setSelectedScenario(e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-space-950 border border-cyan-500/30 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-400"
          >
            {scenarios.map((s) => (
              <option key={s.filename} value={s.filename}>
                {s.scenario_name} ({s.total_samples} samples)
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleRunAnalysis}
            disabled={isAnalyzing || isLoadingData}
            className="px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-cyan-600 hover:from-cyan-400 hover:to-cyan-500 text-space-950 font-bold font-mono text-xs uppercase tracking-wider transition-all shadow-[0_0_15px_rgba(0,240,255,0.4)] disabled:opacity-50 flex items-center gap-1.5"
          >
            <Zap className="w-3.5 h-3.5 fill-space-950" />
            <span>{isAnalyzing ? 'Running Analytical Pipeline...' : 'Run Scenario Analysis'}</span>
          </button>
        </div>
      </div>

      {/* Telemetry Metrics Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard
          label="SCENARIO SAMPLES"
          value={records.length}
          subtitle={isLoadingData ? 'Loading selected scenario…' : lastLoadedAt ? `Loaded ${lastLoadedAt.toLocaleTimeString()}` : 'No successful scenario load'}
          variant="cyan"
        />
        <MetricCard
          label="DROPOUT / MISSING"
          value={missingCount}
          unit={`/ ${records.length}`}
          subtitle="Rendered as true gaps"
          variant={missingCount > 0 ? 'alert' : 'normal'}
        />
        <MetricCard
          label="SENSOR CHANNELS"
          value={currentScenarioMeta?.sensor_types.length ?? 'Unavailable'}
          subtitle={currentScenarioMeta?.sensor_types.join(', ') || 'No scenario data'}
          variant="gold"
        />
        <MetricCard
          label="SENSOR RELIABILITY"
          value={
            pipelineResult?.sensor_trust
              ? Object.values(pipelineResult.sensor_trust)[0]?.reliability_category
              : 'EVALUATE'
          }
          subtitle="Hampel & Cross-Check"
          variant="slate"
        />
      </div>

      {loadError && <div role="status" className="rounded border border-rose-500/40 bg-rose-950/40 px-3 py-2 text-xs font-mono text-rose-200">SCENARIO DATA ERROR — {loadError}{lastLoadedAt ? `; last successful load ${lastLoadedAt.toLocaleTimeString()}` : ''}</div>}

      {/* Real-time Multi-Channel Sensor Charts */}
      <div className="space-y-4">
        {/* Heart Rate Chart */}
        <TelemetryChart
          title="ELECTROCARDIOGRAM / OPTICAL HEART RATE (HR)"
          data={hrData}
          unit="BPM"
          color="#f43f5e"
          glowColor="#e11d48"
        />

        {/* SpO2 Chart */}
        <TelemetryChart
          title="PULSE OXIMETRY ARTERIAL OXYGEN SATURATION (SpO₂)"
          data={spo2Data}
          unit="%"
          color="#00f0ff"
          glowColor="#0891b2"
        />

        {/* Accelerometer Chart */}
        <TelemetryChart
          title="TRI-AXIAL ACCELEROMETER MOTION ARTIFACT REJECTION"
          data={accelData}
          unit="g"
          color="#fbbf24"
          glowColor="#d97706"
        />
      </div>

      {/* Real-Time Analytical Results Drawer if available */}
      {pipelineResult && (
        <div className="p-4 rounded-xl bg-space-900/90 border border-cyan-400/40 shadow-glow-cyan space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase text-cyan-300 font-bold flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>Pipeline Analysis Output (Request {pipelineResult.request_id})</span>
            </span>
            <StatusBadge status={pipelineResult.processing_status} size="sm" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs font-mono">
            <div className="p-3 rounded bg-space-950 border border-slate-800">
              <span className="text-slate-400">Alert State:</span>
              <div className="mt-1">
                <StatusBadge
                  status={pipelineResult.alert?.highest_operational_state || 'UNAVAILABLE'}
                  size="sm"
                />
              </div>
            </div>
            <div className="p-3 rounded bg-space-950 border border-slate-800">
              <span className="text-slate-400">Sensor Trust Score:</span>
              <div className="text-base font-bold text-cyan-200 mt-0.5">
                {pipelineResult.sensor_trust
                  ? `${Object.values(pipelineResult.sensor_trust)[0]?.quality_score?.toFixed(1)} / 100`
                  : 'N/A'}
              </div>
            </div>
            <div className="p-3 rounded bg-space-950 border border-slate-800">
              <span className="text-slate-400">Active Operational Alerts:</span>
              <div className="text-base font-bold text-amber-300 mt-0.5">
                {activePipelineAlerts ? activePipelineAlerts.length : 'Unavailable'}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
