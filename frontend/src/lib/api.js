import axios from "axios";

export const API_BASE = `${process.env.REACT_APP_BACKEND_URL}/api`;

const api = axios.create({ baseURL: API_BASE, withCredentials: true, adapter: "fetch" });

export function errMsg(e) {
  const d = e?.response?.data?.detail;
  if (!d) return e?.message || "Something went wrong. Please try again.";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg || JSON.stringify(x)).join(" ");
  return d.msg || String(d);
}

let refreshing = null;
const AI_URL = /^\/(mock-oa\/(generate|submit)|interview\/(start|answer|finish)|resume\/upload|code\/run|learning|prepare|experiences\/insights)/;
export const aiPending = new Map();
let seq = 0;

api.interceptors.request.use((cfg) => {
  if (AI_URL.test(cfg.url || "")) {
    cfg._aiId = ++seq;
    aiPending.set(cfg._aiId, Date.now());
  }
  return cfg;
});
const doneAi = (cfg) => cfg?._aiId && aiPending.delete(cfg._aiId);

api.interceptors.response.use(
  (r) => {
    doneAi(r.config);
    return r;
  },
  async (error) => {
    const status = error?.response?.status;
    const detail = error?.response?.data?.detail;
    const cfg = error.config || {};
    doneAi(cfg);
    if (status === 503 && typeof detail === "string" && /AI/i.test(detail)) window.dispatchEvent(new CustomEvent("joblens:ai-busy"));
    if (status === 401 && detail === "SESSION_REPLACED") {
      window.dispatchEvent(new CustomEvent("joblens:session-replaced"));
    } else if (status === 403 && typeof detail === "string" && detail.includes("banned")) {
      window.dispatchEvent(new CustomEvent("joblens:banned", { detail }));
    } else if (status === 401 && detail === "Token expired" && !cfg._retry && !cfg.url?.includes("/auth/refresh")) {
      cfg._retry = true;
      try {
        refreshing = refreshing || api.post("/auth/refresh");
        await refreshing;
        refreshing = null;
        return api(cfg);
      } catch (e) {
        refreshing = null;
      }
    }
    return Promise.reject(error);
  }
);

export default api;
