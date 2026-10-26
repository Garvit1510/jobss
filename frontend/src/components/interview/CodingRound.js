import React, { useEffect, useState } from "react";
import { Camera, Code2, Mic, MicOff, SkipForward } from "lucide-react";
import { speakable, STT_SUPPORTED, useSpeech } from "../../lib/useSpeech";
import { Badge, Button, Card } from "../ui";
import { CamPreview } from "../oa/ProctorMedia";
import CodeWorkspace from "../code/CodeWorkspace";
import { pickLang, useCodeDrafts } from "../../lib/codeTemplates";

function Permission({ onAllow, denied, onSkip }) {
  return (
    <Card className="p-7 bg-brand-yellow/30" data-testid="coding-permission">
      <Badge tone="dark">Coding round unlocked</Badge>
      <h2 className="mt-3 text-2xl font-bold">You're doing well, so let's write some code.</h2>
      <p className="mt-2 text-sm text-ink/70">Your camera stays on in a corner and the mic picks up your spoken walkthrough, like a real live-coding interview.</p>
      {denied && <p className="mt-4 border-2 border-brand-red bg-brand-red/10 p-3 text-sm" data-testid="coding-permission-error">Camera or mic access was blocked. Allow it from the address bar and try again, or skip this round.</p>}
      <div className="mt-6 flex flex-wrap gap-3">
        <Button variant="primary" onClick={onAllow} data-testid="coding-allow-btn"><Camera size={17} /> Allow camera & mic</Button>
        <Button onClick={onSkip} data-testid="coding-skip-btn"><SkipForward size={17} /> Skip coding round</Button>
      </div>
    </Card>
  );
}

function Walkthrough({ sp, talk, onSkip }) {
  return (
    <div className="mt-3 border-3 border-ink bg-white p-3" data-testid="coding-walkthrough-box">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="font-display font-bold">Talk me through your approach</p>
        <div className="flex gap-2">
          {STT_SUPPORTED && (
            <Button variant={sp.listening ? "green" : "white"} className="h-9 py-0 px-3 text-sm" onClick={() => (sp.listening ? sp.stopListening() : sp.startListening())} data-testid="coding-mic-btn">
              {sp.listening ? <Mic size={15} /> : <MicOff size={15} />} {sp.listening ? "Listening" : "Speak"}
            </Button>
          )}
          <Button className="h-9 py-0 px-3 text-sm" onClick={onSkip} data-testid="coding-skip-round-btn"><SkipForward size={15} /> Skip</Button>
        </div>
      </div>
      <textarea value={talk} onChange={(e) => { if (sp.listening) sp.stopListening(); sp.setText(e.target.value); }} data-testid="coding-walkthrough"
        placeholder="Explain your idea, edge cases and complexity (speak or type)" className="mt-2 min-h-[70px] w-full resize-y border-2 border-ink bg-offwhite p-2 text-sm outline-none" />
    </div>
  );
}

export default function CodingRound({ q, refId, onSubmit, busy, voice = false, proctor = null }) {
  const proctored = !!proctor?.active && !!proctor.stream;
  const [stream, setStream] = useState(null);
  const [denied, setDenied] = useState(false);
  const drafts = useCodeDrafts(pickLang(q.coding.language));
  const lang = drafts.langOf("iv");
  const code = drafts.codeOf("iv");
  const setCode = (v) => drafts.setCode("iv", v);
  const setLang = (l) => drafts.setLang("iv", l);
  const sp = useSpeech();
  useEffect(() => () => stream?.getTracks().forEach((t) => t.stop()), [stream]);
  useEffect(() => {
    if (proctored && voice) sp.speak(speakable(q.question || q.text));
  }, []);

  const allow = async () => {
    try {
      setStream(await navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240 }, audio: true }));
      setDenied(false);
      if (voice) sp.speak(speakable(q.question || q.text));
    } catch {
      setDenied(true);
    }
  };
  const talk = `${sp.finalText}${sp.interim ? ` ${sp.interim}` : ""}`.trim();
  const submit = () => {
    sp.stopListening();
    sp.stopSpeaking();
    const s = drafts.submission("iv");
    onSubmit({ answer: talk || "(No walkthrough given)", code: s.code || code, language: s.code ? s.lang : lang });
  };
  const skip = () => {
    sp.stopListening();
    sp.stopSpeaking();
    onSubmit({ answer: "(Candidate skipped the coding round)", code: "", language: "" });
  };

  if (!proctored && !stream) return <Permission onAllow={allow} denied={denied} onSkip={skip} />;
  return (
    <div className="space-y-4" data-testid="coding-round">
      <p className="eyebrow flex items-center gap-2"><Code2 size={14} /> Live coding round <Badge tone="yellow">{q.difficulty}</Badge></p>
      <CodeWorkspace problem={q.coding} context="interview" refId={refId} language={lang} onLanguage={setLang} code={code} onCode={setCode}
        onSubmit={submit} submitLabel="Submit solution" submitBusy={busy} footer={<Walkthrough sp={sp} talk={talk} onSkip={skip} />} />
      {!proctored && (
        <div className="fixed bottom-4 left-4 z-50 w-44 brutal-card p-1.5" data-testid="coding-cam">
          <div className="relative">
            <CamPreview stream={stream} className="w-full aspect-[4/3] border-2 border-ink" testid="coding-cam-video" />
            <span className="absolute left-1.5 top-1.5 flex items-center gap-1 bg-brand-red px-1.5 py-0.5 font-mono text-[10px] font-bold text-white"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-white" /> LIVE</span>
          </div>
        </div>
      )}
    </div>
  );
}
