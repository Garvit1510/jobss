import React, { useState } from "react";
import { Play } from "lucide-react";
import { toast } from "sonner";
import { errMsg } from "../../lib/api";
import { Button, Spinner } from "../ui";
import CodeEditor, { useEditorPrefs } from "./CodeEditor";
import ResultTable from "./ResultTable";
import { SQL_NOTE, tryQuery } from "./SqlWorkspace";
import { EMPTY_WEB, WebEditor } from "./WebWorkspace";

const SQL_START = "CREATE TABLE employees (id INT, name VARCHAR(50), dept VARCHAR(30), salary DECIMAL(10,2));\nINSERT INTO employees VALUES (1, 'Asha', 'Eng', 90000), (2, 'Ravi', 'Eng', 75000), (3, 'Meera', 'Sales', 60000);\n\nSELECT dept, COUNT(*) AS people, AVG(salary) AS avg_salary\nFROM employees\nGROUP BY dept\nORDER BY avg_salary DESC;\n";

export function SqlPlayground({ tid }) {
  const [q, setQ] = useState(SQL_START);
  const [out, setOut] = useState(null);
  const [busy, setBusy] = useState(false);
  const [prefs] = useEditorPrefs();
  const run = async () => {
    setBusy(true);
    try { setOut(await tryQuery(q)); } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };
  return (
    <div className="flex flex-col gap-3" data-testid={`sql-playground-${tid}`}>
      <p className="font-mono text-[11px] text-ink/55">{SQL_NOTE}. Create tables, insert rows and query them; the last SELECT is shown. Scratchpad only, not graded.</p>
      <div className="flex"><CodeEditor value={q} onChange={setQ} language="MySQL" fontSize={prefs.fontSize} autoClose={prefs.autoClose} testid={`sql-playground-editor-${tid}`} /></div>
      <div className="border-3 border-ink bg-paper p-3 min-h-[80px]">
        {busy ? <p className="flex items-center gap-2 font-mono text-sm"><Spinner /> Running…</p>
          : out ? (out.error ? <pre className="bg-ink p-3 font-mono text-xs text-brand-red whitespace-pre-wrap" data-testid={`sql-playground-error-${tid}`}>{out.error}</pre> : <ResultTable table={out} testid={`sql-playground-output-${tid}`} empty="No rows" />)
          : <p className="font-mono text-sm text-ink/55">Press <b>Run SQL</b> to see the result table.</p>}
      </div>
      <div className="flex justify-end"><Button variant="green" onClick={run} disabled={busy || !q.trim()} data-testid={`sql-playground-run-${tid}`}><Play size={16} /> Run SQL</Button></div>
    </div>
  );
}

export function WebPlayground({ tid }) {
  const [v, setV] = useState(EMPTY_WEB);
  return (
    <div data-testid={`web-playground-${tid}`}>
      <p className="mb-2 font-mono text-[11px] text-ink/55">HTML / CSS / JS scratchpad with a live preview. Not graded for this problem.</p>
      <WebEditor value={v} onChange={setV} tid={`pg-${tid}`} />
    </div>
  );
}
