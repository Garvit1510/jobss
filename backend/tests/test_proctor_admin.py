"""Backend tests for new iteration features:

- Proctored Mock OA generate / flag / submit integrity report
- Admin panel: stats, bans list/unban, users list/unban, non-admin 403
- Regression: non-proctored OA still works, test1 can log in

Uses existing seeded users: admin@joblens.dev / Admin@12345 and test1@joblens.dev / Test@12345.
"""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@joblens.dev"
ADMIN_PASSWORD = "Admin@12345"
TEST_EMAIL = "test1@joblens.dev"
TEST_PASSWORD = "Test@12345"
TEST_DEVICE = "devtest000000000000001"


def _login(email, password, device_id):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password, "device_id": device_id}, timeout=20)
    return s, r


@pytest.fixture(scope="module")
def admin_client():
    s, r = _login(ADMIN_EMAIL, ADMIN_PASSWORD, "admin" + uuid.uuid4().hex[:16])
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text}")
    return s


@pytest.fixture(scope="module")
def user_client():
    s, r = _login(TEST_EMAIL, TEST_PASSWORD, TEST_DEVICE)
    if r.status_code != 200:
        pytest.skip(f"Test user login failed: {r.status_code} {r.text}")
    return s


# ---------------- Admin Panel ----------------
class TestAdminAuth:
    def test_admin_login_sets_cookie_and_role(self, admin_client):
        r = admin_client.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

    def test_non_admin_forbidden_on_admin_routes(self, user_client):
        for path in ["/admin/stats", "/admin/bans", "/admin/users"]:
            r = user_client.get(f"{API}{path}", timeout=15)
            assert r.status_code == 403, f"{path} should be 403 got {r.status_code}"

    def test_unauth_admin_route_401(self):
        r = requests.get(f"{API}/admin/stats", timeout=15)
        assert r.status_code == 401


