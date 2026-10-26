import React from "react";
import { motion } from "framer-motion";
import { CheckCircle2, ExternalLink, MinusCircle, RotateCcw, TrendingUp, XCircle } from "lucide-react";
import { Badge, Button, Card, Progress } from "../ui";
import ProctorReport from "./ProctorReport";

const VERDICT = { Correct: "green", Accepted: "green", "Partially Correct": "yellow", Incorrect: "red", "Wrong Answer": "red", "Not Attempted": "white" };
const KIND = { coding: "Code", sql: "MySQL", web: "HTML/CSS/JS" };

function Answer({ q }) {
  const Icon = q.correct === true ? CheckCircle2 : q.correct === false ? XCircle : MinusCircle;
  const tone = q.correct === true ? "text-brand-green" : q.correct === false ? "text-brand-red" : "text-ink/40";
  const empty = q.given === null || q.given === undefined || q.given === "";
  return (
    <div className="border-3 border-ink bg-white p-4" data-testid={`oa-review-${q.id}`}>
      <p className="flex gap-2 font-semibold"><Icon className={`shrink-0 ${tone}`} size={20} /> <span className="whitespace-pre-line">{q.question}</span></p>
      {q.type === "mcq" || !q.type ? (
        <p className="mt-2 text-sm"><b>Correct:</b> {q.options?.[q.answer_index]}{!empty && !q.correct && <> · <b>Yours:</b> {q.options?.[q.given]}</>}{empty && <> · <i>Not answered</i></>}</p>
      ) : q.type === "numeric" ? (
        <p className="mt-2 text-sm font-mono"><b>Correct:</b> {q.answer} {q.unit}{!empty ? <> · <b>Yours:</b> {q.given}</> : <> · <i>Not answered</i></>}</p>
      ) : (
        <div className="mt-2 text-sm space-y-1.5">
          {empty ? <p><i>Not answered</i></p> : <p className="whitespace-pre-line border-l-3 border-ink/20 pl-3 text-ink/80">{q.given}</p>}
          {q.ai_score != null && <p><Badge tone={q.ai_score >= 4 ? "green" : q.ai_score >= 3 ? "yellow" : "red"}>AI score {q.ai_score}/5</Badge> {q.feedback}</p>}
          {q.ai_score == null && q.feedback && <p className="text-ink/60">{q.feedback}</p>}
          {q.model_answer && <p className="text-ink/70"><b>Strong answer covers:</b> {q.model_answer}</p>}
        </div>
      )}
      {q.explanation && <p className="mt-1 text-sm text-ink/70">{q.explanation}</p>}
    </div>
  );
}

