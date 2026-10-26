import React, { useCallback, useEffect, useState } from "react";
import { Hourglass, Zap } from "lucide-react";
import api, { aiPending } from "../lib/api";
import { useAuth } from "../context/AuthContext";

const SLOW_MS = 12000;

function message(status, slow) {
  if (status?.state === "busy") {
    const m = Math.max(1, Math.ceil((status.retry_in || 60) / 60));
    return { tone: "bg-brand-red text-white", icon: Zap, text: `AI is at its limit right now. Please try again in about ${m} min.` };
  }
  if (slow) return { tone: "bg-brand-yellow", icon: Hourglass, text: "AI is still working on your request. This can take up to a minute, please don't refresh." };
  if (status?.state === "degraded") return { tone: "bg-brand-yellow", icon: Zap, text: "AI is under heavy load, so responses may be slower than usual." };
  return null;
}

export default function AIStatusBanner() {
  const { user } = useAuth();
  const [status, setStatus] = useState(null);
  const [slow, setSlow] = useState(false);
  const check = useCallback(() => api.get("/ai/status").then((r) => setStatus(r.data)).catch(() => {}), []);

  useEffect(() => {
    if (!user) return undefined;
    check();
    const poll = setInterval(check, 60000);
    window.addEventListener("joblens:ai-busy", check);
    return () => { clearInterval(poll); window.removeEventListener("joblens:ai-busy", check); };
  }, [user, check]);

  useEffect(() => {
    if (!user) return undefined;
    let was = false;
    const t = setInterval(() => {
      const now = Date.now();
      const s = [...aiPending.values()].some((start) => now - start > SLOW_MS);
      setSlow(s);
      if (s && !was) check();
      was = s;
    }, 1000);
    return () => clearInterval(t);
  }, [user, check]);

  const m = user && message(status, slow);
  if (!m) return null;
  const I = m.icon;
  return (
    <div className="fixed bottom-4 left-1/2 z-[70] w-[calc(100%-2rem)] max-w-xl -translate-x-1/2" role="status" data-testid="ai-status-banner">
      <div className={`flex items-center gap-3 border-3 border-ink px-4 py-2.5 shadow-brutalsm ${m.tone}`}>
        <I size={17} className={`shrink-0 ${slow ? "animate-pulse" : ""}`} />
        <p className="font-display text-sm font-semibold" data-testid="ai-status-text">{m.text}</p>
      </div>
    </div>
  );
}
