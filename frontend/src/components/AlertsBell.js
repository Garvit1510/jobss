import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bell } from "lucide-react";
import api from "../lib/api";

export default function AlertsBell() {
  const [n, setN] = useState(0);
  const load = useCallback(() => api.get("/alerts/summary").then((r) => setN(r.data.total_new)).catch(() => {}), []);
  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    window.addEventListener("joblens:alerts-changed", load);
    return () => {
      clearInterval(t);
      window.removeEventListener("joblens:alerts-changed", load);
    };
  }, [load]);
  return (
    <Link to="/alerts" className="relative brutal-btn bg-white px-3 py-2" aria-label={`Job alerts, ${n} new`} data-testid="alerts-bell">
      <Bell size={18} />
      {n > 0 && (
        <span className="absolute -right-2.5 -top-2.5 min-w-[22px] border-2 border-ink bg-brand-red px-1 text-center font-mono text-[11px] font-bold text-white" data-testid="alerts-bell-count">
          {n > 99 ? "99+" : n}
        </span>
      )}
    </Link>
  );
}
