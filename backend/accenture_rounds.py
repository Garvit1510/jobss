"""Accenture Round 3 (technical MCQs) and Round 4 (coding) attempts: timers, persistence, server-side scoring and judging."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import accenture_mocks as am
import code_runner as cr
import judges
import sandbox
from auth import current_user, require_admin
from database import db

router = APIRouter(prefix="/api")
GRACE = 5
ROUND_ORDER = ["behavioural", "gamified", "technical", "coding"]
TECH_DEFAULT = {"model": "practice_v1", "official": False, "correct": 4, "wrong": -1, "unanswered": 0, "cutoff_percent": 70,
                "note": "Practice scoring: +4 correct, -1 incorrect, 0 unanswered. Round 3 % = max(0, raw score) / (4 x 45) x 100. "
                        "Not an official Accenture rule."}
CODE_DEFAULT = {"model": "practice_v1", "official": False, "visible_weight": 1, "hidden_weight": 2, "cutoff_percent": 70, "max_submissions": 10,
                "note": "Practice scoring: each task = weighted share of passed tests x 100 (visible/sample tests weight 1, hidden & edge-case tests "
                        "weight 2), best submission counts. Round 4 % = mean of the three task scores. Not an official Accenture rule."}
LANG_LABEL = {"python": "Python", "java": "Java", "cpp": "C++", "javascript": "JavaScript"}
STARTERS = {
    "python": "import sys\n\ndef main():\n    data = sys.stdin.read().split()\n    # write your solution here\n\nmain()\n",
    "java": "import java.util.*;\nimport java.io.*;\n\npublic class Main {\n    public static void main(String[] args) throws IOException {\n"
            "        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));\n        // write your solution here\n    }\n}\n",
    "cpp": "#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    ios::sync_with_stdio(false);\n    cin.tie(nullptr);\n"
           "    // write your solution here\n    return 0;\n}\n",
    "javascript": "const data = require('fs').readFileSync(0, 'utf8').trim().split(/\\s+/);\n// write your solution here\n",
}


def now():
    return datetime.now(timezone.utc)


def iso(d):
    return d.isoformat()


def _past(ts, grace=GRACE):
    return ts and now() > datetime.fromisoformat(ts) + timedelta(seconds=grace)


async def _settings(key, default):
    d = await db.acc_mock_settings.find_one({"key": key}, {"_id": 0})
    return {**default, **((d or {}).get("value") or {})}


async def _mock(user, mock_id, preview):
    if preview:
        if user.get("role") != "admin":
            raise HTTPException(403, "Preview is admin-only.")
        m = await db.acc_mocks.find_one({"mock_id": mock_id, "status": "valid"}, {"_id": 0}, sort=[("version", -1)])
        if not m:
            raise HTTPException(404, "No valid draft for this mock.")
        return m
    return await am.accessible_mock(mock_id)


async def _find(user, mock_id, rnd, preview=None):
    q = {"user_id": user["id"], "mock_id": mock_id, "round": rnd, **({} if preview is None else {"preview": preview})}
    return await db.acc_attempts.find_one(q, {"_id": 0}, sort=[("created_at", -1)])


async def _require_previous(user, mock_id, rnd, preview):
    if preview:
        return
    prev = ROUND_ORDER[ROUND_ORDER.index(rnd) - 1]
    p = await _find(user, mock_id, prev, preview=False)  # admin preview attempts never satisfy the real round order
    if not p or not p.get("finished_at"):
        raise HTTPException(409, f"Finish the {prev} round first.")


async def _load(user, mock_id, rnd):
    a = await _find(user, mock_id, rnd)
    if not a:
        raise HTTPException(404, "Round not started.")
    if not a["preview"]:
        await am.accessible_mock(mock_id)
    return a


async def _save(a, fields):
    await db.acc_attempts.update_one({"id": a["id"]}, {"$set": {**{k: a.get(k) for k in fields}, "updated_at": iso(now())}})


class StartIn(BaseModel):
    preview: bool = False


# ======================= Round 3: technical MCQs =======================
class AnswerIn(BaseModel):
    qid: str = Field(..., max_length=40)
    choice: Optional[int] = Field(None, ge=0, le=5)


def _tech_score(a, questions, sc):
    by_q = {q["qid"]: q for q in questions}
    c = w = u = 0
    cats, rows = {}, []
    for qid, q in by_q.items():
        ch = (a["responses"].get(qid) or {}).get("choice")
        st = "unanswered" if ch is None else "correct" if ch == q["answer_index"] else "incorrect"
        c, w, u = c + (st == "correct"), w + (st == "incorrect"), u + (st == "unanswered")
        k = cats.setdefault(q["category"], {"correct": 0, "incorrect": 0, "unanswered": 0})
        k[st] += 1
        rows.append({"qid": qid, "status": st, "choice": ch})
    raw = c * sc["correct"] + w * sc["wrong"] + u * sc["unanswered"]
    mx = len(by_q) * sc["correct"]
    pct = round(max(0, raw) / mx * 100, 1) if mx else 0
    return {"correct": c, "incorrect": w, "unanswered": u, "raw": raw, "max": mx, "percent": pct, "cutoff_percent": sc["cutoff_percent"],
            "passed": pct >= sc["cutoff_percent"], "by_category": cats, "rows": rows, "model": sc["model"], "official": False, "computed_at": iso(now())}


def _tech_close(a, m):
    if not a.get("finished_at") and _past(a["deadline"]):
        a["finished_at"], a["end_reason"] = iso(now()), "time_up"
    if a.get("finished_at") and not a.get("result"):
        a["result"] = _tech_score(a, m["rounds"]["technical"]["questions"], a["scoring"])
        return True
    return False


def _tech_public(a, m):
    qs = m["rounds"]["technical"]["questions"]
    done = bool(a.get("finished_at"))
    out = []
    for q in qs:
        item = {"qid": q["qid"], "category": q["category"], "category_label": am.TECH_CATEGORIES[q["category"]][0], "question": q["question"], "options": q["options"]}
        if done:
            item.update(answer_index=q["answer_index"], explanation=q.get("explanation", ""), origin=q.get("origin"), source_ref=q.get("source_ref") or None,
                        key_label=am.review_label(q))
        out.append(item)
    return {"id": a["id"], "mock_id": a["mock_id"], "preview": a["preview"], "deadline": a["deadline"], "server_time": iso(now()), "questions": out,
            "responses": {k: v.get("choice") for k, v in a["responses"].items()}, "finished_at": a.get("finished_at"), "result": a.get("result"),
            "scoring": {k: a["scoring"][k] for k in ("note", "correct", "wrong", "unanswered", "cutoff_percent")}}


T = "/accenture-mocks/{mock_id}/technical"


@router.post(T + "/start")
async def tech_start(mock_id: str, body: StartIn, user=Depends(current_user)):
    m = await _mock(user, mock_id, body.preview)
    old = await _find(user, mock_id, "technical", preview=body.preview)
    if old and not (body.preview and old.get("finished_at")):
        if _tech_close(old, m):
            await _save(old, ["finished_at", "end_reason", "result"])
        return _tech_public(old, m)
    await _require_previous(user, mock_id, "technical", body.preview)
    t = now()
    doc = {"id": str(uuid.uuid4()), "user_id": user["id"], "mock_id": mock_id, "library_id": m["library_id"], "mock_version": m["version"], "round": "technical",
           "preview": body.preview, "started_at": iso(t), "deadline": iso(t + timedelta(minutes=am.ROUND_CONFIG["technical"]["minutes"])), "responses": {},
           "scoring": await _settings("technical_scoring", TECH_DEFAULT), "created_at": iso(t)}
    from accenture_proctor import oa_config
    doc["proctoring_policy"] = (await oa_config(m))["proctoring"]
    await db.acc_attempts.insert_one(dict(doc))
    return _tech_public(doc, m)


async def _tech_ctx(user, mock_id):
    a = await _load(user, mock_id, "technical")
    m = await db.acc_mocks.find_one({"library_id": a["library_id"], "mock_id": mock_id}, {"_id": 0})
    if _tech_close(a, m):
        await _save(a, ["finished_at", "end_reason", "result"])
    return a, m


@router.get(T)
async def tech_get(mock_id: str, user=Depends(current_user)):
    a, m = await _tech_ctx(user, mock_id)
    return _tech_public(a, m)


@router.post(T + "/answer")
async def tech_answer(mock_id: str, body: AnswerIn, user=Depends(current_user)):
    a, m = await _tech_ctx(user, mock_id)
    if a.get("finished_at"):
        raise HTTPException(409, "Round 3 is closed.")
    q = next((x for x in m["rounds"]["technical"]["questions"] if x["qid"] == body.qid), None)
    if not q or (body.choice is not None and body.choice >= len(q["options"])):
        raise HTTPException(400, "Invalid question or option.")
    await db.acc_attempts.update_one({"id": a["id"]}, {"$set": {f"responses.{body.qid}": {"choice": body.choice, "at": iso(now())}}})
    return {"ok": True, "qid": body.qid, "choice": body.choice}


@router.post(T + "/submit")
async def tech_submit(mock_id: str, user=Depends(current_user)):
    a, m = await _tech_ctx(user, mock_id)
    if not a.get("finished_at"):
        a["finished_at"], a["end_reason"] = iso(now()), "submitted"
        _tech_close(a, m)
        await _save(a, ["finished_at", "end_reason", "result"])
    return _tech_public(a, m)


# ======================= Round 4: coding =======================
class CodeIn(BaseModel):
    lang: Optional[str] = Field(None, max_length=20)
    code: str = Field("", max_length=60000)
    html: str = Field("", max_length=60000)
    css: str = Field("", max_length=30000)
    js: str = Field("", max_length=60000)


def _dsa_tests(p):
    vis = [{"id": f"s{i + 1}", "name": f"Sample {i + 1}", "category": "sample", "visible": True, "input": s["input"], "expected": s["output"]} for i, s in enumerate(p["samples"])]
    hid = [{"id": t["id"], "name": f"Hidden {i + 1}", "category": "hidden", "visible": False, "input": t["input"], "expected": t["expected"]} for i, t in enumerate(p["hidden_tests"])]
    return vis + hid


async def _judge_dsa(p, lang, code, visible_only):
    tests = [t for t in _dsa_tests(p) if t["visible"] or not visible_only]
    if not cr.available(lang):
        raise HTTPException(400, f"{LANG_LABEL.get(lang, lang)} is not available on this server.")
    async with cr.Program(lang, code, isolated=True) as prog:
        err = await prog.compile()
        if err:
            return {"compile_error": err, "results": [{"id": t["id"], "name": t["name"], "category": t["category"], "visible": t["visible"], "passed": False,
                                                        "status": "Compilation Error"} for t in tests], "passed": 0, "total": len(tests)}
        rows = []
        for t in tests:
            r = await prog.run(t["input"])
            ok = not r["status"] and cr.same_output(r["stdout"], t["expected"])
            row = {"id": t["id"], "name": t["name"], "category": t["category"], "visible": t["visible"], "passed": ok,
                   "status": "Passed" if ok else (r["status"] or "Wrong Answer"), "time_ms": r["time_ms"]}
            if t["visible"]:
                row.update(input=t["input"], expected=t["expected"], got=r["stdout"][:4000], stderr=r["stderr"][-1500:])
            rows.append(row)
    return {"compile_error": None, "results": rows, "passed": sum(r["passed"] for r in rows), "total": len(rows)}


RUNNER_DOWN = ("The secure code runner is unavailable, so code is not executed (fail-closed). Your draft is saved; try again later or contact the admin.")


async def _judge(p, body, visible_only):
    """Candidate code only ever runs in the verified sandbox jail; never on the legacy runner."""
    if not sandbox.ready():
        raise HTTPException(503, RUNNER_DOWN)
    try:
        if p["type"] == "dsa":
            lang = cr.norm_lang(body.lang or "python")
            return await _judge_dsa(p, lang, body.code, visible_only)
        pp = {**p, "tests": [t for t in p["tests"] if t["visible"] or not visible_only]}
        if p["type"] == "sql":
            if not body.code.strip():
                raise HTTPException(400, "Write a query first.")
            return await judges.sql_suite(body.code, pp, isolated=True)
        return await judges.web_suite(body.html, body.css, body.js, pp, isolated=True)
    except sandbox.Unavailable:
        raise HTTPException(503, RUNNER_DOWN)


def _weighted(res, sc):
    tot = sum(sc["visible_weight"] if r["visible"] else sc["hidden_weight"] for r in res["results"])
    got = sum(sc["visible_weight"] if r["visible"] else sc["hidden_weight"] for r in res["results"] if r["passed"])
    return round(100 * got / tot, 1) if tot else 0


def _candidate_view(res):
    """Hidden tests: pass/fail + category only; never inputs or expected outputs."""
    keep = ("id", "name", "category", "visible", "passed", "status", "time_ms")
    rows = [r if r["visible"] else {k: r.get(k) for k in keep} for r in res["results"]]
    for r in rows:
        if r["visible"]:
            r.pop("why", None)
    return {**res, "results": rows}


def _task_public(t, p, done_round):
    if t["status"] == "pending":  # problem content stays hidden until its own timer starts
        return {k: t.get(k) for k in ("qid", "type", "order", "minutes", "status")}
    out = {k: t.get(k) for k in ("qid", "type", "order", "minutes", "status", "started_at", "deadline", "best_score", "draft")}
    out.update(title=p["title"], difficulty=p.get("difficulty"), problem=p["problem"], submissions=len(t.get("submissions", [])),
               last_result=_candidate_view(t["submissions"][-1]["result"]) if t.get("submissions") else None)
    if p["type"] == "dsa":
        out.update(input_format=p.get("input_format"), output_format=p.get("output_format"), constraints=p.get("constraints"), samples=p["samples"],
                   languages=[{"id": k, "label": v, "available": cr.available(k)} for k, v in LANG_LABEL.items()], starters=STARTERS,
                   hidden_count=len(p["hidden_tests"]))
    elif p["type"] == "sql":
        vis = [x for x in p["tests"] if x["visible"]]
        out.update(schema=p["schema"], ordered=p.get("ordered"), languages=[{"id": "sql", "label": "MySQL", "available": True}],
                   sample_data=[x["data"] for x in vis], sample_expected=[x["expected"] for x in vis], hidden_count=len(p["tests"]) - len(vis),
                   engine_note="Queries run against a controlled SQLite database with a MySQL-compatibility shim.")
    else:
        out.update(starter=p.get("starter"), languages=[{"id": "web", "label": "HTML/CSS/JS", "available": True}],
                   visible_checks=[{"name": x["name"]} for x in p["tests"] if x["visible"]], hidden_count=sum(1 for x in p["tests"] if not x["visible"]),
                   engine_note="Evaluated with DOM tests in a headless jsdom page.")
    if done_round:
        out["submission_history"] = [{"at": s["at"], "score": s["score"], "passed": s["result"]["passed"], "total": s["result"]["total"]} for s in t.get("submissions", [])]
    return out


def _code_close(a):
    changed = False
    for t in a["tasks"]:
        if t["status"] == "active" and _past(t["deadline"]):
            t.update(status="done", ended_at=iso(now()), end_reason="time_up")
            changed = True
    if all(t["status"] == "done" for t in a["tasks"]) and not a.get("finished_at"):
        sc = a["scoring"]
        scores = {t["qid"]: t.get("best_score") or 0 for t in a["tasks"]}
        pct = round(sum(scores.values()) / len(scores), 1)
        a["finished_at"] = iso(now())
        a["result"] = {"task_scores": scores, "percent": pct, "cutoff_percent": sc["cutoff_percent"], "passed": pct >= sc["cutoff_percent"],
                       "model": sc["model"], "official": False, "computed_at": iso(now())}
        changed = True
    return changed


def _code_public(a, m):
    probs = {p["qid"]: p for p in m["rounds"]["coding"]["problems"]}
    cur = next((i for i, t in enumerate(a["tasks"]) if t["status"] != "done"), None)
    return {"id": a["id"], "mock_id": a["mock_id"], "preview": a["preview"], "server_time": iso(now()), "current": cur, "finished_at": a.get("finished_at"),
            "result": a.get("result"), "scoring": {k: a["scoring"][k] for k in ("note", "cutoff_percent", "max_submissions")},
            "tasks": [_task_public(t, probs[t["qid"]], bool(a.get("finished_at"))) for t in a["tasks"]],
            "runner_available": sandbox.ready(),
            "sandbox_note": ("Code runs in a short-lived process inside a chroot jail with no network (socket syscalls blocked), no access to the "
                             "application files or secrets, an unprivileged uid, and CPU/memory/process/file limits. It shares the host kernel: "
                             "it is not a container/VM sandbox." if sandbox.ready() else RUNNER_DOWN)}


C = "/accenture-mocks/{mock_id}/coding"


async def _demo_guard(mock_id, preview):
    """Demo publication: Round 4 is closed for candidates (start, begin, run, submit, custom input, drafts). Admin preview is unaffected."""
    if not preview and await am.coding_disabled(mock_id):
        raise HTTPException(409, am.DEMO_MSG)


async def _code_ctx(user, mock_id):
    a = await _load(user, mock_id, "coding")
    await _demo_guard(mock_id, a.get("preview"))
    m = await db.acc_mocks.find_one({"library_id": a["library_id"], "mock_id": mock_id}, {"_id": 0})
    if _code_close(a):
        await _save(a, ["tasks", "finished_at", "result"])
    return a, m


class TryIn(BaseModel):
    lang: str = Field("python", max_length=20)
    code: str = Field(..., max_length=60000)
    stdin: str = Field("", max_length=20000)


@router.post(C + "/try")
async def code_try(mock_id: str, body: TryIn, user=Depends(current_user)):
    """Custom-input run for the active DSA task. Same jailed runner, fail-closed; not scored, no tests involved."""
    a, m = await _code_ctx(user, mock_id)
    t = _active(a)
    if t["type"] != "dsa":
        raise HTTPException(400, "Custom input is only for DSA tasks.")
    if not sandbox.ready():
        raise HTTPException(503, RUNNER_DOWN)
    lang = cr.norm_lang(body.lang)
    if not cr.available(lang):
        raise HTTPException(400, f"{LANG_LABEL.get(lang, lang)} is not available on this server.")
    try:
        async with cr.Program(lang, body.code, isolated=True) as prog:
            err = await prog.compile()
            if err:
                return {"compile_error": err}
            r = await prog.run(body.stdin)
    except sandbox.Unavailable:
        raise HTTPException(503, RUNNER_DOWN)
    return {"compile_error": None, "status": r["status"] or "Finished", "stdout": r["stdout"][:8000], "stderr": r["stderr"][-2000:], "time_ms": r["time_ms"]}


class SqlTryIn(BaseModel):
    query: str = Field(..., max_length=20000)


@router.post(C + "/sql-try")
async def code_sql_try(mock_id: str, body: SqlTryIn, user=Depends(current_user)):
    """Runs the query on the task's PUBLIC schema + first sample dataset only (never hidden data), in the jail."""
    a, m = await _code_ctx(user, mock_id)
    t = _active(a)
    p = _prob(m, t)
    if p["type"] != "sql":
        raise HTTPException(400, "Not a SQL task.")
    if not sandbox.ready():
        raise HTTPException(503, RUNNER_DOWN)
    vis = [x for x in p["tests"] if x["visible"]]
    try:
        out = await judges.run_sql(body.query, [p["schema"] + "\n" + (vis[0]["data"] if vis else "")], isolated=True)
    except sandbox.Unavailable:
        raise HTTPException(503, RUNNER_DOWN)
    return out[0] if out else {"error": "No result"}


