import React, { useState } from "react";
import { ArrowDown, ArrowUp, Plus, Save, Sparkles, Trash2, Wand2 } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";
import { Button, Spinner } from "../ui";

export const KINDS = { objective: "MCQ / numeric", written: "Written / case", coding: "Coding (DSA)", sql: "SQL (MySQL)", web: "Web Dev (HTML/CSS/JS)" };
const PRESETS = [
  ["Quantitative Aptitude", "objective", 15, 20, "percentages, ratios, time & work, probability"],
  ["Logical Reasoning", "objective", 15, 20, "series, puzzles, seating, blood relations"],
  ["Verbal Ability", "objective", 10, 10, "grammar, reading comprehension, vocabulary"],
  ["Technical MCQ", "objective", 15, 15, "OOP, DBMS, OS, computer networks"],
  ["Coding", "coding", 2, 45, "arrays, strings, hashing, greedy"],
  ["SQL / MySQL", "sql", 2, 20, "joins, group by, window functions"],
  ["Web Dev (HTML/CSS/JS)", "web", 1, 30, "DOM events, forms, dynamic lists"],
  ["Written / Case", "written", 2, 15, "email writing, case analysis"],
];
const uid = () => Math.random().toString(36).slice(2, 9);
const fromPreset = ([name, kind, count, minutes, topics]) => ({ id: uid(), name, kind, count, minutes, difficulty: "Medium", topics });

function fromProfile(p) {
  const kindOf = (n) => (/sql|database/i.test(n) ? "sql" : /code|coding|program/i.test(n) ? "coding" : /web|html|front/i.test(n) ? "web" : /written|essay|email/i.test(n) ? "written" : "objective");
  const secs = (p?.sections || []).map((s) => ({ id: uid(), name: s.name.slice(0, 60), kind: kindOf(s.name), count: Math.max(1, Math.min(50, s.count || 10)), minutes: 15, difficulty: p.difficulty || "Medium", topics: (s.topics || []).join(", ").slice(0, 400) }));
  if (p?.coding?.count && !secs.some((s) => s.kind === "coding")) secs.push({ id: uid(), name: "Coding", kind: "coding", count: Math.min(50, p.coding.count), minutes: 45, difficulty: p.difficulty || "Medium", topics: (p.coding.topics || []).join(", ").slice(0, 400) });
  return secs;
}

const cell = "brutal-input h-10 w-full min-w-0 py-0 px-2 text-sm";

