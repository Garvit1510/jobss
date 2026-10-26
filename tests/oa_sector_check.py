import json, sys, concurrent.futures as cf, requests
API = open('/app/frontend/.env').read().split('REACT_APP_BACKEND_URL=')[1].split()[0]
s = requests.Session()
s.post(f"{API}/api/auth/login", json={"email": "admin@joblens.dev", "password": "Admin@12345", "device_id": "devtestadmin0000000001"})
CASES = [("sales", "Sales Executive"), ("education", "School Teacher (Maths)"), ("data", "Data Analyst"), ("government", "SSC CGL"), ("trades", "Electrician"), ("tech", "Software Engineer")]

def run(c):
    sid, role = c
    r = s.post(f"{API}/api/mock-oa/generate", json={"sector": sid, "topic": role, "difficulty": "Easy", "num_questions": 8, "duration_minutes": 30}, timeout=240)
    if r.status_code != 200:
        return sid, f"GEN {r.status_code} {r.text[:150]}"
    d = r.json(); t = d["test"]
    types = {}
    ans = {}
    for sec in t["sections"]:
        for q in sec["questions"]:
            types[q["type"]] = types.get(q["type"], 0) + 1
            ans[q["id"]] = 0 if q["type"] == "mcq" else "42" if q["type"] == "numeric" else "I would first listen to the customer, clarify the need, then propose a solution and confirm next steps."
    sub = s.post(f"{API}/api/mock-oa/submit", json={"test_id": d["id"], "answers": ans, "time_taken_sec": 300}, timeout=240)
    res = sub.json() if sub.status_code == 200 else {"err": sub.text[:150]}
    return sid, {"title": t["title"], "sections": [x["name"] for x in t["sections"]], "types": types, "coding": len(t["coding"]),
                 "score": res.get("score_pct"), "sec_pct": [(x["name"], x["pct"]) for x in res.get("sections", [])],
                 "written_graded": sum(1 for x in res.get("review", []) if x.get("ai_score") is not None), "insights": list((res.get("insights") or {}).keys()), "progress": res.get("progress"), "note": t.get("pattern_note", "")[:120]}

with cf.ThreadPoolExecutor(6) as ex:
    for sid, out in ex.map(run, CASES):
        print(sid, json.dumps(out)[:700]); sys.stdout.flush()
