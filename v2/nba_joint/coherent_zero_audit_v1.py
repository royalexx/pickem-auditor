"""Read-only zero-exposure diagnostics for the coherent NBA S4/J shadow law.

No model refit, S4/J resimulation, score, market probability, or pregame
certification is performed. The analytic grid describes O's *prior marginal*
at a declared game duration, not the final event-conditioned predictive law.
"""
from __future__ import annotations

import math
from scipy.special import betainc
from v2.nba_opportunity import MinuteLaw
from v2.nba_joint.coherent_predictive_v1 import validate_bank
from v2.nba_architecture.subset_p3_v1 import require

DEFAULT_WEIGHTS = (0.0, 0.005, 0.01, 0.02, 0.05)


def analytic_minute_grid(model, *, zero_weights=DEFAULT_WEIGHTS,
                         duration_minutes=48.0, thresholds_minutes=(0.0, 0.5, 1.0)):
    """Conditional G-duration O prior, prior to J event-path acceptance.

    If U is uniform and Z is the zero-mixture weight, P(M <= t | Z=z,G)=
    z + (1-z)*I_(t/G)(alpha,beta) for 0<=t<G. For the original
    Z~Beta(.5,49.5), E[Z]=.01, so its one-player marginal equals fixed
    z=.01; its *joint* minute law need not be identical.
    """
    require(type(duration_minutes) in (float,int) and math.isfinite(duration_minutes)
            and duration_minutes>=48 and (duration_minutes-48)%5==0,
            'ZERO_AUDIT_GAME_DURATION')
    require(bool(zero_weights) and len(set(zero_weights))==len(zero_weights)
            and all(type(z) in (int,float) and math.isfinite(z) and 0<=z<1
                    for z in zero_weights), 'ZERO_AUDIT_WEIGHTS')
    require(bool(thresholds_minutes)
            and all(type(t) in (int,float) and math.isfinite(t)
                    and 0<=t<duration_minutes for t in thresholds_minutes),
            'ZERO_AUDIT_THRESHOLDS')
    players=model['named_players']
    require(len(players)==14 and len({p['player_id'] for p in players})==14,
            'ZERO_AUDIT_POPULATION')
    result=[]
    for player in sorted(players,key=lambda p:p['player_id']):
        a,b=MinuteLaw(**player['minutes']).shape()
        require(math.isfinite(a) and math.isfinite(b) and a>0 and b>0,
                'ZERO_AUDIT_BETA_SHAPE')
        for z in zero_weights:
            cdf={}
            for threshold in thresholds_minutes:
                f=float(betainc(a,b,threshold/duration_minutes))
                value=float(z+(1-z)*f)
                require(0<=value<=1 and math.isfinite(value),'ZERO_AUDIT_CDF')
                cdf[str(float(threshold))]=value
            result.append(dict(player_id=player['player_id'],
                               team_id=player['team_id'],zero_weight=float(z),
                               duration_minutes=float(duration_minutes),
                               beta_shape=[float(a),float(b)],cdf_at_minutes=cdf,
                               exact_zero_probability=float(z)))
    return dict(schema='nba-coherent-zero-prior-analytic-grid/1',
                population_named=14,rows=result,
                original_beta_prior=[0.5,49.5],
                original_expected_zero_weight=0.01,
                baseline_marginal_equivalent_fixed_weight=0.01,
                joint_law_equivalence_claim=False,
                event_path_conditional_result=False,
                pregame_participation_proven=False,
                historical_validation=False,release=False)


def assert_zero_exposure_no_credited_events(fixed,accepted):
    """A zero-minute source-listed actor must not acquire any box-score credit."""
    n=0;zeros=0;zero_ids=[]
    for team,actors in fixed['actors'].items():
        require(team in fixed['O'] and team in accepted['counts'],
                'ZERO_AUDIT_TEAM_JOIN')
        for actor in actors:
            pid=actor['identity']['player_id']
            if pid is None:continue
            i=actor['index']
            require(type(i) is int and 0<=i<len(fixed['O'][team]['minutes'])
                    and i<len(accepted['counts'][team]),'ZERO_AUDIT_ACTOR_INDEX')
            mins=fixed['O'][team]['minutes'][i]
            require(type(mins) in (int,float) and math.isfinite(mins) and mins>=0,
                    'ZERO_AUDIT_MINUTES')
            n+=1
            if mins==0:
                zeros+=1;zero_ids.append(pid)
                credited=accepted['counts'][team][i]
                require(all(type(v) is int and v==0 for v in credited.values()),
                        'ZERO_AUDIT_ZERO_MINUTE_ACTOR_HAS_STATS')
    require(n==14 and len(set(zero_ids))==len(zero_ids),
            'ZERO_AUDIT_NAMED_POPULATION')
    return dict(named_players=n,zero_minutes=zeros,zero_player_ids=sorted(zero_ids))


def audit_saved_bank(bank):
    """Validate canonical bank invariants and count zero-minute named actors.

    The caller must independently verify exact saved raw bank/model/trace bytes
    and original source/model admission. This function never certifies them.
    """
    validate_bank(bank)
    by_player={}
    per_scenario=[]
    for s in bank['scenarios']:
        r=assert_zero_exposure_no_credited_events(s['fixed'],s['accepted'])
        per_scenario.append(dict(scenario=s['index'],zero_minutes=r['zero_minutes'],
                                 zero_player_ids=r['zero_player_ids']))
        for pid in r['zero_player_ids']:
            by_player[pid]=by_player.get(pid,0)+1
    n=len(per_scenario)
    require(n==bank['scenario_denominator'],'ZERO_AUDIT_SCENARIO_DENOMINATOR')
    zero_rows=sum(s['zero_minutes'] for s in per_scenario)
    return dict(schema='nba-coherent-zero-exposure-observed-bank/1',
                bank_payload_sha256=bank['payload_sha256'],
                scenarios=n,named_slots_per_scenario=14,
                named_slot_denominator=14*n,
                observed_zero_minute_named_slots=zero_rows,
                observed_zero_minute_slot_fraction=zero_rows/(14*n),
                scenarios_with_one_or_more_named_zero=sum(s['zero_minutes']>0 for s in per_scenario),
                zero_minutes_by_player=by_player,per_scenario=per_scenario,
                zero_prior_is_not_genuine_DNP_or_eligibility=True,
                all14_participation_requires_separate_semantic_review=True,
                prior_sensitivity_only=False,full_S4_J_sensitivity_evaluated=False,
                clinical_or_market_predictions=False,historical_validation=False,
                no_new_forecast_issued=True,release=False)
