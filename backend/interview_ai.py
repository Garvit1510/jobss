import re

import careers
from ai import ask_json

QUESTION_SYS = """You are a friendly, experienced human interviewer hiring for the candidate's target role and industry (any profession: tech, sales, healthcare, teaching, trades, finance, government, hospitality and more), running a live interview.
How you ask questions:
- Ask exactly ONE question per turn. Never bundle several questions, never add "also" or "and how would you..." sub-questions.
- Keep it short and conversational: 1-2 sentences, ideally 8-25 words. Only scenario questions may go up to ~35 words.
- Sound like a real interviewer talking, not an exam paper. No long background, no formal preambles, no lists, no markdown, no numbering, no labels like "Question:".
- Ask practical, commonly asked interview questions for THIS profession: role knowledge, the candidate's experience, real workplace scenarios.
  Never ask coding/DSA questions unless the role is technical. For role-play stages you play the customer/client/patient/student and stay in character briefly.
- Never invent obscure or artificially hard questions to look smart. Never reveal or hint at the answer.
- Listen to the previous answer. If it was incomplete, vague or wrong, ask a short probing or clarifying follow-up on the same topic.
  If it was good, you may ask one natural deeper follow-up, or move on. Do not repeat a question already asked.
- The "reaction" is what you say before the question: a brief natural acknowledgement of the last answer (max ~10 words),
  e.g. "Correct.", "Okay, makes sense.", "Not quite.", "Got it, thanks." Never explain the answer in the reaction. No praise inflation."""

EVAL_SYS = """You are a fair, senior interview assessor. You only grade; you never ask questions.
Rubric for each answer (0-10 each): correctness (accurate for this profession), relevance (answers what was asked),
completeness (covers the key points expected at this level), clarity (clear and structured).
Overall score 0-10 reflects mainly correctness and relevance. A short but correct, relevant answer must score well (7+);
do NOT penalise brevity, only missing key points. Judge against the candidate's level and the question's difficulty.
Feedback: max 2 short sentences, specific. better_answer: a concise model answer (max ~60 words) in plain text."""

STAGES = {
    "intro": "short introduction / background (e.g. tell me about yourself, why this role)",
    "resume": "a specific project or experience from the candidate's resume",
    "core": "a core professional/technical knowledge question for this role (common, practical)",
    "problem": "a practical problem-solving question for this profession (tech: small logic/data problem described verbally; otherwise a numerical, troubleshooting or work-planning problem)",
    "roleplay": "a short role-play: you play a customer/client/prospect/patient and say one line in character; the candidate responds as the professional",
    "case": "a short business, finance or estimation case for this role",
    "situational": "a realistic situational judgement question from this profession's daily work",
    "demo": "ask the candidate to briefly explain/teach a concept from their subject as they would to a class",
    "awareness": "a public-administration / ethics / current-governance awareness question suited to government interview boards (avoid fast-changing news)",
    "scenario": "a realistic role-specific scenario (debugging, design trade-off, handling an incident)",
    "behavioral": "a behavioral question (teamwork, conflict, failure, ownership)",
    "hr": "an HR question (motivation, strengths, career goals, expectations)",
}
PLANS = {
    "Mixed": ["intro", "resume", "core", "core", "problem", "scenario", "core", "behavioral", "problem", "behavioral"],
    "Technical": ["intro", "resume", "core", "core", "problem", "core", "scenario", "problem", "core", "scenario"],
    "HR": ["intro", "hr", "resume", "hr", "behavioral", "hr", "behavioral", "hr", "behavioral", "hr"],
    "Behavioral": ["intro", "behavioral", "resume", "behavioral", "behavioral", "scenario", "behavioral", "behavioral", "behavioral", "behavioral"],
}
PLANS.update(careers.STYLE_PLANS)
LEVELS = ["Easy", "Medium", "Hard"]
START = {"Fresher": 0, "Junior": 0, "Mid": 1, "Senior": 1}


def stage_for(interview_type, n_total, idx):
    plan = PLANS.get(interview_type) or PLANS["Mixed"]
    if idx == n_total - 1 and n_total >= 5 and interview_type == "Mixed":
        return "behavioral"
    return plan[min(idx, len(plan) - 1)]


def difficulty_for(level, scores):
    d = START.get(level, 0)
    recent = [x for x in scores[-2:] if isinstance(x, (int, float))]
    if len(recent) == 2 and sum(recent) / 2 >= 8:
        d += 1 + (len(scores) >= 4 and sum(scores[-4:]) / 4 >= 8)
    elif recent and sum(recent) / len(recent) <= 4:
        d -= 1
    if level in ("Fresher", "Junior", "Auto"):
        d = min(d, 1 if len(scores) < 3 else 2)
    return LEVELS[max(0, min(2, d))]


