import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Inbox } from "lucide-react";

const VARIANTS = {
  primary: "bg-brand-blue text-white",
  dark: "bg-ink text-white",
  yellow: "bg-brand-yellow text-ink",
  white: "bg-white text-ink",
  green: "bg-brand-green text-ink",
};

export function Button({ variant = "white", className = "", children, ...p }) {
  return (
    <button className={`brutal-btn ${VARIANTS[variant]} ${className}`} {...p}>
      {children}
    </button>
  );
}

export function Card({ className = "", hover = false, children, ...p }) {
  return (
    <div
      className={`brutal-card ${hover ? "transition-transform duration-200 hover:-translate-x-1 hover:-translate-y-1 hover:shadow-brutallg" : ""} ${className}`}
      {...p}
    >
      {children}
    </div>
  );
}

const BADGE = {
  Remote: "bg-brand-green", Hybrid: "bg-brand-blue text-white", Onsite: "bg-brand-yellow",
  yellow: "bg-brand-yellow", blue: "bg-brand-blue text-white", green: "bg-brand-green", red: "bg-brand-red text-white",
  purple: "bg-brand-purple", white: "bg-white", dark: "bg-ink text-white",
};

export function Badge({ tone = "white", className = "", children, ...p }) {
  return (
    <span className={`inline-flex items-center gap-1 border-2 border-ink px-2 py-0.5 text-xs font-display font-bold ${BADGE[tone] || BADGE.white} ${className}`} {...p}>
      {children}
    </span>
  );
}

export function SectionTitle({ eyebrow, title, className = "" }) {
  return (
    <div className={className}>
      {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
      <h2 className="text-2xl md:text-3xl font-bold tracking-tight">{title}</h2>
    </div>
  );
}

export function Skeleton({ className = "" }) {
  return <div className={`skeleton border-2 border-ink/10 ${className}`} />;
}

export function Progress({ value = 0, tone = "bg-brand-blue" }) {
  return (
    <div className="h-3 w-full border-2 border-ink bg-offwhite">
      <motion.div className={`h-full ${tone}`} initial={{ width: 0 }} animate={{ width: `${Math.min(100, value)}%` }} transition={{ duration: 0.8 }} />
    </div>
  );
}

export function MatchRing({ value, size = 56, stroke = 6, label }) {
  if (value === null || value === undefined) return null;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const color = value >= 70 ? "#22C55E" : value >= 45 ? "#4D6FFF" : "#FF5A4D";
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} data-testid="match-ring">
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="#EEEAE0" strokeWidth={stroke} fill="none" />
        <motion.circle
          cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={stroke} fill="none" strokeLinecap="round"
          strokeDasharray={c} initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c - (c * value) / 100 }} transition={{ duration: 1 }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-display font-bold" style={{ fontSize: size / 4.2 }}>{value}%</span>
      </div>
      {label && <p className="eyebrow text-center mt-1">{label}</p>}
    </div>
  );
}

export function EmptyState({ icon: Icon = Inbox, title, text, action, testid = "empty-state" }) {
  return (
    <div className="border-3 border-dashed border-ink/40 bg-white/60 p-10 text-center" data-testid={testid}>
      <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center border-3 border-ink bg-brand-yellow shadow-brutalsm">
        <Icon size={24} />
      </div>
      <h3 className="text-xl font-bold">{title}</h3>
      {text && <p className="mt-2 text-ink/60 max-w-md mx-auto">{text}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

export function Modal({ open, onClose, title, children, testid = "modal" }) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/50 p-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
          <motion.div
            className="brutal-card w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6 md:p-8" data-testid={testid}
            initial={{ y: 30, scale: 0.97 }} animate={{ y: 0, scale: 1 }} exit={{ y: 30, opacity: 0 }} onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-6 flex items-center justify-between">
              <h3 className="text-2xl font-bold">{title}</h3>
              <button onClick={onClose} className="border-2 border-ink p-1 hover:bg-brand-yellow" data-testid={`${testid}-close`}><X size={18} /></button>
            </div>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function Spinner({ className = "" }) {
  return <span className={`inline-block h-4 w-4 animate-spin border-2 border-current border-t-transparent rounded-full ${className}`} />;
}
