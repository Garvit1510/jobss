import React, { useCallback, useEffect, useRef, useState } from "react";
import { Building2, FilePlus2, Settings2, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";
import { timeAgo } from "../../lib/format";
import { Badge, Button, Card, EmptyState, Spinner } from "../ui";
import BlueprintEditor from "./BlueprintEditor";
import QuestionBank from "./QuestionBank";

const ACCEPT = ".txt,.csv,.json,.md,.pdf,.docx,.png,.jpg,.jpeg,.webp";

function toForm(fields, files) {
  const fd = new FormData();
  Object.entries(fields).forEach(([k, v]) => fd.append(k, v));
  [...(files || [])].forEach((f) => fd.append("files", f));
  return fd;
}

function AddForm({ onAdded }) {
  const [f, setF] = useState({ name: "", description: "", text: "" });
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);
  const save = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/admin/oa-companies", toForm(f, files));
      toast.success(`${data.name} OA added${data.profile ? " and pattern analysed" : ""}`);
      setF({ name: "", description: "", text: "" });
      setFiles([]);
      if (fileRef.current) fileRef.current.value = "";
      onAdded();
    } catch (e) {
      toast.error(errMsg(e));
    }
    setBusy(false);
  };
  return (
    <Card className="p-6 space-y-4" data-testid="oa-add-form">
      <h3 className="flex items-center gap-2 text-xl font-bold"><FilePlus2 size={20} /> Add company-wise OA</h3>
      <div className="grid md:grid-cols-2 gap-3">
        <input className="brutal-input h-11 py-0" placeholder="Company name, e.g. Amazon" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid="oa-add-name" />
        <input className="brutal-input h-11 py-0" placeholder="Short description (optional)" maxLength={300} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} data-testid="oa-add-desc" />
      </div>
      <label className="flex cursor-pointer items-center gap-3 border-3 border-dashed border-ink bg-offwhite p-4 text-sm" data-testid="oa-add-files-label">
        <Upload size={18} />
        <span className="flex-1">{files.length ? `${files.length} file(s): ${[...files].map((x) => x.name).join(", ")}` : "Upload dataset files: past OA questions, patterns, experiences (PDF incl. scanned/screenshot PDFs, PNG/JPG screenshots, DOCX, TXT, CSV, JSON, MD · max 250 MB each · image pages are OCR'd)"}</span>
        <input ref={fileRef} type="file" multiple accept={ACCEPT} className="hidden" onChange={(e) => setFiles(e.target.files)} data-testid="oa-add-files" />
      </label>
      <textarea className="brutal-input min-h-[120px] text-sm" placeholder="…or paste questions / pattern notes here (sections, number of questions, time limit, coding style)" value={f.text} onChange={(e) => setF({ ...f, text: e.target.value })} data-testid="oa-add-text" />
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-ink/60">Gemini analyses the dataset once to learn the pattern, then generates new OAs that follow it.</p>
        <Button variant="primary" onClick={save} disabled={busy || f.name.trim().length < 2 || (!files.length && !f.text.trim())} data-testid="oa-add-submit">{busy ? <><Spinner /> Analysing…</> : "Add company OA"}</Button>
      </div>
    </Card>
  );
}