@router.post(C + "/draft")
async def code_draft(mock_id: str, body: CodeIn, user=Depends(current_user)):
    """Autosave of the editor contents for the active task (recovery after reload/interruption). Nothing is executed."""
    a, m = await _code_ctx(user, mock_id)
    t = _active(a)
    t["draft"] = body.model_dump()
    await _save(a, ["tasks"])
    return {"ok": True}


@router.post(C + "/start")
async def code_start(mock_id: str, body: StartIn, user=Depends(current_user)):
    m = await _mock(user, mock_id, body.preview)
    await _demo_guard(mock_id, body.preview)
    old = await _find(user, mock_id, "coding", preview=body.preview)
    if old and not (body.preview and old.get("finished_at")):
        if _code_close(old):
            await _save(old, ["tasks", "finished_at", "result"])
        return _code_public(old, m)
    await _require_previous(user, mock_id, "coding", body.preview)
    tasks = [{"qid": p["qid"], "type": p["type"], "order": p["order"], "minutes": p["minutes"], "status": "pending", "submissions": [], "best_score": None}
             for p in sorted(m["rounds"]["coding"]["problems"], key=lambda x: x["order"])]
    doc = {"id": str(uuid.uuid4()), "user_id": user["id"], "mock_id": mock_id, "library_id": m["library_id"], "mock_version": m["version"], "round": "coding",
           "preview": body.preview, "tasks": tasks, "scoring": await _settings("coding_scoring", CODE_DEFAULT), "created_at": iso(now())}
    from accenture_proctor import oa_config
    doc["proctoring_policy"] = (await oa_config(m))["proctoring"]
    await db.acc_attempts.insert_one(dict(doc))
    return _code_public(doc, m)


