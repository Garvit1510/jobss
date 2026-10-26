import React, { useEffect, useRef, useState } from "react";
import { MonitorPlay, RotateCw, Trash2 } from "lucide-react";

const CONSOLE_HOOK = `<script>(function(){var s=function(l,a){try{parent.postMessage({__jl:1,level:l,text:Array.prototype.map.call(a,function(x){try{return typeof x==='object'?JSON.stringify(x):String(x)}catch(e){return String(x)}}).join(' ')},'*')}catch(e){}};
['log','info','warn','error'].forEach(function(l){var o=console[l];console[l]=function(){s(l,arguments);o&&o.apply(console,arguments)}});
window.addEventListener('error',function(e){s('error',[e.message+(e.lineno?' (line '+e.lineno+')':'')])});})();<\/script>`;

export function buildDoc(html = "", css = "", js = "", hook = true) {
  const style = `<style>${css}</style>`;
  const head = (hook ? CONSOLE_HOOK : "") + style;
  const script = `<script>${js}\n<\/script>`;
  if (/<html[\s>]/i.test(html)) {
    let d = /<head[^>]*>/i.test(html) ? html.replace(/<head[^>]*>/i, (m) => m + head) : html.replace(/<html[^>]*>/i, (m) => `${m}<head>${head}</head>`);
    return /<\/body>/i.test(d) ? d.replace(/<\/body>/i, `${script}</body>`) : d + script;
  }
  return `<!DOCTYPE html><html><head><meta charset="utf-8">${head}</head><body>${html}${script}</body></html>`;
}

const TONE = { error: "text-brand-red", warn: "text-brand-yellow", log: "text-white", info: "text-brand-blue" };

// Live server: re-renders the page (debounced) on every keystroke and captures console output.
export default function LivePreview({ html, css, js, tid = "web" }) {
  const frame = useRef(null);
  const [doc, setDoc] = useState(() => buildDoc(html, css, js));
  const [logs, setLogs] = useState([]);
  const [nonce, setNonce] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => { setLogs([]); setDoc(buildDoc(html, css, js)); }, 350);
    return () => clearTimeout(t);
  }, [html, css, js]);
  useEffect(() => {
    const on = (e) => {
      if (e.source !== frame.current?.contentWindow || !e.data?.__jl) return;
      setLogs((l) => [...l.slice(-199), { level: e.data.level, text: String(e.data.text).slice(0, 2000) }]);
    };
    window.addEventListener("message", on);
    return () => window.removeEventListener("message", on);
  }, []);
  return (
    <div className="border-3 border-ink" data-testid={`live-preview-${tid}`}>
      <div className="flex items-center gap-2 border-b-3 border-ink bg-ink px-3 py-2 text-white">
        <MonitorPlay size={15} />
        <p className="font-display text-sm font-bold">Live preview</p>
        <span className="flex items-center gap-1.5 font-mono text-[11px] text-brand-green"><span className="h-2 w-2 animate-pulse rounded-full bg-brand-green" /> live</span>
        <button onClick={() => { setLogs([]); setNonce((n) => n + 1); }} className="ml-auto flex items-center gap-1 font-mono text-[11px] hover:text-brand-yellow" data-testid={`live-preview-reload-${tid}`}><RotateCw size={12} /> Reload</button>
      </div>
      <iframe key={nonce} ref={frame} title="Live preview" srcDoc={doc} sandbox="allow-scripts allow-modals allow-forms" className="block h-[340px] w-full bg-white" data-testid={`live-preview-frame-${tid}`} />
      <div className="border-t-3 border-ink bg-[#1e1f24]">
        <div className="flex items-center justify-between px-3 py-1.5">
          <p className="font-mono text-[11px] font-bold text-white/70">Console {logs.length ? `(${logs.length})` : ""}</p>
          <button onClick={() => setLogs([])} className="text-white/50 hover:text-white" aria-label="Clear console" data-testid={`live-console-clear-${tid}`}><Trash2 size={12} /></button>
        </div>
        <div className="max-h-28 overflow-y-auto px-3 pb-2 font-mono text-[11px]" data-testid={`live-console-${tid}`}>
          {logs.length ? logs.map((l, i) => <p key={i} className={`whitespace-pre-wrap border-b border-white/5 py-0.5 ${TONE[l.level] || "text-white"}`}>{l.level === "error" ? "✕ " : "› "}{l.text}</p>)
            : <p className="text-white/35">console.log output appears here</p>}
        </div>
      </div>
    </div>
  );
}
