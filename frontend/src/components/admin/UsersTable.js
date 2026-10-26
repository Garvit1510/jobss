import React, { useCallback, useEffect, useState } from "react";
import { Search, Users } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";
import { timeAgo } from "../../lib/format";
import { Badge, Button, EmptyState, Spinner } from "../ui";

function UserRow({ u, onUnban, onBan, busy }) {
  return (
    <tr className="border-t-2 border-ink/10" data-testid={`user-row-${u.id}`}>
      <td className="p-3"><p className="font-semibold">{u.name}</p><p className="font-mono text-xs text-ink/60">{u.email}</p></td>
      <td className="p-3 text-xs">{timeAgo(u.created_at)}</td>
      <td className="p-3 text-xs">{u.last_login_at ? timeAgo(u.last_login_at) : "—"}</td>
      <td className="p-3 font-mono text-xs">{u.last_login_ip || u.register_ip || "—"}</td>
      <td className="p-3">{u.banned ? <Badge tone="red">Banned</Badge> : <Badge tone="green">Active</Badge>}{u.banned && u.ban_reason && <p className="mt-1 max-w-[200px] truncate text-[11px] text-ink/60" title={u.ban_reason}>{u.ban_reason}</p>}</td>
      <td className="p-3 text-right">
        {u.banned ? <Button variant="green" className="py-1.5 px-3 text-sm" disabled={busy} onClick={() => onUnban(u)} data-testid={`unban-user-${u.id}`}>{busy ? <Spinner /> : "Unban"}</Button>
          : <Button className="py-1.5 px-3 text-sm bg-brand-red text-white" disabled={busy} onClick={() => onBan(u)} data-testid={`ban-user-${u.id}`}>{busy ? <Spinner /> : "Ban"}</Button>}
      </td>
    </tr>
  );
}

export default function UsersTable({ onChange }) {
  const [q, setQ] = useState("");
  const [onlyBanned, setOnlyBanned] = useState(false);
  const [users, setUsers] = useState(null);
  const [busy, setBusy] = useState("");
  const load = useCallback(() => api.get("/admin/users", { params: { q, banned: onlyBanned ? "true" : "" } })
    .then((r) => setUsers(r.data.users)).catch((e) => toast.error(errMsg(e))), [q, onlyBanned]);
  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [load]);
  const unban = async (u) => {
    if (!window.confirm(`Unban ${u.email}? All bans linked to this account (device + IP) will be lifted.`)) return;
    setBusy(u.id);
    try {
      await api.post(`/admin/users/${u.id}/unban`);
      toast.success(`${u.email} unbanned`);
      load();
      onChange();
    } catch (e) {
      toast.error(errMsg(e));
    }
    setBusy("");
  };
  const ban = async (u) => {
    const reason = window.prompt(`Ban ${u.email}? They will be logged out and blocked from signing in.\n\nReason (shown to the user):`, "Violation of the platform rules");
    if (reason === null) return;
    const blockDevice = window.confirm("Also block their device and network (stops new sign-ups from it)?\n\nOK = yes, Cancel = account only");
    setBusy(u.id);
    try {
      await api.post(`/admin/users/${u.id}/ban`, { reason, block_device: blockDevice });
      toast.success(`${u.email} banned`);
      load();
      onChange();
    } catch (e) {
      toast.error(errMsg(e));
    }
    setBusy("");
  };
  return (
    <div data-testid="admin-users">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <label className="relative block flex-1 min-w-[220px]">
          <Search size={17} className="absolute left-4 top-1/2 -translate-y-1/2 text-ink/40" />
          <input className="brutal-input pl-11" placeholder="Search by name or email" value={q} onChange={(e) => setQ(e.target.value)} data-testid="admin-user-search" />
        </label>
        <button onClick={() => setOnlyBanned(!onlyBanned)} className={`border-2 border-ink px-3 py-2 font-display text-sm font-semibold ${onlyBanned ? "bg-brand-red text-white" : "bg-white"}`} data-testid="admin-banned-only">Banned only</button>
      </div>
      {users === null ? <p className="flex items-center gap-2 text-sm"><Spinner /> Loading users…</p> : !users.length ? (
        <EmptyState icon={Users} title="No users found" testid="users-empty" />
      ) : (
        <div className="brutal-card overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="bg-ink text-white font-display"><tr>{["User", "Joined", "Last login", "IP", "Status", ""].map((h) => <th key={h} className="p-3 font-semibold">{h}</th>)}</tr></thead>
            <tbody>{users.map((u) => <UserRow key={u.id} u={u} busy={busy === u.id} onUnban={unban} onBan={ban} />)}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}
