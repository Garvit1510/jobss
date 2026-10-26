import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ClipboardCheck, Mic, Target } from "lucide-react";
import api from "../../lib/api";
import { Card, Skeleton } from "../ui";

export default function CareerOverview() {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(false);
  useEffect(() => {
    api.get("/career/overview").then((r) => setD(r.data)).catch(() => setErr(true));
  }, []);
  if (err) return null;
  if (!d) return <Skeleton className="h-56" />;
  const sec = d.sectors[0];
  return (
    <div className="grid lg:grid-cols-[1fr_360px] gap-6" data-testid="career-overview">
      <Card className="p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="flex items-center gap-2 text-2xl font-bold"><Target size={22} /> Best matches {sec ? `in ${sec.name}` : ""}</h2>
          <Link to={sec ? `/jobs?sector=${sec.id}` : "/jobs"} className="font-display text-sm font-bold underline" data-testid="overview-all-jobs">See all</Link>
        </div>
        <ul className="mt-4 space-y-3">{d.top_jobs.length ? d.top_jobs.map((j) => (
          <li key={j.id} className="border-2 border-ink bg-white p-3" data-testid={`overview-job-${j.id}`}>
            <Link to={`/jobs/${j.id}`} className="flex items-center justify-between gap-3"><span className="min-w-0"><span className="block truncate font-display font-bold">{j.title}</span><span className="font-mono text-xs text-ink/60">{j.company}</span></span>
              <span className="shrink-0 border-2 border-ink bg-brand-yellow px-2 font-mono text-sm font-bold">{j.match ?? "—"}%</span></Link>
            {!!j.why.length && <p className="mt-1.5 text-xs text-ink/70"><b>Why:</b> {j.why.join(" · ")}</p>}
            {!!j.missing.length && <p className="text-xs text-ink/60"><b>To develop:</b> {j.missing.join(", ")}</p>}
          </li>
        )) : <p className="text-sm text-ink/60">No live listings found for your sectors yet. Coverage for some industries is limited; try other sectors or set an alert.</p>}</ul>
        {!!d.skill_gaps.length && <div className="mt-5"><p className="eyebrow mb-2">Most requested skills you don't list yet</p><div className="flex flex-wrap gap-1.5">{d.skill_gaps.map(([s, n]) => <span key={s} className="tag-chip">{s} · {n}</span>)}</div></div>}
      </Card>
      <div className="space-y-6">
        <Card className="p-6" data-testid="overview-practice">
          <h3 className="text-lg font-bold">Recommended practice</h3>
          <div className="mt-3 grid gap-2">
            <Link to={`/mock-oa${sec ? `?sector=${sec.id}` : ""}`} className="brutal-btn bg-white justify-start text-sm" data-testid="overview-oa"><ClipboardCheck size={16} /> {sec ? `${sec.oa_sections.slice(0, 2).join(" + ")} test` : "Mock assessment"}</Link>
            <Link to={`/interview${sec ? `?sector=${sec.id}` : ""}`} className="brutal-btn bg-white justify-start text-sm" data-testid="overview-interview"><Mic size={16} /> {sec ? `${sec.styles[0]} interview` : "AI interview"}</Link>
          </div>
          {!!d.recent_oa.length && <p className="mt-3 font-mono text-xs text-ink/60">Last assessments: {d.recent_oa.map((o) => `${o.result.score_pct}%`).join(" · ")}</p>}
        </Card>
      </div>
    </div>
  );
}
