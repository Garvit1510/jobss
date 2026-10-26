import React, { useState } from "react";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";
import { Badge, Button } from "../ui";

const chip = (on, label, offLabel, tone = "green") => <Badge tone={on ? tone : "white"} className="mr-1 mb-1">{on ? label : offLabel}</Badge>;

export default function MockPublication({ m, onDone }) {
  const s = m.state;
  const [blk, setBlk] = useState(null);
  const [busy, setBusy] = useState(false);
  if (!s || m.status === "pending") return <span className="text-xs text-ink/40">–</span>;
  const call = async (path, mode = "full") => {
    setBusy(true);
    try {
      await api.post(`/admin/accenture-mocks/mocks/${m.mock_id}/${path}`, path === "publish" ? { library_id: m.library_id, mode } : {});
      toast.success(path === "unpublish" ? `${m.mock_id} unpublished — removed from candidate access` : mode === "full" ? `${m.mock_id} published individually` : `${m.mock_id} published in DEMO mode — Round 4 coding disabled for candidates`);
      setBlk(null); onDone();
    } catch (e) {
      const d = e?.response?.data?.detail;
      if (d && typeof d === "object" && !Array.isArray(d)) { setBlk(d); toast.error(d.message); } else toast.error(errMsg(e));
    } finally { setBusy(false); }
  };
  const list = blk || (s.release_blocked ? { content_blockers: s.content_blockers, security_blockers: s.security_blockers } : null);
  return (
    <div className="min-w-[260px] text-xs" data-testid={`acc-mock-publication-${m.mock_id}`}>
      <div className="flex flex-wrap">
        {chip(s.valid, "valid", "not valid")}{chip(s.reviewed, "reviewed", "review pending", "green")}
        {chip(s.published, s.published_individually ? (s.round4_disabled ? "published (DEMO · R4 disabled)" : "published (individual)") : "published (library)", "unpublished", "dark")}
        {chip(s.unlocked, "unlocked", "locked")}{chip(s.candidate_visible, "candidate-visible", "hidden from candidates")}
        {chip(s.release_blocked, "release-blocked", "release-ready", "red")}
      </div>
      {s.published_individually
        ? <Button className="mt-1 px-2 py-1 text-xs" disabled={busy} onClick={() => window.confirm(`Unpublish ${m.mock_id}? Candidates lose access immediately; content and results are kept.`) && call("unpublish")} data-testid={`acc-mock-unpublish-${m.mock_id}`}>Unpublish mock</Button>
        : <div className="mt-1 flex flex-wrap gap-1">
            <Button variant="green" className="px-2 py-1 text-xs" disabled={busy || m.status !== "valid"} onClick={() => call("publish")} data-testid={`acc-mock-publish-${m.mock_id}`}>{busy ? "Checking…" : "Publish individual mock"}</Button>
            {s.demo_available && <Button className="px-2 py-1 text-xs" disabled={busy} onClick={() => window.confirm(`Publish ${m.mock_id} as a DEMO? Rounds 1–3 open to candidates; Round 4 coding is disabled (no code executed or scored, no overall score). The runner is NOT marked secure.`) && call("publish", "demo_no_coding")} data-testid={`acc-mock-publish-demo-${m.mock_id}`}>Publish demo (Round 4 disabled)</Button>}
          </div>}
      {s.round4_disabled && <p className="mt-1 text-[11px] font-semibold text-brand-red" data-testid={`acc-mock-demo-note-${m.mock_id}`}>Demo publication: Round 4 is closed for candidates; still release-blocked until the runner is isolated.</p>}
      {list && (list.content_blockers.length + list.security_blockers.length > 0) && (
        <ul className="mt-1 list-disc pl-4 text-[11px] text-brand-red" data-testid={`acc-mock-blockers-${m.mock_id}`}>
          {list.content_blockers.map((x) => <li key={x}>Content: {x}</li>)}
          {list.security_blockers.map((x) => <li key={x}>Security: {x}</li>)}
        </ul>
      )}
    </div>
  );
}
