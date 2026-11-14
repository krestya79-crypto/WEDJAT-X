import React from 'react';
import {
  LayoutDashboard,
  User,
  Activity,
  Dna,
  Bell,
  ShieldCheck,
  TrendingUp,
  History,
  ChevronRight,
} from 'lucide-react';

export type TabId =
  | 'mission'
  | 'astronaut'
  | 'telemetry'
  | 'biomarkers'
  | 'alerts'
  | 'trust'
  | 'trajectory'
  | 'history';

interface NavItem {
  id: TabId;
  label: string;
  sublabel: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  syntheticOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  {
    id: 'mission',
    label: 'Mission Control',
    sublabel: 'Command Overview',
    icon: LayoutDashboard,
  },
  {
    id: 'astronaut',
    label: '3D Astronaut',
    sublabel: 'Holographic Vitals',
    icon: User,
  },
  {
    id: 'telemetry',
    label: 'Live Telemetry',
    sublabel: 'Synthetic Streams',
    icon: Activity,
    syntheticOnly: true,
  },
  {
    id: 'biomarkers',
    label: 'NASA Biomarkers',
    sublabel: 'OSD-575 Lab Assays',
    icon: Dna,
  },
  {
    id: 'alerts',
    label: 'Alert Center',
    sublabel: 'Intelligent Support',
    icon: Bell,
  },
  {
    id: 'trust',
    label: 'Sensor Trust',
    sublabel: 'Signal Quality Score',
    icon: ShieldCheck,
    syntheticOnly: true,
  },
  {
    id: 'trajectory',
    label: 'Trajectory',
    sublabel: 'Milestone Recovery',
    icon: TrendingUp,
  },
  {
    id: 'history',
    label: 'Analysis History',
    sublabel: 'SQLite Audit Trail',
    icon: History,
  },
];

interface SidebarProps {
  activeTab: TabId;
  onSelectTab: (tab: TabId) => void;
  activeAlertCount?: number;
  showSyntheticFeatures?: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onSelectTab,
  activeAlertCount = 0,
  showSyntheticFeatures = true,
}) => {
  return (
    <aside className="w-full lg:w-64 bg-space-950/95 lg:min-h-[calc(100vh-61px)] border-r border-cyan-500/15 p-3 flex flex-col justify-between shrink-0">
      <div className="space-y-1">
        <div className="px-3 py-2 text-[10px] font-mono tracking-widest text-cyan-400/70 uppercase">
          OPERATIONAL CONSOLES
        </div>

        <nav className="space-y-1">
          {NAV_ITEMS.filter((item) => showSyntheticFeatures || !item.syntheticOnly).map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-left transition-all duration-200 group relative ${
                  isActive
                    ? 'bg-gradient-to-r from-cyan-950/80 to-space-900 border border-cyan-400/40 text-cyan-200 shadow-[0_0_15px_rgba(0,240,255,0.15)]'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-space-900/60 border border-transparent'
                }`}
              >
                {isActive && (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-cyan-400 rounded-r shadow-[0_0_8px_#00f0ff]" />
                )}

                <div className="flex items-center gap-3">
                  <Icon
                    className={`w-4 h-4 transition-colors ${
                      isActive ? 'text-cyan-400' : 'text-slate-500 group-hover:text-slate-300'
                    }`}
                  />
                  <div>
                    <div className="text-xs font-medium font-sans tracking-wide">
                      {item.label}
                    </div>
                    <div className="text-[10px] font-mono text-slate-400">
                      {item.sublabel}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1.5">
                  {item.id === 'alerts' && activeAlertCount > 0 && (
                    <span className="px-1.5 py-0.5 text-[10px] font-mono rounded-full bg-amber-950 border border-amber-500/50 text-amber-300">
                      {activeAlertCount}
                    </span>
                  )}
                  {item.syntheticOnly && (
                    <span className="px-1.5 py-0.5 text-[9px] font-mono rounded bg-amber-950/40 text-amber-400 border border-amber-500/30">
                      SYNTH
                    </span>
                  )}
                  <ChevronRight
                    className={`w-3.5 h-3.5 text-slate-600 transition-transform ${
                      isActive ? 'text-cyan-400 translate-x-0.5' : 'group-hover:translate-x-0.5'
                    }`}
                  />
                </div>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Flight Surgeon Advisory Notice */}
      <div className="mt-4 p-3 rounded-lg bg-space-900/60 border border-slate-800 text-[10px] font-mono text-slate-400 space-y-1">
        <div className="text-cyan-400/90 font-semibold tracking-wider uppercase flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
          SYSTEM SAFETY RULE
        </div>
        <p className="leading-normal">
          Not certified as an autonomous medical diagnostic device. Authorized flight surgeon review required for all anomalous findings.
        </p>
      </div>
    </aside>
  );
};
