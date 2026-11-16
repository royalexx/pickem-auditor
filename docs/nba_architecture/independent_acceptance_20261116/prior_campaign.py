"""Independent PR156 audit. Run from the exact checkout; writes outside it.

Exit 1 means a G0 violation was accepted, not an environment/import failure.
"""
import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import sys

SHA = '59d28dc23be97de2a6a82d22be8338151e31f5b6'
ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True)
args = ap.parse_args()
root = Path.cwd()
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == SHA
sys.path[:0] = [str(root), str(root / 'tests/nba_architecture')]
from golden_v2 import distribution, original_offer, pregame
from test_g0_pipeline_completion_20261116 import coherent_case
from test_v2_contracts import evaluation, reissue
from v2.nba_architecture.v2_contracts import (
    ContractError, canonical, seal, verify, parse_contract, validate_pregame,
    marginal_from_joint, offer_view, threshold_triplet,
)
from v2.nba_architecture.families_v2 import (
    validate_forecast, validate_settlement, validate_opportunity,
)

out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)
results = []

def edit(obj, **changes):
    x = copy.deepcopy(obj)
    x.pop('content_hash')
    x.update(changes)
    return seal(x)

def save(name, obj):
    (out / (name + '.json')).write_bytes(canonical(obj) + b'\n')

def check(name, expected, fn):
    try:
        result = fn()
        actual, code = 'ACCEPT', None
        assert result is True or isinstance(result, dict)
    except ContractError as exc:
        actual, code = 'REJECT', exc.code
    except Exception as exc:
        actual, code = 'ERROR', repr(exc)
    results.append(dict(name=name, expected=expected, actual=actual, code=code,
                        matched=actual == expected))

def forecast(c):
    return validate_forecast(c['points'], c['pregame'], g=c['game_state'],
                             o=c['opportunity'], scenarios=c.get('scenarios'))

def settle(c, e=None, **kw):
    d = c['points']
    return validate_settlement(e or evaluation(d), d, c['pregame'],
                              g=c['game_state'], o=c['opportunity'],
                              scenarios=c.get('scenarios'), **kw)

def join_o(c, opportunity):
    c = copy.deepcopy(c)
    c['opportunity'] = edit(opportunity)
    if 'scenarios' in c:
        c['scenarios'] = edit(c['scenarios'], opportunity_sha256=c['opportunity']['content_hash'])
        c['points'] = marginal_from_joint(c['scenarios'], c['pregame'],
            c['points']['player_id'], c['points']['stat'], c['points']['frozen_at'], 42)
    return c

base = coherent_case()
check('baseline_complete_forecast', 'ACCEPT', lambda: forecast(base))
check('baseline_complete_settlement', 'ACCEPT', lambda: settle(base))

# F1: No joint law can realize this atom. Enumeration is independent of the
# validator, uses supports not observed MC frequencies, and allows arbitrary
# dependence and DNP for every player with unknown participation probability.
bad = copy.deepcopy(base)
op = bad['opportunity']
target = op['players'][0]
target.update(participation_probability=1., participation_evidence='independently_estimated')
target['minutes_law']['parameters']['support'] = [
    {'minutes': 0., 'mass': .5}, {'minutes': 48., 'mass': .5}]
bad = join_o(bad, op)
team = target['team_id']
people = [x for x in op['players'] if x['team_id'] == team]
supports = []
for person in people:
    support = {a['minutes'] for a in person['minutes_law']['parameters']['support']}
    if person['participation_probability'] != 1:
        support.add(0.)
    supports.append(sorted(support))
assignments = list(itertools.product(*supports))
feasible = [x for x in assignments if sum(x) == 240]
assert feasible and all(x[0] == 48 for x in feasible)
assert not any(x[0] == 0 for x in feasible)
bad['independent_oracle'] = dict(team_minutes=240, enumerated_assignments=len(assignments),
    feasible_assignments=len(feasible), feasible_target_minutes=sorted({x[0] for x in feasible}),
    impossible_declared_atom=dict(minutes=0, mass=.5))
save('F1_infeasible_minutes_law', bad)
check('F1_infeasible_law_at_O', 'REJECT', lambda: validate_opportunity(bad['opportunity'], bad['pregame'], bad['game_state']))
check('F1_infeasible_law_at_forecast', 'REJECT', lambda: forecast(bad))
check('F1_infeasible_law_at_C', 'REJECT', lambda: settle(bad))
good = copy.deepcopy(bad['opportunity'])
good['players'][0]['minutes_law']['parameters']['support'] = [{'minutes':48.,'mass':1.}]
good = join_o(base, good)
check('F1_point48_positive_control', 'ACCEPT', lambda: forecast(good))

