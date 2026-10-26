import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Bookmark, ChevronLeft, ChevronRight, Clock, Eraser, Lock, Send } from "lucide-react";
import { toast } from "sonner";
import { Button } from "../ui";
import ProctorMonitor from "./ProctorMonitor";
import CodeWorkspace from "../code/CodeWorkspace";
import SqlWorkspace from "../code/SqlWorkspace";
import WebWorkspace, { EMPTY_WEB } from "../code/WebWorkspace";
import { useCodeDrafts } from "../../lib/codeTemplates";
import { MAX_TAB_SWITCHES } from "../../lib/useProctor";

function Timer({ seconds, onEnd, label = "" }) {
  const [left, setLeft] = useState(seconds);
  useEffect(() => {
    const t = setInterval(() => setLeft((l) => l - 1), 1000);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    if (left <= 0) onEnd();
  }, [left, onEnd]);
  const m = Math.max(0, Math.floor(left / 60)), s = Math.max(0, left % 60);
  return (
    <span className={`flex items-center gap-2 border-3 border-ink px-3 py-2 font-mono text-base font-bold ${left < 120 ? "bg-brand-red text-white animate-pulse" : "bg-brand-yellow"}`} data-testid="oa-timer">
      <Clock size={17} /> {label && <span className="hidden text-xs font-semibold sm:inline">{label}</span>} {String(m).padStart(2, "0")}:{String(s).padStart(2, "0")}
    </span>
  );
}

