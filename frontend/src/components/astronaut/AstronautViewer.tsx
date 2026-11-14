import React, { Suspense, useRef, useState, useMemo, useEffect } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Html } from '@react-three/drei';
import * as THREE from 'three';
import { Heart, Wind, Activity, Radio, RotateCcw, Play, Pause, Eye, Dna, X, ChevronDown, AlertTriangle, Database } from 'lucide-react';
import { ReliabilityCategory, DiscreteBiomarkerRecord, ProcessingResultData } from '../../types';
import { api } from '../../services/api';
import { AstronautFallback } from './AstronautFallback';

interface AstronautViewerProps {
  heartRate?: number | null;
  spo2?: number | null;
  activityLevel?: string | null;
  sensorReliability?: ReliabilityCategory | string | null;
  isSynthetic?: boolean;
  participantId?: string;
  analysisResult?: ProcessingResultData | null;
}

type BiomarkerRegion = 'immune' | 'chemistry' | 'cardiovascular';
type RegionDefinition = { id: BiomarkerRegion; label: string; description: string; position: [number, number, number]; matches: (panel: string) => boolean };

const BIOMARKER_REGIONS: RegionDefinition[] = [
  { id: 'immune', label: 'IMMUNE ASSAYS', description: 'Circulating immune signaling proteins; represented centrally for navigation only.', position: [-0.48, 0.82, 0.34], matches: (panel) => panel.toLowerCase().startsWith('immune') },
  { id: 'chemistry', label: 'SYSTEMIC CHEMISTRY', description: 'Blood chemistry assays shown on the torso as systemic evidence; no kidney or liver lesion is inferred.', position: [0.40, 0.40, 0.34], matches: (panel) => panel.toLowerCase().includes('metabolic') },
  { id: 'cardiovascular', label: 'CARDIOVASCULAR-ASSOCIATED', description: 'Circulating proteins from the cardiovascular assay panel; not anatomical imaging.', position: [0.30, 0.98, 0.34], matches: (panel) => panel.toLowerCase().includes('cardiovascular') },
];

const TIMEPOINT_ORDER = ['L-92', 'L-44', 'L-3', 'R+1', 'R+45', 'R+82', 'R+194'];

function resultParticipant(result?: ProcessingResultData | null) {
  return result?.source_type === 'NASA_LAB' && !result.is_synthetic
    ? (result.astronaut_id || result.subject_id || null)
    : null;
}

function formatValue(value: unknown, unit = '') {
  return typeof value === 'number' && Number.isFinite(value) ? `${value.toLocaleString(undefined, { maximumFractionDigits: 4 })}${unit ? ` ${unit}` : ''}` : 'NO MEASUREMENT AVAILABLE';
}

function AnimatedDataLine({ position }: { position: [number, number, number] }) {
  const lineMaterial = useMemo(() => new THREE.LineDashedMaterial({ color: '#67e8f9', dashSize: 0.055, gapSize: 0.045, transparent: true, opacity: 0.68 }), []);
  const lineGeometry = useMemo(() => new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(0, 0.65, 0.34),
    new THREE.Vector3(...position),
  ]), [position]);
  const lineObject = useMemo(() => {
    const line = new THREE.Line(lineGeometry, lineMaterial);
    line.computeLineDistances();
    return line;
  }, [lineGeometry, lineMaterial]);
  useFrame(({ clock }) => {
    lineMaterial.dashSize = 0.045 + (Math.sin(clock.getElapsedTime() * 2.5) + 1) * 0.012;
  });
  return <primitive object={lineObject} />;
}

