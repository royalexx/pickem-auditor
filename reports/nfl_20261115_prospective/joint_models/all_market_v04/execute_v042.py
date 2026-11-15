"""WS1-certified current-season history adapter; same existing WS4 simulator.

No source collection. The earlier v0.4.0 five-game forecasts remain immutable.
"""
import csv,io,json,pathlib,sys,datetime as dt
J=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(J))
import ws4_original_contract_adapter as ad
from all_market_v04 import execute as base
from all_market_v04.conditional import require
VERSION='ws4_all_market_v0.4.2'
MANIFEST='reports/nfl_20261115_prospective/market_extension_v2_5_1/EXPANDED_MANIFEST_1977685e911b2a9650afde55f5eb7b580d7f8fdc931bf39fad47b1c344c2a46b.json'
MANIFEST_SHA='1977685e911b2a9650afde55f5eb7b580d7f8fdc931bf39fad47b1c344c2a46b'


def current_history():
    root=J.parents[2];raw,sha=ad.checked(root/MANIFEST,MANIFEST_SHA);m=json.loads(raw)
    receipts=[];data={}
    for name in ('stats2026','games2026'):
        r=m['new_public_source_receipts'][name]
        b,h=ad.checked(root/r['raw_path'],r['sha256'])
        require(ad.parse_time(r['observed_received_at'])<ad.now(),'FUTURE_HISTORY_SOURCE')
        receipts.append(dict(source_uri=r['requested_url'],sha256=h,available_at=r['observed_received_at']))
        data[name]=list(csv.DictReader(io.StringIO(b.decode('utf-8-sig'))))
    valid=set()
    for g in data['games2026']:
        if g.get('season')!='2026' or g.get('game_type')!='REG':continue
        if not g.get('gameday') or not g.get('gametime') or not g.get('home_score') or not g.get('away_score'):continue
        # Only completed games on prior dates, plus a conservative 24h margin.
        start=ad.parse_time(g['gameday']+'T'+g['gametime']+':00+00:00')
        if start+dt.timedelta(hours=24)<ad.now():valid.add(g['game_id'])
    counts=('attempts','completions','carries','targets','receptions')
    yards=('passing_yards','rushing_yards','receiving_yards')
    rows=[]
    for r in data['stats2026']:
        if r['game_id'] not in valid or r.get('season_type')!='REG':continue
        row={k:r[k] for k in ('player_id','position','game_id','team')}
        row.update(season=2026,season_type='REG')
        for k in counts+yards:row[k]=int(float(r.get(k) or 0))
        require(all(row[k]>=0 for k in counts),'INVALID_CURRENT_HISTORY_COUNT')
        rows.append(row)
    require(len(rows)>1000,'CURRENT_HISTORY_JOIN_TOO_SMALL')
    return rows,receipts


def run():
    h,receipts=current_history();oldpar=base.parameterize;oldvalidate=base.sim.validate
    def parameterize(team,roster,ids,old_history):
        # Current 2026 same-team history replaces stale 2025 parameters.
        par,rejected=oldpar(team,roster,ids,h)
        par.update(historical_season=2026,current_source_receipts=receipts,
          source_manifest_sha256=MANIFEST_SHA,adapter_implementation_sha256=ad.digest(pathlib.Path(__file__).read_bytes()))
        return par,rejected
    def validate(payload):
        payload['events'][0]['source_receipts'].extend(receipts)
        payload['model_training_cutoff_at']=max(r['available_at'] for r in receipts)
        payload['input_manifest_sha256']=ad.digest(ad.canonical({k:v for k,v in payload.items() if k!='input_manifest_sha256'}))
        return oldvalidate(payload)
    base.parameterize=parameterize;base.sim.validate=validate;base.VERSION=VERSION
    base.HISTORY_DESCRIPTION='2024 team volumes and 2025 QB attempt-share priors; conditional allocation and yard marks use authenticated completed 2026 games'
    return base.run(draws=4096)

if __name__=='__main__':run()
