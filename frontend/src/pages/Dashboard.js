import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Activity, ArrowRight, Briefcase, Code2, Gauge, GraduationCap, Sparkles, TrendingUp, Upload } from "lucide-react";
import api from "../lib/api";
import { timeAgo } from "../lib/format";
import { Card, EmptyState, Skeleton } from "../components/ui";
import CareerOverview from "../components/career/CareerOverview";

function Stat({ icon: I, tone, value, suffix, label, i, testid }) {
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.07 }}>
      <Card hover className="p-6" data-testid={testid}>
        <span className={`flex h-10 w-10 items-center justify-center border-2 border-ink ${tone}`}><I size={20} /></span>
        <p className="mt-5 font-display text-4xl font-bold">{value}<span className="text-xl text-ink/50">{suffix}</span></p>
        <p className="eyebrow mt-1">{label}</p>
      </Card>
    </motion.div>
  );
}

function Profile({ resume }) {
  const items = [
    ...(resume.education || []).map((e) => ({ k: "edu", t: `${e.degree}, ${e.institution}${e.year ? `, ${e.year}` : ""}`, c: "border-brand-blue" })),
    ...(resume.experience || []).slice(0, 3).map((e) => ({ k: "exp", t: `${e.title} at ${e.company}${e.duration ? ` (${e.duration})` : ""}`, c: "border-brand-yellow" })),
  ];
  return (
    <Card className="p-6" data-testid="profile-card">
      <h3 className="flex items-center gap-2 text-xl font-bold"><GraduationCap size={20} /> Profile</h3>
      <div className="mt-5 space-y-4">
        {items.length ? items.map((x, i) => <p key={i} className={`border-l-3 ${x.c} pl-4 text-sm`}>{x.t}</p>) : <p className="text-sm text-ink/60">No education or experience found in resume.</p>}
      </div>
    </Card>
  );
}

function ActivityFeed({ items }) {
  return (
    <Card className="p-6" data-testid="activity-card">
      <h3 className="flex items-center gap-2 text-xl font-bold"><Activity size={20} /> Recent Activity</h3>
      <ul className="mt-5 space-y-4">
        {items.length ? items.map((a) => (
          <li key={a.id} className="flex gap-3">
            <span className="mt-1.5 h-3 w-3 shrink-0 border-2 border-ink bg-brand-green" />
            <div><p className="text-sm font-semibold">{a.text}</p><p className="font-mono text-xs text-ink/50">{timeAgo(a.created_at)}</p></div>
          </li>
        )) : <p className="text-sm text-ink/60">No activity yet.</p>}
      </ul>
    </Card>
  );
}

export default function Dashboard() {
  const [d, setD] = useState(null);
  useEffect(() => {
    api.get("/dashboard").then((r) => setD(r.data));
  }, []);
  if (!d) return <div className="mx-auto max-w-7xl px-4 md:px-8 py-12 grid md:grid-cols-4 gap-6">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-40" />)}</div>;
  const r = d.resume;
  if (!r) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-20">
        <EmptyState icon={Upload} title={`Welcome, ${d.user.name.split(" ")[0]}!`} text="Upload your resume to unlock your resume score, AI-matched jobs and personalised prep. Every feature adapts to your profession." testid="dashboard-no-resume"
          action={<Link to="/upload" className="brutal-btn bg-brand-blue text-white" data-testid="dashboard-upload-cta">Upload resume <ArrowRight size={18} /></Link>} />
        <div className="mt-10"><CareerOverview /></div>
      </div>
    );
  }
  return (
    <div className="mx-auto max-w-7xl px-4 md:px-8 py-12">
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-6">
        <div className="max-w-3xl">
          <p className="eyebrow mb-2">Welcome back</p>
          <h1 className="text-4xl md:text-5xl font-bold" data-testid="dashboard-name">{r.name}</h1>
          <p className="mt-3 text-ink/70 line-clamp-2">{r.headline}{r.summary ? ` · ${r.summary}` : ""}</p>
        </div>
        <Link to="/jobs" className="brutal-btn bg-brand-blue text-white px-8 py-4 text-lg shadow-brutal" data-testid="view-matched-jobs-btn"><Briefcase size={20} /> View Matched Jobs <ArrowRight size={18} /></Link>
      </div>
      <div className="mt-10 grid grid-cols-2 lg:grid-cols-4 gap-5">
        <Stat i={0} icon={Gauge} tone="bg-brand-yellow" value={r.score} suffix="/100" label="Resume score" testid="stat-resume-score" />
        <Stat i={1} icon={Sparkles} tone="bg-brand-blue text-white" value={r.skills.length} label="Skills found" testid="stat-skills" />
        <Stat i={2} icon={Briefcase} tone="bg-brand-green" value={d.stats.jobs_matched.toLocaleString()} suffix="+" label="Jobs matched (60%+)" testid="stat-jobs-matched" />
        <Stat i={3} icon={TrendingUp} tone="bg-brand-purple" value={d.stats.avg_match} suffix="%" label="Avg match (top 50)" testid="stat-avg-match" />
      </div>
      <div className="mt-10"><CareerOverview /></div>
      <div className="mt-10 grid lg:grid-cols-[1fr_380px] gap-8">
        <div className="space-y-8">
          <Card className="p-7" data-testid="recommended-roles-card">
            <p className="eyebrow">AI recommendation</p>
            <h2 className="text-3xl font-bold mt-1">Recommended Roles</h2>
            <div className="mt-6 flex flex-wrap gap-3">
              {r.recommended_roles.map((role) => (
                <Link key={role} to={`/jobs?q=${encodeURIComponent(role)}`} className="brutal-btn bg-offwhite" data-testid={`role-${role}`}><Code2 size={16} /> {role}</Link>
              ))}
            </div>
          </Card>
          <Card className="p-7" data-testid="skills-card">
            <p className="eyebrow">Extracted</p>
            <h2 className="text-3xl font-bold mt-1">Your Skills</h2>
            <div className="mt-6 flex flex-wrap gap-2">{r.skills.map((s) => <span key={s} className="tag-chip">{s}</span>)}</div>
          </Card>
          <div className="grid md:grid-cols-2 gap-8">
            <Card className="p-7 bg-brand-green/10" data-testid="strengths-card">
              <h3 className="text-xl font-bold">Strengths</h3>
              <ul className="mt-4 space-y-2 text-sm list-disc pl-5">{r.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
            </Card>
            <Card className="p-7 bg-brand-yellow/20" data-testid="improvements-card">
              <h3 className="text-xl font-bold">Improve your resume</h3>
              <ul className="mt-4 space-y-2 text-sm list-disc pl-5">{r.improvements.map((s, i) => <li key={i}>{s}</li>)}</ul>
            </Card>
          </div>
        </div>
        <div className="space-y-8">
          <Profile resume={r} />
          <ActivityFeed items={d.activity} />
          <Card className="p-6 bg-ink text-white">
            <p className="eyebrow !text-white/60">Live job index</p>
            <p className="mt-2 font-display text-4xl font-bold">{d.stats.total_jobs.toLocaleString()}</p>
            <p className="font-mono text-xs text-white/60">real jobs from 12 sources · {d.stats.oa_taken} OAs · {d.stats.interviews_done} interviews done</p>
          </Card>
        </div>
      </div>
    </div>
  );
}
