import React, { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Hourglass } from "lucide-react";

const MIN_WORDS = 2;

export function useAutoSubmit({ enabled, lastActivity, answer, ms, onFire }) {
  const [left, setLeft] = useState(null);
  const fired = useRef(0);
  const live = useRef({ lastActivity, answer, onFire });
  live.current = { lastActivity, answer, onFire };

  useEffect(() => {
    if (!enabled) {
      setLeft(null);
      return undefined;
    }
    const t = setInterval(() => {
      const { lastActivity: la, answer: a, onFire: fire } = live.current;
      const words = a.split(/\s+/).filter(Boolean).length;
      if (!la || words < MIN_WORDS) return setLeft(null);
      const quiet = Date.now() - la;
      if (quiet >= ms) {
        if (fired.current !== la) {
          fired.current = la;
          setLeft(null);
          fire();
        }
      } else setLeft(quiet > 700 ? 1 - quiet / ms : null);
    }, 120);
    return () => clearInterval(t);
  }, [enabled, ms]);

  return left;
}

const OPTIONS = [[2000, "2s"], [3000, "3s"], [5000, "5s"], [10000, "10s"]];

export default function AutoSubmitBar({ auto, setAuto, countdown }) {
  return (
    <div className="w-full border-3 border-ink bg-white p-3" data-testid="auto-submit-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className="flex cursor-pointer items-center gap-2 font-display text-sm font-bold">
          <input type="checkbox" checked={auto.on} onChange={(e) => setAuto({ ...auto, on: e.target.checked })} className="h-4 w-4 accent-[#4D6FFF]" data-testid="auto-submit-toggle" />
          Auto-submit when I stop talking
        </label>
        <div className="flex gap-1" role="group" aria-label="Silence before auto-submit">
          {OPTIONS.map(([v, l]) => (
            <button key={v} onClick={() => setAuto({ ...auto, ms: v })} disabled={!auto.on} aria-pressed={auto.ms === v} data-testid={`auto-submit-${l}`}
              className={`border-2 border-ink px-2 py-0.5 font-mono text-xs font-bold disabled:opacity-40 ${auto.ms === v ? "bg-ink text-white" : "bg-offwhite"}`}>{l}</button>
          ))}
        </div>
      </div>
      <div className="mt-2 h-6">
        {countdown !== null && (
          <div className="flex items-center gap-2" data-testid="auto-submit-countdown">
            <Hourglass size={14} className="shrink-0" />
            <div className="h-2.5 flex-1 border-2 border-ink bg-offwhite">
              <motion.div className="h-full bg-brand-yellow" animate={{ width: `${Math.max(0, countdown) * 100}%` }} transition={{ duration: 0.12 }} />
            </div>
            <span className="font-mono text-[11px]">Submitting soon — keep talking to continue</span>
          </div>
        )}
      </div>
    </div>
  );
}
