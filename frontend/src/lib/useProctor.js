import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import api from "./api";
import { bestMatch, detect, loadVision } from "./proctorVision";

export const FLAG_INFO = {
  tab_switch: { label: "Tab switch", text: "You left the test tab." },
  window_blur: { label: "Window lost focus", text: "Another window or app took focus." },
  fullscreen_exit: { label: "Exited fullscreen", text: "Stay in fullscreen during the test." },
  copy_paste: { label: "Copy / paste", text: "Copy, cut and paste are disabled in proctored mode." },
  camera_off: { label: "Camera off", text: "Your camera stopped or was taken by another app." },
  mic_off: { label: "Mic off", text: "Your microphone stopped or was muted." },
  camera_blocked: { label: "Camera blocked", text: "Your camera view looks covered, dark or blank." },
  loud_noise: { label: "Loud noise", text: "A sudden loud noise was detected." },
  background_voice: { label: "Talking detected", text: "Sustained talking or a second voice was detected." },
  phone_detected: { label: "Device in view", text: "A phone or another screen was seen on camera." },
  multiple_faces: { label: "Multiple people", text: "More than one person was seen on camera." },
  no_face: { label: "No face", text: "Your face was not visible to the camera." },
  different_person: { label: "Different person", text: "The face on camera does not match the registered candidate." },
  gaze_away: { label: "Looking away", text: "You looked away from the screen for a long time." },
};
export const MAX_TAB_SWITCHES = 5;
const COOLDOWN = 6000;

function isFs() {
  return !!(document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement || document.msFullscreenElement);
}

function requestFs() {
  const el = document.documentElement;
  const fn = el.requestFullscreen || el.webkitRequestFullscreen || el.mozRequestFullScreen || el.msRequestFullscreen;
  return fn ? fn.call(el).catch(() => {}) : Promise.resolve();
}

function exitFs() {
  const fn = document.exitFullscreen || document.webkitExitFullscreen || document.mozCancelFullScreen || document.msExitFullscreen;
  if (isFs() && fn) fn.call(document).catch(() => {});
}

function useMediaChecks(stream, flag, levelRef) {
  useEffect(() => {
    if (!stream) return undefined;
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const an = ctx.createAnalyser();
    an.fftSize = 512;
    ctx.createMediaStreamSource(stream).connect(an);
    const buf = new Uint8Array(an.fftSize);
    const video = Object.assign(document.createElement("video"), { muted: true, playsInline: true, srcObject: stream });
    video.play().catch(() => {});
    const canvas = Object.assign(document.createElement("canvas"), { width: 32, height: 24 });
    const c2d = canvas.getContext("2d", { willReadFrequently: true });
    let loud = 0, dark = 0, voice = 0;
    const audioTick = setInterval(() => {
      an.getByteTimeDomainData(buf);
      let sum = 0;
      for (const v of buf) sum += ((v - 128) / 128) ** 2;
      const rms = Math.sqrt(sum / buf.length);
      levelRef.current = Math.min(100, Math.round(rms * 400));
      // sudden loud noise
      loud = rms > 0.10 ? loud + 1 : 0;
      if (loud >= 5) { flag("loud_noise", `Loud (level ${levelRef.current})`); loud = 0; }
      // sustained talking / second voice: accumulate voice-level energy, decay on silence
      voice = rms > 0.045 ? voice + 1 : Math.max(0, voice - 1);
      if (voice >= 14) { flag("background_voice", "Sustained talking ~3.5s+"); voice = 6; }
    }, 250);
    const camTick = setInterval(() => {
      if (video.readyState < 2) return;
      c2d.drawImage(video, 0, 0, 32, 24);
      const d = c2d.getImageData(0, 0, 32, 24).data;
      const lums = [];
      let lum = 0;
      for (let i = 0; i < d.length; i += 4) {
        const l = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
        lums.push(l);
        lum += l;
      }
      const avg = lum / lums.length;
      const variance = lums.reduce((a, l) => a + (l - avg) ** 2, 0) / lums.length;
      // covered/blocked = very dark (shutter) OR nearly uniform frame (hand/paper over lens)
      dark = (avg < 16 || variance < 22) ? dark + 1 : 0;
      if (dark >= 3) { flag("camera_blocked", avg < 16 ? `Too dark (${Math.round(avg)}/255)` : "View looks covered/blank"); dark = 0; }
    }, 1500);
    const onCam = () => flag("camera_off");
    const onMic = () => flag("mic_off");
    const [vt] = stream.getVideoTracks();
    const [at] = stream.getAudioTracks();
    ["ended", "mute"].forEach((e) => { vt?.addEventListener(e, onCam); at?.addEventListener(e, onMic); });
    return () => {
      clearInterval(audioTick);
      clearInterval(camTick);
      ctx.close().catch(() => {});
      video.srcObject = null;
      ["ended", "mute"].forEach((e) => { vt?.removeEventListener(e, onCam); at?.removeEventListener(e, onMic); });
    };
  }, [stream, flag, levelRef]);
}

