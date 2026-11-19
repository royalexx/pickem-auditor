"""Prospective source capture to the narrow research request consumer."""
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
from .p1_capture_v1 import capture
from .research_profile_v1 import instant
from .p1_subset_handoff_v1 import export_requests,canonical,conditional_requests


def capture_subset(cohort,output):
    path=Path(output);path.mkdir(parents=True,exist_ok=False)
    result={'schema':'nba-p1-subset-capture/1.0.0','game_id':cohort['game_id'],'started_at':datetime.now(timezone.utc).isoformat(),'forecasted_rows':0}
    if instant(result['started_at'])>=instant(cohort['freeze_at']):
        result.update(status='MISSED_FREEZE',requests=None)
    else:
        date=instant(cohort['start']).astimezone(__import__('zoneinfo').ZoneInfo('America/Toronto')).strftime('%Y%m%d')
        base='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/'
        urls={'scoreboard':base+'scoreboard?dates='+date}
        urls.update({'roster-'+str(tid):base+'teams/'+str(tid)+'/roster' for tid in cohort['teams']})
        def acquire(pair):return pair[0],capture(pair[1],path/pair[0])
        with ThreadPoolExecutor(max_workers=3) as pool:result['sources']=dict(pool.map(acquire,urls.items()))
        wire=export_requests(path,cohort);(path/'handoff.json').write_bytes(canonical(wire))
        consumed=conditional_requests((path/'handoff.json').read_bytes(),path,cohort)
        (path/'consumer.json').write_text(json.dumps(consumed,indent=2)+'\n')
        result.update(status='CAPTURED_RESEARCH_REQUESTS',candidate_rows=consumed['candidate_denominator'],requests=len(consumed['requests']),abstained=consumed['source_abstentions'],actual_model_consumer_executed=False)
    result['completed_at']=datetime.now(timezone.utc).isoformat()
    (path/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    (path/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(path))+'\n' for p in sorted(path.rglob('*')) if p.is_file()))
    return result
