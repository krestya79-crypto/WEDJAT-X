import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Header } from './components/common/Header';
import { Sidebar, TabId } from './components/common/Sidebar';
import { MissionControlView } from './components/mission/MissionControlView';
import { AstronautViewer } from './components/astronaut/AstronautViewer';
import { LiveTelemetryView } from './components/telemetry/LiveTelemetryView';
import { BiomarkerLabView } from './components/biomarkers/BiomarkerLabView';
import { AlertCenterView } from './components/alerts/AlertCenterView';
import { SensorTrustView } from './components/trust/SensorTrustView';
import { TrajectoryView } from './components/trajectory/TrajectoryView';
import { HistoryView } from './components/history/HistoryView';
import { ReviewDetailView } from './components/review/ReviewDetailView';
import { api } from './services/api';
import {
  SystemStatusData,
  CrewMember,
  ProcessingResultData,
  AlertEvidence,
  SyntheticScenarioSummary,
} from './types';

interface PersistedTrustData {
  is_synthetic: boolean;
  timestamp: string;
  request_id: string;
  sensor_trust: Record<string, unknown>;
}

export function App() {
  const [activeTab, setActiveTab] = useState<TabId>('mission');
  const [reviewAlertId, setReviewAlertId] = useState<string | null>(() => {
    const match = window.location.pathname.match(/^\/review\/([^/]+)\/?$/);
    return match ? decodeURIComponent(match[1]) : null;
  });
  const [selectedCrew, setSelectedCrew] = useState<string>('');
  const [crewList, setCrewList] = useState<CrewMember[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatusData | null>(null);
  const [latestResult, setLatestResult] = useState<ProcessingResultData | null>(null);
  const [recentAlerts, setRecentAlerts] = useState<AlertEvidence[]>([]);
  const [scenarios, setScenarios] = useState<SyntheticScenarioSummary[]>([]);
  const [history, setHistory] = useState<ProcessingResultData[]>([]);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [analysisCount, setAnalysisCount] = useState<number | null>(null);
  const [activeAlertCount, setActiveAlertCount] = useState<number | null>(null);
  const [totalAlertCount, setTotalAlertCount] = useState<number | null>(null);
  const [latestSensorTrust, setLatestSensorTrust] = useState<PersistedTrustData | null>(null);
  const refreshInFlight = useRef(false);
  const refreshQueued = useRef(false);
  const mounted = useRef(true);
  const refreshController = useRef<AbortController | null>(null);

  // Core Data Fetcher
  const loadSystemData = useCallback(async () => {
    if (refreshInFlight.current) { refreshQueued.current = true; return; }
    refreshInFlight.current = true;
    const controller = new AbortController();
    refreshController.current = controller;
    if (mounted.current) setIsRefreshing(true);
    try {
      const [statusRes, crewRes, alertsRes, latestRes, scenariosRes, historyRes, metricsRes] =
        await Promise.allSettled([
          api.getSystemStatus(controller.signal),
          api.getCrewParticipants(controller.signal),
          api.getRecentAlerts(50, undefined, undefined, controller.signal),
          api.getLatestAnalysis(controller.signal),
          api.getScenarios(controller.signal),
          api.getHistory(50, undefined, controller.signal),
          api.getMetrics(controller.signal),
        ]);

      if (!mounted.current) return;

      if (statusRes.status === 'fulfilled') {
        setSystemStatus(statusRes.value);
      }

      if (crewRes.status === 'fulfilled' && crewRes.value?.length > 0) {
        setCrewList(crewRes.value);
        setSelectedCrew((current) => current || crewRes.value[0].participant_id);
      }

      if (alertsRes.status === 'fulfilled') {
        setRecentAlerts(alertsRes.value || []);
      }
      if (latestRes.status === 'fulfilled' && latestRes.value) {
        setLatestResult((current) => !current || latestRes.value!.timestamp >= current.timestamp ? latestRes.value : current);
      }

      if (scenariosRes.status === 'fulfilled' && scenariosRes.value) {
        setScenarios(scenariosRes.value);
      }

      if (historyRes.status === 'fulfilled' && historyRes.value) {
        setHistory(historyRes.value);
      }
      if (metricsRes.status === 'fulfilled') {
        setAnalysisCount(metricsRes.value.analysis_count);
        setActiveAlertCount(metricsRes.value.active_alert_count);
        setTotalAlertCount(metricsRes.value.alert_record_count);
        const trust = metricsRes.value.latest_sensor_trust as PersistedTrustData | null;
        if (trust?.is_synthetic && trust.sensor_trust) {
          setLatestSensorTrust((current) => !current || Date.parse(trust.timestamp) >= Date.parse(current.timestamp) ? trust : current);
        }
      }
      const failures = [statusRes, crewRes, alertsRes, latestRes, scenariosRes, historyRes, metricsRes]
        .filter((item) => item.status === 'rejected');
      setIsConnected(failures.length === 0);
      setConnectionError(failures.length ? `${failures.length} dashboard request(s) failed; showing last successful data.` : null);
      if (!failures.length) setLastUpdated(new Date());
    } catch (e) {
      console.error('System synchronization error:', e);
      if (mounted.current) {
        setIsConnected(false);
        setConnectionError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      refreshInFlight.current = false;
      refreshController.current = null;
      if (mounted.current) setIsRefreshing(false);
      if (mounted.current && refreshQueued.current) {
        refreshQueued.current = false;
        window.setTimeout(() => void loadSystemData(), 0);
      }
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void loadSystemData();
    const timer = window.setInterval(() => void loadSystemData(), 5000);
    return () => { mounted.current = false; window.clearInterval(timer); refreshController.current?.abort(); };
  }, [loadSystemData]);

  useEffect(() => {
    const onPopState = () => {
      const match = window.location.pathname.match(/^\/review\/([^/]+)\/?$/);
      setReviewAlertId(match ? decodeURIComponent(match[1]) : null);
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  const openReview = (alertId: string) => {
    window.history.pushState({}, '', `/review/${encodeURIComponent(alertId)}`);
    setReviewAlertId(alertId);
  };
  const closeReview = () => {
    window.history.pushState({}, '', '/');
    setReviewAlertId(null);
    setActiveTab('alerts');
  };

  // Action: Run NASA Analysis for specific participant
  const handleRunNasaAnalysis = async (crewId: string): Promise<ProcessingResultData | null> => {
    setIsAnalyzing(true);
    try {
      const res = await api.runNasaAnalysis(crewId);
      setLatestResult(res);
      await loadSystemData();
      return res;
    } catch (e) {
      console.error('NASA Analysis execution failed:', e);
      alert(`NASA Analysis error: ${e instanceof Error ? e.message : String(e)}`);
      return null;
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Action: Run Synthetic Wearable Analysis
  const handleRunWearableAnalysis = async (scenario: string): Promise<ProcessingResultData | null> => {
    setIsAnalyzing(true);
    try {
      const res = await api.runWearableAnalysis(scenario);
      setLatestResult(res);
      await loadSystemData();
      return res;
    } catch (e) {
      console.error('Wearable Analysis execution failed:', e);
      alert(`Wearable Analysis error: ${e instanceof Error ? e.message : String(e)}`);
      return null;
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="min-h-screen bg-space-950 text-slate-100 flex flex-col font-sans selection:bg-cyan-500/30 selection:text-cyan-200 telemetry-grid">
      {/* Aerospace Mission Control Header */}
      <Header
        systemStatus={systemStatus}
        activeAlertCount={
          activeAlertCount
        }
        selectedCrew={selectedCrew}
        onSelectCrew={setSelectedCrew}
        crewList={crewList}
        isRefreshing={isRefreshing}
        onRefresh={loadSystemData}
        isConnected={isConnected}
        connectionError={connectionError}
        lastUpdated={lastUpdated}
      />

      {/* Main Mission Control Shell */}
      <div className="flex-1 flex flex-col lg:flex-row w-full max-w-[1780px] mx-auto">
        {/* Navigation Sidebar */}
        <Sidebar
          activeTab={activeTab}
              onSelectTab={setActiveTab}
            activeAlertCount={activeAlertCount ?? 0}
        />

        {/* Dynamic Content Viewport */}
        <main className="flex-1 p-4 lg:p-6 overflow-y-auto">
          {reviewAlertId && <ReviewDetailView alertId={reviewAlertId} onBack={closeReview} />}
          {!reviewAlertId && <>
          {activeTab === 'mission' && (
            <MissionControlView
              systemStatus={systemStatus}
              crewList={crewList}
              selectedCrew={selectedCrew}
              onSelectCrew={setSelectedCrew}
              totalAlertCount={totalAlertCount}
              latestResult={latestResult}
              recentAlerts={recentAlerts}
              activeAlertCount={activeAlertCount}
              onRunNasaAnalysis={handleRunNasaAnalysis}
              onRunWearableAnalysis={handleRunWearableAnalysis}
              isAnalyzing={isAnalyzing}
              onNavigateTab={setActiveTab}
              onOpenReview={openReview}
            />
          )}

          {activeTab === 'astronaut' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-mono uppercase tracking-widest text-cyan-300 font-bold">
                    3D HOLOGRAPHIC ASTRONAUT MONITORING SUITE
                  </h2>
                  <p className="text-xs text-slate-400 font-sans mt-0.5">
                    Interactive spatial display. Participant-specific continuous wearable data is not available in the NASA laboratory records.
                  </p>
                </div>
              </div>
              <AstronautViewer
                isSynthetic={false}
                participantId={selectedCrew}
                analysisResult={latestResult}
              />
            </div>
          )}

          {activeTab === 'telemetry' && (
            <LiveTelemetryView
              scenarios={scenarios}
              onAnalyzeScenario={handleRunWearableAnalysis}
              isAnalyzing={isAnalyzing}
            />
          )}

          {activeTab === 'biomarkers' && (
            <BiomarkerLabView
              crewList={crewList}
              selectedCrew={selectedCrew}
              onSelectCrew={setSelectedCrew}
              onRunNasaAnalysis={handleRunNasaAnalysis}
              isAnalyzing={isAnalyzing}
            />
          )}

          {activeTab === 'alerts' && (
            <AlertCenterView
              alerts={recentAlerts}
              onRefreshAlerts={loadSystemData}
              onOpenReview={openReview}
            />
          )}

          {activeTab === 'trust' && (
              <SensorTrustView trustData={latestSensorTrust} />
          )}

          {activeTab === 'trajectory' && (
            <TrajectoryView
              crewList={crewList}
              selectedCrew={selectedCrew}
              onSelectCrew={setSelectedCrew}
            />
          )}

          {activeTab === 'history' && (
            <HistoryView history={history} analysisCount={analysisCount} />
          )}
          </>}
        </main>
      </div>

      {/* Global Aerospace Footer */}
      <footer className="w-full bg-space-950/95 border-t border-cyan-500/15 py-3 px-6 text-center text-[10px] font-mono text-slate-500 flex flex-col sm:flex-row items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-cyan-400 font-bold">WEDJAT-X</span>
          <span>·</span>
          <span>AEROSPACE MEDICAL MISSION CONTROL</span>
          <span>·</span>
          <span className="text-amber-400/80">NASA SPACE APPS CHALLENGE</span>
        </div>
        <div className="text-slate-400">
          OFFLINE RESEARCH DECISION SUPPORT · HUMAN MEDICAL REVIEW MANDATORY · OSD-575 RETROSPECTIVE
        </div>
      </footer>
    </div>
  );
}

export default App;
