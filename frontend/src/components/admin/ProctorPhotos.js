import React, { useCallback, useEffect, useState } from "react";
import { Camera, ChevronDown, ShieldAlert, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";
import { timeAgo } from "../../lib/format";
import { Badge, Button, EmptyState, Spinner } from "../ui";

const LABEL = { registered: "Registered face", tab_switch: "Tab switch", multiple_faces: "Multiple faces", different_person: "Different person", no_face: "No face",
  phone_detected: "Phone detected", gaze_away: "Looking away", loud_noise: "Loud noise", background_voice: "Background voice", camera_blocked: "Camera blocked",
  mic_off: "Mic off", fullscreen_exit: "Left fullscreen", copy_paste: "Copy/paste" };

// Images are admin-only endpoints (cookie auth), so load them as blobs.
function SnapImage({ id, className, onClick }) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    let u = null;
    api.get(`/admin/proctor/snaps/${id}/image`, { responseType: "blob" }).then((r) => { u = URL.createObjectURL(r.data); setUrl(u); }).catch(() => setUrl(""));
    return () => u && URL.revokeObjectURL(u);
  }, [id]);
  if (url === null) return <div className={`flex items-center justify-center bg-offwhite ${className}`}><Spinner /></div>;
  if (!url) return <div className={`flex items-center justify-center bg-offwhite text-xs text-ink/50 ${className}`}>unavailable</div>;
  return <img src={url} alt="Proctoring capture" className={`cursor-zoom-in object-cover ${className}`} onClick={() => onClick(url)} />;
}

function Snap({ s, onDelete, onZoom }) {
  const reg = s.type === "registered";
  return (
    <div className={`border-3 ${reg ? "border-brand-green" : "border-brand-red"} bg-white`} data-testid={`proctor-snap-${s.id}`}>
      <SnapImage id={s.id} className="aspect-[4/3] w-full -scale-x-100" onClick={onZoom} />
      <div className="flex items-start justify-between gap-2 p-2">
        <div className="min-w-0">
          <p className={`font-display text-xs font-bold ${reg ? "text-brand-green" : "text-brand-red"}`}>{LABEL[s.type] || s.type}</p>
          <p className="truncate font-mono text-[10px] text-ink/60" title={s.detail}>{new Date(s.at).toLocaleString()}{s.detail ? ` · ${s.detail}` : ""}</p>
        </div>
        <button onClick={() => onDelete(s)} className="text-brand-red" aria-label="Delete photo" data-testid={`proctor-snap-delete-${s.id}`}><Trash2 size={14} /></button>
      </div>
    </div>
  );
}

function SessionRow({ r, onChanged }) {
  const [open, setOpen] = useState(false);
  const [snaps, setSnaps] = useState(null);
  const [zoom, setZoom] = useState(null);
  const load = useCallback(() => api.get(`/admin/proctor/sessions/${r.ref_id}`).then((x) => setSnaps(x.data.snaps)).catch((e) => toast.error(errMsg(e))), [r.ref_id]);
  useEffect(() => { if (open) load(); }, [open, load]);
  const del = async (s) => {
    if (!window.confirm("Delete this photo permanently?")) return;
    try { await api.delete(`/admin/proctor/snaps/${s.id}`); setSnaps((l) => l.filter((x) => x.id !== s.id)); onChanged(); } catch (e) { toast.error(errMsg(e)); }
  };
  const delAll = async () => {
    if (!window.confirm(`Delete all ${r.photos} photos of this session permanently?`)) return;
    try { await api.delete(`/admin/proctor/sessions/${r.ref_id}`); toast.success("Session photos deleted"); onChanged(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="brutal-card" data-testid={`proctor-session-${r.ref_id}`}>
      <div className="flex flex-wrap items-center gap-3 p-4">
        <button onClick={() => setOpen(!open)} className="flex min-w-0 flex-1 items-center gap-3 text-left" data-testid={`proctor-session-toggle-${r.ref_id}`}>
          <ChevronDown size={16} className={`shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
          <div className="min-w-0">
            <p className="font-display font-bold">{r.user_name || "Unknown user"} <span className="font-mono text-xs font-normal text-ink/60">{r.user_email}</span> {r.user_banned && <Badge tone="red">Banned</Badge>}</p>
            <p className="truncate font-mono text-[11px] text-ink/60">{r.kind === "oa" ? "Mock OA" : "AI interview"} · {r.title} · {timeAgo(r.last_at)}</p>
          </div>
        </button>
        <span className={`flex items-center gap-1 font-mono text-xs font-bold ${r.flags ? "text-brand-red" : "text-brand-green"}`}><ShieldAlert size={14} /> {r.flags} flag photo{r.flags === 1 ? "" : "s"}</span>
        <Button className="h-9 py-0 px-3 text-sm" onClick={delAll} data-testid={`proctor-session-delete-${r.ref_id}`}><Trash2 size={14} /> Delete all</Button>
      </div>
      {open && <div className="border-t-3 border-ink p-4">
        {snaps === null ? <p className="flex items-center gap-2 text-sm"><Spinner /> Loading photos…</p> : !snaps.length ? <p className="text-sm text-ink/60">No photos left.</p> : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">{snaps.map((s) => <Snap key={s.id} s={s} onDelete={del} onZoom={setZoom} />)}</div>
        )}
      </div>}
      {zoom && <div className="fixed inset-0 z-[120] flex items-center justify-center bg-ink/90 p-6" onClick={() => setZoom(null)} data-testid="proctor-zoom">
        <img src={zoom} alt="Proctoring capture enlarged" className="max-h-full max-w-full -scale-x-100 border-3 border-white" />
        <button className="absolute right-5 top-5 text-white" aria-label="Close"><X size={28} /></button>
      </div>}
    </div>
  );
}

export default function ProctorPhotos() {
  const [rows, setRows] = useState(null);
  const load = useCallback(() => api.get("/admin/proctor/sessions").then((r) => setRows(r.data.sessions)).catch((e) => toast.error(errMsg(e))), []);
  useEffect(() => { load(); }, [load]);
  return (
    <div className="space-y-4" data-testid="admin-proctor">
      <p className="text-sm text-ink/70">Registered face photos and the camera frame captured at every proctoring flag in proctored Mock OAs and AI interviews. Only admins can see these.</p>
      {rows === null ? <p className="flex items-center gap-2 text-sm"><Spinner /> Loading…</p> : !rows.length ? (
        <EmptyState icon={Camera} title="No proctoring photos yet" testid="proctor-empty" />
      ) : rows.map((r) => <SessionRow key={r.ref_id} r={r} onChanged={load} />)}
    </div>
  );
}
