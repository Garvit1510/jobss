import asyncio
import json
import os
import subprocess

import code_runner as cr

WEBJUDGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webjudge")
JSDOM = os.path.join(WEBJUDGE_DIR, "node_modules", "jsdom")

SQL_SCRIPT = r'''
import sys, json, sqlite3, time, math, datetime
d = json.load(sys.stdin)

def _dt(v):
    try:
        return datetime.datetime.fromisoformat(str(v)[:19])
    except Exception:
        return None

def shim(con):
    f = con.create_function
    f("CONCAT", -1, lambda *a: None if any(x is None for x in a) else "".join(str(x) for x in a))
    f("CONCAT_WS", -1, lambda s, *a: str(s).join(str(x) for x in a if x is not None))
    f("YEAR", 1, lambda v: _dt(v).year if _dt(v) else None)
    f("MONTH", 1, lambda v: _dt(v).month if _dt(v) else None)
    f("DAY", 1, lambda v: _dt(v).day if _dt(v) else None)
    f("DAYOFMONTH", 1, lambda v: _dt(v).day if _dt(v) else None)
    f("DATEDIFF", 2, lambda a, b: (_dt(a) - _dt(b)).days if _dt(a) and _dt(b) else None)
    f("NOW", 0, lambda: "2024-01-01 00:00:00")
    f("CURDATE", 0, lambda: "2024-01-01")
    f("FLOOR", 1, lambda v: None if v is None else math.floor(v))
    f("CEIL", 1, lambda v: None if v is None else math.ceil(v))
    f("CEILING", 1, lambda v: None if v is None else math.ceil(v))
    f("POWER", 2, lambda a, b: None if a is None or b is None else a ** b)
    f("POW", 2, lambda a, b: None if a is None or b is None else a ** b)
    f("SQRT", 1, lambda v: None if v is None else math.sqrt(v))
    f("MOD", 2, lambda a, b: None if a is None or not b else a % b)
    f("TRUNCATE", 2, lambda v, n: None if v is None else math.trunc(v * 10 ** n) / 10 ** n)

def split(sql):
    out, buf = [], ""
    for part in sql.split(";"):
        buf += part + ";"
        if sqlite3.complete_statement(buf):
            if buf.strip(" \n\t;"):
                out.append(buf.strip())
            buf = ""
    if buf.strip(" \n\t;"):
        out.append(buf.strip())
    return out

res = []
for setup in d["setups"]:
    con = sqlite3.connect(":memory:")
    shim(con)
    try:
        con.executescript(setup)
    except Exception as e:
        res.append({"error": "Setup failed: " + str(e)})
        continue
    t0 = time.time()
    con.set_progress_handler(lambda: 1 if time.time() - t0 > 3 else 0, 20000)
    cols, rows, err = [], [], None
    try:
        for st in split(d["query"]):
            cur = con.execute(st)
            if cur.description:
                cols = [c[0] for c in cur.description]
                rows = [list(r) for r in cur.fetchmany(1001)]
    except Exception as e:
        err = "Time Limit Exceeded" if "interrupted" in str(e) else str(e)
    res.append({"error": err, "columns": cols, "rows": rows})
print(json.dumps(res, default=str))
'''


def _cell(v):
    if v is None:
        return "NULL"
    if isinstance(v, float):
        return f"{round(v, 2):.2f}".rstrip("0").rstrip(".") if v != int(v) else str(int(v))
    s = str(v).strip()
    try:
        f = float(s)
        if "." in s:
            return f"{round(f, 2):.2f}".rstrip("0").rstrip(".") if f != int(f) else str(int(f))
    except ValueError:
        pass
    return s


def norm_rows(rows, ordered):
    r = [[_cell(c) for c in row] for row in rows]
    return r if ordered else sorted(r)


async def run_sql(query, setups, isolated=False, _verifying=False):
    async with cr.Program("python", SQL_SCRIPT, isolated=isolated, _verifying=_verifying) as prog:
        r = await prog.run(json.dumps({"query": query, "setups": setups}), timeout=4 + 3 * len(setups))
    if r["status"]:
        return [{"error": r["status"] if r["status"] != "Runtime Error" else (r["stderr"][-400:] or "Runtime Error")}] * len(setups)
    try:
        return json.loads(r["stdout"])
    except ValueError:
        return [{"error": "Could not read the query output."}] * len(setups)


