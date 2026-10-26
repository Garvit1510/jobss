import React, { useEffect, useState } from "react";
import { Clock, Layers } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../lib/api";
import { Badge, Card, EmptyState, Skeleton } from "../components/ui";
import MyResults from "../components/accenture/MyResults";

export default function AccentureMocks() {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/accenture-mocks").then((r) => setD(r.data)).catch((e) => { toast.error(errMsg(e)); setD({ mocks: [] }); }); }, []);
  return (
    <div className="mx-auto max-w-7xl px-4 md:px-8 py-12" data-testid="acc-catalog-page">
      <p className="eyebrow mb-2">Predefined · four rounds</p>
      <h1 className="text-4xl md:text-5xl font-bold">Accenture Mock OAs</h1>
      <p className="mt-3 max-w-2xl text-ink/70">Full-length practice assessments modelled on the Accenture online assessment: Behavioural, Gamified, Technical MCQs and Coding. Practice content — not official Accenture questions.</p>
      <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {!d ? [0, 1, 2].map((i) => <Skeleton key={i} className="h-48" />) : !d.mocks.length ? (
          <div className="sm:col-span-2 lg:col-span-3"><EmptyState title="No Accenture mocks available yet" /></div>
        ) : d.mocks.map((m) => (
          <Card key={m.mock_id} hover className="p-5" data-testid={`acc-catalog-${m.mock_id}`}>
            <div className="flex items-center justify-between">
              <span className="font-mono text-3xl font-bold">{m.mock_id}</span>
              <Badge tone="yellow"><Clock size={12} /> {m.total_minutes} min</Badge>
            </div>
            <p className="mt-1 font-display font-semibold">{m.title}</p>
            {m.demo_mode && <p className="mt-2 border-2 border-brand-red bg-brand-red/10 p-2 text-xs font-semibold" data-testid={`acc-catalog-demo-${m.mock_id}`}>Demo · Round 4 coding unavailable. {m.demo_message}</p>}
            <ul className="mt-4 space-y-1 text-sm">
              {m.rounds.map((r) => (
                <li key={r.key}>
                  <div className="flex justify-between gap-2"><span className={`flex items-center gap-1 font-semibold ${r.disabled ? "text-ink/40 line-through" : ""}`}><Layers size={13} /> {r.title}{r.disabled && <Badge tone="red" className="ml-1 no-underline">disabled in demo</Badge>}</span><span className="font-mono text-xs">{r.items} {r.unit} · {r.minutes}m</span></div>
                  {(r.sections || r.activities) && <p className="pl-5 text-xs text-ink/60">{(r.sections || r.activities).join(" · ")}</p>}
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-ink/50">Rounds unlock in order (1 → 2 → 3 → 4). One attempt per round; order, timers and access are enforced by the server. All scores are practice scores, not official Accenture scoring.</p>
            <MyResults mockId={m.mock_id} />
          </Card>
        ))}
      </div>
    </div>
  );
}
