import React, { useState } from "react";
import { ArrowRight, CalendarDays, CheckCircle2, ClipboardCheck, Mic, Sparkles, Target } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";
import { StepLoader } from "../Loaders";
import { Badge, Button, Card, EmptyState } from "../ui";

const PRI = { High: "red", Medium: "yellow", Low: "green" };

function Gap({ gap }) {
  const cols = [["You have", gap.have, "bg-brand-green"], ["Partial", gap.partial, "bg-brand-yellow"], ["Missing", gap.missing, "bg-brand-red text-white"]];
  return (
    <div className="grid md:grid-cols-3 gap-5">
      {cols.map(([t, list, tone]) => (
        <div key={t} className="border-3 border-ink bg-white p-5">
          <p className={`inline-block border-2 border-ink px-2 py-0.5 font-display font-bold text-sm ${tone}`}>{t}</p>
          <div className="mt-4 flex flex-wrap gap-2">{(list || []).length ? list.map((s) => <span key={s} className="tag-chip">{s}</span>) : <span className="text-sm text-ink/50">—</span>}</div>
        </div>
      ))}
    </div>
  );
}

function PracticeChoice({ job }) {
  const opts = [
    [`/mock-oa?job=${job.id}`, ClipboardCheck, "Mock OA for this job", "Questions built only from this job's posting: its requirements, skills and responsibilities.", "bg-brand-yellow", "prepare-choice-oa"],
    [`/interview?job=${job.id}`, Mic, "Mock interview for this job", "A mix of this job's requirements and your own resume: projects, experience and skills.", "bg-brand-purple", "prepare-choice-interview"],
  ];
  return (
    <section data-testid="prepare-practice-choice">
      <h3 className="text-2xl font-bold">Want to practice for this job?</h3>
      <p className="mt-1 text-sm text-ink/60">Pick one. Nothing is generated until you choose.</p>
      <div className="mt-4 grid md:grid-cols-2 gap-5">
        {opts.map(([to, I, t, d, bg, tid]) => (
          <Link key={tid} to={to} data-testid={tid} className={`group border-3 border-ink p-5 shadow-brutalsm transition-transform hover:-translate-y-1 ${bg}`}>
            <span className="flex items-center justify-between"><I size={24} /><ArrowRight size={20} className="transition-transform group-hover:translate-x-1" /></span>
            <p className="mt-3 font-display text-lg font-bold">{t}</p>
            <p className="mt-1 text-sm text-ink/70">{d}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}

export default function PrepareTab({ job }) {
  const [plan, setPlan] = useState(null);
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/prepare", { job_id: job.id });
      setPlan(data.plan);
    } catch (e) {
      toast.error(errMsg(e));
    }
    setBusy(false);
  };
  if (busy) return <StepLoader title="Building your prep plan" steps={["Comparing resume with job", "Finding skill gaps", "Planning 4-week roadmap", "Ranking subjects"]} />;
  if (!plan) return (
    <div className="space-y-10">
      <EmptyState icon={Sparkles} title="Prepare for this job" text="Get a skill-gap analysis, a 4-week roadmap and ranked subjects to study." testid="prepare-empty"
        action={<Button variant="primary" onClick={go} data-testid="generate-prep-btn"><Sparkles size={18} /> Generate prep plan</Button>} />
      <PracticeChoice job={job} />
    </div>
  );
  return (
    <div className="space-y-10" data-testid="prep-plan">
      <Card className="p-7 bg-brand-yellow/30"><h3 className="flex items-center gap-2 text-xl font-bold"><Target size={20} /> Summary</h3><p className="mt-3">{plan.match_summary}</p></Card>
      <section><h3 className="text-2xl font-bold mb-4">Skill Gap</h3><Gap gap={plan.skill_gap || {}} /></section>
      <section>
        <h3 className="flex items-center gap-2 text-2xl font-bold mb-4"><CalendarDays size={22} /> 4-Week Roadmap</h3>
        <div className="grid md:grid-cols-2 gap-5">
          {(plan.roadmap || []).map((w) => (
            <Card key={w.week} className="p-5">
              <Badge tone="dark">Week {w.week}</Badge>
              <p className="mt-3 font-display text-lg font-bold">{w.focus}</p>
              <ul className="mt-3 space-y-1.5 text-sm">{w.tasks.map((t, i) => <li key={i} className="flex gap-2"><CheckCircle2 size={16} className="shrink-0 mt-0.5 text-brand-blue" /> {t}</li>)}</ul>
            </Card>
          ))}
        </div>
      </section>
      <section>
        <h3 className="text-2xl font-bold mb-4">Important Subjects</h3>
        <div className="space-y-3">
          {(plan.important_subjects || []).map((s, i) => (
            <div key={i} className="flex items-start gap-4 border-3 border-ink bg-white p-4">
              <span className="font-mono text-2xl font-bold text-ink/30">{String(i + 1).padStart(2, "0")}</span>
              <div><p className="font-display font-bold">{s.subject} <Badge tone={PRI[s.priority]} className="ml-2">{s.priority}</Badge></p><p className="text-sm text-ink/70 mt-1">{s.why}</p></div>
            </div>
          ))}
        </div>
      </section>
      {!!(plan.milestones?.length || plan.practice_tasks?.length) && <div className="grid md:grid-cols-2 gap-5" data-testid="prep-milestones">
        <Card className="p-5"><h3 className="text-xl font-bold">Milestones</h3><ul className="mt-3 space-y-1.5 text-sm">{(plan.milestones || []).map((m, i) => <li key={i} className="flex gap-2"><CheckCircle2 size={16} className="shrink-0 mt-0.5 text-brand-green" /> {m}</li>)}</ul></Card>
        <Card className="p-5"><h3 className="text-xl font-bold">Practice tasks</h3><ul className="mt-3 list-disc pl-5 space-y-1.5 text-sm">{(plan.practice_tasks || []).map((m, i) => <li key={i}>{m}</li>)}</ul></Card>
      </div>}
      <PracticeChoice job={job} />
    </div>
  );
}
