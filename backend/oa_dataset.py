import asyncio
import hashlib
import io
import logging
import re
import uuid
from datetime import datetime, timezone

import pdfplumber
from fastapi import HTTPException

import code_runner as cr
import routes_code
from ai import ask_structured
from database import db
from resume_parser import extract_text

log = logging.getLogger("oa_dataset")
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
MAX_PAGES = 400
PROGRAMMING = ("coding", "sql", "web")
KIND_OF = {"mcq": "objective", "numeric": "objective", "written": "written", "coding": "coding", "sql": "sql", "web": "web", "pattern_note": None}
_ocr_sem = asyncio.Semaphore(3)
_import_tasks = {}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ---------- reading files into pages (text layer + OCR for image-based pages) ----------

OCR_SCHEMA = {"type": "object", "properties": {"text": {"type": "string"}, "uncertain": {"type": "boolean"}, "notes": {"type": "string"}},
              "required": ["text", "uncertain"]}
OCR_SYS = ("You are an OCR engine for online-assessment screenshots. Transcribe ALL visible text exactly as written: question wording, options "
           "(keep their letters/numbers), code (preserve indentation and line breaks), tables, examples, constraints. Never paraphrase, "
           "summarise, solve or add anything. Mark unreadable fragments as [illegible]. Set uncertain=true if any part was hard to read.")


async def ocr_image(data, mime):
    async with _ocr_sem:
        r = await ask_structured(OCR_SYS, "Transcribe this page verbatim.", OCR_SCHEMA, images=[(data, mime)])
    return (r.get("text") or "").strip(), bool(r.get("uncertain")), r.get("notes", "")


def _render(data, idx):
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(data)
    try:
        img = pdf[idx].render(scale=2).to_pil()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    finally:
        pdf.close()


def _scan_pdf(fname, data):
    out = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for i, p in enumerate(pdf.pages[:MAX_PAGES]):
            area = float(p.width * p.height) or 1
            img_area = sum(abs((im.get("x1", 0) - im.get("x0", 0)) * (im.get("bottom", 0) - im.get("top", 0))) for im in p.images)
            text = (p.extract_text() or "").strip()
            out.append({"file": fname, "page": i + 1, "text": text, "method": "text", "uncertain": False, "error": "",
                        "needs_ocr": len(text) < 80 or img_area / area > 0.3})
    return out


async def read_pages(fname, data):
    """Fast pass inside the upload request: text layer only. Image pages are flagged needs_ocr and OCR'd by the import job."""
    name = fname.lower()
    if name.endswith(".pdf"):
        return await asyncio.to_thread(_scan_pdf, fname, data)
    if name.endswith(IMG_EXT):
        return [{"file": fname, "page": 1, "text": "", "method": "text", "uncertain": False, "error": "", "needs_ocr": True}]
    body = extract_text(name, data) if name.endswith(".docx") else data.decode("utf-8", errors="ignore")
    return [{"file": fname, "page": 1, "text": body.strip(), "method": "text", "uncertain": False, "error": "", "needs_ocr": False}]


async def ocr_page(page, raw):
    data = raw.get(page["file"])
    if data is None:
        page.update(needs_ocr=False, method="text" if page["text"] else "failed", error="Original file is no longer in memory; re-upload it to OCR this page.")
        return page
    name = page["file"].lower()
    try:
        if name.endswith(".pdf"):
            img, mime = await asyncio.to_thread(_render, data, page["page"] - 1), "image/png"
        else:
            img, mime = data, MIME[name[name.rfind("."):]]
        o, unc, _ = await ocr_image(img, mime)
        t = page["text"]
        page.update(text=(t + "\n[OCR of page image]\n" + o).strip() if t else o, method="text+ocr" if t else "ocr", uncertain=unc, error="")
    except Exception as e:
        page.update(method="text" if page["text"] else "failed", error=f"OCR failed: {getattr(e, 'detail', None) or str(e)[:150]}")
    page["needs_ocr"] = False
    return page


