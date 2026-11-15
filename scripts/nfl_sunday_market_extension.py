"""Versioned WS1 market/feature extension; uses the existing WS1 receipts only.

No sportsbook HTTP client, forecast model, production policy or backdating.
Run from the repository root. Missing official components remain missing.
"""
from __future__ import annotations
import csv
import io
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from nfl_sunday_feature_store import (ROOT, ARCHIVE, canonical, sha, stamp, now,
    numeric, norm, rows_json_gz, unchanged)

VERSION = 'ws1-nfl-market-taxonomy-v2.5.1'
OLD_SOURCE = '5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71'
OLD_FEATURE = '35a1bf7fe16acca1e115c7be7bcad2c2464ec27cdf7e799df4f2b31adba24c2a'
FIELDS = {
    'pass_attempts': ('attempts',), 'pass_completions': ('completions',),
    'passing_yards': ('passing_yards',), 'rush_attempts': ('carries',),
    'rushing_yards': ('rushing_yards',), 'receiving_targets': ('targets',),
    'receptions': ('receptions',), 'receiving_yards': ('receiving_yards',),
    'tackles_assists': ('tackles_combined',),
    'rushing_receiving_yards': ('rushing_yards', 'receiving_yards'),
    'passing_rushing_yards': ('passing_yards', 'rushing_yards'),
}
MIGRATION = dict(zip(('pass attempts','completions','passing yards','rush attempts',
    'rushing yards','targets','receptions','receiving yards','tackles + assists',
    'rushing + receiving yards','passing + rushing yards'), FIELDS))
PROVIDER_KEYS = dict(zip(('player_pass_attempts','player_pass_completions','player_pass_yds',
    'player_rush_attempts','player_rush_yds','player_targets','player_receptions',
    'player_reception_yds','player_tackles_assists','player_rush_reception_yds',
    'player_pass_rush_yds'), FIELDS))
# The last three additions are inbound mappings, NOT undocumented live request keys.
DENIED = {'solo tackles','tackle assists','solo_tackles','assisted_tackles',
          'def_tackles_solo','def_tackle_assists','sacks','interceptions','passes defended'}

def market(value):
    if value in FIELDS: return value
    if value in MIGRATION: return MIGRATION[value]
    if value in PROVIDER_KEYS: return PROVIDER_KEYS[value]
    raise ValueError('UNAPPROVED_MARKET:' + str(value))

def identity(pid):
    if not isinstance(pid,str) or not re.fullmatch(r'00-\d{7}',pid):
        raise ValueError('GSIS_NAMESPACE_REQUIRED')
    return 'gsis:' + pid

def value(row, key):
    """All components come from ONE official player-game record, full game.

    Combined tackles deliberately fail closed until independent provider accounting
    evidence is supplied. Old three-field sums are not recertified by this extension.
    """
    key=market(key)
    if key == 'tackles_assists': return None
    parts=[numeric(row.get(k)) for k in FIELDS[key]]
    return None if any(v is None for v in parts) else sum(parts)

def unique_history(rows):
    out={}
    for r in rows:
        key=(identity(r['gsis_id']),r['game_id'],r.get('period','full_game'))
        if key in out and canonical(out[key])!=canonical(r):
            raise ValueError('CONFLICTING_PLAYER_GAME_SOURCE:' + str(key))
        out[key]=r
    return list(out.values())

def eligible(position, key, qb1, historical_rush):
    if position=='QB':
        return qb1 and key in {'pass_attempts','pass_completions','passing_yards',
            'rush_attempts','rushing_yards','passing_rushing_yards'}
    if key in {'pass_attempts','pass_completions','passing_yards','passing_rushing_yards'}: return False
    if key in {'rush_attempts','rushing_yards'}:
        return position in {'RB','FB','WR','TE'} and historical_rush
    if key in {'receiving_targets','receptions','receiving_yards','rushing_receiving_yards'}:
        return position in {'RB','FB','WR','TE'}
    return key=='tackles_assists' and position in {'LB','ILB','OLB','MLB','CB','DB','S','FS','SS','DE','DT','DL','NT','EDGE'}

def history_valid(row, freeze):
    return (row.get('period','full_game')=='full_game' and
        bool(row.get('game_date')) and row['game_date'][:10]<'2026-11-15' and
        stamp(row['source_available_at'])<=stamp(freeze))

def verified(path, digest):
    b=Path(path).read_bytes()
    if sha(b)!=digest: raise ValueError('SOURCE_SHA_MISMATCH:'+str(path))
    return b

def read_csv(receipt):
    return list(csv.DictReader(io.StringIO(verified(receipt['raw_path'],receipt['sha256']).decode('utf-8-sig'))))

