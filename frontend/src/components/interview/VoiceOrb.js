import React from "react";
import { motion } from "framer-motion";
import { AlertTriangle, Ear, Loader2, MicOff, Volume2 } from "lucide-react";

const STATES = {
  speaking: { icon: Volume2, text: "Interviewer is speaking…", tone: "bg-brand-yellow" },
  listening: { icon: Ear, text: "Listening — speak your answer", tone: "bg-brand-green" },
  processing: { icon: Loader2, text: "Evaluating your answer…", tone: "bg-brand-purple", spin: true },
  idle: { icon: MicOff, text: "Mic paused — speak with the mic button or type", tone: "bg-white" },
  error: { icon: AlertTriangle, text: "Voice error — type your answer instead", tone: "bg-brand-red text-white" },
};

export default function VoiceOrb({ phase }) {
  const s = STATES[phase] || STATES.idle;
  const I = s.icon;
  const active = phase === "speaking" || phase === "listening";
  return (
    <div className="flex flex-col items-center gap-4" role="status" aria-live="polite" data-testid="voice-state">
      <div className="relative flex h-36 w-36 items-center justify-center">
        {active && [0, 1, 2].map((i) => (
          <motion.span key={i} className={`absolute inset-0 border-3 border-ink ${s.tone}`} style={{ borderRadius: "50%" }}
            initial={{ scale: 0.8, opacity: 0.6 }} animate={{ scale: 1.5, opacity: 0 }} transition={{ duration: 1.8, repeat: Infinity, delay: i * 0.6 }} />
        ))}
        <motion.div animate={active ? { scale: [1, 1.06, 1] } : { scale: 1 }} transition={{ duration: 1.2, repeat: active ? Infinity : 0 }}
          className={`relative z-10 flex h-28 w-28 items-center justify-center rounded-full border-3 border-ink shadow-brutal ${s.tone}`}>
          <I size={40} className={s.spin ? "animate-spin" : ""} />
        </motion.div>
      </div>
      <p className="font-display font-bold text-center" data-testid="voice-state-text">{s.text}</p>
    </div>
  );
}
