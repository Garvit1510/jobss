import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";
import useProctor from "../../lib/useProctor";
import ProctorSetup from "../oa/ProctorSetup";
import ProctorMonitor from "../oa/ProctorMonitor";
import { Spinner } from "../ui";

const RULES = [
  "Only you may be visible — no other people in the camera view.",
  "No phone, tablet, second screen, books or notes in view.",
  "Keep your face centered and the camera uncovered and well lit.",
  "Stay in fullscreen; leaving fullscreen locks the screen until you return (the timer keeps running).",
  "Tab switches, focus loss, copy/paste, camera/mic and face events are recorded for admin review. They do not auto-submit the round and are not treated as proof of cheating.",
  "One system check per mock: your camera, mic and registered face stay active across all rounds while you stay in this tab.",
];
const ROUND_PATH = /^\/accenture-mocks\/[^/]+\/(behavioural|gamified|technical|coding)/;
const Shared = createContext(null);
const Done = createContext(null);

// One proctor instance for all Accenture rounds, so the camera/mic stream and registered face carry over between rounds of a mock.
export function AccProctorProvider({ children }) {
  const proctor = useProctor();
  const owner = useRef(null);
  const { pathname } = useLocation();
  const { stop } = proctor;
  useEffect(() => { if (!ROUND_PATH.test(pathname)) { owner.current = null; stop(); } }, [pathname, stop]);
  return <Shared.Provider value={{ proctor, owner }}>{children}</Shared.Provider>;
}

// Round pages call this once their attempt is finished so monitoring stops (camera stays on for the next round).
export function useProctorDone(finished) {
  const done = useContext(Done);
  useEffect(() => { if (finished && done) done(); }, [finished, done]);
}

const live = (s) => !!s?.getVideoTracks().some((t) => t.readyState === "live") && !!s?.getAudioTracks().some((t) => t.readyState === "live");

// Policy comes from the shared mock OA config; each round's session is linked server-side to that round attempt.
export default function AccentureProctorGate({ mockId, round, preview, children }) {
  const { proctor, owner } = useContext(Shared);
  const { begin, stop, withQuiet } = proctor;
  const nav = useNavigate();
  const [phase, setPhase] = useState("loading");
  const [mode, setMode] = useState("off");
  const link = useCallback(async (status, reason = "") => {
    await api.post(`/accenture-mocks/${mockId}/${round}/start`, { preview });
    const s = proctor.stream;
    const checks = { camera: !!s?.getVideoTracks().length, mic: !!s?.getAudioTracks().length, face: proctor.faceRegistered, fullscreen: !!document.fullscreenElement, reused_check: owner.current === mockId };
    return (await api.post(`/accenture-mocks/${mockId}/proctor/session`, { round, preview, status, reason, checks })).data;
  }, [mockId, round, preview, proctor.stream, proctor.faceRegistered, owner]);
  const ready = useCallback(async () => {
    try {
      const d = await link("active");
      owner.current = mockId;
      begin(d.session_id, `/accenture-mocks/proctor/${d.session_id}/flag`, d.ignore_flags || []);
      setPhase("ready");
    } catch (e) { toast.error(`Proctoring could not start: ${errMsg(e)}`); setPhase("setup"); }
  }, [link, begin, mockId, owner]);
  useEffect(() => {
    let on = true;
    (async () => {
      try {
        const { data } = await api.get(`/accenture-mocks/${mockId}/oa-config`, { params: { preview } });
        if (!on) return;
        const m = data.proctoring.mode;
        setMode(m);
        if (m === "off" || (round === "coding" && data.code_runner.disabled_for_demo && !preview)) return setPhase("ready");
        const st = await api.get(`/accenture-mocks/${mockId}/${round}`).then((r) => r.data).catch(() => null);
        if (!on) return;
        if (st?.finished_at && !preview) return setPhase("ready");
        if (owner.current === mockId && live(proctor.stream) && proctor.faceRegistered) return setPhase("relink");
        if (owner.current !== mockId) { owner.current = null; stop(); }
        setPhase("setup");
      } catch { if (on) setPhase("ready"); } // the round page itself reports access errors
    })();
    return () => { on = false; };
  }, [mockId, round, preview]);
  useEffect(() => { if (phase === "relink") ready(); }, [phase, ready]);
  useEffect(() => {
    if (!proctor.active) return undefined;
    const orig = window.confirm;
    window.confirm = (msg) => withQuiet(() => orig(msg)); // dialogs must not raise focus flags
    return () => { window.confirm = orig; };
  }, [proctor.active, withQuiet]);
  useEffect(() => () => stop(true), [stop]);
  const cancel = async () => {
    stop();
    owner.current = null;
    if (mode !== "optional") return nav("/accenture-mocks");
    if (!window.confirm("Continue this round without proctoring? It will be reported as not proctored.")) return;
    try { await link("declined", "Candidate continued without proctoring"); setPhase("ready"); } catch (e) { toast.error(errMsg(e)); }
  };
  const done = useCallback(() => stop(true), [stop]);
  if (phase === "loading" || phase === "relink") return <div className="flex flex-col items-center gap-2 py-24"><Spinner />{phase === "relink" && <p className="text-sm">Reusing your system check…</p>}</div>;
  if (phase === "setup") return <div data-testid={`acc-proctor-setup-${round}`}><ProctorSetup proctor={proctor} onReady={ready} onCancel={cancel} rules={RULES} /></div>;
  return (
    <Done.Provider value={done}>
      {proctor.active && <ProctorMonitor proctor={proctor} identityCountdown={null} />}
      {children}
    </Done.Provider>
  );
}

export function ProctoredRound({ round, children }) {
  const { mockId } = useParams();
  const preview = new URLSearchParams(useLocation().search).get("preview") === "1";
  return <AccentureProctorGate key={`${mockId}-${round}-${preview}`} mockId={mockId} round={round} preview={preview}>{children}</AccentureProctorGate>;
}
