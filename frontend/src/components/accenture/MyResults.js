import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { errMsg } from "../../lib/api";
import { Badge } from "../ui";

const ROUNDS = { behavioural: "Round 1 · Behavioural", gamified: "Round 2 · Gamified", technical: "Round 3 · Technical", coding: "Round 4 · Coding" };
const OVERALL = { demo_round4_disabled: "Demo — Round 4 disabled, no overall score", in_progress: "In progress", pending_behavioural_review: "Awaiting behavioural review — no verdict yet", behavioural_invalidated: "Behavioural profile invalidated — no verdict", complete: "Complete" };

function line(k, r) {
  if (k === "behavioural") return `Completed · ${r.answered}/${r.total} answered${r.profile_index != null ? ` · profile ${r.profile_index}/5` : ""} · ${r.review_status === "needs_admin_review" ? "under review" : r.review_status === "invalidated" ? "invalidated" : "no pass/fail"}`;
  return `${r.percent ?? "–"}% · ${r.passed ? "meets" : "below"} ${r.cutoff_percent}% cutoff (practice)`;
}

export default function MyResults({ mockId }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { api.get(`/accenture-mocks/${mockId}/report`).then((r) => setD(r.data)).catch((e) => setErr(errMsg(e))); }, [mockId]);
  if (err) return <p className="mt-3 text-xs text-brand-red">{err}</p>;
  if (!d) return null;
  const next = d.order.find((k) => !d.rounds[k] && !(k === "coding" && d.coding_disabled));
  const o = d.overall;
  return (
    <div className="mt-4" data-testid={`acc-results-${mockId}`}>
      {next && <Link to={`/accenture-mocks/${mockId}/${next}`} className="brutal-btn inline-flex bg-ink px-3 py-2 text-white" data-testid={`acc-catalog-next-${mockId}`}>{d.rounds.behavioural ? "Continue" : "Start"} {ROUNDS[next]}</Link>}
      <ul className="mt-3 space-y-1 text-xs">
        {d.order.map((k) => {
          const r = d.rounds[k];
          return (
            <li key={k} data-testid={`acc-results-${mockId}-${k}`}>
              <b>{ROUNDS[k]}:</b> {k === "coding" && d.coding_disabled && !r ? <span className="font-semibold text-brand-red" data-testid={`acc-results-${mockId}-coding-disabled`}>unavailable in this demo (code is not executed or scored)</span> : r ? <>{line(k, r)}{r.proctoring && r.proctoring.status !== "not_required" && <> · {r.proctoring.proctored ? `proctored (${r.proctoring.total_flags} signal${r.proctoring.total_flags === 1 ? "" : "s"} for review)` : "not proctored"}</>} · <Link to={`/accenture-mocks/${mockId}/${k}`} className="underline">view</Link></> : k === next ? "next" : "locked until the previous round is finished"}
            </li>
          );
        })}
      </ul>
      <p className="mt-2 text-xs" data-testid={`acc-overall-${mockId}`}><Badge tone={o.status === "complete" ? "green" : "yellow"}>{OVERALL[o.status]}</Badge>
        {o.practice_percent != null && <> Practice overall {o.practice_percent}% (R2–R4) · {o.rounds_meeting_cutoff}/3 cutoffs met{o.meets_all_cutoffs != null ? ` · ${o.meets_all_cutoffs ? "meets all" : "does not meet all"} cutoffs` : ""}</>}</p>
      <p className="mt-1 text-[11px] text-ink/50">{o.method}</p>
    </div>
  );
}