@router.get(C)
async def code_get(mock_id: str, user=Depends(current_user)):
    a, m = await _code_ctx(user, mock_id)
    return _code_public(a, m)


def _active(a):
    t = next((x for x in a["tasks"] if x["status"] != "done"), None)
    if not t or t["status"] != "active":
        raise HTTPException(409, "No active coding task.")
    return t


@router.post(C + "/begin")
async def code_begin(mock_id: str, user=Depends(current_user)):
    a, m = await _code_ctx(user, mock_id)
    t = next((x for x in a["tasks"] if x["status"] != "done"), None)
    if t and t["status"] == "pending":
        s = now()
        t.update(status="active", started_at=iso(s), deadline=iso(s + timedelta(minutes=t["minutes"])))
        await _save(a, ["tasks"])
    return _code_public(a, m)


def _prob(m, t):
    return next(p for p in m["rounds"]["coding"]["problems"] if p["qid"] == t["qid"])


@router.post(C + "/run")
async def code_run(mock_id: str, body: CodeIn, user=Depends(current_user)):
    """Visible tests only; not scored."""
    a, m = await _code_ctx(user, mock_id)
    t = _active(a)
    t["draft"] = body.model_dump()
    await _save(a, ["tasks"])
    res = await _judge(_prob(m, t), body, visible_only=True)
    return _candidate_view(res)


