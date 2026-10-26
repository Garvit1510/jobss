import React, { useEffect, useState } from "react";
import api from "../../lib/api";
import { Badge, Button, Card } from "../ui";

export default function Moderation() {
  const [items, setItems] = useState(null);
  const load = () => api.get("/admin/experiences").then((r) => setItems(r.data.experiences));
  useEffect(() => { load(); }, []);
  const set = async (id, patch) => { await api.post(`/admin/experiences/${id}`, patch); load(); };
  if (!items) return <p className="text-sm">Loading…</p>;
  if (!items.length) return <p className="text-sm text-ink/60" data-testid="mod-empty">No community posts yet.</p>;
  return (
    <div className="space-y-3" data-testid="moderation">
      {items.map((e) => (
        <Card key={e.id} className={`p-4 ${e.hidden ? "opacity-60" : ""}`} data-testid={`mod-${e.id}`}>
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-display font-bold">{e.company} · {e.role}</p>
            <Badge>{e.sector || "?"}</Badge>{e.verified && <Badge tone="green">Verified</Badge>}{e.hidden && <Badge tone="red">Hidden</Badge>}
            {e.reports_n > 0 && <Badge tone="red">{e.reports_n} report{e.reports_n > 1 ? "s" : ""}</Badge>}
            <div className="ml-auto flex gap-2">
              <Button className="h-8 py-0 px-3 text-xs" onClick={() => set(e.id, { verified: !e.verified })} data-testid={`mod-verify-${e.id}`}>{e.verified ? "Unverify" : "Verify"}</Button>
              <Button className="h-8 py-0 px-3 text-xs" variant="dark" onClick={() => set(e.id, { hidden: !e.hidden })} data-testid={`mod-hide-${e.id}`}>{e.hidden ? "Unhide" : "Hide"}</Button>
            </div>
          </div>
          <p className="mt-2 text-sm line-clamp-3">{e.content}</p>
          {(e.reports || []).map((r, i) => <p key={i} className="mt-1 font-mono text-[11px] text-brand-red">Report: {r.reason}</p>)}
        </Card>
      ))}
    </div>
  );
}
