"""Frozen-cohort, common-random-number S4/J numerical sensitivity research.

This module never fits or issues a pregame forecast. The original frozen S4
and J paths remain byte-identical. We use the existing *unchanged* audited
chronological event kernel and strict independent admission of source/model
bytes in the separate CLI. Full-population accuracy is not inferred.
"""
from __future__ import annotations

import collections
import gzip
import math
import resource
import statistics
import time
from pathlib import Path

import numpy as np
from scipy.stats import beta as beta_distribution

from v2.nba_architecture.p1_subset_handoff_v1 import canonical, digest
from v2.nba_architecture.subset_p3_v1 import require
from v2.nba_joint.common import rng_for
from v2.nba_joint.coherent_predictive_v1 import (
    STATS, draw_parameters, fixed_scenario as original_fixed_scenario)
from v2.nba_joint.residual_audit_v1 import audit_path
from v2.nba_joint.residual_events_v1 import PathExecutionFailure, event_path
from v2.nba_joint.residual_opportunity_v1 import draw_team, audit_team

SEED = 2026112001
VARIANTS = (('original_beta', None), ('fixed_0', 0.0),
            ('fixed_0005', 0.005), ('fixed_001', 0.01),
            ('fixed_002', 0.02), ('fixed_005', 0.05))
TAIL_THRESHOLDS = {'points': 40, 'rebounds': 15, 'assists': 12,
                   'threes': 6, 'pr': 50, 'pa': 50, 'ra': 25, 'pra': 65}
PREFIX_SIZES = (64, 256, 1024, 5000, 20000)


class PairedZeroRNG:
    """Always consume the same underlying original Beta zero-mixture draws.

    A fixed-z intervention replaces only the *returned* zero weight. This
    wrapper must be used only for draw_team(), where beta(.5,49.5) is the
    sole beta call. Changing the RNG stream would destroy pairing.
    """
    def __init__(self, generator, weight):
        require(weight is None or (type(weight) is float and
                math.isfinite(weight) and 0 <= weight < 1),
                'S4_SENS_ZERO_WEIGHT')
        self.generator = generator
        self.weight = weight
        self.draw_count = 0

    def random(self, *args, **kwargs):
        return self.generator.random(*args, **kwargs)

    def beta(self, a, b, *args, **kwargs):
        require(a == 0.5 and b == 49.5 and not args and not kwargs,
                'S4_SENS_UNEXPECTED_BETA_CALL')
        original = float(self.generator.beta(a, b))
        self.draw_count += 1
        return original if self.weight is None else self.weight


def fixed_paired_scenario(model, seed, index, weight):
    """Model-fixed G, O, rate parameters; only O's zero-weight changes."""
    require(type(seed) is int and type(index) is int and index >= 0,
            'S4_SENS_SCENARIO_KEY')
    rng = rng_for(seed, model['target'], index,
                  'coherent-fixed-G-O-components/1')
    players = model['named_players']
    teams = sorted({p['team_id'] for p in players})
    require(len(teams) == 2 and len(players) == 14 and
            len({p['player_id'] for p in players}) == 14,
            'S4_SENS_MODEL_POPULATION')
    ots = {(p['minutes']['ot_probability'],
            p['minutes']['ot_continuation']) for p in players}
    require(len(ots) == 1, 'S4_SENS_SHARED_OVERTIME')
    p, q = next(iter(ots))
    k = int(rng.geometric(1 - q)) if rng.random() < p else 0
    length = 48 + 5 * k
    draws, actors = {}, {}

    for team in teams:
        group = [x for x in players if x['team_id'] == team]
        byid = {x['player_id']: x for x in group}
        wrapped = PairedZeroRNG(rng, weight)
        draw = draw_team(group, length, wrapped)
        require(wrapped.draw_count == len(group),
                'S4_SENS_EXACT_ONE_ZERO_DRAW_PER_NAMED')
        audit_team(draw, length)
        draws[team], actors[team] = draw, []
        residual = None
        for i, identity in enumerate(draw['actors']):
            pending = {}
            if identity['player_id']:
                params = draw_parameters(byid[identity['player_id']],
                                         rng, capture=pending)
            else:
                if residual is None:
                    residual = draw_parameters(model['residual_groups'][team],
                                               rng, capture=pending)
                params = residual.copy()
            actors[team].append(dict(identity=identity, index=i, **params))

    pace = float(rng.gamma(model['pace']['shape'],
                           model['pace']['scale']))
    require(math.isfinite(pace) and pace > 0, 'S4_SENS_PACE')
    ep = {key: float(rng.beta(v['alpha'], v['beta']))
          for key, v in model['events'].items()}
    require(all(math.isfinite(x) and 0 < x < 1 for x in ep.values()),
            'S4_SENS_EVENT_PARAMETERS')
    return dict(schema='coherent-fixed-G-O-components/1',
                index=index, seed=seed, game_id=model['target'],
                overtime_count=k, length=length, teams=teams, O=draws,
                actors=actors, pace=pace, event_probabilities=ep,
                rate_rejections=[], independent_points_threes_rejection=False,
                genuine_participation_probability=None,
                complete_legal_roster_claim=False)


