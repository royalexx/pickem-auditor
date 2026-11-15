"""Independent settlement parsing through the unchanged canonical WS1 source adapter.

No outcome contributes to pregame identity, eligibility, model fitting or forecasting.
"""
from dataclasses import asdict
from datetime import datetime,timezone
import gzip
import json
from pathlib import Path
from urllib.request import Request,urlopen
from v2.nba_ws1.store import Receipt,instant,digest
from v2.nba_ws1.adapters import espn_boxscore_records
from v2.nba_ws1.capture import BASE,now
from v2.nba_joint.forecast import freeze
from .evidence import validate_receipt


def settle_original(ledger,raw,receipt):
    receipt.verify(raw);game=ledger['game'];gid=game['game_id']
    if receipt.source!=BASE+'/summary?event='+gid.split(':')[-1]:raise ValueError('SETTLEMENT_SOURCE_GAME_IDENTITY')
    if instant(ledger['input_freeze_at'])>=instant(game['event_start_at']):raise ValueError('RETROSPECTIVE_CAPTURE_NOT_ORIGINAL')
    if instant(receipt.observed_at)<=instant(game['event_start_at']):raise ValueError('SETTLEMENT_BEFORE_START')
    d=json.loads(raw);comp=d['header']['competitions'][0]
    if 'espn:game:'+str(comp['id'])!=gid:raise ValueError('SETTLEMENT_GAME_MISMATCH')
    if comp.get('status',{}).get('type',{}).get('completed') is not True or comp['status']['type'].get('name')!='STATUS_FINAL':raise ValueError('OFFICIAL_FINAL_NOT_AVAILABLE')
    if instant(comp['date'])!=instant(game['event_start_at']):raise ValueError('SETTLEMENT_SCHEDULE_CHANGE_REQUIRES_REVIEW')
    teams={'espn:team:'+str(c['team']['id']) for c in comp['competitors']}
    if teams!={game['home_team_id'],game['away_team_id']}:raise ValueError('SETTLEMENT_TEAM_IDENTITY')
    records=espn_boxscore_records(d,receipt);actual={};rejected=[]
    for record in records:
        p=record.data;key=(p['player_id'],p['team_id'])
        if key in actual:raise ValueError('DUPLICATE_SETTLEMENT_PLAYER')
        actual[key]=p
    candidates=ledger['participation']['rows'];seen=set();rows=[]
    for p in candidates:
        key=(p['player_id'],p['team_id']);seen.add(key);obs=actual.get(key)
        if obs is None:state='UNRESOLVED_NOT_LISTED'
        elif obs['participation']=='played':state='PLAYED'
        elif obs['participation']=='dnp':state='EXPLICIT_DNP'
        else:state='UNKNOWN_BOX_STATUS'
        rows.append(dict(player_id=key[0],team_id=key[1],game_id=gid,status=state,actual=obs,
            pregame_eligibility=p.get('eligibility'),pregame_P0=p.get('P0_probability'),
            participation_scored=False,reason='NO_VALIDATED_OR_ELIGIBILITY_QUALIFIED_PARTICIPATION_FORECAST'))
    missed=[p for k,p in actual.items() if k not in seen and p['participation']=='played']
    return dict(schema='NBAPhase7OfficialSettlement/1',game=game,source_receipt=asdict(receipt),candidate_rows=rows,missed_actual_appearances=missed,
        denominator=dict(original_candidates=len(rows),verified_played=sum(r['status']=='PLAYED' for r in rows),explicit_DNP=sum(r['status']=='EXPLICIT_DNP' for r in rows),
            unresolved=sum(r['status'] in ('UNRESOLVED_NOT_LISTED','UNKNOWN_BOX_STATUS') for r in rows),missed_actual_appearances=len(missed),participation_scored=0,stat_forecasts_scored=0),
        provider='ESPN canonical NBA final summary; independently retrieved settlement source, not a league-native identity substitute',
        review_status='requires independent reviewer and source parity; parser execution alone is not approval')


def settle_slot(slot_root,output):
    root=Path(slot_root);out=Path(output);out.mkdir(parents=True,exist_ok=False)
    try:
        first=json.loads((root/'FIRST_CAPTURE.json').read_text())
        if first['receipt_kind']!='original_capture':raise ValueError('FIXTURE_NOT_SETTLEABLE_AS_REAL')
        path=(root/first['attempt']/'game_day_ledger.json').resolve()
        if not path.is_relative_to(root.resolve()):raise ValueError('CAPTURE_PATH_ESCAPE')
        if digest(path.read_bytes())!=first['ledger_sha256']:raise ValueError('FROZEN_LEDGER_HASH_CHANGED')
        ledger=json.loads(path.read_text());game=ledger['game']
        if datetime.now(timezone.utc)<=instant(game['event_start_at']):raise ValueError('GAME_NOT_STARTED')
        url=BASE+'/summary?event='+game['game_id'].split(':')[-1]
        with urlopen(Request(url,headers={'User-Agent':'pickem-phase7-independent-settlement/1'}),timeout=20) as response:raw=response.read()
        receipt=Receipt.capture(raw,source=url,observed_at=now(),origin='original_capture')
        with (out/'official_raw.json.gz').open('xb') as f:f.write(gzip.compress(raw,mtime=0))
        freeze(out/'source_receipt.json',asdict(receipt));result=settle_original(ledger,raw,receipt)
    except Exception as exc:result=dict(status='BLOCKED-BY-DATA',reason=type(exc).__name__+':'+str(exc),settled=0,scored=0)
    freeze(out/'settlement.json',result);return result


def market_settlement(contract,observation):
    if contract['game_id']!=observation['game_id'] or contract['player_id']!=observation['player_id'] or contract['team_id']!=observation['team_id']:raise ValueError('ORIGINAL_CONTRACT_IDENTITY_MISMATCH')
    if contract.get('period')!='full_game_including_overtime':raise ValueError('UNSUPPORTED_OR_UNSPECIFIED_PERIOD')
    if observation['participation']=='dnp':
        if contract.get('payout_terms',{}).get('dnp')!='void':raise ValueError('DNP_SETTLEMENT_TERMS_UNAVAILABLE')
        return 'void'
    if observation['participation']!='played':raise ValueError('PARTICIPATION_UNRESOLVED')
    value=observation['stats'].get(contract['stat'])
    if value is None:raise ValueError('SETTLEMENT_STAT_UNAVAILABLE')
    return 'over' if value>contract['line'] else 'under' if value<contract['line'] else 'push'


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--slot-root',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    print(json.dumps(settle_slot(a.slot_root,a.output),sort_keys=True))

if __name__=='__main__':main()