def load_history(pin, freeze):
    rows=[]; evidence=[]
    archive=json.loads((ARCHIVE/'MANIFEST.json').read_bytes())
    at=archive['collected_utc']
    for season in range(2016,2026):
        gp=ARCHIVE/f'games_{season}.json.gz';sp=ARCHIVE/f'stats_{season}.json.gz'
        games,_=rows_json_gz(gp,archive['source_files'][gp.name])
        stats,_=rows_json_gz(sp,archive['source_files'][sp.name])
        catalog={g['game_id']:g for g in games if g.get('game_type')=='REG' and g.get('gameday','')[:10]<'2026-11-15'}
        for r in stats:
            g=catalog.get(r.get('game_id'))
            if not g or r.get('season_type')!='REG':continue
            rr={**r,'gsis_id':r.get('player_id'),'game_date':g['gameday'],
                'period':'full_game','source_available_at':at,'source_file':str(sp),
                'source_sha256':archive['source_files'][sp.name]}
            if history_valid(rr,freeze): rows.append(rr)
        evidence.extend([{'path':str(p),'sha256':archive['source_files'][p.name],'source_available_at':at} for p in (gp,sp)])
    recs=pin['new_raw_source_receipts']
    games=read_csv(recs['games2026']);stats=read_csv(recs['stats2026'])
    catalog={}
    for g in games:
        if g.get('season')!='2026' or g.get('game_type')!='REG' or not g.get('gameday') or g['gameday']>='2026-11-15' or numeric(g.get('result')) is None:continue
        for team in (g['away_team'],g['home_team']):catalog[(g['week'],team)]=g
    at=max((recs[n]['observed_received_at'] for n in ('games2026','stats2026')),key=stamp)
    for r in stats:
        team=r.get('recent_team') or r.get('team');g=catalog.get((r.get('week'),team))
        if not g or r.get('season_type')!='REG':continue
        rr={**r,'gsis_id':r.get('player_id') or r.get('gsis_id'),'team':team,
            'game_id':g['game_id'],'game_date':g['gameday'],'period':'full_game',
            'source_available_at':at,'source_file':recs['stats2026']['raw_path'],
            'source_sha256':recs['stats2026']['sha256']}
        if history_valid(rr,freeze):rows.append(rr)
    evidence.extend({'path':r['raw_path'],'sha256':r['sha256'],'source_available_at':r['observed_received_at']} for r in recs.values() if r.get('raw_path'))
    return unique_history(rows),evidence

def table(out, name, rows):
    b=b''.join(canonical(r) for r in rows)
    rec=unchanged(out/(name+'_'+sha(b)+'.jsonl'),b)
    return {**rec,'rows':len(rows)}

