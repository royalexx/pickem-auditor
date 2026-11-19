"""Default source-listed per-player research requests; no invented forecasts."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import re
from urllib.parse import urlsplit
from .gamebook_identity_v1 import name_key
from pathlib import Path
from scripts.nba_p1_prospective_capture import validate_schedule

ROOT=Path(__file__).resolve().parents[2]
CONFIG=ROOT/'config/nba_research_profile.json'


def instant(value):
    if not isinstance(value,str):raise ValueError('INVALID_SOURCE_CLOCK')
    x=datetime.fromisoformat(value.replace('Z','+00:00'))
    if x.tzinfo is None:raise ValueError('NAIVE_SOURCE_CLOCK')
    return x.astimezone(timezone.utc)


def source(path, url, freeze):
    raw=(path/'body.raw').read_bytes();r=json.loads((path/'receipt.json').read_bytes())
    if not isinstance(r,dict):raise ValueError('INVALID_RECEIPT')
    if r.get('url')!=url or r.get('status')!=200:raise ValueError('SOURCE_URL_OR_HTTP')
    if hashlib.sha256(raw).hexdigest()!=r.get('raw_sha256'):raise ValueError('SOURCE_BYTES_CHANGED')
    clocks=[instant(r[k]) for k in ('retrieval_started_at','retrieval_completed_at','ingested_at')]
    if not clocks[0]<=clocks[1]<=clocks[2]<=instant(freeze):raise ValueError('SOURCE_CLOCK_OR_FREEZE')
    return json.loads(raw),r


def build_requests(capture_dir, cohort):
    """Return complete source-candidate ledger; one bad member cannot drop others.

    Readiness is for conditional research input requests, never source/model
    admission or positive legal-eligibility. Actual model integration must use
    existing validated model APIs and preserve these conditioning requirements.
    """
    config=json.loads(CONFIG.read_bytes())
    if config['default_profile']!='source_listed_subset':raise ValueError('UNSUPPORTED_DEFAULT_PROFILE')
    if instant(cohort['freeze_at'])>=instant(cohort['start']):raise ValueError('NOT_PREGAME_FREEZE')
    path=Path(capture_dir);global_errors=[];rows=[];coverage=[]
    try:
        board,r=source(path/'scoreboard','https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates='+instant(cohort['start']).astimezone(__import__('zoneinfo').ZoneInfo('America/Toronto')).strftime('%Y%m%d'),cohort['freeze_at'])
        validate_schedule(json.dumps(board).encode(),cohort,True)
    except (OSError,KeyError,TypeError,ValueError) as error:global_errors.append('SCHEDULE:'+str(error))
    for tid,abbr in cohort['teams'].items():
        errors=[];people=[];attempted=None;receipt=None;raw={}
        try:
            # Read raw candidate count even if the associated receipt is rejected.
            raw=json.loads((path/('roster-'+tid)/'body.raw').read_bytes())
            people=raw['athletes']
            if not isinstance(people,list):people=[];raise ValueError('ROSTER_LIST_REQUIRED')
            attempted=len(people)
            obj,receipt=source(path/('roster-'+tid),'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/'+tid+'/roster',cohort['freeze_at'])
            if str(obj['team']['id'])!=tid:raise ValueError('ROSTER_WRONG_TEAM')
        except (OSError,KeyError,TypeError,ValueError) as error:errors.append(str(error))
        official_names=None;official_rows=[];official_receipt=None
        official_path=path/('official-'+abbr.lower()+'-roster')
        if official_path.exists():
            try:
                rr=json.loads((official_path/'receipt.json').read_bytes());official_receipt=rr;u=urlsplit(rr['url'])
                if u.scheme!='https' or u.netloc!='www.nba.com' or not u.path.endswith('/roster'):raise ValueError('OFFICIAL_ROSTER_URL')
                html=(official_path/'body.raw').read_bytes()
                if hashlib.sha256(html).hexdigest()!=rr['raw_sha256']:raise ValueError('OFFICIAL_ROSTER_BYTES')
                if not instant(rr['retrieval_started_at'])<=instant(rr['retrieval_completed_at'])<=instant(rr['ingested_at'])<=instant(cohort['freeze_at']):raise ValueError('OFFICIAL_ROSTER_CLOCK')
                native=json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',html.decode(),re.S)[1])['props']['pageProps']
                native_name=native['team']['name'];primary_name=raw.get('team',{}).get('name') if isinstance(raw,dict) and isinstance(raw.get('team',{}),dict) else None
                if not isinstance(native_name,str) or (primary_name is not None and not isinstance(primary_name,str)):raise ValueError('INVALID_ROSTER_TEAM_NAME')
                if primary_name is not None and native_name.casefold()!=primary_name.casefold():raise ValueError('OFFICIAL_ROSTER_TEAM')
                candidate_official=native['rosterData']['roster']
                if not isinstance(candidate_official,list):raise ValueError('INVALID_OFFICIAL_ROSTER_LIST')
                official_names={name_key(r['name']) for r in candidate_official}
                official_rows=candidate_official
            except (OSError,KeyError,TypeError,ValueError,IndexError) as error:official_rows=[];official_names=None;errors.append('CORROBORATION:'+str(error))
        coverage.append(dict(team_id=tid,attempted_rows=attempted,source_errors=errors,official_name_population_checked=official_names is not None))
        for n,person in enumerate(people):
            issues=list(global_errors)+list(errors)
            pid=str(person.get('id','')) if isinstance(person,dict) else ''
            if not pid.isdigit():issues.append('INVALID_PLAYER_ID')
            if not isinstance(person,dict) or not isinstance(person.get('displayName'),str) or not person['displayName'].strip():issues.append('MISSING_PLAYER_NAME')
            if official_names is not None and isinstance(person,dict) and isinstance(person.get('displayName'),str) and name_key(person['displayName']) not in official_names:issues.append('CAPTURED_ROSTER_DISAGREEMENT')
            injuries=person.get('injuries',[]) if isinstance(person,dict) else []
            if not isinstance(injuries,list):issues.append('INVALID_INJURY_LIST');injuries=[]
            elif any(not isinstance(i,dict) for i in injuries):issues.append('INVALID_INJURY_ENTRY')
            if any(isinstance(i,dict) and str(i.get('status','')).lower() in ('out','inactive') for i in injuries):issues.append('SOURCE_DECLARED_OUT')
            rows.append(dict(source_row_index=n,player_id='espn:player:'+pid if pid else None,
                team_id='espn:team:'+tid,name=person.get('displayName') if isinstance(person,dict) else None,
                source_status=person.get('status') if isinstance(person,dict) else None,
                source_injuries=injuries,source_raw_sha256=receipt.get('raw_sha256') if receipt else None,
                legal_eligibility=None,genuine_participation_probability=None,issues=issues,
                conditioning='conditional_on_participation',forecast=None))
        # Keep official-only candidates too; no fabricated ESPN identity crosswalk.
        primary_names={name_key(p['displayName']) for p in people if isinstance(p,dict) and isinstance(p.get('displayName'),str)}
        for n,person in enumerate(official_rows):
            if name_key(person['name']) not in primary_names:
                rows.append(dict(source_row_index=n,player_id='nba:player:'+str(person['id']) if person.get('id') is not None else None,
                    team_id='nba:team:'+str(native['team']['id']),name=person['name'],source_status=None,source_injuries=[],
                    source_raw_sha256=official_receipt['raw_sha256'],legal_eligibility=None,genuine_participation_probability=None,
                    issues=list(global_errors)+['UNMATCHED_OFFICIAL_SOURCE_IDENTITY'],conditioning='conditional_on_participation',forecast=None))
    counts=Counter(r['player_id'] for r in rows if r['player_id'])
    for row in rows:
        if row['player_id'] and counts[row['player_id']]>1:row['issues'].append('DUPLICATE_PLAYER_IDENTITY')
        row['source_request_status']='ABSTAIN' if row['issues'] else 'SOURCE_READY_CONDITIONAL_REQUEST'
        row['forecast_status']='ABSTAIN_SOURCE' if row['issues'] else 'AWAITING_VALID_MODEL'
    ready=sum(r['source_request_status']=='SOURCE_READY_CONDITIONAL_REQUEST' for r in rows)
    return dict(schema='nba-subset-research-requests/1.0.0',profile=config['default_profile'],
        profile_config_sha256=hashlib.sha256(CONFIG.read_bytes()).hexdigest(),game_id=cohort['game_id'],
        input_freeze_at=cohort['freeze_at'],source_candidate_rows=len(rows),source_ready_rows=ready,
        abstained_source_rows=len(rows)-ready,forecasted_rows=0,model_pending_rows=ready,
        missing_source_population=any(c['attempted_rows'] is None for c in coverage),coverage=coverage,
        legal_eligible_population_count=None,complete_legal_roster_required=False,
        historical_full_population_gates='SUPERSEDED_FOR_THIS_PROFILE',source_admission='RESEARCH_BYTES_CONSISTENCY_ONLY',
        status='RESEARCH_SUBSET_REQUESTS',production_release=False,rows=rows)
