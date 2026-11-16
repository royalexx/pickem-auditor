"""Additional independent full-contract cases; fixtures are all synthetic."""
import copy
import json
import math
from pathlib import Path
import subprocess
import sys

root=Path.cwd();SHA='59d28dc23be97de2a6a82d22be8338151e31f5b6'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==SHA
sys.path[:0]=[str(root),str(root/'tests/nba_architecture')]
from golden_v2 import pregame, model, game_state, zero_stats, distribution, original_offer
from test_g0_pipeline_completion_20261116 import coherent_case
from test_v2_contracts import evaluation
from v2.nba_architecture.v2_contracts import VERSION,seal,canonical,marginal_from_joint,offer_view,ContractError
from v2.nba_architecture.families_v2 import validate_forecast,validate_settlement,validate_opportunity

out=Path('/workspace/work/evidence157/full-boundaries');out.mkdir(parents=True,exist_ok=True)
records=[]
def rs(x):
    x=copy.deepcopy(x);x.pop('content_hash',None);return seal(x)
def check(name,expected,fn):
    try:
        assert fn() is True
        actual='ACCEPT';code=None
    except ContractError as exc:actual='REJECT';code=exc.code
    except Exception as exc:actual='ERROR';code=repr(exc)
    records.append(dict(name=name,expected=expected,actual=actual,code=code,matched=actual==expected))
def validate(c):
    return validate_forecast(c['distribution'],c['pregame'],g=c['game_state'],o=c['opportunity'],scenarios=c.get('scenarios'))
def settle(c):
    d=c['distribution'];p=c['pregame'];q=original_offer(p)
    q.update(player_id=d['player_id'],team_id=d['team_id'],stat=d['stat']);q=rs(q)
    v=offer_view(d,q,p,'2026-11-16T23:04:00Z',c.get('scenarios'))
    e=evaluation(d,v,actual=0,participation='PLAYED_ZERO_MINUTES')
    return validate_settlement(e,d,p,view=v,quote=q,g=c['game_state'],o=c['opportunity'],scenarios=c.get('scenarios'))

# 13-player game: four fixed home players leave 48 minutes for three actors.
# Three 24/24 pairs form a feasible law, sampled with deliberately unequal
# weights (.2,.3,.5) rather than the law's 1/3,1/3,1/3 masses.
p=pregame('original_prospective',with_offer=True)
home,away=p['team_ids']
extra=copy.deepcopy(p['players'][0]);extra['player_id']='espn:player:independent-actor-C'
p['players'].append(extra);p=rs(p)
actors=[p['players'][0]['player_id'],p['players'][1]['player_id'],extra['player_id']]
templates=((24.,24.,0.),(24.,0.,24.),(0.,24.,24.))
scenarios=[];ow={};gw={}
for i,(minutes,w) in enumerate(zip(templates,(.2,.3,.5))):
    sid=f'independent:triple:{i}';rows=[]
    for person in p['players']:
        pid=person['player_id'];stats=zero_stats()
        if pid in actors:mn=minutes[actors.index(pid)]
        elif person['team_id']==home:mn=48.
        else:mn=0. if pid==p['players'][11]['player_id'] else 48.
        # A fixed home player supplies the non-tied final score, independently
        # of the target's always-zero counts.
        if pid==p['players'][2]['player_id']:
            stats.update(points=2,two_pm=1,two_pa=1,fgm=1,fga=1,pr=2,pa=2,pra=2)
        rows.append(dict(player_id=pid,team_id=person['team_id'],minutes=mn,
                         participation='PLAYED' if mn else 'PLAYED_ZERO_MINUTES',stats=stats))
    scenarios.append(dict(scenario_id=sid,weight=w,overtime_periods=0,
                          team_points={home:2,away:0},players=rows))
    ow[sid]=[{k:r[k] for k in ('player_id','team_id','minutes','participation')} for r in rows]
    gw[sid]=dict(overtime_periods=0,weight=w)
j=dict(schema=VERSION,kind='scenarios',source_snapshot_sha256=p['content_hash'],game_id=p['game_id'],
       pipeline_mode='S_O_J',conditioning='unconditional',lineage={k:model(k,p) for k in ('S','O','G','J')},
       scenarios=scenarios,game_state_witness=gw,opportunity_witness=ow)