def assert_original_fixed_parity(model, *, seed=SEED, indices=(0, 1, 2)):
    checks = []
    for index in indices:
        a = fixed_paired_scenario(model, seed, index, None)
        b = original_fixed_scenario(model, seed, index)
        require(canonical(a) == canonical(b),
                'S4_SENS_ORIGINAL_FIXED_BYTES_CHANGED')
        checks.append(dict(index=index, same_bytes=True,
                           fixed_raw_sha256=digest(canonical(a))))
    return checks


def fixed_pair_invariants(base, other):
    """Check intervention changes only opportunity minute/draw state."""
    require(base['index'] == other['index'] and
            base['seed'] == other['seed'] and
            base['overtime_count'] == other['overtime_count'] and
            base['length'] == other['length'] and
            base['teams'] == other['teams'] and
            base['pace'] == other['pace'] and
            canonical(base['event_probabilities']) ==
                canonical(other['event_probabilities']),
            'S4_SENS_UNPAIRED_SHARED_G')
    for team in base['teams']:
        a, b = base['actors'][team], other['actors'][team]
        require(len(a) == len(b) and
                canonical([{k:v for k,v in x.items() if k != 'identity'}
                           for x in a]) ==
                canonical([{k:v for k,v in x.items() if k != 'identity'}
                           for x in b]),
                'S4_SENS_PARAMETER_STREAM_DRIFT')
        require([x['identity'].get('player_id') for x in a] ==
                [x['identity'].get('player_id') for x in b],
                'S4_SENS_ACTOR_IDENTITY_DRIFT')
        for x, y in zip(a, b):
            if x['identity']['player_id']:
                require(x['identity']['zero_weight_model_draw'] !=
                        y['identity']['zero_weight_model_draw'] or
                        x['identity']['zero_weight_model_draw'] in (0.0, 0.005, 0.01, 0.02, 0.05),
                        'S4_SENS_ZERO_OVERRIDE_UNEXPECTED')
    return True


def _scenario(model, seed, index, name, weight, path_budget, event_budget):
    partial = dict(index=index, variant=name, zero_weight=weight,
                   seed=seed, status='FAILED', proposal_receipts=[])
    try:
        fixed = fixed_paired_scenario(model, seed, index, weight)
        partial.update(fixed_raw_sha256=digest(canonical(fixed)),
                       overtime_count=fixed['overtime_count'],
                       length=fixed['length'])
        for attempt in range(path_budget):
            try:
                proposal = event_path(fixed, seed, attempt,
                                      event_budget=event_budget)
            except PathExecutionFailure as exc:
                partial['proposal_receipts'].append(
                    dict(attempt=attempt, status='REJECT_EXECUTION',
                         error=str(exc),
                         partial_raw_sha256=digest(canonical(exc.partial))))
                partial['error'] = 'S4_SENS_EVENT_PATH_EXECUTION'
                return partial
            h = digest(canonical(proposal))
            partial['proposal_receipts'].append(
                dict(attempt=attempt, status=proposal['status'],
                     path_raw_sha256=h,
                     events=len(proposal['ledger'])))
            if proposal['status'] == 'ACCEPTED_PATH_PROPOSAL':
                audit_path(fixed, proposal)
                counts = {}
                for team, actors in fixed['actors'].items():
                    for actor in actors:
                        pid = actor['identity']['player_id']
                        if pid is None: continue
                        stats = proposal['counts'][team][actor['index']]
                        require(all(type(stats[s]) is int and stats[s] >= 0
                                    for s in STATS),
                                'S4_SENS_STAT_SUPPORT')
                        if fixed['O'][team]['minutes'][actor['index']] == 0:
                            require(all(v == 0 for v in stats.values()),
                                    'S4_SENS_ZERO_MINUTE_STATS')
                        counts[pid] = {s: stats[s] for s in STATS}
                require(len(counts) == 14, 'S4_SENS_NAMED_DENOMINATOR')
                partial.update(status='ACCEPTED_PATH',
                               counts=counts,
                               accepted_attempt=attempt,
                               retained_full_trace=False)
                return partial
            require(proposal['status'] == 'REJECT_OT_PATTERN',
                    'S4_SENS_UNEXPLAINED_PATH_REJECTION')
        partial['error'] = 'S4_SENS_PATH_BUDGET_EXHAUSTED'
    except Exception as exc:
        # Preserve a failed *whole* scenario rather than treating it as an
        # abstention / averaging a successfully generated subset.
        partial['error'] = type(exc).__name__ + ':' + str(exc)
    return partial


