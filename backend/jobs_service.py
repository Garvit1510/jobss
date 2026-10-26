import asyncio
import hashlib
import html
import logging
import re
from datetime import datetime, timezone

import httpx
from pymongo import UpdateOne

from database import db
from skills import extract_skills
from careers import classify
from countries import detect_countries

log = logging.getLogger("jobs")
UA = {"User-Agent": "Mozilla/5.0 (JobLensAI job aggregator)"}
PER_COMPANY_CAP = 150

GREENHOUSE = ["stripe", "airbnb", "databricks", "figma", "discord", "robinhood", "coinbase", "dropbox", "reddit",
              "instacart", "gitlab", "cloudflare", "datadog", "asana", "duolingo", "pinterest", "lyft", "twilio",
              "mongodb", "elastic", "okta", "samsara", "groww", "vercel", "anthropic", "scaleai", "brex", "gusto",
              "affirm", "chime", "toast", "flexport", "webflow", "zscaler"]
LEVER = ["palantir", "spotify", "cred", "zeta", "meesho", "binance"]
ASHBY = ["notion", "openai", "ramp", "linear", "supabase", "posthog", "replit", "cursor", "perplexity", "elevenlabs",
         "zapier", "sardine"]
WORKABLE = ["huggingface"]
SMARTRECRUITERS = ["ServiceNow", "Wise", "Ubisoft2", "Canva", "Experian", "Freshworks"]
RECRUITEE = ["bunq", "personio"]

NAMES = {"openai": "OpenAI", "posthog": "PostHog", "elevenlabs": "ElevenLabs", "cred": "CRED", "zeta": "Zeta",
         "supabase": "Supabase", "replit": "Replit", "perplexity": "Perplexity", "cursor": "Cursor (Anysphere)",
         "huggingface": "Hugging Face", "Ubisoft2": "Ubisoft", "ServiceNow": "ServiceNow"}


def cname(slug):
    return NAMES.get(slug, slug[:1].upper() + slug[1:])


SOURCE_LABELS = {
    "greenhouse": "Greenhouse", "lever": "Lever", "ashby": "Ashby", "workable": "Workable",
    "smartrecruiters": "SmartRecruiters", "recruitee": "Recruitee", "remotive": "Remotive",
    "arbeitnow": "Arbeitnow", "remoteok": "RemoteOK", "himalayas": "Himalayas", "jobicy": "Jobicy", "themuse": "The Muse",
}

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")


