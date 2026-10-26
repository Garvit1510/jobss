"""Accenture Round 2 (gamified) engine: config, runtime generation, server-side validation, timers and persistence."""
import random
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import accenture_mocks as am
from auth import current_user, require_admin
from database import db

router = APIRouter(prefix="/api")
GAME_VERSION = "g1-2026-10"
GRACE_SEC = 3
# Mechanics established from the user's recording/screenshots. Anything not visible there is listed in `unconfirmed`.
GAME_CONFIG = {
    "version": GAME_VERSION,
    "engines": {
        "memory_maze": {"status": "implemented", "rules": [
            "Grid shows the player, a key and a door; the safe path is hidden.",
            "Move one cell at a time with the arrow buttons around the player.",
            "A move off the hidden path flashes red and sends the player back to the start (new attempt).",
            "Collect the key ('Key collected'), then reach the door ('Maze Solved!')."],
            "options": {"reset_key_on_wrong": True, "mazes_per_section": 1},
            "metrics": ["solved", "attempts", "moves", "time_taken_sec"],
            "unconfirmed": ["reset_key_on_wrong: the recording does not show whether the key is dropped after a wrong move (configurable, default: dropped)",
                            "mazes_per_section: the recording shows one maze per section; whether another maze follows a quick solve is not shown (configurable, default 1)"]},
        "bubble_math": {"status": "implemented", "instruction": "Select the bubbles in order from the LOWEST to the HIGHEST value.", "rules": [
            "25 questions, 3 bubbles each showing a number or a small expression (+, -, x, /).",
            "Selected bubbles show their order (1, 2, 3); after the 3rd click the next question loads.",
            "Correct only if selected lowest to highest; 15 seconds per question, timeout = not correct."],
            "options": {"show_incorrect_feedback": False, "difficulty": "flat"},
            "metrics": ["correct", "total", "percent"],
            "unconfirmed": ["show_incorrect_feedback: no feedback for a wrong order is visible in the recording (configurable, default off)",
                            "difficulty: no change in difficulty across the 25 questions is established (configurable 'flat' | 'progressive', default flat)"]},
        "path_finder": {"status": "implemented", "rules": [
            "The board is a grid of arrow tiles; the path starts at the start icon on the left and must reach the goal icon on the right.",
            "Yellow tiles show the path currently traced from the start by following the arrows.",
            "Click a tile to select it. Rotate turns the selected tile's arrow; Swap exchanges two selected tiles. Each rotate/swap counts as a move.",
            "Press Check: if the arrows lead from start to goal you see 'Great! You found the path' with your moves; you can also retry the board."],
            "options": {"rotate_step_deg": 45, "boards_per_section": 1},
            "metrics": ["solved", "moves", "par_moves", "score"],
            "unconfirmed": ["rotate_step_deg: rotation direction/step is not demonstrated (engine: 45 deg clockwise, so diagonal arrows are reachable)",
                            "Swap semantics are not demonstrated (engine: swaps the two selected tiles)",
                            "Board construction: whether every cell holds an arrow (engine: yes) and how scrambled the board starts (engine: n-1 path tiles off by 1-2 rotations)",
                            "Message for an unsuccessful Check is not visible (engine: 'Path is not complete yet')",
                            "Exact 'Score' formula on the results screen is not shown (engine: practice model below)"]},
    },
}
SCORING_DEFAULT = {
    "model": "practice_v1", "official": False, "cutoff_percent": 70,
    "weights": {a: 1 for a in ("memory_maze_3x3", "memory_maze_4x4", "bubble_math", "path_finder_3x3", "path_finder_4x4", "path_finder_5x5")},
    "memory_maze": {"solved_base": 100, "penalty_per_extra_attempt": 10, "min_if_solved": 40},
    "path_finder": {"solve_points": 50, "efficiency_points": 50},
    "note": ("Configurable practice-assessment scoring model, not official Accenture scoring. Memory Maze: solved = 100 minus 10 per extra attempt "
             "(min 40), unsolved/time-up = 0. Bubble Math: % of 25 questions correct (timeouts count as wrong). Path Finder: solved = 50 + 50 x "
             "min(1, par moves / moves used), unsolved/time-up = 0. Round 2 % = weighted mean of the six activity scores; pass if >= cutoff."),
}
DIRS8 = [(0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1)]  # E, SE, S, SW, W, NW, N, NE (clockwise)
OPS = ["+", "-", "x", "/"]


def now():
    return datetime.now(timezone.utc)


def iso(d):
    return d.isoformat()


