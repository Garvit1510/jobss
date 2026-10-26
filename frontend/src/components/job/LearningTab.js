import React, { useEffect, useState } from "react";
import { BookOpen, ExternalLink, FileText, GraduationCap, Youtube } from "lucide-react";
import api, { errMsg } from "../../lib/api";
import { StepLoader } from "../Loaders";
import { Card, EmptyState } from "../ui";

const ICON = { youtube: Youtube, article: FileText, docs: BookOpen, course: GraduationCap, freecodecamp: GraduationCap };
const LABEL = { youtube: "YouTube", article: "GeeksforGeeks", docs: "MDN Docs", course: "Free Course", freecodecamp: "freeCodeCamp" };

export default function LearningTab({ job }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.get("/learning", { params: { job_id: job.id } }).then((r) => setData(r.data)).catch((e) => setErr(errMsg(e)));
  }, [job.id]);
  if (err) return <EmptyState title="Couldn't load resources" text={err} />;
  if (!data) return <StepLoader title="Curating learning resources" steps={["Finding your key gaps", "Picking topics", "Collecting videos, articles & courses"]} />;
  return (
    <div className="space-y-8" data-testid="learning-list">
      {data.topics.map((t, i) => (
        <Card key={i} className="p-6">
          <p className="eyebrow">Topic {i + 1}</p>
          <h3 className="mt-1 text-2xl font-bold">{t.topic}</h3>
          <p className="mt-1 text-ink/70">{t.why}</p>
          <div className="mt-5 grid sm:grid-cols-2 gap-3">
            {t.resources.map((r, k) => {
              const I = ICON[r.type] || FileText;
              return (
                <a key={k} href={r.url} target="_blank" rel="noreferrer" className="group flex items-start gap-3 border-2 border-ink bg-offwhite p-3 hover:bg-brand-yellow/40 transition-colors" data-testid={`resource-${i}-${k}`}>
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center border-2 border-ink bg-white"><I size={17} /></span>
                  <span className="min-w-0"><span className="block font-semibold text-sm">{r.title}</span><span className="font-mono text-[11px] text-ink/60">{LABEL[r.type]}</span></span>
                  <ExternalLink size={14} className="ml-auto shrink-0 opacity-0 group-hover:opacity-100" />
                </a>
              );
            })}
          </div>
        </Card>
      ))}
    </div>
  );
}
