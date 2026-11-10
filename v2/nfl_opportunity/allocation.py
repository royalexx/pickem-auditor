"""P2-02/03/04/05: role priors, verified absence, simplex allocation.

All parameters are estimated exclusively from already available historical
labels. Short-role uncertainty is exposed; structural inactivity requires an
explicit historical label. This is a CPU-only shadow research prototype.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import exp, isfinite, log, sqrt
import math
import random

from v2.contracts import ContractError, finite, utc
from .contracts import NFLPlayerHistory, NFLPregame, NFLRosterPlayer, NFLTeamHistory
from .state import _binomial, _clamp


def _eligible_player_rows(
        players: list[NFLPlayerHistory], team_rows: list[NFLTeamHistory],
        forecast: NFLPregame):
    teams = {(row.event_id,row.team_id):row for row in team_rows}
    return [(r,teams[(r.event_id,r.team_id)])
            for r in players if r.team_id==forecast.team_id and
            (r.event_id,r.team_id) in teams and
            utc(r.label_available_at,"player_label") <= utc(forecast.freeze_at,"freeze_at")]


@dataclass(frozen=True)
class ReceiverPrior:
    player_id: str
    role: str
    status: str
    n_player_history: int
    n_role_peer_history: int
    participation_alpha: float
    participation_beta: float
    route_alpha: float
    route_beta: float
    target_alpha: float
    target_beta: float
    logit_sd: float
    structural_zero_probability: float | None
    absence_role_multiplier: float
    role_transition_n_normal: int
    role_transition_n_absent: int

    def draw_role(self, rng: random.Random, *, is_zidm: bool = False):
        if self.status == "verified_out":
            return False, 0., 0., "verified_out"
        if is_zidm and self.structural_zero_probability is None:
            raise ContractError("zidm_requires_verified_structural_inactivity_labels")
        if is_zidm:
            if rng.random() < self.structural_zero_probability:
                return False, 0., 0., "verified_structural_zero_prior"
            participating = True
        else:
            participating = rng.random() < rng.betavariate(
                self.participation_alpha,self.participation_beta)
        if not participating:
            return False, 0., 0., "sampled_no_route_participation"
        return (True, rng.betavariate(self.route_alpha,self.route_beta),
                rng.betavariate(self.target_alpha,self.target_beta),
                "latent_participation")


@dataclass(frozen=True)
class AllocationFit:
    players: tuple[ReceiverPrior,...]
    residual_alpha: float
    residual_beta: float
    training_cutoff_at: str
    n_games: int
    n_player_rows: int
    absent_roles: tuple[str,...]
    unidentifiable_role_transitions: tuple[str,...]

    def __post_init__(self):
        if self.residual_alpha <= 0 or self.residual_beta <= 0:
            raise ContractError("invalid_unassigned_attempt_pool")


def fit_allocator(team_history: list[NFLTeamHistory],
                  player_history: list[NFLPlayerHistory],
                  forecast: NFLPregame, *,
                  prior_games: float = 6.,
                  prior_route_exposure: float = 30.,
                  min_transition_games: int = 4) -> AllocationFit:
    """Empirical role-peer shrinkage with explicit unverifiable-transition abstention."""
    g = finite(prior_games,"prior_games")
    exposures = finite(prior_route_exposure,"prior_route_exposure")
    if g <= 0 or exposures <= 0 or type(min_transition_games) is not int or min_transition_games < 2:
        raise ContractError("invalid_allocator_prior_settings")
    relevant=[row for row in team_history if row.team_id==forecast.team_id and
              utc(row.label_available_at,"team_label")<=utc(forecast.freeze_at,"freeze")]
    if len(relevant)<2:
        raise ContractError("insufficient_asof_team_target_opportunity_rows")
    records = _eligible_player_rows(player_history,team_history,forecast)
    if not records:
        raise ContractError("insufficient_asof_receiver_usage")
    by_role=defaultdict(list)
    by_player=defaultdict(list)
    for row,team in records:
        by_role[row.role].append((row,team))
        by_player[row.player_id].append((row,team))
    total_att=sum(t.pass_attempts for t in relevant)
    total_residual=sum(t.pass_attempts-t.tracked_targets for t in relevant)
    if total_att<=0:
        raise ContractError("asof_passing_opportunity_empty")
    priors=[]
    absences={r.role for r in forecast.players if r.status=="verified_out"}
    unidentifiable=set()
    for player in forecast.players:
        peers=[rt for rt in by_role[player.role] if rt[0].player_id != player.player_id]
        own=by_player[player.player_id]
        role_pool=peers or by_role[player.role]
        if not role_pool:
            raise ContractError("unknown_receiver_role_without_historical_peer:"+player.role)
        peer_eligible=len(role_pool)
        peer_play=sum(row.routes>0 for row,team in role_pool)
        peer_participation=(peer_play+1)/(peer_eligible+2)
        peer_drop=sum(team.dropbacks for row,team in role_pool)
        peer_routes=sum(row.routes for row,team in role_pool)
        if peer_drop<=0:
            raise ContractError("role_route_denominator_unavailable:"+player.role)
        peer_route=(peer_routes+1)/(peer_drop+2)
        peer_target=(sum(row.targets for row,team in role_pool)+1)/(peer_routes+2)
        n=len(own)
        presence=sum(row.routes>0 for row,team in own)
        own_drop=sum(team.dropbacks for row,team in own)
        own_routes=sum(row.routes for row,team in own)
        own_targets=sum(row.targets for row,team in own)
        parts_a=1+presence+g*peer_participation
        parts_b=1+n-presence+g*(1-peer_participation)
        route_alpha=1+own_routes+exposures*peer_route
        route_beta=1+own_drop-own_routes+exposures*(1-peer_route)
        target_alpha=1+own_targets+exposures*peer_target
        target_beta=1+own_routes-own_targets+exposures*(1-peer_target)

        # Between-game target-rate volatility estimated on pregame-released
        # observations, with posterior uncertainty for short-role players.
        logit_rates=[
            math.log((row.targets+.5)/(row.routes-row.targets+.5))
            for row,team in own if row.routes>0
        ]
        if len(logit_rates)>=3:
            mu=sum(logit_rates)/len(logit_rates)
            empirical=math.sqrt(sum((z-mu)**2 for z in logit_rates)/
                                (len(logit_rates)-1))
        else:
            empirical=0.
        # Floor is numerical regularization, not an asserted NFL dispersion
        # estimate. It is versioned as part of the experimental algorithm.
        # This is predictive BETWEEN-GAME variability, not the standard
        # error of an estimated mean. More games must not erase real role
        # volatility; the Beta rate posterior already carries fit uncertainty.
        logit_sd=max(.05,empirical)
        labelled=[row.structurally_inactive for row,team in own
                  if row.structurally_inactive is not None]
        if len(labelled)<4:
            labelled=[row.structurally_inactive for row,team in role_pool
                      if row.structurally_inactive is not None]
        structural=(sum(labelled)+1)/(len(labelled)+2) if len(labelled)>=4 else None

        # Only VERIFIED historical role-disruption labels can provide an
        # absence uplift. Unknown labels must NOT magically boost teammates.
        normal=[row for row,team in role_pool
                if row.verified_absent_teammate_role is None and row.routes>0]
        affected=[row for row,team in role_pool
                  if row.verified_absent_teammate_role in absences and row.routes>0]
        multiplier=1.
        if absences and (len(normal)<min_transition_games or
                         len(affected)<min_transition_games):
            unidentifiable.add(player.role)
        elif absences:
            rate_normal=(sum(x.targets for x in normal)+1)/(
                sum(x.routes for x in normal)+2)
            rate_affected=(sum(x.targets for x in affected)+1)/(
                sum(x.routes for x in affected)+2)
            multiplier=rate_affected/rate_normal
        priors.append(ReceiverPrior(
            player_id=player.player_id,role=player.role,status=player.status,
            n_player_history=n,n_role_peer_history=len(peers),
            participation_alpha=parts_a,participation_beta=parts_b,
            route_alpha=route_alpha,route_beta=route_beta,
            target_alpha=target_alpha,target_beta=target_beta,
            logit_sd=logit_sd,structural_zero_probability=structural,
            absence_role_multiplier=multiplier,
            role_transition_n_normal=len(normal),
            role_transition_n_absent=len(affected),
        ))
    return AllocationFit(
        players=tuple(priors),
        residual_alpha=1+total_residual,
        residual_beta=1+total_att-total_residual,
        training_cutoff_at=max(
            [utc(row.label_available_at,"team_label") for row in relevant]+
            [utc(row.label_available_at,"player_label") for row,_team in records]).isoformat(),
        n_games=len(relevant),n_player_rows=len(records),
        absent_roles=tuple(sorted(absences)),
        unidentifiable_role_transitions=tuple(sorted(unidentifiable)),
    )


def _weighted_pick(rng: random.Random, weights: list[float]) -> int:
    total=math.fsum(weights)
    if total<=0 or not math.isfinite(total):
        raise ContractError("invalid_opportunity_allocation_weights")
    draw=rng.random()*total
    running=0.
    for i,w in enumerate(weights):
        running += w
        if draw < running:
            return i
    return len(weights)-1


def allocate_attempts(
        state: dict, fit: AllocationFit, rng: random.Random, *,
        method: str = "logistic_normal", dm_concentration: float = 25.) -> dict:
    """Conditional independent player routes, shared fixed attempt pool.

    Each attempt becomes exactly one player-target OR the residual category.
    No infeasible targets are silently clipped or reallocated post hoc.
    """
    if method not in ("logistic_normal","dirichlet_multinomial","zidm"):
        raise ContractError("unregistered_opportunity_allocation_challenger")
    conc=finite(dm_concentration,"dm_concentration")
    if conc<=0:
        raise ContractError("invalid_dm_concentration")
    drop=state["dropbacks"]
    attempts=state["pass_attempts"]
    if (type(drop) is not int or type(attempts) is not int
            or attempts<0 or attempts>drop):
        raise ContractError("invalid_team_attempt_state")
    players={}
    raw_logits=[]
    capacities=[]
    for prior in fit.players:
        active,p_route,p_target,why=prior.draw_role(rng,is_zidm=(method=="zidm"))
        routes=_binomial(rng,drop,p_route) if active else 0
        player_share=0.
        if routes:
            player_share=(routes/max(1,drop))*p_target*prior.absence_role_multiplier
            logit=math.log(max(1e-12,player_share))
            if method=="logistic_normal":
                logit += rng.gauss(0.,prior.logit_sd)
            raw_logits.append(logit)
        else:
            raw_logits.append(None)
        players[prior.player_id]={
            "player_id":prior.player_id,"role":prior.role,
            "roster_status":prior.status,"route_participation":bool(routes),
            "routes":routes,"targets":0,
            "participation_reason":why,
            "n_asof_player_games":prior.n_player_history,
            "n_role_peer_games":prior.n_role_peer_history,
        }
        capacities.append(routes)
    residual_prior=rng.betavariate(fit.residual_alpha,fit.residual_beta)
    residual_logit=math.log(max(1e-12,residual_prior))
    logs=[x for x in raw_logits if x is not None]+[residual_logit]
    offset=max(logs)
    raw_weights=[
        (math.exp(x-offset) if x is not None else 0.)
        for x in raw_logits
    ]+[math.exp(residual_logit-offset)]
    if method in ("dirichlet_multinomial","zidm"):
        # Standard gamma-normalized Dirichlet draws. Inactive slots remain 0.
        raw_weights=[
            (rng.gammavariate(conc*w,1.) if w>0 else 0.)
            for w in raw_weights]
    unattributed=0
    for _ in range(attempts):
        eligible=[(w if cap>0 else 0.)
                  for w,cap in zip(raw_weights[:-1],capacities)]
        idx=_weighted_pick(rng,eligible+[raw_weights[-1]])
        if idx==len(capacities):
            unattributed += 1
        else:
            player_id=fit.players[idx].player_id
            players[player_id]["targets"] += 1
            capacities[idx] -= 1
    targets=sum(p["targets"] for p in players.values())
    if (targets+unattributed != attempts or
            any(p["targets"]>p["routes"] for p in players.values())):
        raise ContractError("simulation_conservation_failure")
    return {
        "method":method,
        "players":players,
        "residual_unassigned_attempts":unattributed,
        "tracked_player_targets":targets,
        "pass_attempts":attempts,
        "dropbacks":drop,
        "conservation_ok":True,
        "model_unvalidated_research_only":True,
    }


def standard_dm_diagnostic(state: dict, fit: AllocationFit,
                           rng: random.Random, *,
                           concentration: float = 25.) -> dict:
    """Untruncated canonical Dirichlet-multinomial comparison.

    Gamma-normalized Dirichlet probabilities and multinomial allocation of
    EVERY pass attempt. Unlike the route-capped champion, this control may
    give a receiver more targets than projected routes. Keep those physical
    violations visible rather than deceptively calling this DM constrained.
    """
    conc=finite(concentration,"standard_dm_concentration")
    if conc<=0:
        raise ContractError("invalid_standard_dm_concentration")
    drop=state["dropbacks"]
    attempts=state["pass_attempts"]
    if type(drop) is not int or type(attempts) is not int or not 0<=attempts<=drop:
        raise ContractError("standard_dm_team_attempt_state_invalid")
    players={}
    expected=[]
    for prior in fit.players:
        active,p_route,p_target,reason=prior.draw_role(rng)
        routes=_binomial(rng,drop,p_route) if active else 0
        share=(routes/max(1,drop))*p_target*prior.absence_role_multiplier if routes else 0.
        players[prior.player_id]={
            "player_id":prior.player_id,"role":prior.role,
            "roster_status":prior.status,"routes":routes,"targets":0,
            "participation_reason":reason,
        }
        expected.append(share)
    residual=rng.betavariate(fit.residual_alpha,fit.residual_beta)
    weights=expected+[residual]
    norm=math.fsum(weights)
    if norm<=0:
        raise ContractError("standard_dm_no_residual_mass")
    fractions=[v/norm for v in weights]
    gamma=[rng.gammavariate(max(1e-6,conc*w),1.) if w>0 else 0.
           for w in fractions]
    # Sampling remains multinomial even if actual route capacity is exhausted.
    unassigned=0
    for _ in range(attempts):
        selected=_weighted_pick(rng,gamma)
        if selected==len(fit.players):
            unassigned+=1
        else:
            players[fit.players[selected].player_id]["targets"]+=1
    violated=[pid for pid,p in players.items() if p["targets"]>p["routes"]]
    return {
        "method":"standard_dirichlet_multinomial_diagnostic",
        "players":players,
        "tracked_player_targets":sum(p["targets"] for p in players.values()),
        "unassigned_pass_attempts":unassigned,
        "pass_attempts":attempts,
        "illegal_route_capacity_players":violated,
        "not_jointly_physically_valid":bool(violated),
        "canonical_dm_not_capacity_truncated":True,
    }


def independent_poisson_diagnostic(
        state: dict, fit: AllocationFit, rng: random.Random) -> dict:
    """Unconstrained count control; illegal team totals remain *visible*."""
    attempts=state["pass_attempts"]
    targets={}
    for prior in fit.players:
        if prior.status=="verified_out":
            targets[prior.player_id]=0
            continue
        p_route=prior.route_alpha/(prior.route_alpha+prior.route_beta)
        p_target=prior.target_alpha/(prior.target_alpha+prior.target_beta)
        exp_targets=attempts*p_route*p_target
        # Knuth Poisson for small expected workloads, standard-library only.
        # A conspicuously high lambda is unsupported by this prototype.
        if exp_targets>50:
            raise ContractError("independent_poisson_parameter_outside_support")
        if exp_targets==0:
            targets[prior.player_id]=0
            continue
        t=1.
        point=math.exp(-exp_targets)
        k=0
        while t>point:
            k+=1
            t*=rng.random()
        targets[prior.player_id]=k-1
    return {
        "method":"independent_poisson_diagnostic",
        "targets":targets,
        "pass_attempts":attempts,
        "total_player_targets":sum(targets.values()),
        "illegal_target_sum":sum(targets.values())>attempts,
        "not_jointly_physically_valid":True,
    }
