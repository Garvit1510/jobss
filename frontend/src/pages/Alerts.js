import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Bell, CheckCheck, ChevronDown, Search, Trash2 } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../lib/api";
import { timeAgo } from "../lib/format";
import JobCard, { JobCardSkeleton } from "../components/JobCard";
import { Badge, Button, Card, EmptyState } from "../components/ui";

const changed = () => window.dispatchEvent(new CustomEvent("joblens:alerts-changed"));

function toQuery(f) {
  const p = new URLSearchParams();
  Object.entries(f).forEach(([k, v]) => v && v !== "All" && v !== "all" && p.set(k, v));
  return p.toString();
}

function AlertRow({ a, onChange }) {
  const [open, setOpen] = useState(false);
  const [jobs, setJobs] = useState(null);
  const toggle = async () => {
    setOpen(!open);
    if (!open && !jobs) setJobs((await api.get(`/alerts/${a.id}/new`)).data.jobs);
  };
  const seen = async () => {
    await api.post(`/alerts/${a.id}/seen`);
    setJobs([]);
    changed();
    onChange();
  };
  const del = async () => {
    try {
      await api.delete(`/alerts/${a.id}`);
      toast.success("Alert deleted");
      changed();
      onChange();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };
  return (
    <Card className="p-5" data-testid={`alert-${a.id}`}>
      <div className="flex flex-wrap items-center gap-4">
        <span className={`flex h-11 w-11 items-center justify-center border-3 border-ink ${a.new_count ? "bg-brand-red text-white" : "bg-offwhite"}`}><Bell size={18} /></span>
        <div className="min-w-0 flex-1">
          <p className="font-display text-lg font-bold truncate">{a.name}</p>
          <p className="font-mono text-xs text-ink/60">{a.total.toLocaleString()} matching now · created {timeAgo(a.created_at)}</p>
        </div>
        <Badge tone={a.new_count ? "red" : "white"} data-testid="alert-new-count">{a.new_count} new</Badge>
        <div className="flex flex-wrap gap-2">
          <Button className="py-2" onClick={toggle} disabled={!a.new_count} data-testid="alert-toggle-btn"><ChevronDown size={16} className={open ? "rotate-180" : ""} /> New jobs</Button>
          <Link to={`/jobs?${toQuery(a.filters)}`} className="brutal-btn bg-white py-2" data-testid="alert-view-all"><Search size={16} /> All</Link>
          {a.new_count > 0 && <Button variant="green" className="py-2" onClick={seen} data-testid="alert-mark-seen"><CheckCheck size={16} /></Button>}
          <Button className="py-2" onClick={del} aria-label="Delete alert" data-testid="alert-delete"><Trash2 size={16} /></Button>
        </div>
      </div>
      {open && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-6 grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {jobs === null ? [0, 1, 2].map((i) => <JobCardSkeleton key={i} />) : jobs.map((j, i) => <JobCard key={j.id} job={j} index={i} />)}
        </motion.div>
      )}
    </Card>
  );
}

export default function Alerts() {
  const [d, setD] = useState(null);
  const load = useCallback(() => api.get("/alerts").then((r) => setD(r.data)), []);
  useEffect(() => {
    load();
  }, [load]);
  return (
    <div className="mx-auto max-w-6xl px-4 md:px-8 py-12">
      <p className="eyebrow mb-2">Saved searches</p>
      <h1 className="text-4xl md:text-5xl font-bold">Job Alerts</h1>
      <p className="mt-3 text-ink/70">New jobs from all 12 sources are checked every refresh{d?.last_refresh ? ` (last: ${timeAgo(d.last_refresh)})` : ""}.</p>
      <div className="mt-10 space-y-5">
        {d === null && <JobCardSkeleton />}
        {d && !d.alerts.length && (
          <EmptyState icon={Bell} title="No alerts yet" text="Search or filter jobs, then press “Alert me on new jobs” to save it." testid="alerts-empty"
            action={<Link to="/jobs" className="brutal-btn bg-brand-blue text-white">Browse jobs</Link>} />
        )}
        {d?.alerts.map((a) => <AlertRow key={a.id} a={a} onChange={load} />)}
      </div>
    </div>
  );
}
