"""Independent accounting path for the new residual-group event representation.

No admission decision is inferred from physics. Source, numerical convergence,
marginal compatibility and predictive validation have separate gates.
"""
import math
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.subset_p3_v1 import require
from v2.nba_joint.residual_opportunity_v1 import audit_team

KEYS=('points','rebounds','assists','threes','fgm','fga','ftm','fta','oreb','dreb','turnovers','fouls')


def audit_path(fixed,path):
    teams=fixed['teams'];length=fixed['length'];k=fixed['overtime_count']
    require(len(teams)==2 and len(set(teams))==2 and length==48+5*k and type(k) is int and k>=0,'J_AUDIT_SHARED_G')
    for team in teams:
        audit_team(fixed['O'][team],length)
        identities=fixed['O'][team]['actors'];ids=[a['player_id'] for a in identities if a['player_id']]
        require(len(ids)==len(set(ids)) and all(a['team_id']==team for a in identities),'J_AUDIT_IDENTITIES')
        require([a['identity'] for a in fixed['actors'][team]]==identities,'J_AUDIT_FIXED_ACTOR_JOIN')
    expected={team:[{s:0 for s in KEYS} for a in fixed['actors'][team]] for team in teams}
    score={t:0 for t in teams};live=set();fouls={};ft_next={};period_ends=[];previous=0.;current_period=0
    offense=None;shot_clock=24.;last_reset=0.;rotation_seen=set()
    boundary={s['end'] for team in teams for s in fixed['O'][team]['segments'] if s['end']<length}
    period_boundaries={12.,24.,36.,48.}|{48.+5*j for j in range(1,k+1)}
    def active(team,t):
        for seg in fixed['O'][team]['segments']:
            if seg['start']<=t<seg['end']:return seg['player_indices']
        raise ValueError('J_AUDIT_NO_LINEUP')
    def actor(row,key='actor',team_key='team'):
        team=row[team_key];i=row[key]
        require(team in teams and type(i) is int and i in active(team,row['elapsed']),'J_AUDIT_OFF_COURT_CREDIT')
        return expected[team][i]
    def other(team):return teams[1] if team==teams[0] else teams[0]
    def change(team,t):
        nonlocal offense,shot_clock,last_reset
        offense=team;shot_clock=24.;last_reset=t
    for index,row in enumerate(path['ledger']):
        t=row['elapsed'];kind=row['kind'];p=row['period']
        require(row['index']==index and type(t) in (int,float) and math.isfinite(t) and previous<=t<=length,'J_AUDIT_CHRONOLOGY')
        require(not live or kind=='REBOUND','J_AUDIT_UNRESOLVED_LIVE_MISS')
        if kind=='PERIOD_START':
            require(p==current_period+1 and t==(0 if p==1 else 12*(p-1) if p<=5 else 48+5*(p-5)),
                'J_AUDIT_PERIOD_START')
            current_period=p;change(row['offense'],t)
            require(offense in teams and row['on_court']=={team:active(team,t) for team in teams},'J_AUDIT_PERIOD_LINEUP')
        else:require(p==current_period,'J_AUDIT_PERIOD_ID')
        require(row['offense']==offense,'J_AUDIT_POSSESSION_TEAM')
        if kind=='DEFLECTION_OUT_OF_BOUNDS':
            require(t in boundary and row['on_court']=={team:active(team,t) for team in teams},'J_AUDIT_SUBSTITUTION')
            require(abs(row['shot_clock_remaining']-(shot_clock-60*(t-last_reset)))<1e-7,'J_AUDIT_SUB_SHOT_CLOCK')
            rotation_seen.add(t)
        elif kind in ('FIELD_GOAL','TURNOVER_OUT_OF_BOUNDS','SHOOTING_FOUL'):
            remaining=shot_clock-60*(t-last_reset)
            require(remaining>=-1e-7,'J_AUDIT_SHOT_CLOCK_EXPIRED')
            if kind!='TURNOVER_OUT_OF_BOUNDS':
                require(abs(row['shot_clock_remaining']-remaining)<1e-7 and row['reset_limit']==shot_clock,'J_AUDIT_SHOT_CLOCK')
            if kind=='SHOOTING_FOUL':
                require(row['team']==other(offense) and row['shooter_team']==offense,'J_AUDIT_FOUL_TEAM')
                defender=actor(row);actor(row,key='shooter',team_key='shooter_team');defender['fouls']+=1
                require(defender['fouls']<=5 and row['attempts'] in (2,3),'J_AUDIT_FOUL_LIMIT')
                fouls[index]=row;ft_next[index]=1
            else:
                require(row['team']==offense,'J_AUDIT_SHOOTING_TEAM');s=actor(row)
                if kind=='TURNOVER_OUT_OF_BOUNDS':s['turnovers']+=1;change(other(offense),t)
                else:
                    value=row['value'];require(type(value) is int and value in (2,3) and type(row['made']) is bool,'J_AUDIT_SHOT_VALUE')
                    s['fga']+=1
                    if row['made']:
                        s['fgm']+=1;s['points']+=value;s['threes']+=int(value==3);score[offense]+=value
                        if row['assist'] is not None:
                            require(row['assist']!=row['actor'],'J_AUDIT_SELF_ASSIST')
                            actor(row,key='assist')['assists']+=1
                        change(other(offense),t)
                    else:
                        require(row['assist'] is None,'J_AUDIT_MISS_ASSIST');live.add(index)
        elif kind=='FREE_THROW':
            f=row['foul'];require(f in fouls and row['number']==ft_next[f] and row['number']<=row['attempts']==fouls[f]['attempts'],
                'J_AUDIT_FT_SERIES')
            require(row['team']==offense==fouls[f]['shooter_team'] and row['actor']==fouls[f]['shooter'] and
                t==fouls[f]['elapsed'] and type(row['made']) is bool,'J_AUDIT_FT_SHOOTER')
            s=actor(row);s['fta']+=1;ft_next[f]+=1
            if row['made']:s['ftm']+=1;s['points']+=1;score[offense]+=1
            if row['number']==row['attempts']:
                if row['made']:change(other(offense),t)
                else:live.add(index)
        elif kind=='REBOUND':
            require(row['miss'] in live and len(live)==1 and type(row['offensive']) is bool and type(row['credited']) is bool,
                'J_AUDIT_REBOUND_MISS_JOIN')
            miss=path['ledger'][row['miss']];require(t==miss['elapsed'],'J_AUDIT_REBOUND_CLOCK')
            require(row['team']==(offense if row['offensive'] else other(offense)),'J_AUDIT_REBOUND_TEAM')
            if row['credited']:
                s=actor(row);s['rebounds']+=1;s['oreb' if row['offensive'] else 'dreb']+=1
            else:require(row['actor'] is None,'J_AUDIT_UNATTRIBUTED_REBOUND')
            live.remove(row['miss'])
            if row['offensive']:shot_clock=14.;last_reset=t
            else:change(other(offense),t)
        elif kind=='PERIOD_HOLD_END':
            require(t==(12*p if p<=4 else 48+5*(p-4)) and
                abs(row['shot_clock_elapsed']-60*(t-row['possession_started']))<1e-7 and
                row['shot_clock_elapsed']<=row['shot_clock_before']+1e-7,'J_AUDIT_PERIOD_HOLD')
        elif kind=='PERIOD_END':
            require(t==(12*p if p<=4 else 48+5*(p-4)),'J_AUDIT_PERIOD_END_CLOCK')
            period_ends.append(score.copy())
            if p>=4:require((score[teams[0]]==score[teams[1]])==(p<4+k),'J_AUDIT_OT_SCORE_PATTERN')
        elif kind!='PERIOD_START':raise ValueError('J_AUDIT_UNKNOWN_EVENT')
        require(row['score']==score,'J_AUDIT_SCORE_LEDGER');previous=t
    require(not live and len(period_ends)==4+k and previous==length,'J_AUDIT_COMPLETE_GAME')
    require(boundary-period_boundaries<=rotation_seen,'J_AUDIT_MISSING_SUBSTITUTION')
    require(all(ft_next[f]==row['attempts']+1 for f,row in fouls.items()),'J_AUDIT_INCOMPLETE_FT_SERIES')
    for team in teams:
        for s in expected[team]:
            p,r,a=s['points'],s['rebounds'],s['assists'];s.update(pr=p+r,pa=p+a,ra=r+a,pra=p+r+a)
    require(expected==path['counts'] and period_ends==path['period_scores'],'J_AUDIT_COUNT_RECONSTRUCTION')
    return dict(violations=0,events=len(path['ledger']),periods=4+k,score=score,
        all_counts_rederived=True,all_stats_same_path=True,residual_identity_claim=False)


def audit_run(run):
    payload={k:v for k,v in run.items() if k!='payload_sha256'}
    require(digest(canonical(payload))==run['payload_sha256'],'J_AUDIT_RUN_PAYLOAD')
    require(run['status']=='ENGINEERING_SAMPLE' and not run['failed'] and
        len(run['scenarios'])==run['n_requested']==run['scenario_denominator'],'J_AUDIT_FAILED_OR_DROPPED_SCENARIO')
    results=[]
    for index,scenario in enumerate(run['scenarios']):
        require(scenario['fixed']['index']==index and scenario['accepted_attempt']==len(scenario['proposals'])-1,
            'J_AUDIT_REJECTION_ANCESTRY')
        require(all(p['status']=='REJECT_OT_PATTERN' for p in scenario['proposals'][:-1]),'J_AUDIT_SELECTED_RERUN')
        results.append(audit_path(scenario['fixed'],scenario['proposals'][-1]))
    return dict(status='PHYSICAL_ACCOUNTING_ONLY',scenarios=len(results),results=results,
        marginal_fidelity_accepted=False,release=False)
