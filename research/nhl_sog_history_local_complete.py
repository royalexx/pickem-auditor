"""Complete a history checkpoint from original captured bytes; no profile/log refetch.

The acquisition worker may still be filling other players. Missing captures are
explicit exclusions, rather than a global barrier for already captured players.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
import sys,json,hashlib,re
root=Path.cwd();sys.path.insert(0,str(root/'research/nhl_sog_transport'))
from scripts.c03_live_transport import capture_signed_live,verify_signed_capture
from v2.nhl_sog_history_refresh import refresh,stamp
from v2.nhl_sog_pregame_schedule import official_games
pool=root/'reports/v25_sog_source_cert_sprint/2026-11-13/signed_pr122_20261113T165907226991Z/original_signed_sources'
canonical_pool=pool
from v2.nhl_sog_local_sources import stage_pool,copy_members,publish_bundle
pool=stage_pool(canonical_pool)
now=datetime.now(timezone.utc);day=now.astimezone(ZoneInfo('America/Toronto')).date().isoformat()
cutoff=now+timedelta(minutes=35);bound=now+timedelta(hours=2)
receipts={}
for path in sorted((pool/'c03_collector_receipts').glob('*.json')):
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=path.stem:raise ValueError('CAPTURE_PROOF_HASH_DRIFT')
    fields=json.loads(raw)['receipt_fields'];url=fields['source_url']
    r=dict(fields,transport_attestation='collector_signed_tls_bytes_v1',collector_proof_sha256=path.stem,
           collector_proof_archive_path='c03_collector_receipts/'+path.name)
    prior=receipts.get(url)
    if prior is None or r['received_at']>prior['received_at']:receipts[url]=r
cache={}
def original(url):
    if url not in receipts:raise ValueError('ORIGINAL_CAPTURE_PENDING')
    rec=receipts[url]
    if '/game-log/' in url and not timedelta(0)<=now-datetime.fromisoformat(rec['received_at'].replace('Z','+00:00'))<=timedelta(hours=6):
        raise ValueError('CURRENT_GAMELOG_CAPTURE_PENDING')
    doc=verify_signed_capture(rec,archive_root=pool,freeze=stamp(cutoff),event_start=stamp(bound))
    return rec,doc
r,schedule=original('https://api-web.nhle.com/v1/schedule/'+day)
games=[g for g in official_games(r['source_url'],schedule,day) if g.get('gameState') in ('FUT','PRE')]
if not games:raise ValueError('NO_CERTIFIED_FUTURE_GAMES')
bound=min(datetime.fromisoformat(g['startTimeUTC'].replace('Z','+00:00')) for g in games)
cutoff=min(cutoff,bound-timedelta(minutes=35));players={}
for team in sorted({g[t]['abbrev'] for g in games for t in ('homeTeam','awayTeam')}):
    _,roster=original('https://api-web.nhle.com/v1/roster/'+team+'/current')
    for key,group in (('forwards','F'),('defensemen','D')):
        for p in roster.get(key,[]):players[str(p['id'])]=group
# Preverify cached original profiles/logs once. Finals can reuse a real prior
# signed FINAL receipt or capture new current official bytes, never sign old bytes.
for pid in sorted(players):
    for url in ('https://api-web.nhle.com/v1/player/'+pid+'/landing',
        'https://api-web.nhle.com/v1/player/'+pid+'/game-log/'+str(games[0]['season'])+'/2'):
        try:cache[url]=original(url)
        except (ValueError,OSError):pass
for url,rec in receipts.items():
    if '/gamecenter/' in url and url.endswith('/landing'):
        try:
            pair=original(url)
            if pair[1].get('gameState') in ('OFF','FINAL'):cache[url]=pair
        except (ValueError,OSError):pass
new_finals=[]
def capture(url):
    if url in cache:return cache[url]
    if '/gamecenter/' not in url:raise ValueError('ORIGINAL_PROFILE_OR_LOG_PENDING')
    rec=capture_signed_live(url,archive_root=canonical_pool,source_namespace='nhl_official',
        source_id='history-complete:'+day+':'+url.split('/v1/')[1],input_cutoff_at=stamp(cutoff),
        event_start_at=stamp(bound),timeout=15)
    copy_members(canonical_pool,pool,[rec['archive_path'],rec['collector_proof_archive_path']])
    doc=verify_signed_capture(rec,archive_root=pool,freeze=stamp(cutoff),event_start=stamp(bound))
    new_finals.append(rec['collector_proof_sha256']);return rec,doc
result,receipt=refresh(players,pool=pool,capture=capture,cutoff=stamp(cutoff),event_start=stamp(bound),
    target_games={str(g['id']) for g in games},workers=8,required_season=int(games[0]['season']))
result,receipt=publish_bundle(canonical_pool,pool,result)
print('HISTORY_LOCAL_CHECKPOINT_COMPLETED',json.dumps({'receipt':receipt,'requested_players':len(players),
    'qualified_players':result['qualified_players'],'captured_players':len(result['player_records']),
    'final_games_captured':result['final_games_captured'],'failure_count':len(result['failures']),
    'failure_examples':result['failures'][:8],'new_final_receipts':len(new_finals),
    'profile_log_network_requests':0,'no_market_requests':True,'no_forecasts':True},sort_keys=True))