# ---------- generators ----------
def gen_maze(n, rnd):
    cells = [(r, c) for r in range(n) for c in range(n)]
    target = max(4, n * n // 2 + 1)
    for _ in range(500):
        path = [rnd.choice(cells)]
        while len(path) < target:
            r, c = path[-1]
            nxt = [(r + dr, c + dc) for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)) if 0 <= r + dr < n and 0 <= c + dc < n and (r + dr, c + dc) not in path]
            if not nxt:
                break
            path.append(rnd.choice(nxt))
        if len(path) >= target:
            k = rnd.randint(len(path) // 3, 2 * len(path) // 3)
            return {"n": n, "path": [list(p) for p in path], "start": list(path[0]), "key": list(path[k]), "door": list(path[-1])}
    raise RuntimeError("maze generation failed")


def _expr(v, rnd):
    kind = rnd.choice(["num", "+", "-", "x", "/"])
    if kind == "+" and v > 1:
        a = rnd.randint(1, v - 1)
        return f"{a} + {v - a}"
    if kind == "-":
        b = rnd.randint(1, 9)
        return f"{v + b} - {b}"
    if kind == "x":
        ds = [d for d in range(2, v) if v % d == 0]
        if ds:
            d = rnd.choice(ds)
            return f"{d} x {v // d}"
    if kind == "/":
        d = rnd.randint(2, 4)
        return f"{v * d} / {d}"
    return str(v)


def gen_bubbles(count, rnd, difficulty="flat"):
    qs = []
    for i in range(count):
        hi = 20 if difficulty == "flat" else 10 + (i * 40) // max(1, count - 1)
        vals = rnd.sample(range(1, hi + 1), 3)
        qs.append({"exprs": [_expr(v, rnd) for v in vals], "values": vals})
    return qs


def pf_trace(board, n, start_row, goal_row):
    cells, seen, cur = [], set(), (start_row, 0)
    while 0 <= cur[0] < n and 0 <= cur[1] < n and cur not in seen:
        seen.add(cur)
        cells.append(list(cur))
        d = board[cur[0]][cur[1]]
        if cur == (goal_row, n - 1) and d == 0:
            return cells, True
        cur = (cur[0] + DIRS8[d][0], cur[1] + DIRS8[d][1])
    return cells, False


def gen_pathfinder(n, rnd, step):
    k = 8 // (step // 45)
    for _ in range(500):
        sr = rnd.randrange(n)
        path, cur = [(sr, 0)], (sr, 0)
        while cur[1] < n - 1:
            opts = [d for d in (0, 1, 7, 2, 6) if 0 <= cur[0] + DIRS8[d][0] < n and (cur[0] + DIRS8[d][0], cur[1] + DIRS8[d][1]) not in path]
            if cur[1] + 1 >= n:
                break
            if not opts:
                break
            d = rnd.choice(opts + [0, 0])
            if d not in opts:
                d = opts[0]
            cur = (cur[0] + DIRS8[d][0], cur[1] + DIRS8[d][1])
            path.append(cur)
        if cur[1] != n - 1:
            continue
        sol = [[rnd.randrange(8) for _ in range(n)] for _ in range(n)]
        for (r, c), nxt in zip(path, path[1:]):
            sol[r][c] = DIRS8.index((nxt[0] - r, nxt[1] - c))
        sol[cur[0]][cur[1]] = 0
        if not pf_trace(sol, n, sr, cur[0])[1]:
            continue
        board = [row[:] for row in sol]
        unit = 8 // k
        par = 0
        for (r, c) in rnd.sample(path, min(len(path), max(1, n - 1))):
            back = rnd.randint(1, 2 if k == 8 else 1)
            board[r][c] = (board[r][c] - back * unit) % 8
            par += back
        if not pf_trace(board, n, sr, cur[0])[1]:
            return {"n": n, "start_row": sr, "goal_row": cur[0], "initial": board, "par": par, "solution": sol}
    raise RuntimeError("path finder generation failed")


def _activity_state(a, rnd):
    if a["game"] == "memory_maze":
        n = int(a["grid"].split("x")[0])
        m = gen_maze(n, rnd)
        return {"maze": m, "pos": m["start"], "has_key": False, "attempts": 1, "moves": 0, "solved": False}
    if a["game"] == "bubble_math":
        return {"questions": gen_bubbles(a["questions"], rnd, GAME_CONFIG["engines"]["bubble_math"]["options"]["difficulty"]), "index": 0, "answers": [], "q_started": None}
    n = int(a["grid"].split("x")[0])
    pf = gen_pathfinder(n, rnd, GAME_CONFIG["engines"]["path_finder"]["options"]["rotate_step_deg"])
    return {"pf": pf, "board": [r[:] for r in pf["initial"]], "moves": 0, "attempts": 1, "checks": 0, "solved": False}


# ---------- persistence ----------
async def scoring_config():
    d = await db.acc_mock_settings.find_one({"key": "gamified_scoring"}, {"_id": 0})
    return {**SCORING_DEFAULT, **((d or {}).get("value") or {})}


class TileIn(BaseModel):
    r: int = Field(..., ge=0, le=9)
    c: int = Field(..., ge=0, le=9)


class SwapIn(BaseModel):
    a: TileIn
    b: TileIn


class ScoringIn(BaseModel):
    cutoff_percent: float = Field(..., ge=0, le=100)
    weights: dict
    memory_maze: dict
    path_finder: dict


class OptionsIn(BaseModel):
    memory_maze: dict
    bubble_math: dict
    path_finder: dict



class StartIn(BaseModel):
    preview: bool = False


class MoveIn(BaseModel):
    dir: Literal["up", "down", "left", "right"]


class BubbleIn(BaseModel):
    index: int = Field(..., ge=0, le=99)
    order: List[int] = Field(..., min_length=0, max_length=3)


async def _mock_for(user, mock_id, preview):
    if preview:
        if user.get("role") != "admin":
            raise HTTPException(403, "Preview is admin-only.")
        m = await db.acc_mocks.find_one({"mock_id": mock_id, "status": "valid"}, {"_id": 0}, sort=[("version", -1)])
        if not m:
            raise HTTPException(404, "No valid draft for this mock.")
        return m
    return await am.accessible_mock(mock_id)


def _deadline(a):
    secs = a["questions"] * a["seconds_per_question"] if a["game"] == "bubble_math" else a["minutes"] * 60
    return secs


def _finish(act, reason):
    st, g = act["state"], act["game"]
    if g == "memory_maze":
        took = (min(now(), datetime.fromisoformat(act["deadline"])) - datetime.fromisoformat(act["started_at"])).total_seconds()
        act["result"] = {"solved": st["solved"], "attempts": st["attempts"], "moves": st["moves"], "time_taken_sec": round(st.get("solved_in", took))}
    elif g == "bubble_math":
        total = len(st["questions"])
        correct = sum(1 for x in st["answers"] if x["correct"])
        act["result"] = {"correct": correct, "total": total, "percent": round(100 * correct / total)}
    else:
        act["result"] = {"solved": st["solved"], "moves": st["moves"], "par_moves": st["pf"]["par"], "attempts": st["attempts"], "checks": st["checks"]}
    act["status"], act["ended_at"], act["end_reason"] = "done", iso(now()), reason


def activity_score(act, sc):
    r, g = act.get("result") or {}, act["game"]
    if g == "memory_maze":
        m = sc["memory_maze"]
        return max(m["min_if_solved"], m["solved_base"] - m["penalty_per_extra_attempt"] * (r.get("attempts", 1) - 1)) if r.get("solved") else 0
    if g == "bubble_math":
        return r.get("percent", 0)
    p = sc["path_finder"]
    return round(p["solve_points"] + p["efficiency_points"] * min(1, r["par_moves"] / max(1, r["moves"]))) if r.get("solved") else 0


def round_score(attempt, sc):
    rows = []
    for a in attempt["activities"]:
        a["score"] = activity_score(a, sc) if a["status"] == "done" else 0
        rows.append((sc["weights"].get(a["activity_id"], 1), a["score"]))
    tw = sum(w for w, _ in rows) or 1
    pct = round(sum(w * s for w, s in rows) / tw, 1)
    return {"percent": pct, "cutoff_percent": sc["cutoff_percent"], "passed": pct >= sc["cutoff_percent"], "model": sc["model"], "official": False,
            "activity_scores": {a["activity_id"]: a["score"] for a in attempt["activities"]}, "computed_at": iso(now())}


def _expire(attempt):
    """Server-side timers: an activity past its deadline is closed, never extended."""
    changed = False
    for act in attempt["activities"]:
        if act["status"] != "active":
            continue
        if act["game"] == "bubble_math":
            st = act["state"]
            while st["index"] < len(st["questions"]) and st["q_started"] and now() > datetime.fromisoformat(st["q_started"]) + timedelta(seconds=15 + GRACE_SEC):
                st["answers"].append({"index": st["index"], "order": [], "correct": False, "timeout": True})
                st["index"] += 1
                st["q_started"] = iso(datetime.fromisoformat(st["q_started"]) + timedelta(seconds=15))
                changed = True
            if st["index"] >= len(st["questions"]):
                _finish(act, "completed")
                changed = True
        if act["status"] == "active" and now() > datetime.fromisoformat(act["deadline"]) + timedelta(seconds=GRACE_SEC):
            _finish(act, "time_up")
            changed = True
    if all(a["status"] == "done" for a in attempt["activities"]) and not attempt.get("finished_at"):
        attempt["finished_at"] = iso(now())
        attempt["round_score"] = round_score(attempt, attempt.get("scoring") or SCORING_DEFAULT)
        changed = True
    return changed


def public(attempt):
    """Never exposes maze paths or bubble values."""
    acts = []
    for a in attempt["activities"]:
        p = {k: a.get(k) for k in ("activity_id", "game", "title", "grid", "minutes", "questions", "seconds_per_question", "rule", "order",
                                   "status", "started_at", "deadline", "result", "mechanics")}
        eng = GAME_CONFIG["engines"][a["game"]]
        p.update(rules=eng["rules"], instruction=eng.get("instruction"), unconfirmed=eng["unconfirmed"])
        st = a.get("state") or {}
        if a["status"] == "active" and a["game"] == "memory_maze":
            m = st["maze"]
            p["play"] = {"n": m["n"], "pos": st["pos"], "door": m["door"], "key": None if st["has_key"] else m["key"], "has_key": st["has_key"], "attempts": st["attempts"]}
        if a["status"] == "active" and a["game"] == "path_finder":
            cells, solved_now = pf_trace(st["board"], st["pf"]["n"], st["pf"]["start_row"], st["pf"]["goal_row"])
            p["play"] = {"n": st["pf"]["n"], "board": st["board"], "start_row": st["pf"]["start_row"], "goal_row": st["pf"]["goal_row"], "trace": cells,
                         "moves": st["moves"], "attempts": st["attempts"]}
        if a["status"] == "done":
            p["score"] = activity_score(a, attempt.get("scoring") or SCORING_DEFAULT)
        if a["status"] == "active" and a["game"] == "bubble_math" and st["index"] < len(st["questions"]):
            p["play"] = {"index": st["index"], "exprs": st["questions"][st["index"]]["exprs"], "q_started": st["q_started"], "total": len(st["questions"])}
        acts.append(p)
    cur = next((i for i, a in enumerate(attempt["activities"]) if a["status"] != "done"), None)
    return {"id": attempt["id"], "mock_id": attempt["mock_id"], "preview": attempt["preview"], "game_version": attempt["game_version"], "current": cur,
            "activities": acts, "finished_at": attempt.get("finished_at"), "scoring": {k: (attempt.get("scoring") or SCORING_DEFAULT)[k] for k in ("note", "cutoff_percent", "model", "official")},
            "round_score": attempt.get("round_score"), "server_time": iso(now())}


async def _attempt(user, mock_id):
    a = await db.acc_attempts.find_one({"user_id": user["id"], "mock_id": mock_id, "round": "gamified"}, {"_id": 0}, sort=[("created_at", -1)])
    if not a:
        raise HTTPException(404, "No attempt started.")
    if not a["preview"]:
        await am.accessible_mock(mock_id)
    if _expire(a):
        await _save(a)
    return a


async def _save(a):
    await db.acc_attempts.update_one({"id": a["id"]}, {"$set": {"activities": a["activities"], "finished_at": a.get("finished_at"),
                                                                 "round_score": a.get("round_score"), "updated_at": iso(now())}})


def _current(a, game=None):
    act = next((x for x in a["activities"] if x["status"] != "done"), None)
    if not act or act["status"] != "active" or (game and act["game"] != game):
        raise HTTPException(409, "This activity is not active.")
    return act


# ---------- candidate / preview endpoints ----------
G = "/accenture-mocks/{mock_id}/gamified"


@router.post(G + "/start")
async def start(mock_id: str, body: StartIn, user=Depends(current_user)):
    m = await _mock_for(user, mock_id, body.preview)
    old = await db.acc_attempts.find_one({"user_id": user["id"], "mock_id": mock_id, "round": "gamified", "preview": body.preview}, {"_id": 0}, sort=[("created_at", -1)])
    if old and not (body.preview and old.get("finished_at")):
        _expire(old)
        return public(old)
    from accenture_rounds import _require_previous
    await _require_previous(user, mock_id, "gamified", body.preview)
    await load_options()
    rnd = random.Random(uuid.uuid4().hex)
    acts = [{**{k: v for k, v in a.items() if k not in ("seed",)}, "status": "pending", "state": _activity_state(a, rnd)}
            for a in sorted(m["rounds"]["gamified"]["activities"], key=lambda x: x["order"])]
    for a in acts:
        a["mechanics"] = GAME_CONFIG["engines"][a["game"]]["status"]
    doc = {"scoring": await scoring_config(), "engine_options": {k: e["options"] for k, e in GAME_CONFIG["engines"].items()},
           "id": str(uuid.uuid4()), "user_id": user["id"], "mock_id": mock_id, "library_id": m["library_id"], "mock_version": m["version"],
           "round": "gamified", "game_version": GAME_VERSION, "preview": body.preview, "activities": acts, "created_at": iso(now())}
    from accenture_proctor import oa_config
    doc["proctoring_policy"] = (await oa_config(m))["proctoring"]
    await db.acc_attempts.insert_one(dict(doc))
    return public(doc)


@router.get(G)
async def get_attempt(mock_id: str, user=Depends(current_user)):
    return public(await _attempt(user, mock_id))


@router.post(G + "/begin")
async def begin(mock_id: str, user=Depends(current_user)):
    a = await _attempt(user, mock_id)
    act = next((x for x in a["activities"] if x["status"] != "done"), None)
    if not act:
        raise HTTPException(409, "Round already finished.")
    if act["status"] == "pending":
        t = now()
        act.update(status="active", started_at=iso(t), deadline=iso(t + timedelta(seconds=_deadline(act))))
        if act["game"] == "bubble_math":
            act["state"]["q_started"] = iso(t)
        await _save(a)
    return public(a)


@router.post(G + "/maze/move")
async def maze_move(mock_id: str, body: MoveIn, user=Depends(current_user)):
    a = await _attempt(user, mock_id)
    act = _current(a, "memory_maze")
    st, m = act["state"], act["state"]["maze"]
    dr, dc = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}[body.dir]
    r, c = st["pos"][0] + dr, st["pos"][1] + dc
    if not (0 <= r < m["n"] and 0 <= c < m["n"]):
        raise HTTPException(400, "Move is outside the grid.")
    st["moves"] += 1
    event = "moved"
    if [r, c] in m["path"]:
        st["pos"] = [r, c]
        if [r, c] == m["key"] and not st["has_key"]:
            st["has_key"], event = True, "key"
        elif [r, c] == m["door"] and st["has_key"]:
            st["solved_count"] = st.get("solved_count", 0) + 1
            event = "solved"
            if st["solved_count"] >= _opt(a, "memory_maze", "mazes_per_section"):
                st["solved"] = True
                st["solved_in"] = (now() - datetime.fromisoformat(act["started_at"])).total_seconds()
                _finish(act, "solved")
            else:
                nm = gen_maze(m["n"], random.Random(uuid.uuid4().hex))
                st.update(maze=nm, pos=nm["start"], has_key=False)
    else:
        st.update(pos=m["start"], attempts=st["attempts"] + 1)
        if _opt(a, "memory_maze", "reset_key_on_wrong"):
            st["has_key"] = False
        event = "wrong"
    _expire(a)
    await _save(a)
    return {"event": event, "wrong_cell": [r, c] if event == "wrong" else None, **public(a)}


