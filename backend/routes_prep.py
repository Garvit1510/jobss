import asyncio
import logging
import json
import random
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ai import ask_json
import interview_ai
import routes_code
import judges
from auth import current_user
from database import db
from routes_core import get_resume, log_activity, user_ctx
import careers
from auth import require_admin
from typing import Any

log = logging.getLogger("mock_oa")
router = APIRouter(prefix="/api")
SYS = "You are JobLens AI, an expert career coach, assessor and hiring manager across ALL industries (tech, business, healthcare, education, trades, government and more). Be specific, accurate and practical."


def now_iso():
    return datetime.now(timezone.utc).isoformat()


async def _job(job_id):
    job = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(404, "Job not found")
    return job


def _resume_ctx(r):
    if not r:
        return "Candidate has not uploaded a resume."
    return (f"Candidate: {r.get('name')} — {r.get('headline')}\nSummary: {r.get('summary')}\nSkills: {', '.join(r.get('skills', []))}\n"
            f"Experience: {'; '.join(e.get('title', '') + ' at ' + e.get('company', '') for e in r.get('experience', []))}\n"
            f"Projects: {'; '.join(p.get('name', '') for p in r.get('projects', []))}")


TRUSTED = {"hidden": {"$ne": True}, "reports_n": {"$not": {"$gte": 3}}}


async def _experience_ctx(company="", sector="", role=""):
    ors = [{"company_key": company.strip().lower()}] if company.strip() else []
    if sector:
        words = [w for w in re.findall(r"[a-z]{4,}", (role or "").lower()) if w not in careers.GENERIC][:3]
        ors.append({"sector": sector, **({"role": {"$regex": "|".join(map(re.escape, words)), "$options": "i"}} if words else {})})
    if not ors:
        return ""
    exps = await db.experiences.find({"$or": ors, **TRUSTED}, {"_id": 0}).sort([("verified", -1), ("created_at", -1)]).to_list(6)
    if not exps:
        return ""
    return ("EVIDENCE from candidate experiences shared on JobLens (use to ground the format and topics; label: "
            "'verified' = checked by a moderator, otherwise candidate-reported and unverified; never copy confidential content verbatim):\n" + "\n".join(
        f"- [{'verified' if e.get('verified') else 'candidate-reported'}] {e.get('company')} · {e['role']} ({e['type']}, {e['year']}): {e['content'][:500]} "
        f"Stages: {', '.join(e.get('stages', []))}. Skills tested: {', '.join(e.get('skills_tested', []))}. Questions: {'; '.join(e.get('questions', [])[:8])}" for e in exps))


class PrepareIn(BaseModel):
    job_id: str


@router.post("/prepare")
async def prepare(body: PrepareIn, user=Depends(current_user)):
    cached = await db.prep_plans.find_one({"user_id": user["id"], "job_id": body.job_id}, {"_id": 0})
    if cached:
        return cached
    job, resume = await _job(body.job_id), await get_resume(user["id"])
    prompt = f"""{_resume_ctx(resume)}

TARGET JOB: {job['title']} at {job['company']} ({job['level']}, {job['work_type']}, {job['location']})
Required skills detected: {', '.join(job.get('skills', []))}
Description: {job.get('description', '')[:5000]}
Job sector: {careers.sector(job.get('sector') or careers.classify(job['title'])).get('name') if (job.get('sector') or careers.classify(job['title'])) != 'other' else 'General'}
{await _experience_ctx(job['company'], job.get('sector', ''), job['title'])}

Return JSON: {{"match_summary": str,
"skill_gap": {{"have": [str], "missing": [str], "partial": [str]}},
"roadmap": [{{"week": int, "focus": str, "tasks": [str]}}] (exactly 4 weeks),
"important_subjects": [{{"subject": str, "priority": "High"|"Medium"|"Low", "why": str}}] (6-8 items ranked, appropriate to this profession, not only technical),
"milestones": [str] (4 measurable checkpoints), "practice_tasks": [str] (4 role-appropriate practice assignments)}}
Roadmap tasks must fit the profession (e.g. lesson plans for teachers, safety drills for trades, mock tests for exam aspirants, sales role-plays for sales)."""
    plan = await ask_json(SYS, prompt)
    doc = {"user_id": user["id"], "job_id": body.job_id, "plan": plan, "created_at": now_iso()}
    await db.prep_plans.insert_one(doc)
    await log_activity(user["id"], "prepare", f"Prep plan generated for {job['title']} at {job['company']}")
    doc.pop("_id", None)
    return doc


LINKS = {
    "youtube": lambda q: f"https://www.youtube.com/results?search_query={quote_plus(q)}",
    "article": lambda q: f"https://www.geeksforgeeks.org/search/?gq={quote_plus(q)}",
    "docs": lambda q: f"https://developer.mozilla.org/en-US/search?q={quote_plus(q)}",
    "course": lambda q: f"https://www.classcentral.com/search?q={quote_plus(q)}&free=true",
    "freecodecamp": lambda q: f"https://www.freecodecamp.org/news/search/?query={quote_plus(q)}",
    "khanacademy": lambda q: f"https://www.khanacademy.org/search?page_search_query={quote_plus(q)}",
    "coursera": lambda q: f"https://www.coursera.org/search?query={quote_plus(q)}",
    "web": lambda q: f"https://www.google.com/search?q={quote_plus(q)}",
}
COST = {"coursera": "Free to audit · certificate may be paid", "course": "Free courses (Class Central filter)"}


def link_resources(items):
    for r in items:
        r["type"] = r.get("type") if r.get("type") in LINKS else "web"
        r["url"] = LINKS[r["type"]](r.get("query") or r.get("title", ""))
        r["cost"] = COST.get(r["type"], "Free")
    return items


