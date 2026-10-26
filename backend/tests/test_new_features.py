"""Backend tests for the NEW features in iteration 2:

- GET /api/jobs/countries
- GET /api/jobs?country=India filter
- Full /api/alerts CRUD + /summary + /new + /seen + ownership
- POST /api/interview/finish with 0 and >=1 answers
- Evaluation payload shape for voice mode (spoken_feedback)

Uses the pre-seeded test1 user. The AI-dependent interview tests may take
10-30s each due to Gemini latency.
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
def _login_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    device_id = "pytestnewf" + uuid.uuid4().hex[:16]
    r = s.post(f"{API}/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD, "device_id": device_id}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Login failed {r.status_code}: {r.text}")
    return s


@pytest.fixture(scope="module")
def auth_client():
    return _login_session()


@pytest.fixture(scope="module", autouse=True)
def cleanup_alerts(auth_client):
    """Delete all alerts owned by test user before and after module runs."""
    def _clear():
        try:
            r = auth_client.get(f"{API}/alerts", timeout=20)
            if r.status_code == 200:
                for a in r.json().get("alerts", []):
                    auth_client.delete(f"{API}/alerts/{a['id']}", timeout=10)
        except Exception:
            pass
    _clear()
    yield
    _clear()


# ---------------- Jobs: countries filter ----------------
class TestJobsCountries:
    def test_countries_endpoint(self, auth_client):
        r = auth_client.get(f"{API}/jobs/countries", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "countries" in d
        countries = d["countries"]
        assert isinstance(countries, list) and len(countries) > 0
        # Every row has name + count
        for c in countries:
            assert "name" in c and "count" in c
            assert isinstance(c["count"], int) and c["count"] > 0
        # Remote / Anywhere, if present, must be first
        names = [c["name"] for c in countries]
        if "Remote / Anywhere" in names:
            assert names[0] == "Remote / Anywhere", f"Remote / Anywhere must be first; got {names[:3]}"
        # Must include at least US or India for a meaningful filter test
        assert any(n in names for n in ("United States", "India")), f"Expected major countries in {names[:10]}"

    def test_filter_by_india(self, auth_client):
        c = auth_client.get(f"{API}/jobs/countries", timeout=20).json()["countries"]
        if not any(x["name"] == "India" for x in c):
            pytest.skip("No India jobs available right now")
        r = auth_client.get(f"{API}/jobs?country=India&limit=12", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["total"] > 0
        # Every returned job must have India in countries
        for j in d["jobs"]:
            # countries may be in LIST_PROJ or not; fall back to total check
            if "countries" in j:
                assert "India" in j["countries"], f"Job returned without India: {j.get('title')}"

    def test_filter_country_all_is_default(self, auth_client):
        r1 = auth_client.get(f"{API}/jobs?limit=1", timeout=20)
        r2 = auth_client.get(f"{API}/jobs?country=all&limit=1", timeout=20)
        assert r1.status_code == r2.status_code == 200
        assert r1.json()["total"] == r2.json()["total"]

    def test_country_combines_with_other_filters(self, auth_client):
        r = auth_client.get(f"{API}/jobs?country=United%20States&work=Remote&limit=12", timeout=30)
        assert r.status_code == 200
        d = r.json()
        # Just make sure endpoint accepts combo and jobs returned (if any) are Remote
        for j in d["jobs"][:5]:
            if j.get("work_type"):
                assert j["work_type"] == "Remote"


# ---------------- Alerts CRUD ----------------
class TestAlerts:
    def test_create_list_summary_new_seen_delete(self, auth_client):
        # CREATE
        payload = {"name": "TEST_alert_py", "q": "engineer", "work": "Remote", "country": "all"}
        r = auth_client.post(f"{API}/alerts", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        a = r.json()
        assert a["name"] == "TEST_alert_py"
        assert "id" in a
        assert a["filters"]["q"] == "engineer"
        assert a["filters"]["work"] == "Remote"
        assert a["new_count"] == 0
        assert a["total"] >= 0
        alert_id = a["id"]

        # LIST
        rl = auth_client.get(f"{API}/alerts", timeout=15)
        assert rl.status_code == 200
        alerts = rl.json()["alerts"]
        assert any(x["id"] == alert_id for x in alerts)

        # SUMMARY
        rs = auth_client.get(f"{API}/alerts/summary", timeout=15)
        assert rs.status_code == 200
        sd = rs.json()
        assert sd["alerts"] >= 1
        assert isinstance(sd["total_new"], int) and sd["total_new"] >= 0

        # NEW jobs (ownership success)
        rn = auth_client.get(f"{API}/alerts/{alert_id}/new", timeout=20)
        assert rn.status_code == 200
        nd = rn.json()
        assert nd["alert"]["id"] == alert_id
        assert isinstance(nd["jobs"], list)

        # SEEN
        rseen = auth_client.post(f"{API}/alerts/{alert_id}/seen", timeout=10)
        assert rseen.status_code == 200
        assert rseen.json() == {"ok": True}

        # DELETE
        rd = auth_client.delete(f"{API}/alerts/{alert_id}", timeout=10)
        assert rd.status_code == 200
        # Verify gone
        rl2 = auth_client.get(f"{API}/alerts", timeout=10).json()["alerts"]
        assert not any(x["id"] == alert_id for x in rl2)

    def test_duplicate_alert_rejected(self, auth_client):
        payload = {"name": "TEST_dup", "q": "python", "work": "All", "level": "All", "source": "all", "country": "all"}
        r1 = auth_client.post(f"{API}/alerts", json=payload, timeout=15)
        assert r1.status_code == 200, r1.text
        aid = r1.json()["id"]
        try:
            # Same filters => 400
            r2 = auth_client.post(f"{API}/alerts", json={**payload, "name": "TEST_dup_2"}, timeout=15)
            assert r2.status_code == 400
            assert "already" in r2.text.lower()
        finally:
            auth_client.delete(f"{API}/alerts/{aid}", timeout=10)

    def test_max_alerts(self, auth_client):
        created = []
        try:
            for i in range(10):
                r = auth_client.post(f"{API}/alerts", json={"name": f"TEST_max_{i}", "q": f"role-{i}"}, timeout=15)
                assert r.status_code == 200, f"create {i} failed: {r.text}"
                created.append(r.json()["id"])
            # 11th must fail
            r11 = auth_client.post(f"{API}/alerts", json={"name": "TEST_max_11", "q": "role-11"}, timeout=15)
            assert r11.status_code == 400
            assert "10" in r11.text or "up to" in r11.text.lower()
        finally:
            for aid in created:
                auth_client.delete(f"{API}/alerts/{aid}", timeout=10)

    def test_other_user_cannot_access(self, auth_client):
        # Create an alert as auth_client
        r = auth_client.post(f"{API}/alerts", json={"name": "TEST_owner", "q": "secretrole"}, timeout=15)
        assert r.status_code == 200
        aid = r.json()["id"]
        try:
            # No other test user exists. Simulate by making a request with no cookie.
            rno = requests.get(f"{API}/alerts/{aid}/new", timeout=10)
            assert rno.status_code == 401
            # Access with a fake alert_id => 404
            rfake = auth_client.get(f"{API}/alerts/nonexistent-{uuid.uuid4().hex}/new", timeout=10)
            assert rfake.status_code == 404
            rfake2 = auth_client.delete(f"{API}/alerts/nonexistent-{uuid.uuid4().hex}", timeout=10)
            assert rfake2.status_code == 404
        finally:
            auth_client.delete(f"{API}/alerts/{aid}", timeout=10)


# ---------------- Interview finish + spoken_feedback ----------------
class TestInterviewFinish:
    def test_finish_with_zero_answers_returns_null_report(self, auth_client):
        r = auth_client.post(f"{API}/interview/start", json={"role": "Backend Engineer", "mode": "voice", "num_questions": 3}, timeout=40)
        assert r.status_code == 200, r.text
        sid = r.json()["session_id"]
        rf = auth_client.post(f"{API}/interview/finish", json={"session_id": sid}, timeout=20)
        assert rf.status_code == 200
        assert rf.json() == {"report": None}
        # Finishing again should 404 (already abandoned)
        rf2 = auth_client.post(f"{API}/interview/finish", json={"session_id": sid}, timeout=10)
        assert rf2.status_code == 404

    def test_answer_contains_spoken_feedback_and_finish_returns_report(self, auth_client):
        r = auth_client.post(f"{API}/interview/start", json={"role": "Backend Engineer", "mode": "voice", "num_questions": 3}, timeout=40)
        assert r.status_code == 200, r.text
        s = r.json()
        sid = s["session_id"]
        # Answer first question
        ra = auth_client.post(f"{API}/interview/answer",
                              json={"session_id": sid, "answer": "I built a FastAPI service with Mongo and JWT auth, scaled to 10k requests/sec using Redis caching and async workers."},
                              timeout=60)
        assert ra.status_code == 200, ra.text
        ev = ra.json()["evaluation"]
        # Spoken feedback must be present in voice mode
        assert "spoken_feedback" in ev, f"Expected spoken_feedback in evaluation keys: {list(ev.keys())}"
        assert isinstance(ev["spoken_feedback"], str) and len(ev["spoken_feedback"]) > 0
        # Finish now with 1 answered question
        rf = auth_client.post(f"{API}/interview/finish", json={"session_id": sid}, timeout=90)
        assert rf.status_code == 200, rf.text
        report = rf.json().get("report")
        assert report is not None, "Expected non-null report when at least one answer exists"
        for k in ("overall_score", "verdict", "summary", "strengths", "improvements", "recommendations", "per_question"):
            assert k in report, f"Report missing key: {k} (got {list(report.keys())})"
        assert isinstance(report["recommendations"], list) and len(report["recommendations"]) >= 1