_MD = re.compile(r"[*_`#>]|^\s*(?:\d+[.)]|[-•])\s*", re.M)
_LABEL = re.compile(r"^\s*(question|q\d*|interviewer)\s*[:\-]\s*", re.I)
_MULTI = re.compile(r"\b(also|additionally|furthermore|as well as|and then explain|and how would you|and what about)\b", re.I)


def clean(text):
    return re.sub(r"\s+", " ", _LABEL.sub("", _MD.sub("", text or ""))).strip()


def _norm(t):
    return set(re.findall(r"[a-z0-9]+", t.lower()))


def problems(q, stage, previous):
    issues = []
    words = len(q.split())
    if words > (38 if stage in ("scenario", "problem") else 30):
        issues.append(f"too long ({words} words)")
    if q.count("?") > 1:
        issues.append("contains more than one question")
    if len([s for s in re.split(r"(?<=[.?!])\s+", q) if s]) > 2:
        issues.append("more than 2 sentences")
    if _MULTI.search(q):
        issues.append("bundles extra sub-questions")
    if words < 3:
        issues.append("too short to be a question")
    qn = _norm(q)
    for p in previous:
        pn = _norm(p)
        if qn and pn and len(qn & pn) / len(qn | pn) > 0.8:
            issues.append("repeats an earlier question")
            break
    return issues


def salvage(q):
    first = q.split("?")[0].strip()
    return (first + "?") if first else q


def context(s, resume_ctx):
    jd = s.get("job_description") or ""
    sec = careers.sector(s["sector"]) if s.get("sector") in {x["id"] for x in careers.sectors()} else None
    sec_txt = (f"Sector: {sec['name']}. Competencies to assess: {', '.join(sec.get('competencies', []))}.\n" if sec else "")
    return (f"Role: {s['role']}{' at ' + s['company'] if s.get('company') else ''}\nInterview type: {s['interview_type']}\n{sec_txt}"
            f"{s.get('evidence', '')}\n"
            f"Candidate level: {s.get('level', 'Auto')} (Auto = infer from resume; no experience = fresher)\n"
            f"{('Job description (excerpt): ' + jd[:2500]) if jd else ''}\nCandidate resume:\n{resume_ctx}"
            + ("\nThis interview is for the job above: mix questions on the job's requirements/responsibilities with questions on the candidate's own resume projects and experience, linking the two where possible." if jd else ""))


def transcript(turns):
    return "\n".join(f"Interviewer: {t['question']}\nCandidate: {t.get('answer', '(no answer yet)')}" for t in turns) or "(interview not started)"


async def next_question(s, resume_ctx, turns):
    idx = len([t for t in turns if t.get("answer")])
    stage = stage_for(s["interview_type"], s["num_questions"], idx)
    scores = [t.get("evaluation", {}).get("score") for t in turns if t.get("evaluation")]
    diff = difficulty_for(s.get("level", "Auto"), scores)
    first = idx == 0
    probed = bool(turns) and turns[-1].get("kind") == "follow_up"
    task = (f"This is question {idx + 1} of {s['num_questions']}. Planned stage: {stage} = {STAGES[stage]}. Target difficulty: {diff}.\n"
            + ("Open the interview: reaction = a warm one-line greeting using the candidate's first name if known (max 12 words). "
               if first else "You already asked a follow-up on this topic, so do NOT follow up again: move on to the planned stage with a new topic. "
               if probed else "Decide: if the last answer was incomplete/incorrect or invites a natural deeper probe, ask ONE short follow-up "
               "on it instead of the planned stage. Otherwise ask the planned stage question. ")
            + 'Return JSON: {"reaction": str, "question": str, "kind": "follow_up"|"new", "stage": str, "difficulty": "Easy"|"Medium"|"Hard"}')
    prompt = f"{context(s, resume_ctx)}\n\nTRANSCRIPT SO FAR:\n{transcript(turns)}\n\n{task}"
    previous = [t["question"] for t in turns]
    data, issues = {}, []
    for _ in range(2):
        data = await ask_json(QUESTION_SYS, prompt + (f"\nYour previous draft was rejected: {'; '.join(issues)}. Rewrite it as ONE short question." if issues else ""))
        q = clean(data.get("question", ""))
        issues = problems(q, stage, previous)
        if not issues:
            break
    if issues:
        q = salvage(q)
    reaction = " ".join(clean(data.get("reaction", "")).split()[:14])
    return {"question": q, "reaction": reaction, "kind": data.get("kind", "new"), "stage": data.get("stage") or stage,
            "difficulty": data.get("difficulty") if data.get("difficulty") in LEVELS else diff}


