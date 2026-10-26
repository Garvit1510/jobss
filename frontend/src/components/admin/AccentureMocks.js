import React, { useCallback, useEffect, useState } from "react";
import { Eye, Lock, RefreshCw, Rocket, Sparkles, Trash2, Unlock } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";
import { Badge, Button, Card, EmptyState, Modal, Progress, Spinner } from "../ui";
import BehaviouralReview from "./BehaviouralReview";
import ReleaseReadiness from "./ReleaseReadiness";
import MockPublication from "./MockPublication";
import AccentureOAReports from "./AccentureOAReports";

const TONE = { pending: "white", generating: "yellow", valid: "green", invalid: "red", failed: "red", ready: "green", incomplete: "red", published: "blue", archived: "white" };

function McqReview({ q, docId, onSaved }) {
  const [key, setKey] = useState(q.answer_index);
  const [exp, setExp] = useState(q.explanation || "");
  const [busy, setBusy] = useState(false);
  useEffect(() => { setKey(q.answer_index); setExp(q.explanation || ""); }, [q]);
  const send = async (path, body, ok) => { setBusy(true); try { await api.post(`/admin/accenture-mocks/mocks/${docId}/questions/${q.qid}/${path}`, body); toast.success(ok); onSaved(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); } };
  const cc = q.cross_check;
  const tone = q.review_issue ? "red" : q.review?.status === "approved" || q.key_status === "source_key" ? "green" : "yellow";
  return (
    <div className={`mt-2 border-2 p-2 ${q.review_issue ? "border-brand-red" : "border-ink"}`} data-testid={`acc-review-q-${q.qid}`}>
      <div className="flex flex-wrap gap-1">
        <span className="font-mono text-xs font-bold">{q.qid}</span>
        <Badge tone={q.origin === "source" ? "blue" : "purple"}>{q.origin}{q.source_ref ? ` · ${q.source_ref}` : ""}</Badge>
        <Badge tone="dark">{q.category}{q.oop_language ? ` · ${q.oop_language}` : ""}</Badge>
        <Badge tone={tone} data-testid={`acc-review-label-${q.qid}`}>{q.review_label}</Badge>
      </div>
      <p className="mt-1 whitespace-pre-wrap">{q.question}</p>
      <ol className="list-[upper-alpha] pl-5">{q.options.map((o, i) => (
        <li key={i} onClick={() => setKey(i)} className={`cursor-pointer ${i === key ? "font-bold text-brand-green" : ""} ${cc && cc.answer_index === i && i !== q.answer_index ? "underline decoration-brand-red" : ""}`}>{o}{i === q.answer_index ? " ✓ key" : ""}{cc && cc.answer_index === i ? " · cross-check" : ""}</li>))}</ol>
      {cc && <p className="text-xs text-ink/60">Independent re-solve: <b>{cc.status}</b>{cc.confidence ? ` (${cc.confidence})` : ""}{cc.note ? ` — ${cc.note}` : ""}</p>}
      {q.review_issue && <p className="text-xs font-bold text-brand-red">Blocks publication: {q.review_issue}</p>}
      <textarea value={exp} onChange={(e) => setExp(e.target.value)} rows={2} className="brutal-input mt-1 w-full py-1 text-xs" data-testid={`acc-review-exp-${q.qid}`} />
      <div className="mt-1 flex flex-wrap gap-1">
        <Button variant="green" className="px-2 py-1 text-xs" disabled={busy} onClick={() => send("review", { action: "approve", answer_index: key, explanation: exp }, "Approved")} data-testid={`acc-review-approve-${q.qid}`}>Approve{key !== q.answer_index ? " with new key" : ""}</Button>
        <Button className="px-2 py-1 text-xs" disabled={busy} onClick={() => send("review", { action: "reject" }, "Rejected")} data-testid={`acc-review-reject-${q.qid}`}>Reject</Button>
        <Button className="px-2 py-1 text-xs" disabled={busy} onClick={() => send("replace", {}, "Replaced")} data-testid={`acc-review-replace-${q.qid}`}>Replace (Gemini)</Button>
        {q.review?.status && q.review.status !== "pending" && <Button className="px-2 py-1 text-xs" disabled={busy} onClick={() => send("review", { action: "reset" }, "Reset")}>Reset</Button>}
      </div>
    </div>
  );
}

