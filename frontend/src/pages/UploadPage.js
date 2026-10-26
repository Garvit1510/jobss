import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useDropzone } from "react-dropzone";
import { motion } from "framer-motion";
import { FileUp, FileText } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../lib/api";
import { StepLoader } from "../components/Loaders";
import { Button } from "../components/ui";

const STEPS = ["Reading your resume", "Extracting skills & experience", "Scoring resume quality", "Finding recommended roles", "Matching live jobs"];

export default function UploadPage() {
  const nav = useNavigate();
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    multiple: false,
    maxSize: 8 * 1024 * 1024,
    accept: { "application/pdf": [".pdf"], "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"] },
    onDrop: (ok, bad) => {
      if (bad.length) toast.error("Upload a PDF or DOCX under 8 MB.");
      if (ok[0]) setFile(ok[0]);
    },
  });

  const upload = async () => {
    setBusy(true);
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.post("/resume/upload", fd);
      toast.success("Resume analyzed!");
      nav("/dashboard");
    } catch (e) {
      toast.error(errMsg(e));
      setBusy(false);
    }
  };

  if (busy) return <div className="px-4 py-24"><StepLoader steps={STEPS} title="Analyzing your resume" testid="analyzing-screen" /></div>;

  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <p className="eyebrow mb-2">Step 1</p>
      <h1 className="text-4xl md:text-5xl font-bold">Upload your resume</h1>
      <p className="mt-3 text-ink/70">We'll analyze it with AI and match you against live jobs from 12 sources.</p>
      <motion.div whileHover={{ scale: 1.005 }} {...getRootProps()} data-testid="resume-dropzone"
        className={`mt-10 cursor-pointer border-3 border-dashed border-ink p-14 text-center transition-colors ${isDragActive ? "bg-brand-yellow" : "bg-white"} shadow-brutal`}>
        <input {...getInputProps()} data-testid="resume-file-input" />
        <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center border-3 border-ink bg-brand-blue text-white shadow-brutalsm"><FileUp size={28} /></div>
        <p className="font-display text-xl font-bold">{isDragActive ? "Drop it here" : "Drag & drop your resume"}</p>
        <p className="mt-1 font-mono text-sm text-ink/60">PDF or DOCX · max 8 MB · or click to browse</p>
      </motion.div>
      {file && (
        <div className="mt-6 flex flex-wrap items-center justify-between gap-4 border-3 border-ink bg-offwhite p-4" data-testid="selected-file">
          <span className="flex items-center gap-2 font-mono text-sm"><FileText size={18} /> {file.name}</span>
          <Button variant="primary" onClick={upload} data-testid="analyze-resume-button">Analyze resume</Button>
        </div>
      )}
    </div>
  );
}
