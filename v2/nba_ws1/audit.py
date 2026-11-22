"""Read-only row-level audit of existing NBA population shards."""
from collections import Counter,defaultdict
import argparse
from datetime import date,timedelta
import gzip
import json
from pathlib import Path
from .store import canonical,digest
from .adapters import norm
import population_history as population


def audit(root,as_of):
    root=Path(root);folder=root/'data/bayesian_warehouse/populations/nba'
    seasons={};manifest=[];all_games={};invalid=[];collision=[];seen=set();pg={};pg_stats=defaultdict(dict);members=defaultdict(list)
    total=0
    franchise=set('ATL BOS BKN CHA CHI CLE DAL DEN DET GS HOU IND LAC LAL MEM MIA MIL MIN NO NY OKC ORL PHI PHX POR SAC SA TOR UTAH WSH'.split())
    quarantines={};team_games=defaultdict(set);same_matchup=defaultdict(set)
    cup_finals={'401607495','401734908','401809839'}
    for path in sorted(folder.glob('*/*.jsonl.gz')):
        raw=path.read_bytes();manifest.append(dict(path=str(path.relative_to(root)),bytes=len(raw),sha256=digest(raw)))
        with gzip.open(path,'rt') as f:
            for i,line in enumerate(f,1):
                r=json.loads(line);total+=1
                try:population.validate(r)
                except ValueError as exc:invalid.append(dict(path=str(path.relative_to(root)),line=i,code=str(exc)));continue
                season=seasons.setdefault(r['season'],dict(rows=0,stats=Counter(),games=set(),dates=set(),players=set(),min_date=r['game_date'],max_date=r['game_date'],zero_stat_rows=0,zero_minute_rows=0))
                season['rows']+=1;season['stats'][r['stat']]+=1;season['games'].add(r['game_id']);season['dates'].add(r['game_date']);season['players'].add(r['player_id'])
                season['min_date']=min(season['min_date'],r['game_date']);season['max_date']=max(season['max_date'],r['game_date'])
                season['zero_stat_rows']+=r['value']==0;season['zero_minute_rows']+=r['workload']==0
                key=(r['game_id'],r['player_id'],r['stat'])
                if key in seen:collision.append(dict(kind='duplicate_player_game_stat',key=key))
                seen.add(key)
                ident=(r['game_id'],r['player_id']);values=(r['team'],r['opponent'],r['game_date'],r['workload'])
                if ident in pg and pg[ident]!=values:collision.append(dict(kind='cross_stat_identity_or_minutes',key=ident))
                pg[ident]=values
                pg_stats[ident][r['stat']]=r['value']
                game=all_games.setdefault(r['game_id'],dict(date=r['game_date'],teams=set(),players=set()))
                if game['date']!=r['game_date']:collision.append(dict(kind='game_date_collision',game_id=r['game_id']))
                game['teams'].add(r['team']);game['players'].add(r['player_id'])
                team_games[(r['season'],r['team'])].add(r['game_id'])
                same_matchup[(r['season'],r['game_date'],tuple(sorted([r['team'],r['opponent']])))].add(r['game_id'])
                if r['team'] not in franchise or r['opponent'] not in franchise or r['game_id'] in cup_finals:
                    q=quarantines.setdefault(r['game_id'],dict(game_id=r['game_id'],season=r['season'],game_date=r['game_date'],teams=sorted([r['team'],r['opponent']]),rows=0,reason='NON_FRANCHISE_EXHIBITION' if r['game_id'] not in cup_finals else 'NBA_CUP_FINAL_NOT_REGULAR_SEASON'))
                    q['rows']+=1
    for (gid,pid),(team,opp,day,minutes) in pg.items():
        members[pid].append((day,gid,team))
        stats=pg_stats[(gid,pid)]
        for combo,parts in norm.NBA_COMBOS.items():
            if combo in stats and all(part in stats for part in parts) and stats[combo]!=sum(stats[part] for part in parts):
                collision.append(dict(kind='combo_component_mismatch',game_id=gid,player_id=pid,stat=combo))
    transitions=[]
    for pid,history in sorted(members.items()):
        history=sorted(history)
        for previous,current in zip(history,history[1:]):
            if previous[2]!=current[2]:transitions.append(dict(player_id=pid,previous=previous,current=current))
    for season,s in seasons.items():
        s['quarantined_games']=sum(q['season']==season for q in quarantines.values())
        s['quarantined_rows']=sum(q['rows'] for q in quarantines.values() if q['season']==season)
        s['game_count']=len(s.pop('games'));s['dates_observed']=len(s.pop('dates'));s['player_count']=len(s.pop('players'));s['stats']=dict(sorted(s['stats'].items()))
    states={}
    for stream,name in [('archive','nba.json'),('recent','nba_recent.json')]:
        p=root/'data/bayesian_warehouse/states'/name
        states[stream]=json.loads(p.read_text()) if p.exists() else None
    missing=[]
    if states['recent']:
        day=date.fromisoformat(states['recent']['cursor'])
        while day<date.fromisoformat(as_of):missing.append(day.isoformat());day+=timedelta(days=1)
    return dict(schema='nba-ws1-coverage-audit/1',as_of=as_of,status='inventory_not_full_source_certification',
        rows_scanned=total,unique_player_games=len(pg),unique_games=len(all_games),seasons=dict(sorted(seasons.items())),
        quarantine=list(sorted(quarantines.values(),key=lambda q:(q['season'],q['game_date'],q['game_id']))),
        team_seasons_over_82_games=[dict(season=season,team=team,games=len(games)) for (season,team),games in sorted(team_games.items()) if len(games)>82],
        repeated_same_date_matchups=[dict(season=season,date=day,teams=teams,game_ids=sorted(games)) for (season,day,teams),games in sorted(same_matchup.items()) if len(games)>1],
        states=states,uncollected_recent_dates=missing,invalid_records=invalid,identity_collisions=collision,
        games_with_other_than_two_observed_teams=[g for g,v in all_games.items() if len(v['teams'])!=2],
        games_with_fewer_than_ten_players=[g for g,v in all_games.items() if len(v['players'])<10],
        team_transitions_observed=len(transitions),transition_examples=transitions[:20],source_manifest=manifest,
        unavailable_fields=['original_capture_at','source_available_at','roster_eligibility','starter','dnp','zero_minute_appearances','fga','fta','fg3a','oreb','dreb','team_possessions','team_pace','venue','exact_game_start','injury_rotation','original_market_quotes'],
        completeness_denominator='regular-season cursor dates; independent official schedule comparison required; preseason/playoffs intentionally excluded',
        historical_origin='retrospective retrieval; original publication clocks absent',
        source_manifest_sha256=digest(canonical(manifest).encode()))


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--as-of',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.root,a.as_of);a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(canonical({k:result[k] for k in ('rows_scanned','unique_player_games','unique_games','source_manifest_sha256')}))

if __name__=='__main__':main()
