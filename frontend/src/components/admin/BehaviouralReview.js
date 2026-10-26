import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";
import { Badge, Button, Card } from "../ui";

function Row({ a, onDone }) {
  const r = a.result;
  const review = async (decision) => {
    try { await api.post(`/admin/accenture-mocks/behavioural-attempts/${a.id}/review`, { decision }); toast.success(`Marked ${decision}`); onDone(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="border-2 border-ink p-3 text-sm" data-testid={`beh-attempt-${a.id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <b>{a.user?.email || a.user_id}</b><Badge tone="dark">{a.mock_id}</Badge>{a.preview && <Badge>preview</Badge>}
        <span className="text-xs">{r.answered}/{r.total} answered · index {r.profile_index ?? "–"}</span>
        <Badge tone={a.admin_review ? (a.admin_review.status === "accepted" ? "green" : "red") : r.flags.length ? "yellow" : "green"}>{a.admin_review?.status || r.review.status}</Badge>
      </div>
      <ul className="mt-1 list-disc pl-5 text-xs text-brand-red">{r.flags.map((f) => <li key={f.code}><b>{f.code}</b>: {f.detail}</li>)}</ul>
      <p className="mt-1 text-xs text-ink/70">{Object.values(r.traits).map((t) => `${t.label} ${t.mean ?? "–"} (${t.band || "n/a"})`).join(" · ")}</p>
      <div className="mt-2 flex gap-1">
        <Button variant="green" className="px-2 py-1 text-xs" onClick={() => review("accepted")} data-testid={`beh-accept-${a.id}`}>Accept profile</Button>
        <Button className="px-2 py-1 text-xs" onClick={() => review("invalidated")} data-testid={`beh-invalidate-${a.id}`}>Invalidate</Button>
        {a.admin_review && <Button className="px-2 py-1 text-xs" onClick={() => review("reset")} data-testid={`beh-reset-${a.id}`}>Reset</Button>}
      </div>
    </div>
  );
}

export default function BehaviouralReview() {
  const [status, setStatus] = useState("flagged");
  const [rows, setRows] = useState(null);
  const load = useCallback(() => api.get("/admin/accenture-mocks/behavioural-attempts", { params: { status } }).then((r) => setRows(r.data.attempts)).catch((e) => toast.error(errMsg(e))), [status]);
  useEffect(() => { load(); }, [load]);
  return (
    <Card className="p-5" data-testid="acc-beh-review">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-lg font-bold">Round 1 profiles · admin review</h3>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="brutal-input py-1 text-sm" data-testid="beh-review-filter"><option value="flagged">Flagged, unreviewed</option><option value="all">All finished</option></select>
      </div>
      <p className="text-xs text-ink/60">Ambiguous response patterns are flagged here instead of producing a pass/fail. Only admins can see individual responses and flags.</p>
      <div className="mt-3 space-y-2">{!rows ? null : !rows.length ? <p className="text-sm text-ink/60" data-testid="beh-review-empty">Nothing to review.</p> : rows.map((a) => <Row key={a.id} a={a} onDone={load} />)}</div>
    </Card>
  );
}