@router.post(G + "/bubble/answer")
async def bubble_answer(mock_id: str, body: BubbleIn, user=Depends(current_user)):
    a = await _attempt(user, mock_id)
    act = _current(a, "bubble_math")
    st = act["state"]
    if body.index != st["index"]:
        return {"event": "stale", **public(a)}
    vals = st["questions"][st["index"]]["values"]
    ok = sorted(body.order) == [0, 1, 2] and [vals[i] for i in body.order] == sorted(vals)
    st["answers"].append({"index": st["index"], "order": body.order, "correct": ok, "timeout": False,
                          "time_ms": round((now() - datetime.fromisoformat(st["q_started"])).total_seconds() * 1000)})
    st["index"] += 1
    st["q_started"] = iso(now())
    if st["index"] >= len(st["questions"]):
        _finish(act, "completed")
    _expire(a)
    await _save(a)
    return {"event": "correct" if ok else "incorrect" if _opt(a, "bubble_math", "show_incorrect_feedback") else "answered", **public(a)}


def _opt(a, eng, key):
    return ((a.get("engine_options") or {}).get(eng) or GAME_CONFIG["engines"][eng]["options"])[key]


def _pf(a):
    act = _current(a, "path_finder")
    return act, act["state"]


def _in(st, t):
    if not (t.r < st["pf"]["n"] and t.c < st["pf"]["n"]):
        raise HTTPException(400, "Tile outside the board.")


