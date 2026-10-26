import re
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ai import ask_json
import oa_dataset

from auth import require_admin
from database import db

router = APIRouter(prefix="/api/admin")
ACTIVE = {"active": {"$ne": False}}
USER_FIELDS = {"_id": 0, "id": 1, "name": 1, "email": 1, "created_at": 1, "banned": 1, "banned_at": 1, "ban_reason": 1, "register_ip": 1,
               "register_device": 1, "last_login_at": 1, "last_login_ip": 1}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


@router.get("/stats")
async def stats(admin=Depends(require_admin)):
    return {"users": await db.users.count_documents({"role": {"$ne": "admin"}}),
            "banned_users": await db.users.count_documents({"banned": True}),
            "active_bans": await db.bans.count_documents(ACTIVE),
            "lifted_bans": await db.bans.count_documents({"active": False})}


@router.get("/bans")
async def list_bans(status: str = "active", admin=Depends(require_admin)):
    q = {} if status == "all" else {"active": False} if status == "lifted" else ACTIVE
    items = await db.bans.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    ids = list({b["user_id"] for b in items if b.get("user_id")})
    users = {u["id"]: u async for u in db.users.find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "email": 1, "name": 1})}
    for b in items:
        u = users.get(b.get("user_id"), {})
        b["user_email"], b["user_name"] = u.get("email"), u.get("name")
        b["active"] = b.get("active") is not False
    return {"bans": items}


async def _lift(q, admin):
    bans = await db.bans.find({**q, **ACTIVE}, {"_id": 0}).to_list(500)
    await db.bans.update_many({**q, **ACTIVE}, {"$set": {"active": False, "unbanned_at": now_iso(), "unbanned_by": admin["email"]}})
    for uid in {b["user_id"] for b in bans if b.get("user_id")}:
        if not await db.bans.find_one({"user_id": uid, **ACTIVE}):
            await db.users.update_one({"id": uid}, {"$set": {"banned": False}, "$unset": {"banned_at": ""}})
    return len(bans)


@router.post("/bans/{ban_id}/unban")
async def unban_ban(ban_id: str, admin=Depends(require_admin)):
    b = await db.bans.find_one({"id": ban_id})
    if not b:
        raise HTTPException(404, "Ban not found")
    if b.get("active") is False:
        raise HTTPException(400, "This ban was already lifted.")
    return {"ok": True, "lifted": await _lift({"id": ban_id}, admin)}


@router.get("/users")
async def list_users(q: str = "", banned: str = "", admin=Depends(require_admin)):
    query = {"role": {"$ne": "admin"}}
    if q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{"email": rx}, {"name": rx}]
    if banned == "true":
        query["banned"] = True
    users = await db.users.find(query, USER_FIELDS).sort("created_at", -1).to_list(200)
    return {"users": users}


@router.post("/users/{uid}/unban")
async def unban_user(uid: str, admin=Depends(require_admin)):
    if not await db.users.find_one({"id": uid}):
        raise HTTPException(404, "User not found")
    n = await _lift({"user_id": uid}, admin)
    await db.users.update_one({"id": uid}, {"$set": {"banned": False}, "$unset": {"banned_at": "", "ban_reason": ""}})
    return {"ok": True, "lifted": n}


class BanIn(BaseModel):
    reason: str = Field(default="", max_length=300)
    block_device: bool = False


@router.post("/users/{uid}/ban")
async def ban_user(uid: str, body: BanIn, admin=Depends(require_admin)):
    u = await db.users.find_one({"id": uid}, {"_id": 0})
    if not u:
        raise HTTPException(404, "User not found")
    if u.get("role") == "admin":
        raise HTTPException(400, "Admins can't be banned.")
    ts, reason = now_iso(), body.reason.strip() or "Banned by an administrator"
    ban = {"id": str(uuid.uuid4()), "active": True, "user_id": uid, "reason": "admin_ban", "note": reason, "banned_by": admin["email"], "created_at": ts}
    if body.block_device:
        ban.update(device_id=u.get("register_device"), ip=u.get("last_login_ip") or u.get("register_ip"))
    await db.bans.insert_one(ban)
    await db.users.update_one({"id": uid}, {"$set": {"banned": True, "banned_at": ts, "ban_reason": reason, "active_session_id": None}})
    return {"ok": True}


OA_EXT = (".txt", ".csv", ".json", ".md", ".pdf", ".docx", ".png", ".jpg", ".jpeg", ".webp")
OA_MAX_FILE, OA_MAX_TEXT = 250 * 1024 * 1024, 300_000
OA_LIST_FIELDS = {"_id": 0, "dataset_text": 0, "pages": 0}