function CompanyRow({ c, onChange }) {
  const [busy, setBusy] = useState("");
  const [cfg, setCfg] = useState(false);
  const ref = useRef(null);
  const act = async (kind, fn) => {
    setBusy(kind);
    try {
      await fn();
      onChange();
    } catch (e) {
      toast.error(errMsg(e));
    }
    setBusy("");
  };
  const addFiles = (files) => files.length && act("data", async () => {
    await api.post(`/admin/oa-companies/${c.id}/dataset`, toForm({}, files));
    toast.success(`Dataset added to ${c.name}`);
  });
  const p = c.profile || {};
  return (
    <Card className="p-5" data-testid={`oa-company-row-${c.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 font-display text-lg font-bold"><Building2 size={16} /> {c.name} {c.active ? <Badge tone="green">Live</Badge> : <Badge>Hidden</Badge>}</p>
          <p className="mt-1 text-sm text-ink/70">{c.description || p.summary || "No description"}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <input ref={ref} type="file" multiple accept={ACCEPT} className="hidden" onChange={(e) => addFiles(e.target.files)} />
          <Button variant={cfg ? "dark" : "yellow"} className="h-9 py-0 px-3 text-sm" onClick={() => setCfg(!cfg)} data-testid={`oa-company-configure-${c.id}`}><Settings2 size={14} /> {cfg ? "Close builder" : "Configure OA"}</Button>
          <Button className="h-9 py-0 px-3 text-sm" disabled={!!busy} onClick={() => ref.current?.click()} data-testid={`oa-company-add-data-${c.id}`}>{busy === "data" ? <Spinner /> : <Upload size={14} />} Add data</Button>
          <Button className="h-9 py-0 px-3 text-sm" disabled={!!busy} onClick={() => act("toggle", () => api.patch(`/admin/oa-companies/${c.id}`, { active: !c.active }))} data-testid={`oa-company-toggle-${c.id}`}>{c.active ? "Hide" : "Publish"}</Button>
          <Button variant="dark" className="h-9 py-0 px-3 text-sm" disabled={!!busy} data-testid={`oa-company-delete-${c.id}`}
            onClick={() => window.confirm(`Delete ${c.name} OA and its dataset?`) && act("del", () => api.delete(`/admin/oa-companies/${c.id}`))}><Trash2 size={14} /></Button>
        </div>
      </div>
      {!!c.blueprint?.sections?.length && (
        <div className="mt-4 flex flex-wrap items-center gap-2" data-testid={`oa-company-blueprint-${c.id}`}>
          <Badge tone="dark">Custom structure</Badge>
          {c.blueprint.sections.map((s) => <span key={s.id} className="tag-chip">{s.name} · {s.count}Q · {s.minutes}m</span>)}
          <span className="tag-chip">{c.blueprint.duration_minutes} min total{c.blueprint.sectional ? " · sectional" : ""}</span>
        </div>
      )}
      {!c.blueprint?.sections?.length && !!p.sections?.length && (
        <div className="mt-4 flex flex-wrap gap-2">
          {p.sections.map((s, i) => <span key={i} className="tag-chip">{s.name} · {s.count}</span>)}
          {p.coding?.count > 0 && <span className="tag-chip">Coding · {p.coding.count}</span>}
          {p.duration_minutes && <span className="tag-chip">{p.duration_minutes} min</span>}
          {p.difficulty && <span className="tag-chip">{p.difficulty}</span>}
        </div>
      )}
      {c.import_status && <p className="mt-3 font-mono text-[11px]" data-testid={`oa-company-import-${c.id}`}>
        Dataset import: <b className={c.import_status.status === "done" ? "text-brand-green" : c.import_status.status === "failed" ? "text-brand-red" : ""}>{c.import_status.status}</b>
        {" "}· {c.import_status.imported} questions imported ({c.import_status.ready} ready, {c.import_status.needs_review} need review, {c.import_status.incomplete} incomplete) · {c.import_status.duplicates} duplicates · {c.import_status.pages_failed} failed pages
      </p>}
      {cfg && <div className="mt-5 space-y-6 border-t-3 border-ink pt-5" data-testid={`oa-builder-${c.id}`}>
        <BlueprintEditor company={c} onSaved={onChange} />
        <QuestionBank key={JSON.stringify(c.blueprint?.sections?.map((s) => s.id))} company={c} />
      </div>}
      <p className="mt-3 font-mono text-[11px] text-ink/50">{(c.files || []).length} source(s) · {(c.chars || 0).toLocaleString()} chars · updated {timeAgo(c.updated_at)}{!c.profile && " · pattern not analysed yet (add data to retry)"}</p>
    </Card>
  );
}

export default function OACompanies() {
  const [list, setList] = useState(null);
  const load = useCallback(() => api.get("/admin/oa-companies").then((r) => setList(r.data.companies)).catch((e) => toast.error(errMsg(e))), []);
  useEffect(() => { load(); }, [load]);
  return (
    <div className="space-y-6" data-testid="admin-oa">
      <AddForm onAdded={load} />
      {list === null ? <p className="flex items-center gap-2 text-sm"><Spinner /> Loading…</p> : !list.length ? (
        <EmptyState icon={Building2} title="No company OAs yet" text="Add a company with its real OA dataset above." testid="oa-companies-empty" />
      ) : <div className="grid gap-4 [&>*]:min-w-0">{list.map((c) => <CompanyRow key={c.id} c={c} onChange={load} />)}</div>}
    </div>
  );
}
