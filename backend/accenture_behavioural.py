"""Accenture Round 1 (behavioural, Likert): server-timed attempt, trait-profile scoring, admin review of ambiguous profiles. No AI calls."""
import uuid
from datetime import timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import accenture_mocks as am
from accenture_rounds import StartIn, _find, _load, _mock, _past, _save, _settings, iso, now
from auth import current_user, require_admin
from database import db

router = APIRouter(prefix="/api")
B = "/accenture-mocks/{mock_id}/behavioural"
METHOD = ("Trait-profile scoring (practice model, not official Accenture scoring). Each answer maps to 1-5 (Strongly Disagree=1 ... Strongly Agree=5). "
          "Reverse-worded statements are scored 6 - value. Each of the 8 traits = mean (or sum, per admin setting) of its answered items; the band "
          "(low / moderate / high) always uses the trait mean against the admin bands. Profile index = mean of all scored answers (1-5), descriptive only. "
          "There are no right or wrong answers and no pass/fail: completing the round unlocks Round 2, and Round 1 never adds points to any score. "
          "Unreliable patterns (low completion, straight-lining, excessive Neutral, forward vs reverse contradictions, uniformly extreme answers, too few "
          "items per trait; thresholds set by the admin) are flagged for admin review instead of being judged automatically.")
TRAIT_LABEL = {"conscientiousness": "Conscientiousness", "teamwork": "Teamwork", "adaptability": "Adaptability", "integrity": "Integrity",
               "learning_agility": "Learning agility", "resilience": "Resilience", "client_focus": "Client focus", "leadership": "Leadership"}


def _band(mean, bands):
    return None if mean is None else "low" if mean < bands["low_below"] else "high" if mean >= bands["high_from"] else "moderate"


def _flags(items, resp, sc, traits):
    th = {**am.BEH_REVIEW_THRESHOLDS, **(sc.get("review_thresholds") or {})}
    flags, raw = [], [resp[i["qid"]] + 1 for i in items if resp.get(i["qid"]) is not None]
    n = len(items)
    if len(raw) < th["min_completion"] * n:
        flags.append({"code": "low_completion", "detail": f"Only {len(raw)}/{n} statements answered."})
    if not raw:
        return flags
    top = max(raw.count(v) for v in set(raw))
    if top >= th["straight_line_share"] * len(raw):
        flags.append({"code": "straight_lining", "detail": f"{top}/{len(raw)} answers are the same option."})
    if raw.count(3) >= th["neutral_share"] * len(raw):
        flags.append({"code": "excessive_neutral", "detail": f"{raw.count(3)}/{len(raw)} answers are Neutral."})
    if few := [TRAIT_LABEL[t] for t, v in traits.items() if v["answered"] < th["min_items_per_trait"]]:
        flags.append({"code": "insufficient_items", "detail": f"Fewer than {th['min_items_per_trait']} answers for: {', '.join(few)}."})
    if sc["consistency_check"]:
        bad = [f"{TRAIT_LABEL[t]} (forward {v['forward_mean']}, reverse {v['reverse_mean']})" for t, v in traits.items()
               if v["forward_mean"] is not None and v["reverse_mean"] is not None and abs(v["forward_mean"] - v["reverse_mean"]) >= th["reverse_gap"]]
        if bad:
            flags.append({"code": "inconsistent_reverse_items", "detail": "Forward and reverse-worded answers contradict each other: " + "; ".join(bad) + "."})
        scored = [v["mean"] for v in traits.values() if v["mean"] is not None]
        if len(raw) >= th["min_completion"] * n and scored and min(scored) >= th["extreme_min_mean"]:
            flags.append({"code": "uniformly_extreme", "detail": "Every trait is at the very top of the scale (possible socially desirable responding)."})
    return flags