@router.get("/learning")
async def learning(job_id: str, user=Depends(current_user)):
    cached = await db.learning.find_one({"user_id": user["id"], "job_id": job_id}, {"_id": 0})
    if cached:
        return cached
    job, resume = await _job(job_id), await get_resume(user["id"])
    sid = job.get("sector") or careers.classify(job["title"])
    prompt = f"""{_resume_ctx(resume)}
TARGET JOB: {job['title']} at {job['company']} (sector: {sid}). Skills: {', '.join(job.get('skills', []))}
Pick the 5 most important topics this candidate must learn or revise for this job (prioritise gaps; fit the profession, not only technical topics).
For each topic give 4 resources as SEARCH queries (we turn them into search links, so never invent URLs or course names).
Types: "youtube" (videos), "khanacademy" (maths/science/finance basics), "coursera" (courses), "course" (free course finder), "web" (general search),
"article"/"docs"/"freecodecamp" (ONLY for programming topics).
Return JSON: {{"topics": [{{"topic": str, "why": str, "resources": [{{"title": str, "type": str, "query": str (precise search query)}}]}}]}}"""
    data = await ask_json(SYS, prompt)
    for t in data.get("topics", []):
        link_resources(t.get("resources", []))
    doc = {"user_id": user["id"], "job_id": job_id, "topics": data.get("topics", []), "created_at": now_iso()}
    await db.learning.insert_one(doc)
    doc.pop("_id", None)
    return doc


class ExperienceIn(BaseModel):
    company: str = Field(min_length=1, max_length=80)
    role: str = Field(min_length=1, max_length=100)
    year: int = Field(ge=2000, le=2100)
    type: str = Field(pattern="^(Interview|OA)$")
    outcome: str = Field(pattern="^(Selected|Rejected|Pending|Withdrew)$")
    difficulty: str = Field(pattern="^(Easy|Medium|Hard)$")
    rounds: Optional[int] = Field(default=None, ge=1, le=20)
    content: str = Field(min_length=30, max_length=6000)
    questions: List[str] = []
    sector: str = ""
    level: str = Field(default="", max_length=30)
    stages: List[str] = Field(default=[], max_length=10)
    skills_tested: List[str] = Field(default=[], max_length=15)


@router.post("/experiences")
async def add_experience(body: ExperienceIn, user=Depends(current_user)):
    doc = {"id": str(uuid.uuid4()), **body.model_dump(), "company": body.company.strip(),
           "company_key": body.company.strip().lower(), "questions": [q.strip() for q in body.questions if q.strip()][:20],
           "sector": body.sector or careers.classify(body.role), "verified": False, "hidden": False, "reports": [], "reports_n": 0, "source": "candidate",
           "author": user["name"].split()[0] if user.get("name") else "Member", "user_id": user["id"], "created_at": now_iso()}
    await db.experiences.insert_one(doc)
    await log_activity(user["id"], "community", f"Shared a {body.type} experience for {body.company}")
    doc.pop("_id", None)
    doc.pop("user_id", None)
    return doc


@router.get("/experiences")
async def list_experiences(company: str = "", type: str = "", user=Depends(current_user)):
    q = {}
    if company:
        q["company_key"] = company.strip().lower()
    if type in ("Interview", "OA"):
        q["type"] = type
    items = await db.experiences.find({**q, "hidden": {"$ne": True}}, {"_id": 0, "user_id": 0, "reports": 0}).sort("created_at", -1).to_list(100)
    return {"experiences": items}


class ReportIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/experiences/{exp_id}/report")
async def report_experience(exp_id: str, body: ReportIn, user=Depends(current_user)):
    r = await db.experiences.update_one({"id": exp_id, "reports.user_id": {"$ne": user["id"]}},
                                        {"$push": {"reports": {"user_id": user["id"], "reason": body.reason, "at": now_iso()}}, "$inc": {"reports_n": 1}})
    return {"ok": True, "recorded": r.modified_count == 1}


class ModerateIn(BaseModel):
    verified: Optional[bool] = None
    hidden: Optional[bool] = None


@router.get("/admin/experiences")
async def admin_experiences(admin=Depends(require_admin)):
    items = await db.experiences.find({}, {"_id": 0}).sort([("reports_n", -1), ("created_at", -1)]).to_list(300)
    return {"experiences": items}


@router.post("/admin/experiences/{exp_id}")
async def moderate_experience(exp_id: str, body: ModerateIn, admin=Depends(require_admin)):
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    await db.experiences.update_one({"id": exp_id}, {"$set": {**upd, "moderated_by": admin["email"], "moderated_at": now_iso()}})
    return {"ok": True}


@router.get("/experiences/insights")
async def experience_insights(company: str, user=Depends(current_user)):
    key = company.strip().lower()
    n = await db.experiences.count_documents({"company_key": key, **TRUSTED})
    if n == 0:
        return {"count": 0, "insights": None}
    cached = await db.insights.find_one({"company_key": key, "count": n}, {"_id": 0})
    if cached:
        return cached
    ctx = await _experience_ctx(company)
    data = await ask_json(SYS, f"""{ctx}
Summarise ONLY what these real experiences say. Return JSON: {{"most_asked": [str], "patterns": [str], "topics": [str], "tips": [str]}}""")
    doc = {"company_key": key, "count": n, "insights": data}
    await db.insights.insert_one(doc)
    doc.pop("_id", None)
    return doc


def _excerpt(text, n=3, size=5000):
    if len(text) <= n * size:
        return text
    starts = sorted(random.sample(range(0, len(text) - size), n))
    return "\n...\n".join(text[a:a + size] for a in starts)


class OAGenIn(BaseModel):
    topic: str = ""
    company: str = ""
    difficulty: str = Field(default="Medium", pattern="^(Easy|Medium|Hard)$")
    proctored: bool = False
    oa_company_id: str = ""
    job_id: str = ""
    sector: str = ""
    assessment_type: str = Field(default="Full OA", max_length=60)
    duration_minutes: int = Field(default=0, ge=0, le=180)
    num_questions: int = Field(default=0, ge=0, le=60)
    skill_areas: List[str] = Field(default=[], max_length=10)
    level: str = Field(default="", max_length=20)


GENERAL = {"id": "other", "name": "General", "coding": False, "competencies": ["Role knowledge", "Reasoning", "Communication", "Judgement"],
           "oa": [careers.S("Role Knowledge", ["mcq"], "core knowledge the role needs"), careers.APT, careers.SJT,
                  careers.S("Written Response", ["written"], "a short practical written task for the role")]}

