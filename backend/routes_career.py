import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional  # noqa: F401

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo import UpdateOne

import careers
from ai import ask_json
from auth import current_user, require_admin
from database import db
from routes_core import get_resume, log_activity, now_iso
from skills import canonical, extract_skills

router = APIRouter(prefix="/api")
log = logging.getLogger("career")
LEVELS = "^(Student|Fresher|Junior|Mid|Senior|Lead)$"


async def get_profile(user_id):
    return await db.career_profiles.find_one({"user_id": user_id}, {"_id": 0}) or {}


async def match_ctx(user_id):
    return careers.ctx_from(await get_resume(user_id), await get_profile(user_id))


def completion(profile, resume):
    checks = [bool(resume), bool(profile.get("target_sectors")), bool(profile.get("target_roles")), profile.get("experience_level") is not None,
              profile.get("years_experience") not in (None, ""), bool(profile.get("education")), bool(profile.get("locations")) or profile.get("work_preference") == "Remote",
              bool((resume or {}).get("skills") or profile.get("skills"))]
    return round(100 * sum(checks) / len(checks))


# ---------------- taxonomy ----------------
@router.get("/careers/sectors")
async def list_sectors(user=Depends(current_user)):
    counts = {d["_id"]: d["n"] async for d in db.jobs.aggregate([{"$match": {"duplicate": {"$ne": True}}}, {"$group": {"_id": "$sector", "n": {"$sum": 1}}}])}
    return {"sectors": [careers.public(s, counts.get(s["id"], 0)) for s in careers.sectors()], "other_jobs": counts.get("other", 0)}


class SectorIn(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,30}$")
    name: str = Field(min_length=2, max_length=80)
    roles: List[str] = []
    kw: str = Field(default="", max_length=2000)
    coding: bool = False
    oa: List[dict] = []
    oa_types: List[str] = []
    styles: List[str] = []
    competencies: List[str] = []
    note: str = ""
    w: dict = {}


@router.put("/admin/sectors")
async def upsert_sector(body: SectorIn, admin=Depends(require_admin)):
    await db.career_sectors.update_one({"id": body.id}, {"$set": {**body.model_dump(), "updated_at": now_iso()}}, upsert=True)
    careers.set_custom(await db.career_sectors.find({}, {"_id": 0}).to_list(200))
    return {"ok": True}


# ---------------- profile ----------------
class ProfileIn(BaseModel):
    target_sectors: List[str] = Field(default=[], max_length=5)
    target_roles: List[str] = Field(default=[], max_length=8)
    experience_level: str = Field(default="Fresher", pattern=LEVELS)
    years_experience: Optional[float] = Field(default=None, ge=0, le=50)
    education: str = Field(default="", max_length=300)
    certifications: List[str] = Field(default=[], max_length=20)
    skills: List[str] = Field(default=[], max_length=40)
    locations: List[str] = Field(default=[], max_length=6)
    work_preference: str = Field(default="Any", pattern="^(Any|Remote|Hybrid|On-site)$")
    employment_type: str = Field(default="Any", max_length=40)
    interests: str = Field(default="", max_length=600)
    links: List[str] = Field(default=[], max_length=10)
    language: str = Field(default="English", max_length=30)


@router.get("/profile")
async def my_profile(user=Depends(current_user)):
    p, r = await get_profile(user["id"]), await get_resume(user["id"])
    return {"profile": p, "completion": completion(p, r), "has_resume": bool(r), "inferred_sectors": (r or {}).get("job_families", [])}


@router.put("/profile")
async def save_profile(body: ProfileIn, user=Depends(current_user)):
    valid = {s["id"] for s in careers.sectors()}
    doc = {**body.model_dump(), "target_sectors": [s for s in body.target_sectors if s in valid],
           "skills": list(dict.fromkeys(canonical(s) for s in body.skills if s.strip())), "user_id": user["id"], "updated_at": now_iso()}
    await db.career_profiles.update_one({"user_id": user["id"]}, {"$set": doc}, upsert=True)
    await db.prep_plans.delete_many({"user_id": user["id"]})
    return {"profile": doc, "completion": completion(doc, await get_resume(user["id"]))}


class ResumeEditIn(BaseModel):
    headline: str = Field(default="", max_length=200)
    skills: List[str] = Field(default=[], max_length=40)
    recommended_roles: List[str] = Field(default=[], max_length=10)
    certifications: List[str] = Field(default=[], max_length=20)