export default function OAResult({ result, title, onRestart }) {
  const r = result;
  const ins = r.insights || {};
  const pg = r.progress || {};
  return (
    <div className="mx-auto max-w-5xl px-4 md:px-8 py-12 space-y-8" data-testid="oa-result">
      <Card className="p-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div><p className="eyebrow">Result</p><h1 className="text-3xl font-bold mt-1">{title}</h1>
          <p className="mt-2 font-mono text-sm text-ink/60">Objective {r.mcq_correct}/{r.mcq_total}{r.coding_max ? ` · Coding ${r.coding_points}/${r.coding_max}` : ""} · {Math.round(r.time_taken_sec / 60)} min</p>
          {pg.attempts_before > 0 && <p className="mt-2 flex items-center gap-1.5 font-mono text-sm" data-testid="oa-progress"><TrendingUp size={15} /> {pg.attempts_before} earlier attempt{pg.attempts_before > 1 ? "s" : ""} in this field · avg {pg.previous_avg}% · best {pg.previous_best}% · {pg.delta_vs_avg >= 0 ? "+" : ""}{pg.delta_vs_avg} vs avg</p>}
        </div>
        <motion.p initial={{ scale: 0.6 }} animate={{ scale: 1 }} className={`border-3 border-ink px-8 py-4 font-display text-6xl font-bold shadow-brutal ${r.score_pct >= 70 ? "bg-brand-green" : r.score_pct >= 40 ? "bg-brand-yellow" : "bg-brand-red text-white"}`} data-testid="oa-score">{r.score_pct}%</motion.p>
      </Card>
      {r.note && <p className="border-2 border-ink bg-white p-3 text-sm" data-testid="oa-note">{r.note}</p>}
      {r.auto_reason && <p className="border-3 border-ink bg-brand-yellow p-4 font-display font-semibold" data-testid="oa-auto-reason">{r.auto_reason}</p>}
      {r.proctoring && <ProctorReport report={r.proctoring} />}
      <div className="grid md:grid-cols-3 gap-5">
        {r.sections.map((s) => (
          <Card key={s.name} className="p-5" data-testid={`oa-section-${s.name}`}><p className="font-display font-bold">{s.name}</p>
            <p className="font-mono text-2xl font-bold mt-2">{s.pct ?? Math.round((100 * s.correct) / Math.max(1, s.total))}%</p>
            <p className="font-mono text-xs text-ink/50">{s.points != null ? `${s.points}/${s.max} points` : `${s.correct}/${s.total}`}</p>
            <div className="mt-3"><Progress value={s.pct ?? (100 * s.correct) / Math.max(1, s.total)} /></div></Card>
        ))}
      </div>
      {(ins.strengths || ins.weaknesses) && (
        <div className="grid md:grid-cols-2 gap-5" data-testid="oa-insights">
          <Card className="p-6 bg-brand-green/10"><h3 className="text-xl font-bold">Strengths</h3><ul className="mt-3 list-disc pl-5 text-sm space-y-1">{(ins.strengths || []).map((x, i) => <li key={i}>{x}</li>)}</ul></Card>
          <Card className="p-6 bg-brand-red/10"><h3 className="text-xl font-bold">Weak areas</h3><ul className="mt-3 list-disc pl-5 text-sm space-y-1">{(ins.weaknesses || []).map((x, i) => <li key={i}>{x}</li>)}</ul></Card>
          <Card className="p-6 bg-brand-yellow/20"><h3 className="text-xl font-bold">Skill gaps</h3><div className="mt-3 flex flex-wrap gap-1.5">{(ins.skill_gaps || []).map((x) => <span key={x} className="tag-chip">{x}</span>)}</div></Card>
          <Card className="p-6 bg-brand-purple/20"><h3 className="text-xl font-bold">Next practice plan</h3><ol className="mt-3 list-decimal pl-5 text-sm space-y-1">{(ins.next_plan || []).map((x, i) => <li key={i}>{x}</li>)}</ol></Card>
        </div>
      )}
      {!!ins.resources?.length && <Card className="p-6" data-testid="oa-resources"><h3 className="text-xl font-bold">Learn next</h3>
        <ul className="mt-3 grid sm:grid-cols-2 gap-2">{ins.resources.map((x, i) => <li key={i}><a href={x.url} target="_blank" rel="noreferrer" className="flex items-center justify-between gap-2 border-2 border-ink bg-offwhite px-3 py-2 text-sm font-semibold hover:bg-brand-yellow/40"><span>{x.title}</span><span className="flex shrink-0 items-center gap-1 font-mono text-[10px]">{x.cost} <ExternalLink size={12} /></span></a></li>)}</ul>
        <p className="mt-2 text-xs text-ink/50">Links open searches on the named platform; we don't claim affiliation.</p></Card>}
      {ins.note && <p className="text-sm text-ink/60">{ins.note}</p>}
      {!!r.coding?.length && <section>
        <h2 className="text-2xl font-bold mb-4">Coding review</h2>
        <div className="space-y-4">{r.coding.map((c) => (
          <Card key={c.id} className="p-5" data-testid={`oa-result-prog-${c.id}`}>{c.title && <p className="mb-2 font-display font-bold">{c.title} <span className="font-mono text-xs text-ink/50">· {KIND[c.kind] || "Code"}</span></p>}<div className="flex items-center gap-3"><Badge tone={VERDICT[c.verdict]}>{c.verdict}</Badge><span className="font-mono font-bold">{c.score}/10</span><span className="font-mono text-xs text-ink/50">{c.complexity}</span>{c.tests_total ? <span className="ml-auto border-2 border-ink px-2 py-0.5 font-mono text-xs font-bold" data-testid={`oa-result-tests-${c.id}`}>{c.tests_passed}/{c.tests_total} tests</span> : null}</div><p className="mt-3 text-sm">{c.feedback}</p></Card>
        ))}</div>
      </section>}
      <section>
        <h2 className="text-2xl font-bold mb-4">Answer review</h2>
        <div className="space-y-3">{r.review.map((q) => <Answer key={q.id} q={q} />)}</div>
      </section>
      <Button variant="yellow" onClick={onRestart} data-testid="oa-restart-btn"><RotateCcw size={17} /> Take another OA</Button>
    </div>
  );
}