Q_SCHEMA = ('{"type": "mcq", "question": str, "options": [str,str,str,str], "answer_index": int, "explanation": str} | '
            '{"type": "numeric", "question": str, "answer": number, "tolerance": number (absolute; 0 for exact), "unit": str, "explanation": str} | '
            '{"type": "written", "question": str (a case, scenario, role-play reply, email, plan or drafting task), "rubric": str (what a strong answer covers), "explanation": str (model answer outline)}')


def _sector_for(body, job, profile_sectors):
    sid = body.sector or (job or {}).get("sector") or careers.classify(body.topic)
    if sid == "other" and profile_sectors:
        sid = profile_sectors[0]
    return sid


def _oa_prompt(sec, body, job, evidence):
    at = body.assessment_type or "Full OA"
    full = at.lower().startswith("full")
    secs = sec["oa"] if full else [s for s in sec["oa"] if any(w in s["name"].lower() for w in at.lower().split()[:2])] or \
        [careers.S(at, sorted({t for s in sec["oa"] for t in s["types"]}), f"{at} for the role")]
    coding_only = "coding" in at.lower()
    want_code = bool(sec.get("coding")) and (full or coding_only)
    n = body.num_questions or (6 if not full else 5) * (1 if not full else 1)
    per = max(2, round((body.num_questions or 5 * len(secs)) / max(1, len(secs)))) if not coding_only else 0
    dur = body.duration_minutes or (40 if full else 25)
    role = (job or {}).get("title") or body.topic or sec["name"]
    jobtxt = (f"JOB POSTING (base the questions ONLY on this posting's requirements; do not use resume data): {job['title']} at {job['company']} "
              f"({job.get('level', '')}). Skills: {', '.join(job.get('skills', []))}\n{(job.get('description') or '')[:4000]}\n") if job else ""
    gov = sec["id"] == "government"
    return f"""Create a realistic, profession-appropriate online assessment.
TARGET: {role}{(' at ' + body.company) if body.company and not job else ''}. Sector: {sec['name']}. Candidate level: {body.level or 'as fits the role'}.
Difficulty: {body.difficulty}. Assessment type: {at}. Duration: {dur} minutes. Focus skill areas: {', '.join(body.skill_areas) or 'the core skills of the role'}.
{jobtxt}{evidence}
SECTIONS to build (name, allowed question types, focus):
{json.dumps([{**s, "questions": per} for s in secs]) if not coding_only else '[] (coding only)'}
Rules: questions must test what employers in THIS profession actually check (never DSA/coding for non-technical roles).
Use only the allowed types per section. MCQs have exactly one correct option. Numeric answers must be exactly computable from the question.
Written tasks must be answerable in ~5 minutes with a clear rubric. All content factually correct and unique.
{'Follow the commonly published structure of this examination; the pattern_note MUST say it is a practice pattern and to verify with the latest official notification.' if gov else 'Do not claim the questions come from a real company test.'}
{sec.get('note', '')}
Return JSON: {{"title": str, "duration_minutes": {dur}, "pattern_note": str (one line describing what this assessment covers),
"sections": [{{"name": str, "questions": [{Q_SCHEMA}]}}],
"coding": {'[{"title": str, "difficulty": str, "problem": str, "input_format": str, "output_format": str, "examples": [{"input": str (exact stdin), "output": str (exact stdout)}], "constraints": str}] (stdin/stdout programs) (' + ('2-3' if coding_only else '2') + ' problems)' if want_code else '[] (no coding for this assessment)'}}}"""


@router.get("/oa-companies")

async def oa_companies(user=Depends(current_user)):
    items = await db.oa_companies.find({"active": True}, {"_id": 0, "id": 1, "name": 1, "description": 1, "profile": 1, "blueprint": 1}).sort("name", 1).to_list(200)
    for c in items:
        p = c.pop("profile", None) or {}
        bp = c.pop("blueprint", None) or {}
        c["summary"], c["duration_minutes"] = p.get("summary", ""), bp.get("duration_minutes") or p.get("duration_minutes")
        c["sections"] = [f"{x['name']} ({x['count']})" for x in bp["sections"]] if bp.get("sections") else [x.get("name") for x in p.get("sections", [])]
    return {"companies": items}


FLAG_WEIGHTS = {"tab_switch": 10, "window_blur": 4, "fullscreen_exit": 8, "copy_paste": 6, "camera_off": 15,
                "mic_off": 10, "camera_blocked": 12, "loud_noise": 3, "phone_detected": 20, "multiple_faces": 25,
                "different_person": 30, "no_face": 6, "gaze_away": 4, "background_voice": 8}


class OAFlagIn(BaseModel):
    type: str
    detail: str = Field(default="", max_length=200)


def proctor_report(t):
    if not t.get("proctored"):
        return None
    flags = t.get("flags", [])
    counts = {}
    for f in flags:
        counts[f["type"]] = counts.get(f["type"], 0) + 1
    score = max(0, 100 - sum(FLAG_WEIGHTS.get(k, 0) * v for k, v in counts.items()))
    return {"integrity_score": score, "risk": "Low" if score >= 80 else "Medium" if score >= 50 else "High",
            "total_flags": len(flags), "counts": counts, "timeline": flags[:100]}


@router.post("/mock-oa/{test_id}/flag")
async def oa_flag(test_id: str, body: OAFlagIn, user=Depends(current_user)):
    if body.type not in FLAG_WEIGHTS:
        raise HTTPException(400, "Unknown flag type")
    r = await db.mock_tests.update_one(
        {"id": test_id, "user_id": user["id"], "proctored": True, "result": {"$exists": False}, "flags.299": {"$exists": False}},
        {"$push": {"flags": {"type": body.type, "detail": body.detail, "at": now_iso()}}})
    return {"ok": True, "recorded": r.modified_count == 1}


