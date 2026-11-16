"""Raw-byte NBA/ESPN identity bridge and official injury PDF extraction.

Names alone never create cross-provider IDs. Membership never grants game eligibility.
"""
from dataclasses import asdict
from datetime import datetime,timedelta
import gzip
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unicodedata
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
from v2.nba_ws1.store import Receipt,canonical,digest,instant

VERSION='NBAPregameIdentityEvidence/1.1.0'
# Verified in Phase 8A retained official team pages and ESPN roster bytes.
# Provider team codes differ; these exact source IDs are not player aliases.
SOURCE_TEAM_CODE_PAIRS={('1610612752','18','NYK','NY'),('1610612744','9','GSW','GS')}


def norm(value):return ' '.join(unicodedata.normalize('NFKC',value).casefold().split())


def page_data(raw):
    m=re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',raw.decode('utf-8'),re.S)
    if not m:raise ValueError('NBA_EMBEDDED_SOURCE_UNAVAILABLE')
    return json.loads(m[1])['props']['pageProps']


def validate_receipt(raw,receipt,freeze,host=None):
    receipt.verify(raw)
    if host is not None and urlsplit(receipt.source).hostname!=host:raise ValueError('SOURCE_PROVIDER_MISMATCH')
    if instant(receipt.observed_at)>instant(freeze) or instant(receipt.source_available_at)>instant(freeze):raise ValueError('SOURCE_AFTER_FREEZE')


def build_crosswalk(nba_raw,nba_receipt,espn_raw,espn_receipt,*,freeze_at):
    validate_receipt(nba_raw,nba_receipt,freeze_at,'www.nba.com');validate_receipt(espn_raw,espn_receipt,freeze_at,'site.api.espn.com')
    nba=page_data(nba_raw)['team'];espn=json.loads(espn_raw);info=nba['info'];team=espn['team']
    if str(nba['id'])!=str(info['TEAM_ID']):raise ValueError('NBA_TEAM_ID_COLLISION')
    if norm(info['TEAM_CITY']+' '+info['TEAM_NAME'])!=norm(team['displayName']):raise ValueError('CROSS_PROVIDER_TEAM_UNRESOLVED')
    if info['TEAM_ABBREVIATION']!=team['abbreviation'] and (str(info['TEAM_ID']),str(team['id']),info['TEAM_ABBREVIATION'],team['abbreviation']) not in SOURCE_TEAM_CODE_PAIRS:raise ValueError('CROSS_PROVIDER_TEAM_UNRESOLVED')
    if '/team/'+str(info['TEAM_ID'])+'/' not in urlsplit(nba_receipt.source).path:raise ValueError('NBA_TEAM_ROUTE_MISMATCH')
    if not urlsplit(espn_receipt.source).path.endswith('/teams/'+str(team['id'])+'/roster'):raise ValueError('ESPN_TEAM_ROUTE_MISMATCH')
    effective=max(instant(nba_receipt.observed_at),instant(espn_receipt.observed_at)).isoformat()
    if any((instant(freeze_at)-instant(r.observed_at)).total_seconds()>86400 for r in (nba_receipt,espn_receipt)):raise ValueError('STALE_CROSSWALK')
    entries=[];unresolved=[];seen=set();espn_seen=set()
    nba_ids=[str(p['PLAYER_ID']) for p in nba['roster']];espn_ids=[str(p['id']) for p in espn.get('athletes',[])]
    if len(nba_ids)!=len(set(nba_ids)) or len(espn_ids)!=len(set(espn_ids)):raise ValueError('CROSSWALK_ID_COLLISION')
    for player in nba['roster']:
        if str(player['TeamID'])!=str(info['TEAM_ID']):raise ValueError('NBA_ROSTER_TEAM_COLLISION')
        try:dob=datetime.strptime(player['BIRTH_DATE'],'%b %d, %Y').date().isoformat()
        except (ValueError,KeyError):unresolved.append({'nba_player_id':str(player['PLAYER_ID']),'reason':'DOB_UNAVAILABLE'});continue
        matches=[p for p in espn.get('athletes',[]) if norm(p.get('fullName',''))==norm(player['PLAYER']) and p.get('dateOfBirth','')[:10]==dob]
        if len(matches)!=1:
            unresolved.append({'nba_player_id':str(player['PLAYER_ID']),'official_name':player['PLAYER'],'reason':'NAME_DOB_MISSING_OR_COLLISION','candidate_count':len(matches)});continue
        p=matches[0]
        if player.get('NUM') and p.get('jersey') and str(player['NUM'])!=str(p['jersey']):
            unresolved.append({'nba_player_id':str(player['PLAYER_ID']),'reason':'CONTEMPORANEOUS_JERSEY_CONFLICT'});continue
        if str(p['id']) in espn_seen:raise ValueError('CROSSWALK_MANY_TO_ONE')
        espn_seen.add(str(p['id']));seen.add(str(player['PLAYER_ID']))
        entries.append(dict(nba_player_id='nba:player:'+str(player['PLAYER_ID']),espn_player_id='espn:player:'+str(p['id']),
            nba_team_id='nba:team:'+str(info['TEAM_ID']),espn_team_id='espn:team:'+str(team['id']),official_team_name=info['TEAM_CITY']+' '+info['TEAM_NAME'],team_abbreviation=info['TEAM_ABBREVIATION'],espn_team_abbreviation=team['abbreviation'],
            official_name=player['PLAYER'],espn_name=p['fullName'],birth_date=dob,nba_jersey=player.get('NUM'),espn_jersey=p.get('jersey'),
            valid_from=effective,valid_until=(instant(effective)+timedelta(hours=24)).isoformat(),
            evidence=[asdict(nba_receipt),asdict(espn_receipt)],method='exact_team_full_name_provider_routes_and_name_DOB_v2',eligibility=None,
            evidence_kind='fixture' if any(r.origin=='fixture' for r in (nba_receipt,espn_receipt)) else 'original_source_identity_bridge'))
    for p in espn.get('athletes',[]):
        if str(p['id']) not in espn_seen:unresolved.append(dict(espn_player_id='espn:player:'+str(p['id']),reason='NO_UNIQUE_NBA_ROSTER_BRIDGE'))
    return dict(schema=VERSION,entries=entries,unresolved=unresolved,source_receipts=[asdict(nba_receipt),asdict(espn_receipt)],
        verified_identity_count=len(entries),legal_game_eligibility_established=False,as_of_at=freeze_at)


