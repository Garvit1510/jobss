import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

import auth
import routes_core
import routes_prep
import routes_alerts
import routes_admin
import routes_code
import routes_career
import routes_oa_builder
import routes_proctor_media
import routes_accenture
import accenture_games
import accenture_rounds
import accenture_behavioural
import accenture_proctor
import judges
import sandbox
from database import create_indexes, db
from jobs_service import migrate_jobs, refresh_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
app = FastAPI(title="JobLens AI")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in os.environ["FRONTEND_URL"].split(",") if o.strip()],
                   allow_origin_regex=os.environ.get("CORS_ORIGIN_REGEX") or None, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router)
app.include_router(routes_core.router)
app.include_router(routes_prep.router)
app.include_router(routes_alerts.router)
app.include_router(routes_admin.router)
app.include_router(routes_code.router)
app.include_router(routes_career.router)
app.include_router(routes_oa_builder.router)
app.include_router(routes_proctor_media.router)
app.include_router(routes_accenture.router)
app.include_router(accenture_games.router)
app.include_router(accenture_rounds.router)
app.include_router(accenture_behavioural.router)
app.include_router(accenture_proctor.router)


@app.get("/api/ai/status")
async def ai_status():
    import ai
    return ai.status()


@app.get("/api/health")
async def health():
    return {"ok": True, "jobs": await db.jobs.count_documents({})}


async def refresh_loop():
    hours = float(os.environ["JOBS_REFRESH_HOURS"])
    while True:
        meta = await db.meta.find_one({"key": "jobs_refresh"})
        last = datetime.fromisoformat(meta["at"]) if meta else None
        if not last or datetime.now(timezone.utc) - last > timedelta(hours=hours):
            await refresh_all()
            await routes_career.dedup_jobs()
        await asyncio.sleep(1800)


async def _sandbox_init():
    if os.name == "nt":
        logging.getLogger("sandbox").info("Code execution sandbox is unavailable on Windows.")
        return
    await judges.ensure_webjudge()
    await sandbox.init()


@app.on_event("startup")
async def startup():
    await create_indexes()
    await auth.seed_admin()
    await migrate_jobs()
    asyncio.create_task(routes_career.backfill())
    asyncio.create_task(refresh_loop())
    asyncio.create_task(_sandbox_init())
    await db.oa_companies.update_many({"import_status.status": "running"}, {"$set": {"import_status.status": "failed", "import_status.stage": "interrupted by a server restart"}})
    await db.oa_bank.create_index([("company_id", 1), ("section_id", 1)])
    await db.proctor_snaps.create_index([("ref_id", 1), ("at", 1)])
    await db.oa_bank.create_index([("company_id", 1), ("content_hash", 1)])
    await db.oa_bank_jobs.update_many({"status": "running"}, {"$set": {"status": "failed", "error": "Interrupted by a server restart"}})
