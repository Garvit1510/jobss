import React, { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Briefcase, Building2, ClipboardCheck, History, Search, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../lib/api";
import { timeAgo } from "../lib/format";
import { StepLoader } from "../components/Loaders";
import { Badge, Button, Card } from "../components/ui";
import OATest from "../components/oa/OATest";
import OAResult from "../components/oa/OAResult";
import ProctorSetup from "../components/oa/ProctorSetup";
import useProctor from "../lib/useProctor";
import { useSectors } from "../lib/careers";
import { useUIMode } from "../context/UIMode";

function CompanyPicker({ value, onPick }) {
  const [q, setQ] = useState("");
  const [list, setList] = useState([]);
  useEffect(() => {
    const t = setTimeout(() => api.get("/companies", { params: { q } }).then((r) => setList(r.data.companies)), 250);
    return () => clearTimeout(t);
  }, [q]);
  return (
    <div>
      <label className="relative block">
        <Search size={17} className="absolute left-4 top-1/2 -translate-y-1/2 text-ink/40" />
        <input className="brutal-input pl-11" placeholder="Search companies hiring now" value={q} onChange={(e) => setQ(e.target.value)} data-testid="oa-company-search" />
      </label>
      <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 max-h-[380px] overflow-y-auto p-1">
        {list.map((c) => (
          <button key={c.name} onClick={() => onPick(value === c.name ? "" : c.name)} data-testid={`oa-company-${c.name}`}
            className={`border-3 border-ink p-3 text-left transition-transform hover:-translate-y-0.5 ${value === c.name ? "bg-brand-yellow shadow-brutalsm" : "bg-white"}`}>
            <p className="flex items-center gap-1.5 font-display font-bold truncate"><Building2 size={14} className="shrink-0" /> {c.name}</p>
            <p className="font-mono text-[11px] text-ink/60">{c.jobs} open roles</p>
          </button>
        ))}
      </div>
    </div>
  );
}

function OACompanyPicker({ value, onPick }) {
  const [list, setList] = useState(null);
  useEffect(() => {
    api.get("/oa-companies").then((r) => setList(r.data.companies)).catch(() => setList([]));
  }, []);
  if (list === null) return <p className="text-sm text-ink/60">Loading companies…</p>;
  if (!list.length) return <p className="border-2 border-dashed border-ink/40 p-4 text-sm text-ink/60" data-testid="oa-cw-empty">No company-wise OAs yet. The admin adds them from real OA datasets.</p>;
  return (
    <div className="grid sm:grid-cols-2 gap-3 max-h-[380px] overflow-y-auto p-1">
      {list.map((c) => (
        <button key={c.id} onClick={() => onPick(value?.id === c.id ? null : c)} data-testid={`oa-cw-${c.id}`}
          className={`border-3 border-ink p-4 text-left transition-transform hover:-translate-y-0.5 ${value?.id === c.id ? "bg-brand-yellow shadow-brutalsm" : "bg-white"}`}>
          <p className="flex items-center justify-between gap-2"><span className="flex items-center gap-1.5 font-display font-bold truncate"><Building2 size={14} className="shrink-0" /> {c.name}</span><Badge tone="green" className="shrink-0">Real pattern</Badge></p>
          <p className="mt-1.5 text-xs text-ink/70 line-clamp-2">{c.description || c.summary}</p>
          {!!c.sections?.length && <p className="mt-2 font-mono text-[11px] text-ink/50 truncate">{c.sections.join(" · ")}{c.duration_minutes ? ` · ${c.duration_minutes} min` : ""}</p>}
        </button>
      ))}
    </div>
  );
}

function JobSetup({ jobId, onStart, onClear }) {
  const [job, setJob] = useState(null);
  const [difficulty, setDifficulty] = useState("Medium");
  const [proctored, setProctored] = useState(false);
  useEffect(() => {
    api.get(`/jobs/${jobId}`).then((r) => setJob(r.data.job || r.data)).catch(() => { toast.error("Job not found"); onClear(); });
  }, [jobId, onClear]);
  if (!job) return <div className="px-4 py-24"><StepLoader title="Loading the job" steps={["Reading the job posting"]} /></div>;
  return (
    <div className="mx-auto max-w-3xl px-4 md:px-8 py-12" data-testid="oa-job-setup">
      <p className="eyebrow mb-2">Mock OA for a job</p>
      <h1 className="text-4xl md:text-5xl font-bold">{job.title}</h1>
      <p className="mt-2 flex items-center gap-2 font-display text-lg font-semibold"><Briefcase size={18} /> {job.company}</p>
      <Card className="mt-8 p-7 space-y-6">
        <p className="border-2 border-ink bg-brand-green/20 px-3 py-2 text-sm font-semibold" data-testid="oa-job-note">Every question is built only from this job posting: its requirements, skills and responsibilities.</p>
        <div>
          <p className="font-display text-lg font-bold mb-3">Difficulty</p>
          <div className="flex gap-2">{["Easy", "Medium", "Hard"].map((d) => (
            <button key={d} onClick={() => setDifficulty(d)} data-testid={`oa-job-diff-${d.toLowerCase()}`} className={`border-3 border-ink px-4 py-2 font-display font-semibold ${difficulty === d ? "bg-ink text-white" : "bg-white"}`}>{d}</button>
          ))}</div>
        </div>
        <label className="flex items-center gap-3 font-display font-semibold">
          <input type="checkbox" checked={proctored} onChange={(e) => setProctored(e.target.checked)} className="h-5 w-5 accent-[#111]" data-testid="oa-job-proctor-toggle" />
          <ShieldCheck size={18} /> Proctored mode (camera + mic, fullscreen, integrity score)
        </label>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t-2 border-ink/10 pt-6">
          <button onClick={onClear} className="font-display text-sm font-bold underline" data-testid="oa-job-clear">Choose a different OA instead</button>
          <Button variant="primary" onClick={() => onStart({ job_id: job.id, difficulty, proctored })} data-testid="oa-job-generate-btn"><ClipboardCheck size={18} /> Generate OA for this job</Button>
        </div>
      </Card>
    </div>
  );
}

function Setup({ onStart }) {
  const [topic, setTopic] = useState("");
  const [company, setCompany] = useState("");
  const [source, setSource] = useState("hiring");
  const [oaCompany, setOaCompany] = useState(null);
  const [difficulty, setDifficulty] = useState("Medium");
  const [proctored, setProctored] = useState(false);
  const [hist, setHist] = useState([]);
  const sectors = useSectors();
  const [params] = useSearchParams();
  const [sector, setSector] = useState(params.get("sector") || "");
  const [type, setType] = useState("Full OA");
  const [duration, setDuration] = useState(40);
  const [count, setCount] = useState(15);
  const [skills, setSkills] = useState("");
  const sec = sectors.find((s) => s.id === sector);
  const pick = source === "company" ? oaCompany?.name : company;
  useEffect(() => {
    api.get("/mock-oa/history").then((r) => setHist(r.data.history));
  }, []);
  return (
    <div className="mx-auto max-w-6xl px-4 md:px-8 py-12">
      <p className="eyebrow mb-2">Practice under real conditions</p>
      <h1 className="text-4xl md:text-5xl font-bold">Mock Online Assessment</h1>
      <div className="mt-10 grid lg:grid-cols-[1fr_320px] gap-8">
        <Card className="p-7 space-y-7">
          <div>
            <p className="font-display text-lg font-bold mb-3">1. Your field</p>
            <select className="brutal-input" value={sector} onChange={(e) => { setSector(e.target.value); setType("Full OA"); }} data-testid="oa-sector-select">
              <option value="">Detect from role</option>
              {sectors.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            {sec && <p className="mt-2 text-xs text-ink/60" data-testid="oa-sector-sections">Tests: {sec.oa_sections.join(" · ")}{sec.coding ? " · Coding" : ""}</p>}
          </div>
          <div>
            <p className="font-display text-lg font-bold mb-3">2. Target role or exam</p>
            <input className="brutal-input" placeholder={sec ? `e.g. ${sec.roles.slice(0, 2).join(", ")}` : "e.g. Sales Executive, Staff Nurse, SSC CGL, SDE Intern"} value={topic} onChange={(e) => setTopic(e.target.value)} data-testid="oa-topic-input" />
            {sec && <div className="mt-2 flex flex-wrap gap-1.5">{sec.roles.slice(0, 10).map((r) => <button key={r} onClick={() => setTopic(r)} className="tag-chip hover:bg-brand-yellow" data-testid={`oa-role-${r}`}>{r}</button>)}</div>}
          </div>
          <div className="grid md:grid-cols-2 gap-5">
            <div>
              <p className="font-display text-lg font-bold mb-3">3. Assessment type</p>
              <select className="brutal-input" value={type} onChange={(e) => setType(e.target.value)} data-testid="oa-type-select">{(sec?.oa_types || ["Full OA"]).map((t) => <option key={t}>{t}</option>)}</select>
            </div>
            <div>
              <p className="font-display text-lg font-bold mb-3">4. Difficulty</p>
              <div className="flex gap-2">{["Easy", "Medium", "Hard"].map((d) => (
                <button key={d} onClick={() => setDifficulty(d)} data-testid={`oa-diff-${d.toLowerCase()}`} className={`border-3 border-ink px-4 py-2 font-display font-semibold ${difficulty === d ? "bg-ink text-white" : "bg-white"}`}>{d}</button>
              ))}</div>
            </div>
            <div>
              <p className="font-display font-bold mb-2">Duration: {duration} min</p>
              <input type="range" min={10} max={120} step={5} value={duration} onChange={(e) => setDuration(Number(e.target.value))} className="w-full accent-[#4D6FFF]" data-testid="oa-duration" />
            </div>
            <div>
              <p className="font-display font-bold mb-2">Questions: {count}</p>
              <input type="range" min={5} max={40} value={count} onChange={(e) => setCount(Number(e.target.value))} className="w-full accent-[#4D6FFF]" data-testid="oa-count" />
            </div>
          </div>
          <div>
            <p className="font-display font-bold mb-2">Focus skill areas <span className="font-mono text-xs font-normal text-ink/50">(optional, comma separated)</span></p>
            <input className="brutal-input" value={skills} onChange={(e) => setSkills(e.target.value)} placeholder="e.g. objection handling, CRM, negotiation" data-testid="oa-skills-input" />
          </div>
          <div>
            <p className="font-display text-lg font-bold mb-1">5. Company OA pattern <span className="font-mono text-xs font-normal text-ink/50">(optional)</span></p>
            <div className="my-3 inline-flex border-3 border-ink" role="tablist">
              {[["hiring", "Hiring now"], ["company", "Company-wise OA"]].map(([k, l]) => (
                <button key={k} role="tab" aria-selected={source === k} onClick={() => setSource(k)} data-testid={`oa-source-${k}`}
                  className={`h-9 px-4 font-display text-sm font-semibold ${source === k ? "bg-ink text-white" : "bg-white"}`}>{l}</button>
              ))}
            </div>
            <p className="text-sm text-ink/60 mb-3">{source === "hiring" ? "Companies actively hiring on JobLens right now." : "Built from real OA datasets, so the test mimics that company's actual OA."}</p>
            {source === "hiring" ? <CompanyPicker value={company} onPick={setCompany} /> : <OACompanyPicker value={oaCompany} onPick={setOaCompany} />}
          </div>
          <div className="flex flex-wrap items-center justify-between gap-4 border-t-2 border-ink/10 pt-6">
            <p className="text-sm" data-testid="oa-summary">{pick ? <>Pattern: <b>{pick}</b>{source === "company" && " (real dataset)"}</> : "General OA pattern"}{topic && <> · <b>{topic}</b></>}{proctored && <> · <b>Proctored</b></>}</p>
            <Button variant="primary" onClick={() => onStart({ topic, difficulty, proctored, sector, assessment_type: type, duration_minutes: duration, num_questions: count, skill_areas: skills.split(",").map((x) => x.trim()).filter(Boolean), ...(source === "company" ? { oa_company_id: oaCompany?.id || "" } : { company }) })} disabled={!topic.trim() && !pick && !sector} data-testid="oa-generate-btn"><ClipboardCheck size={18} /> Generate OA</Button>
          </div>
        </Card>
        <div className="space-y-6">
          <Card className={`p-6 ${proctored ? "bg-brand-purple" : "bg-brand-purple/30"}`} data-testid="oa-proctor-card">
            <div className="flex items-start justify-between gap-3">
              <h3 className="flex items-center gap-2 font-bold text-lg"><ShieldCheck size={18} /> Proctored mode</h3>
              <button role="switch" aria-checked={proctored} onClick={() => setProctored(!proctored)} data-testid="oa-proctor-toggle"
                className={`relative h-7 w-12 shrink-0 border-3 border-ink transition-colors ${proctored ? "bg-brand-green" : "bg-white"}`}>
                <span className={`absolute top-0.5 h-4 w-4 bg-ink transition-transform ${proctored ? "translate-x-6" : "translate-x-0.5"}`} />
              </button>
            </div>
            <p className="mt-2 text-sm text-ink/70">Face registration + live AI monitoring: detects phones/second screens, extra people, a different face, camera blocking, tab switches and fullscreen exits. You get an integrity score and a flag report.</p>
            {proctored && <Badge tone="dark" className="mt-3">Camera + mic needed</Badge>}
          </Card>
          <Card className="p-6" data-testid="oa-history">
            <h3 className="flex items-center gap-2 font-bold text-lg"><History size={18} /> Your attempts</h3>
            <ul className="mt-4 space-y-3">
              {hist.length ? hist.map((h) => (
                <li key={h.id} className="flex items-center justify-between gap-3 border-2 border-ink bg-offwhite p-3">
                  <div className="min-w-0"><p className="font-semibold text-sm truncate">{h.test?.title || h.topic}</p><p className="font-mono text-[11px] text-ink/50">{h.company || h.sector || "General"} · {timeAgo(h.created_at)}</p></div>
                  <span className="text-right"><span className="font-display font-bold">{h.result?.score_pct}%</span>{h.proctored && <span className="flex items-center gap-1 font-mono text-[10px] text-ink/60"><ShieldCheck size={11} /> {h.result?.proctoring?.integrity_score ?? "-"}</span>}</span>
                </li>
              )) : <p className="text-sm text-ink/60">No attempts yet.</p>}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}

export default function MockOA() {
  const [stage, setStage] = useState("setup");
  const [test, setTest] = useState(null);
  const [result, setResult] = useState(null);
  const [pending, setPending] = useState(null);
  const [params, setParams] = useSearchParams();
  const jobId = params.get("job");
  const clearJob = useCallback(() => setParams({}), [setParams]);
  const proctor = useProctor();
  const { stop, begin } = proctor;
  const { setFocusMode } = useUIMode();
  useEffect(() => () => stop(), [stop]);
  useEffect(() => {
    setFocusMode(stage === "test" || stage === "check");
    return () => setFocusMode(false);
  }, [stage, setFocusMode]);
  const generate = async (cfg) => {
    setStage("loading");
    try {
      const { data } = await api.post("/mock-oa/generate", cfg);
      setTest(data);
      if (data.proctored) begin(data.id);
      setStage("test");
    } catch (e) {
      toast.error(errMsg(e));
      stop();
      setStage("setup");
    }
  };
  const start = (cfg) => {
    if (!cfg.proctored) return generate(cfg);
    setPending(cfg);
    setStage("check");
  };
  const submit = async (payload) => {
    stop(true);
    setStage("grading");
    try {
      const { data } = await api.post("/mock-oa/submit", { test_id: test.id, ...payload });
      stop();
      setResult(data);
      setStage("result");
    } catch (e) {
      toast.error(errMsg(e));
      if (test.proctored) begin(test.id);
      setStage("test");
    }
  };
  if (stage === "loading") return <div className="px-4 py-24"><StepLoader title="Generating your OA" steps={["Studying the role and pattern", "Writing role-specific questions", "Adding scenarios and tasks", "Checking answers"]} /></div>;
  if (stage === "grading") return <div className="px-4 py-24"><StepLoader title="Evaluating your answers" steps={["Scoring objective answers", "Reviewing written answers and code", "Building your practice plan"]} /></div>;
  if (stage === "check") return <ProctorSetup proctor={proctor} onReady={() => generate(pending)} onCancel={() => { stop(); setStage("setup"); }} />;
  if (stage === "test") return <OATest data={test} onSubmit={submit} proctor={test.proctored ? proctor : null} />;
  if (stage === "result") return <OAResult result={result} title={test.test.title} onRestart={() => { setStage("setup"); setTest(null); setResult(null); }} />;
  if (jobId) return <JobSetup jobId={jobId} onStart={start} onClear={clearJob} />;
  return <Setup onStart={start} />;
}
