import React, { useCallback, useMemo, useState } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { keymap, EditorView } from "@codemirror/view";
import { indentWithTab } from "@codemirror/commands";
import { indentUnit } from "@codemirror/language";
import { python } from "@codemirror/lang-python";
import { javascript } from "@codemirror/lang-javascript";
import { cpp } from "@codemirror/lang-cpp";
import { java } from "@codemirror/lang-java";
import { html } from "@codemirror/lang-html";
import { css } from "@codemirror/lang-css";
import { sql, MySQL } from "@codemirror/lang-sql";
import { oneDark } from "@codemirror/theme-one-dark";

const LANG = { Python: python, JavaScript: javascript, "C++": cpp, Java: java, HTML: html, CSS: css, MySQL: () => sql({ dialect: MySQL }) };
const frame = EditorView.theme({ ".cm-scroller": { fontFamily: "'JetBrains Mono', monospace", minHeight: "340px" }, ".cm-content": { minHeight: "340px" } });
const PREFS_KEY = "joblens_editor_prefs";
export const FONT_MIN = 12;
export const FONT_MAX = 22;

export function useEditorPrefs() {
  const [prefs, setPrefs] = useState(() => {
    try {
      return { fontSize: 14, autoClose: true, ...JSON.parse(localStorage.getItem(PREFS_KEY) || "{}") };
    } catch {
      return { fontSize: 14, autoClose: true };
    }
  });
  const update = useCallback((patch) => setPrefs((p) => {
    const next = { ...p, ...patch };
    next.fontSize = Math.max(FONT_MIN, Math.min(FONT_MAX, next.fontSize));
    localStorage.setItem(PREFS_KEY, JSON.stringify(next));
    return next;
  }), []);
  return [prefs, update];
}

// Real code editor: language-aware auto-indent (Python ':' blocks, braces), Tab indents, Shift+Tab dedents.
export default function CodeEditor({ value, onChange, language = "Python", fontSize = 14, autoClose = true, testid = "code-editor" }) {
  const extensions = useMemo(() => [(LANG[language] || python)(), indentUnit.of(["HTML", "CSS"].includes(language) ? "  " : "    "), keymap.of([indentWithTab]), EditorView.lineWrapping, frame], [language]);
  const setup = useMemo(() => ({ lineNumbers: true, foldGutter: true, bracketMatching: true, closeBrackets: autoClose, autocompletion: true,
    highlightActiveLine: true, indentOnInput: true, tabSize: 4 }), [autoClose]);
  return (
    <div className="flex-1 border-3 border-ink" style={{ fontSize }} data-testid={testid}>
      <CodeMirror key={`${language}-${autoClose}`} value={value} onChange={onChange} theme={oneDark} extensions={extensions} basicSetup={setup}
        height="100%" minHeight="340px" maxHeight="70vh" placeholder={language === "MySQL" ? "-- Write your SQL query here" : language === "HTML" ? "<!-- Write your HTML here -->" : language === "CSS" ? "/* Write your CSS here */" : "// Write your solution here"} />
    </div>
  );
}
