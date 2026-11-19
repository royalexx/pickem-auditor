"""Independent consumer: no forecast/inference calls, no original-source collection."""
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
import argparse,hashlib,json
from v2.nhl_sog_daily_ledger import Ledger,cumulative_report,canonical,atomic_blob,digest


def official(gid):
    url='https://api-web.nhle.com/v1/gamecenter/'+gid+'/boxscore'
    with urlopen(Request(url,headers={'User-Agent':'pickem-sog-settlement/1','Accept':'application/json'}),timeout=20) as h:
        if h.geturl()!=url:raise ValueError('OFFICIAL_REDIRECT_NOT_ALLOWED')
        if h.status!=200 or 'json' not in h.headers.get('Content-Type',''):
            raise ValueError('OFFICIAL_HTTP_INVALID')
        raw=h.read(10_000_001)
    if len(raw)>10_000_000:raise ValueError('OFFICIAL_BODY_TOO_LARGE')
    return json.loads(raw),{'raw':raw,'sha256':hashlib.sha256(raw).hexdigest(),
                          'url':url,'received_at':datetime.now(timezone.utc).isoformat()}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--ledger',required=True);a=p.parse_args()
    if not Path(a.ledger).is_file():raise SystemExit('BLOCKED_NO_DAILY_FROZEN_LEDGER')
    ledger=Ledger(a.ledger)
    result=ledger.settle(official,run_id=datetime.now(timezone.utc).isoformat())
    report=cumulative_report(ledger)
    path=Path(a.ledger).parent/'evaluations'/(digest(report)+'.json')
    atomic_blob(path,canonical(report))
    print(json.dumps({**result,'evaluation_path':str(path),'evaluation_sha256':digest(report)},sort_keys=True))