def injury_pdf(raw,receipt,*,freeze_at):
    validate_receipt(raw,receipt,freeze_at,'ak-static.cms.nba.com')
    if not raw.startswith(b'%PDF'):raise ValueError('OFFICIAL_PDF_BYTES_REQUIRED')
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'source.pdf';path.write_bytes(raw)
        text=subprocess.check_output(['pdftotext','-layout',str(path),'-'],timeout=15).decode()
        bbox=subprocess.check_output(['pdftotext','-bbox-layout',str(path),'-'],timeout=15)
    m=re.search(r'Injury Report:\s*(\d{2}/\d{2}/\d{2})\s+(\d{2}:\d{2}\s+[AP]M)',text)
    if not m:raise ValueError('PDF_PUBLICATION_HEADER_UNAVAILABLE')
    published=datetime.strptime(m[1]+' '+m[2],'%m/%d/%y %I:%M %p').replace(tzinfo=ZoneInfo('America/Toronto')).isoformat()
    if instant(published)>instant(receipt.observed_at):raise ValueError('FUTURE_INJURY_PUBLICATION')
    doc=ET.fromstring(bbox);ns={'h':'http://www.w3.org/1999/xhtml'};rows=[];gaps=[];context={'date':None,'time':None,'matchup':None,'team':None}
    for page_num,page in enumerate(doc.findall('.//h:page',ns),1):
        if abs(float(page.get('width'))-841.95)>2:raise ValueError('UNSUPPORTED_PDF_LAYOUT')
        words=[(float(w.get('xMin')),float(w.get('yMin')),w.text or '') for w in page.findall('.//h:word',ns)]
        if page_num==1 and not any(t=='Player' and 420<x<450 for x,y,t in words):raise ValueError('PDF_COLUMN_SCHEMA_CHANGED')
        lines={}
        for x,y,t in words:
            if 80<y<560:lines.setdefault(round(y,1),[]).append((x,t))
        names=[]
        for y,line in sorted(lines.items()):
            cols=[' '.join(t for x,t in sorted(line) if a<=x<b) for a,b in [(0,110),(110,195),(195,260),(260,420),(420,580),(580,665),(665,1000)]]
            if cols[4]=='Player Name':continue
            for key,value in zip(('date','time','matchup','team'),cols[:4]):
                if value:context[key]=value
            if 'NOT YET SUBMITTED' in ' '.join(cols):gaps.append(dict(page=page_num,**context,detail='NOT_YET_SUBMITTED'))
            if ',' in cols[4]:
                if not all(context.values()):raise ValueError('PDF_ROW_CONTEXT_MISSING')
                names.append((y,dict(page=page_num,**context,official_player_name=cols[4],status=cols[5],source_receipt_id=receipt.receipt_id)))
        for i,(y,row) in enumerate(names):
            low=(names[i-1][0]+y)/2 if i else 80;high=(y+names[i+1][0])/2 if i+1<len(names) else 560
            row['reason']=' '.join(t for x,yy,t in sorted(words,key=lambda w:(w[1],w[0])) if x>=665 and low<yy<high)
            if row['status'] not in ('Out','Available','Probable','Questionable','Doubtful'):raise ValueError('UNKNOWN_OFFICIAL_STATUS:'+row['status'])
            row['published_at_claim']=published;row['retrieved_at']=receipt.observed_at;rows.append(row)
    if not rows:raise ValueError('EMPTY_OFFICIAL_INJURY_REPORT')
    return dict(schema='NBAOfficialInjuryReport/1.0.0',publication_time_claim=published,publication_evidence='PDF header in original bytes; not independent timestamp attestation',
        source_receipt=asdict(receipt),rows=rows,submission_gaps=gaps,complete_active_roster=False,text_sha256=digest(text.encode()))


