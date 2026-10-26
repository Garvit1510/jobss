import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";
import { useCountdown } from "./timer";

const POS = ["left-[8%] top-[6%]", "right-[8%] top-[6%]", "left-1/2 top-[48%] -translate-x-1/2"];

export default function BubbleMath({ mockId, play, instruction, offset, onState }) {
  const [order, setOrder] = useState([]);
  const [flash, setFlash] = useState(false);
  const [busy, setBusy] = useState(false);
  const qDeadline = play.q_started ? new Date(new Date(play.q_started).getTime() + 15000).toISOString() : null;
  const left = useCountdown(qDeadline, offset);
  useEffect(() => { setOrder([]); }, [play.index]);
  useEffect(() => {
    if (left > 0 || !qDeadline) return undefined;
    const t = setTimeout(() => api.get(`/accenture-mocks/${mockId}/gamified`).then((r) => onState(r.data)).catch(() => {}), 3300);
    return () => clearTimeout(t);
  }, [left, qDeadline, mockId, onState]);
  const pick = async (i) => {
    if (busy || order.includes(i)) return;
    const next = [...order, i];
    setOrder(next);
    if (next.length < 3) return;
    setBusy(true);
    try {
      const { data } = await api.post(`/accenture-mocks/${mockId}/gamified/bubble/answer`, { index: play.index, order: next });
      if (data.event === "correct" || data.event === "incorrect") { setFlash(data.event); await new Promise((r) => setTimeout(r, 350)); setFlash(false); }
      onState(data);
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <div className="w-full" data-testid="bubble-math">
      <div className="mb-2 flex items-center justify-between gap-4">
        <p className="font-display font-semibold" data-testid="bubble-instruction">{instruction}</p>
        <p className="font-mono text-sm" data-testid="bubble-progress">Q {play.index + 1}/{play.total} · <span className={left <= 5 ? "text-brand-red" : ""} data-testid="bubble-timer">{left}s</span></p>
      </div>
      <div className="relative h-[460px] w-full overflow-hidden rounded-xl border-t-2 border-ink/70 bg-[#efefef]">
        {play.exprs.map((e, i) => {
          const k = order.indexOf(i);
          return (
            <button key={`${play.index}-${i}`} onClick={() => pick(i)} className={`absolute flex h-40 w-40 items-center justify-center rounded-full text-2xl font-semibold transition-colors md:h-52 md:w-52 ${POS[i]} ${k >= 0 ? "bg-[#333] text-white" : "bg-[#d4d4d4] text-ink hover:bg-[#c8c8c8]"} ${flash === "correct" ? "ring-4 ring-brand-green" : flash === "incorrect" ? "ring-4 ring-brand-red" : ""}`}
              data-testid={`bubble-${i}`}>
              {e}
              {k >= 0 && <span className="absolute -right-1 top-2 flex h-9 w-9 items-center justify-center rounded-full bg-white text-sm font-bold text-ink shadow" data-testid={`bubble-order-${i}`}>{k + 1}</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}
