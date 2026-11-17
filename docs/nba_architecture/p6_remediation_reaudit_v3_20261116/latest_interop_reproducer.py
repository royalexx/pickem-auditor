import sys,os,json,hashlib,subprocess,copy
from pathlib import Path
import argparse
ap=argparse.ArgumentParser();ap.add_argument('--p2-root',type=Path,required=True);args=ap.parse_args()
import v2
v2.__path__.append(str(args.p2_root/'v2'))
sys.path.append(str(args.p2_root/'tests/nba_s_family'))
from test_p3_o_family import build
from test_statistical import histories,manifest,CUTOFF
from v2.nba_s_family.model import fit,predict,conditional_pmf
from v2.nba_s_family.integration import joint_conditional,history_from_p1
from v2.nba_architecture.v2_contracts import canonical
p,g,o,side=build('O2');f=fit(histories(),source_manifest=manifest(),asof_cutoff_utc=CUTOFF,stat='points')
args=dict(frozen_pregame=p,target_player_id='espn:player:10',role='wing',opportunity=o,game_state=g)
a=predict(f,**args);b=predict(f,**args,conditioning='conditional_on_participation');assert a.abstain_reason=='UNKNOWN_APPEARANCE_PROBABILITY';assert b.abstain_reason is None,b.abstain_reason
pmfs=[];weights=[];kernels=[]
for sc in o['scenarios']:
 row=next(x for x in sc['players'] if x['player_id']=='espn:player:10')
 if row['participation']=='DNP':continue
 mass,tail,_=conditional_pmf(f,player_id=row['player_id'],role='wing',opportunity=row['minutes']);pmfs.append(mass);weights.append(sc['weight'])
 k=joint_conditional(f,pregame=p,game_state=g,opportunity=o,scenario_id=sc['scenario_id'],player_id=row['player_id'],team_id=row['team_id'],role='wing');kernels.append(k)
ref=[sum(w*(m[i] if i<len(m) else 0) for w,m in zip(weights,pmfs))/sum(weights) for i in range(max(map(len,pmfs)))];actual=[x['mass'] for x in b.distribution['pmf']];err=max(abs(x-y) for x,y in zip(ref,actual));assert err<1e-12
result=dict(status='PASS_SYNTHETIC_LATEST_P3_TO_LATEST_P2',P3='191b3f654b3a3ca7dc813edbfc9aacdf35729dff',P2='7ca4269c98a27def485eaa8122ea7148cd0c2c0a',unconditional_abstention=a.abstain_reason,conditional_distribution=b.distribution,opportunity_sha256=o['content_hash'],sidecar_sha256=side['content_hash'],manual_mixture_max_error=err,conditional_kernels=kernels)
print(json.dumps(result,sort_keys=True,indent=2))
