import asyncio
import logging
import math
import json
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import judges
import oa_dataset
import routes_code
from ai import ask_json
from auth import require_admin
from database import db
from routes_prep import Q_SCHEMA, SYS

router = APIRouter(prefix="/api/admin")
log = logging.getLogger("oa_builder")
ORIGINAL_SHARE = 0.65
KINDS = ("objective", "written", "coding", "sql", "web")
BATCH = {"objective": 15, "written": 6, "coding": 3, "sql": 3, "web": 3}
_running = {}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class BPSection(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=2, max_length=60)
    kind: str = Field(pattern="^(objective|written|coding|sql|web)$")
    count: int = Field(ge=1, le=50)
    minutes: int = Field(ge=1, le=180)
    difficulty: str = Field(default="Medium", pattern="^(Easy|Medium|Hard|Mixed)$")
    topics: str = Field(default="", max_length=400)


class Blueprint(BaseModel):
    sectional: bool = True
    sections: List[BPSection] = Field(min_length=1, max_length=10)


async def _company(cid):
    c = await db.oa_companies.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Company OA not found")
    return c


@router.put("/oa-companies/{cid}/blueprint")
async def save_blueprint(cid: str, body: Blueprint, admin=Depends(require_admin)):
    await _company(cid)
    if len({s.id for s in body.sections}) != len(body.sections):
        raise HTTPException(400, "Section ids must be unique.")
    bp = {**body.model_dump(), "duration_minutes": sum(s.minutes for s in body.sections), "updated_at": now_iso()}
    await db.oa_companies.update_one({"id": cid}, {"$set": {"blueprint": bp, "updated_at": now_iso()}})
    await oa_dataset.remap(cid, bp["sections"])
    await autofill(await _company(cid))
    return bp


@router.post("/oa-companies/{cid}/bank/autofill")
async def autofill_bank(cid: str, admin=Depends(require_admin)):
    return {"jobs": await autofill(await _company(cid))}


async def autofill(c):
    """Start background jobs that top every short section up to its configured count (and the 35% related share)."""
    jobs = []
    for sec in (c.get("blueprint") or {}).get("sections", []):
        items = await db.oa_bank.find({"company_id": c["id"], "section_id": sec["id"]}, {"_id": 0, "data": 0, "raw": 0}).to_list(3000)
        o, v, r = pools(items)
        need = max(0, sec["count"] - len(o) - len(v) - len(r), targets(sec["count"])[1] - len(r))
        if not need or await db.oa_bank_jobs.find_one({"company_id": c["id"], "section_id": sec["id"], "status": "running"}):
            continue
        job = {"id": str(uuid.uuid4()), "company_id": c["id"], "section_id": sec["id"], "section": sec["name"], "kind": sec["kind"], "mode": "related",
               "status": "running", "requested": need, "added": 0, "error": "", "created_at": now_iso(), "auto": True}
        await db.oa_bank_jobs.insert_one({**job})
        _running[job["id"]] = asyncio.create_task(_run_job(job, c, sec, need, "related", sec["kind"]))
        job.pop("_id", None)
        jobs.append(job)
    return jobs


@router.delete("/oa-companies/{cid}/blueprint")
async def clear_blueprint(cid: str, admin=Depends(require_admin)):
    await db.oa_companies.update_one({"id": cid}, {"$unset": {"blueprint": ""}})
    return {"ok": True}


def targets(n):
    o = math.floor(n * ORIGINAL_SHARE + 0.5)
    return o, n - o


def _usable(q):
    return q.get("status", "ready") == "ready" and q.get("kind") != "pattern"


def pools(items):
    orig = [q for q in items if q.get("is_original") and _usable(q)]
    var = [q for q in items if not q.get("is_original") and q.get("variant_type") == "variant" and _usable(q)]
    rel = [q for q in items if not q.get("is_original") and q.get("variant_type") != "variant" and _usable(q)]
    return orig, var, rel