async def _read_dataset(files, text):
    parts, meta, pages, raw = [], [], [], {}
    for f in files or []:
        name = (f.filename or "").lower()
        if not name:
            continue
        if not name.endswith(OA_EXT):
            raise HTTPException(400, f"{f.filename}: unsupported type. Use PDF, DOCX, TXT, CSV, JSON, MD or PNG/JPG screenshots.")
        data = await f.read()
        if len(data) > OA_MAX_FILE:
            raise HTTPException(400, f"{f.filename} is larger than 250 MB.")
        try:
            fp = await oa_dataset.read_pages(f.filename, data)
        except Exception:
            raise HTTPException(400, f"Could not read {f.filename}.")
        raw[f.filename] = data
        body = "\n".join(p["text"] for p in fp)
        parts.append(f"### FILE: {f.filename}\n{body.strip()}")
        meta.append({"filename": f.filename, "size": len(data), "chars": len(body), "pages": len(fp), "ocr_pages": sum(p["needs_ocr"] for p in fp)})
        pages += fp
    if text.strip():
        parts.append(f"### PASTED NOTES\n{text.strip()}")
        meta.append({"filename": "Pasted text", "size": len(text), "chars": len(text), "pages": 1, "ocr_pages": 0})
        pages.append({"file": "Pasted text", "page": 1, "text": text.strip(), "method": "text", "uncertain": False, "error": "", "needs_ocr": False})
    return "\n\n".join(parts), meta, pages, raw


async def _profile(name, dataset):
    try:
        return await ask_json("You analyse real company online-assessment (OA) datasets and extract their exact pattern.",
                              f"""Company: {name}\nDATASET (real past OA questions, experiences or pattern notes):\n{dataset[:30000]}\n
Describe this company's real OA pattern. Return JSON: {{"summary": str (2 sentences), "duration_minutes": int,
"sections": [{{"name": str, "count": int, "topics": [str], "style": str}}], "coding": {{"count": int, "style": str, "topics": [str]}},
"difficulty": "Easy"|"Medium"|"Hard", "notes": str}}""")
    except HTTPException:
        return None


@router.get("/oa-companies")
async def admin_oa_companies(admin=Depends(require_admin)):
    return {"companies": await db.oa_companies.find({}, OA_LIST_FIELDS).sort("created_at", -1).to_list(300)}


@router.post("/oa-companies")
async def create_oa_company(name: str = Form(..., min_length=2, max_length=80), description: str = Form("", max_length=300),
                            text: str = Form("", max_length=OA_MAX_TEXT), files: List[UploadFile] = File(default=[]),
                            admin=Depends(require_admin)):
    name = name.strip()
    if await db.oa_companies.find_one({"name_key": name.lower()}):
        raise HTTPException(400, f"{name} already exists. Add more data to it instead.")
    dataset, meta, pages, raw = await _read_dataset(files, text)
    if len(dataset) < 200 and not any(p["needs_ocr"] for p in pages):
        raise HTTPException(400, "Dataset is too small. Upload files or paste at least a few real questions.")
    doc = {"id": str(uuid.uuid4()), "name": name, "name_key": name.lower(), "description": description.strip(), "active": True,
           "dataset_text": dataset[:OA_MAX_TEXT], "chars": min(len(dataset), OA_MAX_TEXT), "files": meta, "pages": pages,
           "profile": await _profile(name, dataset) if len(dataset) >= 200 else None, "created_by": admin["email"], "created_at": now_iso(), "updated_at": now_iso()}
    await db.oa_companies.insert_one(doc)
    oa_dataset.start_import(doc["id"], raw)
    return {k: v for k, v in doc.items() if k not in ("_id", "dataset_text", "pages")}


@router.post("/oa-companies/{cid}/dataset")
async def add_oa_dataset(cid: str, text: str = Form("", max_length=OA_MAX_TEXT), files: List[UploadFile] = File(default=[]),
                         admin=Depends(require_admin)):
    c = await db.oa_companies.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Company OA not found")
    extra, meta, pages, raw = await _read_dataset(files, text)
    if not pages:
        raise HTTPException(400, "Add a file or paste some text.")
    dataset = f"{c['dataset_text']}\n\n{extra}"[:OA_MAX_TEXT]
    upd = {"dataset_text": dataset, "chars": len(dataset), "files": c.get("files", []) + meta, "updated_at": now_iso(),
           "pages": (c.get("pages") or oa_dataset.pages_from_text(c["dataset_text"])) + pages,
           "profile": await _profile(c["name"], dataset) or c.get("profile")}
    await db.oa_companies.update_one({"id": cid}, {"$set": upd})
    oa_dataset.start_import(cid, raw)
    return await db.oa_companies.find_one({"id": cid}, OA_LIST_FIELDS)


@router.post("/oa-companies/{cid}/import")
async def import_oa_dataset(cid: str, admin=Depends(require_admin)):
    if not await db.oa_companies.find_one({"id": cid}, {"_id": 1}):
        raise HTTPException(404, "Company OA not found")
    oa_dataset.start_import(cid)
    return {"ok": True}


class OACompanyPatch(BaseModel):
    active: bool | None = None
    description: str | None = Field(default=None, max_length=300)


@router.patch("/oa-companies/{cid}")
async def patch_oa_company(cid: str, body: OACompanyPatch, admin=Depends(require_admin)):
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    r = await db.oa_companies.update_one({"id": cid}, {"$set": {**upd, "updated_at": now_iso()}})
    if not r.matched_count:
        raise HTTPException(404, "Company OA not found")
    return await db.oa_companies.find_one({"id": cid}, OA_LIST_FIELDS)


@router.delete("/oa-companies/{cid}")
async def delete_oa_company(cid: str, admin=Depends(require_admin)):
    r = await db.oa_companies.delete_one({"id": cid})
    if not r.deleted_count:
        raise HTTPException(404, "Company OA not found")
    await db.oa_bank.delete_many({"company_id": cid})
    return {"ok": True}