def score(items, resp, sc):
    traits = {}
    for t in am.TRAITS:
        rows = [(i, resp[i["qid"]] + 1) for i in items if i["trait"] == t and resp.get(i["qid"]) is not None]
        rev = sc["reverse_scoring"]
        vals = [6 - v if rev and i["reverse_scored"] else v for i, v in rows]
        fwd = [v for i, v in rows if not i["reverse_scored"]]
        bwd = [6 - v for i, v in rows if i["reverse_scored"]]
        mean = round(sum(vals) / len(vals), 2) if vals else None
        traits[t] = {"label": TRAIT_LABEL[t], "items": sum(1 for i in items if i["trait"] == t), "answered": len(vals), "mean": mean,
                     "score": (round(sum(vals), 2) if sc["aggregation"] == "sum" else mean) if vals else None, "band": _band(mean, sc["bands"]),
                     "forward_mean": round(sum(fwd) / len(fwd), 2) if fwd else None, "reverse_mean": round(sum(bwd) / len(bwd), 2) if bwd else None}
    flat = [v for t in traits.values() for v in [t["mean"]] * t["answered"] if v is not None]
    answered = sum(1 for i in items if resp.get(i["qid"]) is not None)
    flags = _flags(items, resp, sc, traits)
    return {"type": "trait_profile", "objective_marking": False, "passed": None, "answered": answered, "total": len(items),
            "aggregation": sc["aggregation"], "bands": sc["bands"], "reverse_scoring": sc["reverse_scoring"], "traits": traits,
            "profile_index": round(sum(flat) / len(flat), 2) if flat else None, "flags": flags,
            "review": {"status": "needs_admin_review" if flags else "no_flags"}, "thresholds": {**am.BEH_REVIEW_THRESHOLDS, **(sc.get("review_thresholds") or {})},
            "method": METHOD, "official": False, "computed_at": iso(now())}


def _close(a, m):
    if not a.get("finished_at") and _past(a["deadline"]):
        a["finished_at"], a["end_reason"] = iso(now()), "time_up"
    if a.get("finished_at") and not a.get("result"):
        a["result"] = score(m["rounds"]["behavioural"]["items"], {k: v.get("choice") for k, v in a["responses"].items()}, a["scoring"])
        return True
    return False


def candidate_result(a):
    """What the owner sees: trait bands only if the admin allows it; flags never shown in detail."""
    r = a.get("result")
    if not r:
        return None
    out = {k: r[k] for k in ("type", "answered", "total", "passed", "method", "official")}
    out["review_status"] = (a.get("admin_review") or {}).get("status") or r["review"]["status"]
    if a["scoring"]["show_trait_profile_to_candidate"]:
        out.update(profile_index=r["profile_index"], traits={t: {k: v[k] for k in ("label", "band", "mean", "score", "answered", "items")} for t, v in r["traits"].items()})
    return out


def _public(a, m):
    return {"id": a["id"], "mock_id": a["mock_id"], "preview": a["preview"], "deadline": a["deadline"], "server_time": iso(now()),
            "items": [{"qid": i["qid"], "statement": i["statement"]} for i in m["rounds"]["behavioural"]["items"]], "options": am.LIKERT,
            "responses": {k: v.get("choice") for k, v in a["responses"].items()}, "finished_at": a.get("finished_at"), "end_reason": a.get("end_reason"),
            "result": candidate_result(a), "minutes": am.ROUND_CONFIG["behavioural"]["minutes"]}


async def _ctx(user, mock_id):
    a = await _load(user, mock_id, "behavioural")
    m = await db.acc_mocks.find_one({"library_id": a["library_id"], "mock_id": mock_id}, {"_id": 0})
    if _close(a, m):
        await _save(a, ["finished_at", "end_reason", "result"])
    return a, m


