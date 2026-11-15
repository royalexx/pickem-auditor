"""One-shot supplements to the existing WS1 capture path; no scheduled collector."""
from dataclasses import asdict
from datetime import datetime,timezone
import gzip
import json
from pathlib import Path
import re
from urllib.request import Request,urlopen
from v2.nba_ws1.capture import now
from v2.nba_ws1.store import Receipt,digest,instant
from v2.nba_joint.forecast import freeze
from research.nba_phase6.roster import build_roster_contract
from v2.nba_ws1 import NBAPregameFeatureSnapshot
from .evidence import injury_pdf,build_crosswalk,resolve_injuries,page_data,norm
from .participation import participation_layer


def acquire_supplements(output,board_event,*,deadline_at):
    root=Path(output);root.mkdir(parents=True,exist_ok=False);items=[];errors=[]
    def fetch(kind,url):
        if instant(now())>instant(deadline_at):raise ValueError('SUPPLEMENT_FREEZE_DEADLINE_MISSED')
        with urlopen(Request(url,headers={'User-Agent':'pickem-phase7-bounded-research/1'}),timeout=15) as response:raw=response.read(4*1024*1024+1)
        if len(raw)>4*1024*1024:raise ValueError('SOURCE_SIZE_BOUND')
        r=Receipt.capture(raw,source=url,observed_at=now(),origin='original_capture');filename=r.raw_sha256+'.gz'
        with (root/filename).open('xb') as f:f.write(gzip.compress(raw,mtime=0))
        items.append(dict(kind=kind,receipt=asdict(r),path=filename))
        if instant(r.observed_at)>instant(deadline_at):raise ValueError('SUPPLEMENT_LATE_RECEIPT')
        return raw,r
    try:
        raw,_=fetch('nba_player_directory','https://www.nba.com/players');directory=page_data(raw)['players']
        for comp in board_event['competitions'][0]['competitors']:
            expected=comp['team']['displayName'];teams={(str(p['TEAM_ID']),p['TEAM_SLUG']) for p in directory if norm(p['TEAM_CITY']+' '+p['TEAM_NAME'])==norm(expected)}
            if len(teams)!=1:errors.append(dict(code='NBA_TEAM_DIRECTORY_UNRESOLVED',team=expected));continue
            tid,slug=next(iter(teams));fetch('nba_team_roster','https://www.nba.com/team/'+tid+'/'+slug)
        raw,_=fetch('official_injury_index','https://official.nba.com/nba-injury-report-2026-27-season/')
        candidates=[]
        for url in re.findall(r'href=["\x27]([^"\x27]+)',raw.decode()):
            m=re.search(r'Injury-Report_(\d{4}-\d{2}-\d{2})_(\d{2})_(\d{2})(AM|PM)\.pdf$',url)
            if m:
                claimed=datetime.strptime(' '.join(m.groups()),'%Y-%m-%d %I %M %p').replace(tzinfo=__import__('zoneinfo').ZoneInfo('America/Toronto'))
                if claimed<=instant(now()) and claimed<=instant(deadline_at):candidates.append((claimed,url))
        if not candidates:raise ValueError('ORIGINAL_OFFICIAL_PDF_UNAVAILABLE')
        fetch('official_injury_pdf',max(candidates)[1])
    except Exception as exc:errors.append(dict(code=type(exc).__name__,detail=str(exc)))
    report=dict(schema='NBAPhase7SupplementCapture/1',items=items,errors=errors,captured_at=now(),status='captured_partial' if items else 'blocked',used_for_model=False)
    freeze(root/'receipt.json',report);return report


def read_supplement(folder,item):
    root=Path(folder).resolve();path=(root/item['path']).resolve()
    if not path.is_relative_to(root):raise ValueError('SUPPLEMENT_PATH_ESCAPE')
    raw=gzip.decompress(path.read_bytes());r=Receipt(**item['receipt']);r.verify(raw);return raw,r


