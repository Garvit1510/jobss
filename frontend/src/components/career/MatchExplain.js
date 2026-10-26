import React from "react";
import { AlertTriangle, CheckCircle2, HelpCircle, XCircle } from "lucide-react";
import { Card, Progress } from "../ui";

const ST = { met: [CheckCircle2, "text-brand-green", "Met"], unmet: [XCircle, "text-brand-red", "Not met"], unknown: [HelpCircle, "text-ink/60", "Needs confirmation"] };

export default function MatchExplain({ e }) {
  if (!e) return null;
  return (
    <Card className="p-6" data-testid="match-explain">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-xl font-bold">Why this match{e.score != null ? `: ${e.score}%` : ""}</h3>
        <span className={`border-2 border-ink px-2 py-1 font-mono text-xs font-bold ${e.eligibility.startsWith("Not") ? "bg-brand-red text-white" : e.eligibility.startsWith("Needs") ? "bg-brand-yellow" : "bg-brand-green"}`} data-testid="match-eligibility">{e.eligibility}</span>
      </div>
      {e.score == null && <p className="mt-2 text-sm text-ink/60">Add a resume or fill your career profile to get a personal match score.</p>}
      <div className="mt-4 grid sm:grid-cols-2 gap-4">
        {e.factors.map((f) => (
          <div key={f.key} data-testid={`match-factor-${f.key}`}>
            <p className="flex justify-between font-display text-sm font-bold"><span>{f.label}</span><span className="font-mono text-xs text-ink/50">weight {f.weight}</span></p>
            <div className="mt-1.5">{f.fit == null ? <p className="font-mono text-xs text-ink/50">Unknown</p> : <Progress value={Math.round(f.fit * 100)} />}</div>
            <p className="mt-1 text-xs text-ink/60">{f.detail}</p>
          </div>
        ))}
      </div>
      <div className="mt-5 grid md:grid-cols-2 gap-4">
        <div><p className="eyebrow mb-2">You already have</p><div className="flex flex-wrap gap-1.5">{e.have.length ? e.have.map((s) => <span key={s} className="tag-chip bg-brand-green/30">{s}</span>) : <span className="text-sm text-ink/50">—</span>}</div></div>
        <div><p className="eyebrow mb-2">To develop</p><div className="flex flex-wrap gap-1.5">{e.missing.length ? e.missing.map((s) => <span key={s} className="tag-chip bg-brand-red/15">{s}</span>) : <span className="text-sm text-ink/50">—</span>}</div></div>
      </div>
      {!!e.requirements.length && (
        <div className="mt-5" data-testid="match-requirements">
          <p className="eyebrow mb-2 flex items-center gap-1.5"><AlertTriangle size={13} /> Requirements detected in the posting</p>
          <ul className="space-y-1.5">{e.requirements.map((r, i) => { const [I, c, t] = ST[r.status]; return (
            <li key={i} className="flex items-start gap-2 text-sm"><I size={16} className={`mt-0.5 shrink-0 ${c}`} /><span><b>{r.label}</b> · {t}{r.evidence && <span className="block text-xs text-ink/50">"…{r.evidence}…"</span>}</span></li>); })}</ul>
          <p className="mt-2 text-xs text-ink/50">Detected automatically from the job text. Always check the original posting.</p>
        </div>
      )}
    </Card>
  );
}