def pages_from_text(text):
    """Legacy datasets only kept the flat text: split it back into files/pages using '### FILE:' and 'Page N' footers."""
    pages = []
    for block in re.split(r"(?m)^### (?=FILE: |PASTED NOTES)", text):
        if not block.strip():
            continue
        head, _, body = block.partition("\n")
        fname = head.replace("FILE:", "").strip() or "Pasted text"
        parts = re.split(r"(?im)^.*\bPage (\d+)\s*$", body)
        chunks = [(parts[0], int(parts[1]) if len(parts) > 1 else 1)] + [(parts[k + 1], int(parts[k]) + 1) for k in range(1, len(parts) - 1, 2)]
        for t, n in chunks:
            if t.strip():
                pages.append({"file": fname, "page": n, "text": t.strip(), "method": "text", "uncertain": False, "error": ""})
    return pages


# ---------- structured extraction (verbatim) ----------

EXTRACT_SCHEMA = {"type": "object", "required": ["questions"], "properties": {"questions": {"type": "array", "items": {
    "type": "object", "required": ["source_ref", "question_type", "question_text", "completeness"],
    "properties": {
        "source_ref": {"type": "string"}, "source_page": {"type": "integer"},
        "question_type": {"type": "string", "enum": ["mcq", "numeric", "coding", "sql", "web", "written", "pattern_note"]},
        "section_hint": {"type": "string"}, "topic": {"type": "string"}, "difficulty": {"type": "string", "enum": ["Easy", "Medium", "Hard", "Unknown"]},
        "title": {"type": "string"}, "question_text": {"type": "string"}, "options": {"type": "array", "items": {"type": "string"}},
        "correct_answer": {"type": "string"}, "answer_in_source": {"type": "boolean"}, "explanation": {"type": "string"},
        "code_snippet": {"type": "string"}, "starter_html": {"type": "string"}, "starter_css": {"type": "string"}, "starter_js": {"type": "string"},
        "sql_schema": {"type": "string"}, "input_format": {"type": "string"}, "output_format": {"type": "string"}, "constraints": {"type": "string"},
        "examples": {"type": "array", "items": {"type": "object", "properties": {"input": {"type": "string"}, "output": {"type": "string"}}}},
        "completeness": {"type": "string", "enum": ["complete", "partial", "incomplete"]},
        "ocr_uncertain": {"type": "boolean"}, "duplicate_of_ref": {"type": "string"}, "source_notes": {"type": "string"}}}}}}

EXTRACT_SYS = """You convert a company online-assessment dataset into structured question records. You are a transcriber, not an author.
- Copy question wording, options, code, examples and constraints EXACTLY as in the source (fix only OCR line-break artefacts). Never paraphrase or improve.
- Never invent an answer key, schema, test case, constraint or starter code. correct_answer only if the source states it (answer_in_source=true).
- question_type: mcq (has options), numeric (single number answer), coding (DSA/program), sql (SQL query task), web (HTML/CSS/JS task),
  written (free text), pattern_note (pattern/structure notes or recollections that are not a question).
- completeness: complete = solvable exactly as given; partial = solvable with small reasonable assumptions; incomplete = key details missing.
- If the source says an item duplicates another, set duplicate_of_ref to that item's reference.
- source_ref: the item's id in the source (e.g. FE-01) or "p<page>-q<n>". source_page from the [[PAGE n]] markers.
- Put any dataset notes about the item in source_notes. Set ocr_uncertain=true for text marked [illegible] or [OCR] content you are unsure of."""


def _chunks(pages, size=4500):
    out, cur = [], ""
    for p in pages:
        piece = f"[[PAGE {p['page']} · {p['file']}]]\n{p['text']}\n"
        if cur and len(cur) + len(piece) > size:
            out.append(cur)
            cur = ""
        cur += piece[:size]
    return out + ([cur] if cur else [])


def content_hash(kind, text, options=()):
    norm = re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()[:800] + "|" + "|".join(re.sub(r"\s+", " ", o.lower()).strip() for o in options or [])
    return hashlib.sha1(f"{kind}|{norm}".encode()).hexdigest()


