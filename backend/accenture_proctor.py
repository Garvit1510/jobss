"""Accenture mock OA: shared proctoring + code-runner config, proctoring sessions per round attempt, admin attempt reports.
Reuses the existing proctoring system (routes_prep.FLAG_WEIGHTS / proctor_report, useProctor on the client, proctor snaps)."""
import uuid
from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import accenture_mocks as am
import sandbox
from accenture_rounds import CODE_DEFAULT, ROUND_ORDER, _find, _mock, _past, _settings, iso, now
from auth import current_user, require_admin
from database import db
from routes_prep import FLAG_WEIGHTS, proctor_report

router = APIRouter(prefix="/api")
SIGNAL_NOTE = "Proctoring events are review signals for an admin, not proof of misconduct."


async def shared_proctoring():
    d = await db.acc_mock_settings.find_one({"key": "proctoring"}, {"_id": 0})
    return {**am.PROCTOR_DEFAULT, **((d or {}).get("value") or {})}


async def oa_config(m):
    """Shared config inherited by every mock (existing and newly generated); optional per-mock override in m['oa_config']."""
    ov = (m or {}).get("oa_config") or {}
    proctoring = {**await shared_proctoring(), **(ov.get("proctoring") or {})}
    cfg = am.ROUND_CONFIG["coding"]
    runner = {"engine": "sandbox_jail", "ready": sandbox.ready(), "languages": cfg.get("languages", ["python", "java", "cpp", "javascript"]),
              "max_submissions": (await _settings("coding_scoring", CODE_DEFAULT))["max_submissions"], "custom_input": True, **(ov.get("code_runner") or {}),
              "disabled_for_demo": await am.coding_disabled(m["mock_id"]) if m else False}
    return {"proctoring": proctoring, "code_runner": runner}


@router.get("/accenture-mocks/{mock_id}/oa-config")
async def get_oa_config(mock_id: str, preview: bool = False, user=Depends(current_user)):
    return await oa_config(await _mock(user, mock_id, preview))


class SessionIn(BaseModel):
    round: Literal["behavioural", "gamified", "technical", "coding"]
    preview: bool = False
    status: Literal["active", "failed", "declined"]
    reason: str = Field("", max_length=300)
    checks: dict = Field(default_factory=dict)


@router.post("/accenture-mocks/{mock_id}/proctor/session")
async def proctor_session(mock_id: str, body: SessionIn, user=Depends(current_user)):
    """Links a proctoring session to the candidate's current attempt of a round. Called after the attempt is started."""
    m = await _mock(user, mock_id, body.preview)
    pol = (await oa_config(m))["proctoring"]
    a = await _find(user, mock_id, body.round, preview=body.preview)
    if not a or a.get("finished_at"):
        raise HTTPException(409, "Start the round first.")
    if body.status == "declined" and pol["mode"] == "strict":
        raise HTTPException(409, "This mock requires proctoring.")
    checks = {k: bool(v) for k, v in list(body.checks.items())[:10]}
    s = await db.acc_proctor_sessions.find_one({"attempt_id": a["id"]}, {"_id": 0, "id": 1, "status": 1})
    t = iso(now())
    if s:
        upd = {"status": body.status if s["status"] != "active" or body.status == "active" else "active", "last_init_at": t, "checks": checks}
        if body.status != "active":
            upd["init_failure"] = body.reason or body.status
        await db.acc_proctor_sessions.update_one({"id": s["id"]}, {"$set": upd, "$inc": {"inits": 1}})
        sid = s["id"]
    else:
        sid = str(uuid.uuid4())
        await db.acc_proctor_sessions.insert_one({"id": sid, "attempt_id": a["id"], "user_id": user["id"], "mock_id": mock_id, "round": body.round,
                                                  "preview": body.preview, "mode": pol["mode"], "policy": pol, "status": body.status, "checks": checks,
                                                  "init_failure": None if body.status == "active" else (body.reason or body.status),
                                                  "flags": [], "inits": 1, "created_at": t, "last_init_at": t})
    return {"session_id": sid, "status": body.status, "ignore_flags": pol.get("ignore_flags", [])}


class FlagIn(BaseModel):
    type: str = Field(..., max_length=40)
    detail: str = Field("", max_length=200)


@router.post("/accenture-mocks/proctor/{sid}/flag")
async def proctor_flag(sid: str, body: FlagIn, user=Depends(current_user)):
    if body.type not in FLAG_WEIGHTS:
        raise HTTPException(400, "Unknown flag type")
    s = await db.acc_proctor_sessions.find_one({"id": sid, "user_id": user["id"]}, {"_id": 0, "attempt_id": 1, "status": 1})
    if not s:
        raise HTTPException(404, "Proctoring session not found")
    a = await db.acc_attempts.find_one({"id": s["attempt_id"]}, {"_id": 0, "finished_at": 1, "deadline": 1})
    if not a or a.get("finished_at") or (a.get("deadline") and _past(a["deadline"])):
        return {"ok": True, "recorded": False}
    r = await db.acc_proctor_sessions.update_one({"id": sid, "flags.299": {"$exists": False}},
                                                 {"$push": {"flags": {"type": body.type, "detail": body.detail, "at": iso(now())}}})
    return {"ok": True, "recorded": r.modified_count == 1}


