"""Read-only HTTP checks against the configured DB, with an ephemeral local API process."""
import json
import subprocess
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from backend.app.db.postgres import get_connection

def main():
    with get_connection() as db:
        actor=db.execute("select id from public.employees where payload->>'role'='Factory Manager' and payload->>'status'='Active' limit 1").fetchone()
        assert actor, 'Add an active Factory Manager in HR before the read-only HTTP check.'
        for table in ['production_job_tasks','product_proposals','production_workflow_documents']:
            assert db.execute('select to_regclass(%s) as name',('public.'+table,)).fetchone()['name']
        assert not db.execute("select id from public.employees where id like 'WF-TEST-%%' limit 1").fetchone(), 'Rollback fixture unexpectedly persisted.'
    process=subprocess.Popen([sys.executable,'-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','18055'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    base='http://127.0.0.1:18055'
    try:
        for _ in range(50):
            try:
                with urlopen(base+'/openapi.json',timeout=1) as response: schema=json.load(response)
                break
            except (URLError,TimeoutError): time.sleep(.2)
        else: raise RuntimeError('Local API did not start.')
        assert '/api/production-jobs/manufacturing-action' in schema['paths']
        headers={'X-Demo-Role':'Factory Manager','X-Demo-Employee-Id':actor['id']}
        for path in ['/api/production-jobs/metadata','/api/production-jobs','/api/production-jobs/analytics','/api/product-proposals']:
            with urlopen(Request(base+path,headers=headers),timeout=45) as response: body=json.load(response)
            assert isinstance(body,(dict,list)),path
            print('PASS GET',path)
        try:
            urlopen(Request(base+'/api/production-jobs',headers={**headers,'X-Demo-Role':'Manufacturing Operator'}),timeout=20)
            raise AssertionError('Mismatched HR identity was accepted')
        except HTTPError as error: assert error.code==403
        print('PASS: actual HTTP routes, Supabase reads, role mismatch rejection, no persisted fixtures.')
    finally:
        process.terminate()
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired: process.kill();process.wait()

if __name__=='__main__': main()
