import React, { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { BellPlus, Search, SlidersHorizontal } from "lucide-react";
import { toast } from "sonner";
import api, { errMsg } from "../lib/api";
import JobCard, { JobCardSkeleton } from "../components/JobCard";
import { Button, EmptyState, Spinner } from "../components/ui";

const WORK = ["All", "Remote", "Hybrid", "Onsite"];
const LEVEL = ["All", "Entry", "Mid", "Senior"];
const SELECT = "h-9 border-2 border-ink bg-white pl-3 pr-2 font-display text-sm font-semibold shadow-brutalsm outline-none cursor-pointer";

function Pills({ label, options, value, onChange, testid }) {
  return (
    <div className="flex flex-wrap sm:flex-nowrap items-center gap-1.5">
      <span className="eyebrow mr-1">{label}</span>
      {options.map((o) => (
        <button key={o} onClick={() => onChange(o)} data-testid={`${testid}-${o.toLowerCase()}`}
          className={`h-9 border-2 border-ink px-3 font-display font-semibold text-sm transition-transform hover:-translate-y-0.5 ${value === o ? "bg-ink text-white" : "bg-white"}`}>
          {o}
        </button>
      ))}
    </div>
  );
}

export default function Jobs() {
  const [params, setParams] = useSearchParams();
  const [sectors, setSectors] = useState([]);
  const [q, setQ] = useState(params.get("q") || "");
  const [f, setF] = useState({
    q: params.get("q") || "", work: params.get("work") || "All", level: params.get("level") || "All",
    source: params.get("source") || "all", country: params.get("country") || "all", sort: params.get("sort") || "best", sector: params.get("sector") || "all",
  });
  const [countries, setCountries] = useState([]);
  const [saving, setSaving] = useState(false);
  const [data, setData] = useState({ jobs: [], total: 0, has_more: false });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [sources, setSources] = useState([]);

  useEffect(() => {
    api.get("/jobs/sources").then((r) => setSources(r.data.sources));
    api.get("/careers/sectors").then((r) => setSectors(r.data.sectors)).catch(() => {});
    api.get("/jobs/countries").then((r) => setCountries(r.data.countries));
  }, []);

  const saveAlert = async () => {
    setSaving(true);
    try {
      const { sort, ...filters } = f;
      const { data: a } = await api.post("/alerts", filters);
      toast.success(`Alert saved: ${a.name}. You'll see new matching jobs in the bell.`, { id: "alert-save" });
      window.dispatchEvent(new CustomEvent("joblens:alerts-changed"));
    } catch (e) {
      toast.error(errMsg(e), { id: "alert-save" });
    }
    setSaving(false);
  };

  const load = useCallback(async (pg) => {
    setLoading(true);
    const { data: d } = await api.get("/jobs", { params: { ...f, page: pg, limit: 24 } });
    setData((prev) => (pg === 1 ? d : { ...d, jobs: [...prev.jobs, ...d.jobs] }));
    setPage(pg);
    setLoading(false);
  }, [f]);

  useEffect(() => {
    load(1);
  }, [load]);

  const upd = (k) => (v) => setF((x) => ({ ...x, [k]: v }));
  const doSearch = (e) => {
    e.preventDefault();
    setF((x) => ({ ...x, q }));
    setParams(q ? { q } : {});
  };

  return (
    <div className="mx-auto max-w-7xl px-4 md:px-8 py-12">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-5">
        <div>
          <p className="eyebrow mb-2">Live + AI matched</p>
          <h1 className="text-3xl md:text-4xl font-bold">Opportunities for you</h1>
        </div>
        <form onSubmit={doSearch} className="flex w-full md:w-auto gap-3">
          <label className="relative flex-1 md:w-80">
            <Search size={17} className="absolute left-4 top-1/2 -translate-y-1/2 text-ink/40" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search roles, e.g. React" className="brutal-input h-11 py-0 pl-11" data-testid="jobs-search-input" />
          </label>
          <Button variant="dark" className="h-11 py-0 px-6" data-testid="jobs-search-button">Search</Button>
        </form>
      </div>

      <div className="brutal-card mt-7 px-5 py-4 flex flex-wrap items-center gap-x-5 gap-y-3">
        <span className="flex items-center gap-2 font-display font-bold"><SlidersHorizontal size={17} /> Filters</span>
        <Pills label="Work" options={WORK} value={f.work} onChange={upd("work")} testid="filter-work" />
        <span className="hidden md:block h-6 w-0.5 bg-ink/15" />
        <Pills label="Level" options={LEVEL} value={f.level} onChange={upd("level")} testid="filter-level" />
        <div className="flex w-full flex-wrap items-center gap-2 border-t-2 border-ink/10 pt-3">
          <select value={f.sector} onChange={(e) => upd("sector")(e.target.value)} className={`${SELECT} w-[150px]`} data-testid="filter-sector">
            <option value="all">All sectors</option>
            {sectors.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.job_count})</option>)}
          </select>
          <select value={f.source} onChange={(e) => upd("source")(e.target.value)} className={`${SELECT} w-[112px]`} data-testid="filter-source">
            <option value="all">Source</option>
            {sources.map((s) => <option key={s.key} value={s.key}>{s.label} ({s.count})</option>)}
          </select>
          <select value={f.country} onChange={(e) => upd("country")(e.target.value)} className={`${SELECT} w-[112px]`} data-testid="filter-country">
            <option value="all">Country</option>
            {countries.map((c) => <option key={c.name} value={c.name}>{c.name} ({c.count})</option>)}
          </select>
          <select value={f.sort} onChange={(e) => upd("sort")(e.target.value)} className={`${SELECT} w-[132px] font-bold`} data-testid="sort-select">
            <option value="best">Best match</option>
            <option value="recent">Most recent</option>
            <option value="salary">Top salary</option>
          </select>
        </div>
      </div>

      <div className="mt-7 flex flex-wrap items-center justify-between gap-4">
        <p className="font-mono text-sm text-ink/60" data-testid="jobs-count">{loading && page === 1 ? "Searching live jobs…" : `${data.total.toLocaleString()} roles found`}</p>
        <Button variant="yellow" className="h-9 py-0 px-4 text-sm" onClick={saveAlert} disabled={saving} data-testid="save-alert-btn">{saving ? <Spinner /> : <BellPlus size={15} />} Job alert</Button>
      </div>
      <div className="mt-5 grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {data.jobs.map((j, i) => <JobCard key={j.id} job={j} index={i % 24} />)}
        {loading && page === 1 && Array.from({ length: 6 }).map((_, i) => <JobCardSkeleton key={i} />)}
      </div>
      {f.sector !== "all" && (sectors.find((s) => s.id === f.sector)?.job_count ?? 0) < 25 && <p className="mt-4 border-3 border-ink bg-brand-yellow/40 p-3 text-sm" data-testid="jobs-low-coverage">Our free job sources have limited coverage for this sector right now, so only a few real listings are shown. We never add sample or fake vacancies. Set an alert to hear about new ones.</p>}
      {!loading && data.jobs.length === 0 && <EmptyState title="No roles found" text="Try a different search or loosen the filters." testid="jobs-empty" />}
      {data.has_more && (
        <div className="mt-12 flex justify-center">
          <Button variant="yellow" onClick={() => load(page + 1)} disabled={loading} data-testid="jobs-load-more">{loading ? <Spinner /> : "Load more roles"}</Button>
        </div>
      )}
    </div>
  );
}
