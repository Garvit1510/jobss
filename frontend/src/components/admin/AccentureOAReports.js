import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";
import { FLAG_INFO } from "../../lib/useProctor";
import { Badge, Button, Card } from "../ui";

const NAMES = { behavioural: "R1", gamified: "R2", technical: "R3", coding: "R4" };

function ProctorPolicy() {
  const [c, setC] = useState(null);
  useEffect(() => { api.get("/admin/accenture-mocks/settings/proctoring").then((r) => setC(r.data)).catch((e) => toast.error(errMsg(e))); }, []);
  if (!c) return null;
  const save = async () => { try { setC({ ...c, ...(await api.put("/admin/accenture-mocks/settings/proctoring", { mode: c.mode, ignore_flags: c.ignore_flags })).data }); toast.success("Proctoring policy saved (applies to new round attempts of every mock)"); } catch (e) { toast.error(errMsg(e)); } };
  const tog = (f) => setC({ ...c, ignore_flags: c.ignore_flags.includes(f) ? c.ignore_flags.filter((x) => x !== f) : [...c.ignore_flags, f] });
  return (
    <div data-testid="acc-proctor-policy">
      <p className="text-sm font-bold">Shared proctoring policy (inherited by all mocks, incl. newly generated)</p>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
        {["off", "optional", "strict"].map((m) => <label key={m} className="flex items-center gap-1"><input type="radio" checked={c.mode === m} onChange={() => setC({ ...c, mode: m })} data-testid={`acc-proctor-mode-${m}`} /> {m}</label>)}
        <Button className="ml-auto px-2 py-1 text-xs" onClick={save} data-testid="acc-proctor-save">Save</Button>
      </div>
      <p className="mt-1 text-xs text-ink/60">strict: camera, mic, face registration and fullscreen are required before a round starts; attempts without an active session are reported as NOT proctored. optional: the candidate may decline (reported as unproctored). Events never auto-submit; they are review signals.</p>
      <p className="mt-2 text-xs font-bold">Ignored signals</p>
      <div className="mt-1 flex flex-wrap gap-1">{c.flag_types.map((f) => <button key={f} onClick={() => tog(f)} className={`border-2 px-1.5 py-0.5 text-[11px] ${c.ignore_flags.includes(f) ? "border-ink bg-ink text-white" : "border-ink/20"}`} data-testid={`acc-proctor-ignore-${f}`}>{FLAG_INFO[f]?.label || f}</button>)}</div>
    </div>
  );
}

function Proc({ p }) {
  if (!p || p.status === "not_required") return <span className="text-ink/40">not required</span>;
  if (!p.proctored) return <Badge tone={p.mode === "strict" ? "red" : "white"}>{p.status.replace("_", " ")}{p.init_failure ? ` · ${p.init_failure}` : ""}</Badge>;
  return (
    <details>
      <summary className="cursor-pointer"><Badge tone={p.total_flags ? "yellow" : "green"}>integrity {p.integrity_score} · {p.total_flags} signal{p.total_flags === 1 ? "" : "s"}</Badge></summary>
      <ul className="mt-1 max-h-40 overflow-y-auto">{(p.timeline || []).map((f, i) => <li key={i}>{new Date(f.at).toLocaleTimeString()} · {FLAG_INFO[f.type]?.label || f.type}{f.detail ? ` (${f.detail})` : ""}</li>)}</ul>
      {p.session_id && <p className="text-ink/50">Evidence photos: Admin → Proctor photos (session {p.session_id.slice(0, 8)})</p>}
    </details>
  );
}

export default function AccentureOAReports() {
  const [d, setD] = useState(null);
  const [prev, setPrev] = useState(false);
  const load = useCallback(() => api.get("/admin/accenture-mocks/attempt-reports", { params: { include_preview: prev } }).then((r) => setD(r.data)).catch((e) => toast.error(errMsg(e))), [prev]);
  useEffect(() => { load(); }, [load]);
  return (
    <Card className="space-y-4 p-5" data-testid="acc-oa-reports">
      <h3 className="text-lg font-bold">Mock OA proctoring & attempt reports</h3>
      <ProctorPolicy />
      <div className="flex items-center gap-2 text-sm"><label className="flex items-center gap-1"><input type="checkbox" checked={prev} onChange={(e) => setPrev(e.target.checked)} data-testid="acc-reports-preview" /> include admin previews</label><Button className="ml-auto px-2 py-1 text-xs" onClick={load}>Refresh</Button></div>
      <p className="text-xs text-ink/60">{d?.note}</p>
      <div className="space-y-2">{!d ? null : !d.reports.length ? <p className="text-sm text-ink/60" data-testid="acc-reports-empty">No attempts yet.</p> : d.reports.map((r) => (
        <div key={`${r.user?.email}-${r.mock_id}-${r.preview}`} className="border-2 border-ink p-3 text-xs" data-testid={`acc-report-${r.mock_id}-${r.user?.email}`}>
          <p className="text-sm"><b>{r.user?.email || "unknown"}</b> · {r.mock_id}{r.preview ? " · preview" : ""}</p>
          <table className="mt-1 w-full"><tbody>{r.order.map((k) => {
            const x = r.rounds[k];
            return (
              <tr key={k} className="border-t border-ink/10 align-top">
                <td className="py-1 pr-2 font-bold">{NAMES[k]}</td>
                <td className="py-1 pr-2">{!x ? "not started" : !x.finished_at ? "in progress" : k === "behavioural" ? `profile ${x.result?.profile_index ?? "–"} · ${x.review_status}` : `${x.result?.percent ?? "–"}% (${x.result?.passed ? "meets" : "below"} cutoff)`}
                  {x?.tasks && <ul>{x.tasks.map((t) => <li key={t.qid}>{t.type}: best {t.best_score ?? "–"}% · {t.submissions.map((s) => `${s.lang || "-"} ${s.passed}/${s.total} (${s.score}%)`).join(", ") || "no submissions"}</li>)}</ul>}</td>
                <td className="py-1"><Proc p={x?.proctoring} /></td>
              </tr>
            );
          })}</tbody></table>
        </div>
      ))}</div>
    </Card>
  );
}
