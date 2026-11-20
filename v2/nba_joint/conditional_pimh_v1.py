"""Bootstrap particle filter + particle-independent Metropolis--Hastings.

For fixed S4/J G/O/rates, the *unmodified* chronological event law has
a conditional target P(path | tie at regulation and every nonfinal OT,
non-tie at final period). Ordinary full-path rejection is exact but can be
extremely inefficient.

A bootstrap particle filter (BPF) with period-end indicator potentials
produces an unbiased nonnegative estimate Z_hat of the event evidence.
The particle-independent Metropolis-Hastings (PIMH) transition accepts
independent (path, Z_hat) proposals with min(1,Z_hat_new/Z_hat_old).
By the extended-space pseudo-marginal construction, its invariant
marginal is the original event path conditional distribution.

IMPORTANT: A finite-length PIMH chain is NOT an exact iid draw.
A source-equivalent law, an exact invariant distribution, good acceptance
and independent-chain diagnostics are all distinct claims. Production or
numerical gate approval requires independent convergence assessment.
"""
from __future__ import annotations

import math
import copy

from v2.nba_joint.common import rng_for
from v2.nba_joint.conditional_periods_v1 import (
    SCHEMA,empty_state,stage_transition,finalize_path)
from v2.nba_architecture.subset_p3_v1 import require
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest

VERSION='nba-conditional-OT-PIMH/1'


def bootstrap_particle_filter(fixed,seed,replicate,*,particles=128,
                              event_budget=4096):
    """Independent bootstrap filter, indicator weight at each OT boundary.

    Each stage's surviving paths are equally weighted; multinomial
    resampling is exact given the finite particle population.
    Normalizing estimator product_j (#survivors_j / particles) is unbiased
    for P(original-path matches K | fixed G/O/rates). This is the
    extended-target correction, NOT a replacement predictive prior.
    """
    require(type(seed) is int and type(replicate) is int and replicate>=0 and
            type(particles) is int and particles>=2 and
            type(event_budget) is int and event_budget>=16,
            'PIMH_PARAMETERS')
    k=fixed['overtime_count'];n=particles
    parents=[empty_state(fixed) for _ in range(n)]
    stages=[];logZ=0.;failed=0;completed=0
    for stage in range(k+1):
        survivors=[]
        for i,prev in enumerate(parents):
            rng=rng_for(seed,fixed['game_id'],fixed['index'],
                f'conditional-pf/1/rep:{replicate}/stage:{stage}/particle:{i}')
            current,valid=stage_transition(fixed,prev,rng,stage,event_budget=event_budget)
            if valid:survivors.append(current)
            completed+=1
        alive=len(survivors)
        stages.append(dict(stage=stage,particles=n,survivors=alive,
                           indicator_fraction=alive/n,
                           requires_equal_final_score=stage<k))
        if not alive:
            return dict(status='ZERO_PARTICLE_EVIDENCE',path=None,logZ=None,
                        evidence_estimate=0.,stages=stages,
                        stage_proposals=completed,
                        replicate=replicate)
        logZ+=math.log(alive/n)
        selector=rng_for(seed,fixed['game_id'],fixed['index'],
                  f'conditional-pf/1/rep:{replicate}/resample:{stage}')
        if stage<k:
            indexes=selector.integers(alive,size=n)
            parents=[survivors[int(j)] for j in indexes]
        else:
            selected=survivors[int(selector.integers(alive))]
    path=finalize_path(fixed,selected)
    return dict(status='POSITIVE_PARTICLE_EVIDENCE',path=path,logZ=logZ,
                evidence_estimate=math.exp(logZ),
                stages=stages,stage_proposals=completed,replicate=replicate,
                path_raw_sha256=digest(canonical(path)))


