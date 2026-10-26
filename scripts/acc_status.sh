cd /app/backend && python3 -c "
import asyncio,os
from dotenv import load_dotenv;load_dotenv()
from motor.motor_asyncio import AsyncIOMotorClient
async def m():
  db=AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
  l=await db.acc_mock_libraries.find_one({'version':1},{'_id':0,'source_cache':0})
  sp=l.get('source_pool') or {}
  print(l['status'], l['stage'], l.get('errors'), {k:v for k,v in sp.items() if k!='flagged'}, 'flagged', len(sp.get('flagged',[])))
  c={}
  async for x in db.acc_mocks.find({'library_id':l['id']},{'_id':0,'mock_id':1,'status':1,'error':1,'validation.errors':1}):
    c.setdefault(x['status'],[]).append(x['mock_id'])
    if x['status'] in('invalid','failed'): print(x['mock_id'], x.get('error'), (x.get('validation') or {}).get('errors'))
  print({k:len(v) for k,v in c.items()})
asyncio.run(m())"
