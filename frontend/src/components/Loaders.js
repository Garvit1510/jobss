import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Check, Loader2 } from "lucide-react";

export function StepLoader({ steps, title = "Working on it", testid = "step-loader" }) {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((x) => Math.min(x + 1, steps.length - 1)), 2600);
    return () => clearInterval(t);
  }, [steps.length]);
  return (
    <div className="brutal-card mx-auto max-w-lg p-8" data-testid={testid}>
      <p className="eyebrow mb-2">AI at work</p>
      <h3 className="text-2xl font-bold mb-6">{title}</h3>
      <ul className="space-y-3">
        {steps.map((s, k) => (
          <motion.li key={s} initial={{ opacity: 0, x: -10 }} animate={{ opacity: k <= i ? 1 : 0.35, x: 0 }} transition={{ delay: k * 0.08 }} className="flex items-center gap-3 font-display font-semibold">
            <span className={`flex h-7 w-7 items-center justify-center border-2 border-ink ${k < i ? "bg-brand-green" : k === i ? "bg-brand-yellow" : "bg-white"}`}>
              {k < i ? <Check size={14} /> : k === i ? <Loader2 size={14} className="animate-spin" /> : null}
            </span>
            {s}
          </motion.li>
        ))}
      </ul>
    </div>
  );
}

export function FullLoader() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center" data-testid="full-loader">
      <div className="flex items-center gap-3 border-3 border-ink bg-brand-yellow px-6 py-4 shadow-brutal font-display font-bold">
        <Loader2 className="animate-spin" size={20} /> Loading
      </div>
    </div>
  );
}