def section_stats(sec, items):
    o_t, r_t = targets(sec["count"])
    orig, var, rel = pools(items)
    allo = [q for q in items if q.get("is_original")]
    return {"count": sec["count"], "target_original": o_t, "target_related": r_t, "original_ready": len(orig),
            "original_review": sum(q.get("status") == "needs_review" for q in allo), "original_incomplete": sum(q.get("status") == "incomplete" for q in allo),
            "variant_ready": len(var), "related_ready": len(rel), "available": len(orig) + len(var) + len(rel),
            "can_start": len(orig) + len(var) + len(rel) >= sec["count"], "ratio_met": len(orig) >= o_t and len(rel) >= r_t,
            "need_related": max(0, r_t - len(rel)), "need_variants": max(0, o_t - len(orig) - len(var))}


@router.get("/oa-companies/{cid}/bank")
async def list_bank(cid: str, admin=Depends(require_admin)):
    c = await _company(cid)
    items = await db.oa_bank.find({"company_id": cid}, {"_id": 0, "raw": 0}).sort("created_at", 1).to_list(3000)
    jobs = await db.oa_bank_jobs.find({"company_id": cid, "status": "running"}, {"_id": 0}).to_list(20)
    secs = (c.get("blueprint") or {}).get("sections", [])
    ids = {s["id"] for s in secs}
    stats = {s["id"]: section_stats(s, [q for q in items if q.get("section_id") == s["id"]]) for s in secs}
    return {"questions": items, "jobs": jobs, "stats": stats, "import_status": c.get("import_status"),
            "unassigned": [q for q in items if q.get("section_id") not in ids]}


class BankPatch(BaseModel):
    selected: Optional[bool] = None
    answer_verified: Optional[bool] = None
    rejected: Optional[bool] = None
    data: Optional[Dict[str, Any]] = None


