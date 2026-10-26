import React, { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Repeat2, ShieldCheck, Trash2 } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../lib/api";
import { Badge, Button, Card, Spinner } from "../components/ui";


function Switcher() {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState(false);
  const go = async () => { setBusy(true); try { setD((await api.post("/career/switch", {}, { timeout: 120000 })).data); } catch (e) { toast.error(errMsg(e)); } setBusy(false); };
  return (
    <div className="space-y-5" data-testid="career-switcher">
      <Card className="p-7"><p className="text-sm text-ink/70">See realistic alternative careers based on transferable skills you already have, what's missing and how to get there.</p>
        <Button variant="primary" className="mt-4" onClick={go} disabled={busy} data-testid="switch-btn">{busy ? <Spinner /> : <Repeat2 size={17} />} Suggest career switches</Button></Card>
      {d?.options?.map((o, i) => (
        <Card key={i} className="p-6" data-testid={`switch-option-${i}`}>
          <p className="flex flex-wrap items-center gap-2 font-display text-xl font-bold">{o.role} <Badge tone="yellow">{o.timeline}</Badge></p>
          <p className="mt-2 text-sm">{o.why}</p>
          <div className="mt-3 grid md:grid-cols-2 gap-4 text-sm">
            <div><p className="eyebrow mb-1">Transferable</p>{(o.transferable_skills || []).join(", ")}</div>
            <div><p className="eyebrow mb-1">To gain</p>{(o.missing || []).join(", ")}</div>
          </div>
          <ol className="mt-3 list-decimal pl-5 text-sm space-y-1">{(o.steps || []).map((s, k) => <li key={k}>{s}</li>)}</ol>
          <p className="mt-3 text-sm"><b>Entry roles:</b> {(o.entry_roles || []).join(", ")}</p>
        </Card>
      ))}
    </div>
  );
}

function Privacy() {
  const del = async () => {
    if (!window.confirm("Delete your resume, profile, assessments, interviews and alerts? Your login stays. This cannot be undone.")) return;
    try { await api.delete("/me/data"); toast.success("Your data was deleted."); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Card className="p-7 space-y-3" data-testid="privacy-card">
      <p className="text-sm">Webcam and microphone are used only in proctored mode after you agree. Video and audio are analysed in your browser and never uploaded; only flag events (type and time) are stored.</p>
      <p className="text-sm">Proctoring flags are signals for your own practice, not proof of cheating.</p>
      <Button variant="dark" onClick={del} data-testid="delete-data-btn"><Trash2 size={16} /> Delete my data</Button>
    </Card>
  );
}

const TABS = [["switch", "Career switcher", Repeat2], ["privacy", "Privacy", ShieldCheck]];

export default function Profile() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "privacy" ? "privacy" : "switch";
  return (
    <div className="mx-auto max-w-5xl px-4 md:px-8 py-12">
      <p className="eyebrow mb-2">Works for every profession</p>
      <h1 className="text-4xl md:text-5xl font-bold">Your profile</h1>
      <div className="mt-8 flex flex-wrap gap-2" role="tablist">{TABS.map(([k, l, I]) => (
        <button key={k} role="tab" aria-selected={tab === k} onClick={() => setParams({ tab: k })} data-testid={`profile-tab-${k}`} className={`brutal-btn text-sm ${tab === k ? "bg-ink text-white" : "bg-white"}`}><I size={16} /> {l}</button>
      ))}</div>
      <div className="mt-6">{tab === "switch" ? <Switcher /> : <Privacy />}</div>
    </div>
  );
}
