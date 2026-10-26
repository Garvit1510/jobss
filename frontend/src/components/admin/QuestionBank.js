import React, { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, CheckSquare, ChevronDown, Database, FileSearch, Pencil, ShieldCheck, Sparkles, Square, Trash2, XCircle } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";
import { Badge, Button, Spinner } from "../ui";
import { KINDS } from "./BlueprintEditor";

const titleOf = (q) => q.data.title || q.data.question || "Untitled";
const ORIGIN = (q) => (q.is_original ? ["Original", "green"] : q.variant_type === "variant" ? ["Variant", "yellow"] : ["Related", "blue"]);
const STATUS_TONE = { ready: "text-brand-green", needs_review: "text-brand-yellow", incomplete: "text-ink/50", rejected: "text-brand-red" };

function Preview({ q }) {
  const d = q.data;
  return (
    <div className="space-y-2 text-sm">
      <p className="font-mono text-[11px] text-ink/60">
        {q.source_ref && <>Ref {q.source_ref} · </>}{q.source_page && <>page {q.source_page} · </>}{q.question_type || q.kind}
        {q.harness && <> · judge harness {q.harness}</>}{q.answer_verified && <> · answer verified</>}{q.parent_question_id && <> · derived from a dataset question</>}
      </p>
      {(q.review_notes || []).length > 0 && <ul className="list-disc pl-5 text-xs text-brand-red">{q.review_notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
      {q.source_notes && <p className="text-xs text-ink/60"><b>Dataset note:</b> {q.source_notes}</p>}
      {d.question && <p className="whitespace-pre-line">{d.question}</p>}
      {d.options && <ol className="list-[upper-alpha] pl-5">{d.options.map((o, i) => <li key={i} className={i === d.answer_index ? "font-bold text-brand-green" : ""}>{o}</li>)}</ol>}
      {d.type === "numeric" && <p className="font-mono">Answer: {d.answer ?? "—"} {d.unit}</p>}
      {d.problem && <p className="whitespace-pre-line">{d.problem}</p>}
      {(d.examples || []).map((e, i) => <pre key={i} className="bg-offwhite p-2 font-mono text-xs whitespace-pre-wrap">Input: {e.input}{"\n"}Output: {e.output}</pre>)}
      {q.kind === "sql" && d.schema && <pre className="max-h-40 overflow-auto bg-offwhite p-2 font-mono text-xs whitespace-pre-wrap">{d.schema}{d.reference ? `\n\n-- reference\n${d.reference}` : ""}</pre>}
      {d.tests && <p className="font-mono text-xs text-ink/60">{d.tests.length} test cases{d.tests[0]?.name ? `: ${d.tests.map((t) => t.name).join(" · ")}` : ""}</p>}
      {d.starter_code && <p className="font-mono text-xs text-ink/60">Starter code: {Object.keys(d.starter_code).join(", ") || "generic templates"}</p>}
    </div>
  );
}

function EditBox({ q, onSave, onClose }) {
  const [txt, setTxt] = useState(JSON.stringify(q.data, null, 2));
  const save = () => {
    try { onSave(JSON.parse(txt)); } catch { toast.error("Invalid JSON"); }
  };
  return (
    <div className="space-y-2" data-testid={`bank-q-edit-${q.id}`}>
      <p className="font-mono text-[11px] text-ink/60">Edit the question record (e.g. set "answer_index" for MCQs). Test cases are kept if you remove them here.</p>
      <textarea className="brutal-input h-64 w-full font-mono text-xs" value={txt} onChange={(e) => setTxt(e.target.value)} data-testid={`bank-q-edit-text-${q.id}`} />
      <div className="flex gap-2"><Button className="h-8 py-0 px-3 text-xs" variant="primary" onClick={save} data-testid={`bank-q-edit-save-${q.id}`}>Save</Button><Button className="h-8 py-0 px-3 text-xs" onClick={onClose}>Cancel</Button></div>
    </div>
  );
}

function BankItem({ q, act }) {
  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState(false);
  const [label, tone] = ORIGIN(q);
  const patch = (body) => act(() => api.patch(`/admin/oa-bank/${q.id}`, body));
  return (
    <li className={`border-2 border-ink ${q.selected ? "bg-brand-green/15" : "bg-white"}`} data-testid={`bank-q-${q.id}`}>
      <div className="flex items-center gap-2 px-3 py-2">
        <button onClick={() => patch({ selected: !q.selected })} aria-label="Hand-pick question" data-testid={`bank-q-select-${q.id}`}>{q.selected ? <CheckSquare size={18} /> : <Square size={18} />}</button>
        <Badge tone={tone}>{label}</Badge>
        <span className={`font-mono text-[10px] font-bold uppercase ${STATUS_TONE[q.status || "ready"]}`} data-testid={`bank-q-status-${q.id}`}>{(q.status || "ready").replace("_", " ")}</span>
        <button onClick={() => setOpen(!open)} className="min-w-0 flex-1 truncate text-left text-sm">{q.source_ref ? <b className="mr-1 font-mono text-xs">{q.source_ref}</b> : null}{titleOf(q)}</button>
        {q.kind && <span className="hidden font-mono text-[10px] text-ink/50 md:inline">{q.kind}</span>}
        <ChevronDown size={14} className={`shrink-0 cursor-pointer transition-transform ${open ? "rotate-180" : ""}`} onClick={() => setOpen(!open)} />
        <button onClick={() => window.confirm("Delete this question from the bank?") && act(() => api.delete(`/admin/oa-bank/${q.id}`))} className="text-brand-red" aria-label="Delete question" data-testid={`bank-q-delete-${q.id}`}><Trash2 size={14} /></button>
      </div>
      {open && <div className="space-y-3 border-t-2 border-ink/10 px-3 py-2">
        {edit ? <EditBox q={q} onClose={() => setEdit(false)} onSave={(data) => { patch({ data }); setEdit(false); }} /> : <Preview q={q} />}
        {!edit && <div className="flex flex-wrap gap-2">
          {q.is_original && q.status !== "ready" && q.status !== "rejected" && <Button className="h-8 py-0 px-3 text-xs" variant="green" onClick={() => patch({ answer_verified: true })} data-testid={`bank-q-verify-${q.id}`}><ShieldCheck size={13} /> Mark verified</Button>}
          {q.is_original && ["coding", "sql", "web"].includes(q.kind) && q.status === "needs_review" && <Button className="h-8 py-0 px-3 text-xs" onClick={() => { toast.info("Building judge test cases… this can take a minute"); act(() => api.post(`/admin/oa-bank/${q.id}/enrich`, {}, { timeout: 300000 })); }} data-testid={`bank-q-enrich-${q.id}`}><Sparkles size={13} /> Rebuild test cases</Button>}
          <Button className="h-8 py-0 px-3 text-xs" onClick={() => setEdit(true)} data-testid={`bank-q-edit-btn-${q.id}`}><Pencil size={13} /> Edit</Button>
          {q.status === "rejected" ? <Button className="h-8 py-0 px-3 text-xs" onClick={() => patch({ rejected: false })} data-testid={`bank-q-restore-${q.id}`}>Restore</Button>
            : <Button className="h-8 py-0 px-3 text-xs" onClick={() => patch({ rejected: true })} data-testid={`bank-q-reject-${q.id}`}><XCircle size={13} /> Reject</Button>}
        </div>}
      </div>}
    </li>
  );
}

function Stat({ label, v, warn, testid }) {
  return <span className={`border-2 border-ink px-2 py-0.5 font-mono text-[11px] ${warn ? "bg-brand-red/15" : "bg-white"}`} data-testid={testid}>{label}: <b>{v}</b></span>;
}

function SectionBank({ company, s, items, stats, job, reload }) {
  const prog = ["coding", "sql", "web"].includes(s.kind);
  const [mode, setMode] = useState("related");
  const [kind, setKind] = useState(s.kind);
  const [n, setN] = useState(Math.max(1, Math.min(30, stats?.need_related || 5)));
  const act = (fn) => fn().then(reload).catch((e) => toast.error(errMsg(e)));
  const gen = () => act(async () => {
    await api.post(`/admin/oa-companies/${company.id}/bank/generate`, { section_id: s.id, count: n, mode, kind });
    toast.success(`Gemini is writing ${n} ${mode} ${s.name} questions from the dataset…`);
  });
  const st = stats || {};
  return (
    <div className="border-3 border-ink bg-offwhite p-4" data-testid={`bank-section-${s.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-display font-bold">{s.name} <span className="font-mono text-xs font-normal text-ink/60">· {KINDS[s.kind]} · {s.count} per test · {s.minutes} min</span></p>
          <div className="mt-2 flex flex-wrap gap-1.5" data-testid={`bank-section-stats-${s.id}`}>
            <Stat label="Target" v={`${st.target_original} original + ${st.target_related} related`} />
            <Stat label="Originals ready" v={st.original_ready} warn={st.original_ready < st.target_original} testid={`bank-stat-orig-${s.id}`} />
            <Stat label="Needs review" v={st.original_review} />
            <Stat label="Incomplete" v={st.original_incomplete} />
            <Stat label="Variants" v={st.variant_ready} />
            <Stat label="Related" v={st.related_ready} warn={st.related_ready < st.target_related} testid={`bank-stat-rel-${s.id}`} />
          </div>
          <p className={`mt-2 flex items-center gap-1.5 font-mono text-[11px] ${st.can_start ? (st.ratio_met ? "text-brand-green" : "text-brand-yellow") : "text-brand-red"}`} data-testid={`bank-section-ready-${s.id}`}>
            {st.can_start ? <CheckCircle2 size={13} /> : <AlertTriangle size={13} />}
            {!st.can_start ? `Not enough ready questions: ${st.available}/${s.count}. Tests will refuse to start until this is filled.`
              : st.ratio_met ? "Ready · 65/35 mix met" : `Can start, but the 65/35 mix is not met (shortfall is reported in each test).`}
            {(st.need_related > 0 || st.need_variants > 0) && <> · suggested: {st.need_related > 0 && `${st.need_related} related`}{st.need_related > 0 && st.need_variants > 0 && ", "}{st.need_variants > 0 && `${st.need_variants} variants`}</>}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select className="brutal-input h-9 w-auto py-0 text-sm" value={mode} onChange={(e) => setMode(e.target.value)} data-testid={`bank-gen-mode-${s.id}`}>
            <option value="related">Related questions</option><option value="variant">Variants of originals</option>
          </select>
          {prog && <select className="brutal-input h-9 w-auto py-0 text-sm" value={kind} onChange={(e) => setKind(e.target.value)} data-testid={`bank-gen-kind-${s.id}`}>
            <option value="coding">DSA coding</option><option value="sql">SQL</option><option value="web">HTML/CSS/JS</option>
          </select>}
          <input type="number" min={1} max={60} value={n} onChange={(e) => setN(Math.max(1, Math.min(60, +e.target.value || 1)))} className="brutal-input h-9 w-16 py-0 text-sm" data-testid={`bank-gen-count-${s.id}`} />
          <Button variant="primary" className="h-9 py-0 px-3 text-sm" disabled={!!job} onClick={gen} data-testid={`bank-generate-${s.id}`}>
            {job ? <><Spinner /> Generating {job.added}/{job.requested}</> : <><Sparkles size={14} /> Generate</>}
          </Button>
        </div>
      </div>
      {items.length > 0 && <div className="mt-3 flex gap-3">
        <button className="font-mono text-xs underline" onClick={() => act(() => api.post(`/admin/oa-companies/${company.id}/bank/select`, { section_id: s.id, selected: true }))} data-testid={`bank-select-all-${s.id}`}>Hand-pick all</button>
        <button className="font-mono text-xs underline" onClick={() => act(() => api.post(`/admin/oa-companies/${company.id}/bank/select`, { section_id: s.id, selected: false }))} data-testid={`bank-select-none-${s.id}`}>Clear picks</button>
        <span className="font-mono text-[11px] text-ink/50">Hand-picked questions are preferred inside each original/related group.</span>
      </div>}
      {items.length > 0 && <ul className="mt-2 max-h-96 space-y-1.5 overflow-y-auto">{items.map((q) => <BankItem key={q.id} q={q} act={act} />)}</ul>}
    </div>
  );
}

function ImportPanel({ company, status, reload }) {
  const run = () => api.post(`/admin/oa-companies/${company.id}/import`).then(() => { toast.success("Dataset import started"); reload(); }).catch((e) => toast.error(errMsg(e)));
  const s = status;
  const busy = s?.status === "running";
  return (
    <div className="border-3 border-ink bg-white p-4" data-testid={`import-panel-${company.id}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="flex items-center gap-2 font-display font-bold"><FileSearch size={16} /> Dataset import</p>
        <Button className="h-9 py-0 px-3 text-sm" disabled={busy} onClick={run} data-testid={`import-run-${company.id}`}>{busy ? <><Spinner /> {s.stage}</> : "Import questions from dataset"}</Button>
      </div>
      {s ? <div className="mt-2 space-y-1 font-mono text-[11px]" data-testid={`import-status-${company.id}`}>
        <p>Status: <b className={s.status === "done" ? "text-brand-green" : s.status === "failed" ? "text-brand-red" : ""}>{s.status}</b>{s.finished_at && ` · ${new Date(s.finished_at).toLocaleString()}`}</p>
        <p>Pages: {s.pages_total} · OCR'd: {s.pages_ocr} · failed: {s.pages_failed} · records extracted: {s.extracted} · imported: {s.imported} · duplicates: {s.duplicates} · rejected: {s.rejected}</p>
        <p>Ready: <b className="text-brand-green">{s.ready}</b> · needs review: <b>{s.needs_review}</b> · incomplete in source: <b>{s.incomplete}</b></p>
        {[...(s.page_errors || []), ...(s.errors || [])].map((e, i) => <p key={i} className="text-brand-red">{e}</p>)}
      </div> : <p className="mt-2 text-xs text-ink/60">Not imported yet. Importing turns the uploaded dataset into individual question records (verbatim wording, page refs, answer keys only when the source has them).</p>}
    </div>
  );
}

export default function QuestionBank({ company }) {
  const [bank, setBank] = useState(null);
  const timer = useRef(null);
  const load = useCallback(() => api.get(`/admin/oa-companies/${company.id}/bank`).then((r) => {
    setBank((prev) => {
      (prev?.jobs || []).filter((j) => !r.data.jobs.some((x) => x.id === j.id)).forEach((j) =>
        api.get(`/admin/oa-bank-jobs/${j.id}`).then(({ data }) => (data.status === "done" ? toast.success(`${data.added} ${data.section} questions added`) : toast.error(`${data.section}: ${data.error || "generation failed"}`))).catch(() => {}));
      return r.data;
    });
  }).catch((e) => toast.error(errMsg(e))), [company.id]);
  useEffect(() => { load(); }, [load]);
  const polling = !!bank?.jobs?.length || bank?.import_status?.status === "running";
  useEffect(() => {
    clearInterval(timer.current);
    if (polling) timer.current = setInterval(load, 4000);
    return () => clearInterval(timer.current);
  }, [polling, load]);
  const secs = company.blueprint?.sections || [];
  return (
    <div className="space-y-3" data-testid={`bank-${company.id}`}>
      <p className="flex items-center gap-2 font-display text-lg font-bold"><Database size={18} /> 2. Question bank</p>
      <p className="text-xs text-ink/60">Each test takes 65% of every section from the imported dataset (originals) and 35% from related questions Gemini writes using those originals as context. If a section can't be filled, the test refuses to start and says why.</p>
      {bank === null ? <p className="flex items-center gap-2 text-sm"><Spinner /> Loading bank…</p> : <>
        <ImportPanel company={company} status={bank.import_status} reload={load} />
        {!secs.length && <p className="text-sm text-ink/60">Save an OA structure above to map imported questions to sections.</p>}
        {secs.map((s) => (
          <SectionBank key={s.id} company={company} s={s} items={bank.questions.filter((q) => q.section_id === s.id)} stats={bank.stats?.[s.id]}
            job={bank.jobs.find((j) => j.section_id === s.id)} reload={load} />
        ))}
        {bank.unassigned?.length > 0 && <div className="border-3 border-dashed border-ink/50 p-4" data-testid="bank-unassigned">
          <p className="font-display font-bold">Not in any section ({bank.unassigned.length})</p>
          <p className="text-xs text-ink/60">Pattern notes, or questions whose type has no matching section. Add a section of that type to use them.</p>
          <ul className="mt-2 max-h-72 space-y-1.5 overflow-y-auto">{bank.unassigned.map((q) => <BankItem key={q.id} q={q} act={(fn) => fn().then(load).catch((e) => toast.error(errMsg(e)))} />)}</ul>
        </div>}
      </>}
    </div>
  );
}
