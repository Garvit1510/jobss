import React from "react";
import { motion } from "framer-motion";
import { RotateCcw } from "lucide-react";
import { Badge, Button, Card, Progress } from "../ui";
import VoiceCoach from "./VoiceCoach";
import FollowUpTrail from "./FollowUpTrail";
import ProctorReport from "../oa/ProctorReport";

const VTONE = { "Strong Hire": "green", Hire: "green", "Lean Hire": "yellow", "Lean No Hire": "red", "No Hire": "red" };

function List({ title, items, tone }) {
  return (
    <Card className={`p-6 ${tone}`}>
      <h3 className="text-xl font-bold">{title}</h3>
      <ul className="mt-3 list-disc pl-5 space-y-1.5 text-sm">{(items || []).map((x, i) => <li key={i}>{x}</li>)}</ul>
    </Card>
  );
}

export default function InterviewReport({ report: r, cfg, onRestart }) {
  const bars = [["Technical", r.technical_score], ["Communication", r.communication_score], ["Confidence", r.confidence_score]];
  return (
    <div className="mx-auto max-w-5xl px-4 md:px-8 py-12 space-y-8" data-testid="iv-report">
      <Card className="p-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="max-w-2xl">
          <p className="eyebrow">Interview report</p>
          <h1 className="text-3xl font-bold mt-1">{cfg.role}{cfg.company ? ` · ${cfg.company}` : ""}</h1>
          <Badge tone={VTONE[r.verdict] || "white"} className="mt-3 text-sm" data-testid="iv-verdict">{r.verdict}</Badge>
          <p className="mt-4 text-ink/80">{r.summary}</p>
        </div>
        <motion.div initial={{ scale: 0.6 }} animate={{ scale: 1 }} className="border-3 border-ink bg-brand-yellow px-8 py-5 text-center shadow-brutal">
          <p className="font-display text-6xl font-bold" data-testid="iv-overall-score">{r.overall_score}</p><p className="font-mono text-xs">/ 100</p>
        </motion.div>
      </Card>
      <div className="grid md:grid-cols-3 gap-5">
        {bars.map(([k, v]) => <Card key={k} className="p-5"><p className="font-display font-bold">{k}</p><p className="font-mono text-2xl font-bold my-2">{v}</p><Progress value={v} /></Card>)}
      </div>
      <div className="grid md:grid-cols-2 gap-5">
        <List title="Strengths" items={r.strengths} tone="bg-brand-green/10" />
        <List title="Mistakes" items={r.mistakes} tone="bg-brand-red/10" />
        <List title="How to improve" items={r.improvements} tone="bg-brand-yellow/20" />
        <List title="Recommendations" items={r.recommendations} tone="bg-brand-purple/20" />
      </div>
      {!!r.competencies?.length && <Card className="p-6" data-testid="iv-competencies-report"><h3 className="text-xl font-bold">Competencies</h3>
        <div className="mt-4 grid md:grid-cols-2 gap-4">{r.competencies.map((c) => (
          <div key={c.name}><p className="flex justify-between font-display text-sm font-bold"><span>{c.name}</span><span className="font-mono">{c.score}/10</span></p><div className="mt-1"><Progress value={c.score * 10} /></div><p className="mt-1 text-xs text-ink/70">{c.feedback}</p></div>
        ))}</div></Card>}
      {(r.answer_frameworks?.length || r.practice_questions?.length || r.roadmap?.length) ? <div className="grid md:grid-cols-3 gap-5" data-testid="iv-practice-report">
        <List title="Answer frameworks" items={r.answer_frameworks} tone="bg-white" />
        <List title="Practice next" items={r.practice_questions} tone="bg-brand-blue/10" />
        <List title="Improvement roadmap" items={r.roadmap} tone="bg-brand-green/10" />
      </div> : null}
      <VoiceCoach coach={r.voice_coach} tips={r.delivery_feedback} />
      {r.proctoring && <ProctorReport report={r.proctoring} />}
      {r.trail?.length ? <FollowUpTrail trail={r.trail} /> : <section>
        <h2 className="text-2xl font-bold mb-4">Question by question</h2>
        <div className="space-y-3">{(r.per_question || []).map((q, i) => (
          <div key={i} className="border-3 border-ink bg-white p-4 flex gap-4">
            <span className="font-mono text-xl font-bold shrink-0">{q.score}/10</span>
            <div><p className="font-semibold">{q.question}</p><p className="mt-1 text-sm text-ink/70">{q.comment}</p></div>
          </div>
        ))}</div>
      </section>}
      <Button variant="yellow" onClick={onRestart} data-testid="iv-restart-btn"><RotateCcw size={17} /> New interview</Button>
    </div>
  );
}
