import React, { useCallback, useEffect, useRef, useState } from "react";
import { Mic, MicOff, Repeat, Send, Square, Timer } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";
import { requestMic, speakable, STT_SUPPORTED, TTS_SUPPORTED, useSpeech } from "../../lib/useSpeech";
import CodingRound from "./CodingRound";
import InterviewProctor from "./InterviewProctor";
import { Button, Progress, Spinner } from "../ui";
import VoiceOrb from "./VoiceOrb";
import VoiceTranscript from "./VoiceTranscript";
import AutoSubmitBar, { useAutoSubmit } from "./AutoSubmit";

function Elapsed() {
  const [s, setS] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setS((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, []);
  return <span className="flex items-center gap-1.5 font-mono font-bold" data-testid="voice-timer"><Timer size={16} /> {String(Math.floor(s / 60)).padStart(2, "0")}:{String(s % 60).padStart(2, "0")}</span>;
}

const MIC_MSG = {
  denied: "Microphone access was denied. Allow mic access in your browser's address bar, or type your answers below.",
  unsupported: "Your browser doesn't support speech recognition (use Chrome or Edge for voice). You can type your answers below.",
  unavailable: "No microphone was found. You can type your answers below.",
};

export default function VoiceInterview({ session, onDone, onExit, proctor = null }) {
  const [mic, setMic] = useState(STT_SUPPORTED ? "checking" : "unsupported");
  const [phase, setPhase] = useState("speaking");
  const [question, setQuestion] = useState(session.question);
  const [reaction, setReaction] = useState(session.reaction || "");
  const [coding, setCoding] = useState(null);
  const [idx, setIdx] = useState({ index: session.index, total: session.total });
  const [log, setLog] = useState([]);
  const [ending, setEnding] = useState(false);
  const micOk = useRef(false);
  const alive = useRef(true);
  const sp = useSpeech({
    onError: (e) => {
      if (e === "denied") {
        micOk.current = false;
        setMic("denied");
        setPhase("idle");
      } else setPhase("error");
    },
  });

  const askToken = useRef(0);
  const ask = useCallback(async (q, reaction = "") => {
    const my = ++askToken.current;
    sp.stopListening();
    setPhase("speaking");
    await sp.speak(speakable(`${reaction} ${q}`));
    if (!alive.current || my !== askToken.current) return;
    if (micOk.current) {
      sp.startListening();
      setPhase("listening");
    } else setPhase("idle");
  }, [sp]);

  useEffect(() => {
    alive.current = true;
    (async () => {
      const m = STT_SUPPORTED ? await requestMic() : "unsupported";
      micOk.current = m === "granted";
      setMic(m);
      ask(session.question, session.reaction);
    })();
    return () => { alive.current = false; };
  }, []);

  useEffect(() => {
    if (sp.listening) setPhase("listening");
    else if (phase === "listening") setPhase("idle");
  }, [sp.listening]);

  const answer = `${sp.finalText}${sp.interim ? ` ${sp.interim}` : ""}`.trim();
  const [auto, setAutoState] = useState(() => {
    try {
      return { on: true, ms: 3000, ...JSON.parse(localStorage.getItem("joblens_auto_submit") || "{}") };
    } catch {
      return { on: true, ms: 3000 };
    }
  });
  const setAuto = (v) => {
    setAutoState(v);
    localStorage.setItem("joblens_auto_submit", JSON.stringify(v));
  };
  const submitting = useRef(false);

  const advance = async (data, q, a) => {
    setLog((l) => [...l, { q, a }]);
    if (data.done) {
      setPhase("speaking");
      await sp.speak("Thank you, that concludes our interview. Your report is ready.");
      return onDone(data.report);
    }
    setIdx({ index: data.index, total: data.total });
    setQuestion(data.question);
    setReaction(data.reaction || "");
    if (data.coding) {
      setCoding(data);
      setPhase("idle");
      return;
    }
    if (alive.current) ask(data.question, data.reaction);
  };
  const submitCoding = async (payload) => {
    setPhase("processing");
    try {
      const { data } = await api.post("/interview/answer", { session_id: session.session_id, ...payload });
      setCoding(null);
      await advance(data, question, payload.answer);
    } catch (e) {
      toast.error(`${errMsg(e)} Your code is kept — press Submit to try again.`);
      setPhase("idle");
    }
  };

  const submit = async (retry = 0) => {
    const text = answer;
    if (submitting.current) return;
    if (!text) return toast.error("Say or type an answer first.");
    submitting.current = true;
    askToken.current++;
    sp.stopListening();
    sp.stopSpeaking();
    setPhase("processing");
    const metrics = sp.getMetrics(text);
    try {
      const { data } = await api.post("/interview/answer", { session_id: session.session_id, answer: text, metrics });
      submitting.current = false;
      sp.setText("");
      await advance(data, question, text);
    } catch (e) {
      submitting.current = false;
      if (retry < 1 && e?.response?.status === 503 && alive.current) {
        toast.message("AI is busy — retrying your answer in a few seconds…", { id: "iv-retry" });
        setTimeout(() => submitRef.current(1), 4000);
        return;
      }
      toast.error(`${errMsg(e)} Your answer is kept — press Submit to try again.`, { id: "iv-retry" });
      setPhase("idle");
    }
  };
  const submitRef = useRef(submit);
  submitRef.current = submit;
  const countdown = useAutoSubmit({ enabled: auto.on && phase === "listening", lastActivity: sp.lastActivity, answer, ms: auto.ms, onFire: () => submitRef.current() });

  const stop = async () => {
    if (!window.confirm("Stop the interview now? You'll get a report for the questions answered so far.")) return;
    alive.current = false;
    sp.stopListening();
    sp.stopSpeaking();
    setEnding(true);
    try {
      const { data } = await api.post("/interview/finish", { session_id: session.session_id });
      if (data.report) onDone(data.report);
      else onExit();
    } catch (e) {
      toast.error(errMsg(e));
      setEnding(false);
      alive.current = true;
    }
  };

  const toggleMic = () => {
    if (sp.listening) sp.stopListening();
    else if (micOk.current) { sp.stopSpeaking(); sp.startListening(); }
  };
  const busy = phase === "processing" || ending;

  return (
    <div className={`mx-auto px-4 md:px-8 py-10 ${coding ? "max-w-[1400px]" : "max-w-5xl"}`} data-testid="voice-interview">
      {proctor?.active && <InterviewProctor proctor={proctor} sessionId={session.session_id} onDone={onDone}
        beforeFinish={() => { alive.current = false; askToken.current++; sp.stopListening(); sp.stopSpeaking(); }} />}
      <div className="brutal-card p-4 flex flex-wrap items-center justify-between gap-4">
        <div><p className="font-display font-bold">{session.cfg.role}{session.cfg.company ? ` · ${session.cfg.company}` : ""}</p><p className="font-mono text-xs text-ink/60">Voice · {session.cfg.interview_type} interview</p></div>
        <Elapsed />
        <div className="w-40"><p className="font-mono text-xs text-right mb-1" data-testid="iv-progress">Q {idx.index}/{idx.total}</p><Progress value={(100 * idx.index) / idx.total} /></div>
      </div>
      {coding ? <div className="mt-6"><CodingRound q={coding} refId={session.session_id} voice busy={phase === "processing"} onSubmit={submitCoding} proctor={proctor} /></div> : <>
      {MIC_MSG[mic] && <p className="mt-6 border-3 border-ink bg-brand-yellow/40 p-4 text-sm font-medium" role="alert" data-testid="mic-warning">{MIC_MSG[mic]}</p>}
      {!TTS_SUPPORTED && <p className="mt-4 border-3 border-ink bg-brand-yellow/40 p-4 text-sm" role="alert">Your browser can't speak aloud — questions are shown as text.</p>}
      <div className="mt-8 grid lg:grid-cols-[1fr_1.2fr] gap-8">
        <div className="brutal-card p-6 flex flex-col items-center gap-6">
          <VoiceOrb phase={ending ? "processing" : phase} />
          <div className="w-full border-3 border-ink bg-offwhite p-4"><p className="eyebrow mb-2">Current question</p>{reaction && <p className="mb-1 text-sm text-ink/60" data-testid="voice-reaction">{reaction}</p>}<p className="font-display text-lg font-bold" data-testid="voice-question">{question}</p></div>
          <AutoSubmitBar auto={auto} setAuto={setAuto} countdown={countdown} />
          <div className="grid w-full grid-cols-2 gap-3">
            <Button onClick={() => ask(question)} disabled={busy} data-testid="voice-repeat-btn"><Repeat size={16} /> Repeat</Button>
            <Button variant={sp.listening ? "green" : "white"} onClick={toggleMic} disabled={busy || mic !== "granted"} aria-pressed={sp.listening} data-testid="voice-mic-btn">
              {sp.listening ? <Mic size={16} /> : <MicOff size={16} />} {sp.listening ? "Mic on" : "Mic off"}
            </Button>
            <Button variant="primary" onClick={() => submit()} disabled={busy || !answer} data-testid="voice-submit-btn">{phase === "processing" ? <Spinner /> : <Send size={16} />} Submit</Button>
            <Button variant="dark" onClick={stop} disabled={ending} data-testid="voice-stop-btn">{ending ? <Spinner /> : <Square size={16} />} Stop</Button>
          </div>
        </div>
        <VoiceTranscript log={log} answer={answer} interim={sp.interim} listening={sp.listening} disabled={busy}
          onEdit={(t) => { if (sp.listening) sp.stopListening(); sp.setText(t); }} onSubmit={() => submit()} />
      </div>
      </>}
    </div>
  );
}