@router.post(G + "/path/rotate")
async def pf_rotate(mock_id: str, body: TileIn, user=Depends(current_user)):
    a = await _attempt(user, mock_id)
    act, st = _pf(a)
    _in(st, body)
    st["board"][body.r][body.c] = (st["board"][body.r][body.c] + _opt(a, "path_finder", "rotate_step_deg") // 45) % 8
    st["moves"] += 1
    await _save(a)
    return public(a)


@router.post(G + "/path/swap")
async def pf_swap(mock_id: str, body: SwapIn, user=Depends(current_user)):
    a = await _attempt(user, mock_id)
    act, st = _pf(a)
    _in(st, body.a)
    _in(st, body.b)
    if (body.a.r, body.a.c) == (body.b.r, body.b.c):
        raise HTTPException(400, "Select two different tiles.")
    b = st["board"]
    b[body.a.r][body.a.c], b[body.b.r][body.b.c] = b[body.b.r][body.b.c], b[body.a.r][body.a.c]
    st["moves"] += 1
    await _save(a)
    return public(a)


@router.post(G + "/path/check")
async def pf_check(mock_id: str, user=Depends(current_user)):
    a = await _attempt(user, mock_id)
    act, st = _pf(a)
    st["checks"] += 1
    ok = pf_trace(st["board"], st["pf"]["n"], st["pf"]["start_row"], st["pf"]["goal_row"])[1]
    if ok:
        st["solved"] = True
        _finish(act, "solved")
        _expire(a)
    await _save(a)
    return {"event": "solved" if ok else "not_yet", "moves": st["moves"], **public(a)}


@router.post(G + "/path/retry")
async def pf_retry(mock_id: str, user=Depends(current_user)):
    a = await _attempt(user, mock_id)
    act, st = _pf(a)
    st["board"] = [r[:] for r in st["pf"]["initial"]]
    st["attempts"] += 1
    await _save(a)
    return public(a)


@router.post(G + "/time-up")
async def time_up(mock_id: str, user=Depends(current_user)):
    """Client timer hint; the server only closes the activity if its own deadline has passed."""
    return public(await _attempt(user, mock_id))


@router.delete(G)
async def reset_preview(mock_id: str, admin=Depends(require_admin)):
    await db.acc_attempts.delete_many({"user_id": admin["id"], "mock_id": mock_id, "round": "gamified", "preview": True})
    return {"ok": True}


@router.get("/admin/accenture-mocks/games-config")
async def games_config(admin=Depends(require_admin)):
    return {**GAME_CONFIG, "activities": am.GAME_ACTIVITIES, "scoring": await scoring_config()}


@router.put("/admin/accenture-mocks/games-config/scoring")
async def put_scoring(body: ScoringIn, admin=Depends(require_admin)):
    await db.acc_mock_settings.update_one({"key": "gamified_scoring"}, {"$set": {"value": body.model_dump(), "updated_by": admin["email"], "updated_at": iso(now())}}, upsert=True)
    return await scoring_config()


@router.put("/admin/accenture-mocks/games-config/options")
async def put_options(body: OptionsIn, admin=Depends(require_admin)):
    """Settings for rules the references do not establish; applied to new attempts and persisted across restarts."""
    for k, v in body.model_dump().items():
        allowed = GAME_CONFIG["engines"][k]["options"]
        allowed.update({o: v[o] for o in allowed if o in v})
    if GAME_CONFIG["engines"]["path_finder"]["options"]["rotate_step_deg"] not in (45, 90):
        GAME_CONFIG["engines"]["path_finder"]["options"]["rotate_step_deg"] = 45
    await db.acc_mock_settings.update_one({"key": "gamified_options"}, {"$set": {"value": {k: e["options"] for k, e in GAME_CONFIG["engines"].items()}}}, upsert=True)
    return {k: e["options"] for k, e in GAME_CONFIG["engines"].items()}


async def load_options():
    d = await db.acc_mock_settings.find_one({"key": "gamified_options"}, {"_id": 0})
    for k, v in ((d or {}).get("value") or {}).items():
        if k in GAME_CONFIG["engines"]:
            GAME_CONFIG["engines"][k]["options"].update(v)