def clean_html(raw: str) -> str:
    if not raw:
        return ""
    t = html.unescape(raw)
    t = re.sub(r"<\s*(br|/p|/li|/h\d|/div)\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"<\s*li[^>]*>", "\n• ", t, flags=re.I)
    t = html.unescape(_TAG_RE.sub("", t))
    t = _WS_RE.sub(" ", t)
    t = re.sub(r"\n\s*\n+", "\n\n", t)
    return t.strip()[:9000]


def infer_level(title: str, hint: str = "") -> str:
    s = f"{title} {hint}".lower()
    if re.search(r"intern|new grad|graduate|junior|\bjr\b|entry|trainee|apprentice|fresher|early career", s):
        return "Entry"
    if re.search(r"senior|\bsr\b|staff|principal|lead|head of|director|manager|\bvp\b|architect|expert", s):
        return "Senior"
    return "Mid"


def infer_work(location: str = "", remote=None, hybrid=None, text: str = "") -> str:
    if hybrid:
        return "Hybrid"
    if remote is True:
        return "Remote"
    s = f"{location} {text}".lower()
    if "hybrid" in s:
        return "Hybrid"
    if "remote" in s or "anywhere" in s:
        return "Remote"
    return "Onsite"


FX = {}
PERIOD_NORM = {"annual": "year", "yearly": "year", "annually": "year", "monthly": "month", "hourly": "hour", "weekly": "week", "daily": "day"}
PERIOD_MULT = {"year": 1, "month": 12, "week": 52, "day": 260, "hour": 2080}


async def load_fx(client):
    try:
        d = await get_json(client, "https://open.er-api.com/v6/latest/USD")
        FX.update(d.get("rates") or {})
    except Exception as e:
        log.warning("fx load failed: %s", e)


def make_salary(mn=None, mx=None, currency=None, period=None, text=None):
    try:
        mn = float(mn) if mn not in (None, "", 0, "0") else None
        mx = float(mx) if mx not in (None, "", 0, "0") else None
    except (TypeError, ValueError):
        mn = mx = None
    if mn is None and mx is None:
        text = (text or "").strip()
        return {"text": text} if text else None
    cur = (currency or "USD").upper()
    per = (period or "year").lower()
    per = PERIOD_NORM.get(per, per)
    usd = None
    rate = FX.get(cur)
    if rate:
        usd = round((mx or mn) / rate * PERIOD_MULT.get(per, 1))
    return {"min": mn, "max": mx, "currency": cur, "period": per, "usd_annual": usd}


def to_iso(v):
    if v is None or v == "":
        return None
    try:
        if isinstance(v, (int, float)):
            ts = v / 1000 if v > 1e11 else v
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    except Exception:
        try:
            return datetime.strptime(str(v)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc).isoformat()
        except Exception:
            return None


def build(source, unit, ext_id, title, company, location, description, apply_url, posted, work, level=None,
          salary=None, employment=None, tags=None):
    title = (title or "").strip()
    desc = description or ""
    skills = list(dict.fromkeys((tags or []) + extract_skills(f"{title}\n{desc}")))[:18]
    return {
        "id": hashlib.md5(f"{source}:{ext_id}".encode()).hexdigest()[:16],
        "source": source, "source_label": SOURCE_LABELS[source], "unit": unit, "external_id": str(ext_id),
        "title": title, "company": (company or "").strip(), "location": re.sub(r"(\s*,\s*)+", ", ", (location or "Not specified")).strip(" ,")[:120] or "Not specified",
        "countries": detect_countries(location or "", work),
        "work_type": work, "level": level or infer_level(title), "employment_type": employment,
        "description": desc, "skills": skills, "salary": salary, "apply_url": apply_url, "posted_at": to_iso(posted),
        "sector": classify(title, desc),
    }


def _norm_tags(tags):
    from skills import canonical, SKILLS
    out = []
    for t in tags or []:
        c = canonical(str(t))
        if c in SKILLS:
            out.append(c)
    return out


async def get_json(client, url, **kw):
    r = await client.get(url, **kw)
    r.raise_for_status()
    return r.json()


async def f_greenhouse(c, slug):
    d = await get_json(c, f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
                       params={"content": "true", "pay_transparency": "true"})
    out = []
    for j in d.get("jobs", [])[:PER_COMPANY_CAP]:
        loc = (j.get("location") or {}).get("name", "")
        desc = clean_html(j.get("content"))
        pr = (j.get("pay_input_ranges") or [None])[0]
        sal = make_salary(pr["min_cents"] / 100, pr["max_cents"] / 100, pr.get("currency_type"), "year") if pr and pr.get("min_cents") else None
        out.append(build("greenhouse", slug, j["id"], j.get("title"), j.get("company_name") or slug.title(), loc, desc,
                         j.get("absolute_url"), j.get("first_published") or j.get("updated_at"),
                         infer_work(loc, text=j.get("title", "")), salary=sal))
    return out


async def f_lever(c, slug):
    d = await get_json(c, f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"})
    out = []
    for j in d[:PER_COMPANY_CAP]:
        cat = j.get("categories") or {}
        loc = cat.get("location") or ""
        wt = j.get("workplaceType") or ""
        work = {"remote": "Remote", "hybrid": "Hybrid", "onsite": "Onsite", "on-site": "Onsite"}.get(wt.lower()) or infer_work(loc)
        lists = "\n".join(f"{l.get('text', '')}\n{clean_html(l.get('content', ''))}" for l in j.get("lists") or [])
        desc = f"{j.get('descriptionPlain') or ''}\n{lists}\n{j.get('additionalPlain') or ''}".strip()[:9000]
        sr = j.get("salaryRange") or {}
        sal = make_salary(sr.get("min"), sr.get("max"), sr.get("currency"), (sr.get("interval") or "year").replace("per-", ""))
        out.append(build("lever", slug, j["id"], j.get("text"), cname(slug), loc, desc, j.get("hostedUrl"),
                         j.get("createdAt"), work, employment=cat.get("commitment"), salary=sal))
    return out


async def f_ashby(c, slug):
    d = await get_json(c, f"https://api.ashbyhq.com/posting-api/job-board/{slug}", params={"includeCompensation": "true"})
    out = []
    for j in d.get("jobs", [])[:PER_COMPANY_CAP]:
        if j.get("isListed") is False:
            continue
        wt = (j.get("workplaceType") or "").lower()
        work = "Remote" if j.get("isRemote") or wt == "remote" else "Hybrid" if wt == "hybrid" else "Onsite"
        comp = j.get("compensation") or {}
        sal = None
        for comp_c in comp.get("summaryComponents") or []:
            if comp_c.get("compensationType") == "Salary":
                interval = (comp_c.get("interval") or "1 YEAR").lower()
                sal = make_salary(comp_c.get("minValue"), comp_c.get("maxValue"), comp_c.get("currencyCode"),
                                  "hour" if "hour" in interval else "month" if "month" in interval else "year")
                break
        if not sal and comp.get("compensationTierSummary"):
            sal = make_salary(text=comp["compensationTierSummary"])
        out.append(build("ashby", slug, j["id"], j.get("title"), cname(slug), j.get("location"),
                         (j.get("descriptionPlain") or "")[:9000], j.get("jobUrl"), j.get("publishedAt"), work,
                         employment=j.get("employmentType"), salary=sal))
    return out


async def f_workable(c, slug):
    d = await get_json(c, f"https://apply.workable.com/api/v1/widget/accounts/{slug}", params={"details": "true"})
    out = []
    for j in d.get("jobs", [])[:PER_COMPANY_CAP]:
        loc = ", ".join(x for x in [j.get("city"), j.get("country")] if x)
        out.append(build("workable", slug, j.get("shortcode"), j.get("title"), d.get("name") or slug.title(), loc,
                         clean_html(j.get("description") or ""), j.get("url"), j.get("published_on"),
                         "Remote" if j.get("telecommuting") else infer_work(loc), employment=j.get("employment_type"),
                         level=infer_level(j.get("title", ""), j.get("experience", ""))))
    return out


async def f_smartrecruiters(c, slug):
    d = await get_json(c, f"https://api.smartrecruiters.com/v1/companies/{slug}/postings", params={"limit": 100})
    out = []
    for j in d.get("content", [])[:PER_COMPANY_CAP]:
        l = j.get("location") or {}
        loc = l.get("fullLocation") or ", ".join(x for x in [l.get("city"), l.get("country", "").upper()] if x)
        work = "Remote" if l.get("remote") else "Hybrid" if l.get("hybrid") else infer_work(loc)
        comp = j.get("company") or {}
        job = build("smartrecruiters", slug, j["id"], j.get("name"), comp.get("name") or slug, loc, "",
                    f"https://jobs.smartrecruiters.com/{comp.get('identifier', slug)}/{j['id']}", j.get("releasedDate"),
                    work, level=infer_level(j.get("name", ""), (j.get("experienceLevel") or {}).get("label", "")),
                    employment=(j.get("typeOfEmployment") or {}).get("label"))
        job["detail_url"] = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{j['id']}"
        out.append(job)
    return out


async def f_recruitee(c, slug):
    d = await get_json(c, f"https://{slug}.recruitee.com/api/offers/")
    out = []
    for j in d.get("offers", [])[:PER_COMPANY_CAP]:
        s = j.get("salary") or {}
        desc = clean_html(f"{j.get('description', '')}<br>{j.get('requirements', '')}")
        out.append(build("recruitee", slug, j["id"], j.get("title"), j.get("company_name") or slug.title(),
                         j.get("location"), desc, j.get("careers_url"), j.get("published_at") or j.get("created_at"),
                         "Remote" if j.get("remote") else "Hybrid" if j.get("hybrid") else "Onsite",
                         level=infer_level(j.get("title", ""), j.get("experience_code") or ""),
                         salary=make_salary(s.get("min"), s.get("max"), s.get("currency"), s.get("period")),
                         employment=j.get("employment_type_code")))
    return out


async def f_remotive(c, _):
    d = await get_json(c, "https://remotive.com/api/remote-jobs")
    return [build("remotive", "all", j["id"], j.get("title"), j.get("company_name"),
                  j.get("candidate_required_location") or "Remote", clean_html(j.get("description")), j.get("url"),
                  j.get("publication_date"), "Remote", salary=make_salary(text=j.get("salary")),
                  employment=j.get("job_type"), tags=_norm_tags(j.get("tags"))) for j in d.get("jobs", [])]


async def f_arbeitnow(c, _):
    out = []
    for page in (1, 2, 3):
        d = await get_json(c, "https://www.arbeitnow.com/api/job-board-api", params={"page": page})
        for j in d.get("data", []):
            out.append(build("arbeitnow", "all", j["slug"], j.get("title"), j.get("company_name"), j.get("location"),
                             clean_html(j.get("description")), j.get("url"), j.get("created_at"),
                             "Remote" if j.get("remote") else infer_work(j.get("location", "")),
                             employment=", ".join(j.get("job_types") or []) or None, tags=_norm_tags(j.get("tags"))))
    return out


async def f_remoteok(c, _):
    d = await get_json(c, "https://remoteok.com/api")
    return [build("remoteok", "all", j["id"], j.get("position"), j.get("company"), j.get("location") or "Remote",
                  clean_html(j.get("description")), j.get("url") or j.get("apply_url"), j.get("date"), "Remote",
                  salary=make_salary(j.get("salary_min"), j.get("salary_max"), "USD", "year"),
                  tags=_norm_tags(j.get("tags"))) for j in d if isinstance(j, dict) and j.get("id")]


async def f_himalayas(c, _):
    out = []
    for offset in range(0, 200, 20):
        d = await get_json(c, "https://himalayas.app/jobs/api", params={"limit": 20, "offset": offset})
        for j in d.get("jobs", []):
            loc = ", ".join(j.get("locationRestrictions") or []) or "Remote (Global)"
            out.append(build("himalayas", "all", j.get("guid") or j.get("applicationLink"), j.get("title"),
                             j.get("companyName"), loc, clean_html(j.get("description")), j.get("applicationLink"),
                             j.get("pubDate"), "Remote", level=infer_level(j.get("title", ""), " ".join(j.get("seniority") or [])),
                             salary=make_salary(j.get("minSalary"), j.get("maxSalary"), j.get("currency"), j.get("salaryPeriod")),
                             employment=j.get("employmentType")))
        if not d.get("jobs"):
            break
    return out


async def f_jobicy(c, _):
    d = await get_json(c, "https://jobicy.com/api/v2/remote-jobs", params={"count": 100})
    return [build("jobicy", "all", j["id"], html.unescape(j.get("jobTitle", "")), j.get("companyName"),
                  j.get("jobGeo") or "Remote", clean_html(j.get("jobDescription")), j.get("url"), j.get("pubDate"),
                  "Remote", level=infer_level(j.get("jobTitle", ""), j.get("jobLevel", "")),
                  salary=make_salary(j.get("annualSalaryMin") or j.get("salaryMin"), j.get("annualSalaryMax") or j.get("salaryMax"),
                                     j.get("salaryCurrency"), j.get("salaryPeriod") or "year"),
                  employment=", ".join(j.get("jobType") or []) if isinstance(j.get("jobType"), list) else j.get("jobType"))
            for j in d.get("jobs", [])]


async def f_themuse(c, _):
    out = []
    for page in range(0, 10):
        d = await get_json(c, "https://www.themuse.com/api/public/jobs", params={"page": page})
        for j in d.get("results", []):
            loc = "; ".join(x.get("name", "") for x in j.get("locations") or []) or "Not specified"
            lv = " ".join(x.get("name", "") for x in j.get("levels") or [])
            out.append(build("themuse", "all", j["id"], j.get("name"), (j.get("company") or {}).get("name"), loc,
                             clean_html(j.get("contents")), (j.get("refs") or {}).get("landing_page"),
                             j.get("publication_date"), infer_work(loc), level=infer_level(j.get("name", ""), lv)))
    return out


UNITS = ([("greenhouse", s, f_greenhouse) for s in GREENHOUSE] + [("lever", s, f_lever) for s in LEVER]
         + [("ashby", s, f_ashby) for s in ASHBY] + [("workable", s, f_workable) for s in WORKABLE]
         + [("smartrecruiters", s, f_smartrecruiters) for s in SMARTRECRUITERS]
         + [("recruitee", s, f_recruitee) for s in RECRUITEE]
         + [(src, "all", fn) for src, fn in [("remotive", f_remotive), ("arbeitnow", f_arbeitnow), ("remoteok", f_remoteok),
                                             ("himalayas", f_himalayas), ("jobicy", f_jobicy), ("themuse", f_themuse)]])

_refreshing = False


async def refresh_all():
    global _refreshing
    if _refreshing:
        return
    _refreshing = True
    started = datetime.now(timezone.utc).isoformat()
    sem = asyncio.Semaphore(8)
    stats = {}
    try:
        async with httpx.AsyncClient(headers=UA, timeout=45, follow_redirects=True) as client:
            await load_fx(client)

            async def run(src, unit, fn):
                async with sem:
                    try:
                        jobs = [j for j in await fn(client, unit) if j["title"] and j["apply_url"]]
                    except Exception as e:
                        log.warning("source %s/%s failed: %s", src, unit, str(e)[:200])
                        stats.setdefault(src, {"jobs": 0, "errors": 0})["errors"] += 1
                        return
                    for j in jobs:
                        j["fetched_at"] = started
                    if jobs:
                        await db.jobs.bulk_write([UpdateOne({"id": j["id"]}, {"$set": j, "$setOnInsert": {"first_seen_at": started}}, upsert=True) for j in jobs], ordered=False)
                    await db.jobs.delete_many({"source": src, "unit": unit, "fetched_at": {"$lt": started}})
                    stats.setdefault(src, {"jobs": 0, "errors": 0})["jobs"] += len(jobs)
            await asyncio.gather(*(run(*u) for u in UNITS))
        await migrate_jobs()
        await db.meta.update_one({"key": "jobs_refresh"}, {"$set": {"key": "jobs_refresh", "at": started, "stats": stats}}, upsert=True)
        log.info("jobs refresh done: %s", stats)
    finally:
        _refreshing = False


async def migrate_jobs():
    await db.jobs.update_many({"first_seen_at": {"$exists": False}}, [{"$set": {"first_seen_at": "$fetched_at"}}])
    ops = [UpdateOne({"id": j["id"]}, {"$set": {"countries": detect_countries(j.get("location", ""), j.get("work_type", ""))}})
           async for j in db.jobs.find({"countries": {"$exists": False}}, {"_id": 0, "id": 1, "location": 1, "work_type": 1})]
    if ops:
        await db.jobs.bulk_write(ops, ordered=False)


async def enrich_job(job: dict) -> dict:
    if job.get("description") or not job.get("detail_url"):
        return job
    try:
        async with httpx.AsyncClient(headers=UA, timeout=20) as c:
            d = await get_json(c, job["detail_url"])
        secs = ((d.get("jobAd") or {}).get("sections") or {})
        desc = clean_html("<br>".join(f"<b>{v.get('title', '')}</b><br>{v.get('text', '')}" for v in secs.values() if v.get("text")))
        skills = list(dict.fromkeys(job.get("skills", []) + extract_skills(f"{job['title']}\n{desc}")))[:18]
        await db.jobs.update_one({"id": job["id"]}, {"$set": {"description": desc, "skills": skills}})
        job.update(description=desc, skills=skills)
    except Exception as e:
        log.warning("enrich failed %s: %s", job["id"], e)
    return job


def match_score(user_skills: set, roles: list, job: dict):
    if not user_skills:
        return None
    js = {s.lower() for s in job.get("skills", [])}
    title = job.get("title", "").lower()
    role_hit = any(w in title for r in roles for w in r.lower().split() if len(w) > 3 and w not in GENERIC)
    if not js:
        return 20 + (15 if role_hit else 0)
    overlap = len(js & user_skills) / max(len(js), 5)
    return int(min(97, round(15 + 70 * overlap + (12 if role_hit else 0))))


GENERIC = {"engineer", "developer", "intern", "junior", "senior", "lead", "associate", "development", "specialist",
           "trainee", "staff", "principal", "level", "entry", "graduate", "analyst", "manager", "consultant"}