class TestAdminStatsAndLists:
    def test_stats_shape(self, admin_client):
        r = admin_client.get(f"{API}/admin/stats", timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ("users", "banned_users", "active_bans", "lifted_bans"):
            assert k in d and isinstance(d[k], int)

    def test_bans_filters(self, admin_client):
        for st in ("active", "lifted", "all"):
            r = admin_client.get(f"{API}/admin/bans?status={st}", timeout=15)
            assert r.status_code == 200
            bans = r.json()["bans"]
            assert isinstance(bans, list)
            for b in bans:
                assert "id" in b and "active" in b
                if st == "active":
                    assert b["active"] is True
                elif st == "lifted":
                    assert b["active"] is False

    def test_users_list_and_search(self, admin_client):
        r = admin_client.get(f"{API}/admin/users", timeout=15)
        assert r.status_code == 200
        users = r.json()["users"]
        assert isinstance(users, list)
        # Admin itself excluded
        assert not any(u["email"] == ADMIN_EMAIL for u in users)
        # Search
        r2 = admin_client.get(f"{API}/admin/users?q=test1", timeout=15)
        assert r2.status_code == 200
        assert any(u["email"] == TEST_EMAIL for u in r2.json()["users"])


class TestAdminUnbanFlow:
    """Creates a ban via duplicate-register, then unbans. Must always clean up to avoid blocking the test IP."""

    def test_create_ban_then_unban_restores_login(self, admin_client):
        # Trigger ban by registering a 2nd account using test1's device_id
        attempted = f"TEST_dup_{uuid.uuid4().hex[:8]}@joblens.dev"
        rr = requests.post(f"{API}/auth/register", json={
            "name": "Dup", "email": attempted, "password": "Dup@12345x", "device_id": TEST_DEVICE
        }, timeout=20)
        assert rr.status_code == 403, f"Expected duplicate device register to 403, got {rr.status_code}: {rr.text}"

        try:
            # Confirm test1 is now banned (login forbidden)
            _, rlog = _login(TEST_EMAIL, TEST_PASSWORD, TEST_DEVICE)
            assert rlog.status_code == 403, f"Expected test1 login to be 403 after ban, got {rlog.status_code}"

            # Find the new active ban for test1
            rb = admin_client.get(f"{API}/admin/bans?status=active", timeout=15)
            assert rb.status_code == 200
            bans = rb.json()["bans"]
            target = next((b for b in bans if b.get("user_email") == TEST_EMAIL), None)
            assert target is not None, f"No active ban found for {TEST_EMAIL}: {bans}"

            # Unban via /bans/{id}/unban
            ru = admin_client.post(f"{API}/admin/bans/{target['id']}/unban", timeout=15)
            assert ru.status_code == 200, ru.text
            assert ru.json()["ok"] is True

            # Second unban should 400 (already lifted)
            ru2 = admin_client.post(f"{API}/admin/bans/{target['id']}/unban", timeout=15)
            assert ru2.status_code == 400

            # Also hit /users/{uid}/unban idempotently to clear any residual flags
            # Fetch user id
            ulist = admin_client.get(f"{API}/admin/users?q=test1", timeout=15).json()["users"]
            uid = next(u["id"] for u in ulist if u["email"] == TEST_EMAIL)
            rbu = admin_client.post(f"{API}/admin/users/{uid}/unban", timeout=15)
            assert rbu.status_code == 200

            # test1 must now be able to log in again
            _, rlog2 = _login(TEST_EMAIL, TEST_PASSWORD, TEST_DEVICE)
            assert rlog2.status_code == 200, f"Expected test1 login OK after unban, got {rlog2.status_code}: {rlog2.text}"
        finally:
            # Safety: unban anything active for test1 to avoid blocking next tests
            try:
                rb = admin_client.get(f"{API}/admin/bans?status=active", timeout=15).json()["bans"]
                for b in rb:
                    if b.get("user_email") == TEST_EMAIL:
                        admin_client.post(f"{API}/admin/bans/{b['id']}/unban", timeout=15)
                ulist = admin_client.get(f"{API}/admin/users?q=test1", timeout=15).json()["users"]
                for u in ulist:
                    if u["email"] == TEST_EMAIL:
                        admin_client.post(f"{API}/admin/users/{u['id']}/unban", timeout=15)
            except Exception as e:
                print("cleanup error:", e)

    def test_unban_missing_ban_404(self, admin_client):
        r = admin_client.post(f"{API}/admin/bans/nonexistent-{uuid.uuid4().hex}/unban", timeout=15)
        assert r.status_code == 404

    def test_unban_missing_user_404(self, admin_client):
        r = admin_client.post(f"{API}/admin/users/nope-{uuid.uuid4().hex}/unban", timeout=15)
        assert r.status_code == 404


# ---------------- Proctored OA ----------------
def _re_login_user():
    s, r = _login(TEST_EMAIL, TEST_PASSWORD, TEST_DEVICE)
    assert r.status_code == 200, f"user re-login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def oa_user_client(user_client):
    # After admin flow test runs, test1 session may have been replaced by re-login.
    # Give a fresh session just for OA tests.
    return _re_login_user()


class TestProctoredOA:
    @pytest.fixture(scope="class")
    def proctored_test(self, oa_user_client):
        last_err = None
        for _ in range(3):
            r = oa_user_client.post(f"{API}/mock-oa/generate",
                                    json={"topic": "Python Backend", "difficulty": "Easy", "proctored": True},
                                    timeout=120)
            if r.status_code == 200:
                return oa_user_client, r.json()
            last_err = (r.status_code, r.text[:200])
            time.sleep(5)
        pytest.skip(f"OA generate failed (likely Gemini rate-limit): {last_err}")

    def test_generate_returns_proctored_true(self, proctored_test):
        _, d = proctored_test
        assert d["proctored"] is True
        assert "id" in d
        assert "test" in d and "sections" in d["test"]

    def test_flag_known_types_recorded(self, proctored_test):
        client, d = proctored_test
        for t in ["tab_switch", "window_blur", "fullscreen_exit", "copy_paste",
                  "camera_off", "mic_off", "camera_blocked", "loud_noise"]:
            r = client.post(f"{API}/mock-oa/{d['id']}/flag", json={"type": t, "detail": "auto"}, timeout=15)
            assert r.status_code == 200, f"{t}: {r.status_code} {r.text}"
            body = r.json()
            assert body["ok"] is True
            assert body["recorded"] is True

    def test_flag_unknown_type_rejected(self, proctored_test):
        client, d = proctored_test
        r = client.post(f"{API}/mock-oa/{d['id']}/flag", json={"type": "nope"}, timeout=15)
        assert r.status_code == 400

    def test_submit_includes_proctoring_report(self, proctored_test):
        client, d = proctored_test
        r = client.post(f"{API}/mock-oa/submit",
                        json={"test_id": d["id"], "answers": {}, "code": {},
                              "time_taken_sec": 42, "auto_reason": "auto_submitted_integrity"},
                        timeout=120)
        assert r.status_code == 200, r.text
        res = r.json()
        assert res.get("auto_reason") == "auto_submitted_integrity"
        p = res.get("proctoring")
        assert p is not None, "Expected proctoring report in result"
        for k in ("integrity_score", "risk", "counts", "timeline"):
            assert k in p
        assert 0 <= p["integrity_score"] <= 100
        assert p["risk"] in ("Low", "Medium", "High")
        # We flagged 8 distinct types; integrity should be noticeably <100
        assert p["integrity_score"] < 100
        for k in ["tab_switch", "window_blur", "fullscreen_exit", "copy_paste",
                  "camera_off", "mic_off", "camera_blocked", "loud_noise"]:
            assert p["counts"].get(k, 0) >= 1

    def test_flag_ignored_after_submit(self, proctored_test):
        client, d = proctored_test
        r = client.post(f"{API}/mock-oa/{d['id']}/flag", json={"type": "tab_switch"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["recorded"] is False  # already submitted


class TestNonProctoredOARegression:
    def test_generate_submit_non_proctored(self, oa_user_client):
        last = None
        for _ in range(3):
            r = oa_user_client.post(f"{API}/mock-oa/generate",
                                    json={"topic": "Python", "difficulty": "Easy", "proctored": False},
                                    timeout=120)
            if r.status_code == 200:
                break
            last = (r.status_code, r.text[:200])
            time.sleep(5)
        else:
            pytest.skip(f"OA generate rate-limited: {last}")
        d = r.json()
        assert d["proctored"] is False
        sr = oa_user_client.post(f"{API}/mock-oa/submit",
                                 json={"test_id": d["id"], "answers": {}, "code": {}, "time_taken_sec": 10},
                                 timeout=120)
        assert sr.status_code == 200
        res = sr.json()
        assert res.get("proctoring") is None