async def evaluate(s, resume_ctx, turns):
    t = turns[-1]
    if t.get("kind") == "coding":
        c = t.get("coding") or {}
        prompt = (f"{context(s, resume_ctx)}\n\nLIVE CODING PROBLEM ({t.get('difficulty', 'Medium')}): {c.get('title')}\n{c.get('problem')}\n"
                  f"Examples: {c.get('examples')}\nConstraints: {c.get('constraints')}\n\nCANDIDATE CODE ({t.get('language') or 'unspecified'}):\n"
                  f"{(t.get('code') or '(no code)')[:8000]}\n\nJUDGE RESULTS: {t.get('judge', 'not run')}\n"
                  f"CANDIDATE'S SPOKEN WALKTHROUGH: {t['answer']}\n\n"
                  "Grade the code (correctness: judge test pass rate is the main signal; efficiency) and the walkthrough (clear reasoning). "
                  'Return JSON: {"score": int, "rubric": {"correctness": int, "relevance": int, "completeness": int, "clarity": int}, '
                  '"feedback": str, "better_answer": str (short description of the optimal approach), "complexity": str}')
        ev = await ask_json(EVAL_SYS, prompt)
        ev["score"] = max(0, min(10, int(ev.get("score") or 0)))
        return ev
    prompt = (f"{context(s, resume_ctx)}\n\nEARLIER TRANSCRIPT:\n{transcript(turns[:-1])}\n\nQUESTION ({t.get('difficulty', 'Medium')}, {t.get('stage', 'core')}): {t['question']}\n"
              f"CANDIDATE ANSWER: {t['answer']}\n\n"
              'Grade only this answer. Return JSON: {"score": int, "rubric": {"correctness": int, "relevance": int, "completeness": int, "clarity": int}, '
              '"feedback": str, "better_answer": str}')
    ev = await ask_json(EVAL_SYS, prompt)
    ev["score"] = max(0, min(10, int(ev.get("score") or 0)))
    return ev


TECH_RX = re.compile(r"develop|engineer|sde|programm|software|backend|frontend|front-end|back-end|full ?stack|data|machine learning|\bml\b|"
                     r"devops|android|ios|\bweb\b|coder|analyst|java|python|react|node|golang|\bc\+\+", re.I)


def wants_coding(s, turns):
    tech = careers.sector(s["sector"]).get("coding") if s.get("sector") in {x["id"] for x in careers.sectors()} else bool(TECH_RX.search(s["role"]))
    if s.get("coding_done") or s["interview_type"] not in ("Technical", "Mixed") or not tech:
        return False
    if s["num_questions"] - len(turns) < 1:
        return False
    graded = [t["evaluation"]["score"] for t in turns if t.get("evaluation") and t.get("stage") != "intro"]
    recent = graded[-3:]
    return len(graded) >= 2 and sum(recent) / len(recent) >= 7


async def coding_question(s, resume_ctx, turns):
    scores = [t.get("evaluation", {}).get("score") for t in turns if t.get("evaluation")]
    diff = difficulty_for(s.get("level", "Auto"), scores)
    prompt = (f"{context(s, resume_ctx)}\n\nTRANSCRIPT SO FAR:\n{transcript(turns)}\n\n"
              f"The candidate is doing well, so run a short live coding round. Give ONE coding problem that real {s['role']} interviews commonly ask "
              f"(LeetCode easy/medium style; for data/analyst roles a data-processing problem), difficulty {diff}, solvable in about 10 minutes. "
              "No trick questions. It must be a stdin/stdout program: the candidate reads input from standard input and prints the answer. "
              "Return JSON: {\"spoken\": str (max 30 words, plain speech: state the task briefly and ask them to talk through "
              "their approach while coding), \"title\": str, \"problem\": str (max 80 words), \"input_format\": str, \"output_format\": str, "
              "\"examples\": [{\"input\": str (exact stdin), \"output\": str (exact stdout)}] (1-2), "
              "\"constraints\": str, \"language\": \"Python\"|\"JavaScript\"|\"C++\"|\"Java\" (best fit for this role)}")
    d = await ask_json(QUESTION_SYS, prompt)
    spoken = " ".join(clean(d.get("spoken", "")).split()[:40]) or f"Let's do a quick coding problem: {d.get('title', '')}. Talk me through your approach."
    return {"question": spoken, "reaction": "You're doing well, so let's try a quick coding round.", "kind": "coding", "stage": "coding",
            "difficulty": diff, "coding": {k: d.get(k) for k in ("title", "problem", "input_format", "output_format", "examples", "constraints", "language")}}


def trail(turns):
    groups = []
    for i, t in enumerate(turns):
        if not t.get("answer"):
            continue
        ev = t.get("evaluation", {})
        item = {"n": i + 1, "question": t["question"], "answer": t["answer"], "score": ev.get("score"), "feedback": ev.get("feedback", ""),
                "stage": t.get("stage"), "difficulty": t.get("difficulty"), "kind": t.get("kind", "new"), "code": t.get("code", "")}
        if item["kind"] == "follow_up" and groups:
            groups[-1]["follow_ups"].append(item)
        else:
            groups.append({**item, "follow_ups": []})
    for g in groups:
        g["depth"] = len(g["follow_ups"])
    return groups
