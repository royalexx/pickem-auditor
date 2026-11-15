"""Authenticated WS1 JSONL -> unchanged O-family, conditional research scenario.

No collector. No participation calibration: scenario p=1 means conditioning on
all modeled roster members appearing, and QB1 starting, never an active claim.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict, Counter
import csv, json, math
import numpy as np
from . import models as m

PIN='35a1bf7fe16acca1e115c7be7bcad2c2464ec27cdf7e799df4f2b31adba24c2a'
MANIFEST='5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71'
VERSION='ws3-ws1-historical-adapter-v1'

def team_id(value):
    # ESPN uses LAR; nflverse weekly/schedule evidence uses LA.
    return {'LAR':'LA'}.get(value,value)

def checked(root,path,digest):
    p=(Path(root)/path).resolve()
    m.require(p.is_relative_to(Path(root).resolve()),'path_escape')
    b=p.read_bytes();m.require(m.sha(b)==digest,'hash_mismatch:'+path)
    return b

def numeric(x):
    try: v=float(x)
    except (ValueError,TypeError): return None
    return v if math.isfinite(v) else None

def authenticate(root):
    raw=checked(root,'reports/nfl_20261115_prospective/FORECAST_FEATURE_PIN.json',PIN)
    pin=m.strict_json(raw)
    native=m.strict_json(checked(root,pin['canonical_source_manifest_path'],MANIFEST))
    checked(root,pin['archived_history_source_manifest_path'],pin['archived_history_manifest_file_sha256'])
    checked(root,pin['original_handoff_pin_path'],pin['original_handoff_pin_sha256'])
    checks=[]
    tables={}
    for name,d in pin['tables'].items():
        b=checked(root,d['path'],d['sha256'])
        tables[name]=[m.strict_json(x) for x in b.splitlines()]
        m.require(len(tables[name])==d['rows'],'row_count')
        checks.append(d)
    for d in pin['history_evidence_files']:
        checked(root,d['path'],d['sha256']); checks.append(d)
        m.require(m.stamp(d['source_first_verified_available_at'])<=m.stamp(pin['feature_freeze_at']),'history_source_future')
    for d in pin['new_raw_source_receipts'].values():
        checked(root,d['raw_path'],d['sha256']);checks.append(d)
        m.require(m.stamp(d['observed_received_at'])<=m.stamp(pin['feature_freeze_at']),'receipt_future')
    for d in native['sources'].values():
        checked(root,'reports/nfl_20261115_prospective/'+d['archive_path'],d['sha256'])
        m.require(m.stamp(d['source_received_at'])<=m.stamp(native['input_freeze_at']),'native_source_future')
        checks.append(d)
    m.require(len(tables['original_contracts'])==1845,'denominator')
    return pin,native,tables,checks

def build(root,now):
    m.require(m.sha(Path(m.__file__).read_bytes())=='54175541f90ac68b36afd9d0766b790dbacb0a6e01903627e5fafb404ff157cb','model_code_binding')
    pin,native,t,checks=authenticate(root)
    freeze=pin['feature_freeze_at'];m.require(m.stamp(freeze)<=m.stamp(now),'freeze_future')
    raw=pin['new_raw_source_receipts']
    def csvrows(name):
        return list(csv.DictReader(checked(root,raw[name]['raw_path'],raw[name]['sha256']).decode().splitlines()))
    # Explicit ESPN -> GSIS bridge, never string equality across namespaces.
    bridge=defaultdict(set);pfr=defaultdict(set)
    for r in csvrows('players'):
        if r.get('espn_id') and r.get('gsis_id'):bridge[r['espn_id'].removesuffix('.0')].add(r['gsis_id'])
        if r.get('pfr_id') and r.get('gsis_id'):pfr[r['pfr_id']].add(r['gsis_id'])
    schedule={}
    target_schedule={}
    for r in csvrows('games2026'):
        if r['season']!='2026' or r['game_type']!='REG':continue
        if r['gameday']=='2026-11-15':target_schedule[r['espn']]=r
        if r['gameday']<'2026-11-15' and numeric(r['result']) is not None:schedule[r['game_id']]=r
    groups=defaultdict(list)
    target_week=min(int(g['week']) for g in target_schedule.values())
    same_week_excluded=0
    for r in csvrows('stats2026'):
        if r['season']=='2026' and r['season_type']=='REG' and r['game_id'] in schedule:
            if int(r['week'])>=target_week:
                same_week_excluded+=1
                continue
            groups[r['game_id'],r['team']].append(r)
    teams=[];team_exclusions=[]
    for (gid,team),rs in groups.items():
        g=schedule[gid];opp=g['away_team'] if team==g['home_team'] else g['home_team']
        m.require(team in (g['home_team'],g['away_team']),'historical_team_conflict')
        # Complete weekly team totals from actual count columns, including sacks
        # suffered. Missing cells invalidate the team-game; never impute zeros.
        vals=[[numeric(r[k]) for r in rs] for k in ('attempts','carries','sacks_suffered')]
        if any(v is None for col in vals for v in col):
            team_exclusions.append({'game_id':gid,'team':team,'reason':'missing_actual_team_count'});continue
        pa,ru,sa=map(sum,vals)
        m.require(all(v>=0 and float(v).is_integer() for v in (pa,ru,sa)),'invalid_team_count')
        teams.append(dict(game_id=gid,team=team,opponent=opp,season=2026,week=int(g['week']),
            end_at=g['gameday']+'T23:59:59Z',source_id=raw['stats2026']['sha256'],
            plays=pa+ru+sa,pass_attempts=pa,rush_attempts=ru,sacks=sa,pace_seconds=None))
    tm={(h['game_id'],h['team']):h for h in teams}
    players={};history_exclusions=Counter({'same_week_raw_rows_excluded_by_frozen_model_gate':same_week_excluded})
    for h in t['player_history_last10_by_contract']:
        key=(h['game_id'],h['team'])
        if key not in tm:history_exclusions['no_complete_team_accounting']+=1;continue
        m.require(h['game_date']<'2026-11-15','target_history')
        m.require(m.stamp(h['source_available_at'])<=m.stamp(freeze),'history_future')
        # Positive recorded production establishes appearance. A zero-stat row
        # alone does not. Defense snap joins require separate exact evidence.
        evidence=any((numeric(h.get(k)) or 0)>0 for k in ('attempts','carries','targets','receptions','def_tackles_solo','def_tackles_with_assist','def_tackle_assists'))
        if not evidence:history_exclusions['appearance_unestablished']+=1;continue
        row={k:None for k in m.PLAYER_FIELDS}
        row.update({k:h[k] for k in ('game_id','team','position')})
        row.update(player_id=h['gsis_id'],season=2026,week=tm[key]['week'],end_at=tm[key]['end_at'],source_id=h['source_sha256'],state='played')
        for k,src in {'pass_attempts':'attempts','targets':'targets','receptions':'receptions','receiving_yards':'receiving_yards','carries':'carries','rushing_yards':'rushing_yards','completions':'completions','passing_yards':'passing_yards','solo':'def_tackles_solo','with_assist':'def_tackles_with_assist','tackle_assists':'def_tackle_assists'}.items():row[k]=numeric(h.get(src))
        pk=(row['game_id'],row['player_id'])
        m.require(pk not in players or players[pk]==row,'conflicting_duplicate_history')
        players[pk]=row
    events=[]
    for e in t['events']:
        if m.stamp(e['scheduled_kickoff'])<=m.stamp(now):continue
        if m.stamp(e['scheduled_kickoff']).date().isoformat()!=m.DAY:continue
        g=target_schedule.get(e['espn_event_id'])
        m.require(g is not None and (g['home_team'],g['away_team'])==(team_id(e['home']),team_id(e['away'])),'event_namespace_conflict:'+str(e['espn_event_id']))
        events.append(dict(game_id=e['espn_event_id'],home=team_id(e['home']),away=team_id(e['away']),season=2026,week=int(g['week']),event_start=e['scheduled_kickoff'],source_id=e['source_sha256']))
    em={e['game_id']:e for e in events}
    availability={(r['event_id'],r['player_id']):r for r in t['pregame_roster_availability']}
    contracts=[];roster={};rejections={}
    for c in t['original_contracts']:
        c={**c}
        original_c={**c}
        c['team']=team_id(c['team']);c['opponent']=team_id(c['opponent'])
        reasons=list(c['abstention_reasons'])
        if c['event_id'] not in em:reasons.append('KICKOFF_PASSED_OR_UNVERIFIED_EVENT')
        if c.get('event_start_at') and m.stamp(c['event_start_at']).date().isoformat()!=m.DAY:reasons.append('ORIGINAL_MODEL_UTC_EVENT_DAY_UNSUPPORTED')
        if bridge.get(c['player_id'])!={c['gsis_player_id']}:reasons.append('ESPN_GSIS_IDENTITY_CONFLICT')
        if not c['status']['CONDITIONAL_ON_APPEARANCE_FORECASTABLE']:reasons.append('WS1_EXCLUDED')
        if reasons:rejections[c['candidate_id']]=reasons;continue
        e=em[c['event_id']]
        m.require(c['team'] in (e['home'],e['away']) and c['opponent'] in (e['home'],e['away']) and c['team']!=c['opponent'],'contract_team_conflict')
        m.require(c['event_start_at']==e['event_start'],'kickoff_conflict')
        a=availability[c['event_id'],c['player_id']]
        expected=a['expected_qb_starter_source_backed'] is True
        if c['position']=='QB' and not expected:rejections[c['candidate_id']]=['QB_STARTER_NOT_VERIFIED'];continue
        m.require(m.stamp(c['original_quote_observed_at'])<=m.stamp(freeze),'quote_future')
        r=dict(game_id=c['event_id'],team=c['team'],player_id=c['gsis_player_id'],position=c['position'],source_id=a['roster_receipt_sha256'],status='uncertain',participation_probability=1.,expected_starter=expected,starter_probability=1. if expected else None)
        roster[r['game_id'],r['player_id']]=r
        stat=c['stat']
        if stat=='rush attempts':stat='qb rushing attempts' if c['position']=='QB' else 'carries'
        if stat=='rushing yards' and c['position']=='QB':stat='qb rushing yards'
        contracts.append(dict(contract_id=c['candidate_id'],game_id=c['event_id'],team=c['team'],player_id=c['gsis_player_id'],stat=stat,line=c['line'],period=c['period'],source_id=c['source_sha256'],dnp_policy='void',frozen_60_40=None,market=None,comparison_probabilities=None,quote_id=c['quote_id'],book=c['book'],over_odds=c.get('over_odds'),under_odds=c.get('under_odds'),original_contract=original_c))
    packet=dict(manifest={'training_cutoff_at':freeze,'input_freeze_at':freeze},manifest_sha256=PIN,forecast_at=now,events=events,team_history=teams,player_history=list(players.values()),roster=list(roster.values()),contracts=contracts)
    m.validate(packet)
    return packet,dict(version=VERSION,checks=checks,team_exclusions=team_exclusions,history_exclusions=dict(history_exclusions),source_denominator=1845,rejections=rejections,originals=t['original_contracts'],training_provenance={'team':'2026 authenticated weekly attempts + carries + sacks_suffered; accounting plays derived from observed counts','player':'WS1 last10 deduplicated by GSIS game/player; only 2026 complete team exposures and positive recorded participation','routes':'unavailable','defense':'exact snap/component join unavailable; O4 must abstain'},conditional_assumption='All modeled roster members appear; expected QB1 starts. Scenario weights are assumptions, not calibrated availability. Product DNP rules unverified; probabilities describe statistics only.')

def audit_report(report):
    checked_n=0
    for row in report['rows']:
        if row['status']!='forecast':continue
        d=row['predictive_distribution_conditional'];v=np.asarray(d['values']);p=np.asarray(d['masses']);line=row['contract']['line']
        m.require(abs(p.sum()-1)<1e-10 and (p>=0).all() and (v==np.rint(v)).all(),'invalid_predictive_mass')
        mu=float(v@p);var=float(((v-mu)**2)@p)
        m.require(abs(mu-row['workload_conditional']['mean'])<1e-9,'mean_reconstruction')
        m.require(abs(var-row['workload_conditional']['sd']**2)<1e-8,'variance_reconstruction')
        for key,mask in [('over',v>line),('under',v<line),('push',v==line)]:
            m.require(abs(float(p[mask].sum())-row['probabilities_conditional'][key])<1e-10,'OUP_reconstruction')
        row['expected_stat']=mu;row['variance_stat']=var
        checked_n+=1
    return {'mass_mean_variance_push_reconstructions':checked_n,'independent_method':'mass summation vs simulation sample moments; sequential audit by same agent'}

def execute(root,canary=False):
    now=datetime.now(timezone.utc).isoformat();p,meta=build(root,now)
    if canary:
        qbs=[c for c in p['contracts'] if c['stat']=='pass attempts']
        m.require(qbs,'no_authentic_canary')
        c=qbs[0];p['contracts']=[c];p['events']=[e for e in p['events'] if e['game_id']==c['game_id']]
        p['roster']=[r for r in p['roster'] if r['game_id']==c['game_id']]
    report=m.OpportunityModel(p,8192).run()
    if canary:m.require(any(r['status']=='forecast' and r['model']==m.MODELS[2] for r in report['rows']),'no_genuine_O3_canary')
    for row in report['rows']:
        if row['status']=='forecast':
            row['conditioning']=meta['conditional_assumption']
            row['unconditional_stat_probabilities']=None;row['dnp_probability']=None
            row['dnp_settlement']='UNVERIFIED_PRODUCT_TERMS; statistical conditional forecast only'
    if not canary:
        present={(r['contract']['contract_id'],r['model']) for r in report['rows']}
        for c in meta['originals']:
            for model in m.MODELS:
                if (c['candidate_id'],model) not in present:
                    report['rows'].append(dict(contract={'contract_id':c['candidate_id'],'stat':c['stat'],'original_contract':c},model=model,status='abstain',reason_codes=meta['rejections'].get(c['candidate_id'],['ADAPTER_EXCLUSION'])))
    report['adapter_audit']={k:v for k,v in meta.items() if k!='originals'}
    report['numerical_audit']=audit_report(report)
    report['adapter_packet_sha256']=m.sha(m.canonical(p))
    report['coverage']=[{'model':model,'event_id':event,'market':market,'status':status,'n':n}
        for (model,event,market,status),n in sorted(Counter((r['model'],str(r['contract'].get('original_contract',{}).get('event_id',r['contract'].get('game_id'))),r['contract']['stat'],r['status']) for r in report['rows']).items())]
    report['original_contracts_attempted']=1 if canary else 1845
    report['model_counts']=dict(Counter(r['model'] for r in report['rows'] if r['status']=='forecast'))
    report['forecast_completed_at']=datetime.now(timezone.utc).isoformat()
    for e in p['events']:m.require(m.stamp(report['forecast_completed_at'])<m.stamp(e['event_start']),'completed_after_kickoff')
    report['stage']='canary' if canary else 'expanded'
    receipt=m.freeze_output(report,Path(root)/'reports/nfl_20261115_prospective/opportunity_models/activation_v1')
    with (Path(receipt['directory'])/'adapter_packet.json').open('xb') as f:f.write(m.canonical(p))
    print(json.dumps({'receipt':receipt,'counts':report['model_counts'],'numerical_audit':report['numerical_audit'],'team_distributions':len(report['team_opportunities']),'packet_teams':len(p['team_history']),'packet_players':len(p['player_history'])}))
    return receipt
