import React, { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { toast } from "sonner";
import api, { errMsg } from "../lib/api";
import { useProctorDone } from "../components/accenture/ProctorGate";
import { Badge, Button, Card, Spinner } from "../components/ui";
import { fmt, useCountdown } from "../components/accenture/timer";

function Review({ s }) {
  const r = s.result;
  const rows = Object.fromEntries(r.rows.map((x) => [x.qid, x]));
  return (
    <div className="space-y-6" data-testid="tech-results">
      <Card className="p-6">
        <h2 className="text-2xl font-bold">Round 3 complete</h2>
        <p className="mt-2 text-xl font-bold" data-testid="tech-percent">{r.percent}% · {r.passed ? "meets" : "below"} the {r.cutoff_percent}% cutoff</p>
        <p className="text-sm" data-testid="tech-breakdown">{r.correct} correct · {r.incorrect} incorrect · {r.unanswered} unanswered · raw {r.raw}/{r.max}</p>
        <p className="mt-2 text-xs text-ink/60">{s.scoring.note}</p>
        <Link to={`/accenture-mocks/${s.mock_id}/coding${s.preview ? "?preview=1" : ""}`} className="brutal-btn mt-4 inline-flex bg-ink px-3 py-2 text-white" data-testid="tech-to-coding">Continue to Round 4 · Coding</Link>
      </Card>
      {s.questions.map((q, i) => (
        <Card key={q.qid} className="p-4" data-testid={`tech-review-${q.qid}`}>
          <div className="flex flex-wrap gap-1 text-xs"><b>Q{i + 1}</b><Badge>{q.category_label}</Badge><Badge tone={rows[q.qid].status === "correct" ? "green" : rows[q.qid].status === "incorrect" ? "red" : "white"}>{rows[q.qid].status}</Badge><Badge tone="yellow">{q.key_label}</Badge>{q.source_ref && <Badge tone="blue">source {q.source_ref}</Badge>}</div>
          <p className="mt-2 whitespace-pre-wrap text-sm">{q.question}</p>
          <ol className="mt-1 list-[upper-alpha] pl-5 text-sm">{q.options.map((o, j) => <li key={j} className={j === q.answer_index ? "font-bold text-brand-green" : j === rows[q.qid].choice ? "text-brand-red line-through" : ""}>{o}</li>)}</ol>
          <p className="mt-1 text-xs text-ink/60">{q.explanation}</p>
        </Card>
      ))}
    </div>
  );
}

export default function AccentureTechnical() {
  const { mockId } = useParams();
  const preview = new URLSearchParams(useLocation().search).get("preview") === "1";
  const [s, setS] = useState(null);
  useProctorDone(!!s?.finished_at);
  const [resp, setResp] = useState({});
  const [i, setI] = useState(0);
  const offset = useMemo(() => (s ? new Date(s.server_time).getTime() - Date.now() : 0), [s?.server_time]);
  const left = useCountdown(s && !s.finished_at ? s.deadline : null, offset);
  useEffect(() => { api.post(`/accenture-mocks/${mockId}/technical/start`, { preview }).then((r) => { setS(r.data); setResp(r.data.responses); }).catch((e) => { toast.error(errMsg(e)); setS({ error: errMsg(e) }); }); }, [mockId, preview]);
  useEffect(() => {
    if (!s || s.finished_at || left > 0) return undefined;
    const t = setTimeout(() => api.get(`/accenture-mocks/${mockId}/technical`).then((r) => setS(r.data)).catch(() => {}), 6000);
    return () => clearTimeout(t);
  }, [left, s, mockId]);
  if (s === null) return <div className="flex justify-center py-24"><Spinner /></div>;
  if (s.error) return <div className="p-12 text-center" data-testid="tech-unavailable"><p className="font-bold">Round 3 is not available.</p><p className="mt-2 text-sm" data-testid="tech-unavailable-reason">{s.error}</p><Link to="/accenture-mocks" className="mt-3 inline-block underline">Back to Accenture mocks</Link></div>;
  if (s.finished_at && s.result) return <div className="mx-auto max-w-4xl px-4 py-8"><Review s={s} /></div>;
  const q = s.questions[i];
  const choose = async (choice) => {
    const prev = resp[q.qid];
    setResp({ ...resp, [q.qid]: choice });
    try { await api.post(`/accenture-mocks/${mockId}/technical/answer`, { qid: q.qid, choice }); } catch (e) { setResp((r) => ({ ...r, [q.qid]: prev })); toast.error(errMsg(e)); }
  };
  const submit = async () => {
    const un = s.questions.filter((x) => resp[x.qid] === undefined || resp[x.qid] === null).length;
    if (!window.confirm(`Submit Round 3? ${un} unanswered. Incorrect answers cost 1 mark; unanswered cost 0.`)) return;
    try { const { data } = await api.post(`/accenture-mocks/${mockId}/technical/submit`); setS(data); window.scrollTo(0, 0); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="mx-auto grid max-w-7xl gap-6 px-4 py-8 lg:grid-cols-[1fr_300px]" data-testid="tech-page">
      <Card className="p-6">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-ink/60" data-testid="tech-q-meta">Round 3 · Question {i + 1} of {s.questions.length} · {q.category_label}{preview ? " · Admin preview" : ""}</p>
          <span className={`font-mono text-lg font-bold ${left <= 300 ? "text-brand-red" : ""}`} data-testid="tech-timer">{fmt(left)}</span>
        </div>
        <p className="mt-4 whitespace-pre-wrap font-mono text-[15px] leading-relaxed" data-testid="tech-question">{q.question}</p>
        <div className="mt-6 space-y-2">
          {q.options.map((o, j) => (
            <button key={j} onClick={() => choose(j)} className={`flex w-full items-start gap-3 border-2 px-4 py-3 text-left transition-colors ${resp[q.qid] === j ? "border-ink bg-brand-yellow" : "border-ink/20 hover:border-ink"}`} data-testid={`tech-option-${j}`}>
              <b>{String.fromCharCode(65 + j)}.</b><span className="whitespace-pre-wrap">{o}</span>
            </button>
          ))}
        </div>
        <div className="mt-6 flex flex-wrap gap-2">
          <Button disabled={i === 0} onClick={() => setI(i - 1)} data-testid="tech-prev">Previous</Button>
          <Button onClick={() => choose(null)} disabled={resp[q.qid] === undefined || resp[q.qid] === null} data-testid="tech-clear">Clear answer</Button>
          <Button variant="dark" disabled={i === s.questions.length - 1} onClick={() => setI(i + 1)} data-testid="tech-next">Next</Button>
        </div>
      </Card>
      <Card className="h-fit p-4">
        <p className="mb-2 text-xs font-bold">Scoring: +{s.scoring.correct} / {s.scoring.wrong} / {s.scoring.unanswered}</p>
        <div className="grid grid-cols-7 gap-1" data-testid="tech-palette">
          {s.questions.map((x, j) => <button key={x.qid} onClick={() => setI(j)} title={x.category_label} className={`h-8 border text-xs font-bold ${j === i ? "border-2 border-ink" : "border-ink/20"} ${resp[x.qid] !== undefined && resp[x.qid] !== null ? "bg-brand-green" : ""}`} data-testid={`tech-palette-${j + 1}`}>{j + 1}</button>)}
        </div>
        <Button variant="green" className="mt-4 w-full" onClick={submit} data-testid="tech-submit">Submit Round 3</Button>
      </Card>
    </div>
  );
}
