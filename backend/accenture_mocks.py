"""Accenture predefined mock library (M1-M40): Gemini generation, validation, versioning."""
import asyncio
import hashlib
import logging
import math
import random
import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

import code_runner
import ai
from ai import ask_json as _ask_json, ask_structured as _ask_structured
from database import db
from routes_oa_builder import SQL_RULES, WEB_RULES, _valid_sql, _valid_web

log = logging.getLogger("accenture_mocks")

MOCK_IDS = [f"M{i}" for i in range(1, 41)]
COMPANY = "Accenture"
CONFIG_VERSION = 3
LIKERT = ["Strongly Disagree", "Disagree", "Neutral", "Agree", "Strongly Agree"]
TECH_CATEGORIES = {  # key: (label, questions per mock) - sums to 45
    "pseudocode": ("Pseudocode", 8), "ms_office": ("MS Office concepts", 5), "cloud": ("Cloud computing", 5),
    "networks": ("Computer networks", 6), "cybersecurity": ("Cybersecurity", 5), "oop": ("OOP concepts (Python, Java, JavaScript)", 6),
    "cs_fundamentals": ("CS fundamentals", 5), "sjt": ("Situational Judgement Test (SJT)", 5)}
OOP_LANGS = ["python", "java", "javascript"]
GAME_ACTIVITIES = [
    {"order": 1, "activity_id": "memory_maze_3x3", "game": "memory_maze", "title": "Memory Maze", "grid": "3x3", "minutes": 3},
    {"order": 2, "activity_id": "memory_maze_4x4", "game": "memory_maze", "title": "Memory Maze", "grid": "4x4", "minutes": 3},
    {"order": 3, "activity_id": "bubble_math", "game": "bubble_math", "title": "Bubble Math", "questions": 25, "seconds_per_question": 15,
     "rule": "Select the bubbles in order from LOWEST to HIGHEST value"},
    {"order": 4, "activity_id": "path_finder_3x3", "game": "path_finder", "title": "Path Finder", "grid": "3x3", "minutes": 3},
    {"order": 5, "activity_id": "path_finder_4x4", "game": "path_finder", "title": "Path Finder", "grid": "4x4", "minutes": 3},
    {"order": 6, "activity_id": "path_finder_5x5", "game": "path_finder", "title": "Path Finder", "grid": "5x5", "minutes": 3},
]
CODING_SLOTS = [{"order": 1, "type": "dsa", "title": "DSA", "minutes": 20}, {"order": 2, "type": "sql", "title": "SQL", "minutes": 20},
                {"order": 3, "type": "frontend_js", "title": "JavaScript Frontend", "minutes": 20}]
ROUND_CONFIG = {
    "config_version": CONFIG_VERSION,
    "behavioural": {"order": 1, "title": "Behavioural Assessment (Psychometric)", "count": 50, "minutes": 20, "options": LIKERT,
                    "scoring": {"type": "trait_profile", "objective_marking": False, "settings_key": "behavioural_scoring"}},
    "gamified": {"order": 2, "title": "Gamified Assessment", "count": len(GAME_ACTIVITIES), "minutes": 30, "activities": GAME_ACTIVITIES,
                 "mechanics": "pending_recording", "scoring": {"type": "per_activity", "defined_in": "gamified-round phase"}},
    "technical": {"order": 3, "title": "Technical Assessment (MCQs)", "count": 45, "minutes": 45, "options_per_question": 4,
                  "categories": {k: {"label": l, "count": n} for k, (l, n) in TECH_CATEGORIES.items()}, "source_target": 0.65,
                  "scoring": {"type": "objective_per_question", "correct": 1, "wrong": 0, "negative_marking": False,
                              "sjt": "single best answer with explicit rationale; ambiguous scenarios flagged for review"}},
    "coding": {"order": 4, "title": "Coding Round", "count": len(CODING_SLOTS), "minutes": 60, "slots": CODING_SLOTS,
               "languages": ["python", "java", "cpp", "javascript"], "scoring": {"type": "test_cases"}},
}
ROUND_KEYS = ["behavioural", "gamified", "technical", "coding"]
CONCURRENCY = 3
JOBS = {}


AI_MAX_ATTEMPTS = 3      # key/model attempts per request
AI_ABORT_AFTER = 3       # consecutive failed requests -> stop the whole job (quota / outage)
GUARD = {"fails": 0, "aborted": False}


async def _guarded(coro_fn):
    if GUARD["aborted"]:
        raise HTTPException(503, "Generation stopped: Gemini unavailable or quota exhausted.")
    try:
        r = await coro_fn()
        GUARD["fails"] = 0
        return r
    except HTTPException:
        GUARD["fails"] += 1
        if GUARD["fails"] >= AI_ABORT_AFTER:
            GUARD["aborted"] = True
        raise


async def ask_structured(system, prompt, schema):
    return await _guarded(lambda: _ask_structured(system, prompt, schema, rounds=1, thinking="low", timeout=90, max_attempts=AI_MAX_ATTEMPTS))


async def ask_json(system, prompt):
    return await _guarded(lambda: _ask_json(system, prompt, rounds=1, max_attempts=AI_MAX_ATTEMPTS))


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())).strip()


def qhash(*parts):
    return hashlib.sha1("|".join(norm(p) for p in parts).encode()).hexdigest()


def _jacc(a, b):
    a, b = set(a.split()), set(b.split())
    return len(a & b) / max(1, len(a | b))


class Dedup:
    def __init__(self):
        self.hashes, self.stems = set(), []

    def seen(self, text):
        n = norm(text)
        return qhash(text) in self.hashes or any(_jacc(n, s) > 0.75 for s in self.stems)

    def add(self, text):
        self.hashes.add(qhash(text))
        self.stems.append(norm(text))


