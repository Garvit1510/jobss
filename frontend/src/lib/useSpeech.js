import { useCallback, useEffect, useRef, useState } from "react";

const SR = typeof window !== "undefined" ? window.SpeechRecognition || window.webkitSpeechRecognition : null;
export const TTS_SUPPORTED = typeof window !== "undefined" && "speechSynthesis" in window;
export const STT_SUPPORTED = !!SR;
export const speakable = (t) => (t || "").replace(/[*_`#>]/g, "").replace(/^\s*(?:\d+[.)]|[-•])\s*/gm, "").replace(/\s+/g, " ").trim();

function pickVoice() {
  const voices = window.speechSynthesis.getVoices();
  const en = voices.filter((v) => v.lang?.toLowerCase().startsWith("en"));
  const pref = ["Google UK English Male", "Google US English", "Microsoft Guy", "Microsoft Aria", "Microsoft Jenny", "Samantha", "Daniel"];
  for (const name of pref) {
    const v = en.find((x) => x.name.includes(name));
    if (v) return v;
  }
  return en[0] || voices[0] || null;
}

export function useSpeech({ onError } = {}) {
  const [speaking, setSpeaking] = useState(false);
  const [listening, setListening] = useState(false);
  const [finalText, setFinalText] = useState("");
  const [interim, setInterim] = useState("");
  const recRef = useRef(null);
  const wantRef = useRef(false);
  const finalRef = useRef("");
  const cancelRef = useRef(null);
  const timing = useRef({ first: 0, last: 0, pauses: [] });
  const [lastActivity, setLastActivity] = useState(0);
  const errRef = useRef(onError);
  errRef.current = onError;

  useEffect(() => {
    if (TTS_SUPPORTED) window.speechSynthesis.getVoices();
    return () => {
      wantRef.current = false;
      recRef.current?.abort();
      if (TTS_SUPPORTED) window.speechSynthesis.cancel();
    };
  }, []);

  const speak = useCallback((text) => new Promise((resolve) => {
    if (!TTS_SUPPORTED || !text) return resolve();
    const synth = window.speechSynthesis;
    synth.cancel();
    const parts = text.match(/[^.!?]+[.!?]*/g) || [text];
    const voice = pickVoice();
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      clearTimeout(guard);
      setSpeaking(false);
      resolve();
    };
    const words = text.split(/\s+/).length;
    const guard = setTimeout(finish, (words / 2.2) * 1000 + 4000);
    setSpeaking(true);
    setTimeout(() => {
      parts.forEach((p, i) => {
        const u = new SpeechSynthesisUtterance(p.trim());
        if (voice) u.voice = voice;
        u.rate = 1;
        if (i === parts.length - 1) {
          u.onend = finish;
          u.onerror = finish;
        }
        synth.speak(u);
      });
      if (synth.paused) synth.resume();
    }, 60);
    cancelRef.current = finish;
  }), []);

  const stopSpeaking = useCallback(() => {
    if (TTS_SUPPORTED) window.speechSynthesis.cancel();
    cancelRef.current?.();
    setSpeaking(false);
  }, []);

  const startListening = useCallback(() => {
    if (!SR || wantRef.current) return;
    const rec = new SR();
    rec.lang = "en-US";
    rec.continuous = true;
    rec.interimResults = true;
    rec.onresult = (e) => {
      const now = Date.now();
      const tm = timing.current;
      if (!tm.first) tm.first = now;
      else if (now - tm.last > 2000) tm.pauses.push((now - tm.last) / 1000);
      tm.last = now;
      setLastActivity(now);
      let inter = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalRef.current = `${finalRef.current} ${t}`.replace(/\s+/g, " ").trimStart();
        else inter += t;
      }
      setFinalText(finalRef.current);
      setInterim(inter);
    };
    rec.onerror = (e) => {
      if (e.error === "no-speech" || e.error === "aborted") return;
      wantRef.current = false;
      setListening(false);
      errRef.current?.(e.error === "not-allowed" || e.error === "service-not-allowed" ? "denied" : e.error);
    };
    rec.onend = () => {
      setInterim("");
      if (wantRef.current) {
        try { rec.start(); } catch { wantRef.current = false; setListening(false); }
      } else setListening(false);
    };
    recRef.current = rec;
    wantRef.current = true;
    try {
      rec.start();
      setListening(true);
    } catch {
      wantRef.current = false;
    }
  }, []);

  const stopListening = useCallback(() => {
    wantRef.current = false;
    recRef.current?.stop();
    setListening(false);
    setInterim("");
  }, []);

  const setText = useCallback((t) => {
    finalRef.current = t;
    setFinalText(t);
    if (!t) {
      timing.current = { first: 0, last: 0, pauses: [] };
      setLastActivity(0);
    }
  }, []);

  const getMetrics = useCallback((text) => {
    const tm = timing.current;
    if (!tm.first) return null;
    return {
      words: text.split(/\s+/).filter(Boolean).length,
      duration_sec: Math.max(0, (tm.last - tm.first) / 1000),
      long_pauses: tm.pauses.length,
      longest_pause_sec: tm.pauses.length ? Math.max(...tm.pauses) : 0,
    };
  }, []);

  return { speaking, listening, finalText, interim, lastActivity, speak, stopSpeaking, startListening, stopListening, setText, getMetrics };
}

export async function requestMic() {
  if (!navigator.mediaDevices?.getUserMedia) return "unsupported";
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((t) => t.stop());
    return "granted";
  } catch (e) {
    return e?.name === "NotAllowedError" || e?.name === "SecurityError" ? "denied" : "unavailable";
  }
}