@router.put("/resume/corrections")
async def correct_resume(body: ResumeEditIn, user=Depends(current_user)):
    r = await get_resume(user["id"])
    if not r:
        raise HTTPException(404, "Upload or build a resume first.")
    upd = {"headline": body.headline or r.get("headline", ""), "skills": list(dict.fromkeys(canonical(s) for s in body.skills if s.strip())),
           "recommended_roles": [x for x in body.recommended_roles if x.strip()], "certifications": body.certifications, "corrected_at": now_iso()}
    await db.resumes.update_one({"user_id": user["id"]}, {"$set": upd})
    return {"resume": await get_resume(user["id"])}


class BuilderIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    target_role: str = Field(min_length=2, max_length=100)
    sector: str = ""
    education: str = Field(default="", max_length=600)
    experience: str = Field(default="", max_length=3000)
    skills: str = Field(default="", max_length=1000)
    projects: str = Field(default="", max_length=2000)
    certifications: str = Field(default="", max_length=600)
    achievements: str = Field(default="", max_length=1000)
    languages: str = Field(default="", max_length=200)
    location: str = Field(default="", max_length=100)


@router.post("/profile/build-resume")
async def build_resume(body: BuilderIn, user=Depends(current_user)):
    a = await ask_json("You are a careful resume writer for every profession (students, freshers, tradespeople, professionals).",
                       f"""Turn ONLY the facts below into a structured resume. Rephrase professionally but NEVER invent employers, dates, degrees,
certifications, numbers, tools or achievements that are not stated. If a section is empty, return an empty list for it.
FACTS: {body.model_dump_json()}
Return JSON: {{"headline": str, "summary": str (2-3 sentences, factual), "skills": [str] (only skills stated or directly implied by stated work),
"education": [{{"degree": str, "institution": str, "year": str}}], "experience": [{{"title": str, "company": str, "duration": str, "highlights": [str]}}],
"projects": [{{"name": str, "description": str, "tech": [str]}}], "certifications": [str], "achievements": [str],
"recommended_roles": [str] (4-6 realistic roles), "job_families": [str] (ids from: {', '.join(s['id'] for s in careers.sectors())}),
"transferable_skills": [str], "resume_text": str (a clean plain-text resume draft the user can copy)}}""")
    resume = {"id": str(uuid.uuid4()), "user_id": user["id"], "filename": "Built with JobLens", "source": "builder", "name": body.name,
              "headline": a.get("headline", body.target_role), "summary": a.get("summary", ""),
              "skills": list(dict.fromkeys(canonical(s) for s in a.get("skills", []) if s))[:30], "education": a.get("education", []),
              "experience": a.get("experience", []), "projects": a.get("projects", []), "certifications": a.get("certifications", []),
              "achievements": a.get("achievements", []), "recommended_roles": a.get("recommended_roles", [])[:8],
              "job_families": [x for x in a.get("job_families", []) if x in {s["id"] for s in careers.sectors()}] or ([body.sector] if body.sector else []),
              "transferable_skills": a.get("transferable_skills", []), "years_experience": None, "score": 0, "score_breakdown": {},
              "strengths": [], "improvements": ["Add measurable results to each experience once you have them."], "draft_text": a.get("resume_text", ""),
              "raw_text": a.get("resume_text", "")[:20000], "uploaded_at": now_iso()}
    await db.resumes.delete_many({"user_id": user["id"]})
    await db.resumes.insert_one(resume)
    await db.prep_plans.delete_many({"user_id": user["id"]})
    await log_activity(user["id"], "resume", "Built a resume with the career profile builder")
    resume.pop("_id", None)
    resume.pop("raw_text", None)
    return resume


@router.post("/career/switch")
async def career_switch(user=Depends(current_user)):
    r, p = await get_resume(user["id"]), await get_profile(user["id"])
    if not r and not p:
        raise HTTPException(400, "Add a resume or fill your career profile first.")
    from routes_prep import _resume_ctx
    names = ", ".join(f"{s['id']}={s['name']}" for s in careers.sectors())
    d = await ask_json("You are a realistic, honest career-transition advisor across all industries.",
                       f"""{_resume_ctx(r)}\nProfile: {p.get('target_roles')} | sectors {p.get('target_sectors')} | {p.get('years_experience')} yrs | education {p.get('education')} | interests {p.get('interests')}
Suggest 4 realistic alternative careers this person could move into using TRANSFERABLE skills they actually have. Do not invent qualifications.
Sectors: {names}
Return JSON: {{"options": [{{"role": str, "sector": str (id), "why": str, "transferable_skills": [str], "missing": [str] (skills/qualifications to gain),
"steps": [str] (3-5 concrete transition steps), "entry_roles": [str] (realistic first job titles), "timeline": str}}]}}""")
    return d