function MockReview({ id, onClose }) {
  const [m, setM] = useState(null);
  const [only, setOnly] = useState(false);
  const reload = useCallback(() => api.get(`/admin/accenture-mocks/mocks/${id}`).then((r) => setM(r.data)).catch((e) => toast.error(errMsg(e))), [id]);
  useEffect(() => { if (id) reload(); else setM(null); }, [id, reload]);
  const r = m?.rounds || {};
  return (
    <Modal open={!!id} onClose={onClose} title={m ? `${m.mock_id} · review` : "Loading"} testid="acc-mock-review">
      {!m ? <Spinner /> : (
        <div className="max-h-[70vh] space-y-5 overflow-y-auto text-sm">
          {[...(m.validation?.errors || []).map((e) => ["red", e]), ...(m.validation?.warnings || []).map((w) => ["yellow", w])].map(([t, x], i) => <Badge key={i} tone={t} className="mr-1">{x}</Badge>)}
          {m.error && <p className="text-brand-red">{m.error}</p>}
          <section><h4 className="font-bold">Behavioural ({r.behavioural?.items?.length || 0}) · subjective, trait-profile scoring (no right/wrong key)</h4>
            <p className="text-xs text-ink/60">Scale: {r.behavioural?.items?.[0]?.options?.join(" · ")}</p>
            <ol className="list-decimal pl-5">{r.behavioural?.items?.map((b) => <li key={b.qid}>{b.statement} <span className="font-mono text-xs text-ink/50">[{b.origin} · {b.trait}{b.reverse_scored ? ", reverse" : ""}]</span></li>)}</ol></section>
          <section><h4 className="font-bold">Gamified ({r.gamified?.activities?.length || 0} activities · mechanics from recording in the gamified phase)</h4>
            <ol className="list-decimal pl-5">{r.gamified?.activities?.map((g) => <li key={g.activity_id}>{g.title}{g.grid ? ` ${g.grid} · ${g.minutes} min` : ` · ${g.questions} questions × ${g.seconds_per_question}s · ${g.rule}`}</li>)}</ol></section>
          <section><h4 className="flex items-center gap-3 font-bold">Technical MCQs ({r.technical?.questions?.length || 0}) · {m.validation?.stats?.review_blocking || 0} blocking
              <label className="text-xs font-normal"><input type="checkbox" checked={only} onChange={(e) => setOnly(e.target.checked)} data-testid="acc-review-only-blocking" /> show blocking only</label></h4>
            {r.technical?.questions?.filter((q) => !only || q.review_issue).map((q) => <McqReview key={q.qid} q={q} docId={m.id} onSaved={reload} />)}</section>
          <section><h4 className="font-bold">Coding ({r.coding?.problems?.length || 0})</h4>
            {r.coding?.problems?.map((p) => (
              <div key={p.qid} className="mt-2 border-2 border-ink p-2">
                <Badge tone={p.origin === "source" ? "blue" : "purple"}>{p.origin}</Badge> <Badge tone="dark">{p.type} · {p.minutes} min</Badge> <b>{p.title}</b> <span className="text-xs">({p.difficulty} · {(p.hidden_tests || p.tests)?.length} tests · expected outputs computed by running the reference solution)</span>
                <p className="mt-1 whitespace-pre-wrap">{p.problem}</p>
              </div>))}</section>
        </div>)}
    </Modal>
  );
}

