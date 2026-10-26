import React, { useState } from "react";
import { CheckCircle2, ListChecks, Play, Send, XCircle } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";
import { Badge, Button, Spinner } from "../ui";
import CodeEditor, { useEditorPrefs } from "./CodeEditor";
import LivePreview from "./LivePreview";
import { TestRow } from "./RunPanel";

const FILES = [["html", "index.html", "HTML"], ["css", "style.css", "CSS"], ["js", "script.js", "JavaScript"]];
export const EMPTY_WEB = { html: "<h1>Hello</h1>\n", css: "body {\n  font-family: sans-serif;\n}\n", js: "console.log('ready');\n" };

// HTML / CSS / JS tabs + live preview below. Used by Web Dev OA questions and the coding-panel playground.
export function WebEditor({ value, onChange, tid = "web" }) {
  const [file, setFile] = useState("html");
  const [prefs] = useEditorPrefs();
  return (
    <div className="space-y-3" data-testid={`web-editor-${tid}`}>
      <div className="flex border-3 border-b-0 border-ink">
        {FILES.map(([k, name]) => (
          <button key={k} onClick={() => setFile(k)} data-testid={`web-tab-${k}-${tid}`}
            className={`border-r-3 border-ink px-4 py-2 font-mono text-xs font-bold transition-colors ${file === k ? "bg-ink text-white" : "bg-white hover:bg-brand-yellow/40"}`}>{name}</button>
        ))}
      </div>
      <div className="-mt-3 flex">
        <CodeEditor key={file} value={value[file] || ""} onChange={(v) => onChange({ ...value, [file]: v })} language={FILES.find((f) => f[0] === file)[2]}
          fontSize={prefs.fontSize} autoClose={prefs.autoClose} testid={`web-code-${file}-${tid}`} />
      </div>
      <LivePreview html={value.html} css={value.css} js={value.js} tid={tid} />
    </div>
  );
}

function WebProblem({ p }) {
  return (
    <div className="brutal-card p-6 lg:sticky lg:top-[150px] lg:max-h-[calc(100vh-170px)] lg:overflow-y-auto" data-testid="web-problem">
      <div className="flex items-center gap-2">{p.difficulty && <Badge tone="dark">{p.difficulty}</Badge>}<Badge tone="blue">HTML · CSS · JS</Badge></div>
      <p className="mt-2 font-display text-xl font-bold">{p.title}</p>
      <p className="mt-3 whitespace-pre-line text-[15px] leading-relaxed">{p.problem}</p>
      {!!p.requirements?.length && <div className="mt-5">
        <p className="font-display font-bold">Test cases ({p.requirements.length})</p>
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">{p.requirements.map((r, i) => <li key={i}><b>{r.name}</b>{r.why && <span className="text-ink/60"> · {r.why}</span>}</li>)}</ol>
        <p className="mt-2 font-mono text-[11px] text-ink/55">Accepted only when every test case passes.</p>
      </div>}
    </div>
  );
}

// runTestsFn: optional adapter (default: existing /code/web/run endpoint).
export default function WebWorkspace({ problem, refId, value, onChange, onSubmit, submitLabel = "Submit & Next", runTestsFn, footer, submitRunsTests = true, initialResult = null }) {
  const [res, setRes] = useState(initialResult);
  const [busy, setBusy] = useState(false);
  const tid = problem.id;
  const run = async () => {
    setBusy(true);
    try {
      const data = runTestsFn ? await runTestsFn() : (await api.post("/code/web/run", { ref_id: refId, problem_id: problem.id, ...value }, { timeout: 90000 })).data;
      setRes(data);
    } catch (e) {
      toast.error(errMsg(e));
    }
    setBusy(false);
  };
  const ok = res && res.passed === res.total;
  return (
    <div className="grid lg:grid-cols-[1fr_1.25fr] gap-5" data-testid={`web-workspace-${tid}`}>
      <WebProblem p={problem} />
      <div className="flex flex-col gap-3">
        <WebEditor value={value} onChange={onChange} tid={tid} />
        <div className="border-3 border-ink">
          <div className="flex items-center border-b-3 border-ink bg-white">
            <p className="flex items-center gap-1.5 px-4 py-2.5 font-display text-sm font-bold"><ListChecks size={15} /> Test Results</p>
            {res && <span className={`ml-auto flex items-center gap-1.5 px-4 font-mono text-sm font-bold ${ok ? "text-brand-green" : "text-brand-red"}`} data-testid={`web-verdict-${tid}`}>
              {ok ? <CheckCircle2 size={15} /> : <XCircle size={15} />} {res.verdict} · {res.passed}/{res.total}</span>}
          </div>
          <div className="max-h-72 overflow-y-auto bg-paper p-3">
            {busy ? <p className="flex items-center gap-2 font-mono text-sm"><Spinner /> Running DOM test cases…</p>
              : res?.results?.length ? <ul className="space-y-1.5">{res.results.map((r) => <TestRow key={r.id} r={r} />)}</ul>
              : <p className="font-mono text-sm text-ink/55">Press <b>Run Tests</b> to check your page against the test cases.</p>}
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-3">
          <Button variant="green" onClick={run} disabled={busy} data-testid={`web-run-btn-${tid}`}>{busy ? <Spinner /> : <Play size={16} />} Run Tests</Button>
          {onSubmit && <Button variant="primary" onClick={async () => { if (submitRunsTests) await run(); const o = await onSubmit(); if (o?.results) setRes(o); }} disabled={busy} data-testid={`web-submit-btn-${tid}`}><Send size={16} /> {submitLabel}</Button>}
        </div>
        {footer}
      </div>
    </div>
  );
}