def _answer_index(q):
    opts, ans = q.get("options") or [], (q.get("correct_answer") or "").strip()
    if not ans:
        return None
    m = re.match(r"^\(?([A-Ha-h])[\).:\s]*$", ans) or re.match(r"^(?:option\s*)?\(?([A-Ha-h])\)?[\).:]\s", ans + " ", re.I)
    if m and ord(m.group(1).upper()) - 65 < len(opts):
        return ord(m.group(1).upper()) - 65
    low = re.sub(r"^\(?[a-h][\).:]\s*", "", ans.lower()).strip()
    for i, o in enumerate(opts):
        if re.sub(r"^\(?[a-h][\).:]\s*", "", o.lower()).strip() == low:
            return i
    return None


def normalise(q, company, dataset):
    """Source record -> bank document (original, unchanged wording). Returns None for unusable records."""
    qt = q.get("question_type")
    kind = KIND_OF.get(qt)
    text = (q.get("question_text") or "").strip()
    if not text:
        return None
    meta = {"id": str(uuid.uuid4()), "company_id": company["id"], "company": company["name"], "source": "dataset", "source_dataset": dataset,
            "source_page": q.get("source_page"), "source_ref": q.get("source_ref", ""), "question_type": qt, "kind": kind or "pattern",
            "topic": q.get("topic", ""), "difficulty": q.get("difficulty") if q.get("difficulty") in ("Easy", "Medium", "Hard") else "",
            "section_hint": q.get("section_hint", ""), "is_original": True, "parent_question_id": None, "variant_type": None,
            "answer_verified": False, "harness": None, "ocr_uncertain": bool(q.get("ocr_uncertain")), "completeness": q.get("completeness", "partial"),
            "source_notes": q.get("source_notes", ""), "selected": False, "review_notes": [], "created_at": now_iso(), "section_id": None,
            "raw": {k: v for k, v in q.items() if v not in ("", None, [], False)}}
    title = q.get("title") or text[:70]
    code = q.get("code_snippet", "").strip()
    if kind == "objective":
        if qt == "mcq":
            idx = _answer_index(q)
            data = {"type": "mcq", "question": text + (f"\n\n{code}" if code else ""), "options": q.get("options") or [], "explanation": q.get("explanation", "")}
            if idx is not None:
                data["answer_index"] = idx
            meta["answer_verified"] = idx is not None and bool(q.get("answer_in_source"))
        else:
            try:
                ans = float(re.sub(r"[^0-9.\-]", "", q.get("correct_answer") or ""))
            except ValueError:
                ans = None
            data = {"type": "numeric", "question": text, "tolerance": 0.01, "unit": "", "explanation": q.get("explanation", "")}
            if ans is not None:
                data["answer"] = ans
            meta["answer_verified"] = ans is not None and bool(q.get("answer_in_source"))
    elif kind == "written":
        data = {"type": "written", "question": text, "rubric": q.get("explanation") or "Judge against the original prompt.", "explanation": q.get("explanation", "")}
    elif kind in PROGRAMMING:
        data = {"title": title, "difficulty": meta["difficulty"], "problem": text + (f"\n\n{code}" if code and kind != "web" else ""),
                "input_format": q.get("input_format", ""), "output_format": q.get("output_format", ""), "constraints": q.get("constraints", ""),
                "examples": [e for e in q.get("examples") or [] if e.get("input") or e.get("output")]}
        if kind == "sql":
            data["schema"] = q.get("sql_schema", "")
        if kind == "web":
            data["starter"] = {"html": q.get("starter_html", ""), "css": q.get("starter_css", ""), "js": q.get("starter_js", "")}
            data["source_code"] = code
    else:
        data = {"type": "pattern_note", "question": text, "title": title}
    meta["data"] = data
    meta["content_hash"] = content_hash(meta["kind"], text, data.get("options"))
    meta["status"], notes = status_of(meta)
    meta["review_notes"] = notes
    return meta


