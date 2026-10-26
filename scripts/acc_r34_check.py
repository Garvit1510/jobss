import requests, os, sys
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv; load_dotenv("/app/backend/.env")
from pymongo import MongoClient
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
API = "https://career-lens-ai-3.preview.emergentagent.com/api"
s = requests.Session()
s.post(API + "/auth/login", json={"email": "admin@joblens.dev", "password": "Admin@12345", "device_id": "devtest000000000000099"})
s.delete(API + "/accenture-mocks/M1/preview-attempts")
T = API + "/accenture-mocks/M1/technical"
st = s.post(T + "/start", json={"preview": True}).json()
print("R3 questions", len(st["questions"]), "has key before submit:", any("answer_index" in q for q in st["questions"]))
m = db.acc_mocks.find_one({"mock_id": "M1"}, sort=[("version", -1)])
for i, q in enumerate(m["rounds"]["technical"]["questions"]):
    if i < 40:
        s.post(T + "/answer", json={"qid": q["qid"], "choice": q["answer_index"] if i < 36 else (q["answer_index"] + 1) % 4})
r = s.post(T + "/submit").json()["result"]
print("R3", {k: r[k] for k in ("correct", "incorrect", "unanswered", "raw", "max", "percent", "passed")})
C = API + "/accenture-mocks/M1/coding"
st = s.post(C + "/start", json={"preview": True}).json()
probs = {p["type"]: p for p in m["rounds"]["coding"]["problems"]}
for t in st["tasks"]:
    s.post(C + "/begin")
    p = probs[t["type"]]
    if t["type"] == "dsa":
        body = {"lang": "python", "code": p["reference_python"]}
        bad = {"lang": "python", "code": "print(0)"}
    elif t["type"] == "sql":
        body = {"lang": "sql", "code": p["reference"]}
        bad = {"lang": "sql", "code": "SELECT 1"}
    else:
        body = {"lang": "web", **p["reference"]}
        bad = {"lang": "web", **p["starter"]}
    rr = s.post(C + "/run", json=bad).json()
    sb = s.post(C + "/submit", json=bad).json()
    sg = s.post(C + "/submit", json=body).json()
    hidden_leak = any("input" in x or "expected" in x for x in sg["result"]["results"] if not x["visible"])
    print(t["type"], "run visible", rr.get("passed"), "/", rr.get("total"), "| bad", sb.get("score"), "| ref", sg.get("score"), "| hidden leak", hidden_leak)
    s.post(C + "/next")
fin = s.get(C).json()
print("R4", fin["result"])
print("report", s.get(API + "/accenture-mocks/M1/report").json()["rounds"].keys())
s.delete(API + "/accenture-mocks/M1/preview-attempts")
