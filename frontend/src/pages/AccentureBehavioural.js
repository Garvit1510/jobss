import React, { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { toast } from "sonner";
import api, { errMsg } from "../lib/api";
import { useProctorDone } from "../components/accenture/ProctorGate";
import { Badge, Button, Card, Spinner } from "../components/ui";
import { fmt, useCountdown } from "../components/accenture/timer";

const BAND_TONE = { high: "green", moderate: "yellow", low: "white" };

function Result({ s }) {
  const r = s.result;
  return (
    <Card className="p-6" data-testid="beh-results">
      <h2 className="text-2xl font-bold">Round 1 complete</h2>
      <p className="mt-1 text-sm" data-testid="beh-answered">{r.answered}/{r.total} statements answered · {s.end_reason === "time_up" ? "time ran out" : "submitted"}</p>
      <p className="mt-2 text-sm">There are no right or wrong answers in this round and no pass/fail. {r.review_status === "needs_admin_review" ? "Your profile has been sent for an admin review." : ""}</p>
      {r.traits && (
        <div className="mt-4 grid gap-2 sm:grid-cols-2" data-testid="beh-trait-profile">
          {Object.entries(r.traits).map(([k, t]) => (
            <div key={k} className="flex items-center justify-between border-2 border-ink px-3 py-2" data-testid={`beh-trait-${k}`}>
              <span className="font-semibold">{t.label}</span>
              <span className="flex items-center gap-2 font-mono text-xs">{t.mean ?? "–"} / 5 <Badge tone={BAND_TONE[t.band] || "white"}>{t.band || "n/a"}</Badge></span>
            </div>
          ))}
        </div>
      )}
      {r.profile_index != null && <p className="mt-3 text-sm" data-testid="beh-profile-index">Profile index (descriptive): <b>{r.profile_index}</b> / 5</p>}
      <p className="mt-3 text-xs text-ink/60">{r.method}</p>
      <Link to={`/accenture-mocks/${s.mock_id}/gamified${s.preview ? "?preview=1" : ""}`} className="brutal-btn mt-5 inline-flex bg-ink px-3 py-2 text-white" data-testid="beh-to-gamified">Continue to Round 2 · Gamified</Link>
    </Card>
  );
}

function Statement({ item, n, total, options, value, onPick }) {
  return (
    <>
      <p className="mt-6 font-display text-2xl font-semibold leading-snug" data-testid="beh-statement">{item.statement}</p>
      <div className="mt-8 grid gap-2 sm:grid-cols-5" data-testid="beh-scale">
        {options.map((o, j) => (
          <button key={o} onClick={() => onPick(j)} className={`border-2 px-3 py-4 text-sm font-semibold transition-colors ${value === j ? "border-ink bg-brand-yellow" : "border-ink/20 hover:border-ink"}`} data-testid={`beh-option-${j}`}>{o}</button>
        ))}
      </div>
      <p className="mt-3 text-xs text-ink/50">Statement {n} of {total} · choose the option that best describes you.</p>
    </>
  );
}

export default function AccentureBehavioural() {
  const { mockId } = useParams();
  const preview = new URLSearchParams(useLocation().search).get("preview") === "1";
  const [s, setS] = useState(null);
  useProctorDone(!!s?.finished_at);
  const [resp, setResp] = useState({});
  const [i, setI] = useState(0);
  const offset = useMemo(() => (s ? new Date(s.server_time).getTime() - Date.now() : 0), [s?.server_time]);
  const left = useCountdown(s && !s.finished_at ? s.deadline : null, offset);
  useEffect(() => { api.post(`/accenture-mocks/${mockId}/behavioural/start`, { preview }).then((r) => { setS(r.data); setResp(r.data.responses); }).catch((e) => { toast.error(errMsg(e)); setS({ error: errMsg(e) }); }); }, [mockId, preview]);
  useEffect(() => {
    if (!s || s.finished_at || left > 0) return undefined;
    const t = setTimeout(() => api.get(`/accenture-mocks/${mockId}/behavioural`).then((r) => setS(r.data)).catch(() => {}), 6000);
    return () => clearTimeout(t);
  }, [left, s, mockId]);
  if (s === null) return <div className="flex justify-center py-24"><Spinner /></div>;
  if (s.error) return <div className="p-12 text-center" data-testid="beh-unavailable"><p className="font-bold">Round 1 is not available.</p><p className="mt-2 text-sm" data-testid="beh-unavailable-reason">{s.error}</p><Link to="/accenture-mocks" className="mt-3 inline-block underline">Back to Accenture mocks</Link></div>;
  if (s.finished_at && s.result) return <div className="mx-auto max-w-3xl px-4 py-8"><Result s={s} /></div>;
  if (s.finished_at || left === 0) return <div className="flex flex-col items-center gap-3 py-24" data-testid="beh-closing"><Spinner /><p>Time is up — saving your responses…</p></div>;
  const item = s.items[i];
  const answered = s.items.filter((x) => resp[x.qid] != null).length;
  const pick = async (choice) => {
    const prev = resp[item.qid];
    setResp((r) => ({ ...r, [item.qid]: choice }));
    if (choice !== null && i < s.items.length - 1) setTimeout(() => setI((x) => Math.min(x + 1, s.items.length - 1)), 250);
    try { await api.post(`/accenture-mocks/${mockId}/behavioural/answer`, { qid: item.qid, choice }); } catch (e) { setResp((r) => ({ ...r, [item.qid]: prev })); toast.error(errMsg(e)); }
  };
  const submit = async () => {
    if (!window.confirm(`Submit Round 1? ${s.items.length - answered} statement(s) unanswered.`)) return;
    try { const { data } = await api.post(`/accenture-mocks/${mockId}/behavioural/submit`); setS(data); window.scrollTo(0, 0); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="mx-auto grid max-w-7xl gap-6 px-4 py-8 lg:grid-cols-[1fr_300px]" data-testid="beh-page">
      <Card className="p-6">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-ink/60" data-testid="beh-meta">Round 1 · Behavioural Assessment{preview ? " · Admin preview" : ""}</p>
          <span className={`font-mono text-lg font-bold ${left <= 120 ? "text-brand-red" : ""}`} data-testid="beh-timer">{fmt(left)}</span>
        </div>
        <Statement item={item} n={i + 1} total={s.items.length} options={s.options} value={resp[item.qid]} onPick={pick} />
        <div className="mt-6 flex flex-wrap gap-2">
          <Button disabled={i === 0} onClick={() => setI(i - 1)} data-testid="beh-prev">Previous</Button>
          <Button onClick={() => pick(null)} disabled={resp[item.qid] == null} data-testid="beh-clear">Clear</Button>
          <Button variant="dark" disabled={i === s.items.length - 1} onClick={() => setI(i + 1)} data-testid="beh-next">Next</Button>
        </div>
      </Card>
      <Card className="h-fit p-4">
        <p className="mb-2 text-xs font-bold" data-testid="beh-progress">{answered}/{s.items.length} answered · {s.minutes} min total</p>
        <div className="grid grid-cols-7 gap-1" data-testid="beh-palette">
          {s.items.map((x, j) => <button key={x.qid} onClick={() => setI(j)} className={`h-8 border text-xs font-bold ${j === i ? "border-2 border-ink" : "border-ink/20"} ${resp[x.qid] != null ? "bg-brand-green" : ""}`} data-testid={`beh-palette-${j + 1}`}>{j + 1}</button>)}
        </div>
        <p className="mt-3 text-xs text-ink/60">No right or wrong answers. Answer honestly; the timer runs on the server and the round closes automatically at 0:00.</p>
        <Button variant="green" className="mt-4 w-full" onClick={submit} data-testid="beh-submit">Submit Round 1</Button>
      </Card>
    </div>
  );
}