@router.post(C + "/submit")
async def code_submit(mock_id: str, body: CodeIn, user=Depends(current_user)):
    a, m = await _code_ctx(user, mock_id)
    t = _active(a)
    if len(t["submissions"]) >= a["scoring"]["max_submissions"]:
        raise HTTPException(409, "Submission limit reached for this task.")
    t["draft"] = body.model_dump()
    await _save(a, ["tasks"])
    res = await _judge(_prob(m, t), body, visible_only=False)
    score = _weighted(res, a["scoring"])
    t["submissions"].append({"at": iso(now()), "lang": body.lang, "code": body.code, "html": body.html, "css": body.css, "js": body.js, "result": res, "score": score})
    t["best_score"] = max(score, t.get("best_score") or 0)
    t["draft"] = body.model_dump()
    await _save(a, ["tasks"])
    return {"score": score, "best_score": t["best_score"], "result": _candidate_view(res)}


@router.post(C + "/next")
async def code_next(mock_id: str, user=Depends(current_user)):
    a, m = await _code_ctx(user, mock_id)
    t = _active(a)
    t.update(status="done", ended_at=iso(now()), end_reason="moved_on")
    _code_close(a)
    await _save(a, ["tasks", "finished_at", "result"])
    return _code_public(a, m)


# ======================= private report + admin =======================
@router.get("/accenture-mocks/{mock_id}/report")
async def report(mock_id: str, user=Depends(current_user)):
    """Owner-only summary of finished rounds (admins see their own preview attempts here)."""
    out = {}
    for rnd in ROUND_ORDER:
        a = await _find(user, mock_id, rnd)
        if a and a.get("finished_at") and rnd == "behavioural":
            from accenture_behavioural import candidate_result
            out[rnd] = {"finished_at": a["finished_at"], "preview": a["preview"], "passed": None, **(candidate_result(a) or {})}
        elif a and a.get("finished_at"):
            r = a.get("round_score") if rnd == "gamified" else a.get("result")
            out[rnd] = {"finished_at": a["finished_at"], "percent": (r or {}).get("percent"), "passed": (r or {}).get("passed"),
                        "cutoff_percent": (r or {}).get("cutoff_percent"), "preview": a["preview"]}
    from accenture_proctor import sessions_for, summarize
    atts = {rnd: await _find(user, mock_id, rnd) for rnd in out}
    ses = await sessions_for([x["id"] for x in atts.values() if x])
    for rnd, x in atts.items():
        out[rnd]["proctoring"] = summarize(x, ses.get(x["id"]))
        if rnd == "coding":
            out[rnd]["tasks"] = [{"qid": t["qid"], "type": t["type"], "best_score": t.get("best_score"), "submissions": len(t.get("submissions", []))} for t in x.get("tasks", [])]
    demo = await am.coding_disabled(mock_id)
    ov = overall(out)
    if demo and "coding" not in out:
        ov.update(status="demo_round4_disabled", practice_percent=None, meets_all_cutoffs=None,
                  method="Demo publication: Round 4 coding is disabled, so no Round 4 score and no overall practice score are produced. " + OVERALL_METHOD)
    return {"mock_id": mock_id, "rounds": out, "order": ROUND_ORDER, "overall": ov, "demo_mode": demo, "coding_disabled": demo,
            "demo_message": am.DEMO_MSG if demo else None}