@router.post(B + "/start")
async def beh_start(mock_id: str, body: StartIn, user=Depends(current_user)):
    m = await _mock(user, mock_id, body.preview)
    old = await _find(user, mock_id, "behavioural", preview=body.preview)
    if old and not (body.preview and old.get("finished_at")):
        if _close(old, m):
            await _save(old, ["finished_at", "end_reason", "result"])
        return _public(old, m)
    items = m["rounds"]["behavioural"]["items"]
    if len(items) != am.ROUND_CONFIG["behavioural"]["count"]:
        raise HTTPException(409, "Round 1 content is incomplete for this mock.")
    t = now()
    doc = {"id": str(uuid.uuid4()), "user_id": user["id"], "mock_id": mock_id, "library_id": m["library_id"], "mock_version": m["version"], "round": "behavioural",
           "preview": body.preview, "started_at": iso(t), "deadline": iso(t + timedelta(minutes=am.ROUND_CONFIG["behavioural"]["minutes"])), "responses": {},
           "scoring": await _settings("behavioural_scoring", am.BEHAVIOURAL_SCORING_DEFAULT), "created_at": iso(t)}
    from accenture_proctor import oa_config
    doc["proctoring_policy"] = (await oa_config(m))["proctoring"]
    await db.acc_attempts.insert_one(dict(doc))
    return _public(doc, m)


@router.get(B)
async def beh_get(mock_id: str, user=Depends(current_user)):
    a, m = await _ctx(user, mock_id)
    return _public(a, m)


class LikertIn(BaseModel):
    qid: str = Field(..., max_length=40)
    choice: Optional[int] = Field(None, ge=0, le=4)


@router.post(B + "/answer")
async def beh_answer(mock_id: str, body: LikertIn, user=Depends(current_user)):
    a, m = await _ctx(user, mock_id)
    if a.get("finished_at"):
        raise HTTPException(409, "Round 1 is closed.")
    if not any(i["qid"] == body.qid for i in m["rounds"]["behavioural"]["items"]):
        raise HTTPException(400, "Invalid statement.")
    await db.acc_attempts.update_one({"id": a["id"]}, {"$set": {f"responses.{body.qid}": {"choice": body.choice, "at": iso(now())}}})
    return {"ok": True, "qid": body.qid, "choice": body.choice}


@router.post(B + "/submit")
async def beh_submit(mock_id: str, user=Depends(current_user)):
    a, m = await _ctx(user, mock_id)
    if not a.get("finished_at"):
        a["finished_at"], a["end_reason"] = iso(now()), "submitted"
        _close(a, m)
        await _save(a, ["finished_at", "end_reason", "result"])
    return _public(a, m)


# ---------- admin review of flagged / all behavioural profiles ----------
@router.get("/admin/accenture-mocks/behavioural-attempts")
async def admin_list(status: Literal["flagged", "all"] = "flagged", admin=Depends(require_admin)):
    q = {"round": "behavioural", "finished_at": {"$ne": None}, **({"result.review.status": "needs_admin_review", "admin_review": None} if status == "flagged" else {})}
    rows = [a async for a in db.acc_attempts.find(q, {"_id": 0, "responses": 0}).sort("finished_at", -1).limit(200)]
    users = {u["id"]: u async for u in db.users.find({"id": {"$in": list({a["user_id"] for a in rows})}}, {"_id": 0, "id": 1, "email": 1, "name": 1})}
    return {"attempts": [{**a, "user": users.get(a["user_id"])} for a in rows]}


class BehReviewIn(BaseModel):
    decision: Literal["accepted", "invalidated", "reset"]
    note: str = Field("", max_length=500)


@router.post("/admin/accenture-mocks/behavioural-attempts/{attempt_id}/review")
async def admin_review(attempt_id: str, body: BehReviewIn, admin=Depends(require_admin)):
    a = await db.acc_attempts.find_one({"id": attempt_id, "round": "behavioural"}, {"_id": 0, "id": 1, "finished_at": 1})
    if not a or not a.get("finished_at"):
        raise HTTPException(404, "Finished behavioural attempt not found.")
    rv = None if body.decision == "reset" else {"status": body.decision, "by": admin["email"], "at": iso(now()), "note": body.note}
    await db.acc_attempts.update_one({"id": attempt_id}, {"$set": {"admin_review": rv}})
    return {"ok": True, "admin_review": rv}