# ---------- Gemini schemas ----------
CAT_KEYS = list(TECH_CATEGORIES)
MCQ_SCHEMA = {"type": "object", "required": ["questions"], "properties": {"questions": {"type": "array", "items": {"type": "object",
              "required": ["question", "options", "answer_index", "explanation", "category", "topic", "difficulty"], "properties": {
                  "question": {"type": "string"}, "options": {"type": "array", "items": {"type": "string"}}, "answer_index": {"type": "integer"},
                  "explanation": {"type": "string"}, "category": {"type": "string", "enum": CAT_KEYS}, "topic": {"type": "string"},
                  "oop_language": {"type": "string", "enum": OOP_LANGS + ["none"]}, "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]}}}}}}
SOLVE_SCHEMA = {"type": "object", "required": ["answers"], "properties": {"answers": {"type": "array", "items": {"type": "object",
                "required": ["ref", "answer_index", "explanation", "confidence", "ambiguous", "category"], "properties": {
                    "ref": {"type": "string"}, "answer_index": {"type": "integer"}, "explanation": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]}, "ambiguous": {"type": "boolean"},
                    "category": {"type": "string", "enum": CAT_KEYS}, "oop_language": {"type": "string", "enum": OOP_LANGS + ["none"]}}}}}}
TRAITS = ["conscientiousness", "teamwork", "adaptability", "integrity", "learning_agility", "resilience", "client_focus", "leadership"]
BEH_SCHEMA = {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {"type": "object",
              "required": ["statement", "trait", "reverse_scored"], "properties": {"statement": {"type": "string"}, "trait": {"type": "string", "enum": TRAITS},
                                                                                    "reverse_scored": {"type": "boolean"}}}}}}
DSA_SCHEMA = {"type": "object", "required": ["problems"], "properties": {"problems": {"type": "array", "items": {"type": "object",
              "required": ["title", "difficulty", "topic", "problem", "input_format", "output_format", "constraints", "samples", "hidden_inputs", "reference_python"],
              "properties": {"title": {"type": "string"}, "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]}, "topic": {"type": "string"},
                             "problem": {"type": "string"}, "input_format": {"type": "string"}, "output_format": {"type": "string"}, "constraints": {"type": "string"},
                             "samples": {"type": "array", "items": {"type": "object", "required": ["input", "output"], "properties": {
                                 "input": {"type": "string"}, "output": {"type": "string"}, "explanation": {"type": "string"}}}},
                             "hidden_inputs": {"type": "array", "items": {"type": "string"}}, "reference_python": {"type": "string"},
                             "flags": {"type": "array", "items": {"type": "string"}}}}}}}
SYS = ("You write content for a realistic Accenture online assessment mock. Match the real Accenture OA level, terminology and style "
       "shown in the reference questions. Never claim content is an official or verified Accenture question.")


def _guess_category(topic, text):
    t = f"{topic} {text[:200]}".lower()
    for key, words in (("pseudocode", ["pseudo"]), ("ms_office", ["excel", "word", "powerpoint", "office", "slide"]), ("cybersecurity", ["secur", "cyber", "encrypt", "hack"]),
                       ("cloud", ["cloud"]), ("networks", ["network", "protocol", "tcp", "topolog", "packet"]),
                       ("oop", ["object-oriented", "oop", "class ", "inherit", "polymorph"])):
        if any(w in t for w in words):
            return key
    return "cs_fundamentals"


# ---------- source pool (Accenture dataset already imported into oa_bank via Company OAs) ----------
async def _bank(query):
    return [q async for q in db.oa_bank.find({"company": COMPANY, "status": {"$in": ["ready", "needs_review"]}, **query}, {"_id": 0, "raw": 0})]


def _src_meta(q):
    return {"origin": "source", "bank_id": q["id"], "source_ref": q.get("source_ref", ""), "source_page": q.get("source_page"),
            "source_dataset": q.get("source_dataset", ""), "verified_official": False}


async def prepare_sources(lib):
    """Source wording/options kept verbatim. Missing answer keys are solved by Gemini and marked ai_derived (review required); ambiguous items dropped."""
    flagged = []
    raw = [q for q in await _bank({"question_type": "mcq"}) if not q.get("ocr_uncertain") and (q.get("data") or {}).get("question")
           and len([o for o in q["data"].get("options") or [] if isinstance(o, str) and o.strip()]) >= 4]
    solved = {}

    async def solve(i):
        chunk = raw[i:i + 10]
        txt = "\n\n".join(f"REF {q['id']}\nQ: {q['data']['question']}\n" + "\n".join(f"{j}. {o}" for j, o in enumerate(q["data"]["options"])) for q in chunk)
        try:
            r = await ask_structured("You are a careful examiner. Solve each multiple-choice question (0-based answer_index) and classify it into one category. "
                                     "Mark ambiguous=true if more than one option could be right, an option looks cut off, or the question is unclear.",
                                     f"Categories: {CAT_KEYS}\n\n{txt}\n\nReturn one answer per REF (ref = the REF id).", SOLVE_SCHEMA)
            solved.update({a["ref"]: a for a in r.get("answers", [])})
        except HTTPException as e:
            lib["errors"].append(f"Source answer-key batch {i // 10 + 1} failed: {e.detail}")

    await asyncio.gather(*[solve(i) for i in range(0, len(raw), 10)])
    mcqs = []
    for q in raw:
        d, a = q["data"], solved.get(q["id"])
        item = {**_src_meta(q), "question": d["question"], "options": [o for o in d["options"] if o.strip()][:6], "topic": q.get("topic") or "",
                "difficulty": q.get("difficulty") or "medium", "category": (a or {}).get("category") or _guess_category(q.get("topic", ""), d["question"])}
        if item["category"] == "oop":
            item["oop_language"] = (a or {}).get("oop_language", "none")
        if isinstance(d.get("answer_index"), int) and 0 <= d["answer_index"] < len(item["options"]):
            item.update(answer_index=d["answer_index"], explanation=d.get("explanation") or (a or {}).get("explanation", ""), answer_key_source="source",
                        key_status="source_key", review_required=False)
        elif not a or a["ambiguous"] or a["confidence"] == "low" or not 0 <= a["answer_index"] < len(item["options"]):
            flagged.append({"bank_id": q["id"], "source_ref": q.get("source_ref"), "reason": "ambiguous / unsolvable answer key" if a else "not solved",
                            "question": d["question"][:200]})
            continue
        else:
            item.update(answer_index=a["answer_index"], explanation=a["explanation"], answer_key_source="ai_solved", key_status="ai_derived_unverified",
                        review_required=True, key_confidence=a["confidence"])
        item["review"] = {"status": "pending"}
        mcqs.append(item)
    await cross_check([q for q in mcqs if q["answer_key_source"] == "ai_solved"])
    for q in [q for q in mcqs if q["answer_key_source"] == "ai_solved" and q["cross_check"]["status"] != "agree"]:
        flagged.append({"bank_id": q["bank_id"], "source_ref": q.get("source_ref"), "reason": f"AI answer key not confirmed by independent re-solve ({q['cross_check']['status']})",
                        "question": q["question"][:200]})
        mcqs.remove(q)
    beh = [{**_src_meta(q), "statement": (q["data"].get("question") or q["data"].get("statement") or "").strip(), "trait": q.get("topic") or "general",
            "reverse_scored": False, "options": LIKERT} for q in await _bank({"question_type": {"$in": ["behavioral", "behavioural", "psychometric", "likert"]}})
           if (q.get("data") or {}).get("question") or (q.get("data") or {}).get("statement")]
    dsa = []

    async def one_dsa(q):
        try:
            r = await ask_structured(SYS, f"SOURCE PROBLEM (Accenture dataset, page {q.get('source_page')}):\n{q['data'].get('problem', '')}\n"
                                          f"Notes: {q.get('source_notes', '')}\n\nRewrite as ONE stdin/stdout problem. Keep the original wording, names and examples; "
                                          "remove only the language template. Do NOT invent rules missing from the source - list anything unclear in flags. "
                                          "Give input/output format, constraints, the source's examples as samples, 8 varied hidden_inputs and a correct reference_python.",
                                     DSA_SCHEMA)
            p = (r.get("problems") or [None])[0]
            v = await validate_dsa(p) if p and not p.get("flags") else None
            if v:
                dsa.append({**v, **_src_meta(q), "type": "dsa"})
            else:
                flagged.append({"bank_id": q["id"], "source_ref": q.get("source_ref"), "reason": "coding source unclear or reference failed"
                                + (": " + "; ".join(p["flags"]) if p and p.get("flags") else "")})
        except HTTPException as e:
            lib["errors"].append(f"Source coding {q.get('source_ref')} failed: {e.detail}")

    await asyncio.gather(*[one_dsa(q) for q in await _bank({"question_type": "coding", "completeness": {"$ne": "partial"}})])
    return {"mcqs": mcqs, "beh": beh, "dsa": dsa}, flagged


# ---------- validators ----------
def valid_mcq(q):
    opts = [str(o).strip() for o in (q.get("options") or [])]
    ok_len = 4 <= len(opts) <= 6 if q.get("origin") == "source" else len(opts) == 4
    return (bool((q.get("question") or "").strip()) and ok_len and all(opts) and len({norm(o) for o in opts}) == len(opts)
            and isinstance(q.get("answer_index"), int) and 0 <= q["answer_index"] < len(opts) and bool((q.get("explanation") or "").strip())
            and q.get("category") in TECH_CATEGORIES)


PROCTOR_DEFAULT = {"mode": "strict", "ignore_flags": [], "auto_submit": False, "require_face_registration": True}
BEH_REVIEW_THRESHOLDS = {"min_completion": 0.8, "straight_line_share": 0.9, "neutral_share": 0.6, "reverse_gap": 2.0, "extreme_min_mean": 4.7,
                         "min_items_per_trait": 3}
BEHAVIOURAL_SCORING_DEFAULT = {"type": "trait_profile", "objective_marking": False, "scale_values": [1, 2, 3, 4, 5], "reverse_scoring": True,
                               "aggregation": "mean", "bands": {"low_below": 2.5, "high_from": 3.75}, "consistency_check": True,
                               "show_trait_profile_to_candidate": True, "review_thresholds": BEH_REVIEW_THRESHOLDS}
CROSS_BATCH = 15


async def cross_check(items):
    """Independent blind re-solve (key hidden). Sets cross_check = agree | disagree | ambiguous | error. Never marks anything verified."""
    await asyncio.gather(*[_cross_batch(items[i:i + CROSS_BATCH]) for i in range(0, len(items), CROSS_BATCH)])
    return items


async def _cross_batch(chunk):
    if chunk:
        refs = {f"q{j}": q for j, q in enumerate(chunk)}
        txt = "\n\n".join(f"REF {r}\n[{q['category']}] {q['question']}\n" + "\n".join(f"{j}. {o}" for j, o in enumerate(q["options"])) for r, q in refs.items())
        try:
            res = await ask_structured("You are an independent examiner. Solve each question from scratch (0-based answer_index). For SJT scenarios choose the "
                                       "single most effective workplace response. Set ambiguous=true if two options are defensible, the question is unclear, "
                                       "or no option is correct.", f"Categories: {CAT_KEYS}\n\n{txt}", SOLVE_SCHEMA)
            got = {a["ref"]: a for a in res.get("answers", [])}
        except HTTPException:
            got = {}
        for r, q in refs.items():
            a = got.get(r)
            st = "error" if not a else "ambiguous" if a["ambiguous"] or a["confidence"] == "low" else "agree" if a["answer_index"] == q["answer_index"] else "disagree"
            q["cross_check"] = {"status": st, "answer_index": (a or {}).get("answer_index"), "confidence": (a or {}).get("confidence"),
                                "note": (a or {}).get("explanation", "")[:400], "at": now_iso()}


def review_issue(q):
    """Why this question blocks publication (None = publishable). Admin approval overrides AI checks, never the structure."""
    if not valid_mcq(q):
        return "invalid structure or answer key"
    rv = (q.get("review") or {}).get("status")
    if rv == "rejected":
        return "rejected by admin - replace it"
    if rv == "approved" or q.get("key_status") == "source_key":
        return None
    cc = (q.get("cross_check") or {}).get("status")
    return None if cc == "agree" else f"AI-derived key not confirmed (cross-check: {cc or 'pending'})"


def review_label(q):
    if (q.get("review") or {}).get("status") == "approved":
        return "Admin reviewed"
    if (q.get("review") or {}).get("status") == "rejected":
        return "Rejected"
    if q.get("key_status") == "source_key":
        return "Source answer key"
    cc = (q.get("cross_check") or {}).get("status")
    return "AI-derived — unverified" + (" (independently cross-checked)" if cc == "agree" else f" · FLAGGED: {cc or 'not cross-checked'}")


def _ai_mcq(q, k):
    return {"origin": "generated", "verified_official": False, "answer_key_source": "ai_generated", "key_status": "ai_derived_unverified",
            "review_required": True, "review": {"status": "pending"}, "question": q["question"].strip(), "options": [o.strip() for o in q["options"]],
            "answer_index": q["answer_index"], "explanation": q["explanation"], "category": k, "topic": q["topic"], "difficulty": q["difficulty"],
            **({"oop_language": q["oop_language"]} if k == "oop" else {})}


async def validate_dsa(p):
    """Expected outputs come from executing the reference solution, never from the model."""
    if not p or not all(p.get(k) for k in ("title", "problem", "input_format", "output_format", "reference_python")) or not p.get("samples"):
        return None
    async with code_runner.Program("python", p["reference_python"]) as prog:
        for s in p["samples"]:
            r = await prog.run(s["input"])
            if r["status"] or not code_runner.same_output(r["stdout"], s["output"]):
                return None
        tests = []
        for inp in dict.fromkeys(i for i in p.get("hidden_inputs") or [] if i.strip()):
            r = await prog.run(inp)
            if not r["status"] and r["stdout"].strip():
                tests.append({"id": f"h{len(tests) + 1}", "input": inp, "expected": r["stdout"].strip()})
    if len(tests) < 5:
        return None
    return {**{k: p.get(k, "") for k in ("title", "difficulty", "topic", "problem", "input_format", "output_format", "constraints")},
            "samples": [{"input": s["input"], "output": s["output"], "explanation": s.get("explanation", "")} for s in p["samples"]],
            "hidden_tests": tests[:10], "reference_python": p["reference_python"]}


def validate_mock(rounds):
    errs, warns = [], []
    cfg = ROUND_CONFIG
    b = rounds.get("behavioural", {}).get("items", [])
    if len(b) != cfg["behavioural"]["count"]:
        errs.append(f"Behavioural: {len(b)}/{cfg['behavioural']['count']} statements")
    if len({norm(i["statement"]) for i in b}) != len(b) or any(not i.get("statement") or i.get("options") != LIKERT for i in b):
        errs.append("Behavioural: duplicate/empty statements or wrong agreement scale")
    g = rounds.get("gamified", {}).get("activities", [])
    if [{k: v for k, v in a.items() if k in GAME_ACTIVITIES[0] or k in GAME_ACTIVITIES[2]} for a in g] != GAME_ACTIVITIES:
        errs.append("Gamified: activities do not match the required 6-activity sequence")
    t = rounds.get("technical", {}).get("questions", [])
    if len(t) != cfg["technical"]["count"]:
        errs.append(f"Technical: {len(t)}/{cfg['technical']['count']} MCQs")
    if bad := [i + 1 for i, q in enumerate(t) if not valid_mcq(q)]:
        errs.append(f"Technical: invalid structure in Q{bad}")
    per = {k: sum(1 for q in t if q.get("category") == k) for k in TECH_CATEGORIES}
    if miss := [f"{TECH_CATEGORIES[k][0]} {per[k]}/{n}" for k, (_, n) in TECH_CATEGORIES.items() if per[k] != n]:
        errs.append("Technical: category counts wrong - " + ", ".join(miss))
    langs = {q.get("oop_language") for q in t if q.get("category") == "oop"}
    if not set(OOP_LANGS) <= langs:
        errs.append(f"Technical: OOP must cover Python, Java and JavaScript (has {sorted(l for l in langs if l)})")
    if len({qhash(q["question"]) for q in t}) != len(t):
        errs.append("Technical: duplicate questions")
    if n := sum(1 for q in t if q.get("review_required")):
        warns.append(f"Technical: {n} answer key(s) are AI-derived and not independently verified - review required")
    c = rounds.get("coding", {}).get("problems", [])
    if [p.get("type") for p in c] != [s["type"] for s in CODING_SLOTS]:
        errs.append(f"Coding: must be exactly DSA, SQL, JavaScript Frontend in order (has {[p.get('type') for p in c]})")
    for p in c:
        if p.get("type") == "dsa" and len(p.get("hidden_tests") or []) < 5:
            errs.append("Coding: DSA has fewer than 5 verified hidden tests")
        if p.get("type") == "sql" and len(p.get("tests") or []) < 2:
            errs.append("Coding: SQL has fewer than 2 verified datasets")
        if p.get("type") == "frontend_js" and len(p.get("tests") or []) < 3:
            errs.append("Coding: Frontend has fewer than 3 verified DOM tests")
    blocking = [{"qid": q.get("qid"), "reason": r} for q in t if (r := review_issue(q))]
    if blocking:
        warns.append(f"Review: {len(blocking)} question(s) block publication until reviewed or replaced")
    src = sum(1 for q in t if q["origin"] == "source")
    stats = {"review_blocking": len(blocking), "awaiting_admin_review": sum(1 for q in t if q.get("review_required") and (q.get("review") or {}).get("status") != "approved"),"behavioural": len(b), "behavioural_source": sum(1 for i in b if i["origin"] == "source"), "activities": len(g),
             "technical_source": src, "technical_generated": len(t) - src, "technical_source_ratio": round(src / max(1, len(t)), 2), "technical_by_category": per,
             "coding_source": sum(1 for p in c if p.get("origin") == "source"), "ai_derived_keys": n}
    if stats["technical_source_ratio"] < cfg["technical"]["source_target"]:
        warns.append(f"Technical: actual source ratio {int(stats['technical_source_ratio'] * 100)}% (target 65% not reachable with the usable source pool)")
    stats["blocking"] = blocking
    return errs, warns, stats


# ---------- per-mock generation ----------
def _games(idx):
    rnd = random.Random(f"accenture-mock-{idx}")
    return [{**a, "seed": rnd.randint(1, 10 ** 9), "mechanics": "pending_recording"} for a in GAME_ACTIVITIES]


async def _gen_behavioural(idx, need, refs, dedup):
    out = []
    ref_txt = "\n".join(f"- {r['statement']}" for r in refs[:10])
    for _ in range(2):
        if len(out) >= need:
            break
        r = await ask_structured(SYS, (f"REFERENCE STATEMENTS (Accenture style):\n{ref_txt}\n\n" if ref_txt else "") +
                                 f"Mock M{idx}. Write {need - len(out) + 6} distinct first-person workplace statements for a psychometric round answered on "
                                 f"the scale {LIKERT}. Spread evenly over traits {TRAITS}; about 1/3 reverse_scored. Realistic for Accenture "
                                 "(client delivery, teamwork, deadlines, learning new tech). No duplicates, no trick wording.", BEH_SCHEMA)
        for it in r.get("items", []):
            if len(out) < need and it.get("statement") and not dedup.seen(it["statement"]):
                dedup.add(it["statement"])
                out.append({"statement": it["statement"].strip(), "trait": it["trait"], "reverse_scored": bool(it["reverse_scored"]), "options": LIKERT,
                            "origin": "generated", "verified_official": False})
    return out


async def _gen_mcq_batch(idx, quota, refs, dedup):
    ref_txt = "\n\n".join(f"- [{q['category']}] {q['question']}\n  options: {q['options']}" for q in refs[:8])
    spec = ", ".join(f"{n} x {k} ({TECH_CATEGORIES[k][0]})" for k, n in quota.items())
    r = await ask_structured(SYS, f"REFERENCE ACCENTURE OA QUESTIONS (style/difficulty guide, do not copy):\n{ref_txt}\n\n"
                                  f"Write NEW technical MCQs for mock M{idx}: {spec}, plus 2 spare per category. Exactly 4 distinct options, one correct "
                                  "(0-based answer_index), short explanation. Scenario style ('Assume that...', 'Consider that...'). Pseudocode questions include "
                                  "the code and a deterministic output. OOP questions set oop_language (python/java/javascript) and must use that language's code "
                                  "or semantics. SJT questions are workplace scenarios with exactly one clearly most effective response (others clearly weaker); the explanation must "
                                  "justify the key AND say briefly why each other option is less effective. Other categories: oop_language=none.",
                             MCQ_SCHEMA)
    return r.get("questions", [])


async def _gen_mcqs(idx, quota, refs, dedup, oop_need):
    """Generated MCQs are kept only if an independent blind re-solve agrees with the key; others are discarded and regenerated."""
    out = []
    for _ in range(3):
        left = {k: n for k, n in quota.items() if n > 0}
        if not left:
            break
        keys = list(left)
        batches = [dict((k, left[k]) for k in keys[i:i + 3]) for i in range(0, len(keys), 3)]
        res = await asyncio.gather(*[_gen_mcq_batch(idx, b, refs, dedup) for b in batches], return_exceptions=True)
        need, cand = dict(quota), []
        for qs in [r for r in res if not isinstance(r, Exception)]:
            for q in qs:
                q["origin"] = "generated"
                k = q.get("category")
                if k == "oop" and q.get("oop_language") not in OOP_LANGS:
                    continue
                if k == "oop" and oop_need and q["oop_language"] not in oop_need and need.get("oop", 0) <= len(oop_need):
                    continue
                if need.get(k, 0) > 0 and valid_mcq(q) and not dedup.seen(q["question"]):
                    need[k] -= 1
                    cand.append(_ai_mcq(q, k))
        for q in await cross_check(cand):
            if q["cross_check"]["status"] == "agree" and quota.get(q["category"], 0) > 0 and not dedup.seen(q["question"]):
                dedup.add(q["question"])
                quota[q["category"]] -= 1
                oop_need.discard(q.get("oop_language"))
                out.append(q)
    return out


async def replace_question(lib_id, mock, qid):
    """Admin-triggered: swap one technical question for a new same-category one (cross-checked)."""
    qs = mock["rounds"]["technical"]["questions"]
    old = next((q for q in qs if q["qid"] == qid), None)
    if not old:
        raise HTTPException(404, "Question not found.")
    dedup = Dedup()
    async for m in db.acc_mocks.find({"library_id": lib_id}, {"_id": 0, "rounds.technical.questions.question": 1}):
        for q in (m.get("rounds") or {}).get("technical", {}).get("questions", []):
            dedup.add(q["question"])
    others = {q.get("oop_language") for q in qs if q["category"] == "oop" and q["qid"] != qid}
    need = (set(OOP_LANGS) - others) if old["category"] == "oop" else set()
    new = await _gen_mcqs(mock["index"], {old["category"]: 1}, [q for q in qs if q["category"] == old["category"]], dedup, need)
    if not new:
        raise HTTPException(503, "Could not generate a replacement that passed the independent check. Try again.")
    new[0].update(qid=qid, replaced_from={"question": old["question"][:300], "origin": old["origin"], "at": now_iso()})
    return new[0]


async def _gen_dsa(idx, refs, dedup):
    ref_txt = "\n\n".join(p["problem"][:800] for p in refs[:2])
    for _ in range(3):
        r = await ask_structured(SYS, f"REFERENCE ACCENTURE CODING PROBLEMS:\n{ref_txt or '(none) - arrays, strings, math, greedy; easy-medium'}\n\n"
                                      f"Write 2 NEW Accenture-style DSA problems for mock M{idx} (solvable in 20 minutes). Story-style statement, stdin/stdout, "
                                      "precise input/output format, constraints, 2 samples, 8 hidden_inputs with edge cases, a correct efficient reference_python.", DSA_SCHEMA)
        for p in r.get("problems", []):
            if not dedup.seen(p.get("problem", "")) and (v := await validate_dsa(p)):
                dedup.add(p["problem"])
                return {**v, "type": "dsa", "origin": "generated", "verified_official": False}
    return None


async def _gen_sql(idx, dedup):
    for _ in range(3):
        data = await ask_json(SYS, f"Write 2 NEW SQL query problems for Accenture mock M{idx} (solvable in 20 minutes; joins/group by/subqueries).\n{SQL_RULES}\n"
                                   'Return JSON: {"problems": [{"title": str, "difficulty": str, "problem": str (task + exact output columns, order and row order rule), '
                                   '"schema": str (CREATE TABLE only), "datasets": [str, str, str] (INSERT scripts: sample, edge cases, larger), '
                                   '"reference": str (one correct SELECT), "ordered": bool}]}')
        for p in data.get("problems", []):
            if not dedup.seen(p.get("problem", "")) and (v := await _valid_sql(p)):
                dedup.add(p["problem"])
                return {**v, "type": "sql", "origin": "generated", "verified_official": False}
    return None


async def _gen_web(idx, dedup):
    for _ in range(3):
        data = await ask_json(SYS, f"Write 2 NEW JavaScript frontend (HTML/CSS/vanilla JS DOM) tasks for Accenture mock M{idx}, solvable in 20 minutes.\n{WEB_RULES}\n"
                                   'Return JSON: {"problems": [{"title": str, "difficulty": str, "problem": str (requirements naming exact ids/classes/text), '
                                   '"starter": {"html": str, "css": str, "js": str} (skeleton, does NOT solve), "reference": {"html": str, "css": str, "js": str}, '
                                   '"tests": [{"name": str, "why": str, "script": str}] (6-8 DOM tests)}]}')
        for p in data.get("problems", []):
            if not dedup.seen(p.get("problem", "")) and (v := await _valid_web(p)):
                dedup.add(p["problem"])
                return {**v, "type": "frontend_js", "origin": "generated", "verified_official": False}
    return None


def _pick_sources(pool, k, uses, cap, quota=None):
    avail = sorted((q for q in pool if uses.get(q["bank_id"], 0) < cap), key=lambda q: (uses.get(q["bank_id"], 0), random.random()))
    sel = []
    for q in avail:
        if len(sel) >= k:
            break
        if quota is not None:
            if quota.get(q["category"], 0) <= 0:
                continue
            quota[q["category"]] -= 1
        sel.append(q)
        uses[q["bank_id"]] = uses.get(q["bank_id"], 0) + 1
    return [dict(q) for q in sel]


def _budget(pool, cap, per_mock_max):
    return min(per_mock_max, math.ceil(len(pool) * cap / len(MOCK_IDS)))


def _round_ok(errs, prefix):
    return not any(e.startswith(prefix) for e in errs)


async def _safe(coro):
    try:
        return await coro
    except Exception as e:
        log.warning("round generation failed: %s", getattr(e, "detail", None) or e)
        return e


async def build_mock(lib, idx, ctx):
    """Resumable: rounds (and coding problems) that already passed validation are kept; only missing parts are generated."""
    mid = f"M{idx}"
    prev = await db.acc_mocks.find_one({"library_id": lib["id"], "mock_id": mid}, {"_id": 0, "rounds": 1})
    old = (prev or {}).get("rounds") or {}
    old_errs = validate_mock(old)[0] if old else ["Behavioural:", "Technical:", "Coding:"]
    await db.acc_mocks.update_one({"library_id": lib["id"], "mock_id": mid}, {"$set": {"status": "generating", "updated_at": now_iso(), "error": None}})
    try:
        cfg, cap, s = ROUND_CONFIG, ctx["cap"], ctx["src"]
        keep_b, keep_t = old and _round_ok(old_errs, "Behavioural:"), old and _round_ok(old_errs, "Technical:")
        need_tests = {"dsa": ("hidden_tests", 5), "sql": ("tests", 2), "frontend_js": ("tests", 3)}
        old_code = {p["type"]: p for p in (old.get("coding") or {}).get("problems", [])
                    if p.get("type") in need_tests and len(p.get(need_tests[p["type"]][0]) or []) >= need_tests[p["type"]][1]}
        jobs = {}
        if not keep_b:
            src_b = _pick_sources(s["beh"], _budget(s["beh"], cap, round(cfg["behavioural"]["count"] * 0.65)), ctx["uses"], cap)
            jobs["beh"] = _gen_behavioural(idx, cfg["behavioural"]["count"] - len(src_b), src_b or s["beh"], ctx["beh_dedup"])
        if not keep_t:
            quota = {k: n for k, (_, n) in TECH_CATEGORIES.items()}
            src_q = _pick_sources(s["mcqs"], _budget(s["mcqs"], cap, round(cfg["technical"]["count"] * cfg["technical"]["source_target"])), ctx["uses"], cap, quota)
            oop_need = set(OOP_LANGS) - {q.get("oop_language") for q in src_q if q["category"] == "oop"}
            jobs["mcq"] = _gen_mcqs(idx, quota, src_q or s["mcqs"], ctx["mcq_dedup"], oop_need)
        if "dsa" not in old_code:
            src_dsa = _pick_sources(s["dsa"], 1, ctx["uses"], cap)
            jobs["dsa"] = asyncio.sleep(0, src_dsa[0]) if src_dsa else _gen_dsa(idx, s["dsa"], ctx["code_dedup"])
        if "sql" not in old_code:
            jobs["sql"] = _gen_sql(idx, ctx["code_dedup"])
        if "frontend_js" not in old_code:
            jobs["web"] = _gen_web(idx, ctx["code_dedup"])
        res = dict(zip(jobs, await asyncio.gather(*[_safe(c) for c in jobs.values()])))
        failed = [k for k, v in res.items() if isinstance(v, Exception) or v is None]
        ok = lambda k: None if k in failed else res.get(k)
        if keep_b:
            items = old["behavioural"]["items"]
        else:
            items = src_b + (ok("beh") or [])
            for i, it in enumerate(items):
                it["qid"] = f"{mid}-B{i + 1}"
        if keep_t:
            questions = old["technical"]["questions"]
        else:
            order = list(TECH_CATEGORIES)
            questions = sorted(src_q + (ok("mcq") or []), key=lambda q: (order.index(q["category"]), random.Random(mid + q["question"]).random()))
            for i, q in enumerate(questions):
                q["qid"] = f"{mid}-T{i + 1}"
        problems = [old_code.get(t) or ok(k) for t, k in (("dsa", "dsa"), ("sql", "sql"), ("frontend_js", "web"))]
        problems = [p for p in problems if p]
        for p in problems:
            slot = next(x for x in CODING_SLOTS if x["type"] == p["type"])
            p.update(qid=f"{mid}-C{slot['order']}", order=slot["order"], minutes=slot["minutes"])
        rounds = {"behavioural": {"items": items}, "gamified": {"activities": _games(idx)}, "technical": {"questions": questions}, "coding": {"problems": problems}}
        errs, warns, stats = validate_mock(rounds)
        unfinished = [n for n, pre in (("Round 1 Behavioural", "Behavioural:"), ("Round 2 Gamified", "Gamified:"), ("Round 3 Technical", "Technical:"),
                                       ("Round 4 Coding", "Coding:")) if not _round_ok(errs, pre)]
        status = "valid" if not errs else "incomplete" if failed or unfinished else "invalid"
        await db.acc_mocks.update_one({"library_id": lib["id"], "mock_id": mid}, {"$set": {
            "rounds": rounds, "validation": {"errors": errs, "warnings": warns, "stats": stats, "validated_at": now_iso(), "unfinished_rounds": unfinished},
            "status": status, "error": ("Gemini failed for: " + ", ".join(failed)) if failed else None, "updated_at": now_iso()}})
    except Exception as e:
        log.exception("mock %s failed", mid)
        msg = getattr(e, "detail", None) or str(e) or type(e).__name__
        await db.acc_mocks.update_one({"library_id": lib["id"], "mock_id": mid}, {"$set": {"status": "failed", "error": str(msg)[:300], "updated_at": now_iso()}})


async def _ctx(lib, cap):
    """Source pool is prepared once per library and cached, so retries never re-call Gemini for it."""
    if lib.get("source_cache"):
        src, flagged = lib["source_cache"], (lib.get("source_pool") or {}).get("flagged", [])
    else:
        n_err = len(lib["errors"])
        src, flagged = await prepare_sources(lib)
        if len(lib["errors"]) == n_err and not GUARD["aborted"]:
            await db.acc_mock_libraries.update_one({"id": lib["id"]}, {"$set": {"source_cache": src}})
    ctx = {"src": src, "cap": cap, "uses": {}, "beh_dedup": Dedup(), "mcq_dedup": Dedup(), "code_dedup": Dedup()}
    for q in src["mcqs"]:
        ctx["mcq_dedup"].add(q["question"])
    for q in src["beh"]:
        ctx["beh_dedup"].add(q["statement"])
    async for m in db.acc_mocks.find({"library_id": lib["id"], "status": "valid"}, {"_id": 0, "rounds": 1}):
        r = m.get("rounds") or {}
        for coll, dd, key in (("behavioural.items", "beh_dedup", "statement"), ("technical.questions", "mcq_dedup", "question"), ("coding.problems", "code_dedup", "problem")):
            a, b = coll.split(".")
            for it in r.get(a, {}).get(b, []):
                if it.get("origin") == "source":
                    ctx["uses"][it["bank_id"]] = ctx["uses"].get(it["bank_id"], 0) + 1
                else:
                    ctx[dd].add(it[key])
    return ctx, flagged


async def refresh_library(lib_id):
    counts = {}
    async for r in db.acc_mocks.aggregate([{"$match": {"library_id": lib_id}}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}]):
        counts[r["_id"]] = r["n"]
    return counts


