import React, { useCallback, useEffect, useState } from "react";
import { Ban } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";
import { timeAgo } from "../../lib/format";
import { Badge, Button, EmptyState, Spinner } from "../ui";

const short = (s) => (s && s.length > 14 ? `${s.slice(0, 6)}…${s.slice(-6)}` : s || "—");

function BanRow({ b, onUnban, busy }) {
  return (
    <tr className="border-t-2 border-ink/10 align-top" data-testid={`ban-row-${b.id}`}>
      <td className="p-3"><p className="font-semibold">{b.user_email || "—"}</p><p className="text-xs text-ink/50">{b.user_name}</p></td>
      <td className="p-3 font-mono text-xs">{b.attempted_email || "—"}</td>
      <td className="p-3 font-mono text-xs" title={b.device_id}>{short(b.device_id)}</td>
      <td className="p-3 font-mono text-xs">{b.ip}</td>
      <td className="p-3 text-xs">{b.reason?.replace("_", " ")}<p className="text-ink/50">{timeAgo(b.created_at)}</p></td>
      <td className="p-3">
        {b.active ? <Badge tone="red">Active</Badge> : <><Badge tone="green">Lifted</Badge><p className="mt-1 text-[11px] text-ink/50">by {b.unbanned_by}</p></>}
      </td>
      <td className="p-3 text-right">
        {b.active && <Button variant="green" className="py-1.5 px-3 text-sm" disabled={busy} onClick={() => onUnban(b)} data-testid={`unban-ban-${b.id}`}>{busy ? <Spinner /> : "Unban"}</Button>}
      </td>
    </tr>
  );
}

export default function BansTable({ onChange }) {
  const [status, setStatus] = useState("active");
  const [bans, setBans] = useState(null);
  const [busy, setBusy] = useState("");
  const load = useCallback(() => api.get("/admin/bans", { params: { status } }).then((r) => setBans(r.data.bans)).catch((e) => toast.error(errMsg(e))), [status]);
  useEffect(() => { setBans(null); load(); }, [load]);
  const unban = async (b) => {
    if (!window.confirm(`Lift this ban? Device ${short(b.device_id)}, IP ${b.ip} and account ${b.user_email || ""} will be able to sign in again.`)) return;
    setBusy(b.id);
    try {
      await api.post(`/admin/bans/${b.id}/unban`);
      toast.success("Ban lifted");
      load();
      onChange();
    } catch (e) {
      toast.error(errMsg(e));
    }
    setBusy("");
  };
  return (
    <div data-testid="admin-bans">
      <div className="mb-4 flex gap-2">
        {["active", "lifted", "all"].map((s) => (
          <button key={s} onClick={() => setStatus(s)} className={`border-2 border-ink px-3 py-1 font-display text-sm font-semibold capitalize ${status === s ? "bg-brand-yellow" : "bg-white"}`} data-testid={`bans-filter-${s}`}>{s}</button>
        ))}
      </div>
      {bans === null ? <p className="flex items-center gap-2 text-sm"><Spinner /> Loading bans…</p> : !bans.length ? (
        <EmptyState icon={Ban} title="No bans here" text="Multiple-account violations will show up here." testid="bans-empty" />
      ) : (
        <div className="brutal-card overflow-x-auto">
          <table className="w-full min-w-[860px] text-left text-sm">
            <thead className="bg-ink text-white font-display"><tr>{["Linked account", "Attempted email", "Device", "IP", "Reason", "Status", ""].map((h) => <th key={h} className="p-3 font-semibold">{h}</th>)}</tr></thead>
            <tbody>{bans.map((b) => <BanRow key={b.id} b={b} busy={busy === b.id} onUnban={unban} />)}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}
