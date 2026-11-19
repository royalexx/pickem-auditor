"""Original official history acquisition only: deliberately no sportsbook call."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
import sys,json,tempfile
root=Path.cwd()
sys.path.insert(0,str(root/'research/nhl_sog_transport'))
from scripts.c03_live_transport import capture_signed_live,verify_signed_capture
from v2.nhl_sog_pregame_schedule import official_games
from v2.nhl_sog_history_refresh import refresh,stamp
now=datetime.now(timezone.utc);day=now.astimezone(ZoneInfo('America/Toronto')).date().isoformat()
pool=root/'reports/v25_sog_source_cert_sprint/2026-11-13/signed_pr122_20261113T165907226991Z/original_signed_sources'
canonical_pool=pool
from v2.nhl_sog_local_sources import publish_bundle
from v2.nhl_sog_source_packets import persist_packet
pool=Path(tempfile.mkdtemp(prefix='nhl_original_capture_'))
# Discovery also captures original receipts with an actual short deadline.
cutoff=now+timedelta(minutes=50);bound=now+timedelta(hours=2)
def capture(url):
    rec=capture_signed_live(url,archive_root=pool,source_namespace='nhl_official',
        source_id='daily-history:'+day+':'+url.split('/v1/')[1],
        input_cutoff_at=stamp(cutoff),event_start_at=stamp(bound),timeout=15)
    persist_packet(canonical_pool,pool,rec)
    return rec,verify_signed_capture(rec,archive_root=pool,freeze=stamp(cutoff),event_start=stamp(bound))
r,d=capture('https://api-web.nhle.com/v1/schedule/'+day)
games=[g for g in official_games(r['source_url'],d,day) if g.get('gameState') in ('FUT','PRE') and datetime.fromisoformat(g['startTimeUTC'].replace('Z','+00:00'))>cutoff]
if not games:raise RuntimeError('NO_FUTURE_GAME_WITH_HISTORY_ACQUISITION_MARGIN')
bound=min(datetime.fromisoformat(g['startTimeUTC'].replace('Z','+00:00')) for g in games)
cutoff=min(cutoff,bound-timedelta(minutes=35))
players={};rosters={}
for team in sorted({g[t]['abbrev'] for g in games for t in ('homeTeam','awayTeam')}):
    rr,doc=capture('https://api-web.nhle.com/v1/roster/'+team+'/current');rosters[team]=rr
    for group,role in (('forwards','F'),('defensemen','D')):
        for item in doc.get(group,[]):
            pid=str(item['id'])
            if pid in players and players[pid]!=role:raise ValueError('ROSTER_POSITION_CONFLICT')
            players[pid]=role
result,receipt=refresh(players,pool=pool,capture=capture,cutoff=stamp(cutoff),
    event_start=stamp(bound),target_games={str(g['id']) for g in games},
    required_season=int(games[0]['season']),workers=8)
result,receipt=publish_bundle(canonical_pool,pool,result)
print('NHL_HISTORY_PREWARM',json.dumps({'receipt':receipt,'requested_players':len(players),
    'qualified_players':result['qualified_players'],'captured_players':len(result['player_records']),
    'final_games_captured':result['final_games_captured'],'failures':result['failures'][:12],
    'failure_count':len(result['failures']),'no_market_requests':True,'no_forecasts':True,
    'future_games':[g['id'] for g in games]},sort_keys=True))