function MockRow({ m, onToggle, onView, onReload }) {
  const v = m.validation?.stats;
  return (
    <tr className="border-t-2 border-ink/10" data-testid={`acc-mock-row-${m.mock_id}`}>
      <td className="p-2 font-mono font-bold">{m.mock_id}</td>
      <td className="p-2"><Badge tone={TONE[m.status]}>{m.status}</Badge></td>
      <td className="p-2 text-xs">{v ? `MCQ ${v.technical_source} src / ${v.technical_generated} gen (${Math.round(v.technical_source_ratio * 100)}% source) · ${v.ai_derived_keys} AI keys` : "–"}</td>
      <td className="p-2 text-xs text-brand-red">{m.validation?.unfinished_rounds?.length ? `Unfinished: ${m.validation.unfinished_rounds.join(", ")} · ` : ""}{(m.validation?.errors || []).length || m.error ? `${(m.validation?.errors || []).length || 1} error(s)` : ""}{(m.validation?.warnings || []).length ? <span className="text-ink/60"> · {(m.validation?.warnings || []).length} warning(s)</span> : null}
        {v && <span className={v.review_blocking ? "font-bold text-brand-red" : "text-brand-green"}> · {v.review_blocking ? `${v.review_blocking} blocking review` : "review clear"}</span>}</td>
      <td className="p-2">{m.status === "valid" && <a href={`/accenture-mocks/${m.mock_id}/behavioural?preview=1`} target="_blank" rel="noreferrer" className="mr-1 text-xs underline" data-testid={`acc-mock-preview-behavioural-${m.mock_id}`}>R1</a>}
        {m.status === "valid" && <a href={`/accenture-mocks/${m.mock_id}/gamified?preview=1`} target="_blank" rel="noreferrer" className="mr-1 text-xs underline" data-testid={`acc-mock-preview-gamified-${m.mock_id}`}>R2</a>}
        {m.status === "valid" && <a href={`/accenture-mocks/${m.mock_id}/technical?preview=1`} target="_blank" rel="noreferrer" className="mr-1 text-xs underline" data-testid={`acc-mock-preview-technical-${m.mock_id}`}>R3</a>}
        {m.status === "valid" && <a href={`/accenture-mocks/${m.mock_id}/coding?preview=1`} target="_blank" rel="noreferrer" className="mr-1 text-xs underline" data-testid={`acc-mock-preview-coding-${m.mock_id}`}>R4</a>}<button onClick={() => onView(m.id)} className="brutal-btn bg-white px-2 py-1" data-testid={`acc-mock-view-${m.mock_id}`}><Eye size={14} /></button></td>
      <td className="p-2"><button onClick={() => onToggle([m.mock_id], !m.unlocked)} className={`brutal-btn px-2 py-1 ${m.unlocked ? "bg-brand-green" : "bg-white"}`} data-testid={`acc-mock-lock-${m.mock_id}`}>
        {m.unlocked ? <><Unlock size={14} /> Unlocked</> : <><Lock size={14} /> Locked</>}</button>
        <p className={`mt-1 max-w-[220px] text-[11px] font-semibold ${m.candidate_visible ? "text-green-700" : "text-brand-red"}`} data-testid={`acc-mock-visibility-${m.mock_id}`}>
          {m.candidate_visible ? "Visible to candidates" : `Hidden from candidates: ${m.visibility_reason}`}</p></td>
      <td className="p-2 align-top"><MockPublication m={m} onDone={onReload} /></td>
    </tr>
  );
}

