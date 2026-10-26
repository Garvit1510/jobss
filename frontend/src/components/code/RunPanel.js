import React, { useState } from "react";
import { CheckCircle2, ChevronDown, Lock, Play, Terminal, XCircle } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";
import { Badge, Button, Spinner } from "../ui";
import ResultTable from "./ResultTable";

const CAT = { sample: "white", edge: "yellow", boundary: "blue", stress: "dark" };

export function TestRow({ r }) {
  const [open, setOpen] = useState(!r.passed && r.visible);
  return (
    <li className="border-2 border-ink bg-white" data-testid={`run-test-${r.id}`}>
      <button onClick={() => setOpen(!open)} className="flex w-full items-center gap-3 px-3 py-2 text-left">
        {r.passed ? <CheckCircle2 size={17} className="shrink-0 text-brand-green" /> : <XCircle size={17} className="shrink-0 text-brand-red" />}
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2 text-sm font-semibold">{r.name} <Badge tone={CAT[r.category]} className="capitalize">{r.category}</Badge>{!r.visible && <Lock size={12} className="text-ink/40" />}</span>
          {r.why && <span className="block text-xs text-ink/55">{r.why}</span>}
        </span>
        <span className={`shrink-0 font-mono text-xs font-bold ${r.passed ? "text-brand-green" : "text-brand-red"}`}>{r.status}</span>
        <span className="shrink-0 font-mono text-[11px] text-ink/50">{r.time_ms}ms</span>
        <ChevronDown size={15} className={`shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="border-t-2 border-ink/10 p-3 font-mono text-xs space-y-2">
          {r.visible && r.expected_table ? (
            <div className="grid gap-2 xl:grid-cols-2">
              <div><p className="mb-1 font-bold">Expected</p><ResultTable table={r.expected_table} /></div>
              <div><p className="mb-1 font-bold">Your output</p><ResultTable table={r.got_table} /></div>
            </div>
          ) : r.visible && r.input === undefined ? <p className="text-ink/60">Test failed: the page did not meet this requirement.</p> : r.visible ? (
            <>
              <p className="font-bold">Input</p><pre className="max-h-32 overflow-auto bg-offwhite p-2 whitespace-pre-wrap">{r.input}</pre>
              <div className="grid sm:grid-cols-2 gap-2">
                <div><p className="font-bold">Expected</p><pre className="max-h-32 overflow-auto bg-brand-green/10 p-2 whitespace-pre-wrap">{r.expected}</pre></div>
                <div><p className="font-bold">Your output</p><pre className="max-h-32 overflow-auto bg-brand-red/10 p-2 whitespace-pre-wrap">{r.got || "(no output)"}</pre></div>
              </div>
            </>
          ) : <p className="text-ink/60">Hidden test: input is not shown, like on real judges.</p>}
          {r.stderr && <pre className="max-h-32 overflow-auto bg-ink p-2 text-brand-red whitespace-pre-wrap">{r.stderr}</pre>}
        </div>
      )}
    </li>
  );
}

function CustomInput({ language, code, sampleInput, tid }) {
  const [open, setOpen] = useState(false);
  const [stdin, setStdin] = useState(sampleInput || "");
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState(null);
  const run = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/code/try", { language, code, stdin }, { timeout: 60000 });
      setOut(data);
    } catch (e) {
      toast.error(errMsg(e));
    }
    setBusy(false);
  };
  if (!open) return <button onClick={() => setOpen(true)} className="flex items-center gap-1.5 font-display text-sm font-semibold underline underline-offset-4" data-testid={`custom-input-toggle-${tid}`}><Terminal size={14} /> Try custom input</button>;
  const ok = out && !out.compile_error && out.status === "Finished";
  return (
    <div className="border-2 border-ink bg-white p-3 space-y-2" data-testid={`custom-input-${tid}`}>
      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 font-display text-sm font-bold"><Terminal size={14} /> Custom input</p>
        <button onClick={() => setOpen(false)} className="text-xs underline" data-testid={`custom-input-close-${tid}`}>Hide</button>
      </div>
      <textarea value={stdin} onChange={(e) => setStdin(e.target.value)} spellCheck={false} placeholder="Type stdin here" data-testid={`custom-input-stdin-${tid}`}
        className="min-h-[80px] w-full resize-y border-2 border-ink bg-offwhite p-2 font-mono text-xs outline-none" />
      <div className="flex flex-wrap items-center gap-3">
        <Button className="h-8 py-0 px-3 text-sm" onClick={run} disabled={busy || !code.trim()} data-testid={`custom-input-run-${tid}`}>{busy ? <Spinner /> : <Play size={14} />} Run with this input</Button>
        {out && !out.compile_error && <span className={`font-mono text-xs font-bold ${ok ? "text-brand-green" : "text-brand-red"}`} data-testid={`custom-input-status-${tid}`}>{out.status} · {out.time_ms}ms</span>}
      </div>
      {out?.compile_error && <pre className="max-h-40 overflow-auto bg-ink p-2 font-mono text-xs text-brand-red whitespace-pre-wrap">{out.compile_error}</pre>}
      {out && !out.compile_error && (
        <>
          <pre className="max-h-48 overflow-auto bg-ink p-2 font-mono text-xs text-white whitespace-pre-wrap" data-testid={`custom-input-stdout-${tid}`}>{out.stdout || "(no output)"}</pre>
          {out.stderr && <pre className="max-h-32 overflow-auto bg-brand-red/10 p-2 font-mono text-xs whitespace-pre-wrap">{out.stderr}</pre>}
        </>
      )}
    </div>
  );
}

export default function RunPanel({ context, refId, problemId = "", language, code, sampleInput = "" }) {
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const run = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/code/run", { context, ref_id: refId, problem_id: problemId, language, code }, { timeout: 180000 });
      setRes(data);
    } catch (e) {
      toast.error(errMsg(e));
    }
    setBusy(false);
  };
  const all = res && !res.compile_error && res.passed === res.total;
  return (
    <div className="space-y-3" data-testid={`run-panel-${problemId || "iv"}`}>
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="green" className="h-9 py-0 px-4 text-sm" onClick={run} disabled={busy || !code.trim()} data-testid={`run-btn-${problemId || "iv"}`}>
          {busy ? <Spinner /> : <Play size={15} />} {busy ? (res ? "Running…" : "Preparing tests…") : "Run tests"}
        </Button>
        {res && !res.compile_error && (
          <span className={`border-2 border-ink px-2 py-1 font-mono text-sm font-bold ${all ? "bg-brand-green" : "bg-brand-yellow"}`} data-testid={`run-summary-${problemId || "iv"}`}>
            {res.passed}/{res.total} passed
          </span>
        )}
        {!res && !busy && <span className="text-xs text-ink/55">Runs your code against samples, edge, boundary and stress tests.</span>}
      </div>
      <CustomInput language={language} code={code} sampleInput={sampleInput} tid={problemId || "iv"} />
      {res?.io_note && <p className="text-xs text-ink/60"><b>I/O:</b> {res.io_note}</p>}
      {res?.compile_error && <pre className="max-h-48 overflow-auto border-2 border-brand-red bg-ink p-3 font-mono text-xs text-brand-red whitespace-pre-wrap" data-testid="run-compile-error">{res.compile_error}</pre>}
      {res?.results?.length > 0 && <ul className="space-y-1.5">{res.results.map((r) => <TestRow key={r.id} r={r} />)}</ul>}
    </div>
  );
}