async def run_generation(lib_id, only_bad=False, mock_ids=None):
    lib = await db.acc_mock_libraries.find_one({"id": lib_id}, {"_id": 0})
    lib["errors"] = []
    GUARD.update(fails=0, aborted=False)
    attempts0 = ai.ATTEMPTS["n"]
    todo = []
    try:
        await db.acc_mock_libraries.update_one({"id": lib_id}, {"$set": {"status": "generating", "stage": "Preparing Accenture source questions", "updated_at": now_iso()}})
        ctx, flagged = await _ctx(lib, lib.get("max_source_reuse", 1))
        s = ctx["src"]
        await db.acc_mock_libraries.update_one({"id": lib_id}, {"$set": {
            "source_pool": {"mcq_usable": len(s["mcqs"]), "behavioural_usable": len(s["beh"]), "coding_usable": len(s["dsa"]), "flagged": flagged,
                            "ai_solved_keys": sum(1 for q in s["mcqs"] if q["answer_key_source"] == "ai_solved"),
                            "mcq_by_category": {k: sum(1 for q in s["mcqs"] if q["category"] == k) for k in TECH_CATEGORIES}},
            "stage": "Generating mocks", "errors": lib["errors"]}})
        q = {"library_id": lib_id, **({"status": {"$ne": "valid"}} if only_bad else {}), **({"mock_id": {"$in": mock_ids}} if mock_ids else {})}
        todo = [d["mock_id"] async for d in db.acc_mocks.find(q, {"mock_id": 1})]
        todo.sort(key=lambda m: int(m[1:]))
        sem = asyncio.Semaphore(CONCURRENCY)

        async def one(mid):
            async with sem:
                await build_mock(lib, int(mid[1:]), ctx)

        await asyncio.gather(*[one(m) for m in todo])
        counts = await refresh_library(lib_id)
        status = "ready" if counts.get("valid", 0) == len(MOCK_IDS) else "incomplete"
        stage = "Stopped: Gemini unavailable/quota exhausted" if GUARD["aborted"] else f"Done ({', '.join(todo) if mock_ids else 'all requested'})"
        await db.acc_mock_libraries.update_one({"id": lib_id}, {"$set": {"status": status, "stage": stage, "last_run": {
            "mock_ids": todo, "api_attempts": ai.ATTEMPTS["n"] - attempts0, "aborted": GUARD["aborted"], "at": now_iso()}, "counts": counts, "errors": lib["errors"],
                                                                         "finished_at": now_iso(), "updated_at": now_iso()}})
    except Exception as e:
        log.exception("library %s generation crashed", lib_id)
        await db.acc_mock_libraries.update_one({"id": lib_id}, {"$set": {"status": "incomplete", "stage": "Crashed",
                                                                         "errors": lib["errors"] + [str(getattr(e, "detail", e))[:300]], "updated_at": now_iso()}})
    finally:
        JOBS.pop(lib_id, None)


