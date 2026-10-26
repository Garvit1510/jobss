from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import accenture_mocks as am
from auth import current_user, require_admin
from database import db
from code_runner import sandbox_isolated
import sandbox

router = APIRouter(prefix="/api")
ADMIN = "/admin/accenture-mocks"


class GenerateIn(BaseModel):
    max_source_reuse: int = Field(1, ge=1, le=5)
    mock_ids: Optional[List[str]] = Field(None, max_length=40)


class RetryIn(BaseModel):
    mock_ids: Optional[List[str]] = Field(None, max_length=40)


def _ids(ids):
    if ids is None:
        return None
    out = [m for m in dict.fromkeys(ids) if m in am.MOCK_IDS]
    if not out:
        raise HTTPException(400, "No valid mock ids (M1-M40).")
    return out


class ReviewIn(BaseModel):
    action: Literal["approve", "reject", "reset"]
    answer_index: Optional[int] = Field(None, ge=0, le=5)
    explanation: Optional[str] = Field(None, max_length=3000)
    note: str = Field("", max_length=500)


class Bands(BaseModel):
    low_below: float = Field(..., ge=1, le=5)
    high_from: float = Field(..., ge=1, le=5)


class ReviewThresholds(BaseModel):
    min_completion: float = Field(..., ge=0.1, le=1)
    straight_line_share: float = Field(..., ge=0.5, le=1)
    neutral_share: float = Field(..., ge=0.3, le=1)
    reverse_gap: float = Field(..., ge=0.5, le=4)
    extreme_min_mean: float = Field(..., ge=3, le=5)
    min_items_per_trait: int = Field(..., ge=1, le=7)


class BehaviouralScoringIn(BaseModel):
    reverse_scoring: bool
    aggregation: Literal["mean", "sum"]
    bands: Bands
    consistency_check: bool
    show_trait_profile_to_candidate: bool
    review_thresholds: ReviewThresholds = ReviewThresholds(**am.BEH_REVIEW_THRESHOLDS)


class AccessIn(BaseModel):
    mock_ids: List[str] = Field(..., min_length=1, max_length=40)
    unlocked: bool


async def _lib(lib_id):
    lib = await db.acc_mock_libraries.find_one({"id": lib_id}, {"_id": 0})
    if not lib:
        raise HTTPException(404, "Library not found.")
    if lib["status"] == "generating" and lib_id not in am.JOBS:
        lib["status"], lib["stage"] = "incomplete", "Interrupted (server restarted) - use Retry"
        await db.acc_mock_libraries.update_one({"id": lib_id}, {"$set": {"status": lib["status"], "stage": lib["stage"]}})
    return lib


def _running():
    return next(iter(am.JOBS), None)


@router.get(ADMIN)
async def admin_overview(library_id: str = "", admin=Depends(require_admin)):
    libs = [l async for l in db.acc_mock_libraries.find({}, {"_id": 0, "source_pool.flagged": 0, "source_cache": 0}).sort("version", -1).limit(20)]
    sel = library_id or (libs[0]["id"] if libs else "")
    lib = await _lib(sel) if sel else None
    unlocked = await am.unlocked_ids()
    pub = await am.published_library()
    ind = await am.individually_published()
    pubs = {p["mock_id"]: p async for p in db.acc_mock_publications.find({}, {"_id": 0})}
    mocks = []
    if lib:
        async for m in db.acc_mocks.find({"library_id": lib["id"]}, {"_id": 0, "rounds": 0}).sort("index", 1):
            mocks.append({**m, "unlocked": m["mock_id"] in unlocked, **_visibility(m, lib, pub, unlocked, ind, pubs),
                          "state": await _mock_status(m, lib, pub, unlocked, ind, pubs)})
        lib["counts"] = await am.refresh_library(lib["id"])
        lib.pop("source_cache", None)
        lib["review_blocking"] = sum(((m.get("validation") or {}).get("stats") or {}).get("review_blocking", 0) for m in mocks)
        lib["awaiting_admin_review"] = sum(((m.get("validation") or {}).get("stats") or {}).get("awaiting_admin_review", 0) for m in mocks)
    access = [{"mock_id": m, "unlocked": m in unlocked} for m in am.MOCK_IDS]
    return {"libraries": libs, "library": lib, "mocks": mocks, "access": access, "published": pub, "running": _running(), "round_config": am.ROUND_CONFIG}


