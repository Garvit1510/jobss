import { useCallback, useEffect, useState } from "react";
import api from "./api";

export const RUN_LANGS = ["Python", "JavaScript", "C++", "Java"];

export const TEMPLATES = {
  Python: "import sys\n\ndef main():\n    data = sys.stdin.read().split()\n    # parse input and print the answer\n\nmain()\n",
  JavaScript: "const data = require('fs').readFileSync(0, 'utf8').trim().split(/\\s+/);\n// parse input and print the answer with console.log\n",
  "C++": "#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    ios::sync_with_stdio(false);\n    cin.tie(nullptr);\n    // read input and print the answer\n    return 0;\n}\n",
  Java: "import java.util.*;\nimport java.io.*;\n\npublic class Main {\n    public static void main(String[] args) throws IOException {\n        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));\n        // read input and print the answer\n    }\n}\n",
};

export const PLAYGROUND_LANGS = ["MySQL", "HTML/CSS/JS"];
const withPlay = (l) => [...l, ...PLAYGROUND_LANGS.map((name) => ({ name, available: true, playground: true }))];

export const pickLang = (hint) => RUN_LANGS.find((l) => l.toLowerCase() === (hint || "").toLowerCase()) || "Python";

const norm = (s) => (s || "").replace(/\s+/g, "");
const TEMPLATE_KEYS = new Set(Object.values(TEMPLATES).map(norm));
export const isWritten = (code) => !!code?.trim() && !TEMPLATE_KEYS.has(norm(code));

// Per-problem, per-language drafts: switching language loads that language's boilerplate (or your earlier draft in it).
// starterOf(id, lang) may return problem-specific boilerplate; falls back to the generic template.
export function useCodeDrafts(initialLang = "Python", starterOf = null) {
  const [state, setState] = useState({});
  const langOf = useCallback((id) => state[id]?.lang || initialLang, [state, initialLang]);
  const starter = useCallback((id, l) => (starterOf && starterOf(id, l)) || TEMPLATES[l], [starterOf]);
  const codeOf = useCallback((id) => {
    const l = langOf(id);
    return state[id]?.drafts?.[l] ?? starter(id, l);
  }, [state, langOf, starter]);
  const setCode = useCallback((id, v) => setState((x) => {
    const cur = x[id] || { lang: initialLang, drafts: {} };
    return { ...x, [id]: { ...cur, drafts: { ...cur.drafts, [cur.lang]: v } } };
  }), [initialLang]);
  const setLang = useCallback((id, l) => setState((x) => ({ ...x, [id]: { drafts: {}, ...x[id], lang: l } })), []);
  // what gets graded: the current language's code, or another language's draft if only that one was written
  const submission = useCallback((id) => {
    const l = langOf(id);
    const d = state[id]?.drafts || {};
    const pick = [l, ...Object.keys(d)].find((k) => isWritten(d[k]) && norm(d[k]) !== norm(starter(id, k)));
    return pick ? { lang: pick, code: d[pick] } : { lang: l, code: "" };
  }, [state, langOf, starter]);
  const resetCode = useCallback((id) => setState((x) => {
    const cur = x[id] || { lang: initialLang, drafts: {} };
    const drafts = { ...cur.drafts };
    delete drafts[cur.lang];
    return { ...x, [id]: { ...cur, drafts } };
  }), [initialLang]);
  return { langOf, codeOf, setCode, setLang, submission, resetCode };
}

let langCache = null;
// Languages the judge can run right now (Java depends on the server having a JDK).
export function useRunLangs() {
  const [langs, setLangs] = useState(withPlay(langCache || RUN_LANGS.map((name) => ({ name, available: true }))));
  useEffect(() => {
    if (langCache) return;
    api.get("/code/languages").then((r) => { langCache = r.data.languages; setLangs(withPlay(langCache)); }).catch(() => {});
  }, []);
  return langs;
}
