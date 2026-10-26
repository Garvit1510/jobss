import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from ai import ask_json
from auth import current_user
from database import db
import careers
from jobs_service import SOURCE_LABELS, enrich_job, refresh_all
from resume_parser import extract_text
from skills import canonical

router = APIRouter(prefix="/api")
LIST_PROJ = {"_id": 0, "description": 0, "unit": 0, "detail_url": 0, "fetched_at": 0}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


async def log_activity(user_id, kind, text):
    await db.activity.insert_one({"id": str(uuid.uuid4()), "user_id": user_id, "kind": kind, "text": text, "created_at": now_iso()})


async def get_resume(user_id):
    return await db.resumes.find_one({"user_id": user_id}, {"_id": 0, "raw_text": 0})


def user_skillset(resume):
    return {s.lower() for s in (resume or {}).get("skills", [])}


async def user_ctx(user_id, resume=None):
    resume = resume if resume is not None else await get_resume(user_id)
    return careers.ctx_from(resume, await db.career_profiles.find_one({"user_id": user_id}, {"_id": 0}))


RESUME_PROMPT = """Analyze this resume (it can be from ANY profession: tech, sales, finance, healthcare, teaching, trades, government, etc.)
and return JSON with exactly these keys:
{"name": str, "headline": str (e.g. "Registered Nurse - Critical Care" or "Full Stack Developer"), "summary": str (2-3 sentences),
"skills": [str] (concrete professional skills, tools, techniques and domain knowledge actually shown, canonical names, max 30),
"education": [{"degree": str, "institution": str, "year": str}], "education_level": str (highest level, e.g. "12th", "Diploma", "Bachelor's", "Master's", "PhD", ""),
"experience": [{"title": str, "company": str, "duration": str, "highlights": [str]}], "years_experience": number|null (total relevant years, null if unclear),
"projects": [{"name": str, "description": str, "tech": [str]}], "certifications": [str], "achievements": [str],
"job_families": [str] (1-3 best-fit sector ids from: SECTOR_IDS), "transferable_skills": [str] (skills useful across professions),
"score": int 0-100 (honest ATS + quality score), "score_breakdown": {"formatting": int, "impact": int, "skills": int, "experience": int} (each 0-100),
"strengths": [str], "improvements": [str] (specific, actionable),
"recommended_roles": [str] (6 realistic job titles this candidate is eligible for now, entry and experienced as appropriate)}
Use only information present in the resume; never invent employers, degrees, certifications, skills or years.

RESUME:
"""


@router.post("/resume/upload")
async def upload_resume(file: UploadFile = File(...), user=Depends(current_user)):
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 8 MB).")
    try:
        text = extract_text(file.filename, data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if len(text.strip()) < 80:
        raise HTTPException(400, "Could not read enough text from this file. Try a text-based PDF or DOCX.")
    a = await ask_json("You are an expert recruiter and resume analyst for every industry.", RESUME_PROMPT.replace("SECTOR_IDS", ", ".join(s["id"] for s in careers.sectors())) + text[:14000])
    resume = {
        "id": str(uuid.uuid4()), "user_id": user["id"], "filename": file.filename, "raw_text": text[:20000],
        "name": a.get("name") or user["name"], "headline": a.get("headline", ""), "summary": a.get("summary", ""),
        "skills": list(dict.fromkeys(canonical(s) for s in a.get("skills", []) if s))[:30],
        "education": a.get("education", []), "experience": a.get("experience", []), "projects": a.get("projects", []),
        "score": int(a.get("score") or 0), "score_breakdown": a.get("score_breakdown", {}),
        "strengths": a.get("strengths", []), "improvements": a.get("improvements", []),
        "recommended_roles": a.get("recommended_roles", [])[:8], "uploaded_at": now_iso(),
        "education_level": a.get("education_level", ""), "certifications": a.get("certifications", []), "achievements": a.get("achievements", []),
        "years_experience": a.get("years_experience") if isinstance(a.get("years_experience"), (int, float)) else None,
        "job_families": [x for x in a.get("job_families", []) if x in {s["id"] for s in careers.sectors()}], "transferable_skills": a.get("transferable_skills", []),
    }
    await db.resumes.delete_many({"user_id": user["id"]})
    await db.resumes.insert_one(resume)
    await db.prep_plans.delete_many({"user_id": user["id"]})
    await db.learning.delete_many({"user_id": user["id"]})
    await log_activity(user["id"], "resume", f"Resume analyzed — {len(resume['skills'])} skills found, score {resume['score']}/100")
    resume.pop("_id", None)
    resume.pop("raw_text", None)
    return resume


@router.get("/resume")
async def my_resume(user=Depends(current_user)):
    return {"resume": await get_resume(user["id"])}


@router.get("/dashboard")
async def dashboard(user=Depends(current_user)):
    resume = await get_resume(user["id"])
    acts = await db.activity.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(8)
    total_jobs = await db.jobs.count_documents({})
    stats = {"jobs_matched": 0, "avg_match": 0, "total_jobs": total_jobs}
    if resume:
        c = await user_ctx(user["id"], resume)
        scores = [careers.quick_score(c, j) async for j in db.jobs.find({"duplicate": {"$ne": True}}, {"_id": 0, "skills": 1, "title": 1, "sector": 1, "level": 1, "work_type": 1, "location": 1})]
        scores = sorted((s for s in scores if s is not None), reverse=True)
        stats["jobs_matched"] = sum(1 for s in scores if s >= 60)
        top = scores[:50]
        stats["avg_match"] = round(sum(top) / len(top)) if top else 0
    oa = await db.mock_tests.count_documents({"user_id": user["id"], "result": {"$exists": True}})
    iv = await db.interviews.count_documents({"user_id": user["id"], "status": "completed"})
    return {"user": {"name": user["name"], "email": user["email"]}, "resume": resume, "stats": {**stats, "oa_taken": oa, "interviews_done": iv}, "activity": acts}


def _job_query(q, work, level, source, country="", sector="all"):
    query = {"duplicate": {"$ne": True}}
    if sector and sector != "all":
        query["sector"] = sector
    if q:
        import re
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{"title": rx}, {"company": rx}, {"skills": rx}, {"location": rx}]
    if work and work != "All":
        query["work_type"] = work
    if level and level != "All":
        query["level"] = level
    if source and source != "all":
        query["source"] = source
    if country and country != "all":
        query["countries"] = country
    return query