def resolve_injuries(report,crosswalks,*,freeze_at):
    resolved=[];unresolved=[];entries=[e for w in crosswalks for e in w['entries']]
    for row in report['rows']:
        last,first=row['official_player_name'].split(',',1);name=norm(first.strip()+' '+last.strip())
        matches=[e for e in entries if norm(e['official_name'])==name and norm(e['official_team_name'])==norm(row['team']) and e['team_abbreviation'] in row['matchup'].split('@')]
        if len(matches)!=1:unresolved.append({**row,'reason_code':'OFFICIAL_ROW_IDENTITY_UNRESOLVED','identity_candidates':len(matches)});continue
        e=matches[0]
        if not instant(e['valid_from'])<=instant(freeze_at)<instant(e['valid_until']):
            unresolved.append({**row,'reason_code':'CROSSWALK_OUTSIDE_OBSERVED_VALIDITY'});continue
        if instant(row['retrieved_at'])>instant(freeze_at) or instant(row['published_at_claim'])>instant(freeze_at):
            unresolved.append({**row,'reason_code':'INJURY_AFTER_FREEZE'});continue
        resolved.append({**row,'player_id':e['espn_player_id'],'nba_player_id':e['nba_player_id'],'team_id':e['espn_team_id'],
            'identity_evidence':e,'identity_verified':True,'eligibility':None,'participation_probability':None,
            'source_exclusion':row['status']=='Out','evidence_kind':e['evidence_kind']})
    return dict(schema='NBAResolvedAvailability/1.0.0',resolved=resolved,unresolved=unresolved,submission_gaps=report['submission_gaps'],complete_game_day_universe=False,
        resolved_count=len(resolved),unresolved_count=len(unresolved),new_participation_estimator_fitted=False)
