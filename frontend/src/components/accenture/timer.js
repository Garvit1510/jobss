import { useEffect, useState } from "react";

// Remaining seconds until an ISO deadline, corrected by the server/client clock offset.
export function useCountdown(deadline, offsetMs = 0) {
  const calc = () => (deadline ? Math.max(0, Math.ceil((new Date(deadline).getTime() - (Date.now() + offsetMs)) / 1000)) : 0);
  const [left, setLeft] = useState(calc);
  useEffect(() => {
    setLeft(calc());
    if (!deadline) return undefined;
    const t = setInterval(() => setLeft(calc()), 250);
    return () => clearInterval(t);
  }, [deadline, offsetMs]);
  return left;
}

export const fmt = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

export function TimerRing({ left, total, testid = "game-timer" }) {
  const r = 22;
  const c = 2 * Math.PI * r;
  const frac = total ? left / total : 0;
  return (
    <div className="relative h-14 w-14" data-testid={testid}>
      <svg width="56" height="56" className="-rotate-90">
        <circle cx="28" cy="28" r={r} stroke="#e5e5e5" strokeWidth="5" fill="none" />
        <circle cx="28" cy="28" r={r} stroke={left <= 10 ? "#FF5A4D" : "#333"} strokeWidth="5" fill="none" strokeDasharray={c} strokeDashoffset={c - c * frac} />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center font-mono text-xs font-bold">{fmt(left)}</span>
    </div>
  );
}
