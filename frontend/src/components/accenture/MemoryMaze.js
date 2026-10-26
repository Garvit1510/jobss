import React, { useState } from "react";
import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp, DoorClosed, KeyRound, PersonStanding } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";

const DIRS = [["up", -1, 0, ChevronUp, "left-1/2 top-1 -translate-x-1/2"], ["down", 1, 0, ChevronDown, "left-1/2 bottom-1 -translate-x-1/2"],
  ["left", 0, -1, ChevronLeft, "left-1 top-1/2 -translate-y-1/2"], ["right", 0, 1, ChevronRight, "right-1 top-1/2 -translate-y-1/2"]];

export default function MemoryMaze({ mockId, play, onState }) {
  const [busy, setBusy] = useState(false);
  const [wrong, setWrong] = useState(null);
  const [msg, setMsg] = useState("");
  const { n, pos, key, door, has_key: hasKey, attempts } = play;
  const move = async (dir) => {
    if (busy) return;
    setBusy(true);
    try {
      const { data } = await api.post(`/accenture-mocks/${mockId}/gamified/maze/move`, { dir });
      if (data.event === "wrong") { setWrong(data.wrong_cell); setTimeout(() => setWrong(null), 600); }
      if (data.event === "key") setMsg("Key collected ✓");
      if (data.event === "wrong") setMsg("");
      if (data.event === "solved") setMsg("Maze Solved!");
      onState(data);
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const size = n <= 3 ? "h-28 w-28 md:h-36 md:w-36" : "h-20 w-20 md:h-28 md:w-28";
  return (
    <div className="flex flex-col items-center" data-testid="memory-maze">
      <p className="mb-3 font-mono text-xs text-ink/60" data-testid="maze-attempts">Attempt {attempts}</p>
      <div className="grid overflow-hidden rounded-2xl border-2 border-ink/70 bg-[#f7f7f5]" style={{ gridTemplateColumns: `repeat(${n}, minmax(0, 1fr))` }}>
        {Array.from({ length: n * n }, (_, i) => {
          const r = Math.floor(i / n), c = i % n;
          const here = pos[0] === r && pos[1] === c;
          const isWrong = wrong && wrong[0] === r && wrong[1] === c;
          return (
            <div key={i} className={`relative flex items-center justify-center border border-ink/15 ${size} ${here ? "bg-[#262626]" : ""} ${isWrong ? "ring-4 ring-inset ring-brand-red" : ""}`} data-testid={`maze-cell-${r}-${c}`}>
              {here && <PersonStanding size={44} className="text-brand-yellow" />}
              {!here && key && key[0] === r && key[1] === c && <KeyRound size={40} className="text-amber-500" />}
              {!here && door[0] === r && door[1] === c && <DoorClosed size={40} className="text-amber-700" />}
              {here && DIRS.map(([d, dr, dc, I, cls]) => {
                const nr = r + dr, nc = c + dc;
                if (nr < 0 || nc < 0 || nr >= n || nc >= n) return null;
                return (
                  <button key={d} onClick={() => move(d)} disabled={busy} className={`absolute z-10 flex h-9 w-9 items-center justify-center rounded-lg bg-[#333] text-white shadow transition-transform hover:scale-110 disabled:opacity-60 ${cls}`}
                    aria-label={`Move ${d}`} data-testid={`maze-move-${d}`}><I size={18} /></button>
                );
              })}
            </div>
          );
        })}
      </div>
      <p className={`mt-3 h-6 font-display font-bold ${msg === "Maze Solved!" ? "text-brand-blue" : "text-brand-green"}`} data-testid="maze-message">{hasKey && !msg ? "Key collected ✓" : msg}</p>
    </div>
  );
}