export default function OATest({ data, onSubmit, proctor }) {
  const t = data.test;
  const [answers, setAnswers] = useState({});
  const [review, setReview] = useState({});
  const [cur, setCur] = useState(0);
  const started = useRef(Date.now());
  const sent = useRef(false);
  const starterOf = useCallback((id, l) => (t.coding || []).find((c) => c.id === id)?.starter_code?.[l], [t.coding]);
  const { langOf, codeOf, setCode, setLang, submission, resetCode } = useCodeDrafts("Python", starterOf);
  const [sqlAns, setSqlAns] = useState({});
  const [webAns, setWebAns] = useState({});
  const webOf = useCallback((c) => webAns[c.id] || { ...EMPTY_WEB, ...(c.starter || {}) }, [webAns]);

  // flatten every MCQ (across sections) + coding problems into one ordered list, shown one at a time
  const items = useMemo(() => {
    const list = [];
    const progs = [["code", t.coding, "Coding"], ["sql", t.sql, "SQL"], ["web", t.web, "Web Dev"]];
    const order = t.blueprint?.sections?.length ? t.blueprint.sections.map((b) => b.name) : null;
    const inSec = (name) => (sec) => !order || sec === name;
    (order || [null]).forEach((name) => {
      t.sections.filter((s) => inSec(name)(s.name)).forEach((s) => s.questions.forEach((q) => list.push({ type: "mcq", section: s.name, q })));
      progs.forEach(([type, arr, def]) => (arr || []).filter((c) => inSec(name)(c.section || def)).forEach((c) => list.push({ type, section: c.section || def, c })));
    });
    return list;
  }, [t]);
  const sectionNames = useMemo(() => [...new Set(items.map((i) => i.section))], [items]);
  const item = items[cur];
  const isAnswered = useCallback((it) => {
    if (it.type === "mcq") return answers[it.q.id] != null && answers[it.q.id] !== "";
    if (it.type === "sql") return !!sqlAns[it.c.id]?.trim();
    if (it.type === "web") return !!webAns[it.c.id];
    return !!submission(it.c.id).code;
  }, [answers, submission, sqlAns, webAns]);
  const secs = useMemo(() => (t.blueprint?.sectional ? t.blueprint.sections.filter((b) => items.some((i) => i.section === b.name)) : null), [t, items]);
  const [secIdx, setSecIdx] = useState(0);
  const curSec = secs?.[secIdx];
  const answeredCount = items.filter(isAnswered).length;

  const finish = useCallback((reason = "") => {
    if (sent.current) return;
    sent.current = true;
    const subs = (t.coding || []).map((c) => [c.id, submission(c.id)]);
    const written = Object.fromEntries(subs.filter(([, s]) => s.code).map(([id, s]) => [id, s.code]));
    const languages = Object.fromEntries(subs.map(([id, s]) => [id, s.lang]));
    const web = Object.fromEntries((t.web || []).filter((c) => webAns[c.id]).map((c) => [c.id, webAns[c.id]]));
    onSubmit({ answers, code: written, languages, sql: sqlAns, web, time_taken_sec: Math.round((Date.now() - started.current) / 1000), auto_reason: typeof reason === "string" ? reason : "" });
  }, [answers, submission, onSubmit, t.coding, t.web, sqlAns, webAns]);

  const tabs = proctor ? proctor.flags.filter((f) => f.type === "tab_switch").length : 0;
  useEffect(() => {
    if (tabs >= MAX_TAB_SWITCHES) finish(`Auto-submitted after ${tabs} tab switches`);
  }, [tabs, finish]);

  // Identity breach: a face that isn't the registered candidate -> red lockout + 30s to return, else auto-submit.
  const [idLeft, setIdLeft] = useState(null);
  const finishRef = useRef(finish);
  finishRef.current = finish;
  const breach = !!proctor?.identityBreach;
  useEffect(() => {
    if (!breach) { setIdLeft(null); return undefined; }
    setIdLeft(30);
    const int = setInterval(() => {
      setIdLeft((x) => {
        if (x <= 1) { clearInterval(int); finishRef.current("Auto-submitted: registered candidate not present"); return 0; }
        return x - 1;
      });
    }, 1000);
    return () => clearInterval(int);
  }, [breach]);

  const confirmSubmit = () => {
    const ask = () => window.confirm(`Submit your assessment?\n\nAnswered ${answeredCount} of ${items.length}.`);
    if (proctor ? proctor.withQuiet(ask) : ask()) finish();
  };

  const allowed = (i) => !curSec || items[i]?.section === curSec.name;
  const go = (i) => { const n = Math.max(0, Math.min(items.length - 1, i)); if (allowed(n)) setCur(n); };
  const jumpSection = (name) => { const i = items.findIndex((it) => it.section === name); if (i >= 0) go(i); };
  const key = item?.type === "mcq" ? item.q.id : item?.c.id;
  const toNextSection = useCallback(() => {
    const nxt = secs[secIdx + 1];
    setSecIdx(secIdx + 1);
    setCur(items.findIndex((it) => it.section === nxt.name));
  }, [secs, secIdx, items]);
  const nextSection = () => {
    const ask = () => window.confirm(`Submit the "${curSec.name}" section and move on?\n\nYou can't come back to this section.`);
    if (proctor ? proctor.withQuiet(ask) : ask()) toNextSection();
  };
  const onTimeUp = useCallback(() => {
    if (!secs || secIdx >= secs.length - 1) return finish("Time is up");
    toast.info(`Time is up for ${secs[secIdx].name}. Moving to the next section.`);
    toNextSection();
  }, [secs, secIdx, finish, toNextSection]);
  const isLast = cur === items.length - 1;
  const lastInSec = !!curSec && !isLast && items[cur + 1]?.section !== item?.section;
  const advance = () => (isLast ? confirmSubmit() : lastInSec ? nextSection() : go(cur + 1));
  const advanceLabel = isLast ? "Submit & Finish" : lastInSec ? "Submit section" : "Submit & Next";
  const toggleReview = () => setReview((r) => ({ ...r, [key]: !r[key] }));
  const clearResponse = () => { if (item.type === "mcq") setAnswers((a) => { const n = { ...a }; delete n[item.q.id]; return n; }); };

  return (
    <div className="min-h-[calc(100vh-67px)] bg-offwhite">
      {proctor?.active && <ProctorMonitor proctor={proctor} identityCountdown={idLeft} />}

      {/* Assessment control bar */}
      <div className="sticky top-[67px] z-30 border-b-3 border-ink bg-paper">
        <div className="mx-auto max-w-6xl px-4 md:px-8 py-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <select value={item?.section || ""} onChange={(e) => jumpSection(e.target.value)} data-testid="oa-section-select"
              className="h-10 border-3 border-ink bg-white px-3 font-display text-sm font-bold outline-none">
              {sectionNames.map((n) => <option key={n} value={n} disabled={!!curSec && n !== curSec.name}>{n}{curSec && n !== curSec.name ? " (locked)" : ""}</option>)}
            </select>
            <p className="font-mono text-xs text-ink/60 truncate" data-testid="oa-answered-count">Answered {answeredCount}/{items.length}</p>
          </div>
          <div className="flex items-center gap-2">
            <Button onClick={() => go(cur - 1)} disabled={cur === 0} data-testid="oa-prev-top"><ChevronLeft size={16} /> Prev</Button>
            {lastInSec ? <Button onClick={nextSection} data-testid="oa-next-section-top">Next section <ChevronRight size={16} /></Button>
              : <Button onClick={() => go(cur + 1)} disabled={isLast} data-testid="oa-next-top">Next <ChevronRight size={16} /></Button>}
            {curSec ? <Timer key={secIdx} seconds={curSec.minutes * 60} onEnd={onTimeUp} label={`${curSec.name} ·`} />
              : <Timer seconds={(t.duration_minutes || 45) * 60} onEnd={onTimeUp} />}
            <Button variant="primary" onClick={confirmSubmit} data-testid="oa-submit-btn"><Send size={16} /> Submit</Button>
          </div>
        </div>
        {/* Question palette */}
        <div className="mx-auto max-w-6xl px-4 md:px-8 pb-3 flex items-center gap-2">
          <button onClick={() => go(cur - 1)} className="brutal-btn bg-white px-2 py-2 shrink-0" aria-label="Previous question"><ChevronLeft size={16} /></button>
          <div className="flex items-center gap-1.5 overflow-x-auto py-1" data-testid="oa-palette">
            {items.map((it, i) => {
              const k = it.type === "mcq" ? it.q.id : it.c.id;
              const done = isAnswered(it);
              const locked = !allowed(i);
              const active = i === cur;
              const marked = review[k];
              return (
                <button key={k} onClick={() => go(i)} data-testid={`oa-palette-${i}`} disabled={locked} title={locked ? "Section locked" : it.section}
                  className={`relative h-9 w-9 shrink-0 border-2 border-ink font-mono text-sm font-bold transition-colors
                    ${locked ? "cursor-not-allowed opacity-30 bg-white" : active ? "bg-ink text-white" : done ? "bg-brand-green text-ink" : "bg-white text-ink hover:bg-brand-yellow/50"}`}>
                  {locked ? <Lock size={12} className="mx-auto" /> : i + 1}
                  {marked && <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full border border-ink bg-brand-yellow" />}
                </button>
              );
            })}
          </div>
          <button onClick={() => go(cur + 1)} className="brutal-btn bg-white px-2 py-2 shrink-0" aria-label="Next question"><ChevronRight size={16} /></button>
        </div>
      </div>

      {/* One question at a time */}
      <div className={`mx-auto px-4 md:px-8 py-8 ${item && item.type !== "mcq" ? "max-w-[1400px]" : "max-w-6xl"}`}>
        {curSec && <p className="mb-4 font-mono text-xs text-ink/60" data-testid="oa-section-progress">Section {secIdx + 1} of {secs.length}: <b>{curSec.name}</b> · {curSec.minutes} min · earlier sections are locked</p>}
        {(t.pattern_note || t.note) && cur === 0 && <p className="mb-6 border-2 border-ink bg-white px-4 py-2 text-sm" data-testid="oa-pattern-note">{t.pattern_note}{t.note && <span className="block text-xs text-ink/60">{t.note}</span>}</p>}
        {item?.type === "mcq" ? (
          <div className="grid lg:grid-cols-2 gap-6">
            <div className="brutal-card p-6" data-testid={`oa-question-${item.q.id}`}>
              <div className="flex items-center justify-between gap-3 border-b-2 border-ink/10 pb-3">
                <p className="font-display text-xl font-bold">Question {cur + 1}</p>
                <button onClick={toggleReview} data-testid="oa-review-toggle"
                  className={`flex items-center gap-1.5 border-2 border-ink px-3 py-1.5 font-display text-xs font-bold transition-colors ${review[key] ? "bg-brand-yellow" : "bg-white hover:bg-offwhite"}`}>
                  <Bookmark size={14} className={review[key] ? "fill-ink" : ""} /> {review[key] ? "Marked" : "Revisit later"}
                </button>
              </div>
              <p className="mt-5 whitespace-pre-line text-[15px] leading-relaxed" data-testid="oa-question-text">{item.q.question}</p>
            </div>
            <div className="brutal-card p-6">
              <div className="flex items-center justify-between gap-3 border-b-2 border-ink/10 pb-3">
                <p className="font-display text-lg font-bold">{(item.q.type || "mcq") === "mcq" ? "Select an option" : item.q.type === "numeric" ? "Your numeric answer" : "Your written answer"}</p>
                <button onClick={clearResponse} disabled={answers[item.q.id] == null || answers[item.q.id] === ""} data-testid="oa-clear-response"
                  className="flex items-center gap-1.5 font-display text-xs font-bold text-brand-red disabled:text-ink/30">
                  <Eraser size={14} /> Clear response
                </button>
              </div>
              {(item.q.type || "mcq") === "mcq" ? <div className="mt-4 space-y-3">
                {(item.q.options || []).map((o, k) => {
                  const picked = answers[item.q.id] === k;
                  return (
                    <button key={k} onClick={() => setAnswers({ ...answers, [item.q.id]: k })} data-testid={`oa-option-${item.q.id}-${k}`}
                      className={`flex w-full items-center gap-3 border-2 border-ink px-4 py-3 text-left text-sm transition-colors ${picked ? "bg-brand-blue text-white" : "bg-white hover:bg-brand-yellow/30"}`}>
                      <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 ${picked ? "border-white" : "border-ink"}`}>
                        {picked && <span className="h-2 w-2 rounded-full bg-white" />}
                      </span>
                      <span><span className="font-mono font-bold mr-1.5">{String.fromCharCode(65 + k)}.</span>{o}</span>
                    </button>
                  );
                })}
              </div> : item.q.type === "numeric" ? <div className="mt-4">
                <div className="flex items-center gap-2">
                  <input inputMode="decimal" value={answers[item.q.id] ?? ""} onChange={(e) => setAnswers({ ...answers, [item.q.id]: e.target.value.replace(/[^0-9.,\-]/g, "") })}
                    placeholder="Type a number" className="brutal-input font-mono text-lg" data-testid={`oa-numeric-${item.q.id}`} />
                  {item.q.unit && <span className="font-mono text-sm font-bold">{item.q.unit}</span>}
                </div>
                <p className="mt-2 font-mono text-xs text-ink/50">Numbers only. Small rounding differences are accepted.</p>
              </div> : <div className="mt-4">
                <textarea value={answers[item.q.id] ?? ""} onChange={(e) => setAnswers({ ...answers, [item.q.id]: e.target.value.slice(0, 4000) })}
                  placeholder="Write your answer. Structure it clearly; it is graded against a rubric." className="brutal-input min-h-[260px] text-sm leading-relaxed" data-testid={`oa-written-${item.q.id}`} />
                <p className="mt-1 text-right font-mono text-xs text-ink/50">{String(answers[item.q.id] ?? "").length}/4000</p>
              </div>}
            </div>
          </div>
        ) : item?.type === "sql" ? (
          <div data-testid={`oa-sql-${item.c.id}`}>
            <SqlWorkspace key={item.c.id} problem={item.c} refId={data.id} value={sqlAns[item.c.id] || ""} onChange={(v) => setSqlAns((a) => ({ ...a, [item.c.id]: v }))}
              submitLabel={advanceLabel} onSubmit={advance} />
          </div>
        ) : item?.type === "web" ? (
          <div data-testid={`oa-web-${item.c.id}`}>
            <WebWorkspace key={item.c.id} problem={item.c} refId={data.id} value={webOf(item.c)} onChange={(v) => setWebAns((a) => ({ ...a, [item.c.id]: v }))}
              submitLabel={advanceLabel} onSubmit={advance} />
          </div>
        ) : item ? (
          <div data-testid={`oa-coding-${item.c.id}`}>
            <CodeWorkspace key={item.c.id} problem={item.c} context="oa" refId={data.id} problemId={item.c.id}
              language={langOf(item.c.id)} onLanguage={(l) => setLang(item.c.id, l)}
              code={codeOf(item.c.id)} onCode={(v) => setCode(item.c.id, v)} onReset={() => resetCode(item.c.id)}
              submitLabel={advanceLabel} onSubmit={advance} />
          </div>
        ) : null}

        {/* Footer navigation (MCQs only; coding has its own Submit & Next) */}
        {item?.type === "mcq" && <div className="mt-8 flex items-center justify-between gap-3">
          <Button onClick={() => go(cur - 1)} disabled={cur === 0} data-testid="oa-prev-btn"><ChevronLeft size={17} /> Previous</Button>
          <span className="font-mono text-xs text-ink/50">{cur + 1} / {items.length}</span>
          {isLast
            ? <Button variant="primary" onClick={confirmSubmit} data-testid="oa-submit-footer"><Send size={16} /> Submit assessment</Button>
            : lastInSec ? <Button variant="primary" onClick={nextSection} data-testid="oa-next-section-btn">Submit section <ChevronRight size={17} /></Button>
            : <Button variant="primary" onClick={() => go(cur + 1)} data-testid="oa-next-btn">Save & Next <ChevronRight size={17} /></Button>}
        </div>}
      </div>
    </div>
  );
}