g=game_state(p,j)
people=[]
for person in p['players']:
    pid=person['player_id']
    support=[{'minutes':0.,'mass':1/3},{'minutes':24.,'mass':2/3}] if pid in actors else [
        {'minutes':0. if pid==p['players'][11]['player_id'] else 48.,'mass':1.}]
    people.append(dict(player_id=pid,team_id=person['team_id'],participation_probability=1.,
        participation_evidence='independently_estimated',minutes_law=dict(family='discrete_minutes',
        parameters=dict(support=support),conditioning='given_played',units='minutes')))
o=seal(dict(schema=VERSION,kind='opportunity',source_snapshot_sha256=p['content_hash'],game_id=p['game_id'],
            model=model('O',p),game_state_sha256=g['content_hash'],players=people,
            scenarios=[dict(scenario_id=s['scenario_id'],weight=s['weight'],overtime_periods=0,players=ow[s['scenario_id']]) for s in scenarios]))
j.update(game_state_sha256=g['content_hash'],opportunity_sha256=o['content_hash']);j=seal(j)
d=marginal_from_joint(j,p,actors[0],'points','2026-11-16T23:03:00Z',42)
c=dict(pregame=p,game_state=g,opportunity=o,scenarios=j,distribution=d)
check('three_actor_feasible_at_O','ACCEPT',lambda:validate_opportunity(o,p,g))
check('three_actor_feasible_at_forecast','ACCEPT',lambda:validate(c))
check('three_actor_feasible_at_C','ACCEPT',lambda:settle(c))
(out/'three_actor_positive.json').write_bytes(canonical(c)+b'\n')

# The following marginals have the SAME required expected pool and individually
# attainable atoms, but the (24_B,24_C) allocation would need mass -1/4.
bad=copy.deepcopy(c)
for pid,a,b in zip(actors,(.125,.125,.25),(.75,.125,.125)):
    person=next(x for x in bad['opportunity']['players'] if x['player_id']==pid)
    person['minutes_law']['parameters']['support']=[{'minutes':m,'mass':w} for m,w in ((0.,1-a-b),(24.,b),(48.,a))]
assert sum(48*a+24*b for a,b in zip((.125,.125,.25),(.75,.125,.125)))==48
bad['opportunity']=rs(bad['opportunity']);bad['scenarios']['opportunity_sha256']=bad['opportunity']['content_hash'];bad['scenarios']=rs(bad['scenarios'])
bad['distribution']=marginal_from_joint(bad['scenarios'],p,actors[0],'points','2026-11-16T23:03:00Z',42)
check('same_mean_impossible_joint_at_O','REJECT',lambda:validate_opportunity(bad['opportunity'],p,g))
check('same_mean_impossible_joint_at_forecast','REJECT',lambda:validate(bad))
check('same_mean_impossible_joint_at_C','REJECT',lambda:settle(bad))
(out/'same_mean_negative.json').write_bytes(canonical(bad)+b'\n')

# All eight markets, all declared conditionings, analytic and empirical S_O:
# structural zero exposure must remain a hard zero while valid zero laws pass.
base=coherent_case();p,g,o=base['pregame'],base['game_state'],base['opportunity']
for stat in ('points','rebounds','assists','threes','pr','pa','ra','pra'):
 for conditioning in ('unconditional','conditional_on_participation','conditional_on_declared_roster'):
  for method in ('analytic','empirical_mc'):
   for positive in (0.,.125):
    d=distribution(p,stat=stat,mode='S_O');d['lineage']['G']=g['model']
    d.update(player_id=p['players'][5]['player_id'],conditioning=conditioning,
             opportunity_output_sha256=o['content_hash'],pmf=[{'value':0,'mass':1-positive},{'value':3,'mass':positive}])
    if method=='empirical_mc':
        d['numerical'].update(method='empirical_mc',scenario_count=8,effective_sample_size=8.,
             max_probability_se=math.sqrt(positive*(1-positive)/8),zero_event_95_upper_bound=1-.05**(1/8),uncertainty_basis='heuristic_weighted_ess')
    d=rs(d);case=dict(pregame=p,game_state=g,opportunity=o,distribution=d)
    expected='ACCEPT' if positive==0 else 'REJECT'
    name=f'{stat}_{conditioning}_{method}_{positive}'
    check(name+'_forecast',expected,lambda case=case:validate(case))
    check(name+'_C',expected,lambda case=case:settle(case))

summary=dict(source_commit=SHA,total_cases=len(records),matched=sum(x['matched'] for x in records),
             expected_accept=sum(x['expected']=='ACCEPT' for x in records),expected_reject=sum(x['expected']=='REJECT' for x in records),
             mismatches=[x for x in records if not x['matched']],records=records)
(out/'results.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='records'},indent=2))
sys.exit(1 if summary['mismatches'] else 0)
