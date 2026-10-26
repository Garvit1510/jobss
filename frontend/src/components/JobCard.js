import React from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowUpRight, Building2, MapPin, Wifi } from "lucide-react";
import { Badge, MatchRing } from "./ui";
import { formatSalary, timeAgo } from "../lib/format";

export default function JobCard({ job, index = 0 }) {
  const salary = formatSalary(job.salary);
  return (
    <motion.div className="min-w-0" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(index, 12) * 0.04 }}>
      <Link
        to={`/jobs/${job.id}`}
        className="brutal-card flex h-full flex-col p-5 transition-transform duration-200 hover:-translate-x-1 hover:-translate-y-1 hover:shadow-brutallg"
        data-testid={`job-card-${job.id}`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="flex items-center gap-1.5 font-mono text-xs text-ink/60 truncate"><Building2 size={13} className="shrink-0" /> <span className="truncate">{job.company}</span>{job.posted_at && <span className="shrink-0 text-ink/40">· {timeAgo(job.posted_at)}</span>}</p>
            <h3 className="mt-1 text-lg font-bold leading-snug line-clamp-2" data-testid="job-card-title">{job.title}</h3>
          </div>
          <MatchRing value={job.match} />
        </div>
        <div className="mt-4 flex flex-nowrap gap-2 overflow-hidden">
          <Badge tone={job.work_type} className="shrink-0"><Wifi size={12} /> {job.work_type}</Badge>
          <Badge className="min-w-0"><MapPin size={12} className="shrink-0" /> <span className="truncate">{job.location}</span></Badge>
          <Badge className="shrink-0">{job.level}</Badge>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {job.skills?.slice(0, 4).map((s) => <span key={s} className="tag-chip">{s.toLowerCase()}</span>)}
        </div>
        <div className="mt-auto pt-5">
          <div className="flex items-center justify-between border-t-2 border-ink/10 pt-4">
            <span className="font-mono text-sm font-bold truncate" data-testid="job-card-salary">{salary || <span className="text-ink/40 font-normal">Not disclosed</span>}</span>
            <span className="flex shrink-0 items-center gap-1 font-display font-bold text-brand-blue">View <ArrowUpRight size={15} /></span>
          </div>
        </div>
      </Link>
    </motion.div>
  );
}

export function JobCardSkeleton() {
  return (
    <div className="brutal-card p-5 space-y-4">
      <div className="skeleton h-3 w-1/3" />
      <div className="skeleton h-6 w-3/4" />
      <div className="flex gap-2"><div className="skeleton h-6 w-20" /><div className="skeleton h-6 w-28" /></div>
      <div className="flex gap-2"><div className="skeleton h-6 w-14" /><div className="skeleton h-6 w-16" /><div className="skeleton h-6 w-12" /></div>
      <div className="skeleton h-5 w-1/2" />
    </div>
  );
}
