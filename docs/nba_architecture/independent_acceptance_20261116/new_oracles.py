"""Independent exact-rational exposure oracles for PR157; no source edits."""
import copy
from fractions import Fraction as F
import hashlib
import itertools
import json
from pathlib import Path
import random
import subprocess
import sys

ROOT=Path.cwd()
SHA='59d28dc23be97de2a6a82d22be8338151e31f5b6'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==SHA
sys.path[:0]=[str(ROOT),str(ROOT/'tests/nba_architecture')]
from v2.nba_architecture.exposure_v2 import _check_team
from v2.nba_architecture.v2_contracts import ContractError
out=Path('/workspace/work/evidence157/new-oracles');out.mkdir(parents=True,exist_ok=True)
records=[]

def run(name,players,groups,expected,witnesses=(),bound_reference=None):
    try:
        result=_check_team(players,groups,witnesses)
        outcome='ACCEPT';code=None
        if bound_reference is not None:
            assert all(abs(got-want)<=2e-12 for got,want in zip(result[0],bound_reference)),(result[0],bound_reference)
    except ContractError as exc:
        outcome='REJECT';code=exc.code
    except Exception as exc:
        outcome='ERROR';code=repr(exc)
    records.append(dict(name=name,expected='ACCEPT' if expected else 'REJECT',actual=outcome,code=code,
                        matched=outcome==('ACCEPT' if expected else 'REJECT')))

def atoms(a,b):
    # a=P(48), b=P(24); remaining mass is genuine played-zero.
    return tuple((float(m),float(p)) for m,p in ((0,1-a-b),(24,b),(48,a)) if p)

fixed=((1.,((48.,1.),)),)*4
rng=random.Random(15720261116)

# Four fixed players leave a pool of 48 for three other players on {0,24,48}.
# The six conserving allocations are pure 48_i and paired (24_i,24_j).
# Thus x_i=a_i and x_ij=(b_i+b_j-b_k)/2 uniquely. These exact fractions give
# an independent necessary AND sufficient feasibility oracle, without an LP.
def exact(a,b):
    pairs=((b[0]+b[1]-b[2])/2,(b[0]+b[2]-b[1])/2,(b[1]+b[2]-b[0])/2)
    feasible=sum(a)+sum(b)/2==1 and min(pairs)>=0
    return feasible,tuple(a)+pairs

laws=[(F(i,8),F(j,8)) for i in range(9) for j in range(9-i)]
for n in range(300):
    ab=[rng.choice(laws) for _ in range(3)]
    a,b=tuple(x[0] for x in ab),tuple(x[1] for x in ab)
    expected,_=exact(a,b)
    players=tuple((1.,atoms(x,y)) for x,y in zip(a,b))+fixed
    run(f'three_player_arbitrary_marginals_{n}',players,((0,1.),),expected)

# Construct valid distributions directly on the six allocations. Each unique
# joint mass then also supplies an exact oracle for positive sampled support.
templates=((48,0,0),(0,48,0),(0,0,48),(24,24,0),(24,0,24),(0,24,24))
for n in range(80):
    counts=[rng.randrange(5) for _ in range(6)]
    if not sum(counts): counts[0]=1
    joint=tuple(F(x,sum(counts)) for x in counts)
    a=joint[:3]
    b=(joint[3]+joint[4],joint[3]+joint[5],joint[4]+joint[5])
    expected,recovered=exact(a,b)
    assert expected and recovered==joint
    players=tuple((1.,atoms(x,y)) for x,y in zip(a,b))+fixed
    run(f'constructed_three_player_law_{n}',players,((0,1.),),True)
    for k,minutes in enumerate(templates):
        state=tuple(('PLAYED' if m else 'PLAYED_ZERO_MINUTES',float(m)) for m in minutes)+(('PLAYED',48.),)*4
        run(f'exact_joint_witness_{n}_{k}',players,((0,1.),),joint[k]>0,((0,state),))

# Unknown participation: with conditional {0,48} laws, conservation is exactly
# sum_i q_i*r_i=1. All unspecified q_i may vary independently over [0,1].
# Existence and the maximum of q_0 follow from interval arithmetic over rationals.
values=(F(0),F(1,4),F(1,2),F(3,4),F(1))
q_values=(None,F(0),F(1,4),F(1,2),F(1))
for n in range(150):
    r=tuple(rng.choice(values) for _ in range(3))
    q=tuple(rng.choice(q_values) for _ in range(3))
    known=sum((x*y for x,y in zip(q,r) if x is not None),F())
    possible=known<=1<=known+sum((y for x,y in zip(q,r) if x is None),F())
    players=tuple((None if x is None else float(x),atoms(y,F(0))) for x,y in zip(q,r))+fixed
    bound=None
    if possible:
        maximum=(F(1) if r[0]==0 else min(F(1),(1-known)/r[0])) if q[0] is None else q[0]
        bound=(float(maximum),float(maximum*r[0]))
    run(f'unknown_participation_interval_{n}',players,((0,1.),),possible,bound_reference=bound)

# OT mixtures: exactly five players with {48,58} support must all be 48 in
# regulation and 58 in double OT. Their atom masses must equal G's OT masses.
for n in range(1,16):
    f=F(n,16)
    groups=((0,float(f)),(2,float(1-f)))
    players=((1.,((48.,float(f)),(58.,float(1-f)))),)*5+((1.,((0.,1.),)),)
    run(f'ot_mixture_rational_{n}',players,groups,True)
    wrong=list(players)
    other=F(1,2) if f!=F(1,2) else F(1,4)
    wrong[2]=(1.,((48.,float(other)),(58.,float(1-other))))
    run(f'ot_one_player_probability_drift_{n}',tuple(wrong),groups,False)

# Harmless representations: consistent permutations and per-G subdivision.
players=((1.,((0.,.25),(24.,.5),(48.,.25))),)*2+((1.,((48.,1.),)),)*4
for n in range(20):
    indices=list(range(len(players)));rng.shuffle(indices)
    permuted=tuple(players[i] for i in indices)
    run(f'permutation_{n}',permuted,((0,1.),),True)

summary=dict(source_commit=SHA,seed=15720261116,total_cases=len(records),
    expected_accept=sum(r['expected']=='ACCEPT' for r in records),
    expected_reject=sum(r['expected']=='REJECT' for r in records),
    matched=sum(r['matched'] for r in records),
    mismatches=[r for r in records if not r['matched']],records=records)
(out/'results.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='records'},indent=2))
sys.exit(1 if summary['mismatches'] else 0)
