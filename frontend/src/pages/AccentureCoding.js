import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { toast } from "sonner";
import api, { errMsg } from "../lib/api";
import { useProctorDone } from "../components/accenture/ProctorGate";
import { Badge, Button, Card, Spinner } from "../components/ui";
import CodeWorkspace from "../components/code/CodeWorkspace";
import SqlWorkspace from "../components/code/SqlWorkspace";
import WebWorkspace from "../components/code/WebWorkspace";
import { fmt, useCountdown } from "../components/accenture/timer";

const LANG_LABEL_BY_ID = { python: "Python", java: "Java", cpp: "C++", javascript: "JavaScript" };

const LANG_ID = { Python: "python", Java: "java", "C++": "cpp", JavaScript: "javascript" };
const isTable = (x) => x && Array.isArray(x.columns) && Array.isArray(x.rows);

function useAutosave(mockId, body, deps) {
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return undefined; }
    const x = setTimeout(() => api.post(`/accenture-mocks/${mockId}/coding/draft`, body()).catch(() => {}), 1500);
    return () => clearTimeout(x);
  }, deps);
}

// Round 4 reuses the existing CodeWorkspace / SqlWorkspace / WebWorkspace UI; execution goes only to the jailed Accenture endpoints.
function Workspace({ mockId, t, onState, offset }) {
  const d = t.draft || {};
  const base = t.type === "dsa" ? (d.lang && LANG_LABEL_BY_ID[d.lang]) || "Python" : null;
  const [lang, setLang] = useState(base);
  const [codes, setCodes] = useState(() => (t.type === "dsa" ? { ...Object.fromEntries(Object.entries(t.starters).map(([k, v]) => [LANG_LABEL_BY_ID[k], v])), ...(d.code ? { [base]: d.code } : {}) } : {}));
  const [sql, setSql] = useState(d.code || "-- write your query\nSELECT ");
  const [web, setWeb] = useState({ html: d.html ?? t.starter?.html ?? "", css: d.css ?? t.starter?.css ?? "", js: d.js ?? t.starter?.js ?? "" });
  const [subBusy, setSubBusy] = useState(false);
  const [subs, setSubs] = useState({ n: t.submissions, best: t.best_score });
  const left = useCountdown(t.deadline, offset);
  useEffect(() => {
    if (left > 0) return undefined;
    const x = setTimeout(() => api.get(`/accenture-mocks/${mockId}/coding`).then((r) => onState(r.data)).catch(() => {}), 6000);
    return () => clearTimeout(x);
  }, [left, mockId, onState]);
  const body = () => (t.type === "frontend_js" ? { lang: "web", ...web } : t.type === "sql" ? { lang: "sql", code: sql } : { lang: LANG_ID[lang], code: codes[lang] || "" });
  useAutosave(mockId, body, [codes, lang, sql, web]);
  const run = async () => (await api.post(`/accenture-mocks/${mockId}/coding/run`, body(), { timeout: 180000 })).data;
  const submit = async () => {
    setSubBusy(true);
    try {
      const { data } = await api.post(`/accenture-mocks/${mockId}/coding/submit`, body(), { timeout: 180000 });
      setSubs((x) => ({ n: x.n + 1, best: data.best_score }));
      toast.success(`Submission scored ${data.score}% (best ${data.best_score}%)`);
      return data.result;
    } catch (e) { toast.error(errMsg(e)); return null; } finally { setSubBusy(false); }
  };
  const next = async () => {
    if (!window.confirm("Finish this task and move on? You cannot come back to it.")) return;
    try { const { data } = await api.post(`/accenture-mocks/${mockId}/coding/next`); onState(data); } catch (e) { toast.error(errMsg(e)); }
  };
  const footer = (
    <div className="mt-3 flex flex-wrap items-center gap-3 border-2 border-ink bg-white p-2" data-testid="code-task-footer">
      <span className={`font-mono text-lg font-bold ${left <= 120 ? "text-brand-red" : ""}`} data-testid="code-timer">{fmt(left)}</span>
      <span className="text-xs text-ink/60" data-testid="code-submissions">Submissions {subs.n} · best {subs.best ?? "–"}% · Run checks visible tests; Submit runs visible + hidden tests and is scored</span>
      <Button variant="dark" className="ml-auto" onClick={next} data-testid="code-next-btn">Finish task</Button>
    </div>
  );
  const common = { onSubmit: submit, submitLabel: "Submit (scored)", submitRunsTests: false, runTestsFn: run, footer, initialResult: t.last_result || null };
  if (t.type === "sql") {
    const problem = { id: t.qid, title: t.title, difficulty: t.difficulty, problem: t.problem, schema: t.schema, sample_data: t.sample_data?.[0] || "",
      sample_output: isTable(t.sample_expected?.[0]) ? t.sample_expected[0] : null };
    const tryFn = async (query) => (await api.post(`/accenture-mocks/${mockId}/coding/sql-try`, { query }, { timeout: 60000 })).data;
    return <SqlWorkspace problem={problem} value={sql} onChange={setSql} tryFn={tryFn} {...common} />;
  }
  if (t.type === "frontend_js") {
    const problem = { id: t.qid, title: t.title, difficulty: t.difficulty, problem: t.problem, requirements: (t.visible_checks || []).map((c) => ({ name: c.name })) };
    return <WebWorkspace problem={problem} value={web} onChange={setWeb} {...common} />;
  }
  const problem = { title: t.title, difficulty: t.difficulty, problem: t.problem, input_format: t.input_format, output_format: t.output_format, constraints: t.constraints,
    examples: (t.samples || []).map((x) => ({ input: x.input, output: x.output })) };
  const languages = t.languages.map((l) => ({ name: l.label, available: l.available }));
  const runCustomFn = async (stdin) => (await api.post(`/accenture-mocks/${mockId}/coding/try`, { lang: LANG_ID[lang], code: codes[lang] || "", stdin }, { timeout: 60000 })).data;
  return (
    <CodeWorkspace problem={problem} problemId={t.qid} language={lang} onLanguage={setLang} code={codes[lang] || ""} onCode={(v) => setCodes((c) => ({ ...c, [lang]: v }))}
      onReset={() => setCodes((c) => ({ ...c, [lang]: t.starters[LANG_ID[lang]] }))} languages={languages} runCustomFn={runCustomFn} submitBusy={subBusy}
      note={`${t.hidden_count} hidden tests · read from stdin, print to stdout · runs in the isolated Round 4 runner`} {...common} />
  );
}