def status_of(d):
    """ready = can be served and graded honestly; needs_review = admin must check; incomplete = source lacks key details."""
    k, data, notes = d["kind"], d["data"], []
    if d.get("ocr_uncertain"):
        notes.append("OCR text uncertain: compare with the original page.")
    if k == "pattern":
        return "incomplete", ["Pattern note, not a question. Used only as context for related questions."]
    if d.get("completeness") == "incomplete":
        return "incomplete", notes + ["The source is missing key details."]
    if k == "objective":
        if data["type"] == "mcq" and (len(data.get("options") or []) < 2):
            return "incomplete", notes + ["Options are missing in the source."]
        has = "answer_index" in data if data["type"] == "mcq" else "answer" in data
        if not has:
            return "needs_review", notes + ["No answer key in the source. Add and verify the correct answer."]
        if not d.get("answer_verified"):
            return "needs_review", notes + ["Answer key not verified."]
    if k == "coding" and not data.get("tests"):
        return "needs_review", notes + ["No judge test cases yet."]
    if k == "sql" and not data.get("tests"):
        return ("incomplete" if not data.get("schema") else "needs_review"), notes + (["The source has no table schema; it can only seed variants."] if not data.get("schema") else ["Datasets/expected results not built yet."])
    if k == "web" and not data.get("tests"):
        return "needs_review", notes + ["No DOM test cases yet."]
    if d.get("ocr_uncertain"):
        return "needs_review", notes
    return "ready", notes


# ---------- enrichment: judge harness for programming originals (question text stays verbatim) ----------

STARTER_SCHEMA = {"type": "object", "properties": {k: {"type": "string"} for k in ("python", "java", "cpp", "javascript")}, "required": ["python", "java", "cpp", "javascript"]}
LANG_KEYS = {"python": "Python", "java": "Java", "cpp": "C++", "javascript": "JavaScript"}


async def starter_code(p):
    """Problem-specific boilerplate: reads stdin in the stated format and calls an empty solve() stub. Compiled before use."""
    try:
        r = await ask_structured("You write starter code (boilerplate) for coding-assessment problems. Never include the solution logic.",
                                 f"{routes_code._problem_text(p)}\nSTDIN FORMAT: {p.get('io_note') or p.get('input_format')}\n"
                                 "For each language write a complete program that: reads the input exactly in the stdin format, calls a function "
                                 "with a meaningful name and typed parameters (e.g. solve(n, arr)) whose body is a TODO returning a default value, and prints "
                                 "the result in the output format. Java must use 'public class Main'. Keep each under 40 lines.", STARTER_SCHEMA)
    except HTTPException:
        return {}
    out = {}
    for k, lang in LANG_KEYS.items():
        code = (r.get(k) or "").strip()
        if len(code) < 30:
            continue
        async with cr.Program(lang, code + "\n") as prog:
            if not await prog.compile():
                out[lang] = code + "\n"
    return out


