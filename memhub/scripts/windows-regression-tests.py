from pathlib import Path
import tempfile,sqlite3,unittest
from one_memory.memory_server.contracts import BatchIdentity,WriteRequest
from one_memory.memory_server.durable_queue import DurableWriteQueue,UNKNOWN
from one_memory.opencode_compat import opencode_session_header
class RetryTests(unittest.TestCase):
 def tearDown(self):
  from one_memory.database_access import close_main_databases
  close_main_databases()
 def test_confirmed_retry_persists_separate_sdk_identity(self):
  with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
   db=Path(root)/'test.sqlite3';q=DurableWriteQueue(db,sdk_authority=True)
   req=WriteRequest(internal_session_id='test',batch_identity=BatchIdentity(internal_session_id='test',first_round=1,last_round=1),evidence_ids=["fixture"],idempotency_key='original')
   r=q.submit(req)
   self.assertEqual(q.sdk_request_id(r.job_id),'original')
   q.settle(r.job_id,state=UNKNOWN,error_code='hy_sdk_write_failed',hy_invoked=True)
   self.assertEqual(q.retry_unknown_confirmed(r.job_id),1)
   current=q.sdk_request_id(r.job_id)
   self.assertNotEqual(current,'original')
   self.assertEqual(q.retry_unknown_confirmed(r.job_id),0)
   reopened=DurableWriteQueue(db,sdk_authority=True)
   self.assertEqual(reopened.sdk_request_id(r.job_id),current)
   self.assertIsNotNone(reopened.get('original'))
   reopened.settle(r.job_id,state=UNKNOWN,error_code='hy_sdk_write_failed',hy_invoked=True)
   self.assertEqual(reopened.unknown_jobs()[0].request_id,current)
   self.assertEqual(reopened.retry_unknown_confirmed(r.job_id),1)
   self.assertNotEqual(reopened.sdk_request_id(r.job_id),current)
 def test_windows_import_receipt_replay_and_commit(self):
  from uuid import uuid4,UUID
  from one_memory.file_imports import FileImportStore
  from one_memory.imports.models import EvidenceContentKind
  with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
   store=FileImportStore(Path(root)/'imports')
   op=str(uuid4())
   receipt=store.prepare(b'Synthetic memory: budget is 8000.', 'memory.txt',input_kind=EvidenceContentKind.MEMORY_CONTENT,operation_id=op)
   self.assertEqual(receipt.state,'completed')
   self.assertEqual(receipt.upload_state,'staged')
   self.assertEqual(store.lookup_operation(op),receipt)
   self.assertEqual(store.prepare(b'Synthetic memory: budget is 8000.', 'memory.txt',input_kind=EvidenceContentKind.MEMORY_CONTENT,operation_id=op),receipt)
   store.commit(receipt.upload_id)
   self.assertEqual(store.lookup_operation(op).upload_state,'committed')
 def test_windows_rejects_public_storage(self):
  import os
  from one_memory.windows_private_storage import windows_private_storage
  if os.name!='nt':self.skipTest('Windows ACL test')
  with tempfile.TemporaryDirectory() as root:
   with self.assertRaises(OSError):windows_private_storage(Path(root))
 def test_imported_memory_is_queued_once_without_a_user_turn(self):
  from one_memory.database_access import main_database
  from one_memory.imports.models import EvidenceInput,EvidenceContentKind,EvidenceOrigin,OriginMetadata,materialize_write_input
  with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
   db=Path(root)/'test.sqlite3';q=DurableWriteQueue(db,sdk_authority=True)
   record=materialize_write_input(EvidenceInput(source_id='memory-content-export',conversation_id='fixture',message_id='1',role='memory',written_by='person',verbatim='Synthetic imported memory.',content_kind=EvidenceContentKind.MEMORY_CONTENT,origin_meta={EvidenceOrigin.MANUAL_IMPORT:OriginMetadata()}))
   with main_database(db).write(row_factory=sqlite3.Row) as c,c:
    q.stage_sdk_input(record,file_key='fixture',priority='normal',connection=c)
    q.finalize_sdk_file(user_id='local',source_id=record.source_id,file_key='fixture',connection=c)
    q.stage_sdk_input(record,file_key='fixture',priority='normal',connection=c)
    rows=c.execute('select state,payload_json from memory_write_jobs').fetchall()
   self.assertEqual(len(rows),1)
   self.assertEqual(rows[0]['state'],'pending')
   self.assertIn('Synthetic imported memory.',rows[0]['payload_json'])
 def test_provider_retry_preserves_queue_identity_and_gets_new_sdk_id(self):
  from datetime import datetime,UTC,timedelta
  with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
   db=Path(root)/'retry.sqlite3';q=DurableWriteQueue(db,sdk_authority=True)
   req=WriteRequest(internal_session_id='test',batch_identity=BatchIdentity(internal_session_id='test',first_round=1,last_round=1),evidence_ids=['fixture'],idempotency_key='provider')
   r=q.submit(req)
   with sqlite3.connect(db) as c,c:
    c.execute("UPDATE memory_write_jobs SET state='running',hy_invoked=1,attempts=1 WHERE job_id=?",(r.job_id,))
   self.assertTrue(q.requeue_for_model(r.job_id,error_code='model_auth_failed'))
   self.assertEqual(q.sdk_request_id(r.job_id),'provider#r1')
   self.assertEqual(q.get('provider').state,'pending')
   with sqlite3.connect(db) as c:
    self.assertEqual(c.execute('SELECT retries,attempts FROM memory_write_jobs').fetchone(),(0,0))
 def test_unknown_recovery_waits_for_running_sdk_call(self):
  with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
   db=Path(root)/'retry.sqlite3';q=DurableWriteQueue(db,sdk_authority=True)
   req=WriteRequest(internal_session_id='test',batch_identity=BatchIdentity(internal_session_id='test',first_round=1,last_round=1),evidence_ids=['fixture'],idempotency_key='unknown')
   r=q.submit(req);q.settle(r.job_id,state=UNKNOWN,error_code='hy_sdk_write_failed',hy_invoked=True)
   self.assertEqual(q.recover_unknown(in_flight=lambda _:True),0)
   self.assertEqual(q.recover_unknown(),1)
   self.assertEqual(q.sdk_request_id(r.job_id),'unknown#r1')
 def test_job_retries_are_bounded(self):
  with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
   db=Path(root)/'retry.sqlite3';q=DurableWriteQueue(db,sdk_authority=True)
   req=WriteRequest(internal_session_id='test',batch_identity=BatchIdentity(internal_session_id='test',first_round=1,last_round=1),evidence_ids=['fixture'],idempotency_key='bounded')
   r=q.submit(req)
   for expected in ['pending','pending','pending','failed']:
    with sqlite3.connect(db) as c,c:c.execute("UPDATE memory_write_jobs SET state='running',hy_invoked=1 WHERE job_id=?",(r.job_id,))
    self.assertEqual(q.retry_or_fail(r.job_id,error_code='hy_sdk_json_parse_failed'),expected)
 def test_recovered_write_checks_previous_receipt_before_sending_again(self):
  import asyncio
  from one_memory.imports.models import EvidenceInput,EvidenceContentKind,EvidenceOrigin,OriginMetadata,materialize_write_input
  from one_memory.memory_server.durable_queue import execute_job
  from one_memory.sdk_write_processor import SdkWriteReceipt
  with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
   db=Path(root)/'receipt.sqlite3';q=DurableWriteQueue(db,sdk_authority=True)
   record=materialize_write_input(EvidenceInput(source_id='memory-content-export',conversation_id='fixture',message_id='1',role='memory',written_by='person',verbatim='Synthetic memory.',content_kind=EvidenceContentKind.MEMORY_CONTENT,origin_meta={EvidenceOrigin.MANUAL_IMPORT:OriginMetadata()}))
   req=WriteRequest(internal_session_id='test',source_id=record.source_id,batch_identity=BatchIdentity(internal_session_id='test',first_round=1,last_round=1),evidence_ids=[record.evidence_id],input_records=(record,),idempotency_key='receipt')
   r=q.submit(req)
   with sqlite3.connect(db) as c,c:c.execute("UPDATE memory_write_jobs SET state='running',sdk_attempt=1 WHERE job_id=?",(r.job_id,))
   class Supervisor:
    async def inquire_write_outcome(self,request_id):
     if request_id!='receipt':raise AssertionError(request_id)
     return SdkWriteReceipt(memory_ids=('already-stored',))
    async def process_sdk_job(self,*a,**k):raise AssertionError('duplicate SDK write')
   asyncio.run(execute_job(r.job_id,queue=q,supervisor=Supervisor(),evidence=None))
   self.assertEqual(q.get('receipt').state,'completed')
   self.assertEqual(q.get('receipt').sdk_memory_ids,('already-stored',))
 def test_header_only_for_exact_gateway(self):
  self.assertIn('x-opencode-session',opencode_session_header('https://opencode.ai/inference/go/openai/v1'))
  self.assertEqual(opencode_session_header('https://example.com/opencode.ai/v1'),{})
  self.assertEqual(opencode_session_header('https://opencode.ai.evil.test/v1'),{})
if __name__=='__main__':unittest.main()


