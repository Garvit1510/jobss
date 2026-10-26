import React, { useState } from "react";
import { Braces, CheckCircle2, ListChecks, Minus, Play, Plus, Send, Terminal, XCircle } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";
import { Badge, Button, Spinner } from "../ui";
import { TestRow } from "./RunPanel";
import CodeEditor, { FONT_MAX, FONT_MIN, useEditorPrefs } from "./CodeEditor";
import { PLAYGROUND_LANGS, useRunLangs } from "../../lib/codeTemplates";
import { SqlPlayground, WebPlayground } from "./Playgrounds";

function EditorPrefsBar({ prefs, setPrefs, tid }) {
  const btn = "flex h-9 w-9 items-center justify-center border-2 border-ink bg-white font-display text-sm font-bold disabled:opacity-30 hover:bg-brand-yellow/40";
  return (
    <div className="flex items-center gap-2" data-testid={`editor-prefs-${tid}`}>
      <div className="flex items-center" title="Font size">
        <button className={btn} onClick={() => setPrefs({ fontSize: prefs.fontSize - 1 })} disabled={prefs.fontSize <= FONT_MIN} aria-label="Smaller font" data-testid={`editor-font-dec-${tid}`}><Minus size={14} /></button>
        <span className="flex h-9 min-w-[52px] items-center justify-center border-y-2 border-ink bg-offwhite px-1 font-mono text-xs font-bold" data-testid={`editor-font-size-${tid}`}>{prefs.fontSize}px</span>
        <button className={btn} onClick={() => setPrefs({ fontSize: prefs.fontSize + 1 })} disabled={prefs.fontSize >= FONT_MAX} aria-label="Bigger font" data-testid={`editor-font-inc-${tid}`}><Plus size={14} /></button>
      </div>
      <button role="switch" aria-checked={prefs.autoClose} onClick={() => setPrefs({ autoClose: !prefs.autoClose })} data-testid={`editor-autoclose-${tid}`}
        className={`flex h-9 items-center gap-1.5 border-2 border-ink px-2.5 font-mono text-xs font-bold transition-colors ${prefs.autoClose ? "bg-brand-green" : "bg-white"}`} title="Auto-close brackets and quotes">
        <Braces size={14} /> Auto-close {prefs.autoClose ? "on" : "off"}
      </button>
    </div>
  );
}


function ProblemPanel({ c }) {
  return (
    <div className="brutal-card p-6 lg:sticky lg:top-[150px] lg:max-h-[calc(100vh-170px)] lg:overflow-y-auto" data-testid="code-problem">
      <div className="flex items-center gap-2">{c.difficulty && <Badge tone="dark">{c.difficulty}</Badge>}<p className="font-display text-xl font-bold">{c.title}</p></div>
      <p className="mt-3 whitespace-pre-line text-[15px] leading-relaxed">{c.problem}</p>
      {c.input_format && <p className="mt-4 text-sm"><b>Input:</b> {c.input_format}</p>}
      {c.output_format && <p className="text-sm"><b>Output:</b> {c.output_format}</p>}
      {c.constraints && <p className="mt-1 text-sm"><b>Constraints:</b> {c.constraints}</p>}
      {c.io_note && <p className="mt-2 border-l-4 border-brand-blue bg-brand-blue/10 px-3 py-2 text-sm" data-testid="code-io-note"><b>Judge input format (stdin):</b> {c.io_note}</p>}
      {(c.examples || []).map((ex, i) => (
        <pre key={i} className="mt-3 border-2 border-ink bg-offwhite p-3 font-mono text-xs whitespace-pre-wrap">Input: {ex.input}{"\n"}Output: {ex.output}</pre>
      ))}
    </div>
  );
}