def summarize(attempt, session, admin=False):
    """Per-round proctoring summary; strict attempts without an active session are never reported as proctored."""
    pol = (attempt or {}).get("proctoring_policy") or {}
    mode = pol.get("mode") or (session or {}).get("mode") or "off"
    if mode == "off" and not session:
        return {"mode": "off", "status": "not_required"}
    if not session or session["status"] != "active":
        st = "failed" if session and session["status"] == "failed" else "declined" if session and session["status"] == "declined" else "not_initialized"
        out = {"mode": mode, "status": st, "proctored": False, "needs_review": mode == "strict",
               "message": "Required proctoring was not initialised; this attempt is NOT treated as proctored." if mode == "strict" else "Taken without proctoring."}
        if admin and session:
            out["init_failure"] = session.get("init_failure")
        return out
    rep = proctor_report({"proctored": True, "flags": session.get("flags", [])})
    out = {"mode": mode, "status": "active", "proctored": True, "integrity_score": rep["integrity_score"], "risk": rep["risk"],
           "total_flags": rep["total_flags"], "counts": rep["counts"], "needs_review": rep["total_flags"] > 0, "note": SIGNAL_NOTE}
    if admin:
        out.update(timeline=rep["timeline"], session_id=session["id"], checks=session.get("checks"), inits=session.get("inits"))
    return out


async def sessions_for(attempt_ids):
    return {s["attempt_id"]: s async for s in db.acc_proctor_sessions.find({"attempt_id": {"$in": attempt_ids}}, {"_id": 0})}


# ---------- admin ----------
class ProctorCfgIn(BaseModel):
    mode: Literal["off", "optional", "strict"]
    ignore_flags: List[str] = Field(default_factory=list, max_length=20)


@router.get("/admin/accenture-mocks/settings/proctoring")
async def get_proctor_cfg(admin=Depends(require_admin)):
    return {**await shared_proctoring(), "flag_types": sorted(FLAG_WEIGHTS)}


@router.put("/admin/accenture-mocks/settings/proctoring")
async def put_proctor_cfg(body: ProctorCfgIn, admin=Depends(require_admin)):
    bad = [f for f in body.ignore_flags if f not in FLAG_WEIGHTS]
    if bad:
        raise HTTPException(400, f"Unknown flag types: {', '.join(bad)}")
    v = {**am.PROCTOR_DEFAULT, **body.model_dump()}
    await db.acc_mock_settings.update_one({"key": "proctoring"}, {"$set": {"key": "proctoring", "value": v, "updated_at": iso(now()), "updated_by": admin["email"]}}, upsert=True)
    return v


@router.get("/admin/accenture-mocks/attempt-reports")
async def attempt_reports(mock_id: str = "", include_preview: bool = False, admin=Depends(require_admin)):
    """One row per candidate x mock: every round's result, Round 4 per-task submissions, and proctoring for each round attempt."""
    q = {**({"mock_id": mock_id} if mock_id else {}), **({} if include_preview else {"preview": False})}
    atts = [a async for a in db.acc_attempts.find(q, {"_id": 0, "responses": 0, "answers": 0, "states": 0}).sort("created_at", -1).limit(400)]
    ses = await sessions_for([a["id"] for a in atts])
    users = {u["id"]: u async for u in db.users.find({"id": {"$in": list({a["user_id"] for a in atts})}}, {"_id": 0, "id": 1, "email": 1, "name": 1})}
    rows = {}
    for a in atts:
        key = (a["user_id"], a["mock_id"], a.get("preview", False))
        r = rows.setdefault(key, {"user": users.get(a["user_id"]), "mock_id": a["mock_id"], "preview": a.get("preview", False), "rounds": {}})
        if a["round"] in r["rounds"]:
            continue  # latest attempt per round
        res = a.get("round_score") if a["round"] == "gamified" else a.get("result")
        entry = {"attempt_id": a["id"], "started_at": a.get("started_at"), "finished_at": a.get("finished_at"), "end_reason": a.get("end_reason"),
                 "result": {k: res.get(k) for k in ("percent", "passed", "cutoff_percent", "profile_index", "answered", "total") if k in res} if res else None,
                 "proctoring": summarize(a, ses.get(a["id"]), admin=True)}
        if a["round"] == "behavioural" and res:
            entry["review_status"] = (a.get("admin_review") or {}).get("status") or res["review"]["status"]
        if a["round"] == "coding":
            entry["tasks"] = [{"qid": t["qid"], "type": t["type"], "status": t["status"], "best_score": t.get("best_score"),
                               "submissions": [{"at": s.get("at"), "lang": s.get("lang"), "score": s.get("score"), "passed": (s.get("result") or {}).get("passed"),
                                                "total": (s.get("result") or {}).get("total")}
                                               for s in t.get("submissions", [])]} for t in a.get("tasks", [])]
        r["rounds"][a["round"]] = entry
    out = list(rows.values())
    for r in out:
        r["order"] = ROUND_ORDER
    return {"reports": out, "note": SIGNAL_NOTE}
