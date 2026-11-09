"""Current-season NFL history for qualitative scouting. No picks or market lines.

FTN Data via nflverse (CC BY-SA 4.0). Read categories follow the versioned
nflreadr dictionary; they describe the observed throw, not every route/read.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

VERSION='nfl-season-v1'
READ_MAP={'0':'first_read','1':'second_read','2':'later_read','CHK':'checkdown',
          'DES':'designed','SD':'scramble_drill'}
BUCKETS=tuple(READ_MAP.values())+('unknown',)
PBP_SOURCE='https://github.com/nflverse/nflverse-data/releases/tag/pbp'
FTN_SOURCE='https://github.com/nflverse/nflverse-data/releases/tag/ftn_charting'
DICTIONARY='https://nflreadr.nflverse.com/articles/dictionary_ftn_charting.html'
CATEGORIES=('interior_run','off_tackle_run','edge_run','unknown_run','short_pass','deep_pass','unknown_pass','scramble','sack','other')
PBP_FIELDS=('game_id','play_id','season','season_type','week','game_date','posteam','defteam',
            'no_play','two_point_attempt','extra_point_attempt','field_goal_attempt','kickoff_attempt','punt_attempt','qb_dropback','pass_attempt','rush_attempt','qb_scramble','sack',
            'passer_player_id','passer_player_name','receiver_player_id','receiver_player_name',
            'run_location','run_gap','air_yards','epa','qb_hit','complete_pass')+tuple(
                f'{kind}_{i}_player_id' for kind,limit in [('solo_tackle',2),('assist_tackle',4),('tackle_with_assist',2)]
                for i in range(1,limit+1))
FTN_FIELDS=('nflverse_game_id','nflverse_play_id','season','week','read_thrown',
            'is_screen_pass','is_rpo','is_play_action','is_motion','n_defense_box','n_blitzers','n_pass_rushers')


def number(value):
    if value is None or isinstance(value,bool):return None
    try:
        n=float(value)
        return n if math.isfinite(n) else None
    except (TypeError,ValueError):return None


def one(value):return value is True or number(value)==1


def token(value):
    if value is None or isinstance(value,bool):return None
    n=number(value)
    return str(int(n)) if n is not None and n.is_integer() else None


def bucket(code):
    text=code.strip() if isinstance(code,str) else token(code)
    return READ_MAP.get(text,'unknown')


def category(row):
    if one(row.get('qb_scramble')):return 'scramble'
    if one(row.get('sack')):return 'sack'
    if one(row.get('rush_attempt')):
        gap=str(row.get('run_gap') or '').lower()
        loc=str(row.get('run_location') or '').lower()
        if loc=='middle' or gap=='guard':return 'interior_run'
        if gap=='tackle':return 'off_tackle_run'
        if gap=='end':return 'edge_run'
        return 'unknown_run'
    if one(row.get('pass_attempt')):
        depth=number(row.get('air_yards'))
        return 'unknown_pass' if depth is None else ('short_pass' if depth<15 else 'deep_pass')
    return 'other'


def ratio(n,d):return n/d if d else None


def distribution(counts):
    total=sum(counts.values())
    return {k:ratio(counts.get(k,0),total) for k in BUCKETS}


def completed_catalog(games, season, as_of):
    """Only earlier-day completed regular-season games. Same-day games wait.

    Avoid treating a partial game feed as completed history. The slate date is a
    hard exclusion even if the schedule has a postgame score in a replay fixture.
    """
    cutoff=datetime.fromisoformat(as_of.replace('Z','+00:00')).astimezone(ZoneInfo('America/Toronto')).date().isoformat()
    found={}
    for g in games:
        day=str(g.get('gameday') or g.get('game_date') or '')[:10]
        if (str(g.get('season'))!=str(season) or g.get('game_type',g.get('season_type'))!='REG'
                or not day or day>=cutoff or number(g.get('result')) is None):continue
        found[str(g['game_id'])]={'date':day,'week':g.get('week')}
    return found


class SeasonStore:
    def __init__(self,path):self.path=Path(path)

    def refresh(self,season,pbp,charting,games,*,as_of,retrieved_at=None):
        """Replace a complete source snapshot transactionally; retries never duplicate plays."""
        season=int(season)
        catalog=completed_catalog(games,season,as_of)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS metadata (season INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS plays (season INTEGER, game_id TEXT, play_id TEXT, payload TEXT NOT NULL, PRIMARY KEY(season,game_id,play_id))')
            db.execute('CREATE TABLE IF NOT EXISTS charting (season INTEGER, game_id TEXT, play_id TEXT, payload TEXT NOT NULL, PRIMARY KEY(season,game_id,play_id))')
            db.execute('DELETE FROM plays WHERE season=?',(season,))
            db.execute('DELETE FROM charting WHERE season=?',(season,))
            duplicate_pbp=duplicate_chart=0
            seen=set();seen_payloads={}
            for raw in pbp or []:
                gid=str(raw.get('game_id') or '');pid=token(raw.get('play_id'))
                if gid not in catalog or pid is None or str(raw.get('season'))!=str(season) or raw.get('season_type')!='REG' or any(one(raw.get(k)) for k in ('no_play','two_point_attempt','extra_point_attempt','field_goal_attempt','kickoff_attempt','punt_attempt')):continue
                if (gid,pid) in seen:duplicate_pbp+=1
                seen.add((gid,pid))
                row={k:raw.get(k) for k in PBP_FIELDS if k in raw}
                row['game_date']=catalog[gid]['date']
                row={k:(None if isinstance(v,float) and not math.isfinite(v) else v) for k,v in row.items()}
                if (gid,pid) in seen_payloads and seen_payloads[(gid,pid)]!=row:
                    raise ValueError('conflicting duplicate play in one snapshot')
                seen_payloads[(gid,pid)]=row
                db.execute('INSERT OR REPLACE INTO plays VALUES (?,?,?,?)',(season,gid,pid,json.dumps(row,allow_nan=False)))
            seen_chart=set();seen_chart_payloads={}
            for raw in charting or []:
                gid=str(raw.get('nflverse_game_id') or '');pid=token(raw.get('nflverse_play_id'))
                if (gid,pid) not in seen or str(raw.get('season'))!=str(season):continue
                if (gid,pid) in seen_chart:duplicate_chart+=1
                seen_chart.add((gid,pid))
                row={k:raw.get(k) for k in FTN_FIELDS if k in raw}
                row={k:(None if isinstance(v,float) and not math.isfinite(v) else v) for k,v in row.items()}
                if (gid,pid) in seen_chart_payloads and seen_chart_payloads[(gid,pid)]!=row:
                    raise ValueError('conflicting duplicate charting play in one snapshot')
                seen_chart_payloads[(gid,pid)]=row
                db.execute('INSERT OR REPLACE INTO charting VALUES (?,?,?,?)',(season,gid,pid,json.dumps(row,allow_nan=False)))
            meta=dict(version=VERSION,season=season,as_of=as_of,retrieved_at=retrieved_at or as_of,
                      source_urls=[PBP_SOURCE,FTN_SOURCE],read_dictionary=DICTIONARY,
                      read_mapping=READ_MAP,charting_available=charting is not None,
                      games=len(catalog),plays=len(seen),charted_plays=len(seen_chart),
                      missing_play_game_ids=sorted(set(catalog)-{gid for gid,pid in seen}),
                      duplicate_pbp=duplicate_pbp,duplicate_charting=duplicate_chart,
                      latest_game_date=max((v['date'] for v in catalog.values()),default=None))
            db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',(season,json.dumps(meta)))
        return meta

    def profiles(self,season,*,as_of):
        with sqlite3.connect(f'file:{self.path}?mode=ro',uri=True) as db:
            meta=db.execute('SELECT payload FROM metadata WHERE season=?',(season,)).fetchone()
            if meta is None:raise ValueError('season not stored')
            meta=json.loads(meta[0])
            def at(value, field):
                try:
                    stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
                except (ValueError,TypeError,AttributeError) as exc:
                    raise ValueError('invalid_'+field+'_timestamp') from exc
                if stamp.tzinfo is None:
                    raise ValueError('naive_'+field+'_timestamp')
                return stamp.astimezone(timezone.utc)
            evaluation=at(as_of,'evaluation')
            snapshot_asof=at(meta.get('as_of'),'snapshot')
            source_retrieved=at(meta.get('retrieved_at'),'retrieval')
            if snapshot_asof>evaluation:
                raise ValueError('store snapshot is newer than evaluation; use an as-of snapshot')
            # A post-hoc source refresh must never be silently presented as
            # a true pregame archive even if older game rows were filtered.
            if source_retrieved>evaluation:
                raise ValueError('source_retrieved_after_evaluation')
            plays=[json.loads(x[0]) for x in db.execute('SELECT payload FROM plays WHERE season=? ORDER BY game_id,play_id',(season,))]
            chart={(x[0],x[1]):json.loads(x[2]) for x in db.execute('SELECT game_id,play_id,payload FROM charting WHERE season=?',(season,))}
        return build_profiles(plays,chart,meta)


def build_profiles(plays,chart,meta):
    teams={};qbs={};defenses={};defenders={}
    for p in plays:
        offense=p.get('posteam');defense=p.get('defteam')
        if not offense or not defense:continue
        gid=str(p['game_id']);pid=token(p['play_id']);c=chart.get((gid,pid),{})
        cat=category(p)
        # Full defensive scrimmage exposure, including incompletions and plays
        # with no tackle. Special-team plays do not enter tackle prop estimates.
        scrimmage=one(p.get('rush_attempt')) or one(p.get('pass_attempt')) or one(p.get('qb_dropback'))
        if scrimmage:
            t=teams.setdefault(offense,{'categories':Counter(),'games':set()})
            t['categories'][cat]+=1;t['games'].add(gid)
            d=defenses.setdefault(defense,{'categories':Counter(),'games':set(),'reads':Counter(),
                'targeted_reads':Counter(),'qbs':{},'dropbacks':0,'epa_sum':0.,'epa_n':0,'charted_throws':0,'throws':0})
            d['categories'][cat]+=1;d['games'].add(gid)
            if one(p.get('qb_dropback')):
                d['dropbacks']+=1
                epa=number(p.get('epa'))
                if epa is not None:d['epa_sum']+=epa;d['epa_n']+=1
            credits={}
            for kind,limit in [('solo_tackle',2),('assist_tackle',4),('tackle_with_assist',2)]:
                for i in range(1,limit+1):
                    ident=p.get(f'{kind}_{i}_player_id')
                    if ident:credits.setdefault(str(ident),kind)
            for ident,kind in credits.items():
                v=defenders.setdefault(f'{defense}|{ident}',{'team':defense,'player_id':ident,'credits':Counter(),
                                                           'solo':0,'assists':0,'games':set()})
                v['credits'][cat]+=1;v['games'].add(gid)
                v['solo' if kind=='solo_tackle' else 'assists']+=1
        # nflverse pass_attempt includes sacks; market pass attempts/targets do not.
        if not one(p.get('pass_attempt')) or one(p.get('sack')):continue
        read=bucket(c.get('read_thrown'))
        d=defenses[defense];d['throws']+=1;d['reads'][read]+=1
        d['charted_throws']+=int(read!='unknown')
        qb=p.get('passer_player_id');receiver=p.get('receiver_player_id')
        if not qb:continue
        key=f'{offense}|{qb}'
        q=qbs.setdefault(key,{'team':offense,'player_id':str(qb),'name':p.get('passer_player_name'),
            'throws':0,'throws_by_defense':Counter(),'reads':Counter(),'targeted':Counter(),'receivers':{},'by_defense':{},'by_game':{},'scheme':{}})
        q['throws']+=1;q['throws_by_defense'][defense]+=1;q['reads'][read]+=1
        bydef=q['by_defense'].setdefault(defense,Counter())
        if receiver:
            q['targeted'][read]+=1;bydef[read]+=1;d['targeted_reads'][read]+=1
            d['qbs'].setdefault(key,Counter())[read]+=1
            r=q['receivers'].setdefault(str(receiver),{'name':p.get('receiver_player_name'),'buckets':Counter(),'by_game':{},'by_defense':{}})
            r['by_defense'].setdefault(defense,Counter())[read]+=1
            r['buckets'][read]+=1;r['by_game'].setdefault(gid,Counter())[read]+=1
        q['by_game'].setdefault(gid,Counter())
        if receiver:q['by_game'][gid][read]+=1
        for flag in ('is_screen_pass','is_rpo','is_play_action','is_motion'):
            if flag not in c or c[flag] is None:continue
            group=q['scheme'].setdefault(flag,{'observed':0,'flagged':0,'receivers':Counter()})
            group['observed']+=1
            if one(c[flag]):
                group['flagged']+=1
                if receiver:group['receivers'][str(receiver)]+=1
    # Opponent-QB adjustment uses that same passer's OTHER defenses only.
    for name,d in defenses.items():
        expected=Counter();comparison_n=0;unmatched_qbs=[]
        for qkey,against in d['qbs'].items():
            other=qbs[qkey]['targeted']-against
            # Unknown reads cannot count as coverage wins or force a checkdown.
            comparable=sum(v for k,v in other.items() if k!='unknown')
            known_against=sum(v for k,v in against.items() if k!='unknown')
            if not comparable or not known_against:unmatched_qbs.append(qkey);continue
            comparison_n+=known_against
            for k in BUCKETS[:-1]:expected[k]+=known_against*other[k]/comparable
        d['opponent_qb_expected_counts']=dict(expected)
        d['opponent_adjusted_comparable_targets']=comparison_n
        # Actual matched counts must use the same subset of QBs as expected.
        d['matched_actual_counts']={k:sum(v[k] for qkey,v in d['qbs'].items() if qkey not in unmatched_qbs) for k in BUCKETS[:-1]}
        d['unmatched_qbs']=unmatched_qbs
        d['checkdown_rate_on_known_reads']=ratio(d['reads']['checkdown'],d['charted_throws'])
        d['charting_coverage']=ratio(d['charted_throws'],d['throws'])
        d['epa_per_dropback']=ratio(d.pop('epa_sum'),d.pop('epa_n'))
        d['interpretation']='Observed checkdowns against defense; not proof of causal forcing or overall defensive quality.'
    for q in qbs.values():
        q['targetable_rate']=ratio(sum(q['targeted'].values()),q['throws'])
        q['bucket_probabilities']=distribution(q['targeted'])
        q['leaders_by_bucket']={}
        for read in BUCKETS:
            largest=max((r['buckets'][read] for r in q['receivers'].values()),default=0)
            q['leaders_by_bucket'][read]=[rid for rid,r in q['receivers'].items()
                                         if largest and r['buckets'][read]==largest]
        q['read_coverage']=ratio(q['throws']-q['reads']['unknown'],q['throws'])
        for r in q['receivers'].values():
            r['share_within_bucket']={k:ratio(r['buckets'][k],q['targeted'][k]) for k in BUCKETS}
            # Team/passers' zero-target games remain in both windows.
            dates=sorted(q['by_game'])
            recent=dates[-3:];older=dates[:-3]
            r['trend']={'recent_games':recent,'earlier_games':older,
                'recent_target_share':ratio(sum(sum(r['by_game'].get(g,{}).values()) for g in recent),
                                            sum(sum(q['by_game'][g].values()) for g in recent)),
                'earlier_target_share':ratio(sum(sum(r['by_game'].get(g,{}).values()) for g in older),
                                             sum(sum(q['by_game'][g].values()) for g in older))}
    for key,v in defenders.items():
        d=defenses[v['team']]
        v['team_play_denominators']=dict(d['categories'])
        v['credit_rate_per_team_play']={k:ratio(v['credits'][k],d['categories'][k]) for k in CATEGORIES}
        v['interpretation']='Credited tackles+assists per team scrimmage play, includes historical bench/absence exposure; not per-snap tackling ability.'
    def serial(value):
        if isinstance(value,dict):return {k:serial(v) for k,v in value.items()}
        if isinstance(value,set):return sorted(value)
        return value
    return serial(dict(metadata=meta,offenses=teams,passers=qbs,defenses=defenses,defenders=defenders))


def candidate_context(profiles,team,opponent,player_id):
    return dict(metadata=profiles['metadata'],team=team,opponent=opponent,player_id=str(player_id),
        passers={k:v for k,v in profiles['passers'].items() if v['team']==team},
        defense=profiles['defenses'].get(opponent),
        opponent_offense=profiles['offenses'].get(opponent),
        own_defense=profiles['defenses'].get(team),
        defender=profiles['defenders'].get(f'{team}|{player_id}'))


def refresh_live(path,season,as_of,loader=None):
    if loader is None:import nflreadpy as loader
    def rows(method):
        value=getattr(loader,method)(seasons=[season])
        return value.to_dicts() if hasattr(value,'to_dicts') else list(value)
    games=rows('load_schedules');pbp=rows('load_pbp')
    error=None
    try:charting=rows('load_ftn_charting')
    except Exception as exc:charting=None;error=f'{type(exc).__name__}: {exc}'
    meta=SeasonStore(path).refresh(season,pbp,charting,games,as_of=as_of)
    return dict(metadata=meta,charting_error=error)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['refresh','profiles'])
    parser.add_argument('--season',type=int,required=True)
    parser.add_argument('--db',required=True)
    parser.add_argument('--as-of',default=datetime.now(timezone.utc).isoformat())
    args=parser.parse_args()
    result=refresh_live(args.db,args.season,args.as_of) if args.command=='refresh' else SeasonStore(args.db).profiles(args.season,as_of=args.as_of)
    print(json.dumps(result,allow_nan=False))
