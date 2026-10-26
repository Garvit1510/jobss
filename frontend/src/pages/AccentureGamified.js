import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { toast } from "sonner";
import api, { errMsg } from "../lib/api";
import { useProctorDone } from "../components/accenture/ProctorGate";
import { Button, Card, Spinner } from "../components/ui";
import MemoryMaze from "../components/accenture/MemoryMaze";
import BubbleMath from "../components/accenture/BubbleMath";
import PathFinder from "../components/accenture/PathFinder";
import { TimerRing, fmt, useCountdown } from "../components/accenture/timer";

const label = (a) => (a.game === "bubble_math" ? "Quick-Fire Math — Bubble Math" : `${a.title} — ${a.grid?.replace("x", "×")}`);
const total = (a) => (a.game === "bubble_math" ? a.questions * a.seconds_per_question : a.minutes * 60);

function resultText(a) {
  const r = a.result || {};
  if (a.game === "memory_maze") return `${r.solved ? "Solved" : "Not solved"} · ${r.attempts} attempt${r.attempts === 1 ? "" : "s"} · ${fmt(r.time_taken_sec || 0)}`;
  if (a.game === "bubble_math") return `${r.correct}/${r.total} correct (${r.percent}%)`;
  return `${r.solved ? "Great! You found the path" : "Path not found"} · ${r.moves} moves (par ${r.par_moves})`;
}

function Intro({ a, onBegin, busy }) {
  return (
    <Card className="mx-auto max-w-2xl p-8" data-testid="activity-intro">
      <h2 className="text-2xl font-bold">{label(a)}</h2>
      <p className="mt-1 text-sm text-ink/60">{a.game === "bubble_math" ? `${a.questions} questions · ${a.seconds_per_question} seconds each` : `${a.minutes} minutes`}</p>
      {a.instruction && <p className="mt-4 font-display text-lg font-semibold" data-testid="activity-instruction">{a.instruction}</p>}
      <ul className="mt-4 list-disc space-y-1 pl-5 text-sm">{a.rules.map((r) => <li key={r}>{r}</li>)}</ul>
      <Button variant="dark" className="mt-6" disabled={busy} onClick={onBegin} data-testid="activity-begin-btn">Start</Button>
    </Card>
  );
}

export default function AccentureGamified() {
  const { mockId } = useParams();
  const preview = new URLSearchParams(useLocation().search).get("preview") === "1";
  const [s, setS] = useState(null);
  useProctorDone(!!s?.finished_at);
  const [busy, setBusy] = useState(false);
  const [doneIdx, setDoneIdx] = useState(null);
  const offset = useMemo(() => (s ? new Date(s.server_time).getTime() - Date.now() : 0), [s?.server_time]);
  const onState = useCallback((d) => setS((prev) => {
    if (prev && prev.current !== d.current && prev.current !== null) setDoneIdx(prev.current);
    return d;
  }), []);
  useEffect(() => { api.post(`/accenture-mocks/${mockId}/gamified/start`, { preview }).then((r) => setS(r.data)).catch((e) => { toast.error(errMsg(e)); setS({ error: errMsg(e) }); }); }, [mockId, preview]);
  const act = s?.activities && s.current !== null ? s.activities[s.current] : null;
  const left = useCountdown(act?.status === "active" ? act.deadline : null, offset);
  useEffect(() => {
    if (!act || act.status !== "active" || left > 0) return undefined;
    const t = setTimeout(() => api.post(`/accenture-mocks/${mockId}/gamified/time-up`).then((r) => onState(r.data)).catch(() => {}), 3300);
    return () => clearTimeout(t);
  }, [left, act, mockId, onState]);
  const begin = async () => {
    setBusy(true);
    try { const { data } = await api.post(`/accenture-mocks/${mockId}/gamified/begin`); onState(data); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  if (s === null) return <div className="flex justify-center py-24"><Spinner /></div>;
  if (s.error) return <div className="p-12 text-center" data-testid="gamified-unavailable"><p className="font-bold">Round 2 is not available.</p><p className="mt-2 text-sm" data-testid="gamified-unavailable-reason">{s.error}</p><Link to="/accenture-mocks" className="mt-3 inline-block underline">Back to Accenture mocks</Link></div>;
  const idx = s.current === null ? 6 : s.current;
  const finishedAct = doneIdx !== null ? s.activities[doneIdx] : null;
  return (
    <div className="mx-auto max-w-6xl px-4 py-8" data-testid="gamified-page">
      <div className="mb-6 flex items-end justify-between gap-4">
        <h1 className="text-lg font-semibold md:text-xl" data-testid="gamified-section-title">{act ? `Section ${idx + 1} of 6: ${label(act)}` : "Round 2 complete"}</h1>
        <span className="text-sm text-ink/50">{preview ? "Admin preview · " : ""}Round 2 · {s.mock_id}</span>
      </div>
      <div className="mb-8 h-3 w-full rounded-full bg-[#e5e5e5]"><div className="h-full rounded-full bg-[#ff6a00] transition-all" style={{ width: `${(idx / 6) * 100}%` }} data-testid="gamified-progress" /></div>
      {finishedAct ? (
        <Card className="mx-auto max-w-xl p-8 text-center" data-testid="section-complete">
          <h2 className="text-2xl font-bold">{label(finishedAct)} — done</h2>
          <p className="mt-2" data-testid="section-result">{resultText(finishedAct)}</p>
          {finishedAct.score !== undefined && finishedAct.score !== null && <p className="mt-1 font-mono text-sm" data-testid="section-score">Activity score {finishedAct.score}/100</p>}
          <Button variant="dark" className="mt-6" onClick={() => setDoneIdx(null)} data-testid="continue-next-section-btn">{s.current === null ? "See results" : "Continue to next section"}</Button>
        </Card>
      ) : !act ? (
        <Card className="mx-auto max-w-2xl p-8" data-testid="gamified-results">
          <h2 className="text-2xl font-bold">Mock complete</h2>
          <ul className="mt-4 divide-y-2 divide-ink/10">{s.activities.map((a) => <li key={a.activity_id} className="flex justify-between gap-4 py-2" data-testid={`result-${a.activity_id}`}><span className="font-semibold">{label(a)}</span><span className="text-right text-sm">{resultText(a)} · <b data-testid={`score-${a.activity_id}`}>{a.score ?? 0}/100</b></span></li>)}</ul>
          {s.round_score && <p className="mt-4 text-xl font-bold" data-testid="round2-score">Round 2: {s.round_score.percent}% · {s.round_score.passed ? "meets" : "below"} the {s.round_score.cutoff_percent}% cutoff</p>}
          <p className="mt-4 text-xs text-ink/60">{s.scoring.note}</p>
          <Link to={`/accenture-mocks/${s.mock_id}/technical${s.preview ? "?preview=1" : ""}`} className="brutal-btn mt-4 inline-flex bg-ink px-3 py-2 text-white" data-testid="gamified-to-technical">Continue to Round 3 · Technical</Link>
        </Card>
      ) : act.status === "pending" ? <Intro a={act} onBegin={begin} busy={busy} /> : (
        <div className="flex flex-col items-center gap-4">
          {act.game === "memory_maze" && <MemoryMaze mockId={mockId} play={act.play} onState={onState} />}
          {act.game === "path_finder" && <PathFinder mockId={mockId} play={act.play} onState={onState} />}
          {act.game === "bubble_math" && <BubbleMath mockId={mockId} play={act.play} instruction={act.instruction} offset={offset} onState={onState} />}
          <div className="self-start"><TimerRing left={left} total={total(act)} /></div>
        </div>
      )}
    </div>
  );
}