OVERALL_METHOD = ("Practice overall (not official Accenture scoring). Practice % = unweighted mean of the Round 2, 3 and 4 percentages, each computed "
                  "with its own labelled practice formula. Round 1 is a behavioural trait profile: it is never converted into points, it only has to be "
                  "completed, and while a flagged profile awaits admin review (or after it is invalidated) no overall verdict is given. The verdict "
                  "'meets all cutoffs' requires every scored round to meet its own cutoff.")


def overall(rounds):
    scored = [rounds.get(k) for k in ("gamified", "technical", "coding")]
    beh = rounds.get("behavioural")
    pct = round(sum(r["percent"] or 0 for r in scored) / 3, 1) if all(scored) else None
    status = ("in_progress" if not beh or not all(scored) else "pending_behavioural_review" if beh.get("review_status") == "needs_admin_review"
              else "behavioural_invalidated" if beh.get("review_status") == "invalidated" else "complete")
    return {"status": status, "practice_percent": pct, "rounds_meeting_cutoff": sum(1 for r in scored if r and r.get("passed")),
            "meets_all_cutoffs": all(r["passed"] for r in scored) if status == "complete" else None, "behavioural_included": False,
            "method": OVERALL_METHOD, "official": False}


class TechScoringIn(BaseModel):
    correct: float = Field(..., gt=0, le=10)
    wrong: float = Field(..., ge=-10, le=0)
    unanswered: float = Field(0, ge=-10, le=10)
    cutoff_percent: float = Field(..., ge=0, le=100)