def _cp(k, n, alpha):
    require(0 <= k <= n and n > 0 and 0 < alpha < 1, 'S4_SENS_INTERVAL_ARGS')
    lower = 0. if k == 0 else float(beta_distribution.ppf(alpha/2,k,n-k+1))
    upper = 1. if k == n else float(beta_distribution.ppf(1-alpha/2,k+1,n-k))
    return [lower,upper]


def _pmf_cdf(values):
    hist = collections.Counter(values)
    n = len(values)
    run = 0
    pmf, cdf = {}, {}
    for x in sorted(hist):
        run += hist[x]
        pmf[str(x)] = hist[x]
        cdf[str(x)] = run/n
    return pmf,cdf


def _summary(values, alpha):
    n=len(values)
    require(n>0 and all(type(x) is int and x>=0 for x in values),
            'S4_SENS_INCOMPLETE_VALUES')
    ordered=sorted(values)
    def quantile(q):
        return ordered[max(0,math.ceil(q*n)-1)]
    pmf,cdf=_pmf_cdf(values)
    return dict(n=n,mean=math.fsum(values)/n,standard_deviation=statistics.pstdev(values),
                mass_at_zero=pmf.get('0',0)/n,
                q50=quantile(.5),q90=quantile(.90),
                q95=quantile(.95),q99=quantile(.99),
                pmf_counts=pmf,cdf=cdf)


def _sup_cdf(a,b):
    hist_a=collections.Counter(a);hist_b=collections.Counter(b)
    aa=bb=0;sup=0.
    for x in sorted(set(hist_a)|set(hist_b)):
        aa+=hist_a[x];bb+=hist_b[x]
        sup=max(sup,abs(aa/len(a)-bb/len(b)))
    return sup


def _analyze(samples, n, variants):
    nlabels=len(variants)
    alpha=.05/(112*nlabels)
    dkw=math.sqrt(math.log(2*112*nlabels/.05)/(2*n))
    result={}
    for name,_ in variants:
        by_player=samples[name]
        require(len(by_player)==14 and
                all(len(a[s])>=n for a in by_player.values() for s in STATS),
                'S4_SENS_SUMMARY_DENOMINATOR')
        rows={}
        for pid in sorted(by_player):
            for stat in STATS:
                values=by_player[pid][stat][:n]
                info=_summary(values,alpha)
                k=sum(x>=TAIL_THRESHOLDS[stat] for x in values)
                info['tail_threshold_inclusive']=TAIL_THRESHOLDS[stat]
                info['tail_hits']=k
                info['tail_fraction']=k/n
                info['tail_mc_interval_simultaneous_fixed_threshold']=_cp(k,n,alpha)
                rows[pid+'/'+stat]=info
        result[name]=rows
    compare={}
    for name,_ in variants:
        if name=='original_beta': continue
        pair={}
        for key in result['original_beta']:
            pid,stat=key.rsplit('/',1)
            b=samples['original_beta'][pid][stat][:n]
            a=samples[name][pid][stat][:n]
            diffs=[x-y for x,y in zip(a,b)]
            pair[key]=dict(sup_empirical_cdf_difference=_sup_cdf(a,b),
                           paired_mean_difference=math.fsum(diffs)/n,
                           paired_mean_mc_se=(statistics.stdev(diffs)/math.sqrt(n)
                                             if n>1 else None))
        compare[name]=pair
    return dict(scenarios=n,supported_marginals=112,
                variants=nlabels,dkw_family_epsilon_ideal_iid=dkw,
                dkw_assumptions_verified=False,
                tail_interval_family_alpha=.05,
                forecasts=result,comparisons=compare)