export default function AccentureCoding() {
  const { mockId } = useParams();
  const preview = new URLSearchParams(useLocation().search).get("preview") === "1";
  const [s, setS] = useState(null);
  useProctorDone(!!(s?.finished_at || s?.result));
  const offset = useMemo(() => (s ? new Date(s.server_time).getTime() - Date.now() : 0), [s?.server_time]);
  useEffect(() => { api.post(`/accenture-mocks/${mockId}/coding/start`, { preview }).then((r) => setS(r.data)).catch((e) => { toast.error(errMsg(e)); setS({ error: errMsg(e) }); }); }, [mockId, preview]);
  if (s === null) return <div className="flex justify-center py-24"><Spinner /></div>;
  if (s.error) return <div className="p-12 text-center" data-testid="code-unavailable"><p className="font-bold">Round 4 is not available.</p><p className="mt-2 text-sm" data-testid="code-unavailable-reason">{s.error}</p><Link to="/accenture-mocks" className="mt-3 inline-block underline">Back to Accenture mocks</Link></div>;
  const t = s.current !== null ? s.tasks[s.current] : null;
  const begin = () => api.post(`/accenture-mocks/${mockId}/coding/begin`).then((r) => setS(r.data)).catch((e) => toast.error(errMsg(e)));
  return (
    <div className="mx-auto max-w-[1400px] px-4 py-8" data-testid="code-page">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <h1 className="mr-4 text-xl font-semibold">Round 4 · Coding{preview ? " · Admin preview" : ""}</h1>
        {s.tasks.map((x, i) => <Badge key={x.qid} tone={x.status === "done" ? "green" : i === s.current ? "yellow" : "white"} data-testid={`code-step-${x.type}`}>{i + 1}. {x.type === "dsa" ? "DSA" : x.type === "sql" ? "SQL" : "JS Frontend"} · {x.minutes}m</Badge>)}
      </div>
      {s.runner_available === false && <p className="mb-4 border-2 border-brand-red bg-white p-3 text-sm font-semibold text-brand-red" data-testid="code-runner-down">{s.sandbox_note}</p>}
      {!t ? (
        <Card className="mx-auto max-w-2xl p-8" data-testid="code-final">
          <h2 className="text-2xl font-bold">Round 4 complete</h2>
          <p className="mt-2 text-xl font-bold" data-testid="code-percent">{s.result.percent}% · {s.result.passed ? "meets" : "below"} the {s.result.cutoff_percent}% cutoff</p>
          <ul className="mt-3 text-sm">{s.tasks.map((x) => <li key={x.qid} data-testid={`code-final-${x.type}`}>{x.title}: {x.best_score ?? 0}% (best of {x.submissions} submission{x.submissions === 1 ? "" : "s"})</li>)}</ul>
          <p className="mt-3 text-xs text-ink/60">{s.scoring.note}</p>
          <p className="mt-1 text-xs text-ink/60">{s.sandbox_note}</p>
          <Link to="/accenture-mocks" className="mt-4 inline-block underline">Back to Accenture mocks</Link>
        </Card>
      ) : t.status === "pending" ? (
        <Card className="mx-auto max-w-2xl p-8" data-testid="code-intro">
          <h2 className="text-2xl font-bold">Task {s.current + 1} of 3 · {t.type === "dsa" ? "DSA" : t.type === "sql" ? "SQL" : "JavaScript Frontend"}</h2>
          <p className="mt-2 text-sm">{t.minutes} minutes. Run checks visible tests only; Submit runs visible and hidden tests and is scored (best submission counts, max {s.scoring.max_submissions}). When time runs out the task closes automatically.</p>
          <Button variant="dark" className="mt-6" onClick={begin} data-testid="code-begin-btn">Start task</Button>
        </Card>
      ) : <Workspace key={t.qid} mockId={mockId} t={t} onState={setS} offset={offset} />}
    </div>
  );
}
