import React from "react";
import { ShieldCheck } from "lucide-react";
import { Badge, Card } from "../ui";
import { FLAG_INFO } from "../../lib/useProctor";

const RISK = { Low: "green", Medium: "yellow", High: "red" };

export default function ProctorReport({ report }) {
  const r = report;
  return (
    <section data-testid="proctor-report">
      <h2 className="text-2xl font-bold mb-4 flex items-center gap-2"><ShieldCheck size={24} /> Proctoring report</h2>
      <Card className="p-6">
        <div className="flex flex-wrap items-center gap-6">
          <div><p className="eyebrow">Integrity score</p><p className="font-display text-5xl font-bold" data-testid="proctor-integrity-score">{r.integrity_score}</p></div>
          <div><p className="eyebrow mb-1">Risk</p><Badge tone={RISK[r.risk]} className="text-sm" data-testid="proctor-risk">{r.risk} risk</Badge></div>
          <div><p className="eyebrow">Total flags</p><p className="font-mono text-2xl font-bold" data-testid="proctor-total-flags">{r.total_flags}</p></div>
        </div>
        <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-3">
          {Object.entries(FLAG_INFO).map(([k, v]) => (
            <div key={k} className={`border-2 border-ink p-3 ${r.counts[k] ? "bg-brand-red/10" : "bg-offwhite"}`} data-testid={`proctor-count-${k}`}>
              <p className="text-xs font-display font-semibold">{v.label}</p>
              <p className="font-mono text-xl font-bold">{r.counts[k] || 0}</p>
            </div>
          ))}
        </div>
        {r.timeline.length > 0 && (
          <ul className="mt-6 max-h-64 overflow-y-auto divide-y-2 divide-ink/10 border-2 border-ink" data-testid="proctor-timeline">
            {r.timeline.map((f, i) => (
              <li key={i} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                <span className="font-semibold">{FLAG_INFO[f.type]?.label || f.type}{f.detail && <span className="font-normal text-ink/60"> · {f.detail}</span>}</span>
                <span className="font-mono text-xs text-ink/50">{new Date(f.at).toLocaleTimeString()}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </section>
  );
}
