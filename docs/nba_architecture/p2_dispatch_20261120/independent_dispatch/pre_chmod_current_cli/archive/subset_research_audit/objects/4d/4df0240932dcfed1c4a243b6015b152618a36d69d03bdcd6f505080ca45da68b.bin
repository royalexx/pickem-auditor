#!/usr/bin/env python3
"""One fixed prospective source-evidence cohort; no forecasts or automatic GO."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v2.nba_architecture.p1_capture_v1 import capture

ROOT=Path(__file__).resolve().parents[1]
PACKET=ROOT/'docs/nba_architecture/p1_prospective_20261118'
COHORT_SHA256='692d662a8a256d46e36bc416225e2eb22136e5da41f2a486d725469f704e91b9'
BASE='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/'


def instant(value):
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None:raise ValueError('NAIVE_CLOCK')
    return dt


def roster_rows(raw, team_id):
    """Native listed-candidate reader, explicitly no eligibility admission."""
    x=json.loads(raw)
    if str(x['team']['id'])!=team_id:raise ValueError('WRONG_ROSTER_TEAM')
    ids=[str(a['id']) for a in x['athletes']]
    if len(ids)!=len(set(ids)) or any(not i.isdigit() for i in ids):raise ValueError('DUPLICATE_OR_INVALID_PLAYER')
    return [dict(player_id='espn:player:'+str(a['id']),team_id='espn:team:'+team_id,
                 name=a['displayName'],source_status=a.get('status'),source_generated_at=x.get('timestamp'),
                 source_published_at=None,
                 source_injuries=a.get('injuries',[]),availability='UNKNOWN_UNADMITTED',
                 legal_eligibility=None,participation_probability=None)
            for a in x['athletes']]


def validate_schedule(raw, cohort, pregame):
    matches=[e for e in json.loads(raw)['events'] if str(e['id'])==cohort['game_id']]
    if len(matches)!=1:raise ValueError('TARGET_MISSING_OR_DUPLICATE')
    e=matches[0]
    teams={str(c['team']['id']):c['team']['abbreviation'] for c in e['competitions'][0]['competitors']}
    if teams!=cohort['teams'] or instant(e['date'])!=instant(cohort['start']):raise ValueError('TARGET_IDENTITY_OR_START_CHANGED')
    if pregame and (e['status']['type']['state']!='pre' or e['status']['type']['name']!='STATUS_SCHEDULED'):raise ValueError('TARGET_NO_LONGER_PREGAME')
    return e['status']


def run(stage, output):
    cohort_raw=(PACKET/'COHORT.json').read_bytes()
    if hashlib.sha256(cohort_raw).hexdigest()!=COHORT_SHA256:raise ValueError('COHORT_BYTES_CHANGED')
    cohort=json.loads(cohort_raw)
    start=datetime.now(timezone.utc)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    attempt=output/(stage+'-'+start.strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex[:8]);attempt.mkdir()
    result=dict(schema='nba-p1-prospective-attempt/1.0.0',stage=stage,started_at=start.isoformat(),
                cohort_raw_sha256=hashlib.sha256((PACKET/'COHORT.json').read_bytes()).hexdigest(),
                admission='UNADMITTED',target_eligible_roster_count=None,
                correction_history_complete=None,rows=[],roster_denominators={},sources={},errors=[],G1='NO-GO')
    pregame=stage!='morning'
    if pregame and start>=instant(cohort['freeze_at']):
        result['errors'].append('MISSED_ORIGINAL_FREEZE')
    elif not pregame and start<=instant(cohort['start']):
        result['errors'].append('POSTGAME_CAPTURE_TOO_EARLY')
    else:
        urls={'scoreboard':BASE+'scoreboard?dates=20261118',
              'target-summary':BASE+'summary?event='+cohort['game_id'],
              'official-injury-index':'https://official.nba.com/nba-injury-report-2026-27-season/'}
        for tid,abbr in cohort['teams'].items():
            urls['roster-'+tid]=BASE+'teams/'+tid+'/roster'
            urls['schedule-'+tid]=BASE+'teams/'+tid+'/schedule'
        if not pregame:
            urls['official-gamebook']='https://statsdmz.nba.com/pdfs/20261118/20261118_MEMCLE_book.pdf'
        urls['official-cle-roster']='https://www.nba.com/cavaliers/roster'
        urls['official-mem-roster']='https://www.nba.com/grizzlies/roster'
        def acquire(item):
            name,url=item
            return name,capture(url,attempt/name)
        with ThreadPoolExecutor(max_workers=4) as pool:
            result['sources']=dict(pool.map(acquire,urls.items()))
        for name,r in result['sources'].items():
            r['observed_predecessor_raw_sha256']=None
            # Observed local captures only, never a complete provider correction chain.
            for previous in sorted(output.glob('*/'+name+'/receipt.json'),reverse=True):
                if previous.parent.parent==attempt:continue
                old=json.loads(previous.read_bytes())
                if old.get('url')==r['url'] and old.get('raw_sha256') and instant(old['retrieval_started_at'])<start:
                    r['observed_predecessor_raw_sha256']=old['raw_sha256'];break
            if r.get('status')!=200:result['errors'].append(name+':HTTP_CAPTURE_UNAVAILABLE')
        try:
            result['target_status']=validate_schedule((attempt/'scoreboard/body.raw').read_bytes(),cohort,pregame)
        except (ValueError,KeyError,OSError,TypeError) as e:result['errors'].append('SCHEDULE:'+str(e))
        for tid in cohort['teams']:
            raw=None;attempted=None
            try:
                raw=(attempt/('roster-'+tid)/'body.raw').read_bytes()
                attempted=len(json.loads(raw)['athletes'])
                parsed=roster_rows(raw,tid);result['rows']+=parsed
                result['roster_denominators'][tid]=dict(attempted=attempted,parsed=len(parsed),rejected=0)
            except (ValueError,KeyError,OSError,TypeError) as e:
                result['roster_denominators'][tid]=dict(attempted=attempted,parsed=0,rejected=attempted)
                result['errors'].append('ROSTER_'+tid+':'+str(e))
        if len({r['player_id'] for r in result['rows']})!=len(result['rows']):result['errors'].append('CROSS_TEAM_DUPLICATE_IDENTITY')
        # Bound prior-result acquisition to most recent completed scheduled game per team.
        for tid in cohort['teams']:
            try:
                schedule=json.loads((attempt/('schedule-'+tid)/'body.raw').read_bytes())
                prior=[e for e in schedule.get('events',[]) if instant(e['date'])<instant(cohort['start']) and e['competitions'][0]['status']['type'].get('completed') is True]
                if prior:
                    e=max(prior,key=lambda e:instant(e['date']));name='prior-'+tid+'-'+str(e['id'])
                    result['sources'][name]=capture(BASE+'summary?event='+str(e['id']),attempt/name)
                else:result['errors'].append('PRIOR_RESULT_MISSING_'+tid)
            except (ValueError,KeyError,OSError,TypeError) as e:result['errors'].append('PRIOR_'+tid+':'+str(e))
        # Preserve linked official injury PDFs if actually published on the index.
        try:
            import re
            html=(attempt/'official-injury-index/body.raw').read_text()
            links=sorted(set(re.findall(r'https://ak-static\.cms\.nba\.com/[^\s\"<>]+\.pdf',html)))
            current=[u for u in links if '2026-11-18' in u or '2026-11-19' in u]
            for i,u in enumerate(current[-2:]):
                if urlsplit(u).hostname=='ak-static.cms.nba.com':result['sources']['injury-pdf-'+str(i)]=capture(u,attempt/('injury-pdf-'+str(i)))
            if not current:result['errors'].append('NO_CURRENT_OFFICIAL_INJURY_PDF_LINK')
        except (OSError,UnicodeError):result['errors'].append('OFFICIAL_INJURY_INDEX_UNREADABLE')
        for name,r in result['sources'].items():
            if r.get('status')!=200 and name+':HTTP_CAPTURE_UNAVAILABLE' not in result['errors']:result['errors'].append(name+':HTTP_CAPTURE_UNAVAILABLE')
        if pregame and datetime.now(timezone.utc)>=instant(cohort['freeze_at']):result['errors'].append('CAPTURE_COMPLETED_AFTER_FREEZE')
    result['returned_roster_rows']=len(result['rows'])
    result['availability_unknown_rows']=len(result['rows'])
    result['completed_at']=datetime.now(timezone.utc).isoformat()
    result['status']='CAPTURED_UNADMITTED_WITH_GAPS' if result['errors'] else 'CAPTURED_UNADMITTED'
    (attempt/'attempt.json').write_text(json.dumps(result,indent=2)+'\n')
    manifest=''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+str(f.relative_to(attempt))+'\n' for f in sorted(attempt.rglob('*')) if f.is_file())
    (attempt/'SHA256SUMS').write_text(manifest)
    print(json.dumps({'attempt':str(attempt),'status':result['status'],'returned_roster_rows':len(result['rows']),'errors':result['errors']}))
    return attempt


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['initial','pregame','morning'],required=True);parser.add_argument('--output',type=Path,default=PACKET/'captures');args=parser.parse_args();run(args.stage,args.output)
