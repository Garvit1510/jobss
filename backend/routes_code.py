import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import code_runner as cr
import judges
from ai import ask_json
from auth import current_user
from database import db

router = APIRouter(prefix="/api")
MAX_INPUT = 1_500_000
_locks = {}
_busy = set()

BUILDER_SYS = """You are a senior competitive-programming problem setter who writes judge test suites for coding interviews.
Every program reads from standard input and writes to standard output."""


def _problem_text(p):
    ex = "\n".join(f"Input:\n{e.get('input')}\nOutput:\n{e.get('output')}" for e in p.get("examples") or [])
    return (f"TITLE: {p.get('title')}\nPROBLEM: {p.get('problem')}\nINPUT FORMAT: {p.get('input_format', '')}\n"
            f"OUTPUT FORMAT: {p.get('output_format', '')}\nCONSTRAINTS: {p.get('constraints', '')}\nEXAMPLES:\n{ex}")


BUILD_PROMPT = """{problem}

Write a judge test suite for this problem.
1. "reference": a correct, efficient Python 3 solution that reads stdin and prints the answer exactly in the output format.
   If the examples are not in pure stdin form, choose a clear stdin format consistent with the problem and state it in "io_note".
2. "tests": 8-10 HIGH-VALUE tests, each targeting a specific risk, never random filler:
   - 2 "sample": the problem's own examples (as exact stdin).
   - 3-4 "edge": minimal input (n=0/1 or empty string), all-equal / duplicates, negatives or zeros, no-answer / not-found case.
   - 2 "boundary": values at constraint limits (max value, overflow risk, max length strings), off-by-one traps.
   - 1-2 "stress": maximum-size input that a brute-force O(n^2) solution would fail. For these give "generator":
     a short Python 3 script (deterministic, random.seed(7)) that PRINTS the input, instead of "input". Keep input under 1 MB.
   Each test: {{"name": str (short), "category": "sample"|"edge"|"boundary"|"stress", "why": str (what bug it catches, max 12 words),
   "input": str (exact stdin) OR "generator": str}}.
Return JSON: {{"io_note": str, "reference": str, "tests": [...]}}"""


async def _materialise(spec):
    async with cr.Program("python", spec["reference"]) as ref:
        tests = []
        for i, t in enumerate(spec.get("tests", [])[:12]):
            stdin = t.get("input")
            if t.get("generator"):
                async with cr.Program("python", t["generator"]) as gen:
                    g = await gen.run("", timeout=10)
                if g["status"] or not g["stdout"].strip():
                    continue
                stdin = g["stdout"]
            if stdin is None or len(stdin) > MAX_INPUT:
                continue
            stdin = stdin if stdin.endswith("\n") else stdin + "\n"
            r = await ref.run(stdin, timeout=10)
            if r["status"]:
                continue
            tests.append({"id": f"t{i + 1}", "name": t.get("name") or f"Test {i + 1}", "category": t.get("category", "edge"),
                          "why": t.get("why", ""), "input": stdin, "expected": r["stdout"],
                          "visible": t.get("category") in ("sample", "edge") and len(stdin) <= 2000})
        return tests


def _samples_ok(problem, tests):
    exp = [e.get("output", "") for e in problem.get("examples") or []]
    got = [t["expected"] for t in tests if t["category"] == "sample"]
    return not exp or any(any(cr.same_output(g, e) for g in got) for e in exp)


async def build_tests(problem):
    for _ in range(2):
        spec = await ask_json(BUILDER_SYS, BUILD_PROMPT.format(problem=_problem_text(problem)))
        if not spec.get("reference"):
            continue
        tests = await _materialise(spec)
        if len(tests) >= 3 and _samples_ok(problem, tests):
            return {"io_note": spec.get("io_note", ""), "tests": tests}
    raise HTTPException(503, "Could not prepare reliable test cases for this problem right now. Please try again.")


async def get_tests(key, problem):
    doc = await db.code_tests.find_one({"key": key}, {"_id": 0})
    if doc:
        return doc
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        doc = await db.code_tests.find_one({"key": key}, {"_id": 0})
        if not doc:
            doc = {"id": str(uuid.uuid4()), "key": key, **await build_tests(problem), "created_at": datetime.now(timezone.utc).isoformat()}
            await db.code_tests.insert_one({**doc})
    _locks.pop(key, None)
    return doc


async def run_suite(lang, code, tests):
    async with cr.Program(lang, code) as prog:
        err = await prog.compile()
        if err:
            return {"compile_error": err, "results": [], "passed": 0, "total": len(tests)}
        results = []
        for t in tests:
            r = await prog.run(t["input"])
            ok = not r["status"] and cr.same_output(r["stdout"], t["expected"])
            row = {"id": t["id"], "name": t["name"], "category": t["category"], "why": t["why"], "visible": t["visible"],
                   "passed": ok, "status": "Passed" if ok else (r["status"] or "Wrong Answer"), "time_ms": r["time_ms"]}
            if t["visible"]:
                row.update(input=t["input"], expected=t["expected"][:3000], got=r["stdout"][:3000], stderr=r["stderr"][-800:])
            elif not ok and r["status"] == "Runtime Error":
                row["stderr"] = r["stderr"][-800:]
            results.append(row)
        return {"compile_error": None, "results": results, "passed": sum(r["passed"] for r in results), "total": len(results)}