@router.post(f"{ADMIN}/generate")
async def generate(body: GenerateIn, admin=Depends(require_admin)):
    if _running():
        raise HTTPException(409, "A generation is already running.")
    if not await db.oa_bank.count_documents({"company": am.COMPANY}):
        raise HTTPException(409, "No Accenture dataset questions found. Upload/import the Accenture OA PDF under Company OAs first.")
    ids = _ids(body.mock_ids)
    lib = await am.new_library(admin, body.max_source_reuse)
    am.start(lib["id"], mock_ids=ids)
    return {"library_id": lib["id"], "version": lib["version"]}


@router.post(f"{ADMIN}/libraries/{{lib_id}}/retry")
async def retry(lib_id: str, body: RetryIn = RetryIn(), admin=Depends(require_admin)):
    lib = await _lib(lib_id)
    if _running():
        raise HTTPException(409, "A generation is already running.")
    if lib["status"] in ("published", "archived"):
        raise HTTPException(409, "Published/archived libraries are read-only. Generate a new version instead.")
    if lib.get("config_version") != am.CONFIG_VERSION:
        raise HTTPException(409, "This draft uses an outdated assessment structure. Generate a new version.")
    am.start(lib_id, only_bad=True, mock_ids=_ids(body.mock_ids))
    return {"ok": True}


@router.post(f"{ADMIN}/stop")
async def stop(admin=Depends(require_admin)):
    for lib_id, task in list(am.JOBS.items()):
        task.cancel()
        await db.acc_mock_libraries.update_one({"id": lib_id}, {"$set": {"status": "incomplete", "stage": "Stopped by admin"}})
        await db.acc_mocks.update_many({"library_id": lib_id, "status": "generating"}, {"$set": {"status": "pending"}})
        am.JOBS.pop(lib_id, None)
    return {"ok": True}


@router.post(f"{ADMIN}/libraries/{{lib_id}}/publish")
async def publish(lib_id: str, admin=Depends(require_admin)):
    lib = await _lib(lib_id)
    if lib["status"] not in ("ready", "published"):
        raise HTTPException(409, "Only a complete, validated library (status ready) can be published.")
    if err := await am.publishable(lib):
        raise HTTPException(409, err)
    sb = await sandbox.init()  # fresh live probes; a flag alone is never accepted as proof
    if not sandbox.ready():
        raise HTTPException(409, f"Release blocker: the Round 4 sandbox is not verified ({sb['error'] or 'probes failed'}).")
    if not sandbox_isolated():
        raise HTTPException(409, "Release blocker: Round 4 runs in a shared-kernel chroot jail, not a container/VM. Deploy the isolated runner service "
                                 "(see SANDBOX_DEPLOYMENT.md) and set CODE_SANDBOX_ISOLATED=true only after verifying it.")
    await db.acc_mock_libraries.update_many({"status": "published", "id": {"$ne": lib_id}}, {"$set": {"status": "archived", "archived_at": am.now_iso()}})
    await db.acc_mock_libraries.update_one({"id": lib_id}, {"$set": {"status": "published", "published_at": am.now_iso(), "published_by": admin["email"]}})
    return {"ok": True}


@router.delete(f"{ADMIN}/libraries/{{lib_id}}")
async def delete_draft(lib_id: str, admin=Depends(require_admin)):
    lib = await _lib(lib_id)
    if lib["status"] in ("published", "generating"):
        raise HTTPException(409, "Cannot delete a published or running library.")
    await db.acc_mocks.delete_many({"library_id": lib_id})
    await db.acc_mock_libraries.delete_one({"id": lib_id})
    return {"ok": True}


@router.get(f"{ADMIN}/mocks/{{doc_id}}")
async def admin_mock(doc_id: str, admin=Depends(require_admin)):
    m = await _mock(doc_id)
    for q in (m.get("rounds") or {}).get("technical", {}).get("questions", []):
        q["review_label"], q["review_issue"] = am.review_label(q), am.review_issue(q)
    return m


