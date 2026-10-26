import React, { useState } from "react";
import { ArrowLeftRight, ArrowRight, Check, Flag, PersonStanding, RotateCcw, RotateCw } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";

export default function PathFinder({ mockId, play, onState }) {
  const [sel, setSel] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const { n, board, start_row: sr, goal_row: gr, trace, moves } = play;
  const onTrace = new Set(trace.map(([r, c]) => `${r}-${c}`));
  const call = async (path, body) => {
    setBusy(true);
    try {
      const { data } = await api.post(`/accenture-mocks/${mockId}/gamified/path/${path}`, body);
      if (path === "check") setMsg(data.event === "solved" ? `Great! You found the path · ${data.moves} moves` : "Path is not complete yet");
      else setMsg("");
      onState(data);
      return data;
    } catch (e) { toast.error(errMsg(e)); return null; } finally { setBusy(false); }
  };
  const toggle = (r, c) => {
    const k = `${r}-${c}`;
    setSel((s) => (s.includes(k) ? s.filter((x) => x !== k) : [...s, k].slice(-2)));
  };
  const tile = (k) => { const [r, c] = k.split("-").map(Number); return { r, c }; };
  const cell = n <= 3 ? "h-24 w-24" : n === 4 ? "h-20 w-20" : "h-16 w-16";
  const sideRow = (row, icon, testid) => (
    <div className="grid gap-1" style={{ gridTemplateRows: `repeat(${n}, minmax(0, 1fr))` }}>
      {Array.from({ length: n }, (_, r) => <div key={r} className={`flex items-center justify-center ${cell.split(" ")[0]} w-12`} data-testid={r === row ? testid : undefined}>{r === row ? icon : null}</div>)}
    </div>
  );
  return (
    <div className="flex flex-col items-center" data-testid="path-finder">
      <p className="mb-3 font-mono text-xs text-ink/60" data-testid="pf-moves">Moves {moves}</p>
      <div className="flex items-center gap-2">
        {sideRow(sr, <PersonStanding size={34} className="text-brand-blue" />, "pf-start")}
        <div className="grid gap-1 rounded-xl border-2 border-ink/60 bg-[#f4f4f2] p-1" style={{ gridTemplateColumns: `repeat(${n}, minmax(0, 1fr))` }}>
          {board.flatMap((row, r) => row.map((d, c) => {
            const k = `${r}-${c}`;
            const on = onTrace.has(k), picked = sel.includes(k);
            return (
              <button key={k} onClick={() => toggle(r, c)} className={`flex items-center justify-center rounded-md transition-colors ${cell} ${on ? "bg-brand-yellow text-ink" : "bg-[#333] text-white"} ${picked ? "ring-4 ring-brand-blue ring-offset-1" : ""}`}
                data-testid={`pf-tile-${r}-${c}`} aria-label={`tile ${r + 1},${c + 1}`}>
                <ArrowRight size={n <= 3 ? 40 : 30} style={{ transform: `rotate(${d * 45}deg)` }} />
              </button>
            );
          }))}
        </div>
        {sideRow(gr, <Flag size={30} className="text-brand-green" />, "pf-goal")}
      </div>
      <div className="mt-5 flex gap-3">
        <button disabled={busy || sel.length !== 1} onClick={() => call("rotate", tile(sel[0]))} className="flex h-12 w-12 items-center justify-center rounded-full bg-[#333] text-white disabled:opacity-40" title="Rotate selected tile" data-testid="pf-rotate-btn"><RotateCw size={20} /></button>
        <button disabled={busy || sel.length !== 2} onClick={async () => { if (await call("swap", { a: tile(sel[0]), b: tile(sel[1]) })) setSel([]); }} className="flex h-12 w-12 items-center justify-center rounded-full bg-[#333] text-white disabled:opacity-40" title="Swap two selected tiles" data-testid="pf-swap-btn"><ArrowLeftRight size={20} /></button>
        <button disabled={busy} onClick={() => call("check")} className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-green text-ink disabled:opacity-40" title="Check path" data-testid="pf-check-btn"><Check size={22} /></button>
        <button disabled={busy} onClick={() => { setSel([]); call("retry"); }} className="flex h-12 items-center gap-1 rounded-full border-2 border-ink px-3 text-xs font-semibold disabled:opacity-40" data-testid="pf-retry-btn"><RotateCcw size={14} /> Retry board</button>
      </div>
      <p className="mt-2 text-xs text-ink/50">Select 1 tile to rotate, 2 tiles to swap.</p>
      <p className={`mt-2 h-6 font-display font-bold ${msg.startsWith("Great") ? "text-brand-green" : "text-brand-red"}`} data-testid="pf-message">{msg}</p>
    </div>
  );
}