async def sql_suite(query, p, isolated=False):
    tests = p["tests"]
    outs = await run_sql(query, [p["schema"] + "\n" + t["data"] for t in tests], isolated)
    results = []
    for t, o in zip(tests, outs):
        if o.get("error"):
            status, ok = "Error", False
        else:
            ok = len(o["columns"]) == len(t["expected"]["columns"]) and norm_rows(o["rows"], p.get("ordered")) == norm_rows(t["expected"]["rows"], p.get("ordered"))
            status = "Passed" if ok else "Wrong Answer"
        row = {"id": t["id"], "name": t["name"], "category": t["category"], "why": t.get("why", ""), "visible": t["visible"], "passed": ok, "status": status, "time_ms": 0}
        if o.get("error"):
            row["stderr"] = o["error"][:800]
        if t["visible"]:
            row.update(expected_table=t["expected"], got_table={"columns": o.get("columns", []), "rows": (o.get("rows") or [])[:200]})
        results.append(row)
    return {"compile_error": None, "results": results, "passed": sum(r["passed"] for r in results), "total": len(results)}


WEB_SCRIPT = r'''
const { JSDOM, VirtualConsole } = require(%s);
const input = JSON.parse(require("fs").readFileSync(0, "utf8"));
function build(h, c, j) {
  const style = `<style>${c}</style>`, script = `<script>${j}<\/script>`;
  if (/<html[\s>]/i.test(h)) {
    let d = /<\/head>/i.test(h) ? h.replace(/<\/head>/i, style + "</head>") : h.replace(/<body[^>]*>/i, (m) => m + style);
    return /<\/body>/i.test(d) ? d.replace(/<\/body>/i, script + "</body>") : d + script;
  }
  return `<!DOCTYPE html><html><head>${style}</head><body>${h}${script}</body></html>`;
}
const withTimeout = (p, ms) => Promise.race([p, new Promise((_, r) => setTimeout(() => r(new Error("Test timed out")), ms))]);
(async () => {
  const out = [];
  for (const t of input.tests) {
    const vc = new VirtualConsole();
    let pageErr = null;
    vc.on("jsdomError", (e) => { pageErr = pageErr || String(e.message || e); });
    const dom = new JSDOM(build(input.html, input.css, input.js), { runScripts: "dangerously", pretendToBeVisual: true, virtualConsole: vc });
    const w = dom.window;
    await new Promise((r) => (w.document.readyState === "complete" ? r() : w.addEventListener("load", r)));
    await new Promise((r) => setTimeout(r, 30));
    try {
      w.__t = new w.Function("document", "window", `return (async () => { ${t.script}\n })();`);
      const ok = await withTimeout(Promise.resolve(w.__t(w.document, w)), 1500);
      out.push({ id: t.id, passed: !!ok, error: ok ? null : (pageErr ? "Page error: " + pageErr : null) });
    } catch (e) {
      out.push({ id: t.id, passed: false, error: String(e && e.message || e).slice(0, 300) });
    }
    w.close();
  }
  console.log(JSON.stringify(out));
  process.exit(0);
})();
'''


async def run_web(html, css, js, tests, isolated=False, _verifying=False):
    code = WEB_SCRIPT % json.dumps("/webjudge/node_modules/jsdom" if isolated else JSDOM)
    async with cr.Program("javascript", code, isolated=isolated, _verifying=_verifying) as prog:
        r = await prog.run(json.dumps({"html": html, "css": css, "js": js, "tests": [{"id": t["id"], "script": t["script"]} for t in tests]}),
                           timeout=6 + 1.6 * len(tests))
    if r["status"]:
        return [{"id": t["id"], "passed": False, "error": r["status"] if r["status"] != "Runtime Error" else r["stderr"][-300:]} for t in tests]
    try:
        return json.loads(r["stdout"].strip().splitlines()[-1])
    except (ValueError, IndexError):
        return [{"id": t["id"], "passed": False, "error": "Judge produced no output"} for t in tests]


async def web_suite(html, css, js, p, isolated=False):
    outs = {o["id"]: o for o in await run_web(html, css, js, p["tests"], isolated)}
    results = []
    for t in p["tests"]:
        o = outs.get(t["id"], {"passed": False, "error": "Not run"})
        row = {"id": t["id"], "name": t["name"], "category": t.get("category", "dom"), "why": t.get("why", ""), "visible": t["visible"],
               "passed": o["passed"], "status": "Passed" if o["passed"] else "Failed", "time_ms": 0}
        if o.get("error"):
            row["stderr"] = o["error"]
        results.append(row)
    return {"compile_error": None, "results": results, "passed": sum(r["passed"] for r in results), "total": len(results)}


def verdict(res):
    return "Accepted" if res and res["total"] and res["passed"] == res["total"] else "Wrong Answer"


async def ensure_webjudge():
    if os.path.isdir(JSDOM):
        return
    await asyncio.to_thread(subprocess.run, ["npm", "install", "--silent", "--no-audit", "--no-fund"], cwd=WEBJUDGE_DIR, capture_output=True)
