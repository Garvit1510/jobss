import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { History, Keyboard, Mic, Play, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../lib/api";
import { timeAgo } from "../lib/format";
import { StepLoader } from "../components/Loaders";
import { Badge, Button, Card } from "../components/ui";
import InterviewChat from "../components/interview/InterviewChat";
import InterviewReport from "../components/interview/InterviewReport";
import VoiceInterview from "../components/interview/VoiceInterview";
import ProctorSetup from "../components/oa/ProctorSetup";
import useProctor from "../lib/useProctor";
import { useUIMode } from "../context/UIMode";
import { useSectors } from "../lib/careers";
import { STT_SUPPORTED, TTS_SUPPORTED } from "../lib/useSpeech";

const LEVELS = ["Auto", "Fresher", "Junior", "Mid", "Senior"];
const LEVEL_MAP = { Entry: "Fresher", Mid: "Mid", Senior: "Senior" };

function Setup({ onStart }) {
  const [params] = useSearchParams();
  const [f, setF] = useState({ role: "", company: "", interview_type: "Mixed", level: "Auto", job_id: "", job_description: "", num_questions: 5, proctored: false, sector: "", mode: STT_SUPPORTED && TTS_SUPPORTED ? "voice" : "text" });
  const [showJd, setShowJd] = useState(false);
  const sectors = useSectors();
  const sec = sectors.find((s) => s.id === f.sector);
  const styles = sec?.styles || ["Mixed", "Technical", "HR", "Behavioral"];
  useEffect(() => { const s = params.get("sector"); if (s) setF((x) => ({ ...x, sector: s })); }, [params]);
  useEffect(() => { if (!styles.includes(f.interview_type)) setF((x) => ({ ...x, interview_type: styles[0] })); }, [f.sector]);
  const [hist, setHist] = useState([]);
  useEffect(() => {
    api.get("/interview/history").then((r) => setHist(r.data.history));
    const jobId = params.get("job");
    if (jobId) {
      api.get(`/jobs/${jobId}`).then((r) => {
        const j = r.data.job || r.data;
        setF((x) => ({ ...x, role: j.title || x.role, company: j.company || "", job_id: jobId, level: LEVEL_MAP[j.level] || x.level, sector: j.sector && j.sector !== "other" ? j.sector : x.sector }));
      }).catch(() => {});
    } else {
      api.get("/resume").then((r) => r.data.resume && setF((x) => ({ ...x, role: x.role || r.data.resume.recommended_roles?.[0] || "" })));
    }
  }, [params]);
  return (
    <div className="mx-auto max-w-6xl px-4 md:px-8 py-12">
      <p className="eyebrow mb-2">Practice with a professional</p>
      <h1 className="text-4xl md:text-5xl font-bold">AI Interview</h1>
      <div className="mt-10 grid lg:grid-cols-[1fr_320px] gap-8">
        <Card className="p-7 space-y-6">
          <div>
            <p className="font-display font-bold mb-2">Your field</p>
            <select className="brutal-input" value={f.sector} onChange={(e) => setF({ ...f, sector: e.target.value })} data-testid="iv-sector-select">
              <option value="">Detect from role</option>
              {sectors.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            {sec && <p className="mt-2 text-xs text-ink/60" data-testid="iv-competencies">Assesses: {sec.competencies.join(" · ")}</p>}
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div><p className="font-display font-bold mb-2">Role</p><input className="brutal-input" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })} placeholder={sec ? `e.g. ${sec.roles[0]}` : "e.g. Sales Executive, Staff Nurse, Backend Engineer"} data-testid="iv-role-input" /></div>
            <div><p className="font-display font-bold mb-2">Company <span className="font-mono text-xs font-normal text-ink/50">(optional)</span></p><input className="brutal-input" value={f.company} onChange={(e) => setF({ ...f, company: e.target.value })} placeholder="e.g. Stripe" data-testid="iv-company-input" /></div>
          </div>
          {f.job_id && <p className="border-2 border-ink bg-brand-green/20 px-3 py-2 text-sm font-semibold" data-testid="iv-job-linked">Questions will be tailored to this job's description.</p>}
          <div className="flex flex-wrap items-end gap-6">
            <div>
              <p className="font-display font-bold mb-2">Your level</p>
              <div className="flex flex-wrap gap-1.5">{LEVELS.map((l) => (
                <button key={l} onClick={() => setF({ ...f, level: l })} data-testid={`iv-level-${l.toLowerCase()}`} className={`h-9 border-2 border-ink px-3 font-display text-sm font-semibold ${f.level === l ? "bg-ink text-white" : "bg-white"}`}>{l}</button>
              ))}</div>
            </div>
            {!f.job_id && <button onClick={() => setShowJd(!showJd)} className="h-9 border-2 border-dashed border-ink px-3 font-display text-sm font-semibold bg-white" data-testid="iv-jd-toggle">{showJd ? "Hide" : "+ Paste"} job description</button>}
          </div>
          {showJd && !f.job_id && <textarea className="brutal-input min-h-[110px] text-sm" maxLength={6000} value={f.job_description} onChange={(e) => setF({ ...f, job_description: e.target.value })} placeholder="Paste the job description so questions match the role (optional)" data-testid="iv-jd-input" />}
          <div>
            <p className="font-display font-bold mb-2">Mode</p>
            <div className="grid sm:grid-cols-2 gap-3">
              {[["voice", Mic, "Voice", "AI speaks, you answer out loud"], ["text", Keyboard, "Text", "Read and type your answers"]].map(([m, I, t, d]) => (
                <button key={m} onClick={() => setF({ ...f, mode: m })} aria-pressed={f.mode === m} data-testid={`iv-mode-${m}`}
                  className={`flex items-center gap-3 border-3 border-ink p-4 text-left transition-transform hover:-translate-y-0.5 ${f.mode === m ? "bg-brand-yellow shadow-brutalsm" : "bg-white"}`}>
                  <I size={22} /><span><span className="block font-display font-bold">{t}</span><span className="text-xs text-ink/60">{d}</span></span>
                </button>
              ))}
            </div>
            {f.mode === "voice" && !STT_SUPPORTED && <p className="mt-2 text-xs text-brand-red font-semibold" data-testid="iv-voice-unsupported">Voice answers need Chrome or Edge. You can still hear questions and type answers.</p>}
          </div>
          <div>
            <p className="font-display font-bold mb-2">Interview type</p>
            <div className="flex flex-wrap gap-2">{styles.map((t) => (
              <button key={t} onClick={() => setF({ ...f, interview_type: t })} data-testid={`iv-type-${t.toLowerCase().replace(/ /g, "-")}`} className={`border-3 border-ink px-4 py-2 font-display font-semibold ${f.interview_type === t ? "bg-ink text-white" : "bg-white"}`}>{t}</button>
            ))}</div>
          </div>
          <div>
            <p className="font-display font-bold mb-2">Questions: {f.num_questions}</p>
            <input type="range" min={3} max={10} value={f.num_questions} onChange={(e) => setF({ ...f, num_questions: Number(e.target.value) })} className="w-full accent-[#4D6FFF]" data-testid="iv-num-questions" />
          </div>
          <Button variant="primary" className="w-full py-3.5 text-lg" disabled={f.role.trim().length < 2} onClick={() => onStart(f)} data-testid="iv-start-btn"><Play size={18} /> Start interview</Button>
        </Card>
        <div className="space-y-6">
          <Card className={`p-6 ${f.proctored ? "bg-brand-purple" : "bg-brand-purple/30"}`} data-testid="iv-proctor-card">
            <div className="flex items-start justify-between gap-3">
              <h3 className="flex items-center gap-2 font-bold text-lg"><ShieldCheck size={18} /> Proctored mode</h3>
              <button role="switch" aria-checked={f.proctored} onClick={() => setF({ ...f, proctored: !f.proctored })} data-testid="iv-proctor-toggle"
                className={`relative h-7 w-12 shrink-0 border-3 border-ink transition-colors ${f.proctored ? "bg-brand-green" : "bg-white"}`}>
                <span className={`absolute top-0.5 h-4 w-4 bg-ink transition-transform ${f.proctored ? "translate-x-6" : "translate-x-0.5"}`} />
              </button>
            </div>
            <p className="mt-2 text-sm text-ink/70">Fullscreen + face registration + live AI monitoring like a real proctored interview. Your report gets an integrity score.</p>
            {f.proctored && <Badge tone="dark" className="mt-3">Camera + mic needed</Badge>}
          </Card>
          <Card className="p-6 bg-brand-purple/30">
            <h3 className="flex items-center gap-2 font-bold text-lg"><Mic size={18} /> Voice tips</h3>
            <ul className="mt-2 text-sm text-ink/70 list-disc pl-5 space-y-1">
              <li>Use Chrome or Edge and allow microphone access.</li>
              <li>Wait for the green "Listening" state, then speak.</li>
              <li>You can edit the transcript before pressing Submit.</li>
            </ul>
            <Badge tone="green" className="mt-3">Free · runs in your browser</Badge>
          </Card>
          <Card className="p-6" data-testid="iv-history">
            <h3 className="flex items-center gap-2 font-bold text-lg"><History size={18} /> Past interviews</h3>
            <ul className="mt-4 space-y-3">{hist.length ? hist.map((h) => (
              <li key={h.id} className="flex items-center justify-between gap-3 border-2 border-ink bg-offwhite p-3">
                <div className="min-w-0"><p className="font-semibold text-sm truncate">{h.role}{h.company ? ` · ${h.company}` : ""}</p><p className="font-mono text-[11px] text-ink/50">{h.interview_type} · {timeAgo(h.completed_at)}</p></div>
                <span className="font-display font-bold">{h.report?.overall_score}</span>
              </li>
            )) : <p className="text-sm text-ink/60">No interviews yet.</p>}</ul>
          </Card>
        </div>
      </div>
    </div>
  );
}