async def _mock(doc_id, editable=False):
    m = await db.acc_mocks.find_one({"id": doc_id}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Mock not found.")
    if editable:
        lib = await _lib(m["library_id"])
        if lib["status"] in ("published", "archived", "generating"):
            raise HTTPException(409, "Published, archived or running libraries cannot be edited. Generate a new version.")
    return m


async def _save_rounds(m):
    errs, warns, stats = am.validate_mock(m["rounds"])
    await db.acc_mocks.update_one({"id": m["id"]}, {"$set": {"rounds": m["rounds"], "status": "valid" if not errs else "invalid",
                                                             "validation": {"errors": errs, "warnings": warns, "stats": stats, "validated_at": am.now_iso()},
                                                             "updated_at": am.now_iso()}})
    return {"status": "valid" if not errs else "invalid", "validation": {"errors": errs, "warnings": warns, "stats": stats}}


@router.post(f"{ADMIN}/mocks/{{doc_id}}/questions/{{qid}}/review")
async def review_question(doc_id: str, qid: str, body: ReviewIn, admin=Depends(require_admin)):
    m = await _mock(doc_id, editable=True)
    q = next((x for x in m["rounds"]["technical"]["questions"] if x["qid"] == qid), None)
    if not q:
        raise HTTPException(404, "Question not found.")
    if body.action == "approve":
        if body.answer_index is not None:
            if body.answer_index >= len(q["options"]):
                raise HTTPException(400, "Answer index out of range.")
            if body.answer_index != q["answer_index"]:
                q["key_changed_from"] = q["answer_index"]
            q["answer_index"] = body.answer_index
        if body.explanation is not None:
            q["explanation"] = body.explanation.strip()
        if not q.get("explanation"):
            raise HTTPException(400, "An explanation is required to approve.")
    q["review"] = {"status": {"approve": "approved", "reject": "rejected", "reset": "pending"}[body.action], "by": admin["email"], "at": am.now_iso(), "note": body.note}
    out = await _save_rounds(m)
    # same source question reused in other mocks of this draft gets the same decision
    if q.get("origin") == "source" and body.action != "reset":
        async for o in db.acc_mocks.find({"library_id": m["library_id"], "id": {"$ne": m["id"]}, "rounds.technical.questions.bank_id": q["bank_id"]}, {"_id": 0}):
            for x in o["rounds"]["technical"]["questions"]:
                if x.get("bank_id") == q["bank_id"]:
                    x.update(answer_index=q["answer_index"], explanation=q["explanation"], review=q["review"])
            await _save_rounds(o)
    return out


@router.post(f"{ADMIN}/mocks/{{doc_id}}/questions/{{qid}}/replace")
async def replace_question(doc_id: str, qid: str, admin=Depends(require_admin)):
    m = await _mock(doc_id, editable=True)
    new = await am.replace_question(m["library_id"], m, qid)
    m["rounds"]["technical"]["questions"] = [new if q["qid"] == qid else q for q in m["rounds"]["technical"]["questions"]]
    return await _save_rounds(m)


@router.get(f"{ADMIN}/settings/behavioural-scoring")
async def get_beh_scoring(admin=Depends(require_admin)):
    d = await db.acc_mock_settings.find_one({"key": "behavioural_scoring"}, {"_id": 0})
    out = {**am.BEHAVIOURAL_SCORING_DEFAULT, **((d or {}).get("value") or {})}
    out.pop("include_in_overall_score", None)  # removed: R1 never feeds a numeric overall score
    return out


@router.put(f"{ADMIN}/settings/behavioural-scoring")
async def put_beh_scoring(body: BehaviouralScoringIn, admin=Depends(require_admin)):
    if body.bands.low_below >= body.bands.high_from:
        raise HTTPException(400, "Low band must be below the high band.")
    await db.acc_mock_settings.update_one({"key": "behavioural_scoring"}, {"$set": {"value": body.model_dump(), "updated_by": admin["email"],
                                                                                  "updated_at": am.now_iso()}}, upsert=True)
    return {**am.BEHAVIOURAL_SCORING_DEFAULT, **body.model_dump()}


@router.post(f"{ADMIN}/access")
async def set_access(body: AccessIn, admin=Depends(require_admin)):
    ids = [m for m in dict.fromkeys(body.mock_ids) if m in am.MOCK_IDS]
    if not ids:
        raise HTTPException(400, "No valid mock ids (M1-M40).")
    for m in ids:
        await db.acc_mock_access.update_one({"mock_id": m}, {"$set": {"unlocked": body.unlocked, "updated_at": am.now_iso(), "updated_by": admin["email"]}}, upsert=True)
    return {"ok": True, "updated": ids}


UNITS = {"behavioural": "questions", "gamified": "activities", "technical": "MCQs", "coding": "questions"}


def _summary(m, demo=False):
    r = m.get("rounds") or {}
    cfg = m.get("round_config") or am.ROUND_CONFIG
    counts = {"behavioural": len(r.get("behavioural", {}).get("items", [])), "gamified": len(r.get("gamified", {}).get("activities", [])),
              "technical": len(r.get("technical", {}).get("questions", [])), "coding": len(r.get("coding", {}).get("problems", []))}
    rounds = [{"key": k, "title": cfg[k]["title"], "minutes": cfg[k]["minutes"], "items": counts[k], "unit": UNITS[k],
               **({"categories": [c["label"] for c in cfg[k]["categories"].values()]} if k == "technical" else {}),
               **({"activities": [f"{a['title']}{' ' + a['grid'] if a.get('grid') else ''}" for a in cfg[k]["activities"]]} if k == "gamified" else {}),
               **({"sections": [f"{x['title']} · {x['minutes']}m" for x in cfg[k]["slots"]]} if k == "coding" else {})} for k in am.ROUND_KEYS]
    out = {"mock_id": m["mock_id"], "title": m["title"], "version": m["version"], "rounds": rounds, "total_minutes": sum(x["minutes"] for x in rounds)}
    if demo:
        out.update(demo_mode=True, coding_disabled=True, demo_message=am.DEMO_MSG)
        for x in rounds:
            if x["key"] == "coding":
                x["disabled"] = True
    return out


def _visibility(m, lib, pub, unlocked, ind, pubs):
    """Mirrors am.accessible_mock exactly, so the admin sees the candidate's real view."""
    why = []
    pinned = m["mock_id"] in ind and ind[m["mock_id"]]["id"] == m["id"]
    p = pubs.get(m["mock_id"])
    if pinned:
        pass
    elif p and p.get("published") and p.get("mock_doc_id") == m["id"]:
        why.append("published individually but no longer valid/fully reviewed")
    elif p and p.get("published"):
        why.append(f"a different version (v{p['version']}) is the individually published one")
    elif not pub:
        why.append("not published (neither individually nor via a published library)")
    elif pub["id"] != lib["id"]:
        why.append(f"this library is not the published one (v{pub['version']} is)")
    if m["status"] != "valid":
        why.append(f"mock status is {m['status']}")
    if m["mock_id"] not in unlocked:
        why.append("mock is locked")
    return {"candidate_visible": not why, "visibility_reason": "; ".join(why)}


@router.get("/accenture-mocks")
async def catalog(user=Depends(current_user)):
    ids = await am.unlocked_ids()
    found = {k: v for k, v in (await am.individually_published()).items() if k in ids}
    lib = await am.published_library()
    if lib:
        async for m in db.acc_mocks.find({"library_id": lib["id"], "status": "valid", "mock_id": {"$in": [i for i in ids if i not in found]}}, {"_id": 0}):
            found[m["mock_id"]] = m
    out = [_summary(m, await am.coding_disabled(m["mock_id"])) for m in sorted(found.values(), key=lambda m: m.get("index", 0))]
    return {"mocks": out, "version": lib["version"] if lib else None}


# ---------- individual mock publication (separate from library publication) ----------
def _content_blockers(m):
    out = []
    if m.get("status") != "valid":
        out.append(f"mock status is {m.get('status')} (must be valid)")
    if m.get("config_version") != am.CONFIG_VERSION:
        out.append("generated with an outdated assessment structure")
    if m.get("rounds"):
        errs, _, st = am.validate_mock(m["rounds"])
    else:  # list view: persisted validation (publish always re-validates fresh)
        v = m.get("validation") or {}
        errs, st = v.get("errors") or ([] if m.get("status") == "valid" else ["no validated content"]), v.get("stats") or {}
    out += [f"validation: {e}" for e in errs]
    if st.get("review_blocking"):
        out.append(f"{st['review_blocking']} question(s) blocked pending answer-key review")
    if st.get("awaiting_admin_review"):
        out.append(f"{st['awaiting_admin_review']} AI-derived answer key(s) awaiting admin approval")
    return out


def _security_blockers(fresh_state=None):
    sb = fresh_state or sandbox.STATE
    out = []
    if not sandbox.ready():
        out.append(f"Round 4 code runner not verified ({sb.get('error') or 'live probes not passed'}); Round 4 would refuse all code")
    if not sandbox_isolated():
        out.append("Round 4 code runner not approved for candidate use: it is a shared-kernel chroot jail, not a container/VM with network "
                   "disabled (see SANDBOX_DEPLOYMENT.md). CODE_SANDBOX_ISOLATED is not set.")
    return out


async def _mock_status(m, lib, pub_lib, unlocked, ind, pubs):
    p = pubs.get(m["mock_id"])
    pinned = bool(p and p.get("published") and p.get("mock_doc_id") == m["id"])
    via_lib = bool(pub_lib and pub_lib["id"] == lib["id"])
    content = _content_blockers(m)
    security = _security_blockers()
    visible = m["mock_id"] in unlocked and ((m["mock_id"] in ind and ind[m["mock_id"]]["id"] == m["id"]) or (via_lib and m.get("status") == "valid"))
    mode = (p or {}).get("mode") or "full" if pinned else None
    return {"publication_mode": mode, "round4_disabled": mode == am.DEMO_MODE, "demo_available": not content and bool(security),
            "valid": m.get("status") == "valid", "reviewed": not any("review" in c or "approval" in c for c in content) and m.get("status") == "valid",
            "published": pinned or via_lib, "published_individually": pinned, "published_via_library": via_lib,
            "unlocked": m["mock_id"] in unlocked, "candidate_visible": visible, "content_blockers": content, "security_blockers": security,
            "release_blocked": bool(content or security), "publication": p}


@router.get(f"{ADMIN}/mocks/{{mock_id}}/publication")
async def mock_publication(mock_id: str, library_id: str = "", admin=Depends(require_admin)):
    m = await _mock_doc(mock_id, library_id)
    pubs = {p["mock_id"]: p async for p in db.acc_mock_publications.find({"mock_id": mock_id}, {"_id": 0})}
    lib = {"id": m["library_id"]}
    return {"mock_id": mock_id, "version": m["version"], **await _mock_status(m, lib, await am.published_library(), await am.unlocked_ids(), await am.individually_published(), pubs)}


async def _mock_doc(mock_id, library_id):
    q = {"mock_id": mock_id, **({"library_id": library_id} if library_id else {})}
    m = await db.acc_mocks.find_one(q, {"_id": 0}, sort=[("version", -1)])
    if not m:
        raise HTTPException(404, "Mock not found.")
    return m


class MockPublishIn(BaseModel):
    library_id: str = Field("", max_length=64)
    mode: Literal["full", "demo_no_coding"] = "full"


@router.post(f"{ADMIN}/mocks/{{mock_id}}/publish")
async def publish_mock(mock_id: str, body: MockPublishIn, admin=Depends(require_admin)):
    """Publishes ONE mock (pinned to this mock document). Never changes library status. Requires content + live security gates."""
    m = await _mock_doc(mock_id, body.library_id)
    content = _content_blockers(m)
    security = _security_blockers(await sandbox.init())  # fresh live probes; the flag alone is never accepted
    # demo_no_coding: Round 4 execution is disabled server-side, so the runner-isolation gate does not apply. It is NOT waived for full publication.
    if content or (security and body.mode == "full"):
        raise HTTPException(409, {"message": f"{mock_id} cannot be published individually{' (full mode)' if body.mode == 'full' else ''}.",
                                  "content_blockers": content, "security_blockers": security if body.mode == "full" else [],
                                  "demo_available": not content and body.mode == "full"})
    await db.acc_mock_publications.update_one({"mock_id": mock_id}, {"$set": {
        "mock_id": mock_id, "mock_doc_id": m["id"], "library_id": m["library_id"], "version": m["version"], "published": True, "mode": body.mode,
        "security_blockers_at_publish": security, "published_at": am.now_iso(), "published_by": admin["email"], "unpublished_at": None}}, upsert=True)
    return {"ok": True, "mock_id": mock_id, "version": m["version"], "mode": body.mode, "round4_disabled": body.mode == am.DEMO_MODE}


@router.post(f"{ADMIN}/mocks/{{mock_id}}/unpublish")
async def unpublish_mock(mock_id: str, admin=Depends(require_admin)):
    """Immediately removes the individual publication; content and attempts/results are untouched."""
    r = await db.acc_mock_publications.update_one({"mock_id": mock_id, "published": True},
                                                  {"$set": {"published": False, "unpublished_at": am.now_iso(), "unpublished_by": admin["email"]}})
    return {"ok": True, "changed": bool(r.modified_count)}


@router.get("/accenture-mocks/{mock_id}")
async def catalog_item(mock_id: str, user=Depends(current_user)):
    return _summary(await am.accessible_mock(mock_id), await am.coding_disabled(mock_id))
