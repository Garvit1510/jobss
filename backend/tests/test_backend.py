"""Backend tests for JobLens AI.

Covers: health, auth (register/login/me/validation/brute-force), jobs listing,
dashboard, job detail, resume state for the pre-seeded test1 user.

NOTE: The destructive ban-flow test is NOT run here; it bans the IP.
See /app/backend/tests/ban_flow.sh — run at the VERY END manually.
"""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://career-lens-ai-3.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

TEST_EMAIL = "test1@joblens.dev"
TEST_PASSWORD = "Test@12345"


# ---------------- Fixtures ----------------
@pytest.fixture(scope="module")
def unauth_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_client():
    """Login as the pre-seeded test user. Uses a NEW device_id so we don't
    permanently replace the existing session for the browser-based tests.

    NOTE: Login with a new device_id invalidates any prior session for that
    account (single-active-session rule) — this is expected and does not harm
    subsequent frontend testing because the frontend re-logs-in with its own
    device_id.
    """
    s = requests.Session()
    device_id = "pytestdev" + uuid.uuid4().hex[:16]
    r = s.post(f"{API}/auth/login",
               json={"email": TEST_EMAIL, "password": TEST_PASSWORD, "device_id": device_id},
               timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Login failed {r.status_code}: {r.text}")
    return s


# ---------------- Health ----------------
class TestHealth:
    def test_health(self, unauth_client):
        r = unauth_client.get(f"{API}/health", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert isinstance(d["jobs"], int) and d["jobs"] > 1000, f"Expected many jobs, got {d['jobs']}"


# ---------------- Auth: validation & protection ----------------
class TestAuthValidation:
    def test_register_short_password_422(self, unauth_client):
        r = unauth_client.post(f"{API}/auth/register", json={
            "name": "Bad", "email": f"TEST_short_{uuid.uuid4().hex[:6]}@ex.com",
            "password": "short", "device_id": "x" * 20})
        assert r.status_code == 422, r.text

    def test_register_duplicate_email_400(self, unauth_client):
        # Known duplicate — the pre-seeded user. Use a FAKE device_id that
        # does NOT exist so we hit the duplicate-email branch BEFORE the
        # multi-account/ban branch. (Device existence is checked after email.)
        r = unauth_client.post(f"{API}/auth/register", json={
            "name": "Dup", "email": TEST_EMAIL, "password": "Password123!",
            "device_id": "dupcheckdevice" + uuid.uuid4().hex[:8]})
        assert r.status_code == 400, r.text
        assert "exists" in r.text.lower() or "already" in r.text.lower()

    def test_me_without_cookie_401(self, unauth_client):
        r = requests.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 401

    def test_dashboard_without_cookie_401(self):
        r = requests.get(f"{API}/dashboard", timeout=10)
        assert r.status_code == 401

    def test_jobs_without_cookie_401(self):
        r = requests.get(f"{API}/jobs", timeout=10)
        assert r.status_code == 401

    def test_login_invalid_password_401(self, unauth_client):
        # Use a NEW IP-local identifier? We can't change IP, but 5 wrong
        # attempts triggers lockout for ident = ip:email. Use a non-existent
        # email so we don't lock out the real test user.
        r = unauth_client.post(f"{API}/auth/login", json={
            "email": f"nouser_{uuid.uuid4().hex[:6]}@ex.com", "password": "wrongpass123",
            "device_id": "loginbaddev" + uuid.uuid4().hex[:10]})
        assert r.status_code == 401

    def test_brute_force_lockout(self, unauth_client):
        """Make 5 failed attempts with an email tied to a unique random IP?
        We can't change IP, so this will also lock future tests for that
        email. Use a RANDOM email so no real user is affected."""
        email = f"brute_{uuid.uuid4().hex[:8]}@ex.com"
        last = None
        for i in range(6):
            last = unauth_client.post(f"{API}/auth/login", json={
                "email": email, "password": "wrong",
                "device_id": "brutedev" + uuid.uuid4().hex[:10]})
        # 6th should be 429 (locked) or 401 if logic differs
        assert last.status_code in (429, 401)
        # Verify 429 at least once after threshold
        r = unauth_client.post(f"{API}/auth/login", json={
            "email": email, "password": "wrong", "device_id": "brutedev" + uuid.uuid4().hex[:10]})
        assert r.status_code == 429, f"Expected 429 lockout, got {r.status_code}: {r.text}"


# ---------------- Auth: logged-in flows ----------------
class TestAuthLoggedIn:
    def test_me(self, auth_client):
        r = auth_client.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["email"] == TEST_EMAIL
        assert "id" in d and "name" in d

    def test_session_replaced(self, auth_client):
        """Log the same user in from ANOTHER device → old auth_client should
        start getting 401 SESSION_REPLACED."""
        s2 = requests.Session()
        new_dev = "replacedev" + uuid.uuid4().hex[:16]
        r = s2.post(f"{API}/auth/login",
                    json={"email": TEST_EMAIL, "password": TEST_PASSWORD, "device_id": new_dev},
                    timeout=15)
        assert r.status_code == 200
        time.sleep(1)
        r2 = auth_client.get(f"{API}/auth/me", timeout=10)
        assert r2.status_code == 401, f"Old session should be invalidated, got {r2.status_code}"
        assert "SESSION_REPLACED" in r2.text or "session" in r2.text.lower()
        # Re-login the module auth_client so remaining tests can run
        dev = "pytestrelog" + uuid.uuid4().hex[:16]
        r3 = auth_client.post(f"{API}/auth/login",
                              json={"email": TEST_EMAIL, "password": TEST_PASSWORD, "device_id": dev},
                              timeout=15)
        assert r3.status_code == 200


# ---------------- Core endpoints ----------------
class TestCore:
    def test_dashboard_has_resume(self, auth_client):
        r = auth_client.get(f"{API}/dashboard", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["user"]["email"] == TEST_EMAIL
        assert d["resume"] is not None, "Pre-seeded user should have a resume"
        assert isinstance(d["resume"].get("score"), int)
        assert d["stats"]["total_jobs"] > 1000
        # Should match some jobs if resume has skills
        assert isinstance(d["stats"]["jobs_matched"], int)

    def test_jobs_list(self, auth_client):
        r = auth_client.get(f"{API}/jobs?limit=24&page=1&sort=best", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["total"] > 1000
        assert len(d["jobs"]) == 24
        job = d["jobs"][0]
        for k in ("id", "title", "company", "source"):
            assert k in job, f"Missing {k} in job"
        assert "_id" not in job

    def test_jobs_search_and_filters(self, auth_client):
        r = auth_client.get(f"{API}/jobs?q=engineer&work=Remote&limit=12", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d["jobs"], list)
        for j in d["jobs"][:5]:
            # Can't guarantee title match (search is broader) but work_type should match
            assert j.get("work_type") == "Remote" or j.get("work_type") is None

    def test_jobs_sources(self, auth_client):
        r = auth_client.get(f"{API}/jobs/sources", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert len(d["sources"]) == 12
        assert d["total"] > 1000

    def test_job_detail(self, auth_client):
        r = auth_client.get(f"{API}/jobs?limit=1", timeout=30)
        job_id = r.json()["jobs"][0]["id"]
        r2 = auth_client.get(f"{API}/jobs/{job_id}", timeout=30)
        assert r2.status_code == 200
        d = r2.json()
        assert d["id"] == job_id
        assert "url" in d or "apply_url" in d or d.get("source")
        assert "_id" not in d
        assert isinstance(d.get("skills_have"), list)

    def test_job_detail_404(self, auth_client):
        r = auth_client.get(f"{API}/jobs/does-not-exist-{uuid.uuid4().hex}", timeout=10)
        assert r.status_code == 404

    def test_resume_get(self, auth_client):
        r = auth_client.get(f"{API}/resume", timeout=10)
        assert r.status_code == 200
        assert r.json()["resume"] is not None

    def test_mock_oa_history(self, auth_client):
        r = auth_client.get(f"{API}/mock-oa/history", timeout=10)
        assert r.status_code == 200

    def test_interview_history(self, auth_client):
        r = auth_client.get(f"{API}/interview/history", timeout=10)
        assert r.status_code == 200

    def test_experiences_empty_or_list(self, auth_client):
        # Use first job for experiences
        r = auth_client.get(f"{API}/jobs?limit=1", timeout=20)
        job = r.json()["jobs"][0]
        r2 = auth_client.get(f"{API}/experiences?company={job['company']}", timeout=10)
        assert r2.status_code == 200