def simulate_sensitivity(model,cohort,out,*,seed=SEED,
                         n=64,variants=VARIANTS,
                         path_budget=4096,event_budget=4096,
                         chunk_size=16,max_wall_seconds=None):
    require(type(n) is int and 1<=n<=20000 and type(seed) is int and
            type(path_budget) is int and path_budget>0 and
            type(event_budget) is int and event_budget>0 and
            type(chunk_size) is int and chunk_size>0 and
            max_wall_seconds is None or (type(max_wall_seconds) in (int,float) and max_wall_seconds>0),
            'S4_SENS_BUDGET')
    require(len(variants)==len(set(x[0] for x in variants)) and
            variants[0] == ('original_beta',None),'S4_SENS_VARIANTS')
    require(model['target'] == cohort['game_id'] == '401910026' and
            len(cohort['frozen_candidates'])==35 and
            len(model['named_players'])==14,'S4_SENS_FROZEN_COHORT')
    ids={p['player_id']:p['team_id'] for p in cohort['frozen_candidates']}
    require(len(ids)==35 and
            all(ids.get(p['player_id'])==p['team_id']
                for p in model['named_players']),
            'S4_SENS_COHORT_IDENTITY')
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    t0=time.monotonic()
    samples={name:{p['player_id']:{s:[] for s in STATS}
                   for p in model['named_players']}
             for name,_ in variants}
    status={name:dict(requested=n,completed=0,failed=0,
                      proposals=0,ot_rejections=0,errors=[])
            for name,_ in variants}
    chunks=[];buffer=[];timeout=False
    parity=assert_original_fixed_parity(model,seed=seed,indices=(0,1,2))
    for i in range(n):
        if max_wall_seconds is not None and time.monotonic()-t0>max_wall_seconds:
            timeout=True;break
        base_fixed=fixed_paired_scenario(model,seed,i,None)
        for name,weight in variants:
            if weight is not None:
                fixed_pair_invariants(base_fixed,
                    fixed_paired_scenario(model,seed,i,weight))
            rec=_scenario(model,seed,i,name,weight,path_budget,event_budget)
            status[name]['proposals']+=len(rec['proposal_receipts'])
            status[name]['ot_rejections']+=sum(
                q['status']=='REJECT_OT_PATTERN'
                for q in rec['proposal_receipts'])
            if rec['status']=='ACCEPTED_PATH':
                status[name]['completed']+=1
                for pid,stats in rec['counts'].items():
                    for stat,val in stats.items():
                        samples[name][pid][stat].append(val)
            else:
                status[name]['failed']+=1
                status[name]['errors'].append(dict(index=i,error=rec.get('error')))
            buffer.append(rec)
        if len(buffer)>=len(variants)*chunk_size or i==n-1:
            raw=b''.join(canonical(x)+b'\n' for x in buffer)
            gz=gzip.compress(raw,compresslevel=9,mtime=0)
            fn='chunk-%06d-%06d.jsonl.gz'%(i+1-len(buffer)//len(variants),i)
            (out/fn).write_bytes(gz)
            chunks.append(dict(path=fn,rows=len(buffer),
                               gzip_raw_sha256=digest(gz),gzip_bytes=len(gz),
                               raw_sha256=digest(raw),raw_bytes=len(raw)))
            buffer.clear()
    if buffer:
        # A time-budget stop may leave a final short chunk.
        raw=b''.join(canonical(x)+b'\n' for x in buffer)
        gz=gzip.compress(raw,compresslevel=9,mtime=0)
        fn='chunk-partial.jsonl.gz'
        (out/fn).write_bytes(gz)
        chunks.append(dict(path=fn,rows=len(buffer),
                           gzip_raw_sha256=digest(gz),gzip_bytes=len(gz),
                           raw_sha256=digest(raw),raw_bytes=len(raw)))
    wall=time.monotonic()-t0
    whole=not timeout and all(s['completed']==n and s['failed']==0 for s in status.values())
    receipt=dict(schema='nba-s4-J-CRN-zero-sensitivity/1',
                 scientific_status='NUMERICAL_RESEARCH_SAMPLE' if whole else 'FAILED_INCOMPLETE',
                 requested_per_variant=n,variants=[dict(name=x,weight=z) for x,z in variants],
                 seed=seed,model_semantic_sha256=digest(canonical(model)),
                 cohort_semantic_sha256=digest(canonical(cohort)),
                 parity=parity,by_variant=status,chunks=chunks,
                 chunk_row_denominator=sum(x['rows'] for x in chunks),
                 completed_variants=whole,path_budget=path_budget,
                 event_budget=event_budget,max_wall_seconds=max_wall_seconds,
                 stopped_by_time_budget=timeout,wall_seconds=wall,
                 max_rss_kb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                 source_population_changed=False,
                 actual_forecast_issued=False,outcomes_scored=0,
                 genuine_participation_proven=False,
                 historical_validation=False,production_release=False)
    if whole:
        receipt['prefix_scores']={str(x):_analyze(samples,x,variants)
                                  for x in PREFIX_SIZES if x<=n}
        if n not in PREFIX_SIZES:
            receipt['prefix_scores'][str(n)]=_analyze(samples,n,variants)
        require(receipt['chunk_row_denominator']==n*len(variants),
                'S4_SENS_CHUNK_DENOMINATOR')
    (out/'RECEIPT.json').write_bytes(canonical(receipt)+b'\n')
    return receipt