def build_game_ledger(capture_folder,supplement_folder,model):
    root=Path(capture_folder);cap=json.loads((root/'capture_receipt.json').read_text())
    roster=build_roster_contract(root,model);snap=NBAPregameFeatureSnapshot.from_json((root/cap['snapshot_path']).read_text()).to_dict()
    at=snap['input_freeze_at'];espn=[]
    receipts={r['receipt_id']:Receipt(**r) for r in snap['receipts']}
    for source in cap['sources']:
        r=receipts[source['receipt_id']]
        if r.source.endswith('/roster'):
            path=(root/source['path']).resolve()
            if not path.is_relative_to(root.resolve()):raise ValueError('WS1_SOURCE_PATH_ESCAPE')
            raw=gzip.decompress(path.read_bytes());r.verify(raw);espn.append((raw,r))
    supplement=json.loads((Path(supplement_folder)/'receipt.json').read_text());walks=[];errors=[];reports=[]
    for item in supplement['items']:
        raw,r=read_supplement(supplement_folder,item)
        if item['kind']=='nba_team_roster':
            for e,er in espn:
                try:w=build_crosswalk(raw,r,e,er,freeze_at=at)
                except ValueError as exc:
                    if str(exc)!='CROSS_PROVIDER_TEAM_UNRESOLVED':errors.append(dict(code=str(exc),receipt_id=r.receipt_id))
                else:walks.append(w)
        if item['kind']=='official_injury_pdf':
            try:reports.append(injury_pdf(raw,r,freeze_at=at))
            except ValueError as exc:errors.append(dict(code=str(exc),receipt_id=r.receipt_id))
    resolved=[];unresolved=[];gaps=[]
    for report in reports:
        result=resolve_injuries(report,walks,freeze_at=at);resolved+=result['resolved'];unresolved+=result['unresolved'];gaps+=result['submission_gaps']
    availability=dict(resolved=resolved,unresolved=unresolved,submission_gaps=gaps)
    abbr=[json.loads(e)['team']['abbreviation'] for e,er in espn]
    participation=participation_layer(roster,availability,game_abbreviations=abbr)
    pmap={p['player_id']:p for p in snap['players']};supported=0;missing=[]
    from v2.nba_opportunity import causal_features
    day=instant(snap['game']['event_start_at']).astimezone(__import__('zoneinfo').ZoneInfo('America/Toronto')).date().isoformat()
    for row in participation['rows']:
        p=pmap[row['player_id']];h=[{**x,'workload':x['minutes'],'team':x['team_id']} for x in p['history'] if x['participation']=='played' and x['minutes']>0]
        try:causal_features(h,game_date=day,team=p['team_id'],home=p['home'])
        except ValueError as exc:row['M0_usable']=False;row['M0_abstention']=str(exc);missing.append(p['player_id'])
        else:row['M0_usable']=True;supported+=1
    return dict(schema='NBAPhase7GameDayLedger/1.0.0',game=snap['game'],input_freeze_at=at,
        model_sha256=roster['model_sha256'],ws1_snapshot_content_hash=snap['content_hash'],roster_contract=roster,
        identity_crosswalks=walks,official_injury_reports=reports,availability=availability,participation=participation,
        denominators=dict(original_candidate_players=len(snap['players']),confirmed_eligible=0,confirmed_ineligible=0,
            eligibility_unknown=len(snap['players']),availability_unknown=sum(r['availability']=='unknown' for r in participation['rows']),
            source_verified_inactive=participation['source_exclusions'],announced_starters=0,positive_validated_participation_probabilities=0,
            known_candidate_usable_M0=supported,known_candidate_missing_M0=len(missing),actual_participants=None,actual_DNPs=None,missed_actual_appearances=None,
            F_accepted=0,F_abstained=len(snap['players']),original_contracts=len(snap['market_context']['original_contracts'])),
        errors=errors+supplement['errors'],F_status='BLOCKED-BY-DATA',market_status='BLOCKED-BY-DATA',
        reasons=['COMPLETE_GAME_DAY_ELIGIBILITY_UNAVAILABLE','VALIDATED_POSITIVE_PARTICIPATION_UNAVAILABLE'],
        scoring_status='pending future official settlement; no conditional score claimed as participation calibration')
