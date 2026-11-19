"""Acquire original official prior-game evidence now; never backdate availability.

No bookmaker requests, inference, final target statistics, or old-file mutation.
Uses the existing signed transport and independent historical importer.
"""
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone,timedelta
from pathlib import Path
import hashlib,json,re
from .nhl_sog_official_history_producer import import_signed_official_history


def stamp(d):return d.isoformat().replace('+00:00','Z')
def utc(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def canon(d):return json.dumps(d,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def refresh(players,*,pool,capture,cutoff,event_start,target_games=(),workers=4):
    """players maps official roster ID to F/D; one immutable batch, typed exclusions."""
    pool=Path(pool);cache={};logs={};profiles={};failures=[]
    def get(url):
        r,d=capture(url)
        if utc(r['received_at'])>utc(cutoff):raise ValueError('SOURCE_AFTER_REFRESH_CUTOFF')
        return r,d
    def player_job(pid,group):
        p,d=get('https://api-web.nhle.com/v1/player/'+pid+'/landing')
        if str(d.get('playerId'))!=pid:raise ValueError('PROFILE_ID_MISMATCH')
        actual='D' if d.get('position')=='D' else 'F' if d.get('position') in ('C','L','R','LW','RW') else None
        if actual!=group:raise ValueError('PROFILE_ROSTER_POSITION_MISMATCH')
        season=d.get('currentTeamRosterSeason') or d.get('featuredStats',{}).get('season')
        # Season comes from authoritative profile seasonTotals if feature wrapper differs.
        seasons=[x.get('season') for x in d.get('seasonTotals',[]) if x.get('gameTypeId')==2 and x.get('leagueAbbrev')=='NHL']
        if seasons:season=max(int(x) for x in seasons)
        if not re.fullmatch(r'\d{8}',str(season)):raise ValueError('OFFICIAL_SEASON_UNAVAILABLE')
        r,doc=get('https://api-web.nhle.com/v1/player/'+pid+'/game-log/'+str(season)+'/2')
        rows=doc.get('gameLog')
        if not isinstance(rows,list) or not rows:raise ValueError('EMPTY_OFFICIAL_GAMELOG')
        if any(str(x.get('gameId')) in target_games for x in rows):
            raise ValueError('TARGET_GAME_IN_HISTORY')
        for x in rows:
            day=x.get('gameDate')
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(day)) or day>=utc(event_start).date().isoformat():
                raise ValueError('NON_PRIOR_GAME_DATE')
        return pid,group,p,r,rows
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fs={ex.submit(player_job,str(pid),g):str(pid) for pid,g in sorted(players.items())}
        for f in as_completed(fs):
            try:
                pid,g,p,r,rows=f.result();profiles[pid]=p;logs[pid]=(g,r,rows)
            except Exception as e:failures.append({'player_id':fs[f],'stage':'PROFILE_OR_LOG','reason':type(e).__name__+':'+str(e)[:120]})
    gids=sorted({str(x['gameId']) for _,_,rows in logs.values() for x in rows})
    def final_job(gid):
        r,d=get('https://api-web.nhle.com/v1/gamecenter/'+gid+'/landing')
        if str(d.get('id'))!=gid or d.get('gameState') not in ('OFF','FINAL'):
            raise ValueError('PRIOR_GAME_NOT_FINAL')
        return gid,r
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fs={ex.submit(final_job,g):g for g in gids}
        for f in as_completed(fs):
            try:g,r=f.result();cache[g]=r
            except Exception as e:failures.append({'game_id':fs[f],'stage':'FINAL','reason':type(e).__name__+':'+str(e)[:120]})
    own={};catalog={}
    for pid,(group,log,rows) in sorted(logs.items()):
        try:
            entries=import_signed_official_history(player_id=pid,position_group=group,
                gamelog_receipt=log,player_profile_receipt=profiles[pid],completed_game_receipts=cache,
                archive_root=pool,input_freeze_at=cutoff,event_start_at=event_start)
            # Reverify the raw original row chronology and every HMAC downstream.
            entries.sort(key=lambda x:(json.loads((pool/x['observation_receipt']['archive_path']).read_bytes())['source_game_log_row']['gameDate'],
                json.loads((pool/x['observation_receipt']['archive_path']).read_bytes())['event_id']))
            own[pid]=entries;catalog[pid]={'official_position_group':group,'official_team':None}
        except Exception as e:failures.append({'player_id':pid,'stage':'SIGNED_IMPORT','reason':type(e).__name__+':'+str(e)[:120]})
    result={'schema':'nhl_sog_current_signed_history/1','created_at':stamp(datetime.now(timezone.utc)),
        'acquisition_semantics':'new_actual_receipts_for_prior_final_games_not_historical_pregame_provenance',
        'signed_observation_contracts_by_player':own,'player_records':catalog,
        'requested_players':len(players),'qualified_players':sum(len(x)>=5 for x in own.values()),
        'final_games_captured':len(cache),'failures':sorted(failures,key=lambda x:json.dumps(x,sort_keys=True)),
        'cutoff':cutoff,'event_start':event_start,'target_games_excluded':sorted(target_games)}
    raw=canon(result);digest=hashlib.sha256(raw).hexdigest()
    dest=pool/'daily_history_manifests'/(digest+'.json');dest.parent.mkdir(parents=True,exist_ok=True)
    try:
        with dest.open('xb') as f:f.write(raw)
    except FileExistsError:
        if dest.read_bytes()!=raw:raise ValueError('HISTORY_MANIFEST_MUTATED')
    return result,{'path':str(dest),'sha256':digest}


def load_current(pool,*,day,now):
    """Latest pregame evidence batch, age <=6h; no stale fallback to limited cohort."""
    choices=[]
    for p in (Path(pool)/'daily_history_manifests').glob('*.json'):
        raw=p.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=p.stem:raise ValueError('HISTORY_MANIFEST_HASH_DRIFT')
        d=json.loads(raw);created=utc(d['created_at'])
        from zoneinfo import ZoneInfo
        if created.astimezone(ZoneInfo('America/Toronto')).date().isoformat()==day and timedelta(0)<=now-created<=timedelta(hours=6):
            choices.append((created,p,d))
    if not choices:raise ValueError('NO_FRESH_SIGNED_HISTORY_BATCH')
    _,p,d=max(choices,key=lambda x:(x[0],str(x[1])))
    return d,{'path':str(p),'sha256':p.stem}
