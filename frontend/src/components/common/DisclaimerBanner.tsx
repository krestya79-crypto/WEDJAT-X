import React from 'react';
import { ShieldAlert, Info, Database } from 'lucide-react';
import { SourceType } from '../../types';

interface DisclaimerBannerProps {
  source?: SourceType | 'BOTH';
  compact?: boolean;
}

export const DisclaimerBanner: React.FC<DisclaimerBannerProps> = ({
  source = 'BOTH',
  compact = false,
}) => {
  if (compact) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-amber-950/40 border border-amber-500/30 text-amber-200/90 text-[11px] font-mono">
        <ShieldAlert className="w-3.5 h-3.5 text-amber-400 shrink-0" />
        <span>NON-CLINICAL PROTOTYPE · HUMAN AEROSPACE FLIGHT SURGEON REVIEW REQUIRED</span>
      </div>
    );
  }

  return (
    <div className="p-3.5 rounded-lg bg-space-900/90 border border-cyan-500/20 backdrop-blur-md space-y-2">
      <div className="flex items-start gap-2.5">
        <ShieldAlert className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
        <div className="text-xs text-slate-300 leading-relaxed font-sans">
          <span className="font-semibold text-amber-300 tracking-wide font-mono uppercase">
            Aerospace Biomedical Research Decision Support Only:
          </span>{' '}
          WEDJAT-X is an exploratory biomedical engineering and mission-control decision-support prototype. It does not provide autonomous clinical diagnoses, disease predictions, or treatment prescriptions.
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-1 border-t border-slate-800/80 text-[11px] font-mono">
        <div className="flex items-center gap-2 text-cyan-300/90 bg-cyan-950/30 px-2.5 py-1.5 rounded border border-cyan-500/20">
          <Database className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
          <span>
            <strong className="text-cyan-200">NASA OSD-575:</strong> Discrete venipuncture lab assays (N=4 Inspiration4 crew).
          </span>
        </div>
        <div className="flex items-center gap-2 text-amber-300/90 bg-amber-950/30 px-2.5 py-1.5 rounded border border-amber-500/20">
          <Info className="w-3.5 h-3.5 text-amber-400 shrink-0" />
          <span>
            <strong className="text-amber-200">SYNTHETIC STREAMS:</strong> Continuous physiological telemetry is simulated.
          </span>
        </div>
      </div>
    </div>
  );
};
