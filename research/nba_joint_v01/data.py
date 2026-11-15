"""Research-only reconstruction; no original pregame clock is manufactured."""
from collections import defaultdict
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import numpy as np
from v2.nba_joint.common import sha, STATS
from v2.nba_opportunity import causal_features
from .prepare import population


def box(path):
    d=json.loads(Path(path).read_text());c=d['header']['competitions'][0]
    teams=[x for x in c['competitors'] if x['homeAway']=='home']+[x for x in c['competitors'] if x['homeAway']=='away']
    team_ids=[x['team']['abbreviation'] for x in teams]
    periods=[len(x.get('linescores',[])) for x in teams]
    if len(set(periods))!=1 or periods[0]<4:raise ValueError('OFFICIAL_PERIODS_UNAVAILABLE')
    result=dict(game_id=str(c['id']),event_start_at=c['date'],teams=team_ids,players=[],totals={},period=periods[0],home_away={x['team']['abbreviation']:x['homeAway'] for x in teams})
    for group in d['boxscore']['players']:
        team=group['team']['abbreviation'];seen=set()
        for cat in group['statistics']:
            labels=cat['labels']
            for p in cat['athletes']:
                pid=str(p['athlete']['id'])
                if pid in seen:raise ValueError('DUPLICATE_BOX_PLAYER')
                seen.add(pid)
                if p.get('didNotPlay') or not p.get('stats'):continue
                s=dict(zip(labels,p['stats']));v=s['MIN']
                if v in ('--',''):continue
                mins=float(v.split(':')[0])+float(v.split(':')[1])/60 if ':' in v else float(v)
                fgm,fga=map(int,s['FG'].split('-'));pm3,pa3=map(int,s['3PT'].split('-'));ftm,fta=map(int,s['FT'].split('-'))
                values=dict(points=int(s['PTS']),rebounds=int(s['REB']),assists=int(s['AST']),threes=pm3,two_pa=fga-pa3,two_pm=fgm-pm3,three_pa=pa3,fta=fta,ftm=ftm,oreb=int(s['OREB']),dreb=int(s['DREB']),tov=int(s['TO']))
                if values['points']!=2*(fgm-pm3)+3*pm3+ftm:raise ValueError('RAW_POINTS_IDENTITY')
                result['players'].append(dict(player_id=pid,team=team,minutes=mins,stats=values))
    for team in team_ids:
        ps=[p for p in result['players'] if p['team']==team]
        result['totals'][team]={k:sum(p['stats'][k] for p in ps) for k in result['players'][0]['stats']}
        result['totals'][team]['minutes']=sum(p['minutes'] for p in ps)
    return result


