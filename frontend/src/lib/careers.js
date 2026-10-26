import { useEffect, useState } from "react";
import api from "./api";

let cache = null;
export function useSectors() {
  const [s, setS] = useState(cache || []);
  useEffect(() => {
    if (cache) return;
    api.get("/careers/sectors").then((r) => { cache = r.data.sectors; setS(cache); }).catch(() => {});
  }, []);
  return s;
}

export const LOW_COVERAGE = 25;
