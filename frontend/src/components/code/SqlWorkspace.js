import React, { useEffect, useState } from "react";
import { CheckCircle2, Database, ListChecks, Play, Send, Table2, XCircle } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";
import { Badge, Button, Spinner } from "../ui";
import CodeEditor, { useEditorPrefs } from "./CodeEditor";
import ResultTable from "./ResultTable";
import { TestRow } from "./RunPanel";

export const SQL_NOTE = "MySQL-style SQL · runs in a sandbox database (MySQL-compatible SQLite engine)";
const tableNames = (schema) => [...(schema || "").matchAll(/create\s+table\s+(?:if\s+not\s+exists\s+)?[`"]?(\w+)/gi)].map((m) => m[1]);

export async function tryQuery(query, setup = "") {
  const { data } = await api.post("/code/sql/try", { query, setup }, { timeout: 60000 });
  return data;
}

function SampleTables({ p, tryFn = tryQuery }) {
  const [tables, setTables] = useState(null);
  useEffect(() => {
    let live = true;
    (async () => {
      const out = [];
      for (const name of tableNames(p.schema)) {
        try { out.push([name, await tryFn(`SELECT * FROM ${name};`, `${p.schema}\n${p.sample_data}`)]); } catch { /* shown as schema only */ }
      }
      if (live) setTables(out);
    })();
    return () => { live = false; };
  }, [p.schema, p.sample_data, tryFn]);
  if (!tables) return <p className="mt-3 flex items-center gap-2 font-mono text-xs"><Spinner /> Loading sample tables…</p>;
  return tables.map(([name, t]) => (
    <div key={name} className="mt-3"><p className="mb-1 font-mono text-xs font-bold">{name}</p><ResultTable table={t} testid={`sql-sample-${name}`} /></div>
  ));
}

function SqlProblem({ p, tryFn }) {
  return (
    <div className="brutal-card p-6 lg:sticky lg:top-[150px] lg:max-h-[calc(100vh-170px)] lg:overflow-y-auto" data-testid="sql-problem">
      <div className="flex items-center gap-2">{p.difficulty && <Badge tone="dark">{p.difficulty}</Badge>}<Badge tone="yellow">MySQL</Badge></div>
      <p className="mt-2 font-display text-xl font-bold">{p.title}</p>
      <p className="mt-3 whitespace-pre-line text-[15px] leading-relaxed">{p.problem}</p>
      <p className="mt-5 flex items-center gap-1.5 font-display font-bold"><Database size={15} /> Schema</p>
      <pre className="mt-2 max-h-48 overflow-auto border-2 border-ink bg-offwhite p-3 font-mono text-xs whitespace-pre-wrap">{p.schema}</pre>
      <p className="mt-5 flex items-center gap-1.5 font-display font-bold"><Table2 size={15} /> Sample data</p>
      <SampleTables p={p} tryFn={tryFn} />
      {p.sample_output && <><p className="mt-5 font-display font-bold">Expected output (sample)</p><div className="mt-2"><ResultTable table={p.sample_output} testid="sql-sample-output" /></div></>}
    </div>
  );
}

// runTestsFn / tryFn: optional adapters (default: existing /code/sql/* endpoints).
export default function SqlWorkspace({ problem, refId, value, onChange, onSubmit, submitLabel = "Submit & Next", runTestsFn, tryFn, footer, submitRunsTests = true, initialResult = null }) {
  const [tab, setTab] = useState("results");
  const [res, setRes] = useState(initialResult);
  const [out, setOut] = useState(null);
  const [busy, setBusy] = useState("");
  const [prefs] = useEditorPrefs();
  const tid = problem.id;
  const runTests = async () => {
    setBusy("tests"); setTab("results");
    try {
      const data = runTestsFn ? await runTestsFn() : (await api.post("/code/sql/run", { ref_id: refId, problem_id: problem.id, query: value }, { timeout: 60000 })).data;
      setRes(data);
    } catch (e) { toast.error(errMsg(e)); }
    setBusy("");
  };
  const runQuery = async () => {
    setBusy("query"); setTab("output");
    try { setOut(await (tryFn || tryQuery)(value, `${problem.schema}\n${problem.sample_data}`)); } catch (e) { toast.error(errMsg(e)); }
    setBusy("");
  };
  const ok = res && res.passed === res.total;
  const empty = !value.trim();
  return (
    <div className="grid lg:grid-cols-[1fr_1.15fr] gap-5" data-testid={`sql-workspace-${tid}`}>
      <SqlProblem p={problem} tryFn={tryFn} />
      <div className="flex flex-col">
        <p className="mb-2 font-mono text-[11px] text-ink/55">{SQL_NOTE}</p>
        <div className="flex flex-1 flex-col"><CodeEditor value={value} onChange={onChange} language="MySQL" fontSize={prefs.fontSize} autoClose={prefs.autoClose} testid={`sql-editor-${tid}`} /></div>
        <div className="mt-3 border-3 border-ink">
          <div className="flex border-b-3 border-ink">
            {[["results", "Test Results", ListChecks], ["output", "Query Output", Table2]].map(([k, label, I]) => (
              <button key={k} onClick={() => setTab(k)} data-testid={`sql-tab-${k}-${tid}`}
                className={`flex items-center gap-1.5 border-r-3 border-ink px-4 py-2.5 font-display text-sm font-bold ${tab === k ? "bg-ink text-white" : "bg-white hover:bg-offwhite"}`}><I size={15} /> {label}</button>
            ))}
            {res && tab === "results" && <span className={`ml-auto flex items-center gap-1.5 px-4 font-mono text-sm font-bold ${ok ? "text-brand-green" : "text-brand-red"}`} data-testid={`sql-verdict-${tid}`}>
              {ok ? <CheckCircle2 size={15} /> : <XCircle size={15} />} {res.verdict} · {res.passed}/{res.total}</span>}
          </div>
          <div className="max-h-80 overflow-y-auto bg-paper p-3">
            {busy ? <p className="flex items-center gap-2 font-mono text-sm"><Spinner /> {busy === "tests" ? "Running test cases…" : "Running query on sample data…"}</p>
              : tab === "results" ? (res?.results?.length ? <ul className="space-y-1.5">{res.results.map((r) => <TestRow key={r.id} r={r} />)}</ul>
                : <p className="font-mono text-sm text-ink/55">Press <b>Run Tests</b> to check your query against the sample and hidden datasets.</p>)
              : out ? (out.error ? <pre className="border-2 border-brand-red bg-ink p-3 font-mono text-xs text-brand-red whitespace-pre-wrap" data-testid={`sql-error-${tid}`}>{out.error}</pre>
                : <ResultTable table={out} testid={`sql-output-${tid}`} empty="Query returned no rows" />)
              : <p className="font-mono text-sm text-ink/55">Press <b>Run Query</b> to see your result on the sample data.</p>}
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center justify-end gap-3">
          <Button onClick={runQuery} disabled={!!busy || empty} data-testid={`sql-query-btn-${tid}`}><Play size={16} /> Run Query</Button>
          <Button variant="green" onClick={runTests} disabled={!!busy || empty} data-testid={`sql-run-btn-${tid}`}>{busy === "tests" ? <Spinner /> : <ListChecks size={16} />} Run Tests</Button>
          {onSubmit && <Button variant="primary" onClick={async () => { if (!empty && submitRunsTests) await runTests(); const o = await onSubmit(); if (o?.results) { setRes(o); setTab("results"); } }} disabled={!!busy} data-testid={`sql-submit-btn-${tid}`}><Send size={16} /> {submitLabel}</Button>}
        </div>
        {footer}
      </div>
    </div>
  );
}
