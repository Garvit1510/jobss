import React from "react";
import { createPortal } from "react-dom";
import { Maximize, ScanFace, ShieldAlert, ShieldCheck } from "lucide-react";
import { CamPreview, MicMeter } from "./ProctorMedia";
import { MAX_TAB_SWITCHES } from "../../lib/useProctor";

export default function ProctorMonitor({ proctor, identityCountdown }) {
  const tabs = proctor.flags.filter((f) => f.type === "tab_switch").length;
  const n = proctor.flags.length;
  const idLock = identityCountdown != null;
  // Rendered via a portal to document.body so fixed positioning is relative to the viewport
  // (never affected by transformed/animated ancestors) and stays pinned to the corner.
  return createPortal(
    <>
      {idLock && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-brand-red px-6 text-center text-white" data-testid="proctor-identity-gate">
          <div className="max-w-lg">
            <ScanFace size={56} className="mx-auto" />
            <h2 className="mt-4 font-display text-3xl font-bold">Registered candidate not detected</h2>
            <p className="mt-3 text-white/90">The face on camera does not match the person who started this test. Only the registered candidate may take it.</p>
            <p className="mt-6 font-display text-7xl font-bold" data-testid="proctor-identity-countdown">{identityCountdown}</p>
            <p className="mt-1 font-mono text-sm text-white/80">Return to the camera now, or the test auto-submits.</p>
          </div>
        </div>
      )}
      {!proctor.fullscreen && !idLock && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-ink/95 px-6 text-center" data-testid="proctor-fullscreen-gate">
          <div className="max-w-md border-3 border-white bg-brand-red p-8 text-white shadow-brutal">
            <Maximize size={44} className="mx-auto" />
            <h2 className="mt-4 font-display text-2xl font-bold">You left fullscreen</h2>
            <p className="mt-3 text-sm text-white/90">The assessment is locked until you return to fullscreen. Your answers are saved, but <b>the timer keeps running</b>.</p>
            <button onClick={proctor.enterFullscreen} className="brutal-btn mt-6 w-full bg-white text-ink" data-testid="proctor-refullscreen-btn">
              <Maximize size={17} /> Return to fullscreen
            </button>
            <p className="mt-3 font-mono text-[11px] text-white/70">or press F11 / F12 to go back</p>
          </div>
        </div>
      )}
      <div className="fixed bottom-4 right-4 z-[90] w-48 brutal-card p-2" data-testid="proctor-monitor">
        <div className="relative">
          <CamPreview stream={proctor.stream} className="w-full aspect-[4/3] border-2 border-ink" testid="proctor-monitor-cam" />
          <span className="absolute left-1.5 top-1.5 flex items-center gap-1 bg-brand-red px-1.5 py-0.5 font-mono text-[10px] font-bold text-white">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-white" /> REC
          </span>
        </div>
        <div className="mt-2"><MicMeter levelRef={proctor.levelRef} testid="proctor-monitor-mic" /></div>
        <div className="mt-2 flex items-center justify-between font-mono text-[11px]">
          <span className={`flex items-center gap-1 font-bold ${n ? "text-brand-red" : "text-brand-green"}`} data-testid="proctor-flag-count">
            {n ? <ShieldAlert size={13} /> : <ShieldCheck size={13} />} {n} flag{n === 1 ? "" : "s"}
          </span>
          <span data-testid="proctor-tab-count">Tabs {tabs}/{MAX_TAB_SWITCHES}</span>
        </div>
      </div>
    </>,
    document.body
  );
}