# A genuine two-player, anti-correlated allocation makes the same half-zero
# minute law feasible. This distinguishes conservation from frequency matching.
balanced = copy.deepcopy(base)
j = balanced['scenarios']
op = balanced['opportunity']
for sc in j['scenarios']:
    sc['weight'] = .5
    sid = sc['scenario_id']
    j['game_state_witness'][sid]['weight'] = .5
    if sid.endswith(':1'):
        first, bench = sc['players'][0], sc['players'][5]
        bench.update(minutes=48., participation='PLAYED', stats=first['stats'])
        from golden_v2 import zero_stats
        first.update(minutes=0., participation='PLAYED_ZERO_MINUTES', stats=zero_stats())
    else:
        sc['players'][5]['participation'] = 'PLAYED_ZERO_MINUTES'
    j['opportunity_witness'][sid] = [{k:x[k] for k in ('player_id','team_id','participation','minutes')} for x in sc['players']]
for i in (0,5):
    op['players'][i].update(participation_probability=1.,participation_evidence='independently_estimated')
    op['players'][i]['minutes_law']['parameters']['support'] = [{'minutes':0.,'mass':.5},{'minutes':48.,'mass':.5}]
for os,js in zip(op['scenarios'],j['scenarios']):
    os.update(weight=.5,players=[{k:x[k] for k in ('player_id','team_id','participation','minutes')} for x in js['players']])
g = copy.deepcopy(balanced['game_state'])
for row in g['scenarios']: row['weight'] = .5
g = edit(g)
balanced['game_state'] = g
op['game_state_sha256'] = g['content_hash']
j['game_state_sha256'] = g['content_hash']
balanced = join_o(balanced,op)
save('F1_feasible_balanced_control',balanced)
check('F1_feasible_half_zero_law_control','ACCEPT',lambda:forecast(balanced))

# F2: In S_O, a normalized law with support {0} cannot generate positive
# points/rebounds/assists/threes or any of their nonnegative sums, whether the
# player DNPs or genuinely participates at zero minutes.
so = copy.deepcopy(base)
so.pop('scenarios')
pid = so['pregame']['players'][5]['player_id']
for stat in ('points','rebounds','assists','threes','pr','pa','ra','pra'):
    d = distribution(so['pregame'], stat=stat, mode='S_O')
    d['lineage']['G'] = so['game_state']['model']
    d = edit(d, player_id=pid, opportunity_output_sha256=so['opportunity']['content_hash'])
    case = dict(so, points=d)
    check('F2_zero_exposure_positive_' + stat, 'REJECT', lambda case=case: forecast(case))
    zero = dict(case, points=edit(d, pmf=[{'value':0,'mass':1.}]))
    check('F2_zero_count_control_' + stat, 'ACCEPT', lambda zero=zero: forecast(zero))
    if stat == 'points':
        q = edit(original_offer(so['pregame']), player_id=pid)
        v = offer_view(d, q, so['pregame'], '2026-11-16T23:04:00Z')
        e = evaluation(d, v, actual=0, participation='PLAYED_ZERO_MINUTES')
        save('F2_zero_exposure_positive_count', dict(case, quote=q, view=v, evaluation=e))
        check('F2_at_C_with_original_quote', 'REJECT', lambda case=case,e=e,v=v,q=q: settle(case,e,view=v,quote=q))
        assert v['probabilities'] == {'over':.75,'under':.25,'push':0}

# Full-boundary original-object attacks: changed context, not merely bad hashes.
for kind, field, value in (
    ('game_state','game_id','espn:game:other'),
    ('opportunity','source_snapshot_sha256','f'*64),
    ('scenarios','game_state_sha256','f'*64),
):
    c = copy.deepcopy(base)
    c[kind] = edit(c[kind], **{field:value})
    if kind == 'scenarios':
        c['points'] = marginal_from_joint(c['scenarios'], c['pregame'],
             c['points']['player_id'], 'points', c['points']['frozen_at'], 42)
    check('original_context_' + kind, 'REJECT', lambda c=c: forecast(c))

# Three-record corrections: revalidation must include oldest semantic state.
d = base['points']
a = evaluation(d)
b = evaluation(d, revision=2, previous=a['content_hash'], actual=3)
b = edit(b, evaluated_at='2026-11-17T03:01:00Z')
c = evaluation(d, revision=3, previous=b['content_hash'], actual=4)
c = edit(c, evaluated_at='2026-11-17T03:02:00Z')
check('three_revision_valid_history', 'ACCEPT', lambda: settle(base,c,history=[a,b]))
for name, history in [('missing_oldest',[b]),('reordered',[b,a]),('duplicate',[a,a,b])]:
    check('history_' + name, 'REJECT', lambda history=history: settle(base,c,history=history))