def summary(res):
    if res.get("compile_error"):
        return "Compilation error: " + res["compile_error"][:300]
    failed = [f"{r['name']} ({r['category']}): {r['status']}" for r in res["results"] if not r["passed"]]
    return f"{res['passed']}/{res['total']} judge tests passed." + (f" Failed: {'; '.join(failed)[:600]}" if failed else "")


async def problem_for(user_id, context, ref_id, problem_id):
    if context == "oa":
        t = await db.mock_tests.find_one({"id": ref_id, "user_id": user_id}, {"_id": 0, "test.coding": 1})
        p = next((c for c in (t or {}).get("test", {}).get("coding", []) if c.get("id") == problem_id), None)
        return (f"oa:{ref_id}:{problem_id}", p)
    s = await db.interviews.find_one({"id": ref_id, "user_id": user_id}, {"_id": 0, "turns": 1})
    idx = next((i for i in range(len((s or {}).get("turns", [])) - 1, -1, -1) if s["turns"][i].get("kind") == "coding"), None)
    return (f"iv:{ref_id}:{idx}", s["turns"][idx]["coding"] if idx is not None else None)


async def judge(key, problem, language, code):
    lang = cr.norm_lang(language)
    if not lang or not cr.available(lang) or not code.strip():
        return None
    suite = await get_tests(key, problem)
    return await run_suite(lang, code, suite["tests"])


def _check_lang(language):
    lang = cr.norm_lang(language)
    if not lang:
        raise HTTPException(400, "Run is available for Python, JavaScript, C++ and Java.")
    if not cr.available(lang):
        raise HTTPException(503, "Java is not installed on this server right now. Please use Python, JavaScript or C++.")
    return lang


class TryIn(BaseModel):
    language: str
    code: str = Field(min_length=1, max_length=20000)
    stdin: str = Field(default="", max_length=200_000)


@router.get("/code/languages")
async def code_languages(user=Depends(current_user)):
    return {"languages": [{"name": name, "available": cr.available(key)} for key, name in cr.LANGS.items()]}


@router.post("/code/try")
async def try_code(body: TryIn, user=Depends(current_user)):
    lang = _check_lang(body.language)
    if user["id"] in _busy:
        raise HTTPException(429, "Your previous run is still in progress.")
    _busy.add(user["id"])
    try:
        async with cr.Program(lang, body.code) as prog:
            err = await prog.compile()
            if err:
                return {"compile_error": err}
            r = await prog.run(body.stdin if body.stdin.endswith("\n") or not body.stdin else body.stdin + "\n")
    finally:
        _busy.discard(user["id"])
    return {"compile_error": None, "status": r["status"] or "Finished", "stdout": r["stdout"][:10000], "stderr": r["stderr"], "time_ms": r["time_ms"]}


class RunIn(BaseModel):
    context: str = Field(pattern="^(oa|interview)$")
    ref_id: str
    problem_id: str = ""
    language: str
    code: str = Field(min_length=1, max_length=20000)


@router.post("/code/run")
async def run_code(body: RunIn, user=Depends(current_user)):
    lang = _check_lang(body.language)
    key, problem = await problem_for(user["id"], body.context, body.ref_id, body.problem_id)
    if not problem:
        raise HTTPException(404, "Coding problem not found")
    if user["id"] in _busy:
        raise HTTPException(429, "Your previous run is still in progress.")
    _busy.add(user["id"])
    try:
        suite = await get_tests(key, problem)
        res = await run_suite(lang, body.code, suite["tests"])
    finally:
        _busy.discard(user["id"])
    return {**res, "io_note": suite.get("io_note", "")}


async def _oa_item(user_id, ref_id, kind, problem_id):
    t = await db.mock_tests.find_one({"id": ref_id, "user_id": user_id}, {"_id": 0, f"test.{kind}": 1})
    p = next((c for c in (t or {}).get("test", {}).get(kind, []) if c.get("id") == problem_id), None)
    if not p:
        raise HTTPException(404, "Question not found")
    return p


async def _guard(user_id, coro):
    if user_id in _busy:
        raise HTTPException(429, "Your previous run is still in progress.")
    _busy.add(user_id)
    try:
        return await coro
    finally:
        _busy.discard(user_id)


class SqlRunIn(BaseModel):
    ref_id: str
    problem_id: str
    query: str = Field(min_length=1, max_length=20000)


@router.post("/code/sql/run")
async def sql_run(body: SqlRunIn, user=Depends(current_user)):
    p = await _oa_item(user["id"], body.ref_id, "sql", body.problem_id)
    res = await _guard(user["id"], judges.sql_suite(body.query, p))
    return {**res, "verdict": judges.verdict(res)}


class SqlTryIn(BaseModel):
    query: str = Field(min_length=1, max_length=20000)
    setup: str = Field(default="", max_length=200_000)


@router.post("/code/sql/try")
async def sql_try(body: SqlTryIn, user=Depends(current_user)):
    out = (await _guard(user["id"], judges.run_sql(body.query, [body.setup])))[0]
    return {"error": out.get("error"), "columns": out.get("columns", []), "rows": (out.get("rows") or [])[:200]}


class WebRunIn(BaseModel):
    ref_id: str
    problem_id: str
    html: str = Field(default="", max_length=60000)
    css: str = Field(default="", max_length=60000)
    js: str = Field(default="", max_length=60000)


@router.post("/code/web/run")
async def web_run(body: WebRunIn, user=Depends(current_user)):
    p = await _oa_item(user["id"], body.ref_id, "web", body.problem_id)
    res = await _guard(user["id"], judges.web_suite(body.html, body.css, body.js, p))
    return {**res, "verdict": judges.verdict(res)}
