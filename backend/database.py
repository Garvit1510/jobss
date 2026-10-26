import os
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent / ".env")

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]


async def create_indexes():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.devices.create_index("device_id", unique=True)
    await db.bans.create_index("device_id")
    await db.bans.create_index("ip")
    await db.bans.create_index("id")
    await db.code_tests.create_index("key", unique=True)
    await db.bans.create_index("user_id")
    await db.login_attempts.create_index("identifier")
    await db.jobs.create_index("id", unique=True)
    await db.jobs.create_index([("source", 1), ("unit", 1)])
    await db.jobs.create_index("posted_at")
    await db.jobs.create_index("company")
    await db.jobs.create_index("countries")
    await db.jobs.create_index("first_seen_at")
    await db.job_alerts.create_index("user_id")
    await db.resumes.create_index("user_id")
    await db.experiences.create_index("company_key")
    await db.activity.create_index([("user_id", 1), ("created_at", -1)])
    await db.acc_mock_libraries.create_index("id", unique=True)
    await db.acc_mock_libraries.create_index("version", unique=True)
    await db.acc_mocks.create_index([("library_id", 1), ("mock_id", 1)], unique=True)
    await db.acc_mocks.create_index("id", unique=True)
    await db.acc_mock_access.create_index("mock_id", unique=True)
    await db.acc_attempts.create_index([("user_id", 1), ("mock_id", 1), ("round", 1), ("created_at", -1)])
    await db.acc_attempts.create_index("id", unique=True)