// Face/device/person detection loop (runs only after models are ready and a reference face is set).
function useVisionChecks(stream, active, visionReady, referenceRef, flag, setIdentityBreach) {
  useEffect(() => {
    if (!stream || !active || !visionReady) return undefined;
    let stopped = false, timer;
    let noFace = 0, miss = 0, gaze = 0, breach = false;
    const video = Object.assign(document.createElement("video"), { muted: true, playsInline: true, srcObject: stream });
    video.play().catch(() => {});
    const loop = async () => {
      if (stopped) return;
      try {
        if (video.readyState >= 2) {
          const r = await detect(video);
          if (r.devices.length) flag("phone_detected", r.devices.join(", "));
          if (r.faceCount >= 2 || r.personCount >= 2) flag("multiple_faces", `${Math.max(r.faceCount, r.personCount)} people visible`);
          if (r.faceCount === 0) { noFace += 1; if (noFace >= 2) { flag("no_face", "Face not visible"); noFace = 0; } } else noFace = 0;

          // identity: compare every visible face to the registered reference
          if (referenceRef.current) {
            const best = bestMatch(referenceRef.current, r.embeddings);
            if (best != null && best >= 0.5) {
              miss = 0;
              if (breach) { breach = false; setIdentityBreach(false); }
            } else if (r.embeddings.length && best != null && best < 0.45) {
              miss += 1;
              if (miss >= 2 && !breach) { breach = true; setIdentityBreach(true); flag("different_person", `Face match ${Math.round(best * 100)}%`); }
            }
          }

          // gaze: head turned away from the screen for a long stretch
          if (r.angle && r.faceCount === 1) {
            const yaw = Math.abs(r.angle.yaw || 0), pitch = r.angle.pitch || 0;
            const away = yaw > 0.5 || pitch < -0.4 || pitch > 0.55;
            gaze = away ? gaze + 1 : 0;
            if (gaze >= 3) { flag("gaze_away", yaw > 0.5 ? "Head turned sideways" : "Looking down/away"); gaze = 0; }
          } else gaze = 0;
        }
      } catch (e) { /* transient detect error */ }
      if (!stopped) timer = setTimeout(loop, 2500);
    };
    timer = setTimeout(loop, 1500);
    return () => { stopped = true; clearTimeout(timer); video.srcObject = null; };
  }, [stream, active, visionReady, referenceRef, flag, setIdentityBreach]);
}

