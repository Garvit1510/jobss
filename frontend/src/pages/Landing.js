import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, Briefcase, ClipboardCheck, FileSearch, Mic, Sparkles, Users } from "lucide-react";
import api from "../lib/api";

const SOURCES = ["Greenhouse", "Lever", "Ashby", "Workable", "SmartRecruiters", "Recruitee", "Remotive", "Arbeitnow", "RemoteOK", "Himalayas", "Jobicy", "The Muse"];
const FEATURES = [
  { icon: FileSearch, title: "AI Resume Analysis", text: "Skills, education, experience and an honest resume score, extracted in seconds.", tone: "bg-brand-yellow" },
  { icon: Briefcase, title: "Live Jobs, 12 Sources", text: "Real openings pulled straight from company job boards — never mock listings.", tone: "bg-brand-blue text-white" },
  { icon: Sparkles, title: "Prepare For Any Job", text: "Skill gap, 4-week roadmap, ranked subjects and tailored interview questions.", tone: "bg-brand-green" },
  { icon: ClipboardCheck, title: "Company Mock OAs", text: "Timed assessments modelled on real company OA patterns, auto-evaluated.", tone: "bg-brand-purple" },
  { icon: Mic, title: "AI Interviews", text: "A professional AI interviewer that adapts to you and writes a full report.", tone: "bg-brand-red text-white" },
  { icon: Users, title: "Community Experiences", text: "Real interview & OA stories shared by candidates, summarised by AI.", tone: "bg-white" },
];

export default function Landing() {
  const [jobs, setJobs] = useState(null);
  useEffect(() => {
    api.get("/health").then((r) => setJobs(r.data.jobs)).catch(() => {});
  }, []);
  return (
    <div className="overflow-hidden">
      <section className="mx-auto max-w-7xl px-4 md:px-8 pt-16 md:pt-24 pb-16 grid lg:grid-cols-[1.3fr_1fr] gap-12 items-center">
        <div>
          <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="eyebrow mb-5">Career intelligence platform</motion.p>
          <motion.h1 initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="text-5xl md:text-7xl font-bold leading-[0.95] tracking-tight">
            Upload Resume.<br />
            <span className="bg-brand-yellow px-2 border-3 border-ink inline-block -rotate-1 my-2">Discover</span> Opportunities.<br />
            Prepare <span className="text-brand-blue">Smarter.</span>
          </motion.h1>
          <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.25 }} className="mt-6 max-w-xl text-lg text-ink/70">
            JobLens AI reads your resume, matches you to real live openings and gets you interview-ready with AI prep, mock OAs and interviews.
          </motion.p>
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 }} className="mt-10 flex flex-wrap gap-4">
            <Link to="/register" className="brutal-btn bg-brand-blue text-white text-lg px-7 py-4" data-testid="hero-get-started">Get started free <ArrowRight size={20} /></Link>
            <Link to="/login" className="brutal-btn bg-white text-lg px-7 py-4" data-testid="hero-login">I have an account</Link>
          </motion.div>
        </div>
        <motion.div initial={{ opacity: 0, rotate: 3, y: 30 }} animate={{ opacity: 1, rotate: 0, y: 0 }} transition={{ delay: 0.3 }} className="brutal-card p-8 shadow-brutallg">
          <p className="eyebrow">Live right now</p>
          <p className="mt-3 font-display text-6xl font-bold" data-testid="landing-live-jobs">{jobs === null ? "…" : jobs.toLocaleString()}</p>
          <p className="font-mono text-sm text-ink/60">real job openings indexed</p>
          <div className="mt-6 grid grid-cols-2 gap-3">
            <div className="border-3 border-ink bg-brand-green p-4"><p className="font-display text-3xl font-bold">12</p><p className="font-mono text-xs">job sources</p></div>
            <div className="border-3 border-ink bg-brand-yellow p-4"><p className="font-display text-3xl font-bold">0</p><p className="font-mono text-xs">mock listings</p></div>
          </div>
          <p className="mt-5 text-sm text-ink/60">Refreshed automatically every few hours from company career pages.</p>
        </motion.div>
      </section>

      <div className="border-y-3 border-ink bg-ink py-4 overflow-hidden">
        <div className="flex w-max animate-marquee gap-10">
          {[...SOURCES, ...SOURCES].map((s, i) => (
            <span key={i} className="font-display text-xl font-bold text-paper whitespace-nowrap">{s} <span className="text-brand-yellow">✦</span></span>
          ))}
        </div>
      </div>

      <section className="mx-auto max-w-7xl px-4 md:px-8 py-20">
        <p className="eyebrow mb-3">Everything in one place</p>
        <h2 className="text-4xl md:text-5xl font-bold max-w-2xl">From resume to offer, without the guesswork.</h2>
        <div className="mt-12 grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {FEATURES.map(({ icon: I, title, text, tone }, i) => (
            <motion.div key={title} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.06 }} className="brutal-card p-6 hover:-translate-y-1 transition-transform">
              <span className={`flex h-12 w-12 items-center justify-center border-3 border-ink ${tone}`}><I size={22} /></span>
              <h3 className="mt-5 text-xl font-bold">{title}</h3>
              <p className="mt-2 text-ink/70">{text}</p>
            </motion.div>
          ))}
        </div>
      </section>
    </div>
  );
}