export default function AIInterview() {
  const [stage, setStage] = useState("setup");
  const [session, setSession] = useState(null);
  const [report, setReport] = useState(null);
  const [pending, setPending] = useState(null);
  const proctor = useProctor();
  const { stop, begin } = proctor;
  const { setFocusMode } = useUIMode();
  useEffect(() => () => stop(), [stop]);
  useEffect(() => {
    setFocusMode(stage === "check" || stage === "chat");
    return () => setFocusMode(false);
  }, [stage, setFocusMode]);
  const launch = async (cfg) => {
    setStage("loading");
    try {
      const { data } = await api.post("/interview/start", cfg);
      if (data.proctored) begin(data.session_id, `/interview/${data.session_id}/flag`, ["background_voice", "loud_noise"]);
      setSession({ ...data, cfg });
      setStage("chat");
    } catch (e) {
      toast.error(errMsg(e));
      stop();
      setStage("setup");
    }
  };
  const start = (cfg) => {
    if (!cfg.proctored) return launch(cfg);
    setPending(cfg);
    setStage("check");
  };
  const done = (r) => {
    stop();
    if (!r) return setStage("setup");
    setReport(r);
    setStage("report");
  };
  const exit = () => { stop(); setStage("setup"); };
  const p = session?.proctored ? proctor : null;
  if (stage === "check") return <ProctorSetup proctor={proctor} onReady={() => launch(pending)} onCancel={exit} />;
  if (stage === "loading") return <div className="px-4 py-24"><StepLoader title="Your interviewer is joining" steps={["Reading your resume", "Preparing the interview plan", "Writing the first question"]} /></div>;
  if (stage === "chat" && session.cfg.mode === "voice") return <VoiceInterview session={session} proctor={p} onDone={done} onExit={exit} />;
  if (stage === "chat") return <InterviewChat session={session} proctor={p} onDone={done} />;
  if (stage === "report") return <InterviewReport report={report} cfg={session.cfg} onRestart={() => setStage("setup")} />;
  return <Setup onStart={start} />;
}
