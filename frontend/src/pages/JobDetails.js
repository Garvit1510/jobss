import React, { useEffect, useState } from "react";
import MatchExplain from "../components/career/MatchExplain";
import { Link, useParams } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, BookOpen, Building2, ExternalLink, FileText, ListChecks, MapPin, Sparkles, Users, Wifi } from "lucide-react";
import api, { errMsg } from "../lib/api";
import { formatSalary, timeAgo } from "../lib/format";
import { Badge, Card, EmptyState, MatchRing, Skeleton } from "../components/ui";
import PrepareTab from "../components/job/PrepareTab";
import LearningTab from "../components/job/LearningTab";
import CommunityTab from "../components/job/CommunityTab";

const TABS = [
  { k: "overview", label: "Overview", icon: FileText },
  { k: "prepare", label: "Prepare", icon: Sparkles },
  { k: "learning", label: "Learning", icon: BookOpen },
  { k: "community", label: "Community", icon: Users },
];

function Overview({ job }) {
  const salary = formatSalary(job.salary);
  const rows = [["Company", job.company], ["Location", job.location], ["Work Type", job.work_type], ["Experience", job.level],
    ["Employment", job.employment_type], ["Salary", salary || "Not disclosed"], ["Source", job.source_label], ["Posted", job.posted_at ? timeAgo(job.posted_at) : null], ["Sector", job.sector_name], ["Last refreshed", job.fetched_at ? timeAgo(job.fetched_at) : null]];
  return (
    <div className="space-y-8">
      <Card className="p-7">
        <h2 className="text-2xl font-bold mb-4">About the Role</h2>
        <div className="whitespace-pre-line leading-relaxed text-ink/80 max-h-[600px] overflow-y-auto pr-2" data-testid="job-description">
          {job.description || "The full description is available on the company's job page."}
        </div>
      </Card>
      <div className="grid md:grid-cols-2 gap-8">
        <Card className="p-7">
          <h3 className="flex items-center gap-2 text-xl font-bold"><ListChecks size={20} /> Requirements</h3>
          <ul className="mt-5 space-y-2.5" data-testid="job-requirements">
            {job.skills.length ? job.skills.map((s) => (
              <li key={s} className="flex items-center gap-3">
                <span className={`h-3 w-3 border-2 border-ink ${job.skills_have.includes(s) ? "bg-brand-green" : "bg-brand-blue"}`} />
                {s} {job.skills_have.includes(s) && <span className="font-mono text-[11px] text-brand-green font-bold">YOU HAVE</span>}
              </li>
            )) : <li className="text-ink/60">No specific skills detected — read the full description.</li>}
          </ul>
        </Card>
        <Card className="p-7">
          <h3 className="text-xl font-bold">Details</h3>
          <dl className="mt-4 divide-y-2 divide-ink/10">
            {rows.filter((r) => r[1]).map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4 py-3"><dt className="font-mono text-sm text-ink/60">{k}</dt><dd className="font-display font-semibold text-right">{v}</dd></div>
            ))}
          </dl>
          <a href={job.apply_url} target="_blank" rel="noreferrer" className="brutal-btn mt-6 w-full bg-brand-blue text-white py-3.5 text-lg" data-testid="apply-now-btn">
            Apply Now <ExternalLink size={18} />
          </a>
        </Card>
      </div>
    </div>
  );
}

export default function JobDetails() {
  const { id } = useParams();
  const [job, setJob] = useState(null);
  const [err, setErr] = useState("");
  const [tab, setTab] = useState("overview");
  useEffect(() => {
    api.get(`/jobs/${id}`).then((r) => setJob(r.data)).catch((e) => setErr(errMsg(e)));
  }, [id]);

  if (err) return <div className="mx-auto max-w-3xl px-4 py-20"><EmptyState title="Job unavailable" text={err} action={<Link to="/jobs" className="brutal-btn bg-white">Back to jobs</Link>} /></div>;
  if (!job) return <div className="mx-auto max-w-5xl px-4 py-12 space-y-6"><Skeleton className="h-48" /><Skeleton className="h-96" /></div>;
  const salary = formatSalary(job.salary);
  return (
    <div className="mx-auto max-w-5xl px-4 md:px-8 py-10">
      <Link to="/jobs" className="inline-flex items-center gap-2 font-display font-bold hover:-translate-x-1 transition-transform" data-testid="back-to-jobs"><ArrowLeft size={18} /> Back to Jobs</Link>
      <Card className="mt-6 p-7 flex flex-col sm:flex-row justify-between gap-6">
        <div className="min-w-0">
          <p className="flex items-center gap-2 font-mono text-sm text-ink/60"><Building2 size={15} /> {job.company}</p>
          <h1 className="mt-2 text-3xl md:text-4xl font-bold leading-tight" data-testid="job-title">{job.title}</h1>
          <div className="mt-5 flex flex-wrap gap-2">
            <Badge tone={job.work_type}><Wifi size={12} /> {job.work_type}</Badge>
            <Badge><MapPin size={12} /> {job.location}</Badge>
            <Badge tone="yellow">{job.level}</Badge>
            {salary && <Badge tone="blue" data-testid="job-salary">{salary}</Badge>}
          </div>
        </div>
        <div className="flex flex-col items-center gap-3">
          {job.match !== null && <><MatchRing value={job.match} size={96} stroke={8} /><p className="eyebrow">Match</p></>}
        </div>
      </Card>
      <div className="mt-8 flex flex-wrap gap-3">
        {TABS.map(({ k, label, icon: I }) => (
          <button key={k} onClick={() => setTab(k)} data-testid={`tab-${k}`}
            className={`brutal-btn ${tab === k ? "bg-ink text-white shadow-brutal" : "bg-white"}`}><I size={17} /> {label}</button>
        ))}
      </div>
      <AnimatePresence mode="wait">
        <motion.div key={tab} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }} className="mt-8">
          {tab === "overview" && <div className="space-y-6"><MatchExplain e={job.match_explain} /><Overview job={job} /></div>}
          {tab === "prepare" && <PrepareTab job={job} />}
          {tab === "learning" && <LearningTab job={job} />}
          {tab === "community" && <CommunityTab company={job.company} defaultRole={job.title} />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