bad_a = edit(a, status='settled', participation='DNP', actual=0)
bad_b = edit(b, supersedes_evaluation_sha256=bad_a['content_hash'])
bad_c = edit(c, supersedes_evaluation_sha256=bad_b['content_hash'])
check('history_invalid_grandparent_resealed_chain', 'REJECT', lambda: settle(base,bad_c,history=[bad_a,bad_b]))
bad_c = edit(c, evaluated_at='2026-11-17T03:00:30Z')
check('history_time_reverse', 'REJECT', lambda: settle(base,bad_c,history=[a,b]))

# Strict ingestion attacks use escape-equivalent keys, exponent overflow and
# nested terms. They do not depend on an unsealed root being rejected first.
raw = canonical(base['pregame']).decode()
check('ingest_valid', 'ACCEPT', lambda: parse_contract(raw))
for name, invalid in (
    ('escaped_duplicate',raw.replace('"game_id":','"g\\u0061me_id":"espn:game:ignored","game_id":',1)),
    ('nested_duplicate',raw.replace('"features":[','"features":[',1).replace('"kind":"schedule"','"kind":"schedule","k\\u0069nd":"schedule"',1)),
    ('exponent_overflow',raw.replace('"original_offer_count":1','"original_offer_count":1e9999',1)),
    ('trailing_record',raw+raw),
):
    assert invalid != raw
    check('ingest_' + name, 'REJECT', lambda invalid=invalid: parse_contract(invalid))

# Numeric probability references use exact rational arithmetic and adjacent
# representable thresholds, rather than SciPy as their only oracle.
from fractions import Fraction
import math
pmf = [{'value':0,'mass':.125},{'value':3,'mass':.375},{'value':7,'mass':.5}]
for line in (0, math.nextafter(3.,-math.inf), 3., math.nextafter(3.,math.inf), 7., 7.5):
    got = threshold_triplet(pmf,line)
    want = {label:float(sum((Fraction.from_float(x['mass']) for x in pmf if pred(x['value'],line)),Fraction()))
            for label,pred in [('under',lambda x,y:x<y),('over',lambda x,y:x>y),('push',lambda x,y:x==y)]}
    assert got == want and sum(got.values()) == 1.
    check('rational_triplet_' + repr(line), 'ACCEPT', lambda got=got: got)

# Source identity/correction attacks and a nonblocking observation: the
# candidate expressly forbids stale feature refs, but not stale roster refs.
p = pregame('original_prospective')
r = p['sources'][0]
r2 = reissue(r, source_revision=2, supersedes_receipt_sha256=r['receipt_sha256'],raw_sha256='d'*64)
p = edit(p, sources=[r,r2])
f = copy.deepcopy(p['features']);f[0]['source_receipt_sha256']=r2['receipt_sha256']
p = edit(p, features=f)
players = copy.deepcopy(p['players'])
players[0].update(availability='questionable',availability_evidence=dict(
    source_receipt_sha256=r['receipt_sha256'],player_id=players[0]['player_id'],
    game_id=p['game_id'],field='availability',value='questionable'))
stale = edit(p,players=players)
check('observation_stale_roster_revision_current_feature', 'ACCEPT', lambda: validate_pregame(stale))
save('observation_stale_roster_revision',stale)
wrong = copy.deepcopy(players)
wrong[0]['availability_evidence']['game_id']='espn:game:other'
check('roster_wrong_evidence_identity','REJECT',lambda:validate_pregame(edit(p,players=wrong)))
spliced = reissue(r2,source_id='espn:source:unrelated')
check('source_cross_identity_parent','REJECT',lambda:validate_pregame(edit(p,sources=[r,spliced])))

summary = dict(source_commit=SHA, total_cases=len(results),
    matched=sum(r['matched'] for r in results),
    accepted_violations=[r['name'] for r in results if r['expected']=='REJECT' and r['actual']=='ACCEPT'],
    execution_errors=[r for r in results if r['actual']=='ERROR'],results=results,
    decision='G0_FAIL' if any(not r['matched'] for r in results) else 'PRIOR_CAMPAIGN_ALL_EXPECTATIONS_MET',implementation_changed=False)
save('independent_results',summary)
print(json.dumps({k:v for k,v in summary.items() if k!='results'},indent=2))
sys.exit(1 if any(not r['matched'] for r in results) else 0)