function useFocusChecks(active, flag, setFullscreen) {
  useEffect(() => {
    if (!active) return undefined;
    const onVis = () => document.hidden && flag("tab_switch");
    const onBlur = () => setTimeout(() => !document.hidden && !isFs() && flag("window_blur"), 400);
    let fsTimer;
    const onFs = () => {
      clearTimeout(fsTimer);
      // debounce: fullscreenchange can fire a transient null before settling
      fsTimer = setTimeout(() => {
        const fs = isFs();
        setFullscreen(fs);
        if (!fs) flag("fullscreen_exit");
      }, 250);
    };
    const onClip = (e) => { e.preventDefault(); flag("copy_paste", e.type); };
    const onCtx = (e) => e.preventDefault();
    const onKey = (e) => {
      // F11/F12 re-enter fullscreen (F12 would otherwise open devtools)
      if (e.key === "F11" || e.key === "F12") {
        e.preventDefault();
        if (!isFs()) requestFs();
      }
    };
    const clip = ["copy", "cut", "paste"];
    document.addEventListener("visibilitychange", onVis);
    window.addEventListener("blur", onBlur);
    document.addEventListener("fullscreenchange", onFs);
    document.addEventListener("webkitfullscreenchange", onFs);
    document.addEventListener("contextmenu", onCtx);
    window.addEventListener("keydown", onKey);
    clip.forEach((t) => document.addEventListener(t, onClip));
    return () => {
      clearTimeout(fsTimer);
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener("blur", onBlur);
      document.removeEventListener("fullscreenchange", onFs);
      document.removeEventListener("webkitfullscreenchange", onFs);
      document.removeEventListener("contextmenu", onCtx);
      window.removeEventListener("keydown", onKey);
      clip.forEach((t) => document.removeEventListener(t, onClip));
    };
  }, [active, flag, setFullscreen]);
}

function grabFrame(v, w = 360) {
  if (!v || v.readyState < 2 || !v.videoWidth) return null;
  const c = Object.assign(document.createElement("canvas"), { width: w, height: Math.round((w * v.videoHeight) / v.videoWidth) });
  c.getContext("2d").drawImage(v, 0, 0, c.width, c.height);
  return c.toDataURL("image/jpeg", 0.72);
}

