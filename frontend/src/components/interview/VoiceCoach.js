import React from "react";
import { Gauge, MessageCircleWarning, PauseCircle } from "lucide-react";
import { Badge, Card } from "../ui";

const PACE_TONE = { "Good pace": "green", "Too fast": "red", "Too slow": "yellow" };

function Metric({ icon: I, label, value, sub, tone }) {
  return (
    <Card className="p-5">
      <span className={`flex h-10 w-10 items-center justify-center border-2 border-ink ${tone}`}><I size={18} /></span>
      <p className="mt-4 font-display text-3xl font-bold">{value}</p>
      <p className="eyebrow mt-1">{label}</p>
      {sub && <p className="mt-2 text-xs text-ink/60">{sub}</p>}
    </Card>
  );
}

export default function VoiceCoach({ coach, tips }) {
  if (!coach) return null;
  return (
    <section data-testid="voice-coach">
      <p className="eyebrow">Delivery</p>
      <h2 className="text-2xl font-bold mb-4">Voice Answer Coach</h2>
      <div className="grid md:grid-cols-3 gap-5">
        <Metric icon={Gauge} tone="bg-brand-blue text-white" label="Speaking pace" value={coach.avg_wpm ? `${coach.avg_wpm} wpm` : "—"}
          sub={<><Badge tone={PACE_TONE[coach.pace_label] || "white"}>{coach.pace_label}</Badge> <span className="ml-1">Ideal: 120–160 wpm</span></>} />
        <Metric icon={MessageCircleWarning} tone="bg-brand-yellow" label="Filler words" value={coach.filler_total}
          sub={coach.top_fillers.length ? coach.top_fillers.map(([w, n]) => `"${w}" ×${n}`).join(", ") : `${coach.fillers_per_100_words} per 100 words`} />
        <Metric icon={PauseCircle} tone="bg-brand-purple" label="Long pauses (>2s)" value={coach.long_pauses}
          sub={coach.longest_pause_sec ? `Longest pause: ${coach.longest_pause_sec}s` : "No long pauses"} />
      </div>
      <div className="mt-5 overflow-x-auto border-3 border-ink bg-white">
        <table className="w-full text-sm" data-testid="voice-coach-table">
          <thead className="bg-ink text-white font-display"><tr>{["Q", "Words", "Time", "Pace", "Fillers", "Long pauses"].map((h) => <th key={h} className="px-3 py-2 text-left">{h}</th>)}</tr></thead>
          <tbody>
            {coach.per_question.map((r) => (
              <tr key={r.q} className="border-t-2 border-ink/10 font-mono">
                <td className="px-3 py-2 font-bold">{r.q}</td><td className="px-3 py-2">{r.words}</td><td className="px-3 py-2">{r.duration_sec}s</td>
                <td className="px-3 py-2">{r.wpm ? `${r.wpm} wpm` : "—"} <span className="text-ink/50">{r.wpm ? `(${r.pace_label})` : ""}</span></td>
                <td className="px-3 py-2">{r.filler_total}</td><td className="px-3 py-2">{r.long_pauses}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {tips?.length > 0 && (
        <Card className="mt-5 p-6 bg-brand-blue/10">
          <h3 className="text-lg font-bold">Delivery tips</h3>
          <ul className="mt-3 list-disc pl-5 space-y-1.5 text-sm">{tips.map((t, i) => <li key={i}>{t}</li>)}</ul>
        </Card>
      )}
      <p className="mt-3 font-mono text-[11px] text-ink/50">Measured from your browser's live transcript. Some browsers drop sounds like "um/uh", so real filler counts may be higher.</p>
    </section>
  );
}
