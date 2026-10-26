import React, { useEffect, useState } from "react";
import { Camera, CheckCircle2, Loader2, Maximize, Mic, ScanFace, ShieldCheck, XCircle } from "lucide-react";
import { Button, Card } from "../ui";
import { CamPreview, MicMeter } from "./ProctorMedia";
import { MAX_TAB_SWITCHES } from "../../lib/useProctor";

const RULES = [
  "Only you may be visible — no other people in the camera view.",
  "No phone, tablet, second screen, books or notes in view.",
  "Keep your face centered and the camera uncovered and well lit.",
  "Stay in fullscreen the whole time. Leaving fullscreen locks the test.",
  `Switching tabs is flagged. ${MAX_TAB_SWITCHES} tab switches auto-submit the test.`,
  "Copy, cut, paste and right-click are disabled.",
  "Sit somewhere quiet — talking or someone prompting you is flagged.",
];

const Check = ({ ok, pending, label, testid }) => (
  <li className="flex items-center gap-2 text-sm" data-testid={testid}>
    {pending ? <Loader2 size={18} className="animate-spin text-ink/50" /> : ok ? <CheckCircle2 size={18} className="text-brand-green" /> : <XCircle size={18} className="text-brand-red" />} {label}
  </li>
);

export default function ProctorSetup({ proctor, onReady, onCancel, rules = RULES }) {
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [regMsg, setRegMsg] = useState(null);
  const [regBusy, setRegBusy] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const s = proctor.stream;
  const { visionReady, visionError, faceRegistered } = proctor;

  useEffect(() => { proctor.loadModels(); }, [proctor]);

  const allow = async () => {
    setBusy(true);
    setErr("");
    try {
      await proctor.request();
    } catch (e) {
      setErr(e?.name === "NotAllowedError" ? "Camera/mic permission was denied. Allow it from the address bar and try again." : "No camera or microphone was found on this device.");
    }
    setBusy(false);
  };

  const register = async () => {
    setRegBusy(true);
    setRegMsg(null);
    const res = await proctor.registerFace();
    setRegMsg(res);
    setRegBusy(false);
  };

  const canStart = !!s?.getVideoTracks().length && !!s?.getAudioTracks().length && visionReady && faceRegistered && agreed;
  const go = async () => {
    await proctor.enterFullscreen();
    onReady();
  };

  return (
    <div className="mx-auto max-w-5xl px-4 md:px-8 py-12" data-testid="proctor-setup">
      <p className="eyebrow mb-2">Proctored mode</p>
      <h1 className="text-4xl font-bold flex items-center gap-3"><ShieldCheck size={34} /> System check</h1>
      <div className="mt-8 grid md:grid-cols-[1fr_1fr] gap-6">
        <Card className="p-5">
          {s ? <CamPreview stream={s} className="w-full aspect-video border-3 border-ink" /> :
            <div className="flex aspect-video w-full items-center justify-center border-3 border-dashed border-ink/40 bg-offwhite"><Camera size={40} className="text-ink/30" /></div>}
          <p className="mt-4 flex items-center gap-2 font-display font-semibold text-sm"><Mic size={15} /> Mic level, say something</p>
          <div className="mt-2"><MicMeter levelRef={proctor.levelRef} /></div>
          {s && (
            <div className="mt-4">
              <Button onClick={register} disabled={!visionReady || regBusy} data-testid="proctor-register-btn">
                {regBusy ? <Loader2 size={16} className="animate-spin" /> : <ScanFace size={16} />} {faceRegistered ? "Re-capture my face" : "Register my face"}
              </Button>
              {regMsg && <p className={`mt-3 border-2 p-3 text-sm ${regMsg.ok ? "border-brand-green bg-brand-green/10" : "border-brand-red bg-brand-red/10"}`} data-testid="proctor-register-msg">{regMsg.msg}</p>}
            </div>
          )}
          {err && <p className="mt-4 border-2 border-brand-red bg-brand-red/10 p-3 text-sm" data-testid="proctor-error">{err}</p>}
        </Card>
        <Card className="p-6 flex flex-col">
          <ul className="space-y-2">
            <Check ok={!!s?.getVideoTracks().length} label="Camera connected" testid="proctor-check-camera" />
            <Check ok={!!s?.getAudioTracks().length} label="Microphone connected" testid="proctor-check-mic" />
            <Check ok={!!document.documentElement.requestFullscreen} label="Fullscreen supported" testid="proctor-check-fullscreen" />
            <Check ok={visionReady} pending={!visionReady && !visionError} label="Proctoring AI ready (face & device detection)" testid="proctor-check-ai" />
            <Check ok={faceRegistered} label="Your face registered" testid="proctor-check-face" />
          </ul>
          {visionError && <p className="mt-3 border-2 border-brand-red bg-brand-red/10 p-3 text-sm flex items-center justify-between gap-3" data-testid="proctor-ai-error">{visionError}<button onClick={proctor.loadModels} className="underline font-semibold">Retry</button></p>}
          <p className="mt-6 font-display font-bold">Rules</p>
          <ul className="mt-2 space-y-1.5 text-sm text-ink/75 list-disc pl-5">{rules.map((r) => <li key={r}>{r}</li>)}</ul>
          <label className="mt-5 flex items-start gap-2.5 text-sm cursor-pointer" data-testid="proctor-agree">
            <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} className="mt-0.5 h-4 w-4 accent-brand-green" data-testid="proctor-agree-checkbox" />
            <span>I have closed all other tabs, apps and notifications, I am alone in the room, and no phone or second screen is near me.</span>
          </label>
          <div className="mt-auto pt-6 flex flex-wrap gap-3">
            {!s ? <Button variant="primary" onClick={allow} disabled={busy} data-testid="proctor-allow-btn"><Camera size={17} /> Allow camera & mic</Button> :
              <Button variant="primary" onClick={go} disabled={!canStart} data-testid="proctor-start-btn"><Maximize size={17} /> Enter fullscreen & start</Button>}
            <Button onClick={onCancel} data-testid="proctor-cancel-btn">Back</Button>
          </div>
          {s && !canStart && <p className="mt-3 font-mono text-[11px] text-ink/50" data-testid="proctor-start-hint">Register your face, wait for the AI to load, and tick the box to start.</p>}
        </Card>
      </div>
    </div>
  );
}