export default function useProctor() {
  const [stream, setStream] = useState(null);
  const [active, setActive] = useState(false);
  const [flags, setFlags] = useState([]);
  const [fullscreen, setFullscreen] = useState(isFs());
  const [visionReady, setVisionReady] = useState(false);
  const [visionError, setVisionError] = useState("");
  const [faceRegistered, setFaceRegistered] = useState(false);
  const [identityBreach, setIdentityBreach] = useState(false);
  const testId = useRef(null);
  const flagUrl = useRef(null);
  const last = useRef({});
  const quiet = useRef(false);
  const levelRef = useRef(0);
  const referenceRef = useRef(null);
  const ignore = useRef([]);
  const snapVideo = useRef(null);
  const refImg = useRef(null);
  useEffect(() => {
    if (!stream) return undefined;
    const v = Object.assign(document.createElement("video"), { muted: true, playsInline: true, srcObject: stream });
    v.play().catch(() => {});
    snapVideo.current = v;
    return () => { v.srcObject = null; snapVideo.current = null; };
  }, [stream]);
  // Evidence photos: registered face + a frame at every flag. Stored server-side, visible to admins only.
  const sendSnap = useCallback((type, detail, image) => {
    if (!image || !testId.current) return;
    const u = flagUrl.current || "";
    const kind = u.startsWith("/interview/") ? "interview" : u.startsWith("/accenture-mocks/") ? "accenture" : "oa";
    api.post("/proctor/snap", { kind, ref_id: testId.current, type, detail, image }).catch(() => {});
  }, []);

  const flag = useCallback((type, detail = "") => {
    const t = Date.now();
    if (!testId.current || quiet.current || ignore.current.includes(type)) return;
    if (type !== "tab_switch" && t - (last.current[type] || 0) < COOLDOWN) return;
    last.current[type] = t;
    setFlags((f) => [...f, { type, detail, at: new Date().toISOString() }]);
    toast.warning(`Proctoring flag: ${FLAG_INFO[type].label}`, { description: FLAG_INFO[type].text, id: `proctor-${type}` });
    api.post(flagUrl.current || `/mock-oa/${testId.current}/flag`, { type, detail }).catch(() => {});
    sendSnap(type, detail, grabFrame(snapVideo.current));
  }, [sendSnap]);

  const request = useCallback(async () => {
    const s = await navigator.mediaDevices.getUserMedia({ video: { width: 480, height: 360 }, audio: true });
    setStream(s);
    return s;
  }, []);

  const loadModels = useCallback(async () => {
    try {
      await loadVision();
      setVisionReady(true);
      setVisionError("");
    } catch (e) {
      setVisionError("Could not load the proctoring AI. Check your connection and retry.");
    }
  }, []);

  const registerFace = useCallback(async (s) => {
    const src = s || stream;
    if (!src) return { ok: false, msg: "Start the camera first." };
    const video = Object.assign(document.createElement("video"), { muted: true, playsInline: true, srcObject: src });
    await video.play().catch(() => {});
    await new Promise((r) => setTimeout(r, 500));
    let r;
    try { r = await detect(video); } catch { video.srcObject = null; return { ok: false, msg: "Face reading failed. Retry." }; }
    const shot = grabFrame(video, 480);
    video.srcObject = null;
    if (r.devices.length) return { ok: false, msg: `Remove from view: ${r.devices.join(", ")}.` };
    if (r.faceCount === 0) return { ok: false, msg: "No face detected. Center your face and improve lighting." };
    if (r.faceCount > 1 || r.personCount > 1) return { ok: false, msg: "More than one person detected. You must be alone." };
    if (!r.embedding) return { ok: false, msg: "Could not read your face clearly. Improve lighting and retry." };
    referenceRef.current = r.embedding;
    refImg.current = shot;
    setFaceRegistered(true);
    return { ok: true, msg: "Face registered." };
  }, [stream]);

  const enterFullscreen = useCallback(() => requestFs(), []);

  const begin = useCallback((id, flagPath, ignoreTypes = []) => {
    testId.current = id;
    ignore.current = ignoreTypes;
    flagUrl.current = flagPath || `/mock-oa/${id}/flag`;
    last.current = {};
    setFlags([]);
    setIdentityBreach(false);
    setFullscreen(isFs());
    setActive(true);
    sendSnap("registered", "Face registered before the session", refImg.current);
  }, [sendSnap]);

  const stop = useCallback((keepStream = false) => {
    testId.current = null;
    setActive(false);
    setIdentityBreach(false);
    if (!keepStream) {
      setStream((s) => { s?.getTracks().forEach((t) => t.stop()); return null; });
      referenceRef.current = null;
      setFaceRegistered(false);
      exitFs();
    }
  }, []);

  const withQuiet = useCallback((fn) => {
    quiet.current = true;
    try { return fn(); } finally { setTimeout(() => { quiet.current = false; }, 800); }
  }, []);

  useMediaChecks(stream, flag, levelRef);
  useVisionChecks(stream, active, visionReady, referenceRef, flag, setIdentityBreach);
  useFocusChecks(active, flag, setFullscreen);
  useEffect(() => () => stream?.getTracks().forEach((t) => t.stop()), [stream]);

  return { stream, active, flags, fullscreen, visionReady, visionError, faceRegistered, identityBreach, levelRef,
    request, loadModels, registerFace, enterFullscreen, begin, stop, withQuiet };
}

// 30s red lockout countdown when the registered candidate is not on camera; fires onTimeout to auto-submit.
export function useIdentityLockout(breach, onTimeout) {
  const [left, setLeft] = useState(null);
  const ref = useRef(onTimeout);
  ref.current = onTimeout;
  useEffect(() => {
    if (!breach) { setLeft(null); return undefined; }
    setLeft(30);
    const t = setInterval(() => {
      setLeft((x) => {
        if (x <= 1) { clearInterval(t); ref.current && ref.current(); return 0; }
        return x - 1;
      });
    }, 1000);
    return () => clearInterval(t);
  }, [breach]);
  return left;
}