def fit_model(receipts,rows):
    train=[r for r in receipts if r['split']=='train' and 'error' not in r]
    if len(train)<16:raise ValueError('INSUFFICIENT_TRAINING_GAMES')
    pooled=defaultdict(float);env=[];sources=[]
    for r in train:
        if r['day']>='2024-04-15':raise ValueError('FUTURE_TRAINING_GAME')
        raw=Path(r['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=r['sha256']:raise ValueError('TRAINING_SOURCE_CHANGED')
        b=box(r['path']);duration=48+5*max(0,b['period']-4);pace=[];fg=[]
        for team in b['teams']:
            x=b['totals'][team]
            for k,v in x.items():pooled[k]+=v
            # Rounded player minutes checked, not repaired or used as exact clock.
            if abs(x['minutes']-5*duration)>7:raise ValueError('INCOMPLETE_TRAIN_TEAM_EXPOSURE')
            poss=x['two_pa']+x['three_pa']+.44*x['fta']-x['oreb']+x['tov']
            pace.append(poss*48/duration);fg.append((x['two_pa']+x['three_pa'])*48/duration)
        common=np.mean(pace);env.append([common,fg[0]/common,fg[1]/common]);sources.append(r['sha256'])
    env=np.array(env);logs=np.log(env);cov=np.cov(logs,rowvar=False)
    p2=(pooled['two_pm']+1)/(pooled['two_pa']+2);p3=(pooled['threes']+1)/(pooled['three_pa']+2);pft=(pooled['ftm']+1)/(pooled['fta']+2)
    non3=2*pooled['two_pm']+pooled['ftm']
    misses=pooled['two_pa']+pooled['three_pa']-pooled['two_pm']-pooled['threes']+.44*(pooled['fta']-pooled['ftm'])
    minutes=json.loads(Path('research/nba_ws2/results/model.json').read_text())
    prior_rows=[r for r in rows if r['season']=='2024' and r['game_date']<'2024-04-15']
    prior={k:sum(r['stats'][k] for r in prior_rows)/sum(r['workload'] for r in prior_rows) for k in STATS[:4]}
    return dict(schema='NBAJointModel/0.1.0',training_cutoff_at='2024-04-15T00:00:00Z',minutes=minutes,
        state=dict(pace_mean=float(env[:,0].mean()),log_cov=cov.tolist(),ot_probability=minutes['ot_probability'],ot_continuation=minutes['ot_continuation']),
        events=dict(p2=p2,p3=p3,pft=pft,ft_share=pooled['ftm']/non3,
            rebound_credit=min(1.,(pooled['oreb']+pooled['dreb'])/misses),offensive_rebound_share=pooled['oreb']/(pooled['oreb']+pooled['dreb']),terminal_ft_fraction=.44,
            assist_fraction=pooled['assists']/(pooled['two_pm']+pooled['threes'])),
        prior_rates=prior,
        provenance=dict(source_hashes=sources,training_games=len(train),training_retrieved_at=max(r['retrieved_at'] for r in train),
            source_semantics='retrospective source retrieval; logical training cutoff only, not an original fitted artifact from 2024',
            substitutions=['WS3 not located; pooled conversion and aggregate component fallback','terminal FT .44 is an explicit box-score proxy convention','no learned player-specific conversion or possession tracking'],
            rebound_credit_preclip=float((pooled['oreb']+pooled['dreb'])/misses),covariance_definition='sample covariance of log(regulation proxy pace, home FGA/proxy, away FGA/proxy)'))


def reconstruct(target,rows,model,generated_at):
    """Target contributes ONLY retrospective schedule identity. Roster is prior union."""
    day=target['day'];b=box(target['path']);teams=b['teams'];past=[r for r in rows if r['game_date']<day]
    history=defaultdict(list);teamgames=defaultdict(set)
    for r in past:history[r['player_id']].append(r);teamgames[r['team']].add((r['game_date'],r['game_id']))
    game=dict(schema='NBAJointInput/1',game_id=b['game_id'],teams=teams,game_date=day,event_start_at=b['event_start_at'],
        analysis_cutoff_at=day+'T00:00:00Z',forecast_at=generated_at,mode='historical',conditional_on_roster=True,
        source_hashes=[],source_cutoffs={'latest_allowed_game_date':day,'observed_at':'retrospective; original publication times unavailable'},
        schedule_provenance={'raw_sha256':target['sha256'],'origin':'retrospective schedule reconstruction from final header; outcomes excluded from inputs'},players=[])
    rejected=[]
    for team in teams:
        previous=set(g for _,g in sorted(teamgames[team])[-10:])
        candidate_ids={r['player_id'] for r in past if r['team']==team and r['game_id'] in previous}
        for pid in sorted(candidate_ids):
            h=history[pid]
            if h[-1]['team']!=team:
                rejected.append({'player_id':pid,'team':team,'reason':'PRIOR_MEMBERSHIP_CHANGED'});continue
            try:
                missed=sum(d>h[-1]['game_date'] for d,_ in teamgames[team])
                f=causal_features(h,game_date=day,team=team,home=team==teams[0],prior_team_games_missed=missed)
            except ValueError as exc:
                rejected.append({'player_id':pid,'team':team,'reason':str(exc)});continue
            recent=h[-20:];exposure=sum(r['workload'] for r in recent);prior=model['prior_rates']
            rates={k:(sum(r['stats'][k] for r in recent)+48*prior[k])/(exposure+48) for k in STATS[:4]}
            player=dict(player_id=pid,team_id=team,opponent_id=teams[1] if team==teams[0] else teams[0],position=h[-1]['position'],eligible=None,participation_probability=None,
                minute_features=f,last_observation_date=h[-1]['game_date'],history_game_ids=[r['game_id'] for r in recent],rates=rates,
                history_stats={k:[r['stats'][k] for r in recent] for k in STATS[:4]},availability='UNKNOWN_CONDITIONAL_RESEARCH')
            game['players'].append(player);game['source_hashes']+= [r['source_sha256'] for r in recent]
    game['source_hashes']=sorted(set(game['source_hashes']))
    # Holdout actuals returned separately and never attached to game input.
    actual={p['player_id']:p for p in b['players'] if p['minutes']>0}
    roster={p['player_id'] for p in game['players']}
    ledger=dict(game_id=b['game_id'],game_date=day,attempted_candidates=len(game['players'])+len(rejected),accepted_conditional_candidates=len(game['players']),rejected_candidates=rejected,
        observed_appearances=len(actual),matched_appearances=len(roster & actual.keys()),unforecasted_appearances=sorted(actual.keys()-roster),
        roster_without_observed_appearance=sorted(roster-actual.keys()),authentic_unconditional_forecasts=0,
        caveats=['prior appearance union is not authenticated game roster','conditional cohort scoring excludes DNP outcomes; complete missingness retained','round-trip game schedule is retrospective, never canonical pregame evidence'])
    return game,actual,b,ledger