// Procedural 3D Spacesuit Mesh
function AstronautSuitMesh({
  heartRate,
  spo2,
  sensorReliability,
  regions = [],
  selectedRegion,
  onSelectRegion,
  selectedBiomarker,
  milestone,
}: {
  heartRate?: number | null;
  spo2?: number | null;
  sensorReliability?: string | null;
  regions?: { id: BiomarkerRegion; label: string; measured: number; hasMilestoneEvidence: boolean; anomalyCount: number; position: [number, number, number] }[];
  selectedRegion?: BiomarkerRegion | null;
  onSelectRegion?: (id: BiomarkerRegion) => void;
  selectedBiomarker?: string | null;
  milestone?: string;
}) {
  const suitGroup = useRef<THREE.Group>(null);
  const scanRingRef = useRef<THREE.Mesh>(null);
  const orbitRingRef = useRef<THREE.Group>(null);

  // Materials
  const suitMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: new THREE.Color('#e2e8f0'),
        roughness: 0.35,
        metalness: 0.15,
      }),
    []
  );

  const darkTrimMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: new THREE.Color('#0f172a'),
        roughness: 0.5,
        metalness: 0.8,
      }),
    []
  );

  const visorMaterial = useMemo(
    () =>
      new THREE.MeshPhysicalMaterial({
        color: new THREE.Color('#00e5ff'),
        emissive: new THREE.Color('#005577'),
        emissiveIntensity: 0.4,
        roughness: 0.1,
        metalness: 0.95,
        clearcoat: 1.0,
        clearcoatRoughness: 0.1,
        reflectivity: 0.9,
      }),
    []
  );

  const cyanGlowMaterial = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: new THREE.Color('#00f0ff'),
        wireframe: true,
        transparent: true,
        opacity: 0.4,
      }),
    []
  );

  // Animation loop: subtle breathing, laser scanline sweep, and orbiting data rings
  useFrame((state) => {
    const t = state.clock.getElapsedTime();

    if (suitGroup.current) {
      // Subtle micro-gravity float and respiratory movement
      suitGroup.current.position.y = Math.sin(t * 1.2) * 0.04;
      suitGroup.current.rotation.y = Math.sin(t * 0.4) * 0.05;
    }

    if (scanRingRef.current) {
      // Laser scan sweep: oscillates vertically from feet to helmet
      scanRingRef.current.position.y = -1.2 + Math.sin(t * 1.5) * 1.4;
    }

    if (orbitRingRef.current) {
      orbitRingRef.current.rotation.y = t * 0.6;
      orbitRingRef.current.rotation.x = Math.sin(t * 0.3) * 0.2;
    }
  });

  return (
    <group ref={suitGroup}>
      {/* 1. HELMET & VISOR */}
      <group position={[0, 1.4, 0]}>
        {/* Helmet Sphere */}
        <mesh material={suitMaterial}>
          <sphereGeometry args={[0.32, 32, 32]} />
        </mesh>
        {/* Golden/Cyan Visor */}
        <mesh position={[0, 0.02, 0.14]} material={visorMaterial} rotation={[0.1, 0, 0]}>
          <sphereGeometry args={[0.22, 32, 16, 0, Math.PI * 2, 0, Math.PI * 0.5]} />
        </mesh>
        {/* Comms Earpieces */}
        <mesh position={[0.32, 0, 0]} material={darkTrimMaterial}>
          <cylinderGeometry args={[0.06, 0.06, 0.08, 16]} />
        </mesh>
        <mesh position={[-0.32, 0, 0]} material={darkTrimMaterial}>
          <cylinderGeometry args={[0.06, 0.06, 0.08, 16]} />
        </mesh>
        {/* Neck Seal Collar */}
        <mesh position={[0, -0.28, 0]} material={darkTrimMaterial}>
          <cylinderGeometry args={[0.25, 0.28, 0.1, 24]} />
        </mesh>
      </group>

      {/* 2. TORSO & LIFE SUPPORT SYSTEM (EPLSS) */}
      <group position={[0, 0.65, 0]}>
        {/* Main Chest Body */}
        <mesh material={suitMaterial}>
          <boxGeometry args={[0.7, 0.85, 0.45]} />
        </mesh>

        {/* Chest Display & Control Module (DCM) */}
        <group position={[0, 0.08, 0.25]}>
          <mesh material={darkTrimMaterial}>
            <boxGeometry args={[0.42, 0.38, 0.12]} />
          </mesh>
          {/* Cyan DCM Screen */}
          <mesh position={[0, 0.04, 0.07]}>
            <planeGeometry args={[0.3, 0.18]} />
            <meshBasicMaterial color="#00f0ff" />
          </mesh>
          {/* Pressure / O2 dials */}
          <mesh position={[-0.1, -0.1, 0.07]}>
            <circleGeometry args={[0.04, 16]} />
            <meshBasicMaterial color="#fbbf24" />
          </mesh>
          <mesh position={[0.1, -0.1, 0.07]}>
            <circleGeometry args={[0.04, 16]} />
            <meshBasicMaterial color="#38bdf8" />
          </mesh>
        </group>

        {/* Primary Life Support Backpack (EPLSS) */}
        <group position={[0, 0.08, -0.32]}>
          <mesh material={darkTrimMaterial}>
            <boxGeometry args={[0.62, 0.95, 0.28]} />
          </mesh>
          {/* Oxygen Cylinder 1 */}
          <mesh position={[-0.18, 0.1, -0.05]} material={suitMaterial}>
            <cylinderGeometry args={[0.1, 0.1, 0.7, 16]} />
          </mesh>
          {/* Oxygen Cylinder 2 */}
          <mesh position={[0.18, 0.1, -0.05]} material={suitMaterial}>
            <cylinderGeometry args={[0.1, 0.1, 0.7, 16]} />
          </mesh>
        </group>

        {/* Shoulder Conduits */}
        <mesh position={[-0.38, 0.32, 0]} rotation={[0, 0, 0.4]} material={suitMaterial}>
          <sphereGeometry args={[0.18, 16, 16]} />
        </mesh>
        <mesh position={[0.38, 0.32, 0]} rotation={[0, 0, -0.4]} material={suitMaterial}>
          <sphereGeometry args={[0.18, 16, 16]} />
        </mesh>
      </group>

      {/* 3. ARMS */}
      {/* Left Arm */}
      <group position={[-0.48, 0.7, 0]}>
        <mesh position={[-0.05, -0.22, 0]} material={suitMaterial}>
          <cylinderGeometry args={[0.12, 0.11, 0.42, 16]} />
        </mesh>
        {/* Elbow Joint */}
        <mesh position={[-0.05, -0.45, 0]} material={darkTrimMaterial}>
          <sphereGeometry args={[0.11, 16, 16]} />
        </mesh>
        {/* Forearm & Wrist Telemetry Pad */}
        <mesh position={[-0.05, -0.7, 0.05]} rotation={[0.4, 0, 0]} material={suitMaterial}>
          <cylinderGeometry args={[0.11, 0.09, 0.4, 16]} />
        </mesh>
        {/* Wrist Computer Display */}
        <mesh position={[-0.05, -0.72, 0.15]} rotation={[0.4, 0, 0]}>
          <boxGeometry args={[0.14, 0.08, 0.04]} />
          <meshBasicMaterial color="#00f0ff" />
        </mesh>
        {/* Glove */}
        <mesh position={[-0.05, -0.96, 0.15]} material={darkTrimMaterial}>
          <boxGeometry args={[0.12, 0.16, 0.1]} />
        </mesh>
      </group>

      {/* Right Arm */}
      <group position={[0.48, 0.7, 0]}>
        <mesh position={[0.05, -0.22, 0]} material={suitMaterial}>
          <cylinderGeometry args={[0.12, 0.11, 0.42, 16]} />
        </mesh>
        <mesh position={[0.05, -0.45, 0]} material={darkTrimMaterial}>
          <sphereGeometry args={[0.11, 16, 16]} />
        </mesh>
        <mesh position={[0.05, -0.7, 0.05]} rotation={[0.4, 0, 0]} material={suitMaterial}>
          <cylinderGeometry args={[0.11, 0.09, 0.4, 16]} />
        </mesh>
        <mesh position={[0.05, -0.96, 0.15]} material={darkTrimMaterial}>
          <boxGeometry args={[0.12, 0.16, 0.1]} />
        </mesh>
      </group>

      {/* 4. WAIST & LEGS */}
      <group position={[0, 0.1, 0]}>
        {/* Utility Belt */}
        <mesh material={darkTrimMaterial}>
          <cylinderGeometry args={[0.34, 0.32, 0.18, 20]} />
        </mesh>

        {/* Left Leg */}
        <group position={[-0.2, -0.15, 0]}>
          <mesh position={[0, -0.32, 0]} material={suitMaterial}>
            <cylinderGeometry args={[0.15, 0.13, 0.55, 16]} />
          </mesh>
          <mesh position={[0, -0.62, 0]} material={darkTrimMaterial}>
            <sphereGeometry args={[0.13, 16, 16]} />
          </mesh>
          <mesh position={[0, -0.95, 0]} material={suitMaterial}>
            <cylinderGeometry args={[0.13, 0.11, 0.55, 16]} />
          </mesh>
          {/* Boot */}
          <mesh position={[0, -1.28, 0.08]} material={darkTrimMaterial}>
            <boxGeometry args={[0.18, 0.18, 0.34]} />
          </mesh>
        </group>

        {/* Right Leg */}
        <group position={[0.2, -0.15, 0]}>
          <mesh position={[0, -0.32, 0]} material={suitMaterial}>
            <cylinderGeometry args={[0.15, 0.13, 0.55, 16]} />
          </mesh>
          <mesh position={[0, -0.62, 0]} material={darkTrimMaterial}>
            <sphereGeometry args={[0.13, 16, 16]} />
          </mesh>
          <mesh position={[0, -0.95, 0]} material={suitMaterial}>
            <cylinderGeometry args={[0.13, 0.11, 0.55, 16]} />
          </mesh>
          {/* Boot */}
          <mesh position={[0, -1.28, 0.08]} material={darkTrimMaterial}>
            <boxGeometry args={[0.18, 0.18, 0.34]} />
          </mesh>
        </group>
      </group>

      {/* 5. VERTICAL CYAN LASER SCANNING RING */}
      <mesh ref={scanRingRef} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.85, 0.95, 48]} />
        <meshBasicMaterial
          color="#00f0ff"
          side={THREE.DoubleSide}
          transparent
          opacity={0.7}
        />
      </mesh>

      {/* 6. ORBITING HOLOGRAPHIC DATA RINGS */}
      <group ref={orbitRingRef} position={[0, 0.6, 0]}>
        <mesh material={cyanGlowMaterial}>
          <torusGeometry args={[1.3, 0.015, 16, 64]} />
        </mesh>
        <mesh rotation={[Math.PI / 3, 0, 0]} material={cyanGlowMaterial}>
          <torusGeometry args={[1.5, 0.01, 16, 64]} />
        </mesh>
      </group>

      {/* 7. 3D ANATOMICAL HOLOGRAPHIC PINS (HTML OVERLAY) */}
      {regions.map((region) => (
        <React.Fragment key={region.id}>
          <mesh position={region.position}>
            <sphereGeometry args={[0.025, 12, 12]} />
            <meshBasicMaterial color={selectedRegion === region.id ? '#a5f3fc' : region.anomalyCount ? '#fb7185' : '#22d3ee'} />
          </mesh>
          <Html position={region.position} distanceFactor={5.4} center style={{ pointerEvents: 'auto' }}>
            <button
              type="button"
              onClick={(event) => { event.stopPropagation(); onSelectRegion?.(region.id); }}
              aria-label={`${region.label}, ${region.measured} measurements${region.anomalyCount ? `, ${region.anomalyCount} analysis findings` : ''}`}
              className={`whitespace-nowrap rounded-lg border px-2 py-1.5 text-left font-mono shadow-[0_0_14px_#00e5ff44] backdrop-blur-md transition-all ${selectedRegion === region.id ? 'border-cyan-200 bg-cyan-950/95 text-cyan-100 scale-105' : region.anomalyCount ? 'border-rose-400/80 bg-rose-950/90 text-rose-100' : 'border-cyan-500/50 bg-space-950/90 text-cyan-200 hover:border-cyan-200'}`}
            >
              <span className="flex items-center gap-1.5 text-[9px] font-bold"><Dna className="h-3 w-3" />{region.label}</span>
              <span className="block pl-[18px] text-[8px] text-slate-300">{region.measured} measured · {milestone === 'ALL' ? 'all milestones' : milestone}</span>
              <span className={`block pl-[18px] text-[8px] ${region.anomalyCount ? 'text-rose-300' : region.hasMilestoneEvidence ? 'text-emerald-300' : 'text-amber-200'}`}>
                {region.anomalyCount ? `${region.anomalyCount} engine finding${region.anomalyCount === 1 ? '' : 's'}` : region.hasMilestoneEvidence ? 'evidence available' : 'no value at milestone'}
              </span>
              {selectedRegion === region.id && selectedBiomarker && <span className="mt-1 block border-t border-cyan-700/60 pt-1 text-[8px] text-white">SELECTED · {selectedBiomarker}</span>}
            </button>
          </Html>
        </React.Fragment>
      ))}

      {regions.filter((region) => selectedRegion === region.id).map((region) => <AnimatedDataLine key={`link-${region.id}`} position={region.position} />)}

      {/* Cardiac Chest Node */}
      {heartRate !== null && heartRate !== undefined && <Html position={[0.15, 0.8, 0.3]} distanceFactor={6} center>
        <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-space-950/90 border border-rose-500/80 shadow-[0_0_12px_#f43f5e] backdrop-blur-md pointer-events-none select-none text-[10px] font-mono">
          <Heart className="w-3 h-3 text-rose-400 fill-rose-400 animate-pulse" />
          <span className="text-rose-200 font-bold">
            {heartRate !== null && heartRate !== undefined ? `${heartRate} BPM` : 'Unavailable'}
          </span>
        </div>
      </Html>}

      {/* Pulmonary SpO2 Node */}
      {spo2 !== null && spo2 !== undefined && <Html position={[-0.2, 0.65, 0.3]} distanceFactor={6} center>
        <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-space-950/90 border border-cyan-400/80 shadow-[0_0_12px_#00f0ff] backdrop-blur-md pointer-events-none select-none text-[10px] font-mono">
          <Wind className="w-3 h-3 text-cyan-300" />
          <span className="text-cyan-100 font-bold">
            {spo2 !== null && spo2 !== undefined ? `${spo2}% SpO₂` : 'Unavailable'}
          </span>
        </div>
      </Html>}

      {/* Wrist Kinetic / Sensor Node */}
      {sensorReliability && <Html position={[-0.65, -0.05, 0.2]} distanceFactor={6} center>
        <div className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-space-950/90 border border-emerald-400/70 shadow-[0_0_8px_#34d399] backdrop-blur-md pointer-events-none select-none text-[9px] font-mono text-emerald-300">
          <Radio className="w-2.5 h-2.5 text-emerald-400" />
          <span>{String(sensorReliability || 'UNAVAILABLE').replace('_', ' ')}</span>
        </div>
      </Html>}
    </group>
  );
}

export const AstronautViewer: React.FC<AstronautViewerProps> = ({
  heartRate,
  spo2,
  activityLevel,
  sensorReliability,
  isSynthetic = false,
  participantId,
  analysisResult,
}) => {
  const [autoRotate, setAutoRotate] = useState(true);
  const [force2D, setForce2D] = useState(false);
  const [webglError, setWebglError] = useState(false);
  const [records, setRecords] = useState<DiscreteBiomarkerRecord[]>([]);
  const [dataState, setDataState] = useState<'loading' | 'loaded' | 'error'>('loading');
  const [selectedMilestone, setSelectedMilestone] = useState('ALL');
  const [selectedRegion, setSelectedRegion] = useState<BiomarkerRegion | null>(null);
  const [selectedBiomarker, setSelectedBiomarker] = useState<string | null>(null);
  const controlsRef = useRef<any>(null);

  useEffect(() => {
    const controller = new AbortController();
    setRecords([]);
    setDataState('loading');
    setSelectedMilestone('ALL');
    setSelectedRegion(null);
    setSelectedBiomarker(null);
    if (!participantId) {
      setDataState('loading');
      return () => controller.abort();
    }
    api.getParticipantData(participantId, undefined, undefined, controller.signal).then((response) => {
      if (controller.signal.aborted) return;
      if (response.participant_id !== participantId || response.records.some((record) => record.Participant_ID !== participantId)) {
        throw new Error(`NASA data did not match selected participant ${participantId}`);
      }
      setRecords(response.records);
      setDataState('loaded');
    }).catch((error) => {
      if (controller.signal.aborted) return;
      console.error('Unable to load participant-specific NASA biomarker records:', error);
      setDataState('error');
    });
    return () => controller.abort();
  }, [participantId]);

  const matchingAnalysis = resultParticipant(analysisResult) === participantId ? analysisResult : null;
  const statisticalEvidence = matchingAnalysis?.anomaly_evidence?.statistical || {};
  const bayesianEvidence = matchingAnalysis?.anomaly_evidence?.bayesian || {};
  const activeAlerts = matchingAnalysis?.alert?.active_alerts || [];
  const milestones = useMemo(() => TIMEPOINT_ORDER.filter((timepoint) => records.some((record) => record.Timepoint === timepoint)), [records]);

  const groupedRegions = useMemo(() => BIOMARKER_REGIONS.map((definition) => {
    const categoryRecords = records.filter((record) => definition.matches(record.Panel_Name || ''));
    const biomarkerNames = [...new Set(categoryRecords.map((record) => record.Biomarker_Name))].sort();
    const relevantNames = new Set(biomarkerNames);
    const currentRecords = selectedMilestone === 'ALL' ? categoryRecords : categoryRecords.filter((record) => record.Timepoint === selectedMilestone);
    const statisticalFindings = Object.entries(statisticalEvidence).filter(([key, value]: [string, any]) => {
      const biomarker = value?.biomarker_name || key.split('::')[0];
      return relevantNames.has(biomarker) && value?.is_anomaly === true;
    });
    const bayesianFindings = Object.entries(bayesianEvidence).filter(([key, value]: [string, any]) => {
      const biomarker = value?.biomarker_name || key.split('::')[0];
      return relevantNames.has(biomarker) && value?.is_bayesian_anomaly === true;
    });
    const actualAlerts = activeAlerts.filter((alert: any) => relevantNames.has(alert.measurement_name || alert.biomarker_or_sensor));
    const findingEntries = [...statisticalFindings, ...bayesianFindings];
    const milestoneFindings = selectedMilestone === 'ALL' ? findingEntries : findingEntries.filter(([key, value]: [string, any]) => (value?.timepoint || key.split('::')[1]) === selectedMilestone);
    const milestoneAlerts = selectedMilestone === 'ALL' ? actualAlerts : actualAlerts.filter((alert: any) => !alert.timepoint || alert.timepoint === selectedMilestone);
    return {
      ...definition,
      biomarkerNames,
      measured: categoryRecords.filter((record) => typeof record.Measurement_Value === 'number' && Number.isFinite(record.Measurement_Value)).length,
      currentNames: new Set(currentRecords.filter((record) => typeof record.Measurement_Value === 'number' && Number.isFinite(record.Measurement_Value)).map((record) => record.Biomarker_Name)),
      anomalyNames: new Set([
        ...milestoneFindings.map(([key, value]: [string, any]) => value?.biomarker_name || key.split('::')[0]),
        ...milestoneAlerts.map((alert: any) => alert.measurement_name || alert.biomarker_or_sensor),
      ]),
      findings: findingEntries,
    };
  }), [records, selectedMilestone, statisticalEvidence, bayesianEvidence, activeAlerts]);

  const selectedDefinition = groupedRegions.find((region) => region.id === selectedRegion) || null;
  const availableBiomarkers = selectedDefinition?.biomarkerNames || [];
  const selectedRecords = useMemo(() => records.filter((record) => record.Biomarker_Name === selectedBiomarker), [records, selectedBiomarker]);
  const selectedObservedRecords = selectedRecords.filter((record) => typeof record.Measurement_Value === 'number' && Number.isFinite(record.Measurement_Value));
  const selectedRecord = selectedMilestone === 'ALL'
    ? [...selectedObservedRecords].sort((a, b) => TIMEPOINT_ORDER.indexOf(b.Timepoint) - TIMEPOINT_ORDER.indexOf(a.Timepoint))[0]
    : selectedRecords.find((record) => record.Timepoint === selectedMilestone);
  const baselineValues = selectedRecords.filter((record) => record.Timepoint_Phase?.toUpperCase() === 'PREFLIGHT' && typeof record.Measurement_Value === 'number' && Number.isFinite(record.Measurement_Value)).map((record) => record.Measurement_Value as number).sort((a, b) => a - b);
  const baseline = baselineValues.length ? (baselineValues.length % 2 ? baselineValues[(baselineValues.length - 1) / 2] : (baselineValues[baselineValues.length / 2 - 1] + baselineValues[baselineValues.length / 2]) / 2) : null;
  const currentValue = typeof selectedRecord?.Measurement_Value === 'number' && Number.isFinite(selectedRecord.Measurement_Value) ? selectedRecord.Measurement_Value : null;
  const difference = currentValue !== null && baseline !== null ? currentValue - baseline : null;
  const percentDifference = difference !== null && baseline !== null && baseline !== 0 ? (difference / Math.abs(baseline)) * 100 : null;
  const statistical = selectedRecord ? statisticalEvidence[`${selectedBiomarker}::${selectedRecord.Timepoint}`] : null;
  const bayesian = selectedRecord ? bayesianEvidence[`${selectedBiomarker}::${selectedRecord.Timepoint}`] : null;
  const biomarkerAlerts = activeAlerts.filter((alert: any) => (alert.measurement_name || alert.biomarker_or_sensor) === selectedBiomarker);

  const handleSelectRegion = (id: BiomarkerRegion) => {
    const next = groupedRegions.find((region) => region.id === id);
    setSelectedRegion(id);
    const currentValueNames = next?.currentNames || new Set<string>();
    const selectedFinding = next?.findings.find(([key, value]: [string, any]) => {
      const name = value?.biomarker_name || key.split('::')[0];
      const timepoint = value?.timepoint || key.split('::')[1];
      return next.biomarkerNames.includes(name) && (!selectedMilestone || selectedMilestone === 'ALL' || selectedMilestone === timepoint);
    }) || next?.findings[0];
    const findingName = selectedFinding ? selectedFinding[1]?.biomarker_name || selectedFinding[0].split('::')[0] : null;
    const findingTimepoint = selectedFinding ? selectedFinding[1]?.timepoint || selectedFinding[0].split('::')[1] : null;
    const nextBiomarker = findingName || next?.biomarkerNames.find((name) => currentValueNames.has(name)) || next?.biomarkerNames[0] || null;
    setSelectedBiomarker(nextBiomarker);
    if (findingTimepoint && milestones.includes(findingTimepoint)) setSelectedMilestone(findingTimepoint);
  };

  const handleResetCamera = () => {
    if (controlsRef.current) {
      controlsRef.current.reset();
    }
  };

  if (force2D || webglError) {
    return (
      <div className="relative">
        <AstronautFallback
          heartRate={heartRate}
          spo2={spo2}
          activityLevel={activityLevel}
          sensorReliability={sensorReliability}
          isSynthetic={isSynthetic}
        />
        <div className="absolute top-4 right-4 z-20">
          <button
            onClick={() => setForce2D(false)}
            className="px-2.5 py-1 text-xs font-mono rounded bg-cyan-950/80 border border-cyan-500/40 text-cyan-300 hover:bg-cyan-900 transition-colors"
          >
            Launch 3D Hologram
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="relative w-full h-[540px] rounded-xl bg-space-950 border border-cyan-500/20 overflow-hidden shadow-panel">
      {/* HUD Header Bar */}
      <div className="absolute top-3 left-3 right-3 flex items-center justify-between z-10 pointer-events-none">
        <div className="flex items-center gap-2 pointer-events-auto">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-space-900/80 border border-cyan-500/30 text-cyan-300 text-xs font-mono">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
            <span>{isSynthetic ? 'SYNTHETIC TELEMETRY VIEW' : participantId ? `NASA OSD-575 · ${participantId}` : 'NASA OSD-575 · SELECT PARTICIPANT'}</span>
          </div>
          {isSynthetic && (
            <span className="px-2 py-0.5 rounded bg-amber-950/70 border border-amber-500/40 text-amber-300 text-[10px] font-mono">
              SYNTHETIC SIMULATION
            </span>
          )}
        </div>

        {/* Controls Toolbar */}
        <div className="flex items-center gap-1.5 pointer-events-auto">
          <button
            onClick={() => setAutoRotate(!autoRotate)}
            className={`p-1.5 rounded bg-space-900/80 border text-xs transition-colors ${
              autoRotate
                ? 'border-cyan-400 text-cyan-300 bg-cyan-950/50'
                : 'border-slate-700 text-slate-400 hover:text-slate-200'
            }`}
            title={autoRotate ? 'Pause Auto-Rotation' : 'Resume Auto-Rotation'}
          >
            {autoRotate ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
          </button>

          <button
            onClick={handleResetCamera}
            className="p-1.5 rounded bg-space-900/80 border border-slate-700 text-slate-400 hover:text-slate-200 hover:border-slate-500 text-xs transition-colors"
            title="Reset Camera Orientation"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={() => setForce2D(true)}
            className="px-2 py-1 rounded bg-space-900/80 border border-slate-700 text-slate-300 hover:border-cyan-500/40 hover:text-cyan-300 text-[11px] font-mono transition-colors flex items-center gap-1"
            title="Switch to 2D Biometric Fallback"
          >
            <Eye className="w-3 h-3 text-slate-400" />
            <span>2D HUD</span>
          </button>
        </div>
      </div>

      {/* Three.js Canvas */}
      <Canvas
        camera={{ position: [0, 0.8, 3.8], fov: 42 }}
        className="w-full h-full cursor-grab active:cursor-grabbing"
        onCreated={({ gl }) => {
          gl.setClearColor('#030712', 1);
        }}
        onError={() => setWebglError(true)}
      >
        <ambientLight intensity={0.5} />
        <directionalLight position={[5, 8, 5]} intensity={1.2} />
        <directionalLight position={[-5, -2, -5]} intensity={0.4} color="#00e5ff" />
        <pointLight position={[0, 1.4, 1.2]} intensity={1.5} color="#00f0ff" distance={3} />
        <pointLight position={[0, -1, 1.5]} intensity={0.8} color="#fbbf24" distance={2.5} />

        <Suspense fallback={null}>
          <AstronautSuitMesh
            heartRate={heartRate}
            spo2={spo2}
            sensorReliability={sensorReliability}
            regions={dataState === 'loaded' ? groupedRegions.map((region) => ({
              id: region.id,
              label: region.label,
              measured: region.measured,
              hasMilestoneEvidence: region.currentNames.size > 0,
              anomalyCount: region.anomalyNames.size,
              position: region.position,
            })) : []}
            selectedRegion={selectedRegion}
            onSelectRegion={handleSelectRegion}
            selectedBiomarker={selectedBiomarker}
            milestone={selectedMilestone}
          />
        </Suspense>

        <OrbitControls
          ref={controlsRef}
          enablePan={false}
          enableZoom={true}
          minDistance={2.2}
          maxDistance={5.5}
          maxPolarAngle={Math.PI / 2 + 0.3}
          minPolarAngle={Math.PI / 4}
          autoRotate={autoRotate}
          autoRotateSpeed={0.8}
        />
      </Canvas>

      {/* Participant-specific discrete mission timeline */}
      <div className="absolute bottom-3 left-3 z-20 flex max-w-[58%] items-center gap-2 rounded-lg border border-cyan-500/30 bg-space-950/90 px-3 py-2 font-mono shadow-[0_0_18px_#00e5ff22] backdrop-blur-md">
        <Database className="h-3.5 w-3.5 shrink-0 text-cyan-300" />
        <label htmlFor="astronaut-milestone" className="whitespace-nowrap text-[9px] text-slate-300">{participantId || 'NASA PARTICIPANT'} · COLLECTION</label>
        <select id="astronaut-milestone" value={selectedMilestone} onChange={(event) => setSelectedMilestone(event.target.value)} disabled={dataState !== 'loaded'} className="min-w-0 rounded border border-cyan-500/30 bg-space-900 px-2 py-1 text-[10px] text-cyan-100 outline-none focus:border-cyan-300 disabled:opacity-60">
          <option value="ALL">Latest available</option>
          {milestones.map((timepoint) => <option key={timepoint} value={timepoint}>{timepoint}</option>)}
        </select>
        <span className="hidden text-[8px] text-slate-500 md:inline">DISCRETE LAB DATA</span>
      </div>

      {dataState === 'loading' && <div role="status" className="absolute bottom-[58px] left-3 z-20 rounded border border-cyan-500/30 bg-space-950/90 px-3 py-2 text-[10px] font-mono text-cyan-200">Loading actual NASA records for {participantId || 'selected participant'}…</div>}
      {dataState === 'error' && <div role="alert" className="absolute bottom-[58px] left-3 z-20 rounded border border-amber-500/40 bg-space-950/95 px-3 py-2 text-[10px] font-mono text-amber-100">NASA biomarker records unavailable for {participantId || 'selected participant'}.</div>}

      {/* Detail drawer shows only rows returned for the selected participant. */}
      <aside aria-label="Selected NASA biomarker evidence" className={`absolute right-3 top-14 bottom-14 z-20 w-[min(360px,calc(100%-24px))] overflow-hidden rounded-xl border border-cyan-400/35 bg-space-950/95 shadow-[0_0_28px_#00e5ff22] backdrop-blur-xl transition-all duration-300 ${selectedRegion ? 'translate-x-0 opacity-100' : 'pointer-events-none translate-x-3 opacity-0'}`}>
        {selectedRegion && <div className="flex h-full flex-col">
          <header className="flex items-start justify-between gap-2 border-b border-cyan-500/20 p-3">
            <div>
              <p className="text-[9px] font-mono tracking-widest text-cyan-400">NASA OSD-575 · {participantId}</p>
              <h3 className="mt-1 text-xs font-bold font-mono text-cyan-100">{selectedDefinition?.label}</h3>
              <p className="mt-1 text-[9px] leading-relaxed text-slate-400">{selectedDefinition?.description} Explanatory visualization only; not medical imaging.</p>
            </div>
            <button type="button" onClick={() => setSelectedRegion(null)} aria-label="Close biomarker evidence" className="rounded border border-slate-700 p-1 text-slate-300 hover:border-cyan-400 hover:text-cyan-100"><X className="h-3.5 w-3.5" /></button>
          </header>
          <div className="space-y-3 overflow-y-auto p-3">
            <label className="block text-[9px] font-mono uppercase text-slate-400">Biomarker
              <span className="relative mt-1 block">
                <select value={selectedBiomarker || ''} onChange={(event) => setSelectedBiomarker(event.target.value)} className="w-full appearance-none rounded border border-cyan-500/30 bg-space-900 px-2 py-2 pr-7 text-[10px] text-cyan-100 outline-none focus:border-cyan-300">
                  {availableBiomarkers.map((name) => <option key={name} value={name}>{name}</option>)}
                </select>
                <ChevronDown className="pointer-events-none absolute right-2 top-2 h-3 w-3 text-cyan-300" />
              </span>
            </label>

            {!selectedBiomarker || selectedRecords.length === 0 ? <div className="rounded border border-amber-500/30 bg-amber-950/20 p-3 text-[10px] font-mono text-amber-100">NO MEASUREMENT AVAILABLE for this participant and category.</div> : <>
              <div className="grid grid-cols-2 gap-2">
                <EvidenceValue label={selectedMilestone === 'ALL' ? `LATEST · ${selectedRecord?.Timepoint || '—'}` : selectedMilestone} value={formatValue(currentValue, selectedRecord?.Measurement_Unit || '')} />
                <EvidenceValue label="PREFLIGHT MEDIAN" value={baseline === null ? 'NO BASELINE' : formatValue(baseline, selectedRecord?.Measurement_Unit || '')} />
                <EvidenceValue label="ABSOLUTE DIFFERENCE" value={difference === null ? 'UNAVAILABLE' : formatValue(difference, selectedRecord?.Measurement_Unit || '')} />
                <EvidenceValue label="PERCENT DIFFERENCE" value={percentDifference === null ? 'UNAVAILABLE' : `${percentDifference > 0 ? '+' : ''}${percentDifference.toFixed(2)}%`} />
              </div>
              {selectedRecord && currentValue === null && <p className="rounded border border-amber-500/30 bg-amber-950/20 p-2 text-[9px] font-mono text-amber-100">The selected milestone record exists, but its measured value is missing.</p>}
              <section className="rounded border border-slate-700/70 bg-space-900/60 p-2.5">
                <h4 className="mb-1 text-[9px] font-mono tracking-wider text-cyan-300">AVAILABLE HISTORY · {selectedObservedRecords.length} MEASUREMENTS</h4>
                <div className="space-y-1">
                  {selectedRecords.map((record) => <div key={`${record.Participant_ID}-${record.Biomarker_Name}-${record.Timepoint}`} className={`flex justify-between gap-2 text-[9px] font-mono ${record.Timepoint === selectedRecord?.Timepoint ? 'text-cyan-100' : 'text-slate-400'}`}><span>{record.Timepoint}</span><span>{formatValue(record.Measurement_Value, record.Measurement_Unit)}</span></div>)}
                </div>
              </section>
              <EvidenceBlock title="STATISTICAL ENGINE EVIDENCE" value={statistical} empty="No statistical engine evidence is stored for this biomarker and milestone." />
              <EvidenceBlock title="BAYESIAN ENGINE EVIDENCE" value={bayesian} empty="No Bayesian evidence is stored for this biomarker and milestone." />
              <section className="rounded border border-slate-700/70 bg-space-900/60 p-2.5 text-[9px] font-mono text-slate-300">
                <h4 className="mb-1 text-cyan-300">DATA QUALITY · REVIEW STATE</h4>
                <p>Missing values: {selectedRecords.filter((record) => record.Measurement_Value === null || record.Measurement_Value === undefined).length} / {selectedRecords.length}</p>
                <p>Record validation: {selectedRecord?.Validation_Status || 'not supplied by dataset'}</p>
                <p>Analysis: {matchingAnalysis ? `${matchingAnalysis.processing_status} · ${matchingAnalysis.request_id}` : 'No stored NASA analysis for this participant in the current result context.'}</p>
                <p>Review state: {biomarkerAlerts.length ? biomarkerAlerts.map((alert: any) => alert.alert_state || alert.operational_state || 'FLAGGED').join(', ') : 'No matching stored alert'}</p>
                <p className="mt-2 text-slate-500">NASA OSD-575 contains discrete laboratory assays, not continuous wearable telemetry. Mathematical deviations are not a diagnosis.</p>
              </section>
            </>}
          </div>
        </div>}
      </aside>

      {/* Floating Bottom Telemetry Strip */}
      <div className="absolute bottom-3 left-3 right-3 grid grid-cols-2 md:grid-cols-4 gap-2 z-10 pointer-events-none">
        {heartRate !== null && heartRate !== undefined && <div className="p-2 rounded bg-space-950/80 border border-rose-500/30 backdrop-blur-md pointer-events-auto">
          <div className="flex items-center gap-1 text-[9px] font-mono uppercase text-rose-400">
            <Heart className="w-2.5 h-2.5 text-rose-400" />
            <span>PULSE RATE</span>
          </div>
          <div className="text-base font-bold font-mono text-rose-100">
            {heartRate !== null && heartRate !== undefined ? `${heartRate} BPM` : 'Unavailable'}
          </div>
        </div>}

        {spo2 !== null && spo2 !== undefined && <div className="p-2 rounded bg-space-950/80 border border-cyan-500/30 backdrop-blur-md pointer-events-auto">
          <div className="flex items-center gap-1 text-[9px] font-mono uppercase text-cyan-400">
            <Wind className="w-2.5 h-2.5 text-cyan-400" />
            <span>SpO₂ SATURATION</span>
          </div>
          <div className="text-base font-bold font-mono text-cyan-100">
            {spo2 !== null && spo2 !== undefined ? `${spo2}%` : 'Unavailable'}
          </div>
        </div>}

        {activityLevel !== null && activityLevel !== undefined && <div className="p-2 rounded bg-space-950/80 border border-amber-500/30 backdrop-blur-md pointer-events-auto">
          <div className="flex items-center gap-1 text-[9px] font-mono uppercase text-amber-400">
            <Activity className="w-2.5 h-2.5 text-amber-400" />
            <span>ACTIVITY SENSOR</span>
          </div>
          <div className="text-base font-bold font-mono text-amber-100">
            {activityLevel ?? 'Unavailable'}
          </div>
        </div>}

        {sensorReliability !== null && sensorReliability !== undefined && <div className="p-2 rounded bg-space-950/80 border border-emerald-500/30 backdrop-blur-md pointer-events-auto">
          <div className="flex items-center gap-1 text-[9px] font-mono uppercase text-emerald-400">
            <Radio className="w-2.5 h-2.5 text-emerald-400" />
            <span>SENSOR RELIABILITY</span>
          </div>
          <div className="text-base font-bold font-mono text-emerald-100">
            {String(sensorReliability || 'UNAVAILABLE').replace('_', ' ')}
          </div>
        </div>}
      </div>
    </div>
  );
};

const EvidenceValue: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="min-w-0 rounded border border-cyan-500/20 bg-space-900/70 p-2">
    <p className="text-[8px] font-mono text-slate-500">{label}</p>
    <p className="mt-1 break-words text-[10px] font-mono font-bold text-slate-100">{value}</p>
  </div>
);

const EvidenceBlock: React.FC<{ title: string; value: unknown; empty: string }> = ({ title, value, empty }) => {
  const hasEvidence = !!value && typeof value === 'object' && Object.keys(value as object).length > 0;
  return <details className="group rounded border border-slate-700/70 bg-space-900/60 p-2.5">
    <summary className="cursor-pointer list-none text-[9px] font-mono tracking-wider text-cyan-300">{title} <span className="float-right text-slate-500 group-open:rotate-180">⌄</span></summary>
    {hasEvidence ? <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap break-words text-[8px] leading-relaxed text-slate-300">{JSON.stringify(value, null, 2)}</pre> : <p className="mt-2 text-[9px] text-slate-500">{empty}</p>}
  </details>;
};
