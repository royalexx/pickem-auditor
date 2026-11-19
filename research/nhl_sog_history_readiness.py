"""Verify live acquired source/model readiness WITHOUT offers or forecast freeze."""
from pathlib import Path
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import sys,json,hashlib
root=Path.cwd();sys.path.insert(0,str(root/'research/nhl_sog_transport'))
from v2.nhl_sog_history_refresh import load_current,canon
from v2.nhl_sog_daily_history_producer import independent_verify_observation_lineage
from v2.nhl_sog_daily_math import fit_model
from v2.nhl_sog_daily_ledger import law,KINDS
pool=root/'reports/v25_sog_source_cert_sprint/2026-11-13/signed_pr122_20261113T165907226991Z/original_signed_sources'
now=datetime.now(timezone.utc);day=now.astimezone(ZoneInfo('America/Toronto')).date().isoformat()
d,ref=load_current(pool,day=day,now=now)
from v2.nhl_sog_local_sources import open_history_sources
pool=open_history_sources(pool,d)
own=d['signed_observation_contracts_by_player'];cat=d['player_records']
results=[]
for group in ('F','D'):
    candidates=sorted(pid for pid,rs in own.items() if len(rs)>=5 and cat[pid]['official_position_group']==group)
    if not candidates:raise RuntimeError('NO_QUALIFIED_'+group)
    pid=candidates[0]
    peers=sorted(((p,rs) for p,rs in own.items() if p!=pid and len(rs)>=10 and cat[p]['official_position_group']==group),key=lambda x:(-len(x[1]),x[0]))[:20]
    freeze=datetime.now(timezone.utc).isoformat();event=d['event_start']
    verified=lambda rs:[independent_verify_observation_lineage(x,archive_root=pool,freeze=freeze,event_start=event) for x in rs]
    model=fit_model(verified(own[pid]),verified([x for p,rs in peers for x in rs[-10:]]),archive_root=pool,
        player_id=pid,position_group=group,input_freeze_at=freeze,event_start_at=event,
        target_event_id='SOURCE_READINESS_ONLY_NO_FORECAST',current_team_id='NO_MARKET_CONTRACT')
    for kind in KINDS.values():law(model,kind)
    results.append({'position':group,'source_player_id':pid,'own_games':model['own_played_games'],
        'peer_players':model['peer_players'],'peer_games':model['peer_games'],'five_count_laws':'PASS'})
report={'source_manifest':ref,'qualified_players':d['qualified_players'],'checks':results,
    'evidence_class':'LIVE_PRIOR_SOURCE_AND_MODEL_READINESS_ONLY','no_market_request':True,'frozen_forecasts':0}
raw=canon(report);dest=root/'reports/nhl_sog_repair_20261119'/('live_readiness_'+hashlib.sha256(raw).hexdigest()+'.json');dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
print('LIVE_HISTORY_MODEL_READINESS',json.dumps({'report':str(dest.relative_to(root)),'sha256':hashlib.sha256(raw).hexdigest(),**report},sort_keys=True))