// runTestsFn / runCustomFn / languages: optional adapters so other flows (e.g. Accenture R4) can route execution to their own endpoints.
export default function CodeWorkspace({ problem, language, onLanguage, code, onCode, onReset, context, refId, problemId = "", onSubmit, submitLabel = "Submit & Next", submitBusy = false, footer, runTestsFn, runCustomFn, languages, submitRunsTests = true, initialResult = null, note }) {
  const [tab, setTab] = useState("results");
  const [res, setRes] = useState(initialResult);
  const [busy, setBusy] = useState(false);
  const [stdin, setStdin] = useState(problem.examples?.[0]?.input || "");
  const [cout, setCout] = useState(null);
  const [crun, setCrun] = useState(false);
  const tid = problemId || "iv";

  const runTests = async () => {
    setBusy(true);
    setTab("results");
    try {
      const data = runTestsFn ? await runTestsFn() : (await api.post("/code/run", { context, ref_id: refId, problem_id: problemId, language, code }, { timeout: 180000 })).data;
      setRes(data);
      return data;
    } catch (e) {
      toast.error(errMsg(e));
      return null;
    } finally {
      setBusy(false);
    }
  };
  const runCustom = async () => {
    setCrun(true);
    try {
      const data = runCustomFn ? await runCustomFn(stdin) : (await api.post("/code/try", { language, code, stdin }, { timeout: 60000 })).data;
      setCout(data);
    } catch (e) {
      toast.error(errMsg(e));
    }
    setCrun(false);
  };
  const submit = async () => {
    if (submitRunsTests) await runTests(); // auto-run & check the test cases before moving on
    const out = onSubmit && await onSubmit();
    if (out?.results) setRes(out);
  };

  const all = res && !res.compile_error && res.passed === res.total;
  const cok = cout && !cout.compile_error && cout.status === "Finished";
  const runLangs = useRunLangs();
  const langs = languages || runLangs;
  const [prefs, setPrefs] = useEditorPrefs();
  const changeLang = (l) => { setRes(null); setCout(null); onLanguage(l); };

  const play = PLAYGROUND_LANGS.includes(language);
  return (
    <div className="grid lg:grid-cols-[1fr_1.15fr] gap-5" data-testid={`code-workspace-${tid}`}>
      <ProblemPanel c={problem} />
      <div className="flex flex-col">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <select value={language} onChange={(e) => changeLang(e.target.value)} className="h-9 border-2 border-ink bg-white px-2 font-display text-sm font-semibold" data-testid={`code-lang-${tid}`}>
            {langs.map((l) => <option key={l.name} value={l.name} disabled={!l.available}>{l.name}{l.playground ? " · playground" : l.available ? "" : " (unavailable)"}</option>)}
          </select>
          <div className="flex items-center gap-2">
            {onReset && !play && <button onClick={() => window.confirm("Reset this language's code to the starter code?") && onReset()} className="h-9 border-2 border-ink bg-white px-2.5 font-mono text-xs font-bold hover:bg-brand-yellow/40" data-testid={`code-reset-${tid}`}>Reset</button>}
            <EditorPrefsBar prefs={prefs} setPrefs={setPrefs} tid={tid} />
          </div>
        </div>
        <p className="mt-1.5 font-mono text-[11px] text-ink/55" data-testid={`code-accepted-${tid}`}>
          {note || <>Accepted: {langs.filter((l) => l.available && !l.playground).map((l) => l.name).join(" · ")} — read from stdin, print to stdout. Switching language loads its starter code; your code in each language is kept.</>}
        </p>
        {play ? <div className="mt-2">{language === "MySQL" ? <SqlPlayground tid={tid} /> : <WebPlayground tid={tid} />}</div> : <>
        <div className="mt-2 flex flex-1 flex-col">
          <CodeEditor value={code} onChange={onCode} language={language} fontSize={prefs.fontSize} autoClose={prefs.autoClose} />
        </div>

        {/* Console: Test Results / Custom Input */}
        <div className="mt-3 border-3 border-ink">
          <div className="flex border-b-3 border-ink">
            {[["results", "Test Results", ListChecks], ["custom", "Custom Input", Terminal]].map(([k, label, I]) => (
              <button key={k} onClick={() => setTab(k)} data-testid={`code-tab-${k}-${tid}`}
                className={`flex items-center gap-1.5 px-4 py-2.5 font-display text-sm font-bold border-r-3 border-ink transition-colors ${tab === k ? "bg-ink text-white" : "bg-white hover:bg-offwhite"}`}>
                <I size={15} /> {label}
              </button>
            ))}
            {res && !res.compile_error && tab === "results" && (
              <span className={`ml-auto flex items-center gap-1.5 px-4 font-mono text-sm font-bold ${all ? "text-brand-green" : "text-brand-red"}`} data-testid={`code-summary-${tid}`}>
                {all ? <CheckCircle2 size={15} /> : <XCircle size={15} />} {res.passed}/{res.total} passed
              </span>
            )}
          </div>
          <div className="max-h-72 overflow-y-auto bg-paper p-3">
            {tab === "results" ? (
              busy ? <p className="flex items-center gap-2 font-mono text-sm"><Spinner /> Running test cases…</p>
                : res?.compile_error ? <pre className="max-h-48 overflow-auto border-2 border-brand-red bg-ink p-3 font-mono text-xs text-brand-red whitespace-pre-wrap" data-testid={`code-compile-error-${tid}`}>{res.compile_error}</pre>
                : res?.results?.length ? <ul className="space-y-1.5">{res.results.map((r) => <TestRow key={r.id} r={r} />)}</ul>
                : <p className="font-mono text-sm text-ink/55">Press <b>Run Code</b> to check your solution against sample, edge, boundary and stress tests.</p>
            ) : (
              <div className="space-y-2">
                <textarea value={stdin} onChange={(e) => setStdin(e.target.value)} spellCheck={false} placeholder="Type custom stdin here" data-testid={`code-custom-stdin-${tid}`}
                  className="min-h-[80px] w-full resize-y border-2 border-ink bg-white p-2 font-mono text-xs outline-none" />
                <div className="flex items-center gap-3">
                  <Button className="h-8 py-0 px-3 text-sm" onClick={runCustom} disabled={crun || !code.trim()} data-testid={`code-custom-run-${tid}`}>{crun ? <Spinner /> : <Play size={14} />} Run with input</Button>
                  {cout && !cout.compile_error && <span className={`font-mono text-xs font-bold ${cok ? "text-brand-green" : "text-brand-red"}`}>{cout.status} · {cout.time_ms}ms</span>}
                </div>
                {cout?.compile_error && <pre className="max-h-40 overflow-auto bg-ink p-2 font-mono text-xs text-brand-red whitespace-pre-wrap">{cout.compile_error}</pre>}
                {cout && !cout.compile_error && <pre className="max-h-48 overflow-auto bg-ink p-2 font-mono text-xs text-white whitespace-pre-wrap" data-testid={`code-custom-out-${tid}`}>{cout.stdout || "(no output)"}</pre>}
                {cout?.stderr && <pre className="max-h-32 overflow-auto bg-brand-red/10 p-2 font-mono text-xs whitespace-pre-wrap">{cout.stderr}</pre>}
              </div>
            )}
          </div>
        </div>

        </>}
        {footer}

        {!play && <div className="mt-3 flex flex-wrap items-center justify-end gap-3">
          <Button variant="green" onClick={runTests} disabled={busy || !code.trim()} data-testid={`code-run-btn-${tid}`}>{busy ? <Spinner /> : <Play size={16} />} Run Code</Button>
          {onSubmit && <Button variant="primary" onClick={submit} disabled={submitBusy || busy || !code.trim()} data-testid={`code-submit-btn-${tid}`}>{submitBusy ? <Spinner /> : <Send size={16} />} {submitLabel}</Button>}
        </div>}
      </div>
    </div>
  );
}
