import React, { useState } from "react";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";
import { Badge, Button, Card } from "../ui";

const SECTIONS = [
  ["implemented_confirmed", "Implemented and confirmed (live checks run just now)", "green"],
  ["implemented_not_independently_verified", "Implemented, confirmed by code inspection only (not independently verified)", "yellow"],
  ["blocked_infrastructure", "Blocked by missing infrastructure", "red"],
  ["blocked_manual_review", "Blocked by manual content review", "red"],
];

export default function ReleaseReadiness() {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState(false);
  const run = async () => { setBusy(true); try { setD((await api.get("/admin/accenture-mocks/release-readiness")).data); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); } };
  return (
    <Card className="p-5" data-testid="acc-release-readiness">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-lg font-bold">Release readiness (read-only)</h3>
        <Button className="px-2 py-1 text-xs" disabled={busy} onClick={run} data-testid="acc-readiness-run">{busy ? "Running live probes…" : "Run check"}</Button>
      </div>
      <p className="text-xs text-ink/60">Re-runs the sandbox escape probes on every check. A configured flag or a successful API response is never counted as proof.</p>
      {d && (
        <div className="mt-3 space-y-4 text-sm">
          <p data-testid="acc-readiness-verdict"><Badge tone={d.publishable === false ? "red" : "yellow"}>{d.publishable === false ? "Not releasable" : "Review"}</Badge> Runner {d.sandbox.ready ? "verified (jail)" : "CLOSED"} · kernel-isolation flag {String(d.sandbox.kernel_isolation_flag)} · published {d.published_library ? `v${d.published_library.version}` : "none"} · unlocked {d.unlocked_mocks.length ? d.unlocked_mocks.join(", ") : "none"}</p>
          {SECTIONS.map(([k, title, tone]) => (
            <div key={k} data-testid={`acc-readiness-${k}`}>
              <p className="font-bold"><Badge tone={tone}>{d.sections[k].length}</Badge> {title}</p>
              <ul className="mt-1 list-disc pl-5 text-xs">{d.sections[k].map((x, i) => <li key={i}>{x}</li>)}</ul>
            </div>
          ))}
          <details className="text-xs" data-testid="acc-readiness-probes"><summary className="cursor-pointer font-bold">Sandbox probe details ({d.sandbox.checks.filter((c) => c.passed).length}/{d.sandbox.checks.length} passed · {d.sandbox.verified_at || "never"})</summary>
            <ul className="mt-1 space-y-0.5">{d.sandbox.checks.map((c) => <li key={c.check}><Badge tone={c.passed ? "green" : "red"}>{c.passed ? "pass" : "fail"}</Badge> {c.check}{!c.passed && c.detail ? ` — ${c.detail}` : ""}</li>)}</ul></details>
          <p className="text-xs text-ink/60">All scoring is practice scoring, not official Accenture scoring.</p>
        </div>
      )}
    </Card>
  );
}