async def enrich(d):
    from routes_oa_builder import _valid_sql, _valid_web, SQL_RULES, WEB_RULES
    k, data = d["kind"], d["data"]
    if d["status"] == "incomplete" or k not in PROGRAMMING:
        return d
    try:
        if k == "coding":
            built = await routes_code.build_tests(data)
            data.update(tests=built["tests"], io_note=built.get("io_note", ""))
            data["starter_code"] = await starter_code(data)
            d["harness"] = "generated"
        elif k == "sql" and data.get("schema"):
            spec = await ask_structured("You build judge datasets for SQL assessment questions. Keep the given schema and task unchanged.",
                                        f"TASK: {data['problem']}\nSCHEMA:\n{data['schema']}\n{SQL_RULES}\nWrite 3 INSERT scripts (sample, edge, larger) for this exact schema "
                                        "and one correct reference SELECT.", {"type": "object", "required": ["datasets", "reference", "ordered"], "properties": {
                                            "datasets": {"type": "array", "items": {"type": "string"}}, "reference": {"type": "string"}, "ordered": {"type": "boolean"}}})
            v = await _valid_sql({**data, **spec})
            if v:
                data.update(tests=v["tests"], reference=v["reference"], ordered=v["ordered"])
                d["harness"] = "generated"
        elif k == "web":
            st = data.get("starter") or {}
            spec = await ask_structured("You build judge harnesses for front-end assessment tasks. The task wording is fixed; never change it.",
                                        f"TASK (verbatim): {data['problem']}\nSOURCE CODE SHOWN: {data.get('source_code') or '(none)'}\n"
                                        f"GIVEN STARTER: {st if any(st.values()) else '(none: write a minimal starter with the elements the task mentions, NOT solving it)'}\n{WEB_RULES}\n"
                                        "Return the starter, a complete reference solution and 5-8 DOM tests that check exactly what the task asks.",
                                        {"type": "object", "required": ["starter", "reference", "tests"], "properties": {
                                            "starter": {"type": "object", "properties": {"html": {"type": "string"}, "css": {"type": "string"}, "js": {"type": "string"}}},
                                            "reference": {"type": "object", "properties": {"html": {"type": "string"}, "css": {"type": "string"}, "js": {"type": "string"}}},
                                            "tests": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "why": {"type": "string"}, "script": {"type": "string"}}}}}})
            if any(st.values()):
                spec["starter"] = st
            v = await _valid_web({**data, **spec})
            if v:
                data.update(starter=v["starter"], reference=v["reference"], tests=v["tests"])
                d["harness"] = "generated"
    except Exception as e:
        d["review_notes"] = d.get("review_notes", []) + [f"Harness build failed: {getattr(e, 'detail', None) or str(e)[:150]}"]
    d["status"], notes = status_of(d)
    d["review_notes"] = list(dict.fromkeys([n for n in d.get("review_notes", []) if n.startswith("Harness")] + notes))
    return d


# ---------- section mapping ----------

def _words(s):
    return set(re.findall(r"[a-z]{3,}", (s or "").lower()))


def map_section(item, sections):
    k = item.get("kind")
    cands = [s for s in sections if s["kind"] == k]
    if not cands and k in PROGRAMMING:
        cands = [s for s in sections if s["kind"] in PROGRAMMING]
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0]["id"]
    w = _words(f"{item.get('section_hint', '')} {item.get('topic', '')}")
    return max(cands, key=lambda s: len(w & _words(f"{s['name']} {s.get('topics', '')}")))["id"]


async def remap(company_id, sections):
    ids = {s["id"] for s in sections}
    async for d in db.oa_bank.find({"company_id": company_id}, {"_id": 0, "id": 1, "kind": 1, "section_id": 1, "section_hint": 1, "topic": 1, "is_original": 1}):
        if d.get("section_id") in ids and not d.get("is_original"):
            continue
        sid = map_section(d, sections) if d.get("is_original") or d.get("section_id") not in ids else d["section_id"]
        if sid != d.get("section_id"):
            await db.oa_bank.update_one({"id": d["id"]}, {"$set": {"section_id": sid}})


# ---------- import job ----------

async def _set(cid, **kv):
    await db.oa_companies.update_one({"id": cid}, {"$set": {f"import_status.{k}": v for k, v in kv.items()}})


async def _ocr_pending(c, pages, raw):
    todo = [p for p in pages if p.get("needs_ocr")]
    if not todo:
        return pages
    await _set(c["id"], stage=f"OCR on {len(todo)} image page(s)")
    await asyncio.gather(*[ocr_page(p, raw) for p in todo])
    text = "\n\n".join(f"### FILE: {f}\n" + "\n".join(p["text"] for p in pages if p["file"] == f) for f in dict.fromkeys(p["file"] for p in pages))
    await db.oa_companies.update_one({"id": c["id"]}, {"$set": {"pages": pages, "dataset_text": text[:300_000], "chars": min(len(text), 300_000)}})
    return pages