def pimh_sample(fixed,seed,*,particles=128,iterations=32,
                proposal_budget=256,event_budget=4096,
                chain=0,minimum_accepted_moves=3):
    """Finite PIMH research chain, NEVER claim exact iid samples.

    No steps are omitted from the acceptance/rejection receipt.
    Failed zero-evidence proposals have MH probability zero.
    We require multiple actual moves to avoid an unnoticed frozen chain.
    Convergence, coupling and burn-in remain separate scientific gates.
    """
    require(type(iterations) is int and iterations>=2 and
            type(proposal_budget) is int and proposal_budget>=iterations and
            type(chain) is int and chain>=0 and
            type(minimum_accepted_moves) is int and 0<=minimum_accepted_moves<iterations,
            'PIMH_CHAIN_BUDGET')
    current=None;receipts=[];moves=0;attempts=0
    while attempts<proposal_budget and len(receipts)<iterations:
        rep=chain*1000000+attempts
        proposed=bootstrap_particle_filter(fixed,seed,rep,particles=particles,
                                           event_budget=event_budget)
        attempts+=1
        accept=False
        if proposed['status']=='POSITIVE_PARTICLE_EVIDENCE':
            if current is None:accept=True
            else:
                u=float(rng_for(seed,fixed['game_id'],fixed['index'],
                    f'conditional-pimh/1/chain:{chain}/proposal:{attempts}').random())
                accept=math.log(max(u,1e-300))<min(0.,proposed['logZ']-current['logZ'])
        if accept:
            current=proposed
            moves+=1
        receipts.append(dict(proposal=attempts,proposal_status=proposed['status'],
                             proposed_logZ=proposed['logZ'],
                             selected_logZ=None if current is None else current['logZ'],
                             move_accepted=accept,particle_stages=proposed['stages'],
                             current_path_sha256=None if current is None else
                               current['path_raw_sha256']))
    complete=(current is not None and len(receipts)==iterations and
              moves-1>=minimum_accepted_moves)
    return dict(schema=VERSION,
                status='RESEARCH_FINITE_CHAIN_MIXED' if complete else
                       'FAIL_CANNOT_ASSESS_MIXING',
                path=current['path'] if current else None,
                iterations=len(receipts),accepted_moves=moves,
                post_initial_accepted_moves=max(0,moves-1),
                zero_evidence_proposals=sum(x['proposal_status']=='ZERO_PARTICLE_EVIDENCE'
                                            for x in receipts),
                particles=particles,chain=chain,
                proposal_budget=proposal_budget,
                proposals=receipts,
                exact_original_conditional_law_is_stationary=True,
                finite_chain_is_exact_iid=False,
                independent_P6_convergence_accepted=False,
                accepted_path_raw_sha256=current['path_raw_sha256'] if current else None)


def exact_rejection_for_k_le_1(fixed,seed,*,budget=4096,event_budget=4096):
    """Unmodified exact conditional rejection for 0/1 overtime."""
    from v2.nba_joint.residual_events_v1 import event_path
    from v2.nba_joint.residual_audit_v1 import audit_path
    rejected=[]
    for attempt in range(budget):
        path=event_path(fixed,seed,attempt,event_budget=event_budget)
        if path['status']=='ACCEPTED_PATH_PROPOSAL':
            audit_path(fixed,path)
            return dict(schema=VERSION,status='EXACT_ORIGINAL_CONDITIONAL_REJECTION',
                        path=path,rejected_count=attempt,accepted_attempt=attempt,
                        accepted_path_raw_sha256=digest(canonical(path)),
                        exact_original_conditional_law_is_stationary=True,
                        finite_chain_is_exact_iid=True,
                        independent_P6_convergence_accepted=False)
        require(path['status']=='REJECT_OT_PATTERN','PIMH_UNEXPECTED_REJECTION')
        rejected.append(digest(canonical(path)))
    return dict(schema=VERSION,status='FAIL_REJECTION_BUDGET',
                rejected_count=len(rejected),
                rejected_path_sha256=digest(canonical(rejected)),
                path=None,exact_original_conditional_law_is_stationary=True,
                finite_chain_is_exact_iid=False,
                independent_P6_convergence_accepted=False)


def conditional_event_path(fixed,seed,*,particles=128,iterations=32,
                           budget=4096,event_budget=4096,
                           min_moves=3):
    if fixed['overtime_count']<=1:
        return exact_rejection_for_k_le_1(fixed,seed,budget=budget,
                                          event_budget=event_budget)
    return pimh_sample(fixed,seed,particles=particles,iterations=iterations,
                       proposal_budget=iterations,event_budget=event_budget,
                       minimum_accepted_moves=min_moves)
