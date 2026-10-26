import base64
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from auth import current_user, require_admin
from database import db

router = APIRouter(prefix="/api")
MAX_SNAPS = 80
MAX_BYTES = 400_000


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class SnapIn(BaseModel):
    kind: str = Field(pattern="^(oa|interview|accenture)$")
    ref_id: str = Field(min_length=1, max_length=64)
    type: str = Field(min_length=1, max_length=40)
    detail: str = Field(default="", max_length=300)
    image: str = Field(min_length=100, max_length=600_000)


async def _session(kind, ref_id, user_id):
    if kind == "accenture":
        return await db.acc_proctor_sessions.find_one({"id": ref_id, "user_id": user_id, "status": "active"}, {"_id": 0, "id": 1})
    coll = db.mock_tests if kind == "oa" else db.interviews
    return await coll.find_one({"id": ref_id, "user_id": user_id, "proctored": True}, {"_id": 0, "id": 1})


@router.post("/proctor/snap")
async def save_snap(body: SnapIn, user=Depends(current_user)):
    if not await _session(body.kind, body.ref_id, user["id"]):
        raise HTTPException(404, "Proctored session not found")
    head, _, b64 = body.image.partition(",")
    if head not in ("data:image/jpeg;base64", "data:image/webp;base64", "data:image/png;base64"):
        raise HTTPException(400, "Unsupported image")
    try:
        raw = base64.b64decode(b64, validate=True)
    except ValueError:
        raise HTTPException(400, "Bad image data")
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "Image too large")
    if body.type != "registered" and await db.proctor_snaps.count_documents({"ref_id": body.ref_id}) >= MAX_SNAPS:
        return {"ok": False, "reason": "limit"}
    if body.type == "registered":
        await db.proctor_snaps.delete_many({"ref_id": body.ref_id, "type": "registered"})
    await db.proctor_snaps.insert_one({"id": str(uuid.uuid4()), "user_id": user["id"], "kind": body.kind, "ref_id": body.ref_id, "type": body.type,
                                       "detail": body.detail, "mime": head[5:-7], "data": raw, "size": len(raw), "at": now_iso()})
    return {"ok": True}


@router.get("/admin/proctor/sessions")
async def proctor_sessions(admin=Depends(require_admin)):
    rows = await db.proctor_snaps.aggregate([
        {"$group": {"_id": "$ref_id", "kind": {"$first": "$kind"}, "user_id": {"$first": "$user_id"}, "count": {"$sum": 1},
                    "flags": {"$sum": {"$cond": [{"$eq": ["$type", "registered"]}, 0, 1]}}, "last": {"$max": "$at"}, "first": {"$min": "$at"}}},
        {"$sort": {"last": -1}}, {"$limit": 300}]).to_list(300)
    uids = list({r["user_id"] for r in rows})
    users = {u["id"]: u async for u in db.users.find({"id": {"$in": uids}}, {"_id": 0, "id": 1, "name": 1, "email": 1, "banned": 1})}
    oa = {t["id"]: t async for t in db.mock_tests.find({"id": {"$in": [r["_id"] for r in rows]}}, {"_id": 0, "id": 1, "company": 1, "topic": 1, "test.title": 1})}
    iv = {s["id"]: s async for s in db.interviews.find({"id": {"$in": [r["_id"] for r in rows]}}, {"_id": 0, "id": 1, "role": 1, "company": 1})}
    acc = {s["id"]: {"role": f"Accenture {s['mock_id']} · {s['round']}"} async for s in db.acc_proctor_sessions.find({"id": {"$in": [r["_id"] for r in rows]}}, {"_id": 0, "id": 1, "mock_id": 1, "round": 1})}
    out = []
    for r in rows:
        u = users.get(r["user_id"], {})
        t = oa.get(r["_id"]) or iv.get(r["_id"]) or acc.get(r["_id"]) or {}
        title = (t.get("test") or {}).get("title") or t.get("role") or t.get("company") or t.get("topic") or "Session"
        out.append({"ref_id": r["_id"], "kind": r["kind"], "title": title, "user_id": r["user_id"], "user_name": u.get("name"), "user_email": u.get("email"),
                    "user_banned": bool(u.get("banned")), "photos": r["count"], "flags": r["flags"], "first_at": r["first"], "last_at": r["last"]})
    return {"sessions": out}


@router.get("/admin/proctor/sessions/{ref_id}")
async def proctor_session(ref_id: str, admin=Depends(require_admin)):
    snaps = await db.proctor_snaps.find({"ref_id": ref_id}, {"_id": 0, "data": 0}).sort("at", 1).to_list(MAX_SNAPS + 5)
    return {"snaps": snaps}


@router.get("/admin/proctor/snaps/{sid}/image")
async def proctor_image(sid: str, admin=Depends(require_admin)):
    s = await db.proctor_snaps.find_one({"id": sid}, {"_id": 0, "data": 1, "mime": 1})
    if not s:
        raise HTTPException(404, "Photo not found")
    return Response(s["data"], media_type=s.get("mime") or "image/jpeg", headers={"Cache-Control": "private, no-store"})


@router.delete("/admin/proctor/snaps/{sid}")
async def delete_snap(sid: str, admin=Depends(require_admin)):
    r = await db.proctor_snaps.delete_one({"id": sid})
    if not r.deleted_count:
        raise HTTPException(404, "Photo not found")
    return {"ok": True}


@router.delete("/admin/proctor/sessions/{ref_id}")
async def delete_session_snaps(ref_id: str, admin=Depends(require_admin)):
    r = await db.proctor_snaps.delete_many({"ref_id": ref_id})
    return {"ok": True, "deleted": r.deleted_count}
