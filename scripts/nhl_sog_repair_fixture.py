"""Deterministic synthetic acceptance fixture; NEVER part of prospective evidence."""
from pathlib import Path
import argparse,json,hashlib
from tests.test_nhl_sog_daily_ledger import fixture,outcome
from v2.nhl_sog_daily_ledger import Ledger,canonical,atomic_blob
from v2.nhl_sog_pregame_schedule import capture_identity


def run(dest):
    dest=Path(dest);dest.mkdir(parents=True,exist_ok=False)
    ledger=Ledger(dest/'fixture.sqlite');events=[]
    def unavailable(*a):raise OSError('fixture original source unavailable')
    try:capture_identity('2030-01-01',unavailable,unavailable,lambda *a:None)
    except OSError:events.append({'date':'2030-01-01','status':'BLOCKED_SOURCE_UNAVAILABLE','newly_frozen':0})
    for day in (2,3):
        c,m,n=fixture(day)
        events.append({'date':n.date().isoformat(),**ledger.freeze(c,m,run_id='synthetic-'+str(day),code_sha='a'*40,now=n)})
        events.append(ledger.settle(outcome,run_id='synthetic-morning-'+str(day)))
        events.append(ledger.settle(outcome,run_id='synthetic-retry-'+str(day)))
    exports={}
    for table in ('forecasts','outcomes','heads','runs'):
        columns=[x[1] for x in ledger.db.execute('pragma table_info('+table+')')]
        rows=[dict(zip(columns,[json.loads(x) if isinstance(x,bytes) else x for x in r]))
              for r in ledger.db.execute('select * from '+table+' order by 1')]
        raw=canonical(rows);path=dest/(table+'.json');atomic_blob(path,raw)
        exports[path.name]={'sha256':hashlib.sha256(raw).hexdigest(),'records':len(rows)}
    report={'evidence_class':'SYNTHETIC_ONLY','events':events,'exports':exports,
            'distinct_eligible_slate_dates':2,'consecutive_dates_attempted':3,
            'newly_frozen_model_records':10,'newly_settled_model_records':10,
            'unique_settled_player_games':2,'production_modified':False}
    atomic_blob(dest/'receipt.json',canonical(report));ledger.db.close()
    print(json.dumps({'path':str(dest/'receipt.json'),'sha256':hashlib.sha256(canonical(report)).hexdigest(),**report},sort_keys=True))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);run(p.parse_args().output)
