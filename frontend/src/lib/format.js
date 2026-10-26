function money(v, cur) {
  if (cur === "INR") {
    if (v >= 1e7) return `₹${+(v / 1e7).toFixed(1)}Cr`;
    if (v >= 1e5) return `₹${+(v / 1e5).toFixed(1)}L`;
    return `₹${Math.round(v).toLocaleString("en-IN")}`;
  }
  try {
    return new Intl.NumberFormat("en", { style: "currency", currency: cur, notation: "compact", maximumFractionDigits: 1 })
      .format(v)
      .replace("K", "k");
  } catch {
    return `${cur} ${Math.round(v).toLocaleString()}`;
  }
}

const PERIOD = { hour: "/hr", hourly: "/hr", month: "/mo", monthly: "/mo", week: "/wk", day: "/day", daily: "/day" };

export function formatSalary(s) {
  if (!s) return null;
  if (s.text) return s.text;
  const suf = PERIOD[s.period] || "";
  if (s.min && s.max && s.min !== s.max) return `${money(s.min, s.currency)} - ${money(s.max, s.currency)}${suf}`;
  return `${money(s.min || s.max, s.currency)}${suf}`;
}

export function timeAgo(iso) {
  if (!iso) return "";
  const d = (Date.now() - new Date(iso).getTime()) / 1000;
  if (d < 3600) return `${Math.max(1, Math.round(d / 60))}m ago`;
  if (d < 86400) return `${Math.round(d / 3600)}h ago`;
  if (d < 86400 * 30) return `${Math.round(d / 86400)}d ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}