@router.post("/mock-oa/generate")
async def oa_generate(body: OAGenIn, user=Depends(current_user)):
    oc = job = None
    if body.job_id:
        job = await _job(body.job_id)
        if not job.get("sector"):
            job["sector"] = careers.classify(job["title"], job.get("description") or "")
        body.company, body.topic, body.oa_company_id = job["company"], job["title"], ""
    if body.oa_company_id:
        oc = await db.oa_companies.find_one({"id": body.oa_company_id, "active": True}, {"_id": 0})
        if not oc:
            raise HTTPException(404, "This company OA is no longer available.")
        body.company = oc["name"]
    if not body.topic.strip() and not body.company.strip() and not body.sector:
        raise HTTPException(400, "Choose a sector, enter a role/exam or pick a company.")
    uc = await user_ctx(user["id"])
    sid = _sector_for(body, job, uc["sectors"])
    sec = careers.sector(sid) if sid in {s["id"] for s in careers.sectors()} else GENERAL
    target = f"{body.company.strip()} " if body.company.strip() else ""
    data = None
    if oc and (oc.get("blueprint") or {}).get("sections"):
        from routes_oa_builder import build_from_blueprint
        data = await build_from_blueprint(oc)  # raises 409 instead of silently falling back to a generic AI test
    if data:
        prompt = None
    elif oc:
        prompt = f"""Create a NEW mock online assessment that mimics the real {oc['name']} OA as closely as possible.
Base it strictly on the company dataset below (real past questions / pattern notes). Match its section structure, number of questions per
section, topics, question style, difficulty and coding-problem style. Write NEW questions of the same type and level; never copy a question verbatim.
Target role: {body.topic or 'as in the dataset'}. Difficulty preference: {body.difficulty} (the dataset's real level wins if they conflict).
PATTERN PROFILE: {json.dumps(oc.get('profile') or {})[:3000]}
DATASET EXCERPTS:
{_excerpt(oc.get('dataset_text', ''))}
Return JSON: {{"title": str (include "{oc['name']}"), "duration_minutes": int, "pattern_note": str (one line describing the real pattern),
"sections": [{{"name": str, "questions": [{Q_SCHEMA}]}}] (1-4 sections as in the profile, max 12 questions each, all factually correct),
"coding": [{{"title": str, "difficulty": str, "problem": str, "input_format": str, "output_format": str, "examples": [{{"input": str (exact stdin), "output": str (exact stdout)}}], "constraints": str}}] (stdin/stdout programs) (0-3 problems as in the profile)}}"""
    else:
        prompt = _oa_prompt(sec, body, job, await _experience_ctx("" if job else body.company, sid, body.topic))
    if prompt:
        data = await ask_json(SYS, prompt)
    tid = str(uuid.uuid4())
    qn, dropped = 0, []
    data["coding"] = data.get("coding") or []
    for s in data.get("sections", []):
        clean_q = []
        for q in s.get("questions", []):
            if q.get("type") in ("coding", "code", "programming") or (q.get("problem") and not q.get("options")):
                data["coding"].append({"title": q.get("title") or q.get("question", "")[:60], "problem": q.get("problem") or q.get("question", ""), **{k: q[k] for k in
                                       ("difficulty", "input_format", "output_format", "constraints", "examples") if q.get(k)}})
                continue
            q["type"] = q.get("type") if q.get("type") in ("mcq", "numeric", "written") else ("mcq" if q.get("options") else "written")
            if q["type"] == "mcq" and (len(q.get("options") or []) < 2 or not isinstance(q.get("answer_index"), int)):
                dropped.append(q.get("bank_id") or q.get("question", "")[:40])
                continue
            if q["type"] == "numeric" and not isinstance(q.get("answer"), (int, float)):
                dropped.append(q.get("bank_id") or q.get("question", "")[:40])
                continue
            qn += 1
            q["id"] = f"q{qn}"
            clean_q.append(q)
        s["questions"] = clean_q
    data["sections"] = [s for s in data.get("sections", []) if s["questions"]]
    for i, c in enumerate(data.get("coding", []) or []):
        c["id"] = f"c{i + 1}"
    for c in data["coding"]:
        if c.get("tests"):
            await db.code_tests.update_one({"key": f"oa:{tid}:{c['id']}"}, {"$set": {"id": str(uuid.uuid4()), "key": f"oa:{tid}:{c['id']}", "tests": c.pop("tests"),
                                           "io_note": c.pop("io_note", ""), "created_at": now_iso()}}, upsert=True)
    for prefix, k in (("s", "sql"), ("w", "web")):
        data[k] = data.get(k) or []
        for i, c in enumerate(data[k]):
            c["id"] = f"{prefix}{i + 1}"
    data["sector"], data["sector_name"], data["note"] = sec["id"], sec["name"], sec.get("note", "")
    order = [q["id"] for s in data["sections"] for q in s["questions"]] + [c["id"] for k in ("coding", "sql", "web") for c in data[k]]
    if data.get("blueprint"):
        want = sum(s["count"] for s in data["blueprint"]["sections"])
        bank_ids = [q.get("bank_id") for s in data["sections"] for q in s["questions"]] + [c.get("bank_id") for k in ("coding", "sql", "web") for c in data[k]]
        log.info("OA session %s for %s: requested=%s final=%s distinct=%s dropped=%s", tid, oc["name"], want, len(order), len(set(bank_ids)), dropped)
        if len(order) != want or len(set(bank_ids)) != want:
            raise HTTPException(500, f"Assessment build mismatch: {want} questions configured but {len(set(bank_ids))} valid distinct questions were prepared"
                                     f"{f' ({len(dropped)} failed validation)' if dropped else ''}. Please report this to the admin.")
    data["question_order"] = order
    doc = {"id": tid, "user_id": user["id"], "topic": body.topic, "company": body.company, "oa_company_id": body.oa_company_id, "job_id": body.job_id,
           "difficulty": body.difficulty, "sector": sec["id"], "assessment_type": body.assessment_type, "proctored": body.proctored, "flags": [], "test": data, "created_at": now_iso()}
    await db.mock_tests.insert_one(doc)
    await log_activity(user["id"], "oa", f"Started {target}mock OA: {data.get('title', body.topic)}")
    pub_q = lambda q: {k: q.get(k) for k in ("id", "type", "question", "options", "unit") if q.get(k) is not None}
    public = {**data, "sections": [{"name": s["name"], "questions": [pub_q(q) for q in s["questions"]]} for s in data["sections"]],
              "sql": [_pub_sql(c) for c in data["sql"]], "web": [_pub_web(c) for c in data["web"]]}
    return {"id": tid, "company": body.company, "topic": body.topic, "difficulty": body.difficulty, "proctored": body.proctored, "test": public}


def _pub_sql(c):
    t = next((x for x in c["tests"] if x["visible"]), c["tests"][0])
    return {k: c.get(k) for k in ("id", "title", "difficulty", "problem", "schema", "ordered", "section")} | {"sample_data": t["data"], "sample_output": t["expected"]}


