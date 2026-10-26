import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import current_user
from database import db
from jobs_service import match_score
from routes_core import LIST_PROJ, _job_query, get_resume, log_activity, user_skillset

router = APIRouter(prefix="/api/alerts")
MAX_ALERTS = 10


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class AlertIn(BaseModel):
    name: str = Field(default="", max_length=80)
    q: str = Field(default="", max_length=100)
    work: str = "All"
    level: str = "All"
    source: str = "all"
    country: str = "all"


def _q(a, new_only=True):
    f = a["filters"]
    query = _job_query(f.get("q"), f.get("work"), f.get("level"), f.get("source"), f.get("country"))
    if new_only:
        query["first_seen_at"] = {"$gt": a["last_seen_at"]}
    return query


def _label(f):
    parts = [f"\"{f['q']}\"" if f.get("q") else "All roles"]
    parts += [f[k] for k in ("work", "level") if f.get(k) and f[k] != "All"]
    parts += [f[k] for k in ("country", "source") if f.get(k) and f[k] != "all"]
    return " · ".join(parts)


async def _own(alert_id, user):
    a = await db.job_alerts.find_one({"id": alert_id, "user_id": user["id"]}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Alert not found")
    return a


@router.post("")
async def create_alert(body: AlertIn, user=Depends(current_user)):
    if await db.job_alerts.count_documents({"user_id": user["id"]}) >= MAX_ALERTS:
        raise HTTPException(400, f"You can save up to {MAX_ALERTS} alerts. Delete one first.")
    filters = body.model_dump(exclude={"name"})
    if await db.job_alerts.find_one({"user_id": user["id"], "filters": filters}):
        raise HTTPException(400, "You already have an alert for this search.")
    a = {"id": str(uuid.uuid4()), "user_id": user["id"], "name": body.name.strip() or _label(filters), "filters": filters,
         "created_at": now_iso(), "last_seen_at": now_iso()}
    await db.job_alerts.insert_one(a)
    await log_activity(user["id"], "alert", f"Created job alert: {a['name']}")
    a.pop("_id", None)
    return {**a, "new_count": 0, "total": await db.jobs.count_documents(_q(a, False))}


@router.get("")
async def list_alerts(user=Depends(current_user)):
    alerts = await db.job_alerts.find({"user_id": user["id"]}, {"_id": 0, "user_id": 0}).sort("created_at", -1).to_list(MAX_ALERTS)
    for a in alerts:
        a["new_count"] = await db.jobs.count_documents(_q(a))
        a["total"] = await db.jobs.count_documents(_q(a, False))
    meta = await db.meta.find_one({"key": "jobs_refresh"}, {"_id": 0, "at": 1})
    return {"alerts": alerts, "last_refresh": (meta or {}).get("at")}


@router.get("/summary")
async def alerts_summary(user=Depends(current_user)):
    alerts = await db.job_alerts.find({"user_id": user["id"]}, {"_id": 0}).to_list(MAX_ALERTS)
    total = 0
    for a in alerts:
        total += await db.jobs.count_documents(_q(a))
    return {"total_new": total, "alerts": len(alerts)}


@router.get("/{alert_id}/new")
async def alert_new_jobs(alert_id: str, user=Depends(current_user)):
    a = await _own(alert_id, user)
    resume = await get_resume(user["id"])
    us, roles = user_skillset(resume), (resume or {}).get("recommended_roles", [])
    jobs = await db.jobs.find(_q(a), {**LIST_PROJ, "_id": 0}).sort("first_seen_at", -1).limit(60).to_list(60)
    for j in jobs:
        j["match"] = match_score(us, roles, j)
    jobs.sort(key=lambda j: j["match"] or 0, reverse=True)
    return {"alert": a, "jobs": jobs}


@router.post("/{alert_id}/seen")
async def alert_seen(alert_id: str, user=Depends(current_user)):
    await _own(alert_id, user)
    await db.job_alerts.update_one({"id": alert_id}, {"$set": {"last_seen_at": now_iso()}})
    return {"ok": True}


@router.delete("/{alert_id}")
async def delete_alert(alert_id: str, user=Depends(current_user)):
    await _own(alert_id, user)
    await db.job_alerts.delete_one({"id": alert_id})
    return {"ok": True}
