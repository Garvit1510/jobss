import React, { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { Bot, User } from "lucide-react";

export default function VoiceTranscript({ log, answer, interim, listening, disabled, onEdit, onSubmit }) {
  const end = useRef(null);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [log.length]);
  return (
    <div className="brutal-card p-6 flex flex-col min-h-[520px]" data-testid="voice-transcript">
      <p className="eyebrow mb-4">Live transcript</p>
      <div className="flex-1 space-y-4 overflow-y-auto max-h-[380px] pr-1">
        {log.length === 0 && <p className="text-sm text-ink/50">Your answered questions will appear here.</p>}
        {log.map((t, i) => (
          <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-2">
            <p className="flex gap-2 text-sm font-semibold"><Bot size={16} className="shrink-0 mt-0.5" /> {t.q}</p>
            <p className="flex gap-2 text-sm text-ink/80"><User size={16} className="shrink-0 mt-0.5 text-brand-blue" /> {t.a}</p>
          </motion.div>
        ))}
        <div ref={end} />
      </div>
      <div className="mt-4 border-t-2 border-ink/10 pt-4">
        <label htmlFor="voice-answer" className="flex items-center justify-between font-display font-bold text-sm mb-2">
          Your answer {listening && <span className="flex items-center gap-1.5 font-mono text-xs text-brand-green"><span className="h-2 w-2 animate-pulse rounded-full bg-brand-green" /> transcribing</span>}
        </label>
        <textarea id="voice-answer" value={answer} disabled={disabled} onChange={(e) => onEdit(e.target.value)} data-testid="voice-answer-input"
          onKeyDown={(e) => e.key === "Enter" && (e.ctrlKey || e.metaKey) && onSubmit()}
          placeholder="Speak, or type your answer here (Ctrl+Enter to submit)" className={`brutal-input min-h-[120px] resize-y ${interim ? "italic" : ""}`} />
      </div>
    </div>
  );
}