async def run_import(cid, raw=None):
    c = await db.oa_companies.find_one({"id": cid}, {"_id": 0})
    pages = c.get("pages") or pages_from_text(c.get("dataset_text", ""))
    sections = (c.get("blueprint") or {}).get("sections", [])
    st = {"status": "running", "started_at": now_iso(), "finished_at": None, "pages_total": len(pages),
          "pages_ocr": sum(p["method"] != "text" for p in pages), "pages_failed": sum(p["method"] == "failed" for p in pages),
          "page_errors": [f"{p['file']} p{p['page']}: {p['error']}" for p in pages if p.get("error")][:20],
          "extracted": 0, "imported": 0, "duplicates": 0, "rejected": 0, "ready": 0, "needs_review": 0, "incomplete": 0, "errors": [], "stage": "extracting"}
    await db.oa_companies.update_one({"id": cid}, {"$set": {"import_status": st}})
    try:
        pages = await _ocr_pending(c, pages, raw or {})
        st.update(pages_ocr=sum(p["method"] != "text" for p in pages), pages_failed=sum(p["method"] == "failed" for p in pages),
                  page_errors=[f"{p['file']} p{p['page']}: {p['error']}" for p in pages if p.get("error")][:20], stage="extracting questions")
        await _set(cid, **{k: st[k] for k in ("pages_ocr", "pages_failed", "page_errors", "stage")})
        chunks = _chunks([p for p in pages if p["text"]])
        results = await asyncio.gather(*[ask_structured(EXTRACT_SYS, f"Company: {c['name']}\nDATASET PAGES:\n{ch}\nExtract every question and pattern note.", EXTRACT_SCHEMA)
                                         for ch in chunks], return_exceptions=True)
        raw = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                st["errors"].append(f"Chunk {i + 1}: extraction failed ({getattr(r, 'detail', None) or str(r)[:120]})")
            else:
                raw += r.get("questions", [])
        st["extracted"] = len(raw)
        known = {d["content_hash"] async for d in db.oa_bank.find({"company_id": cid, "is_original": True}, {"_id": 0, "content_hash": 1})}
        docs = []
        for q in raw:
            if q.get("duplicate_of_ref"):
                st["duplicates"] += 1
                continue
            d = normalise(q, c, next((p["file"] for p in pages if p["page"] == q.get("source_page")), pages[0]["file"] if pages else "dataset"))
            if not d:
                st["rejected"] += 1
                continue
            if d["content_hash"] in known:
                st["duplicates"] += 1
                continue
            known.add(d["content_hash"])
            d["section_id"] = map_section(d, sections)
            docs.append(d)
        st["stage"] = "building test harnesses"
        await _set(cid, **{k: st[k] for k in ("extracted", "duplicates", "rejected", "errors", "stage")})
        sem = asyncio.Semaphore(3)

        async def one(d):
            async with sem:
                d = await enrich(d)
            await db.oa_bank.insert_one({**d})
            st["imported"] += 1
            st[d["status"]] += 1
            await _set(cid, imported=st["imported"], ready=st["ready"], needs_review=st["needs_review"], incomplete=st["incomplete"])
        await asyncio.gather(*[one(d) for d in docs])
        st.update(status="done", stage="done")
    except Exception as e:
        log.exception("Dataset import failed for %s", cid)
        st["errors"].append(getattr(e, "detail", None) or str(e)[:200])
        st.update(status="failed", stage="failed")
    st["finished_at"] = now_iso()
    log.info("Dataset import %s: %s", c["name"], {k: st[k] for k in ("pages_total", "pages_ocr", "pages_failed", "extracted", "imported", "duplicates", "rejected", "ready", "needs_review", "incomplete")})
    await db.oa_companies.update_one({"id": cid}, {"$set": {"import_status": st}})
    _import_tasks.pop(cid, None)


def start_import(cid, raw=None):
    if cid in _import_tasks:
        raise HTTPException(409, "An import is already running for this company.")
    _import_tasks[cid] = asyncio.create_task(run_import(cid, raw))
