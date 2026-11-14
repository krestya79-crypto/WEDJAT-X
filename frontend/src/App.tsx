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

const IS_GITHUB_PAGES_BUILD = import.meta.env.BASE_URL === '/WEDJAT-X/';

const getReviewAlertId = () => {
  const pathname = window.location.pathname;
  const basePath = import.meta.env.BASE_URL;
  const appPath = basePath !== '/' && pathname.startsWith(basePath)
    ? `/${pathname.slice(basePath.length)}`
    : pathname;
  const match = appPath.match(/^\/review\/([^/]+)\/?$/);
  return match ? decodeURIComponent(match[1]) : null;
};

export function App() {
  const [activeTab, setActiveTab] = useState<TabId>('mission');
  const [reviewAlertId, setReviewAlertId] = useState<string | null>(getReviewAlertId);
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
  const [apiAvailability, setApiAvailability] = useState<'checking' | 'available' | 'unavailable'>(
    IS_GITHUB_PAGES_BUILD ? 'checking' : 'available'
  );
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
      if (IS_GITHUB_PAGES_BUILD) {
        const healthRes = await Promise.allSettled([api.getHealth()]);
        if (!mounted.current) return;
        if (healthRes[0].status === 'rejected') {
          const reason = healthRes[0].reason;
          setApiAvailability('unavailable');
          setIsConnected(false);
          setConnectionError(reason instanceof Error ? reason.message : String(reason));
          setLastUpdated(null);
          setSystemStatus(null);
          setCrewList([]);
          setSelectedCrew('');
          setLatestResult(null);
          setRecentAlerts([]);
          setScenarios([]);
          setHistory([]);
          setAnalysisCount(null);
          setActiveAlertCount(null);
          setTotalAlertCount(null);
          setLatestSensorTrust(null);
          return;
        }
        setApiAvailability('available');
      }

      const [statusRes, crewRes, alertsRes, latestRes, scenariosRes, historyRes, metricsRes] =
        await Promise.allSettled([
          api.getSystemStatus(controller.signal),
          api.getCrewParticipants(controller.signal),
          api.getRecentAlerts(50, IS_GITHUB_PAGES_BUILD ? 'NASA_LAB' : undefined, undefined, controller.signal),
          api.getLatestAnalysis(controller.signal, IS_GITHUB_PAGES_BUILD ? 'NASA_LAB' : undefined),
          IS_GITHUB_PAGES_BUILD ? Promise.resolve([] as SyntheticScenarioSummary[]) : api.getScenarios(controller.signal),
          api.getHistory(50, IS_GITHUB_PAGES_BUILD ? 'NASA_LAB' : undefined, controller.signal),
          IS_GITHUB_PAGES_BUILD ? Promise.resolve(null) : api.getMetrics(controller.signal),
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
        setRecentAlerts((alertsRes.value || []).filter((alert) => !IS_GITHUB_PAGES_BUILD || !alert.is_synthetic));
      }
      if (latestRes.status === 'fulfilled' && latestRes.value && (!IS_GITHUB_PAGES_BUILD || !latestRes.value.is_synthetic)) {
        setLatestResult((current) => !current || latestRes.value!.timestamp >= current.timestamp ? latestRes.value : current);
      }

      if (scenariosRes.status === 'fulfilled' && scenariosRes.value) {
        setScenarios(scenariosRes.value);
      }

      if (historyRes.status === 'fulfilled' && historyRes.value) {
        setHistory(historyRes.value.filter((session) => !IS_GITHUB_PAGES_BUILD || !session.is_synthetic));
      }
      if (metricsRes.status === 'fulfilled' && metricsRes.value) {
        setAnalysisCount(metricsRes.value.analysis_count);
        setActiveAlertCount(metricsRes.value.active_alert_count);
        setTotalAlertCount(metricsRes.value.alert_record_count);
        const trust = metricsRes.value.latest_sensor_trust as PersistedTrustData | null;
        if (!IS_GITHUB_PAGES_BUILD && trust?.is_synthetic && trust.sensor_trust) {
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
      setReviewAlertId(getReviewAlertId());
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  const openReview = (alertId: string) => {
    window.history.pushState({}, '', `${import.meta.env.BASE_URL}review/${encodeURIComponent(alertId)}`);
    setReviewAlertId(alertId);
  };
  const closeReview = () => {
    window.history.pushState({}, '', import.meta.env.BASE_URL);
    setReviewAlertId(null);
    setActiveTab('alerts');
  };

  if (IS_GITHUB_PAGES_BUILD && apiAvailability !== 'available') {
    const isChecking = apiAvailability === 'checking';
    return (
      <main className="min-h-screen bg-space-950 text-slate-100 flex items-center justify-center p-6">
        <section
          role={isChecking ? 'status' : 'alert'}
          aria-live="polite"
          className="w-full max-w-xl rounded-xl border border-amber-500/40 bg-space-900 p-8 text-center"
        >
          <p className="font-mono text-xs tracking-widest text-amber-300">
            {isChecking ? 'CONNECTING TO WEDJAT-X API' : 'BACKEND API UNAVAILABLE'}
          </p>
          <h1 className="mt-3 text-2xl font-semibold text-slate-100">
            {isChecking ? 'Checking service availability' : 'Mission data is unavailable'}
          </h1>
          <p className="mt-3 text-sm leading-6 text-slate-300">
            {isChecking
              ? 'The frontend is checking its backend connection.'
              : 'The WEDJAT-X frontend is online, but its backend API could not be reached. No synthetic or placeholder data is being shown.'}
          </p>
          {!isChecking && (
            <button
              type="button"
              onClick={() => void loadSystemData()}
              disabled={isRefreshing}
              className="mt-6 rounded border border-cyan-500/40 px-4 py-2 text-sm text-cyan-200 hover:bg-cyan-950 disabled:opacity-50"
            >
              {isRefreshing ? 'Retrying…' : 'Retry connection'}
            </button>
          )}
        </section>
      </main>
    );
  }

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
          showSyntheticFeatures={!IS_GITHUB_PAGES_BUILD}
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
              showSyntheticFeatures={!IS_GITHUB_PAGES_BUILD}
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

          {!IS_GITHUB_PAGES_BUILD && activeTab === 'telemetry' && (
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
              showSyntheticFeatures={!IS_GITHUB_PAGES_BUILD}
            />
          )}

          {!IS_GITHUB_PAGES_BUILD && activeTab === 'trust' && (
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
            <HistoryView
              history={history}
              analysisCount={analysisCount}
              showSyntheticFeatures={!IS_GITHUB_PAGES_BUILD}
            />
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