# ---------------- overview & privacy ----------------
@router.get("/career/overview")
async def overview(user=Depends(current_user)):
    p, r = await get_profile(user["id"]), await get_resume(user["id"])
    c = careers.ctx_from(r, p)
    secs = c["sectors"][:3]
    q = {"duplicate": {"$ne": True}, **({"sector": {"$in": secs}} if secs else {})}
    docs = await db.jobs.find(q, {"_id": 0, "id": 1, "title": 1, "company": 1, "skills": 1, "level": 1, "work_type": 1, "location": 1, "sector": 1, "posted_at": 1}).sort("posted_at", -1).to_list(3000)
    for d in docs:
        d["match"] = careers.quick_score(c, d)
    docs.sort(key=lambda d: d["match"] or 0, reverse=True)
    top = []
    for d in docs[:5]:
        e = careers.explain(c, d)
        top.append({**d, "why": [f"{f['label']}: {f['detail']}" for f in e["factors"] if f["fit"] and f["fit"] >= 0.5][:3], "missing": e["missing"][:5]})
    gaps = {}
    for d in docs[:40]:
        for s in d.get("skills", []):
            if s.lower() not in c["skills"]:
                gaps[s] = gaps.get(s, 0) + 1
    last_oa = await db.mock_tests.find({"user_id": user["id"], "result": {"$exists": True}}, {"_id": 0, "result.score_pct": 1, "sector": 1, "created_at": 1}).sort("created_at", -1).to_list(5)
    return {"completion": completion(p, r), "profile": p, "sectors": [careers.public(careers.sector(s)) for s in secs if s in {x["id"] for x in careers.sectors()}],
            "top_jobs": top, "skill_gaps": sorted(gaps.items(), key=lambda x: -x[1])[:8],
            "recent_oa": last_oa}


@router.delete("/me/data")
async def delete_my_data(user=Depends(current_user)):
    uid = user["id"]
    for col in ("resumes", "career_profiles", "applications", "mock_tests", "interviews", "prep_plans", "learning", "activity", "job_alerts"):
        await db[col].delete_many({"user_id": uid})
    return {"ok": True}


# ---------------- jobs backfill: sector, all-sector skills, cross-source dedup ----------------
async def dedup_jobs():
    seen, ops = {}, []
    async for j in db.jobs.find({}, {"_id": 0, "id": 1, "title": 1, "company": 1, "location": 1, "first_seen_at": 1, "duplicate": 1}).sort("first_seen_at", 1):
        k = (j.get("title", "").strip().lower(), j.get("company", "").strip().lower(), (j.get("location") or "").split(",")[0].strip().lower())
        dup = k in seen
        seen.setdefault(k, j["id"])
        if dup != bool(j.get("duplicate")):
            ops.append(UpdateOne({"id": j["id"]}, {"$set": {"duplicate": dup}}))
    for i in range(0, len(ops), 500):
        await db.jobs.bulk_write(ops[i:i + 500], ordered=False)


async def backfill():
    try:
        careers.set_custom(await db.career_sectors.find({}, {"_id": 0}).to_list(200))
        if not await db.meta.find_one({"key": "careers_v1"}):
            ops = []
            async for j in db.jobs.find({}, {"_id": 0, "id": 1, "title": 1, "description": 1, "skills": 1}):
                text = f"{j.get('title', '')}\n{j.get('description') or ''}"
                skills = list(dict.fromkeys((j.get("skills") or []) + extract_skills(text)))[:18]
                ops.append(UpdateOne({"id": j["id"]}, {"$set": {"sector": careers.classify(j.get("title", ""), j.get("description") or ""), "skills": skills}}))
                if len(ops) >= 500:
                    await db.jobs.bulk_write(ops, ordered=False)
                    ops = []
                    await asyncio.sleep(0)
            if ops:
                await db.jobs.bulk_write(ops, ordered=False)
            await db.meta.update_one({"key": "careers_v1"}, {"$set": {"key": "careers_v1", "at": now_iso()}}, upsert=True)
        await dedup_jobs()
        await db.career_profiles.create_index("user_id", unique=True)
        await db.jobs.create_index("sector")
        log.info("career backfill done")
    except Exception as e:
        log.warning("career backfill failed: %s", e)