def start(lib_id, only_bad=False, mock_ids=None):
    JOBS[lib_id] = asyncio.create_task(run_generation(lib_id, only_bad, mock_ids))


async def new_library(admin, max_source_reuse):
    last = await db.acc_mock_libraries.find_one({}, {"version": 1}, sort=[("version", -1)])
    lib = {"id": str(uuid.uuid4()), "version": (last or {}).get("version", 0) + 1, "company": COMPANY, "status": "generating", "stage": "Queued",
           "round_config": ROUND_CONFIG, "config_version": CONFIG_VERSION, "max_source_reuse": max_source_reuse, "errors": [], "created_by": admin["email"],
           "created_at": now_iso(), "updated_at": now_iso()}
    await db.acc_mock_libraries.insert_one(dict(lib))
    await db.acc_mocks.insert_many([{"id": str(uuid.uuid4()), "library_id": lib["id"], "version": lib["version"], "mock_id": m, "index": i + 1,
                                     "title": f"Accenture Mock {m}", "status": "pending", "round_config": ROUND_CONFIG, "config_version": CONFIG_VERSION,
                                     "created_at": now_iso(), "updated_at": now_iso()} for i, m in enumerate(MOCK_IDS)])
    return lib


async def publishable(lib):
    """Current config only, all 40 mocks re-validated against the exact structure."""
    if lib.get("config_version") != CONFIG_VERSION or lib.get("round_config") != ROUND_CONFIG:
        return "This library was generated with an outdated assessment structure. Generate a new version."
    bad = []
    async for m in db.acc_mocks.find({"library_id": lib["id"]}, {"_id": 0, "mock_id": 1, "status": 1, "rounds": 1, "config_version": 1}):
        errs, _, st = validate_mock(m.get("rounds") or {})
        if m["status"] != "valid" or m.get("config_version") != CONFIG_VERSION or errs or st["review_blocking"]:
            bad.append(m["mock_id"])
    n = await db.acc_mocks.count_documents({"library_id": lib["id"]})
    if bad or n != len(MOCK_IDS):
        return f"Only a complete, validated and fully reviewed library can be published ({n - len(bad)}/40 ready; blocked: {', '.join(bad[:10])})."
    return None


