"""Live Core/SDK acceptance against synthetic data in an isolated temp directory.
Reads only the active model configuration/key from the desktop; never alters its data.
Run with apps/core/.venv/Scripts/python.exe scripts/windows-core-validation.py.
"""
import asyncio,json,os,secrets,sqlite3,tempfile,time
from pathlib import Path
from uuid import uuid4
import httpx
from pydantic import SecretStr
from one_memory.hy_runtime_config import configure_hy_runtime_environment

ROOT=Path(tempfile.mkdtemp(prefix='memhub-core-acceptance-'))
configure_hy_runtime_environment(ROOT/'data')
from one_memory.api import create_app
from one_memory.config import Settings
from one_memory.secrets import InMemorySecretStore,KeyringSecretStore
RESULTS=[]
def passed(name,**details):
 RESULTS.append({'test':name,'status':'passed',**details})
 print('PASS',name,json.dumps(details,ensure_ascii=True),flush=True)
 (ROOT/'results.json').write_text(json.dumps(RESULTS,ensure_ascii=False,indent=2),encoding='utf-8')
async def main():
 real=Path(os.environ['LOCALAPPDATA'])/'MemHub-Windows/Data/one-memory.sqlite3'
 with sqlite3.connect(real.as_uri()+'?mode=ro',uri=True) as db:
  db.row_factory=sqlite3.Row
  profile=dict(db.execute('select * from model_profiles where is_active=1').fetchone())
 key=KeyringSecretStore().resolve(profile['secret_ref'])
 assert key,'active credential unavailable'
 token=secrets.token_hex(32)
 app=create_app(Settings(data_dir=ROOT/'data',source_home=ROOT/'source-home',api_token=SecretStr(token),live_sync_enabled=False),secret_store=InMemorySecretStore())
 async with app.router.lifespan_context(app),httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers={'Authorization':'Bearer '+token},timeout=300) as c:
  async def call(method,path,**kwargs):
   r=await c.request(method,path,**kwargs)
   if r.status_code>=400:raise AssertionError(f'{method} {path}: {r.status_code} {r.text[:300]}')
   return r.json() if r.content else None
  denied=await c.get('/api/v1/sources',headers={'Authorization':'Bearer invalid'})
  assert denied.status_code==401
  passed('Core rejects invalid token')
  fields=['name','provider_kind','base_url','model','embedding_model','embedding_provider_kind','embedding_base_url','embedding_dimensions','timeout_seconds','max_concurrency','context_window','disable_thinking']
  spec={k:profile[k] for k in fields};spec.update(api_key=key,disable_thinking=bool(profile['disable_thinking']),max_concurrency=1)
  created=await call('POST','/api/v1/model-profiles',json=spec)
  assert key not in json.dumps(created)
  pid=created['profile_id'];revision=created['revision']
  probe=await call('POST',f'/api/v1/model-profiles/{pid}/probe')
  assert probe['capabilities']['structured_output'] and probe['capabilities']['embedding_available'],probe
  passed('Real model structured-output and embedding probe')
  await call('POST',f'/api/v1/model-profiles/{pid}/activate')
  stale=await c.patch(f'/api/v1/model-profiles/{pid}',json={'expected_revision':revision+100,'model':'stale'})
  assert stale.status_code==409
  passed('Model activation and stale revision rejection')
  async def upload_and_import(payload,filename,kind):
   op=str(uuid4())
   path=f'/api/v1/import-files?filename={filename}&input_kind={kind}&operation_id={op}'
   receipt=await call('POST',path,content=payload,headers={'Content-Type':'application/octet-stream'})
   assert receipt['state']=='completed',receipt
   replay=await call('POST',path,content=payload,headers={'Content-Type':'application/octet-stream'})
   assert receipt['upload_id']==replay['upload_id']
   uid=receipt['upload_id']
   preview=await call('GET',f'/api/v1/import-files/{uid}')
   assert not preview['committed']
   commit=await call('POST',f'/api/v1/import-files/{uid}/commit',json={'confirmed':True})
   source=next(s for s in await call('GET','/api/v1/sources') if s['source_id']==commit['source_id'])
   connection=await call('POST','/api/v1/sources/connect',json={'source_ids':[source['source_id']],'request_id':str(uuid4()),'source_roots':{source['source_id']:source['candidate_root_id']},'source_candidate_revisions':{source['source_id']:source['candidate_revision']},'import_upload_id':uid,'enable_sync':True})
   assert connection['accepted_source_ids']==[source['source_id']],connection
   passed('Upload preview commit and import accepted',kind=kind)
  now=time.time()
  chat=[{'id':'acceptance-chat','title':'Synthetic acceptance','current_node':'a1','mapping':{'root':{'message':None,'parent':None},'u1':{'parent':'root','message':{'id':'u1','author':{'role':'user'},'create_time':now,'content':{'parts':['测试项目青鹭计划的发布日确定为每周三，负责人是林舟，请记住这个项目安排。']}}},'a1':{'parent':'u1','message':{'id':'a1','author':{'role':'assistant'},'create_time':now+1,'content':{'parts':['好的，青鹭计划由林舟负责，每周三发布。']}}}}}]
  await upload_and_import(json.dumps(chat,ensure_ascii=False).encode(),'conversations.json','raw_conversation')
  await upload_and_import('测试项目紫杉计划预算为八千元，交付日期是十二月十五日。'.encode(),'memories.txt','memory_content')
  for i in range(120):
   status=await call('GET','/api/v1/memory-processing')
   if status['completed']>=2 and status['running']==0 and status['pending']==0:break
   if status['unknown'] or status['failed']:raise AssertionError(f'processing failed: {status}')
   if i%6==0:print('processing',json.dumps({k:status[k] for k in ['pending','running','completed','unknown','failed']}),flush=True)
   await asyncio.sleep(3)
  else:raise AssertionError('processing did not drain in 6 minutes')
  passed('Conversation extraction and memory-content ingestion',completed=status['completed'])
  await app.state.sdk_client_handle.client()
  for query,kinds,expected in [('青鹭计划',['raw'],'林舟'),('紫杉计划',['memory'],'八千')]:
   result=await call('POST','/api/v2/context/search',json={'query':query,'kinds':kinds,'limit':5,'timeout_ms':30000})
   assert expected in json.dumps(result,ensure_ascii=False),(query,result)
   passed('Search '+kinds[0],hits=len(result['items']))
  answer=await call('POST','/api/v2/memories/ask',json={'question':'紫杉计划的预算是多少？'})
  assert answer['mode']=='generated' and answer['memories']
  assert any(x in answer['answer'] for x in ['八千','8000','8,000']),answer
  passed('Generated answer grounded in imported memory')
  before=status['completed']
  request_id=str(uuid4())
  note={'request_id':request_id,'text':'测试项目白鹭计划使用绿色封面。','scope':'all-apps'}
  first=await call('POST','/api/v2/memories',json=note)
  again=await call('POST','/api/v2/memories',json=note)
  assert first['evidence_id']==again['evidence_id']
  for _ in range(60):
   added=await call('GET',f'/api/v2/memories/additions/{request_id}')
   if added['state']=='ready':break
   assert added['state'] not in ['failed','unknown'],added
   await asyncio.sleep(1)
  else:raise AssertionError('manual note not ready')
  assert len(added['memory_ids'])==1
  passed('Manual memory request is idempotent')
  mid=added['memory_ids'][0]
  updated=await call('PUT',f'/api/v2/memories/{mid}',json={'content':'测试项目白鹭计划改用蓝色封面。'})
  assert '蓝色' in updated['content'],updated
  fetched=await call('GET',f'/api/v2/memories/{mid}')
  assert '蓝色' in fetched['content']
  await call('DELETE',f'/api/v2/memories/{mid}')
  assert (await c.get(f'/api/v2/memories/{mid}')).status_code==404
  passed('Memory update readback and deletion')
  await call('GET','/api/v2/memory-library')
  await call('GET','/api/v2/memories/graph')
  passed('Library and graph endpoints')
 print('REPORT',ROOT/'results.json',flush=True)
try:asyncio.run(main())
except Exception as e:
 RESULTS.append({'test':'acceptance','status':'failed','error':str(e)[:800]})
 (ROOT/'results.json').write_text(json.dumps(RESULTS,ensure_ascii=False,indent=2),encoding='utf-8')
 print('FAILED',str(e)[:800],flush=True);print('REPORT',ROOT/'results.json',flush=True);raise