class CodeScoringIn(BaseModel):
    visible_weight: float = Field(..., ge=0, le=10)
    hidden_weight: float = Field(..., ge=0, le=10)
    cutoff_percent: float = Field(..., ge=0, le=100)
    max_submissions: int = Field(..., ge=1, le=50)


@router.get("/admin/accenture-mocks/round-scoring")
async def get_round_scoring(admin=Depends(require_admin)):
    return {"technical": await _settings("technical_scoring", TECH_DEFAULT), "coding": await _settings("coding_scoring", CODE_DEFAULT)}


@router.put("/admin/accenture-mocks/round-scoring/technical")
async def put_tech_scoring(body: TechScoringIn, admin=Depends(require_admin)):
    await db.acc_mock_settings.update_one({"key": "technical_scoring"}, {"$set": {"value": body.model_dump(), "updated_by": admin["email"]}}, upsert=True)
    return await _settings("technical_scoring", TECH_DEFAULT)


@router.put("/admin/accenture-mocks/round-scoring/coding")
async def put_code_scoring(body: CodeScoringIn, admin=Depends(require_admin)):
    await db.acc_mock_settings.update_one({"key": "coding_scoring"}, {"$set": {"value": body.model_dump(), "updated_by": admin["email"]}}, upsert=True)
    return await _settings("coding_scoring", CODE_DEFAULT)


