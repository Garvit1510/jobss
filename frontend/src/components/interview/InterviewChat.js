import React, { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Bot, Send, User } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";
import { Button, Progress, Spinner } from "../ui";
import CodingRound from "./CodingRound";
import InterviewProctor from "./InterviewProctor";

function Bubble({ who, children }) {
  const ai = who === "ai";
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className={`flex gap-3 ${ai ? "" : "flex-row-reverse"}`}>
      <span className={`flex h-10 w-10 shrink-0 items-center justify-center border-3 border-ink ${ai ? "bg-brand-yellow" : "bg-brand-blue text-white"}`}>{ai ? <Bot size={18} /> : <User size={18} />}</span>
      <div className={`max-w-[80%] border-3 border-ink p-4 shadow-brutalsm ${ai ? "bg-white" : "bg-offwhite"}`}>{children}</div>
    </motion.div>
  );
}

export default function InterviewChat({ session, onDone, proctor = null }) {
  const [msgs, setMsgs] = useState([{ who: "ai", text: session.question, reaction: session.reaction, coding: session.coding }]);
  const [idx, setIdx] = useState({ index: session.index, total: session.total });
  const [ans, setAns] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef(null);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, busy]);

  const last = msgs[msgs.length - 1];
  const codingQ = last?.who === "ai" && last.coding ? last : null;

  const post = async (payload, mine, early) => {
    if (early) setMsgs((m) => [...m, mine]);
    setBusy(true);
    try {
      const { data } = await api.post("/interview/answer", { session_id: session.session_id, ...payload });
      const pre = early ? [] : [mine];
      if (data.done) {
        setMsgs((m) => [...m, ...pre]);
        setTimeout(() => onDone(data.report), 900);
        return;
      }
      setMsgs((m) => [...m, ...pre, { who: "ai", text: data.question, reaction: data.reaction, coding: data.coding, difficulty: data.difficulty }]);
      setIdx({ index: data.index, total: data.total });
    } catch (e) {
      toast.error(errMsg(e));
      if (early) {
        setMsgs((m) => m.slice(0, -1));
        setAns(payload.answer);
      }
    }
    setBusy(false);
  };
  const send = () => {
    const text = ans.trim();
    if (!text) return;
    setAns("");
    post({ answer: text }, { who: "me", text }, true);
  };
  const sendCode = (p) => post(p, { who: "me", text: p.answer, code: p.code }, false);

  return (
    <div className={`mx-auto px-4 md:px-8 py-10 ${codingQ ? "max-w-[1400px]" : "max-w-4xl"}`}>
      {proctor?.active && <InterviewProctor proctor={proctor} sessionId={session.session_id} onDone={onDone} />}
      <div className="brutal-card p-4 flex items-center justify-between gap-4">
        <div><p className="font-display font-bold">{session.cfg.role}{session.cfg.company ? ` · ${session.cfg.company}` : ""}</p><p className="font-mono text-xs text-ink/60">{session.cfg.interview_type} interview</p></div>
        <div className="w-40"><p className="font-mono text-xs text-right mb-1" data-testid="iv-progress">Q {idx.index}/{idx.total}</p><Progress value={(100 * idx.index) / idx.total} /></div>
      </div>
      <div className="mt-8 space-y-5" data-testid="iv-chat">
        {msgs.map((m, i) => (
          <Bubble key={i} who={m.who}>
            {m.reaction && <p className="mb-1 text-sm text-ink/60" data-testid="iv-reaction">{m.reaction}</p>}
            <p className={`whitespace-pre-line ${m.who === "ai" ? "font-display font-semibold" : ""}`} data-testid={m.who === "ai" ? "iv-question" : "iv-answer"}>{m.text}</p>
            {m.code && <pre className="mt-2 max-h-48 overflow-auto border-2 border-ink bg-ink p-3 font-mono text-xs text-white">{m.code}</pre>}
          </Bubble>
        ))}
        {busy && !codingQ && <Bubble who="ai"><span className="flex items-center gap-2 font-mono text-sm"><Spinner /> Interviewer is thinking…</span></Bubble>}
        <div ref={end} />
      </div>
      {codingQ ? <div className="mt-8"><CodingRound q={codingQ} refId={session.session_id} busy={busy} onSubmit={sendCode} proctor={proctor} /></div> : <div className="sticky bottom-4 mt-8 brutal-card p-3 flex gap-3">
        <textarea value={ans} onChange={(e) => setAns(e.target.value)} disabled={busy} placeholder="Type your answer… (Ctrl+Enter to send)" data-testid="iv-answer-input"
          onKeyDown={(e) => e.key === "Enter" && (e.ctrlKey || e.metaKey) && send()} className="flex-1 min-h-[80px] resize-y bg-transparent p-2 outline-none" />
        <Button variant="primary" onClick={send} disabled={busy || !ans.trim()} className="self-end" data-testid="iv-send-btn"><Send size={17} /></Button>
      </div>}
    </div>
  );
}
