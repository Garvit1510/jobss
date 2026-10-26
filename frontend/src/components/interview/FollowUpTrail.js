import React from "react";
import { CornerDownRight, Layers } from "lucide-react";
import { Badge } from "../ui";

const scoreBg = (s) => (s >= 7 ? "bg-brand-green" : s >= 4 ? "bg-brand-yellow" : "bg-brand-red text-white");

function Step({ t, follow }) {
  return (
    <div className={`flex gap-4 border-ink bg-white p-4 ${follow ? "border-2" : "border-3"}`} data-testid={`trail-q-${t.n}`}>
      <span className={`h-fit shrink-0 border-2 border-ink px-2 py-1 font-mono text-sm font-bold ${scoreBg(t.score ?? 0)}`}>{t.score ?? "-"}/10</span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          {follow ? <Badge tone="dark">Follow-up</Badge> : t.stage && <Badge className="capitalize">{t.stage}</Badge>}
          {t.difficulty && <Badge tone="yellow">{t.difficulty}</Badge>}
        </div>
        <p className="mt-2 font-semibold">{t.question}</p>
        <p className="mt-1 text-sm text-ink/60 line-clamp-2"><b>You:</b> {t.answer}</p>
        {t.code && <pre className="mt-2 max-h-40 overflow-auto border-2 border-ink bg-ink p-2 font-mono text-[11px] text-white">{t.code}</pre>}
        {t.feedback && <p className="mt-2 text-sm text-ink/80">{t.feedback}</p>}
      </div>
    </div>
  );
}

export default function FollowUpTrail({ trail }) {
  return (
    <section data-testid="iv-trail">
      <h2 className="text-2xl font-bold mb-4 flex items-center gap-2"><Layers size={22} /> Follow-up trail</h2>
      <div className="space-y-5">{trail.map((g) => (
        <div key={g.n}>
          <div className="mb-1.5 flex justify-end"><span className="font-mono text-[11px] text-ink/50" data-testid={`trail-depth-${g.n}`}>{g.depth ? `${g.depth} follow-up${g.depth > 1 ? "s" : ""} deep` : "No follow-up"}</span></div>
          <Step t={g} />
          {g.follow_ups.map((f) => (
            <div key={f.n} className="ml-4 md:ml-8 mt-2 flex gap-2">
              <CornerDownRight size={18} className="mt-4 shrink-0 text-ink/40" />
              <div className="flex-1"><Step t={f} follow /></div>
            </div>
          ))}
        </div>
      ))}</div>
    </section>
  );
}