@router.delete("/accenture-mocks/{mock_id}/preview-attempts")
async def reset_preview(mock_id: str, admin=Depends(require_admin)):
    r = await db.acc_attempts.delete_many({"user_id": admin["id"], "mock_id": mock_id, "round": {"$in": ROUND_ORDER}, "preview": True})
    return {"deleted": r.deleted_count}


@router.get("/admin/accenture-mocks/release-readiness")
async def release_readiness(admin=Depends(require_admin)):
    """Read-only. Re-runs the sandbox escape probes live; flags/API responses are never counted as proof. Never publishes or unlocks."""
    pub = await am.published_library()
    ind = await am.individually_published()
    unlocked = sorted(await am.unlocked_ids(), key=lambda x: int(x[1:]))
    m1 = await db.acc_mocks.find_one({"mock_id": "M1"}, {"_id": 0}, sort=[("version", -1)]) or {}
    errs, warns, st = am.validate_mock(m1.get("rounds") or {}) if m1.get("rounds") else (["No M1 draft"], [], {})
    r = m1.get("rounds") or {}
    counts = {"behavioural": len(r.get("behavioural", {}).get("items", [])), "gamified": len(r.get("gamified", {}).get("activities", [])),
              "technical": len(r.get("technical", {}).get("questions", [])), "coding": [p["type"] for p in r.get("coding", {}).get("problems", [])]}
    sb = await sandbox.init()
    passed = [c for c in sb["checks"] if c["passed"]]
    failed = [c for c in sb["checks"] if not c["passed"]]
    valid = await db.acc_mocks.count_documents({"library_id": m1.get("library_id"), "status": "valid"}) if m1 else 0
    gp = await db.acc_attempts.count_documents({"round": "behavioural", "finished_at": {"$ne": None}, "result.review.status": "needs_admin_review", "admin_review": None})
    confirmed = [
        f"Round 4 runner jail: {len(passed)}/{len(sb['checks'])} live escape/function probes passed just now" if sb["checks"] else None,
        "Round 4 fails closed: run/submit return 503 unless the jail is built and every probe passed (no fallback to the legacy runner)",
        f"Library published={bool(pub)}; individually published mocks={sorted(ind) or 'none'}; unlocked={unlocked or 'none'}",
        f"M1 content counts: R1 {counts['behavioural']} · R2 {counts['gamified']} · R3 {counts['technical']} · R4 {' + '.join(counts['coding'])}",
    ]
    by_code = [
        "Round order R1 -> R2 -> R3 -> R4 enforced on start (409); admin preview attempts never satisfy real-candidate order",
        "One attempt per round per candidate; start resumes the existing attempt",
        "Server deadlines (R1 20m, R2 per activity, R3 45m, R4 20m per task, +5s grace); late answers rejected, rounds auto-closed on next request",
        "Candidate endpoints require published + valid + unlocked (404); preview admin-only (403); admin routes require_admin",
        "R3 answer keys/explanations only returned after the round closes; R4 hidden test inputs/outputs never returned; R4 problem text hidden until its task timer starts",
        "Results owner-only (by session user id); R1 responses and review flags admin-only; practice overall computed from persisted round results",
    ]
    infra = [
        "Kernel-level isolation: the jail shares the host kernel with the app (no container/VM). This pod cannot create namespaces or cgroups "
        "(unshare denied, no CAP_SYS_ADMIN/NET_ADMIN, no Docker/gVisor/KVM). Required: a separate runner service in its own container/VM with "
        "network disabled - see /app/memory/SANDBOX_DEPLOYMENT.md. Set CODE_SANDBOX_ISOLATED=true only after that service is deployed and verified.",
        "Hard memory caps for Node.js/Java are heap flags only (no cgroup), and there is no disk quota for the per-run work dir (per-file 8 MB limit + time limit only).",
        "Production deployment: the jail needs g++, OpenJDK 17, libseccomp and the chroot/mknod capabilities in the deployed image; otherwise Round 4 stays closed there.",
    ]
    if failed:
        infra.insert(0, "Sandbox probes FAILED: " + "; ".join(f"{c['check']} ({c['detail'][:80]})" for c in failed))
    if not sb["built"]:
        infra.insert(0, f"Sandbox jail not available: {sb['error']}")
    content = [f"M1 Round 3: {st.get('review_blocking', 0)} question(s) blocked until an admin individually reviews the unverified AI-derived answer keys "
               f"({st.get('ai_derived_keys', 0)} AI-derived keys total; labels preserved)",
               f"Library has {valid}/40 valid mocks; M2-M40 intentionally not generated, so publication is impossible",
               f"Round 1 profiles awaiting admin review: {gp}",
               "Round 2 game mechanics still need confirmation against a reference recording (see engine 'unconfirmed' notes)"]
    if errs:
        content.insert(0, "M1 validation errors: " + "; ".join(errs))
    return {"sections": {"implemented_confirmed": [c for c in confirmed if c], "implemented_not_independently_verified": by_code,
                         "blocked_infrastructure": infra, "blocked_manual_review": content},
            "sandbox": {"ready": sandbox.ready(), "built": sb["built"], "error": sb["error"], "verified_at": sb["verified_at"], "checks": sb["checks"],
                        "kernel_isolation_flag": cr.sandbox_isolated()},
            "publishable": False if not (sandbox.ready() and cr.sandbox_isolated()) or st.get("review_blocking") or valid < 40 else None,
            "m1": {"version": m1.get("version"), "status": m1.get("status"), "counts": counts, "warnings": warns},
            "published_library": pub, "unlocked_mocks": unlocked, "official_scoring": False}
