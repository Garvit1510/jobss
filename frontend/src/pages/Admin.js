import React, { useCallback, useEffect, useState } from "react";
import { Ban, ShieldCheck, UserX, Users } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../lib/api";
import { Card } from "../components/ui";
import BansTable from "../components/admin/BansTable";
import UsersTable from "../components/admin/UsersTable";
import OACompanies from "../components/admin/OACompanies";
import Moderation from "../components/admin/Moderation";
import ProctorPhotos from "../components/admin/ProctorPhotos";
import AccentureMocks from "../components/admin/AccentureMocks";

const STATS = [
  { k: "users", label: "Users", icon: Users, bg: "bg-white" },
  { k: "banned_users", label: "Banned accounts", icon: UserX, bg: "bg-brand-red/20" },
  { k: "active_bans", label: "Active bans", icon: Ban, bg: "bg-brand-yellow" },
  { k: "lifted_bans", label: "Lifted bans", icon: ShieldCheck, bg: "bg-brand-green/30" },
];

export default function Admin() {
  const [tab, setTab] = useState("bans");
  const [stats, setStats] = useState(null);
  const load = useCallback(() => api.get("/admin/stats").then((r) => setStats(r.data)).catch((e) => toast.error(errMsg(e))), []);
  useEffect(() => { load(); }, [load]);
  return (
    <div className="mx-auto max-w-7xl px-4 md:px-8 py-12" data-testid="admin-page">
      <p className="eyebrow mb-2">Bans · accounts · company OAs</p>
      <h1 className="text-4xl md:text-5xl font-bold">Admin console</h1>
      <div className="mt-8 grid grid-cols-2 lg:grid-cols-4 gap-4">
        {STATS.map(({ k, label, icon: I, bg }) => (
          <Card key={k} className={`p-5 ${bg}`} data-testid={`admin-stat-${k}`}>
            <p className="flex items-center gap-2 font-display font-semibold text-sm"><I size={16} /> {label}</p>
            <p className="mt-2 font-mono text-3xl font-bold">{stats ? stats[k] : "–"}</p>
          </Card>
        ))}
      </div>
      <div className="mt-10 flex flex-wrap gap-2">
        {[["bans", "Bans"], ["users", "Users"], ["proctor", "Proctoring photos"], ["oa", "Company OAs"], ["accenture", "Accenture mocks"], ["community", "Community"]].map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} className={`brutal-btn py-2 ${tab === k ? "bg-ink text-white" : "bg-white"}`} data-testid={`admin-tab-${k}`}>{l}</button>
        ))}
      </div>
      <div className="mt-6">{tab === "bans" ? <BansTable onChange={load} /> : tab === "users" ? <UsersTable onChange={load} /> : tab === "community" ? <Moderation /> : tab === "proctor" ? <ProctorPhotos /> : tab === "accenture" ? <AccentureMocks /> : <OACompanies />}</div>
    </div>
  );
}