async def published_library():
    return await db.acc_mock_libraries.find_one({"status": "published"}, {"_id": 0, "id": 1, "version": 1, "published_at": 1})


async def unlocked_ids():
    return {d["mock_id"] async for d in db.acc_mock_access.find({"unlocked": True}, {"mock_id": 1})}


def _still_clean(m):
    st = ((m or {}).get("validation") or {}).get("stats") or {}
    return bool(m) and m.get("status") == "valid" and m.get("config_version") == CONFIG_VERSION and not st.get("review_blocking") and not st.get("awaiting_admin_review")


async def individually_published():
    """{mock_id: mock doc} for mocks published on their own (pinned to one mock document), still valid and fully reviewed."""
    pubs = [p async for p in db.acc_mock_publications.find({"published": True}, {"_id": 0})]
    docs = {m["id"]: m async for m in db.acc_mocks.find({"id": {"$in": [p["mock_doc_id"] for p in pubs]}}, {"_id": 0})}
    return {p["mock_id"]: docs[p["mock_doc_id"]] for p in pubs if _still_clean(docs.get(p["mock_doc_id"]))}


DEMO_MODE = "demo_no_coding"
DEMO_MSG = ("Round 4 coding is disabled in this demo: the code runner is not yet approved as securely isolated, so candidate code is not "
            "executed or submitted. Rounds 1-3 are available; there is no Round 4 score and no overall practice score.")


async def publication_mode(mock_id):
    """'full' | 'demo_no_coding' for an active individual publication, else None (library publication = full)."""
    p = await db.acc_mock_publications.find_one({"mock_id": mock_id, "published": True}, {"_id": 0, "mode": 1})
    return (p.get("mode") or "full") if p else None


async def coding_disabled(mock_id):
    return await publication_mode(mock_id) == DEMO_MODE


async def accessible_mock(mock_id):
    """Backend gate used by every candidate endpoint: unlocked AND (individually published OR in the published library) AND valid; else 404."""
    if mock_id not in MOCK_IDS or mock_id not in await unlocked_ids():
        raise HTTPException(404, "This mock is not available.")
    ind = await individually_published()
    if mock_id in ind:
        return ind[mock_id]
    lib = await published_library()
    m = await db.acc_mocks.find_one({"library_id": lib["id"], "mock_id": mock_id, "status": "valid"}, {"_id": 0}) if lib else None
    if not m:
        raise HTTPException(404, "This mock is not available.")
    return m