function RoundScoring() {
  const [c, setC] = useState(null);
  useEffect(() => { api.get("/admin/accenture-mocks/round-scoring").then((r) => setC(r.data)).catch(() => {}); }, []);
  if (!c) return null;
  const f = (sec, k, tid) => <label className="text-xs">{k} <input type="number" value={c[sec][k]} onChange={(e) => setC({ ...c, [sec]: { ...c[sec], [k]: +e.target.value } })} className="brutal-input ml-1 w-16 py-0.5 text-xs" data-testid={tid} /></label>;
  const save = async (sec, keys) => {
    try { const { data } = await api.put(`/admin/accenture-mocks/round-scoring/${sec}`, Object.fromEntries(keys.map((k) => [k, c[sec][k]]))); setC({ ...c, [sec]: data }); toast.success("Saved (applies to new attempts)"); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Card className="p-5" data-testid="acc-round-scoring">
      <h3 className="text-lg font-bold">Round 3 & 4 scoring (practice model)</h3>
      <div className="mt-2 flex flex-wrap items-center gap-3">{["correct", "wrong", "unanswered", "cutoff_percent"].map((k) => <span key={k}>{f("technical", k, `acc-tech-${k}`)}</span>)}<Button className="px-2 py-1 text-xs" onClick={() => save("technical", ["correct", "wrong", "unanswered", "cutoff_percent"])} data-testid="acc-tech-save">Save R3</Button></div>
      <p className="text-xs text-ink/60">{c.technical.note}</p>
      <div className="mt-3 flex flex-wrap items-center gap-3">{["visible_weight", "hidden_weight", "cutoff_percent", "max_submissions"].map((k) => <span key={k}>{f("coding", k, `acc-code-${k}`)}</span>)}<Button className="px-2 py-1 text-xs" onClick={() => save("coding", ["visible_weight", "hidden_weight", "cutoff_percent", "max_submissions"])} data-testid="acc-code-save">Save R4</Button></div>
      <p className="text-xs text-ink/60">{c.coding.note}</p>
    </Card>
  );
}

function GamesConfig() {
  const [c, setC] = useState(null);
  const load = () => api.get("/admin/accenture-mocks/games-config").then((r) => setC(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);
  if (!c) return null;
  const sc = c.scoring;
  const opts = Object.fromEntries(Object.entries(c.engines).map(([k, e]) => [k, e.options]));
  const setOpt = (eng, k, v) => setC({ ...c, engines: { ...c.engines, [eng]: { ...c.engines[eng], options: { ...c.engines[eng].options, [k]: v } } } });
  const setSc = (patch) => setC({ ...c, scoring: { ...sc, ...patch } });
  const save = async () => {
    try {
      await api.put("/admin/accenture-mocks/games-config/options", opts);
      await api.put("/admin/accenture-mocks/games-config/scoring", { cutoff_percent: sc.cutoff_percent, weights: sc.weights, memory_maze: sc.memory_maze, path_finder: sc.path_finder });
      toast.success("Round 2 settings saved (apply to new attempts)"); load();
    } catch (e) { toast.error(errMsg(e)); }
  };
  const num = (v, on, tid) => <input type="number" value={v} onChange={(e) => on(+e.target.value)} className="brutal-input ml-1 w-16 py-0.5 text-xs" data-testid={tid} />;
  return (
    <Card className="p-5" data-testid="acc-games-config">
      <h3 className="text-lg font-bold">Round 2 game engine · {c.version}</h3>
      <ol className="mt-2 list-decimal pl-5 text-sm">{c.activities.map((a) => (
        <li key={a.activity_id}>{a.title}{a.grid ? ` ${a.grid} · ${a.minutes} min` : ` · ${a.questions} × ${a.seconds_per_question}s`} · weight {num(sc.weights[a.activity_id] ?? 1, (v) => setSc({ weights: { ...sc.weights, [a.activity_id]: v } }), `acc-weight-${a.activity_id}`)}</li>))}</ol>
      <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
        <label><input type="checkbox" checked={!!opts.memory_maze.reset_key_on_wrong} onChange={(e) => setOpt("memory_maze", "reset_key_on_wrong", e.target.checked)} data-testid="acc-opt-reset-key" /> Memory Maze: wrong move also drops the key</label>
        <label>Memory Maze: mazes per section {num(opts.memory_maze.mazes_per_section, (v) => setOpt("memory_maze", "mazes_per_section", Math.max(1, v)), "acc-opt-mazes")}</label>
        <label><input type="checkbox" checked={!!opts.bubble_math.show_incorrect_feedback} onChange={(e) => setOpt("bubble_math", "show_incorrect_feedback", e.target.checked)} data-testid="acc-opt-bubble-feedback" /> Bubble Math: show feedback for a wrong order</label>
        <label>Bubble Math difficulty <select value={opts.bubble_math.difficulty} onChange={(e) => setOpt("bubble_math", "difficulty", e.target.value)} className="brutal-input py-0.5 text-xs" data-testid="acc-opt-bubble-difficulty"><option value="flat">flat</option><option value="progressive">progressive</option></select></label>
        <label>Path Finder rotate step <select value={opts.path_finder.rotate_step_deg} onChange={(e) => setOpt("path_finder", "rotate_step_deg", +e.target.value)} className="brutal-input py-0.5 text-xs" data-testid="acc-opt-rotate-step"><option value={45}>45°</option><option value={90}>90°</option></select></label>
        <label>Cutoff % {num(sc.cutoff_percent, (v) => setSc({ cutoff_percent: v }), "acc-cutoff")}</label>
        <label>Maze penalty / extra attempt {num(sc.memory_maze.penalty_per_extra_attempt, (v) => setSc({ memory_maze: { ...sc.memory_maze, penalty_per_extra_attempt: v } }), "acc-maze-penalty")}</label>
        <label>Path Finder solve / efficiency points {num(sc.path_finder.solve_points, (v) => setSc({ path_finder: { ...sc.path_finder, solve_points: v } }), "acc-pf-solve")}{num(sc.path_finder.efficiency_points, (v) => setSc({ path_finder: { ...sc.path_finder, efficiency_points: v } }), "acc-pf-eff")}</label>
      </div>
      {Object.entries(c.engines).map(([k, e]) => <p key={k} className="mt-2 text-xs"><b>{k} — needs reference confirmation:</b> {e.unconfirmed.join("; ")}</p>)}
      <p className="mt-2 text-xs text-ink/60">{sc.note}</p>
      <Button variant="dark" className="mt-3" onClick={save} data-testid="acc-games-save">Save Round 2 settings</Button>
    </Card>
  );
}

function BehaviouralScoring() {
  const [c, setC] = useState(null);
  useEffect(() => { api.get("/admin/accenture-mocks/settings/behavioural-scoring").then((r) => setC(r.data)).catch((e) => toast.error(errMsg(e))); }, []);
  if (!c) return null;
  const set = (k, v) => setC({ ...c, [k]: v });
  const save = () => api.put("/admin/accenture-mocks/settings/behavioural-scoring", c).then((r) => { setC(r.data); toast.success("Behavioural scoring saved"); }).catch((e) => toast.error(errMsg(e)));
  const chk = (k, l) => <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!c[k]} onChange={(e) => set(k, e.target.checked)} data-testid={`acc-beh-${k}`} /> {l}</label>;
  return (
    <Card className="p-5" data-testid="acc-beh-scoring">
      <h3 className="text-lg font-bold">Round 1 scoring (behavioural, subjective)</h3>
      <p className="text-xs text-ink/60">5-point agreement scale mapped to 1–5 and aggregated per trait. No right/wrong marking; separate from objective MCQ scoring.</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <label className="text-sm">Aggregation <select value={c.aggregation} onChange={(e) => set("aggregation", e.target.value)} className="brutal-input ml-2 py-1" data-testid="acc-beh-aggregation"><option value="mean">Mean per trait</option><option value="sum">Sum per trait</option></select></label>
        <label className="text-sm">Low band below <input type="number" step="0.05" min={1} max={5} value={c.bands.low_below} onChange={(e) => set("bands", { ...c.bands, low_below: +e.target.value })} className="brutal-input ml-2 w-20 py-1" data-testid="acc-beh-low" /></label>
        <label className="text-sm">High band from <input type="number" step="0.05" min={1} max={5} value={c.bands.high_from} onChange={(e) => set("bands", { ...c.bands, high_from: +e.target.value })} className="brutal-input ml-2 w-20 py-1" data-testid="acc-beh-high" /></label>
        {chk("reverse_scoring", "Reverse-score negatively worded items (6 − value)")}
        {chk("consistency_check", "Flag inconsistent response patterns")}
        {chk("show_trait_profile_to_candidate", "Show trait profile to candidate")}
      </div>
      <p className="mt-4 text-sm font-bold">Review thresholds (a profile that trips any of these is flagged for admin review, never auto-passed or failed)</p>
      <div className="mt-2 grid gap-2 text-xs sm:grid-cols-2 lg:grid-cols-3">
        {[["min_completion", "Min share answered (0–1)", 0.05], ["straight_line_share", "Same-option share flagged from (0–1)", 0.05], ["neutral_share", "Neutral share flagged from (0–1)", 0.05],
          ["reverse_gap", "Forward vs reverse gap flagged from (points)", 0.25], ["extreme_min_mean", "All traits at/above (uniformly extreme)", 0.05], ["min_items_per_trait", "Min answers per trait", 1]].map(([k, l, step]) => (
          <label key={k}>{l} <input type="number" step={step} value={c.review_thresholds[k]} onChange={(e) => set("review_thresholds", { ...c.review_thresholds, [k]: +e.target.value })} className="brutal-input ml-1 w-20 py-0.5 text-xs" data-testid={`acc-beh-th-${k}`} /></label>))}
      </div>
      <p className="mt-2 text-xs text-ink/60">Round 1 is never added to any numeric score. Settings apply to new attempts.</p>
      <Button variant="dark" className="mt-3" onClick={save} data-testid="acc-beh-save">Save scoring</Button>
    </Card>
  );
}

export default function AccentureMocks() {
  const [d, setD] = useState(null);
  const [libId, setLibId] = useState("");
  const [view, setView] = useState(null);
  const [reuse, setReuse] = useState(1);
  const [only, setOnly] = useState("M1");
  const ids = () => (only.trim() ? only.split(/[\s,]+/).filter(Boolean).map((x) => x.toUpperCase()) : null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => api.get("/admin/accenture-mocks", { params: { library_id: libId } }).then((r) => setD(r.data)).catch((e) => toast.error(errMsg(e))), [libId]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (!d?.running) return; const t = setInterval(load, 5000); return () => clearInterval(t); }, [d?.running, load]);
  const act = async (fn, ok) => { setBusy(true); try { await fn(); ok && toast.success(ok); setLibId((x) => x); await load(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); } };
  const toggle = (ids, unlocked) => act(() => api.post("/admin/accenture-mocks/access", { mock_ids: ids, unlocked }));
  if (!d) return <Spinner />;
  const lib = d.library;
  const valid = lib?.counts?.valid || 0;
  const mocks = d.mocks.length ? d.mocks : d.access.map((a) => ({ ...a, id: null, status: "pending" }));
  return (
    <div className="space-y-6" data-testid="acc-mocks-admin">
      <Card className="p-5">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h3 className="text-xl font-bold">Accenture Mock OA library (M1–M40)</h3>
            <p className="text-xs text-ink/70">Structure per mock: Behavioural 50 Q · 20m | Gamified 6 activities · ~30m | Technical 45 MCQs (8 categories) · 45m | Coding DSA + SQL + JS Frontend · 60m</p>
            <p className="text-sm text-ink/60">Published: {d.published ? `v${d.published.version}` : "none"} · Uses the imported Accenture dataset (Company OAs) as source. Gemini is only called here, never when a candidate opens a mock.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-xs font-bold">Max uses per source Q
              <input type="number" min={1} max={5} value={reuse} onChange={(e) => setReuse(+e.target.value)} className="brutal-input ml-2 w-16 py-1" data-testid="acc-reuse-input" /></label>
            <Button variant="primary" disabled={busy || !!d.running} onClick={() => act(() => api.post("/admin/accenture-mocks/generate", { max_source_reuse: reuse, mock_ids: ids() }).then((r) => setLibId(r.data.library_id)), "Generation started")} data-testid="acc-generate-btn">
              <Sparkles size={16} /> Generate / Regenerate Accenture Mock Library</Button>
            <label className="text-xs font-bold">Only mocks
              <input value={only} onChange={(e) => setOnly(e.target.value)} placeholder="blank = all 40" className="brutal-input ml-2 w-32 py-1" data-testid="acc-only-input" /></label>
            {d.running && <Button disabled={busy} onClick={() => act(() => api.post("/admin/accenture-mocks/stop"), "Generation stopped")} data-testid="acc-stop-btn">Stop</Button>}
          </div>
        </div>
        {d.libraries.length > 0 && (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <select value={lib?.id || ""} onChange={(e) => setLibId(e.target.value)} className="brutal-input py-1" data-testid="acc-library-select">
              {d.libraries.map((l) => <option key={l.id} value={l.id}>v{l.version} · {l.status} · {new Date(l.created_at).toLocaleString()}</option>)}
            </select>
            {lib && <Badge tone={TONE[lib.status]} data-testid="acc-library-status">{lib.status}</Badge>}
            {lib && <span className="text-sm" data-testid="acc-library-progress">{valid}/40 valid · {lib.stage} · <b className={lib.review_blocking ? "text-brand-red" : ""}>{lib.review_blocking || 0} blocking review</b> · {lib.awaiting_admin_review || 0} AI keys awaiting admin review</span>}
            {lib && !["published", "archived", "generating"].includes(lib.status) && <>
              <Button disabled={busy || !!d.running} onClick={() => act(() => api.post(`/admin/accenture-mocks/libraries/${lib.id}/retry`, { mock_ids: ids() }), "Retrying failed mocks")} data-testid="acc-retry-btn"><RefreshCw size={14} /> Retry failed</Button>
              <Button variant="green" disabled={busy || lib.status !== "ready" || lib.review_blocking > 0} title={lib.review_blocking ? "Resolve all blocking review items first" : ""} onClick={() => act(() => api.post(`/admin/accenture-mocks/libraries/${lib.id}/publish`), "Published")} data-testid="acc-publish-btn"><Rocket size={14} /> Publish</Button>
              <Button disabled={busy} onClick={() => window.confirm("Delete this draft version?") && act(() => api.delete(`/admin/accenture-mocks/libraries/${lib.id}`).then(() => setLibId("")), "Draft deleted")} data-testid="acc-delete-btn"><Trash2 size={14} /></Button>
            </>}
          </div>)}
        {lib && <div className="mt-3"><Progress value={((Object.entries(lib.counts || {}).filter(([k]) => !["pending", "generating"].includes(k)).reduce((a, [, n]) => a + n, 0)) / 40) * 100} /></div>}
        {lib?.last_run && <p className="mt-2 text-xs" data-testid="acc-last-run">Last run: {lib.last_run.mock_ids?.join(", ")} · {lib.last_run.api_attempts} Gemini request attempts{lib.last_run.aborted ? " · STOPPED (Gemini unavailable/quota)" : ""}</p>}
        {lib?.source_pool && <p className="mt-2 text-xs text-ink/60" data-testid="acc-source-pool">Source pool: {lib.source_pool.mcq_usable} usable MCQs ({lib.source_pool.ai_solved_keys} with AI-solved keys, flagged for review) · {lib.source_pool.behavioural_usable} behavioural · {lib.source_pool.coding_usable} DSA coding. Flagged/dropped: {lib.source_pool.flagged?.length ?? "–"}.</p>}
        {lib?.source_pool?.flagged?.length > 0 && <details className="mt-2 text-xs" data-testid="acc-flagged-sources"><summary className="cursor-pointer font-bold">Flagged source questions excluded from mocks ({lib.source_pool.flagged.length})</summary>
          <ul className="list-disc pl-5">{lib.source_pool.flagged.map((f, i) => <li key={i}><span className="font-mono">{f.source_ref}</span> — {f.reason}{f.question ? `: ${f.question}` : ""}</li>)}</ul></details>}
        {lib?.errors?.length > 0 && <ul className="mt-2 list-disc pl-5 text-xs text-brand-red" data-testid="acc-library-errors">{lib.errors.map((e, i) => <li key={i}>{e}</li>)}</ul>}
      </Card>
      <Card className="p-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm">{!d.published && <span className="mb-1 block font-bold text-brand-red" data-testid="acc-no-published-library">No library is published. Candidates only see mocks that are individually published (or in a published library) AND unlocked. Unlocking does not publish.</span>}Candidates only see mocks that are <b>published (individually or via library) + valid + reviewed + unlocked</b>. Locks apply to the mock ID across versions.</p>
          <div className="flex gap-2">
            <Button disabled={busy} onClick={() => toggle(d.access.map((a) => a.mock_id), true)} data-testid="acc-unlock-all"><Unlock size={14} /> Unlock all</Button>
            <Button disabled={busy} onClick={() => toggle(d.access.map((a) => a.mock_id), false)} data-testid="acc-lock-all"><Lock size={14} /> Lock all</Button>
          </div>
        </div>
        {!mocks.length ? <EmptyState title="No library yet" /> : (
          <div className="overflow-x-auto"><table className="w-full text-left text-sm">
            <thead><tr className="font-display"><th className="p-2">Mock</th><th className="p-2">Status</th><th className="p-2">Provenance</th><th className="p-2">Validation</th><th className="p-2">Review</th><th className="p-2">Access</th><th className="p-2">Publication</th></tr></thead>
            <tbody>{mocks.map((m) => <MockRow key={m.mock_id} m={m} onToggle={toggle} onView={(id) => id && setView(id)} onReload={load} />)}</tbody>
          </table></div>)}
      </Card>
      <BehaviouralScoring />
      <BehaviouralReview />
      <AccentureOAReports />
      <ReleaseReadiness />
      <GamesConfig />
      <RoundScoring />
      <MockReview id={view} onClose={() => { setView(null); load(); }} />
    </div>
  );
}