function SectionRow({ s, i, n, set, move, remove }) {
  const tid = `bp-sec-${i}`;
  return (
    <div className="grid grid-cols-12 items-center gap-2 border-2 border-ink bg-white p-2 [&>*]:min-w-0" data-testid={tid}>
      <div className="col-span-12 flex items-center gap-1 md:col-span-1">
        <span className="font-mono text-xs font-bold">{i + 1}</span>
        <button onClick={() => move(-1)} disabled={!i} className="disabled:opacity-20" aria-label="Move up" data-testid={`${tid}-up`}><ArrowUp size={14} /></button>
        <button onClick={() => move(1)} disabled={i === n - 1} className="disabled:opacity-20" aria-label="Move down" data-testid={`${tid}-down`}><ArrowDown size={14} /></button>
      </div>
      <input className={`${cell} col-span-6 md:col-span-3`} value={s.name} maxLength={60} onChange={(e) => set({ name: e.target.value })} placeholder="Section name" data-testid={`${tid}-name`} />
      <select className={`${cell} col-span-6 md:col-span-2`} value={s.kind} onChange={(e) => set({ kind: e.target.value })} data-testid={`${tid}-kind`}>
        {Object.entries(KINDS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
      </select>
      <label className="col-span-4 md:col-span-1"><span className="block font-mono text-[10px] text-ink/50">Questions</span>
        <input type="number" min={1} max={50} className={cell} value={s.count} onChange={(e) => set({ count: Math.max(1, Math.min(50, +e.target.value || 1)) })} data-testid={`${tid}-count`} /></label>
      <label className="col-span-4 md:col-span-1"><span className="block font-mono text-[10px] text-ink/50">Minutes</span>
        <input type="number" min={1} max={180} className={cell} value={s.minutes} onChange={(e) => set({ minutes: Math.max(1, Math.min(180, +e.target.value || 1)) })} data-testid={`${tid}-minutes`} /></label>
      <select className={`${cell} col-span-4 md:col-span-1`} value={s.difficulty} onChange={(e) => set({ difficulty: e.target.value })} data-testid={`${tid}-difficulty`}>
        {["Easy", "Medium", "Hard", "Mixed"].map((d) => <option key={d}>{d}</option>)}
      </select>
      <input className={`${cell} col-span-10 md:col-span-2`} value={s.topics} maxLength={400} onChange={(e) => set({ topics: e.target.value })} placeholder="Topics (optional)" data-testid={`${tid}-topics`} />
      <button onClick={remove} className="col-span-2 flex justify-center text-brand-red md:col-span-1" aria-label="Remove section" data-testid={`${tid}-remove`}><Trash2 size={16} /></button>
    </div>
  );
}

export default function BlueprintEditor({ company, onSaved }) {
  const [bp, setBp] = useState(() => ({ sectional: company.blueprint?.sectional ?? true, sections: company.blueprint?.sections?.map((s) => ({ ...s })) || [] }));
  const [busy, setBusy] = useState(false);
  const [preset, setPreset] = useState("0");
  const secs = bp.sections;
  const setSecs = (fn) => setBp((b) => ({ ...b, sections: fn(b.sections) }));
  const total = secs.reduce((a, s) => a + s.minutes, 0);
  const qs = secs.reduce((a, s) => a + s.count, 0);
  const save = async () => {
    if (secs.some((s) => s.name.trim().length < 2)) return toast.error("Every section needs a name.");
    setBusy(true);
    try {
      await api.put(`/admin/oa-companies/${company.id}/blueprint`, { ...bp, sections: secs.map((s) => ({ ...s, name: s.name.trim() })) });
      toast.success("OA structure saved");
      onSaved();
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };
  const move = (i, d) => setSecs((l) => { const n = [...l]; [n[i], n[i + d]] = [n[i + d], n[i]]; return n; });
  return (
    <div className="space-y-3" data-testid={`bp-editor-${company.id}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="flex items-center gap-2 font-display text-lg font-bold"><Wand2 size={18} /> 1. OA structure</p>
        <p className="font-mono text-xs" data-testid="bp-totals">{secs.length} sections · {qs} questions · {total} min</p>
      </div>
      {secs.length ? secs.map((s, i) => (
        <SectionRow key={s.id} s={s} i={i} n={secs.length} set={(patch) => setSecs((l) => l.map((x) => (x.id === s.id ? { ...x, ...patch } : x)))}
          move={(d) => move(i, d)} remove={() => setSecs((l) => l.filter((x) => x.id !== s.id))} />
      )) : <p className="border-2 border-dashed border-ink/40 p-4 text-sm text-ink/60" data-testid="bp-empty">No sections yet. Add them below, or prefill from the dataset pattern Gemini found.</p>}
      <div className="flex flex-wrap items-center gap-2">
        <select className="brutal-input h-10 w-auto py-0 text-sm" value={preset} onChange={(e) => setPreset(e.target.value)} data-testid="bp-preset-select">
          {PRESETS.map((p, i) => <option key={i} value={i}>{p[0]} · {KINDS[p[1]]}</option>)}
        </select>
        <Button className="h-10 py-0 px-3 text-sm" disabled={secs.length >= 10} onClick={() => setSecs((l) => [...l, fromPreset(PRESETS[+preset])])} data-testid="bp-add-section"><Plus size={14} /> Add section</Button>
        {company.profile?.sections?.length > 0 && <Button className="h-10 py-0 px-3 text-sm" onClick={() => setSecs(() => fromProfile(company.profile))} data-testid="bp-prefill"><Sparkles size={14} /> Prefill from dataset pattern</Button>}
        <label className="ml-auto flex items-center gap-2 font-display text-sm font-semibold">
          <input type="checkbox" className="h-4 w-4 accent-[#111]" checked={bp.sectional} onChange={(e) => setBp({ ...bp, sectional: e.target.checked })} data-testid="bp-sectional" />
          Sectional timing (lock each section when its time ends)
        </label>
        <Button variant="primary" className="h-10 py-0 px-4 text-sm" disabled={busy || !secs.length} onClick={save} data-testid="bp-save">{busy ? <Spinner /> : <Save size={14} />} Save structure</Button>
      </div>
    </div>
  );
}