@router.get("/jobs")
async def list_jobs(q: str = "", work: str = "All", level: str = "All", source: str = "all", country: str = "all", sort: str = "best", sector: str = "all",
                    page: int = Query(1, ge=1), limit: int = Query(24, ge=1, le=60), user=Depends(current_user)):
    c = await user_ctx(user["id"])
    query = _job_query(q, work, level, source, country, sector)
    total = await db.jobs.count_documents(query)
    skip = (page - 1) * limit
    if sort == "best" and c["has_data"]:
        docs = await db.jobs.find(query, LIST_PROJ).to_list(20000)
        for d in docs:
            d["match"] = careers.quick_score(c, d)
        docs.sort(key=lambda d: (d["match"] or 0, d.get("posted_at") or ""), reverse=True)
        jobs = docs[skip:skip + limit]
    else:
        order = [("salary.usd_annual", -1), ("posted_at", -1)] if sort == "salary" else [("posted_at", -1)]
        if sort == "salary":
            query = {**query, "salary.usd_annual": {"$ne": None, "$exists": True}}
            total = await db.jobs.count_documents(query)
        jobs = await db.jobs.find(query, LIST_PROJ).sort(order).skip(skip).limit(limit).to_list(limit)
        for d in jobs:
            d["match"] = careers.quick_score(c, d)
    return {"total": total, "page": page, "has_more": skip + len(jobs) < total, "jobs": jobs}


@router.get("/jobs/sources")
async def job_sources(user=Depends(current_user)):
    counts = {r["_id"]: r["n"] async for r in db.jobs.aggregate([{"$group": {"_id": "$source", "n": {"$sum": 1}}}])}
    meta = await db.meta.find_one({"key": "jobs_refresh"}, {"_id": 0})
    return {"sources": [{"key": k, "label": v, "count": counts.get(k, 0)} for k, v in SOURCE_LABELS.items()],
            "last_refresh": (meta or {}).get("at"), "total": sum(counts.values())}


@router.get("/jobs/countries")
async def job_countries(user=Depends(current_user)):
    pipe = [{"$unwind": "$countries"}, {"$group": {"_id": "$countries", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}]
    rows = [{"name": r["_id"], "count": r["n"]} async for r in db.jobs.aggregate(pipe)]
    rows.sort(key=lambda r: (r["name"] != "Remote / Anywhere", -r["count"]))
    return {"countries": rows}


@router.post("/jobs/refresh")
async def trigger_refresh(user=Depends(current_user)):
    import asyncio
    asyncio.create_task(refresh_all())
    return {"started": True}


@router.get("/companies")
async def companies(q: str = "", user=Depends(current_user)):
    match = {"company": {"$regex": q, "$options": "i"}} if q else {}
    pipe = [{"$match": match}, {"$group": {"_id": "$company", "jobs": {"$sum": 1}}}, {"$match": {"_id": {"$ne": ""}}},
            {"$sort": {"jobs": -1}}, {"$limit": 60}]
    return {"companies": [{"name": r["_id"], "jobs": r["jobs"]} async for r in db.jobs.aggregate(pipe)]}


@router.get("/jobs/{job_id}")
async def job_detail(job_id: str, user=Depends(current_user)):
    job = await db.jobs.find_one({"id": job_id}, {"_id": 0, "unit": 0})
    if not job:
        raise HTTPException(404, "Job not found or no longer listed.")
    job = await enrich_job(job)
    job.pop("detail_url", None)
    if not job.get("sector"):
        job["sector"] = careers.classify(job.get("title", ""), job.get("description") or "")
    e = careers.explain(await user_ctx(user["id"]), job)
    job["match"], job["match_explain"], job["skills_have"] = e["score"], e, e["have"]
    job["sector_name"] = careers.sector(job["sector"])["name"] if job["sector"] != "other" else "Other"
    return job