@router.patch("/oa-bank/{qid}")
async def patch_bank(qid: str, body: BankPatch, admin=Depends(require_admin)):
    d = await db.oa_bank.find_one({"id": qid}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Question not found")
    upd = {k: v for k, v in body.model_dump().items() if v is not None and k != "rejected"}
    if body.data is not None:
        if d["kind"] in ("coding", "sql", "web") and d["data"].get("tests") and not body.data.get("tests"):
            body.data["tests"] = d["data"]["tests"]
        upd["data"] = body.data
        upd["content_hash"] = oa_dataset.content_hash(d["kind"], body.data.get("question") or body.data.get("problem", ""), body.data.get("options"))
    merged = {**d, **upd}
    if body.rejected:
        upd["status"] = "rejected"
    elif body.rejected is False or body.data is not None or body.answer_verified is not None:
        upd["status"], upd["review_notes"] = oa_dataset.status_of(merged) if d.get("is_original") else ("ready", [])
        if body.answer_verified and d.get("is_original"):
            upd["verified_by"], upd["ocr_uncertain"] = admin["email"], False
            upd["status"], upd["review_notes"] = oa_dataset.status_of({**merged, "ocr_uncertain": False})
    await db.oa_bank.update_one({"id": qid}, {"$set": upd})
    return await db.oa_bank.find_one({"id": qid}, {"_id": 0, "raw": 0})


@router.post("/oa-bank/{qid}/enrich")
async def enrich_bank(qid: str, admin=Depends(require_admin)):
    d = await db.oa_bank.find_one({"id": qid}, {"_id": 0})
    if not d or not d.get("is_original"):
        raise HTTPException(404, "Dataset question not found")
    d = await oa_dataset.enrich(d)
    await db.oa_bank.update_one({"id": qid}, {"$set": {k: d[k] for k in ("data", "status", "review_notes", "harness")}})
    return await db.oa_bank.find_one({"id": qid}, {"_id": 0, "raw": 0})


class BankBulk(BaseModel):
    section_id: str
    selected: bool


@router.post("/oa-companies/{cid}/bank/select")
async def bulk_select(cid: str, body: BankBulk, admin=Depends(require_admin)):
    r = await db.oa_bank.update_many({"company_id": cid, "section_id": body.section_id}, {"$set": {"selected": body.selected}})
    return {"ok": True, "updated": r.modified_count}


@router.delete("/oa-bank/{qid}")
async def delete_bank(qid: str, admin=Depends(require_admin)):
    r = await db.oa_bank.delete_one({"id": qid})
    if not r.deleted_count:
        raise HTTPException(404, "Question not found")
    return {"ok": True}


class GenIn(BaseModel):
    section_id: str
    count: int = Field(default=5, ge=1, le=60)
    mode: str = Field(default="related", pattern="^(related|variant)$")
    kind: str = Field(default="", pattern="^(|objective|written|coding|sql|web)$")


@router.post("/oa-companies/{cid}/bank/generate")
async def generate_bank(cid: str, body: GenIn, admin=Depends(require_admin)):
    c = await _company(cid)
    sec = next((s for s in (c.get("blueprint") or {}).get("sections", []) if s["id"] == body.section_id), None)
    if not sec:
        raise HTTPException(400, "Save the section in the OA blueprint first.")
    kind = body.kind or sec["kind"]
    if (kind in oa_dataset.PROGRAMMING) != (sec["kind"] in oa_dataset.PROGRAMMING):
        raise HTTPException(400, "That question type does not fit this section.")
    if await db.oa_bank_jobs.find_one({"company_id": cid, "section_id": sec["id"], "status": "running"}):
        raise HTTPException(409, "Questions are already being generated for this section.")
    job = {"id": str(uuid.uuid4()), "company_id": cid, "section_id": sec["id"], "section": sec["name"], "kind": kind, "mode": body.mode, "status": "running",
           "requested": body.count, "added": 0, "error": "", "created_at": now_iso()}
    await db.oa_bank_jobs.insert_one({**job})
    _running[job["id"]] = asyncio.create_task(_run_job(job, c, sec, body.count, body.mode, kind))
    job.pop("_id", None)
    return job


@router.get("/oa-bank-jobs/{jid}")
async def bank_job(jid: str, admin=Depends(require_admin)):
    j = await db.oa_bank_jobs.find_one({"id": jid}, {"_id": 0})
    if not j:
        raise HTTPException(404, "Job not found")
    return j


async def _sources(c, sec, kind):
    """Dataset questions this section is grounded on (selected in code, then handed to Gemini)."""
    q = {"company_id": c["id"], "is_original": True, "status": {"$ne": "rejected"}}
    items = await db.oa_bank.find({**q, "section_id": sec["id"]}, {"_id": 0}).to_list(500)
    same = [d for d in items if d["kind"] == kind] or items
    same.sort(key=lambda d: (d.get("derived_count", 0), random.random()))
    notes = await db.oa_bank.find({"company_id": c["id"], "kind": "pattern"}, {"_id": 0, "data": 1, "source_ref": 1}).to_list(6)
    return same[:6], notes


def _src_json(d):
    keep = ("question", "options", "problem", "input_format", "output_format", "constraints", "examples", "schema", "title")
    return {"source_ref": d.get("source_ref") or d["id"], "type": d.get("question_type") or d["kind"], "topic": d.get("topic", ""),
            "difficulty": d.get("difficulty", ""), **{k: d["data"][k] for k in keep if d["data"].get(k)}}


async def generate_into_bank(c, sec, count, mode="related", kind=None):
    """Grounded generation: sources are picked from the DB in code, Gemini only writes related questions/variants. Returns number added."""
    kind = kind or sec["kind"]
    added, tries = 0, 0
    while added < count and tries < 4:
        tries += 1
        existing = [b["data"].get("title") or b["data"].get("question", "")[:80] async for b in
                    db.oa_bank.find({"company_id": c["id"], "section_id": sec["id"]}, {"_id": 0, "data": 1})][-60:]
        known = {b.get("content_hash") async for b in db.oa_bank.find({"company_id": c["id"]}, {"_id": 0, "content_hash": 1})}
        srcs, notes = await _sources(c, sec, kind)
        if mode == "variant" and not srcs:
            raise HTTPException(400, "This section has no dataset questions to make variants of. Import the dataset first.")
        by_ref = {(d.get("source_ref") or d["id"]): d for d in srcs}
        n = min(BATCH[kind], count - added)
        items = await _generate(c, {**sec, "kind": kind}, n, existing, mode, [_src_json(d) for d in srcs], [x["data"]["question"] for x in notes])
        for d in items[:count - added]:
            h = oa_dataset.content_hash(kind, d.get("question") or d.get("problem", ""), d.get("options"))
            if h in known:
                continue
            known.add(h)
            parent = by_ref.get(d.pop("parent_ref", "") or "")
            await db.oa_bank.insert_one({"id": str(uuid.uuid4()), "company_id": c["id"], "company": c["name"], "section_id": sec["id"], "kind": kind,
                                         "question_type": d.get("type") or kind, "data": d, "selected": False, "source": "ai", "is_original": False,
                                         "variant_type": mode, "parent_question_id": parent["id"] if parent else None,
                                         "source_ref": f"{parent.get('source_ref')}-{'V' if mode == 'variant' else 'R'}" if parent else "",
                                         "source_dataset": parent.get("source_dataset") if parent else None, "source_page": parent.get("source_page") if parent else None,
                                         "topic": parent.get("topic", "") if parent else sec.get("topics", ""), "difficulty": d.get("difficulty") or sec["difficulty"],
                                         "content_hash": h, "status": "ready", "answer_verified": False, "harness": "generated" if kind in oa_dataset.PROGRAMMING else None,
                                         "review_notes": [] if parent or not srcs else ["Not linked to a specific dataset question."], "created_at": now_iso()})
            if parent:
                await db.oa_bank.update_one({"id": parent["id"]}, {"$inc": {"derived_count": 1}})
            added += 1
    return added


async def _run_job(job, c, sec, count, mode, kind):
    added, err = 0, ""
    try:
        added = await (_fill(c, sec, count) if mode == "related" and count > BATCH[kind] and kind == sec["kind"] else generate_into_bank(c, sec, count, mode, kind))
        if not added:
            err = "The AI could not produce questions that passed validation. Try again."
    except Exception as e:
        err = getattr(e, "detail", None) or str(e)[:300]
    log.info("Bank job %s/%s %s x%s: added %s %s", c["name"], sec["name"], mode, count, added, err)
    await db.oa_bank_jobs.update_one({"id": job["id"]}, {"$set": {"status": "done" if added else "failed", "added": added, "error": err, "finished_at": now_iso()}})
    _running.pop(job["id"], None)


async def _fill(c, sec, need):
    """Top up a short section before the test starts: parallel grounded batches, saved to the bank for reuse."""
    kind = sec["kind"]
    size = BATCH[kind]
    want = need + (max(2, need // 6) if kind not in oa_dataset.PROGRAMMING else 0)
    chunks = [min(size, want - i) for i in range(0, want, size)][:8]
    res = await asyncio.gather(*[generate_into_bank(c, sec, n, "related", kind) for n in chunks if n > 0], return_exceptions=True)
    added = sum(r for r in res if isinstance(r, int))
    log.info("OA auto-fill %s/%s: needed %s, generated %s, failures %s", c["name"], sec["name"], need, added, [str(r)[:100] for r in res if not isinstance(r, int)])
    return added


MODES = {
    "related": "Write NEW practice questions closely related to the SOURCE QUESTIONS: same topics, concepts, patterns, question style, format and difficulty. "
               "Each one must be clearly derived from one source question (set parent_ref to its source_ref). Never write generic interview questions "
               "unrelated to the sources, and never copy a source verbatim.",
    "variant": "Write CONTROLLED VARIANTS. For each, take one source question (parent_ref = its source_ref) and change ONLY surface details: numbers, names, "
               "variable names, example inputs or equivalent entities. Keep the exact problem structure, required logic, output format and difficulty. "
               "Recompute the answer / examples for the new values.",
}


def _ctx(c, sec, n, existing, mode, sources, notes):
    src = (f"SOURCE QUESTIONS from the {c['name']} dataset (ground truth, retrieved from the database):\n{json.dumps(sources)[:9000]}\n" if sources else
           f"This section has no dataset questions yet. Ground the questions in the {c['name']} pattern below and the section topics; set parent_ref to \"\".\n")
    return (f"Company: {c['name']}. Section: {sec['name']}. Difficulty: {sec['difficulty']}. Topics: {sec.get('topics') or 'as in the sources'}.\n{src}"
            f"DATASET PATTERN NOTES: {json.dumps(notes)[:1500]}\nPATTERN PROFILE: {json.dumps(c.get('profile') or {})[:1500]}\n"
            f"Already in the bank (do NOT repeat): {json.dumps(existing)[:2500]}\n{MODES[mode]}\nWrite exactly {n} unique, factually correct questions. "
            "Every item must include \"parent_ref\".\n")


SQL_RULES = """Use only portable SQL that runs on BOTH MySQL 8 and SQLite: SELECT, JOINs (INNER/LEFT), GROUP BY, HAVING, subqueries, CTEs (WITH),
window functions (ROW_NUMBER, RANK, DENSE_RANK, LAG, LEAD, SUM/AVG OVER), CASE, COALESCE, IFNULL, CONCAT, ROUND, YEAR/MONTH/DAY, DATEDIFF, LIMIT.
Do NOT use DATE_FORMAT, IF(), RIGHT JOIN, FULL JOIN, stored procedures, variables or ALTER. Store dates as 'YYYY-MM-DD' text. Column types: INT, VARCHAR(n), DECIMAL(10,2), DATE."""

WEB_RULES = """Tests run in jsdom (no layout engine): never use offsetWidth/getBoundingClientRect/scroll sizes, fetch, canvas, localStorage timing or animations.
For CSS use window.getComputedStyle(el) ONLY for display, visibility, font-weight, text-align, text-decoration, cursor with keyword values.
Interactions: el.click(); for inputs set el.value then el.dispatchEvent(new window.Event('input', {bubbles: true})); forms: form.dispatchEvent(new window.Event('submit', {bubbles: true, cancelable: true})).
You may 'await new Promise(r => setTimeout(r, 50))' after an interaction. Each script is a JS function BODY with document/window in scope and must 'return' true only when the requirement is met."""


async def _generate(c, sec, n, existing, mode="related", sources=(), notes=()):
    base = _ctx(c, sec, n, existing, mode, list(sources), list(notes))
    k = sec["kind"]
    if k in ("objective", "written"):
        types = "mcq or numeric (mostly mcq, matching the sources' types)" if k == "objective" else "written"
        data = await ask_json(SYS, base + f"Question types allowed: {types}. MCQs have exactly 4 options and one correct answer.\n"
                              f"Return JSON: {{\"questions\": [{Q_SCHEMA}]}} and every question object ALSO has \"parent_ref\": str.")
        return [q for q in data.get("questions", []) if _valid_obj(q, k)]
    if k == "coding":
        data = await ask_json(SYS, base + 'Coding problems are stdin/stdout programs. Return JSON: {"problems": [{"parent_ref": str, "title": str, "difficulty": str, "problem": str, '
                              '"input_format": str, "output_format": str, "examples": [{"input": str (exact stdin), "output": str (exact stdout)}], "constraints": str}]}')
        probs = [p for p in data.get("problems", []) if p.get("title") and p.get("problem")]
        built = await asyncio.gather(*[routes_code.build_tests(p) for p in probs], return_exceptions=True)
        probs = [{**p, "tests": b["tests"], "io_note": b.get("io_note", "")} for p, b in zip(probs, built) if isinstance(b, dict)]
        starters = await asyncio.gather(*[oa_dataset.starter_code(p) for p in probs])
        return [{**p, "starter_code": s} for p, s in zip(probs, starters)]
    if k == "sql":
        data = await ask_json(SYS, base + SQL_RULES + """
Return JSON: {"problems": [{"parent_ref": str, "title": str, "difficulty": str, "problem": str (task + exact output columns, their order and the row order rule),
"schema": str (CREATE TABLE statements only), "datasets": [str, str, str] (INSERT scripts: 1) sample 5-12 rows per table, 2) edge: NULLs, ties,
duplicates, rows that must be excluded, 3) larger 15-30 rows), "reference": str (one correct SELECT query), "ordered": bool (true only if the task fixes the row order)}]}""")
        probs = data.get("problems", [])
        out = await asyncio.gather(*[_valid_sql(p) for p in probs])
        return [{**o, "parent_ref": p.get("parent_ref", "")} for p, o in zip(probs, out) if o]
    data = await ask_json(SYS, base + WEB_RULES + """
Return JSON: {"problems": [{"parent_ref": str, "title": str, "difficulty": str, "problem": str (clear requirements naming the exact ids/classes/text to use),
"starter": {"html": str, "css": str, "js": str} (minimal skeleton that does NOT solve the task), "reference": {"html": str, "css": str, "js": str} (complete solution),
"tests": [{"name": str, "why": str (max 12 words), "script": str}] (6-8 DOM test cases covering every requirement)}]}""")
    probs = data.get("problems", [])
    out = await asyncio.gather(*[_valid_web(p) for p in probs])
    return [{**o, "parent_ref": p.get("parent_ref", "")} for p, o in zip(probs, out) if o]


def _valid_obj(q, kind):
    q["type"] = q.get("type") if q.get("type") in ("mcq", "numeric", "written") else ("mcq" if q.get("options") else "written")
    if not q.get("question"):
        return False
    if kind == "written":
        return q["type"] == "written"
    if q["type"] == "mcq":
        return len(q.get("options") or []) >= 2 and isinstance(q.get("answer_index"), int) and 0 <= q["answer_index"] < len(q["options"])
    return q["type"] == "numeric" and isinstance(q.get("answer"), (int, float))


SQL_TESTS = [("Sample data", "sample", True, "the example tables shown in the problem"), ("Edge cases", "edge", False, "NULLs, ties, duplicates and exclusions"),
             ("Larger dataset", "boundary", False, "more rows, catches hard-coded answers")]


async def _valid_sql(p):
    ds = [d for d in (p.get("datasets") or []) if isinstance(d, str) and d.strip()][:3]
    if not (p.get("schema") and p.get("reference") and p.get("title") and len(ds) >= 2):
        return None
    outs = await judges.run_sql(p["reference"], [p["schema"] + "\n" + d for d in ds])
    if any(o.get("error") for o in outs) or not outs[0].get("rows"):
        return None
    tests = [{"id": f"t{i + 1}", "name": SQL_TESTS[i][0], "category": SQL_TESTS[i][1], "visible": SQL_TESTS[i][2], "why": SQL_TESTS[i][3],
              "data": d, "expected": {"columns": o["columns"], "rows": o["rows"]}} for i, (d, o) in enumerate(zip(ds, outs))]
    return {"title": p["title"], "difficulty": p.get("difficulty", ""), "problem": p["problem"], "schema": p["schema"], "ordered": bool(p.get("ordered")),
            "reference": p["reference"], "tests": tests}


async def _valid_web(p):
    ref, st = p.get("reference") or {}, p.get("starter") or {}
    tests = [{"id": f"w{i + 1}", "name": t.get("name") or f"Test {i + 1}", "why": t.get("why", ""), "script": t["script"]}
             for i, t in enumerate(p.get("tests") or []) if isinstance(t, dict) and t.get("script")]
    if not (p.get("title") and p.get("problem") and ref.get("html") and tests):
        return None
    on_ref = {o["id"]: o["passed"] for o in await judges.run_web(ref.get("html", ""), ref.get("css", ""), ref.get("js", ""), tests)}
    on_start = {o["id"]: o["passed"] for o in await judges.run_web(st.get("html", ""), st.get("css", ""), st.get("js", ""), tests)}
    keep = [t for t in tests if on_ref.get(t["id"]) and not on_start.get(t["id"])]
    if len(keep) < 3:
        return None
    for i, t in enumerate(keep):
        t.update(id=f"w{i + 1}", visible=i < 2, category="sample" if i < 2 else "dom")
    return {"title": p["title"], "difficulty": p.get("difficulty", ""), "problem": p["problem"],
            "starter": {k: st.get(k, "") for k in ("html", "css", "js")}, "reference": {k: ref.get(k, "") for k in ("html", "css", "js")}, "tests": keep}


def _spread(items):
    """Round-robin across question kinds so a mixed section (e.g. DSA + SQL + Web) gets one of each before repeats."""
    by = {}
    for q in items:
        by.setdefault(q.get("kind"), []).append(q)
    groups = list(by.values())
    random.shuffle(groups)
    return [g[i] for i in range(max((len(g) for g in groups), default=0)) for g in groups if i < len(g)]


def _pick(pool, k, used, stats):
    sel = [q for q in pool if q.get("selected")]
    rest = [q for q in pool if not q.get("selected")]
    random.shuffle(sel)
    random.shuffle(rest)
    out = []
    for q in _spread(sel) + _spread(rest):
        if len(out) >= k:
            break
        h = q.get("content_hash") or q["id"]
        if h in used:
            stats["duplicates_removed"] += 1
            continue
        used.add(h)
        out.append(q)
    return out


def _item(q, origin):
    return {**q["data"], "_kind": q["kind"], "bank_id": q["id"], "origin": origin, "source_ref": q.get("source_ref", ""), "source_page": q.get("source_page"),
            "parent_question_id": q.get("parent_question_id")}


async def build_from_blueprint(oc):
    """Select exactly `count` questions per blueprint section: 65% dataset originals, 35% related. Raises 409 instead of starting short."""
    bp = oc.get("blueprint") or {}
    out = {"title": f"{oc['name']} Online Assessment", "pattern_note": f"{oc['name']} OA pattern: " + " · ".join(f"{s['name']} ({s['count']} Q, {s['minutes']} min)" for s in bp.get("sections", [])),
           "duration_minutes": sum(s["minutes"] for s in bp.get("sections", [])),
           "sections": [], "coding": [], "sql": [], "web": [], "blueprint": {"sectional": bp.get("sectional", True), "sections": []}, "mix_report": []}
    used, errors = set(), []

    async def short(s):
        items = await db.oa_bank.find({"company_id": oc["id"], "section_id": s["id"]}, {"_id": 0, "data": 0, "raw": 0}).to_list(3000)
        o, v, r = pools(items)
        o_t, r_t = targets(s["count"])
        return max(0, s["count"] - len(o) - len(v) - len(r), r_t - len(r))
    needs = [(s, await short(s)) for s in bp.get("sections", [])]
    fills = [(s, n) for s, n in needs if n]
    if fills:
        log.info("OA build %s: topping up %s", oc["name"], [(s["name"], n) for s, n in fills])
        await asyncio.gather(*[_fill(oc, s, n) for s, n in fills])
    for s in bp.get("sections", []):
        pool = await db.oa_bank.find({"company_id": oc["id"], "section_id": s["id"]}, {"_id": 0, "raw": 0}).to_list(3000)
        orig, var, rel = pools(pool)
        n, (o_t, r_t) = s["count"], targets(s["count"])
        st = {"section": s["name"], "requested": n, "target_original": o_t, "target_related": r_t, "duplicates_removed": 0, "notes": []}
        o = _pick(orig, o_t, used, st)
        v1 = _pick(var, o_t - len(o), used, st)
        r = _pick(rel, r_t + (o_t - len(o) - len(v1)), used, st)
        left = n - len(o) - len(v1) - len(r)
        v2 = _pick(var, left, used, st)
        o2 = _pick(orig, left - len(v2), used, st)
        picked = [_item(q, "original") for q in o + o2] + [_item(q, "variant") for q in v1 + v2] + [_item(q, "related") for q in r]
        st.update(original=len(o) + len(o2), variant=len(v1) + len(v2), related=len(r), final=len(picked))
        if len(o) < o_t:
            st["notes"].append(f"Only {len(o)} ready dataset originals (target {o_t}); {o_t - len(o)} original slots filled with variants/related questions.")
        if len(r) < r_t and len(picked) == n:
            st["notes"].append(f"Only {len(r)} related questions ready (target {r_t}); filled with extra variants/originals.")
        out["mix_report"].append(st)
        log.info("OA build %s/%s: %s", oc["name"], s["name"], st)
        if len(picked) < n:
            errors.append(f"{s['name']} needs {n} questions but only {len(picked)} are ready ({len(o) + len(o2)} original, {len(v1) + len(v2)} variant, {len(r)} related)")
            continue
        random.shuffle(picked)
        out["blueprint"]["sections"].append({"name": s["name"], "kind": s["kind"], "minutes": s["minutes"], "count": n})
        objective = [q for q in picked if q["_kind"] in ("objective", "written")]
        if objective:
            out["sections"].append({"name": s["name"], "questions": objective})
        for q in picked:
            kind = q.pop("_kind")
            if kind in ("coding", "sql", "web"):
                out[kind].append({**q, "section": s["name"]})
    if errors:
        raise HTTPException(409, f"The {oc['name']} OA can't start with the configured question counts: " + "; ".join(errors) +
                            ". Gemini could not generate the missing questions right now (it may be rate-limited); please try again in a minute.")
    return out