def build():
    freeze=now();old_path=ROOT/'FORECAST_FEATURE_PIN.json'
    old_bytes=verified(old_path,OLD_FEATURE);pin=json.loads(old_bytes)
    source_path=Path(pin['canonical_source_manifest_path'])
    source_bytes=verified(source_path,OLD_SOURCE);manifest=json.loads(source_bytes)
    assert len(manifest['candidates'])==1845
    for rec in pin['tables'].values(): verified(rec['path'],rec['sha256'])
    # Verify all raw archives before deriving identities or replaying exact offers.
    for rec in manifest['sources'].values():
        if rec.get('archive_path'):verified(ROOT/rec['archive_path'],rec['sha256'])
    # Reuse the sole WS1 public-source acquisition helper in a separate receipt
    # namespace. These are fresh observations, never inserted in the old pin.
    import nfl_sunday_feature_store as shared
    old_root=shared.ROOT
    acquired={}
    try:
        shared.ROOT=ROOT/'market_extension_v2_5_1'
        for label,url in shared.PUBLIC.items():
            _,receipt=shared.fetch_public(label,url)
            acquired[label]=receipt
    finally:shared.ROOT=old_root
    pin=dict(pin)
    pin['new_raw_source_receipts']=dict(pin['new_raw_source_receipts'])
    for label,receipt in acquired.items():
        if receipt.get('raw_path'):pin['new_raw_source_receipts'][label]=receipt
    freeze=now()
    history,evidence=load_history(pin,freeze)
    by_player=defaultdict(list)
    for r in history:by_player[r['gsis_id']].append(r)
    for h in by_player.values():h.sort(key=lambda r:(r['game_date'],r['game_id']))
    bridge=defaultdict(set);names={}
    for p in read_csv(pin['new_raw_source_receipts']['players']):
        eid=str(p.get('espn_id') or '').removesuffix('.0');gid=p.get('gsis_id')
        if eid and gid:
            bridge[eid].add(gid);names[(eid,gid)]=p.get('display_name')
    from nfl_sunday_capture import roster_athletes,depth_qb
    sources=manifest['sources'];players=[];history_output=[]
    for event in manifest['events']:
        if not event.get('schedule_verified'):continue
        for team,opp in ((event['home'],event['away']),(event['away'],event['home'])):
            rr=sources.get('espn_'+team+'_roster');dr=sources.get('espn_'+team+'_depthcharts')
            if not rr:continue
            roster=json.loads(verified(ROOT/rr['archive_path'],rr['sha256']))
            depth=depth_qb(json.loads(verified(ROOT/dr['archive_path'],dr['sha256']))) if dr else None
            for p in roster_athletes(roster):
                eid=str(p['id']);gs=bridge.get(eid,set())
                if len(gs)!=1:continue
                gid=next(iter(gs));pid=identity(gid)
                pos=(p.get('position') or {}).get('abbreviation','')
                h=[r for r in by_player.get(gid,[]) if int(r['season'])>=2024]
                rush=any((numeric(r.get('carries')) or 0)>0 for r in h)
                qb1=bool(depth and depth['espn_player_id']==eid)
                status=p.get('status') or {};status=status.get('type',status.get('name','')) if isinstance(status,dict) else str(status)
                for key in FIELDS:
                    if not eligible(pos,key,qb1,rush):continue
                    k=[event['espn_event_id'],pid,key,'full_game'];row_id=sha(canonical(k))
                    vals=[(r,value(r,key)) for r in h];valid=[(r,v) for r,v in vals if v is not None][-10:]
                    reasons=[]
                    if norm(p.get('fullName'))!=norm(names.get((eid,gid))):reasons.append('INDEPENDENT_NAME_ID_MISMATCH')
                    if stamp(event['scheduled_kickoff'])<=stamp(freeze):reasons.append('KICKOFF_PASSED')
                    if len(valid)<2:reasons.append('INSUFFICIENT_OBSERVED_HISTORY')
                    if key=='tackles_assists':reasons.append('TACKLE_ACCOUNTING_NOT_INDEPENDENTLY_CERTIFIED')
                    if str(status).lower() in {'inactive','injured reserve','suspended','practice-squad'}:reasons.append('NONPARTICIPANT_OR_INACTIVE_ROSTER_STATUS')
                    for rec in (rr,dr if pos=='QB' else rr):
                        if rec and stamp(rec['source_received_at'])>stamp(freeze):reasons.append('FUTURE_ROLE_SOURCE')
                    for r,v in valid:
                        history_output.append({'player_stat_id':row_id,'player_id':pid,'market':key,
                            'game_id':r['game_id'],'game_date':r['game_date'],'period':'full_game','value':v,
                            'components':{f:numeric(r.get(f)) for f in FIELDS[key]},
                            'source_sha256':r['source_sha256'],'source_file':r['source_file'],
                            'source_available_at':r['source_available_at']})
                    players.append({'schema':VERSION,'player_stat_id':row_id,'game_id':event['espn_event_id'],
                        'game_id_namespace':'espn','player_id':pid,'espn_player_id':eid,'player':p.get('fullName'),
                        'normalized_market':key,'period':'full_game','team':team,'opponent':opp,'position':pos,
                        'event_start_at':event['scheduled_kickoff'],'feature_freeze_at':freeze,
                        'eligibility_status':'EXPECTED_STARTER' if qb1 else ('NONPARTICIPANT' if 'NONPARTICIPANT_OR_INACTIVE_ROSTER_STATUS' in reasons else 'ROLE_UNCERTAINTY'),
                        'confirmed_game_day_active':False,'historical_participant':bool(h),
                        'participation_status':'UNKNOWN_PARTICIPATION','conditional_on_appearance_only':True,
                        'identity_source_sha256':rr['sha256'],'role_source_sha256':dr['sha256'] if dr and pos=='QB' else None,
                        'history_sufficiency':len(valid),'model_input_ready':not reasons,
                        'missing_stat_rows':sum(v is None for _,v in vals),'abstention_reasons':sorted(set(reasons)),
                        'feature_reference':row_id,'line':None,'book':None})
    keys=[(p['game_id'],p['player_id'],p['normalized_market'],p['period']) for p in players]
    if len(keys)!=len(set(keys)):raise ValueError('DUPLICATE_CANONICAL_PLAYER_STAT')
    index={k:p['player_stat_id'] for k,p in zip(keys,players)}
    old_contracts=[json.loads(l) for l in verified(pin['tables']['original_contracts']['path'],pin['tables']['original_contracts']['sha256']).splitlines()]
    cross={c['candidate_id']:c.get('gsis_player_id') for c in old_contracts}
    contracts=[]
    for c in manifest['candidates']:
        key=market(c['stat']);gid=cross.get(c['candidate_id'])
        stat_id=index.get((c.get('event_id'),identity(gid),key,c['period'])) if gid else None
        # Exact original row embedded verbatim as a JSON object; its raw source bytes
        # and timestamps are referenced, never rewritten or interpreted as fresh.
        contracts.append({'schema':VERSION,'normalized_market':key,'player_stat_id':stat_id,
            'candidate_id':c['candidate_id'],'quote_id':c['quote_id'],
            'observation_origin':'PREVIOUS_IMMUTABLE_CAPTURE','new_offer':False,
            'original_source_manifest_sha256':OLD_SOURCE,'original_record':c})
    out=ROOT/'market_extension_v2_5_1'
    tackle_internal=[]
    defenders={p['player_id'] for p in players if p['normalized_market']=='tackles_assists'}
    for pid in sorted(defenders):
        for r in by_player.get(pid.removeprefix('gsis:'),[])[-10:]:
            tackle_internal.append({'player_id':pid,'game_id':r['game_id'],'game_date':r['game_date'],
                'period':'full_game','combined_total':None,'accounting_status':'UNVERIFIED_COMPONENT_SEMANTICS',
                'internal_components':{f:numeric(r.get(f)) for f in ('def_tackles_solo','def_tackles_with_assist','def_tackle_assists')},
                'source_available_at':r['source_available_at'],'source_sha256':r['source_sha256'],'source_file':r['source_file']})
    tables={'original_contracts':table(out,'original_contracts',contracts),
        'internal_tackle_evidence':table(out,'internal_tackle_evidence',tackle_internal),
        'paired_history':table(out,'paired_history',history_output),
        'crosswalk':table(out,'crosswalk',[{'quote_id':c['quote_id'],'candidate_id':c['candidate_id'],'player_stat_id':c['player_stat_id']} for c in contracts])}
    counts=[]
    for key in FIELDS:
        ps=[p for p in players if p['normalized_market']==key];cs=[c for c in contracts if c['normalized_market']==key]
        linked={c['player_stat_id'] for c in cs if c['player_stat_id']}
        for p in ps:p['original_contract_status']='AVAILABLE' if p['player_stat_id'] in linked else 'ORIGINAL_CONTRACT_UNAVAILABLE'
        counts.append({'market':key,'player_stat_rows':len(ps),'independently_forecastable':sum(p['model_input_ready'] for p in ps),
            'authentic_original_contracts':len(cs),'newly_collected_contracts':0,
            'missing_contract_player_stats':sum(p['player_stat_id'] not in linked for p in ps),
            'missing_feature_player_stats':sum(p['history_sufficiency']<2 for p in ps),
            'not_ready_player_stats':sum(not p['model_input_ready'] for p in ps)})
    tables['player_stats']=table(out,'player_stats',players)
    expanded={'schema':VERSION,'generated_at':now(),'feature_freeze_at':freeze,
        'implementation_sha256':sha(Path(__file__).read_bytes()),
        'previous_canonical_manifest':{'path':str(source_path),'sha256':OLD_SOURCE},
        'previous_feature_pin':{'path':str(old_path),'sha256':OLD_FEATURE},
        'taxonomy_migration':MIGRATION,'provider_inbound_mappings':PROVIDER_KEYS,
        'live_provider_requested_market_count':8,'new_sportsbook_requests':0,
        'source_evidence':evidence,'tables':tables,'coverage':counts,
        'new_public_source_receipts':acquired,
        'unmapped_contract_rows':sum(c['player_stat_id'] is None for c in contracts),
        'history_original_pregame_availability_verified':False,
        'release_authority':False,'status':'SHADOW_ONLY_SOURCE_EXTENSION',
        'limitations':['No documented provider targets/composite live keys; no fabricated offers',
            'Combined tackle credit accounting awaits independent official reconciliation',
            'No final game-day active evidence; all ready rows conditional on appearance',
            'Archived roster/depth evidence is not a fresh lineup confirmation',
            'Defensive snaps/role/opponent opportunity not authenticated by this extension',
            'Historical acquisition receipts support this prospective freeze, not historical point-in-time claims'],
        'handoff_consumers':{ws:str(out/'FEATURE_PIN.json') for ws in ('WS2','WS3','WS4','WS5','WS6')}}
    source_rec=unchanged(out/('EXPANDED_MANIFEST_'+sha(canonical(expanded))+'.json'),canonical(expanded))
    feature_pin={**expanded,'expanded_manifest':source_rec}
    receipt=unchanged(out/'FEATURE_PIN.json',canonical(feature_pin))
    assert verified(old_path,OLD_FEATURE)==old_bytes
    assert verified(source_path,OLD_SOURCE)==source_bytes
    print(json.dumps({'pin':receipt,'source':source_rec,'coverage':counts,'tables':tables,'unmapped_contract_rows':expanded['unmapped_contract_rows']},sort_keys=True))
    return feature_pin

if __name__=='__main__':build()