def _pub_web(c):
    return {k: c.get(k) for k in ("id", "title", "difficulty", "problem", "starter", "section")} | {
        "requirements": [{"name": t["name"], "why": t.get("why", "")} for t in c["tests"]]}


class OASubmitIn(BaseModel):
    test_id: str
    answers: Dict[str, Any] = {}
    code: Dict[str, str] = {}
    languages: Dict[str, str] = {}
    sql: Dict[str, str] = {}
    web: Dict[str, Dict[str, str]] = {}
    time_taken_sec: int = 0
    auto_reason: str = Field(default="", max_length=120)


def _num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _numeric_ok(given, q):
    g, a = _num(given), _num(q.get("answer"))
    if g is None or a is None:
        return False
    tol = _num(q.get("tolerance")) or 0
    return abs(g - a) <= max(tol, abs(a) * 0.01, 1e-9)


WRITTEN_PTS = 3


@router.post("/mock-oa/submit")
async def oa_submit(body: OASubmitIn, user=Depends(current_user)):
    t = await db.mock_tests.find_one({"id": body.test_id, "user_id": user["id"]}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Test not found")
    if t.get("result"):
        return t["result"]
    review, sections, written = [], [], []
    for s in t["test"].get("sections", []):
        for q in s.get("questions", []):
            qt = q.get("type", "mcq")
            given = body.answers.get(q["id"])
            item = {"id": q["id"], "type": qt, "section": s["name"], "question": q["question"], "given": given, "explanation": q.get("explanation", "")}
            if qt == "mcq":
                g = given if isinstance(given, int) else None
                item.update(options=q.get("options", []), given=g, answer_index=q.get("answer_index"), correct=g == q.get("answer_index"), points=float(g == q.get("answer_index")), max=1)
            elif qt == "numeric":
                ok = _numeric_ok(given, q)
                item.update(answer=q.get("answer"), unit=q.get("unit", ""), correct=ok, points=float(ok), max=1)
            else:
                text = str(given or "").strip()[:4000]
                item.update(given=text, rubric=q.get("rubric", ""), points=0.0, max=WRITTEN_PTS, correct=None)
                if text:
                    written.append(item)
            review.append(item)
    coding = []
    probs = t["test"].get("coding", [])
    submitted = [(p, body.code.get(p["id"], "").strip()) for p in probs]

    async def _coding():
        if not any(code for _, code in submitted):
            return [{"id": p["id"], "score": 0, "verdict": "Not Attempted", "feedback": "No code submitted.", "complexity": "-"} for p in probs]

        async def _j(p, code):
            try:
                return await routes_code.judge(f"oa:{t['id']}:{p['id']}", p, body.languages.get(p["id"], ""), code)
            except HTTPException:
                return None
        judged = await asyncio.gather(*[_j(p, code) for p, code in submitted])
        ev = await ask_json(SYS, "Evaluate these coding answers strictly like an OA auto-grader + reviewer. Empty code scores 0. "
                            "When judge test results are given, the score must mainly reflect the pass rate.\n" +
                            "\n\n".join(f"PROBLEM {p['id']}: {p['title']}\n{p['problem']}\nLANGUAGE: {body.languages.get(p['id'], 'unspecified')}\n"
                                          f"CODE:\n{code[:4000] or '(empty)'}\nJUDGE: {routes_code.summary(j) if j else 'not run'}"
                                          for (p, code), j in zip(submitted, judged)) +
                            '\nReturn JSON: {"results": [{"id": str, "score": int 0-10, "verdict": "Correct"|"Partially Correct"|"Incorrect"|"Not Attempted", "feedback": str, "complexity": str}]}')
        res = ev.get("results", [])
        jmap = {p["id"]: j for (p, _), j in zip(submitted, judged)}
        for c in res:
            j = jmap.get(c.get("id"))
            if j and j["total"]:
                c["tests_passed"], c["tests_total"] = j["passed"], j["total"]
                c["score"] = round(0.7 * 10 * j["passed"] / j["total"] + 0.3 * int(c.get("score") or 0))
        return res

    async def _written():
        if not written:
            return {}
        ev = await ask_json(SYS, f"Grade these written answers for a {t['test'].get('sector_name', '')} assessment ({t['test'].get('title')}). "
                            "Use the rubric; be fair; a concise answer that covers the rubric scores well. Score 0-5.\n" +
                            "\n\n".join(f"ID {w['id']}\nTASK: {w['question']}\nRUBRIC: {w['rubric']}\nANSWER: {w['given']}" for w in written) +
                            '\nReturn JSON: {"results": [{"id": str, "score": int 0-5, "feedback": str (2 sentences), "model_answer": str (short outline)}]}')
        return {r.get("id"): r for r in ev.get("results", [])}

    async def _judged(kind, p):
        if kind == "sql":
            q = (body.sql.get(p["id"]) or "").strip()
            res = await judges.sql_suite(q, p) if q else None
        else:
            w = body.web.get(p["id"]) or {}
            st = p.get("starter") or {}
            done = any((w.get(k) or "").strip() != (st.get(k) or "").strip() for k in ("html", "css", "js"))
            res = await judges.web_suite(w.get("html", ""), w.get("css", ""), w.get("js", ""), p) if done else None
        if not res:
            return {"id": p["id"], "title": p["title"], "kind": kind, "score": 0, "verdict": "Not Attempted", "feedback": "No answer submitted.", "complexity": "-"}
        v = judges.verdict(res)
        return {"id": p["id"], "title": p["title"], "kind": kind, "score": round(10 * res["passed"] / max(1, res["total"])), "verdict": v, "complexity": "-",
                "tests_passed": res["passed"], "tests_total": res["total"],
                "feedback": f"{res['passed']}/{res['total']} test cases passed." + (" Accepted." if v == "Accepted" else " Every test case must pass to be accepted.")}

    extra = [("sql", p) for p in t["test"].get("sql", [])] + [("web", p) for p in t["test"].get("web", [])]
    coding_r, written_r, *extra_r = await asyncio.gather(_coding(), _written(), *[_judged(k, p) for k, p in extra], return_exceptions=True)
    coding = coding_r if isinstance(coding_r, list) else [{"id": p["id"], "score": 0, "verdict": "Not graded", "feedback": "Grading was unavailable; try again later.", "complexity": "-"} for p in probs]
    for c in coding:
        p = next((x for x in probs if x["id"] == c.get("id")), {})
        c.setdefault("title", p.get("title", ""))
        c.setdefault("kind", "coding")
    coding += [r if isinstance(r, dict) else {"id": p["id"], "title": p["title"], "kind": k, "score": 0, "verdict": "Not graded", "feedback": "Judge error.", "complexity": "-"}
               for r, (k, p) in zip(extra_r, extra)]
    probs = probs + [p for _, p in extra]
    wmap = written_r if isinstance(written_r, dict) else {}
    for it in review:
        if it["type"] == "written" and it["id"] in wmap:
            r = wmap[it["id"]]
            sc = max(0, min(5, int(r.get("score") or 0)))
            it.update(points=round(sc / 5 * WRITTEN_PTS, 2), ai_score=sc, feedback=r.get("feedback", ""), model_answer=r.get("model_answer", ""), correct=sc >= 3)
        elif it["type"] == "written" and it["given"]:
            it["feedback"] = "AI grading was unavailable for this answer."
    for s in t["test"].get("sections", []):
        items = [r for r in review if r["section"] == s["name"]]
        pts, mx = sum(r["points"] for r in items), sum(r["max"] for r in items)
        sections.append({"name": s["name"], "correct": sum(1 for r in items if r.get("correct")), "total": len(items), "points": round(pts, 2), "max": mx, "pct": round(100 * pts / mx) if mx else 0})
    obj = [r for r in review if r["type"] != "written"]
    mcq_c, mcq_t = sum(1 for r in obj if r["correct"]), len(obj)
    code_pts, code_max = sum(int(c.get("score", 0)) for c in coding), 10 * len(probs)
    q_pts, q_max = sum(r["points"] for r in review), sum(r["max"] for r in review)
    pct = round(100 * (q_pts + code_pts / 10 * 2) / max(1, q_max + 2 * len(probs)))
    prev = await db.mock_tests.find({"user_id": user["id"], "result": {"$exists": True}, "sector": t.get("sector")}, {"_id": 0, "result.score_pct": 1}).to_list(50)
    ps = [x["result"]["score_pct"] for x in prev]
    progress = {"attempts_before": len(ps), "previous_avg": round(sum(ps) / len(ps)) if ps else None, "previous_best": max(ps) if ps else None,
                "delta_vs_avg": (pct - round(sum(ps) / len(ps))) if ps else None}
    insights = {}
    try:
        weak = [f"[{r['section']}] {r['question'][:140]}" for r in review if r.get("correct") is False][:12]
        insights = await ask_json(SYS, f"""Assessment: {t['test'].get('title')} (sector {t['test'].get('sector_name', '')}). Score {pct}%.
Section scores: {[(s['name'], s['pct']) for s in sections]}. Coding: {[(c.get('id'), c.get('score')) for c in coding]}.
Questions missed: {weak}
Return JSON: {{"strengths": [str] (2-4), "weaknesses": [str] (2-4), "skill_gaps": [str] (3-5 concrete skills), "next_plan": [str] (4 short practice steps for the next week),
"resources": [{{"title": str, "type": "youtube"|"khanacademy"|"coursera"|"course"|"web", "query": str}}] (4 search queries; never invent URLs)}}""")
        link_resources(insights.get("resources", []))
    except HTTPException:
        insights = {"note": "AI insights were unavailable; your scores are complete."}
    result = {"score_pct": pct, "mcq_correct": mcq_c, "mcq_total": mcq_t, "coding_points": code_pts, "coding_max": code_max,
              "sections": sections, "coding": coding, "review": review, "time_taken_sec": body.time_taken_sec, "submitted_at": now_iso(),
              "auto_reason": body.auto_reason, "proctoring": proctor_report(t), "insights": insights, "progress": progress,
              "sector": t.get("sector"), "note": t["test"].get("note", "")}
    await db.mock_tests.update_one({"id": body.test_id}, {"$set": {"result": result}})
    await log_activity(user["id"], "oa", f"Completed mock OA — scored {pct}%")
    return result


@router.get("/mock-oa/history")
async def oa_history(user=Depends(current_user)):
    items = await db.mock_tests.find({"user_id": user["id"], "result": {"$exists": True}},
                                     {"_id": 0, "id": 1, "topic": 1, "company": 1, "difficulty": 1, "created_at": 1, "proctored": 1,
                                      "test.title": 1, "sector": 1, "result.score_pct": 1, "result.proctoring.integrity_score": 1}).sort("created_at", -1).to_list(20)
    return {"history": items}


class InterviewStartIn(BaseModel):
    role: str = Field(min_length=2, max_length=100)
    company: str = ""
    interview_type: str = Field(default="Mixed", pattern="^(Technical|HR|Behavioral|Mixed|Role-play|Case|Scenario|Managerial|Teaching demo|Government|Field service|Portfolio)$")
    sector: str = ""
    num_questions: int = Field(default=5, ge=3, le=10)
    mode: str = Field(default="text", pattern="^(text|voice)$")
    level: str = Field(default="Auto", pattern="^(Auto|Fresher|Junior|Mid|Senior)$")
    job_id: str = ""
    job_description: str = Field(default="", max_length=6000)
    proctored: bool = False


class InterviewFinishIn(BaseModel):
    session_id: str


class AnswerMetrics(BaseModel):
    words: int = Field(ge=0, le=5000)
    duration_sec: float = Field(ge=0, le=3600)
    long_pauses: int = Field(default=0, ge=0, le=500)
    longest_pause_sec: float = Field(default=0, ge=0, le=3600)


class InterviewAnswerIn(BaseModel):
    session_id: str
    answer: str = Field(min_length=1, max_length=5000)
    metrics: Optional[AnswerMetrics] = None
    code: str = Field(default="", max_length=20000)
    language: str = Field(default="", max_length=30)


FILLERS = ["um", "uh", "erm", "hmm", "like", "you know", "basically", "actually", "literally", "i mean", "kind of",
           "sort of", "so yeah", "okay so"]
_FILLER_RX = {f: re.compile(rf"(?<![\w']){re.escape(f)}(?![\w'])", re.I) for f in FILLERS}


def answer_coach(text, m):
    fillers = {f: len(rx.findall(text)) for f, rx in _FILLER_RX.items()}
    fillers = {k: v for k, v in fillers.items() if v}
    words = m["words"] if m else len(text.split())
    dur = m["duration_sec"] if m else 0
    return {"words": words, "duration_sec": round(dur, 1), "wpm": round(words / dur * 60) if dur >= 3 else None,
            "fillers": fillers, "filler_total": sum(fillers.values()),
            "long_pauses": m["long_pauses"] if m else 0, "longest_pause_sec": round(m["longest_pause_sec"], 1) if m else 0}


def pace_label(wpm):
    if wpm is None:
        return "Not enough audio"
    return "Too slow" if wpm < 100 else "Good pace" if wpm <= 165 else "Too fast"


def voice_coach(turns):
    rows = [t["coach"] for t in turns if t.get("answer") and t.get("coach") and t.get("voice")]
    if not rows:
        return None
    paced = [r for r in rows if r["wpm"]]
    total_words = sum(r["words"] for r in paced)
    total_dur = sum(r["duration_sec"] for r in paced)
    wpm = round(total_words / total_dur * 60) if total_dur >= 3 else None
    agg = {}
    for r in rows:
        for k, v in r["fillers"].items():
            agg[k] = agg.get(k, 0) + v
    ftotal = sum(agg.values())
    words = sum(r["words"] for r in rows)
    return {"avg_wpm": wpm, "pace_label": pace_label(wpm), "filler_total": ftotal,
            "fillers_per_100_words": round(100 * ftotal / words, 1) if words else 0,
            "top_fillers": sorted(agg.items(), key=lambda x: -x[1])[:6],
            "long_pauses": sum(r["long_pauses"] for r in rows), "longest_pause_sec": max(r["longest_pause_sec"] for r in rows),
            "per_question": [{"q": i + 1, **r, "pace_label": pace_label(r["wpm"])} for i, r in enumerate(rows)]}


def _iv_ctx(s, resume):
    return (f"You are reviewing a {s['interview_type']} interview for the role of {s['role']}"
            f"{' at ' + s['company'] if s['company'] else ''} (candidate level: {s.get('level', 'Auto')}).\n{_resume_ctx(resume)}")


def _q_out(t):
    return {k: t.get(k) for k in ("question", "reaction", "stage", "difficulty", "kind", "coding")}


# Background evaluation: grading runs off the critical path so the conversation does not
# stall between questions. Evaluations are written per-turn and only surface in the report.
_PENDING_EVALS: Dict[str, set] = {}


def _spawn_eval(s, rctx, snapshot, idx):
    async def run():
        try:
            ev = await interview_ai.evaluate(s, rctx, snapshot)
            await db.interviews.update_one({"id": s["id"]}, {"$set": {f"turns.{idx}.evaluation": ev}})
        except Exception:
            pass  # the final report fills any gap synchronously
    task = asyncio.create_task(run())
    tasks = _PENDING_EVALS.setdefault(s["id"], set())
    tasks.add(task)
    task.add_done_callback(lambda t: tasks.discard(t))


async def _await_pending(session_id):
    tasks = list(_PENDING_EVALS.get(session_id, set()))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _PENDING_EVALS.pop(session_id, None)


@router.post("/interview/start")
async def interview_start(body: InterviewStartIn, user=Depends(current_user)):
    resume = await get_resume(user["id"])
    s = {"id": str(uuid.uuid4()), "user_id": user["id"], **body.model_dump(), "turns": [], "flags": [], "status": "active", "created_at": now_iso()}
    if body.job_id and not body.job_description:
        job = await db.jobs.find_one({"id": body.job_id}, {"_id": 0, "description": 1, "skills": 1, "level": 1, "sector": 1})
        if job:
            s["job_description"] = f"Skills: {', '.join(job.get('skills', []))}. Level: {job.get('level', '')}.\n{(job.get('description') or '')[:2500]}"
            s["sector"] = s.get("sector") or job.get("sector") or ""
    if not s.get("sector"):
        sid = careers.classify(body.role)
        s["sector"] = sid if sid != "other" else ((await user_ctx(user["id"], resume))["sectors"] or [""])[0]
    s["evidence"] = (await _experience_ctx(body.company, s["sector"], body.role))[:2500]
    q = await interview_ai.next_question(s, _resume_ctx(resume), [])
    s["turns"].append(q)
    await db.interviews.insert_one(s)
    await log_activity(user["id"], "interview", f"Started AI interview for {body.role}")
    return {"session_id": s["id"], "proctored": body.proctored, **_q_out(q), "index": 1, "total": body.num_questions}


@router.post("/interview/{session_id}/flag")
async def interview_flag(session_id: str, body: OAFlagIn, user=Depends(current_user)):
    if body.type not in FLAG_WEIGHTS:
        raise HTTPException(400, "Unknown flag type")
    r = await db.interviews.update_one(
        {"id": session_id, "user_id": user["id"], "proctored": True, "status": "active", "flags.299": {"$exists": False}},
        {"$push": {"flags": {"type": body.type, "detail": body.detail, "at": now_iso()}}})
    return {"ok": True, "recorded": r.modified_count == 1}


@router.post("/interview/answer")
async def interview_answer(body: InterviewAnswerIn, user=Depends(current_user)):
    s = await db.interviews.find_one({"id": body.session_id, "user_id": user["id"]}, {"_id": 0})
    if not s or s["status"] != "active":
        raise HTTPException(404, "Interview session not found or already completed")
    resume = await get_resume(user["id"])
    rctx = _resume_ctx(resume)
    turns = s["turns"]
    idx = len(turns) - 1
    cur = turns[idx]
    cur["answer"] = body.answer
    cur["voice"] = body.metrics is not None
    cur["coach"] = answer_coach(body.answer, body.metrics.model_dump() if body.metrics else None)
    set_fields = {f"turns.{idx}.answer": cur["answer"], f"turns.{idx}.voice": cur["voice"], f"turns.{idx}.coach": cur["coach"]}
    if body.code.strip():
        cur["code"], cur["language"] = body.code, body.language
        set_fields[f"turns.{idx}.code"], set_fields[f"turns.{idx}.language"] = body.code, body.language
    if cur.get("kind") == "coding" and body.code.strip():
        try:
            j = await routes_code.judge(f"iv:{s['id']}:{idx}", cur["coding"], body.language, body.code)
        except HTTPException:
            j = None
        if j:
            cur["judge"] = routes_code.summary(j)
            cur["tests_passed"], cur["tests_total"] = j["passed"], j["total"]
            set_fields.update({f"turns.{idx}.judge": cur["judge"], f"turns.{idx}.tests_passed": j["passed"], f"turns.{idx}.tests_total": j["total"]})
    # persist the answer with targeted updates so background evaluations are never clobbered
    await db.interviews.update_one({"id": s["id"]}, {"$set": set_fields})
    snapshot = turns[:]  # answered turn is snapshot[-1]; kept stable while we append the next question
    last = len(turns) >= s["num_questions"]
    if last:
        _spawn_eval(s, rctx, snapshot, idx)
        return {"done": True, "report": await _final_report(s, resume)}
    # grading runs in the background; return the next question immediately to keep the conversation flowing
    q = await interview_ai.next_question(s, rctx, turns)
    coding_done = s.get("coding_done", False)
    if interview_ai.wants_coding(s, turns):
        q = await interview_ai.coding_question(s, rctx, turns)
        coding_done = True
    await db.interviews.update_one({"id": s["id"]}, {"$push": {"turns": q}, "$set": {"coding_done": coding_done}})
    _spawn_eval(s, rctx, snapshot, idx)
    return {"done": False, **_q_out(q), "index": len(turns) + 1, "total": s["num_questions"]}


async def _final_report(s, resume):
    await _await_pending(s["id"])
    fresh = await db.interviews.find_one({"id": s["id"]}, {"_id": 0})
    turns = (fresh or s)["turns"]
    rctx = _resume_ctx(resume)
    missing = [i for i, t in enumerate(turns) if t.get("answer") and not t.get("evaluation")]
    if missing:
        evs = await asyncio.gather(*[interview_ai.evaluate(s, rctx, turns[:i + 1]) for i in missing], return_exceptions=True)
        for i, ev in zip(missing, evs):
            if not isinstance(ev, Exception):
                turns[i]["evaluation"] = ev
    answered = [t for t in turns if t.get("answer")]
    history = "\n".join(f"Q{i + 1}: {t['question']}\nA{i + 1}: {t['answer']}" for i, t in enumerate(answered))
    coach = voice_coach(turns)
    delivery = (f"\nVOICE DELIVERY METRICS: avg {coach['avg_wpm']} wpm ({coach['pace_label']}), {coach['filler_total']} filler words "
                f"{coach['top_fillers']}, {coach['long_pauses']} long pauses (longest {coach['longest_pause_sec']}s). "
                'Add key "delivery_feedback": [str] (3 concrete tips on pace, fillers, pauses).') if coach else ""
    report = await ask_json(SYS, f"""{_iv_ctx(s, resume)}{delivery}\n\nFULL TRANSCRIPT ({len(answered)} of {s['num_questions']} planned questions answered):\n{history}
Per-answer scores: {[t.get('evaluation', {}).get('score') for t in answered]}
Grade on correctness for this profession, relevance, completeness and clarity. Do not penalise short answers that are correct.
Never use accent, speech disfluency, disability-related speech patterns, appearance or emotion guesses as signals of ability.
Write the final interview report. Return JSON: {{"overall_score": int 0-100, "verdict": "Strong Hire"|"Hire"|"Lean Hire"|"Lean No Hire"|"No Hire",
"summary": str, "technical_score": int 0-100, "communication_score": int 0-100, "confidence_score": int 0-100,
"strengths": [str], "mistakes": [str], "improvements": [str], "recommendations": [str] (concrete next steps, resources or practice plan),
"per_question": [{{"question": str, "score": int 0-10, "comment": str}}],
"competencies": [{{"name": str (use: {', '.join(careers.sector(s['sector'])['competencies']) if s.get('sector') in {x['id'] for x in careers.sectors()} else 'Role knowledge, Problem solving, Communication, Judgement'}), "score": int 0-10, "feedback": str}}],
"answer_frameworks": [str] (3 frameworks/model-answer structures suited to this role, e.g. STAR, LAER for sales objections, SBAR for clinical handover),
"practice_questions": [str] (5 follow-up practice questions), "roadmap": [str] (4 step personalised improvement plan)}}""")
    report["voice_coach"] = coach
    report["trail"] = interview_ai.trail(turns)
    report["proctoring"] = proctor_report(fresh or s)
    await db.interviews.update_one({"id": s["id"]}, {"$set": {"turns": turns, "status": "completed", "report": report, "completed_at": now_iso()}})
    await log_activity(s["user_id"], "interview", f"Completed {s.get('mode', 'text')} AI interview for {s['role']} — {report.get('overall_score', 0)}/100")
    return report


@router.post("/interview/finish")
async def interview_finish(body: InterviewFinishIn, user=Depends(current_user)):
    s = await db.interviews.find_one({"id": body.session_id, "user_id": user["id"]}, {"_id": 0})
    if not s or s["status"] != "active":
        raise HTTPException(404, "Interview session not found or already completed")
    if not any(t.get("answer") for t in s["turns"]):
        await db.interviews.update_one({"id": s["id"]}, {"$set": {"status": "abandoned"}})
        return {"report": None}
    return {"report": await _final_report(s, await get_resume(user["id"]))}


@router.get("/interview/history")
async def interview_history(user=Depends(current_user)):
    items = await db.interviews.find({"user_id": user["id"], "status": "completed"},
                                     {"_id": 0, "id": 1, "role": 1, "company": 1, "interview_type": 1, "completed_at": 1,
                                      "report.overall_score": 1, "report.verdict": 1}).sort("completed_at", -1).to_list(20)
    return {"history": items}


@router.get("/interview/{session_id}")
async def interview_get(session_id: str, user=Depends(current_user)):
    s = await db.interviews.find_one({"id": session_id, "user_id": user["id"]}, {"_id": 0, "user_id": 0})
    if not s:
        raise HTTPException(404, "Not found")
    return s
