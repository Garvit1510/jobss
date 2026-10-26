import requests, os, sys
sys.path.insert(0,'.')
from dotenv import load_dotenv; load_dotenv(".env")
from pymongo import MongoClient
import accenture_games as g
db=MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
API="https://career-lens-ai-3.preview.emergentagent.com/api"
s=requests.Session()
s.post(API+"/auth/login",json={"email":"admin@joblens.dev","password":"Admin@12345","device_id":"devtest000000000000099"})
B=API+"/accenture-mocks/M1/gamified"
s.delete(B)
st=s.post(B+"/start",json={"preview":True}).json()
DIRS={(-1,0):"up",(1,0):"down",(0,-1):"left",(0,1):"right"}
for i in range(6):
    st=s.post(B+"/begin").json(); act=st["activities"][st["current"]]
    sa=db.acc_attempts.find_one({"id":st["id"]})["activities"][i]["state"]
    if act["game"]=="memory_maze":
        p=sa["maze"]["path"]
        for a,b in zip(p,p[1:]): r=s.post(B+"/maze/move",json={"dir":DIRS[(b[0]-a[0],b[1]-a[1])]}).json()
        print(i, r.get("event"))
    elif act["game"]=="bubble_math":
        for k,q in enumerate(sa["questions"]):
            order=sorted(range(3),key=lambda j:q["values"][j]) if k%5 else [2,1,0]
            r=s.post(B+"/bubble/answer",json={"index":k,"order":order}).json()
        print(i, r["activities"][i]["result"])
    else:
        pf=sa["pf"]; n=pf["n"]
        sol=pf["solution"]
        for r0 in range(n):
            for c0 in range(n):
                while db.acc_attempts.find_one({"id":st["id"]})["activities"][i]["state"]["board"][r0][c0]!=sol[r0][c0] and pf["initial"][r0][c0]!=sol[r0][c0]:
                    s.post(B+"/path/rotate",json={"r":r0,"c":c0})
        r=s.post(B+"/path/check").json(); print(i, r["event"], r["moves"], "par", pf["par"])
fin=s.get(B).json(); print(fin["round_score"])
s.delete(B)
