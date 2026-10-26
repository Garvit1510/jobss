import { useEffect, useState } from "react";
import api from "./api";

let cache = null;
export function useSectors() {
  const [s, setS] = useState(cache || []);
  useEffect(() => {
    if (Array.isArray(cache) && cache.length) return undefined;
    let active = true;
    let retry;
    const load = () => {
      api.get("/careers/sectors").then((r) => {
        const sectors = r.data?.sectors;
        if (!Array.isArray(sectors) || !sectors.length) throw new Error("Sector list response was empty or invalid");
        cache = sectors;
        if (active) setS(sectors);
      }).catch((error) => {
        console.error("Could not load career fields:", error);
        if (active) retry = setTimeout(load, 5000);
      });
    };
    load();
    return () => {
      active = false;
      clearTimeout(retry);
    };
  }, []);
  return s;
}

export const LOW_COVERAGE = 25;
