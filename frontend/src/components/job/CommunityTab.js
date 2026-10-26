import React, { useCallback, useEffect, useState } from "react";
import { Lightbulb, PenLine, Users } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";
import { timeAgo } from "../../lib/format";
import { Badge, Button, Card, EmptyState, Modal, Spinner } from "../ui";

const OUT = { Selected: "green", Rejected: "red", Pending: "yellow", Withdrew: "white" };

function ShareForm({ company, defaultRole, onDone }) {
  const [f, setF] = useState({ role: defaultRole, year: new Date().getFullYear(), type: "Interview", outcome: "Selected", difficulty: "Medium", rounds: "", content: "", questions: "", stages: "", skills_tested: "" });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/experiences", { ...f, company, year: Number(f.year), rounds: f.rounds ? Number(f.rounds) : null, questions: f.questions.split("\n"), stages: f.stages.split(",").map((x) => x.trim()).filter(Boolean).slice(0, 10), skills_tested: f.skills_tested.split(",").map((x) => x.trim()).filter(Boolean).slice(0, 15) });
      toast.success("Thanks for sharing your experience!");
      onDone();
    } catch (ex) {
      toast.error(errMsg(ex));
    }
    setBusy(false);
  };
  const sel = (k, opts) => <select value={f[k]} onChange={set(k)} className="brutal-input" data-testid={`exp-${k}`}>{opts.map((o) => <option key={o}>{o}</option>)}</select>;
  return (
    <form onSubmit={submit} className="space-y-4" data-testid="share-experience-form">
      <input className="brutal-input" value={f.role} onChange={set("role")} placeholder="Role" required data-testid="exp-role" />
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {sel("type", ["Interview", "OA"])}
        {sel("outcome", ["Selected", "Rejected", "Pending", "Withdrew"])}
        {sel("difficulty", ["Easy", "Medium", "Hard"])}
        <input type="number" className="brutal-input" value={f.year} onChange={set("year")} min={2000} max={2100} data-testid="exp-year" />
      </div>
      <input type="number" className="brutal-input" value={f.rounds} onChange={set("rounds")} placeholder="Number of rounds (optional)" min={1} max={20} data-testid="exp-rounds" />
      <textarea className="brutal-input min-h-[140px]" value={f.content} onChange={set("content")} placeholder="Describe the process, rounds and what you'd tell others (min 30 characters)" required minLength={30} data-testid="exp-content" />
      <textarea className="brutal-input min-h-[90px]" value={f.questions} onChange={set("questions")} placeholder="Questions you were asked — one per line" data-testid="exp-questions" />
      <input className="brutal-input" value={f.stages} onChange={set("stages")} placeholder="Recruitment stages, comma separated (e.g. Online test, HR call, Panel)" data-testid="exp-stages" />
      <input className="brutal-input" value={f.skills_tested} onChange={set("skills_tested")} placeholder="Skills tested, comma separated" data-testid="exp-skills" />
      <p className="text-xs text-ink/50">Don't share personal data or confidential test material. Posts show as candidate-reported until a moderator verifies them.</p>
      <Button variant="primary" className="w-full" disabled={busy} data-testid="exp-submit">{busy ? <Spinner /> : "Share experience"}</Button>
    </form>
  );
}

function Insights({ company, count }) {
  const [d, setD] = useState(null);
  useEffect(() => {
    if (count) api.get("/experiences/insights", { params: { company } }).then((r) => setD(r.data.insights)).catch(() => {});
  }, [company, count]);
  if (!count || !d) return null;
  return (
    <Card className="p-6 bg-brand-purple/30" data-testid="community-insights">
      <h3 className="flex items-center gap-2 text-xl font-bold"><Lightbulb size={20} /> AI insights from {count} real experience{count > 1 ? "s" : ""}</h3>
      <div className="mt-4 grid md:grid-cols-2 gap-5 text-sm">
        {[["Most asked", d.most_asked], ["Patterns", d.patterns], ["Topics", d.topics], ["Tips", d.tips]].map(([t, l]) => (
          <div key={t}><p className="eyebrow mb-2">{t}</p><ul className="list-disc pl-5 space-y-1">{(l || []).map((x, i) => <li key={i}>{x}</li>)}</ul></div>
        ))}
      </div>
    </Card>
  );
}

export default function CommunityTab({ company, defaultRole }) {
  const [items, setItems] = useState(null);
  const [open, setOpen] = useState(false);
  const load = useCallback(() => api.get("/experiences", { params: { company } }).then((r) => setItems(r.data.experiences)), [company]);
  useEffect(() => {
    load();
  }, [load]);
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div><p className="eyebrow">Community</p><h3 className="text-2xl font-bold">{company} experiences</h3></div>
        <Button variant="yellow" onClick={() => setOpen(true)} data-testid="share-experience-btn"><PenLine size={17} /> Share your experience</Button>
      </div>
      <Insights company={company} count={items?.length || 0} />
      {items && !items.length && <EmptyState icon={Users} title="No experiences yet" text={`Be the first to share your ${company} interview or OA experience and help others prepare.`} testid="community-empty" />}
      {items?.map((e) => (
        <Card key={e.id} className="p-6" data-testid={`experience-${e.id}`}>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="dark">{e.type}</Badge><Badge tone={OUT[e.outcome]}>{e.outcome}</Badge><Badge>{e.difficulty}</Badge>
            <Badge tone={e.verified ? "green" : "white"} data-testid={`exp-verify-${e.id}`}>{e.verified ? "Verified" : "Candidate-reported"}</Badge>
            <button onClick={() => { const reason = window.prompt("Why are you reporting this post?"); if (reason && reason.trim().length >= 3) api.post(`/experiences/${e.id}/report`, { reason }).then(() => toast.success("Reported to moderators")).catch(() => {}); }}
              className="font-mono text-[11px] underline text-ink/60" data-testid={`exp-report-${e.id}`}>Report</button>
            {e.rounds && <Badge>{e.rounds} rounds</Badge>}
            <span className="ml-auto font-mono text-xs text-ink/50">{e.author} · {e.year} · {timeAgo(e.created_at)}</span>
          </div>
          <p className="mt-3 font-display text-lg font-bold">{e.role}</p>
          <p className="mt-2 whitespace-pre-line text-ink/80">{e.content}</p>
          {(e.stages?.length > 0 || e.skills_tested?.length > 0) && <p className="mt-3 font-mono text-xs text-ink/60">{e.stages?.length ? `Stages: ${e.stages.join(" → ")}` : ""}{e.skills_tested?.length ? ` · Skills: ${e.skills_tested.join(", ")}` : ""}</p>}
          {e.questions?.length > 0 && <ul className="mt-4 space-y-1 border-l-3 border-brand-blue pl-4 text-sm">{e.questions.map((q, i) => <li key={i}>{q}</li>)}</ul>}
        </Card>
      ))}
      <Modal open={open} onClose={() => setOpen(false)} title={`Share — ${company}`} testid="share-modal">
        <ShareForm company={company} defaultRole={defaultRole} onDone={() => { setOpen(false); load(); }} />
      </Modal>
    </div>
  );
}
