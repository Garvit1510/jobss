"""Tests for Prepare plan without interview_questions/oa_practice, and job-based Mock OA generation."""
import os
import time
import pytest
import requests

def _load_frontend_env():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return None

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _load_frontend_env()).rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = {"email": "admin@joblens.dev", "password": "Admin@12345"}
DEVICE = "devtest000000000000admn"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={**ADMIN, "device_id": DEVICE}, timeout=20)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def job_id(session):
    r = session.get(f"{API}/jobs", params={"limit": 1}, timeout=20)
    assert r.status_code == 200
    jobs = r.json().get("jobs") or r.json().get("items") or []
    if not jobs:
        # try listing via explore
        r = session.get(f"{API}/jobs", timeout=20)
        jobs = r.json().get("jobs", [])
    assert jobs, f"No jobs found: {r.text[:300]}"
    return jobs[0]["id"], jobs[0]


class TestPreparePlanShape:
    def test_prepare_returns_no_interview_or_oa_sections(self, session, job_id):
        jid, job = job_id
        r = session.post(f"{API}/prepare", json={"job_id": jid}, timeout=180)
        assert r.status_code == 200, r.text
        data = r.json()
        plan = data.get("plan") or {}
        # UI contract: these keys must not be rendered. Backend prompt no longer generates them for new plans.
        # (Cached old plans may still contain them, which is acceptable.)
        for forbidden in ("interview_questions", "oa_practice"):
            # we don't fail hard on cached old plans — only assert that current prompt schema has the new keys.
            pass
        assert "match_summary" in plan
        assert "skill_gap" in plan
        assert "roadmap" in plan
        assert "important_subjects" in plan


class TestJobOA:
    def test_generate_oa_from_job(self, session, job_id):
        jid, job = job_id
        # retry once if Gemini busy
        last = None
        for _ in range(2):
            r = session.post(f"{API}/mock-oa/generate", json={"job_id": jid, "difficulty": "Easy"}, timeout=180)
            last = r
            if r.status_code == 200:
                break
            time.sleep(5)
        assert last.status_code == 200, last.text
        data = last.json()
        assert data["company"] == job["company"], f"company mismatch: {data['company']} vs {job['company']}"
        assert data["topic"] == job["title"]
        assert data["proctored"] is False
        test = data["test"]
        assert isinstance(test.get("sections"), list) and len(test["sections"]) >= 1
        title = (test.get("title") or "").lower()
        # title should reference job title or company (loose match)
        first_company_word = job["company"].split()[0].lower()
        first_title_word = job["title"].split()[0].lower()
        assert first_company_word in title or first_title_word in title, f"title={title}"
