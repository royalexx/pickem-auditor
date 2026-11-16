"""NBA P3 O-family research producer for frozen G0 v2.0.0.

WS2's MinuteLaw, capped_allocation and lineup_segments are reused unchanged.
No training, final stats, same-game actuals, collector, odds or production writes.
A finite G-conditioned ensemble defines *both* minute marginals and joint draws,
avoiding the impossible independent-marginal projection accepted by old WS2.
The conditional discrete laws are finite scenario approximations, NOT calibrated
population distributions. This is an engineering/scenario adapter only.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import math

import numpy as np

from v2.nba_opportunity import MinuteLaw, capped_allocation, lineup_segments
from v2.nba_architecture.v2_contracts import (
    ContractError, component, digest, instant, num, req, seal, seed_for,
    validate_pregame, verify,
)
from v2.nba_architecture.families_v2 import validate_game_state, validate_opportunity

VERSION = "nba-p3-opportunity/0.1.0"
PRIOR_KEYS = frozenset({
    "source_snapshot_sha256", "source_receipt_sha256", "available_at",
    "training_cutoff_at", "scenario_participation_prior", "participation_basis",
    "minutes_distribution", "played_zero_probability", "early_exit_probability",
    "early_exit_fraction", "role_states", "possession_intensity",
    "usage_concentration", "uncertainty_flags",
})
BASIS = frozenset(("historical_prior", "verified_pregame_fit"))
VARIANTS = frozenset(("O0", "O1", "O2"))


def validate_priors(p, priors, *, variant):
    """Requires a fully enumerated roster; never fills a missing player with 0."""
    req(variant in VARIANTS, "O_UNKNOWN_VARIANT")
    req(isinstance(priors, dict), "O_PRIORS_REQUIRED")
    roster = {r["player_id"]: r for r in p["players"]}
    req(set(priors) == set(roster), "O_PRIOR_ROSTER_COVERAGE")
    receipt_hashes = {x["receipt_sha256"] for x in p["sources"]}
    freeze = instant(p["input_freeze_at"])
    for pid, prior in priors.items():
        req(isinstance(prior, dict) and set(prior) == PRIOR_KEYS,
            "O_PRIOR_FIELDS_OR_POSTGAME_LEAK")
        req(prior["source_snapshot_sha256"] == p["content_hash"],
            "O_PRIOR_SNAPSHOT_MISMATCH")
        req(prior["source_receipt_sha256"] in receipt_hashes,
            "O_PRIOR_SOURCE_MISSING")
        req(instant(prior["available_at"]) <= freeze and
            instant(prior["training_cutoff_at"]) <= freeze,
            "O_PRIOR_FUTURE_DATA")
        req(prior["participation_basis"] in BASIS, "O_PRIOR_BASIS")
        q = num(prior["scenario_participation_prior"])
        req(q <= 1, "O_PRIOR_PARTICIPATION_RANGE")
        if roster[pid]["availability"] == "out" or roster[pid]["legal_eligibility"] is False:
            req(q == 0, "O_PRIOR_EXCLUDED_PLAYER")
        law = prior["minutes_distribution"]
        req(isinstance(law, dict) and set(law) ==
            {"mean", "variance", "ot_probability", "ot_continuation", "family"},
            "O_WS2_LAW_FIELDS")
        MinuteLaw(**law)
        for name in ("played_zero_probability", "early_exit_probability"):
            req(num(prior[name]) <= 1, "O_PRIOR_PROBABILITY")
        fraction = num(prior["early_exit_fraction"])
        req(0 < fraction <= 1, "O_EARLY_EXIT_FRACTION")
        intensity = num(prior["possession_intensity"])
        concentration = num(prior["usage_concentration"])
        req(intensity > 0 and concentration > 0, "O_USAGE_PARAMETERS")
        roles = prior["role_states"]
        req(isinstance(roles, list) and bool(roles), "O_ROLE_STATES")
        req(all(isinstance(r, dict) and set(r) ==
                {"probability", "minutes_multiplier"} for r in roles),
            "O_ROLE_STATE_FIELDS")
        req(all(0 <= num(r["probability"]) <= 1 and
                num(r["minutes_multiplier"]) > 0 for r in roles),
            "O_ROLE_STATE_PARAMETER")
        req(abs(math.fsum(r["probability"] for r in roles)-1) <= 1e-12,
            "O_ROLE_STATE_MASS")
        req(isinstance(prior["uncertainty_flags"], list) and
            all(isinstance(x, str) and bool(x) for x in prior["uncertainty_flags"]),
            "O_UNCERTAINTY_FLAGS")
    return True


def _one_team(roster, priors, sc, rng, variant):
    """Conditional participation draws and constrained minutes. No actual rotation."""
    length = 48 + 5*sc["overtime_periods"]
    total = 5*length
    # Conditional roster draws explicitly enforce >=5 positive-minute players.
    # Recording the conditioning avoids falsely promising original Bernoulli marginals.
    for attempt in range(1, 257):
        status, caps, desired, role_states = [], [], [], []
        for r in roster:
            a = priors[r["player_id"]]
            eligible = r["legal_eligibility"] is not False and r["availability"] != "out"
            participated = eligible and rng.random() < a["scenario_participation_prior"]
            played_zero = (participated and rng.random() < a["played_zero_probability"])
            on_court = participated and not played_zero
            status.append("PLAYED" if on_court else
                          "PLAYED_ZERO_MINUTES" if participated else "DNP")
            if not on_court:
                desired.append(0.); caps.append(0.); role_states.append("none")
                continue
            draw = float(length * a["minutes_distribution"]["mean"] /
                         (48 + 5*a["minutes_distribution"]["ot_probability"] /
                          (1-a["minutes_distribution"]["ot_continuation"])))
            if variant != "O0":
                law = MinuteLaw(**a["minutes_distribution"])
                draw = law.sample_at_length(rng, length)
            chosen = 0
            if variant == "O2":
                chosen = int(rng.choice(len(a["role_states"]),
                             p=[x["probability"] for x in a["role_states"]]))
                draw *= a["role_states"][chosen]["minutes_multiplier"]
            exit_draw = variant == "O2" and rng.random() < a["early_exit_probability"]
            cap = length * (a["early_exit_fraction"] if exit_draw else 1.)
            desired.append(min(draw, cap))
            caps.append(cap)
            role_states.append("early_exit" if exit_draw else f"role:{chosen}")
        if sum(s == "PLAYED" for s in status) < 5:
            continue
        if math.fsum(caps) < total - 1e-9:
            continue
        floor = np.array([min(c, 1e-5) if s == "PLAYED" else 0.
                          for s,c in zip(status,caps)])
        try:
            minutes = floor + capped_allocation(
                np.array(desired)-floor, np.array(caps)-floor, total-float(floor.sum()))
            witness = lineup_segments(minutes, length)
        except ValueError:
            continue
        if any(s == "PLAYED" and minutes[i] <= 0 for i,s in enumerate(status)):
            continue
        return {
            "minutes": [float(x) for x in minutes],
            "states": status,
            "role_states": role_states,
            "lineup_segments": witness,
            "attempts": attempt,
            "duration": length,
        }
    raise ContractError("O_INFEASIBLE_PARTICIPATION_OR_ROTATION")


def _share_scenario(roster, priors, result, pool, rng, variant):
    minutes = result["minutes"]
    intensity = [m * priors[r["player_id"]]["possession_intensity"]
                 for r,m in zip(roster,minutes)]
    divisor = math.fsum(intensity)
    req(divisor > 0, "O_NO_POSITIVE_SHARE")
    shares = [x/divisor for x in intensity]
    if variant == "O2":
        # Optional role/usage uncertainty: no outcome conversion is performed.
        shapes = [max(1e-8, shares[i]*priors[r["player_id"]]["usage_concentration"])
                  if minutes[i] > 0 else 0.
                  for i,r in enumerate(roster)]
        draws = [rng.gamma(shape,1.) if shape else 0. for shape in shapes]
        z = math.fsum(draws)
        req(z > 0, "O_USAGE_DRAW_NUMERICAL")
        shares = [x/z for x in draws]
    return [
        {"player_id":r["player_id"],"minutes":float(minutes[i]),
         "participation":result["states"][i],
         "role_state":result["role_states"][i],
         "possession_share":float(shares[i]),
         "projected_possession_opportunity":float(pool*shares[i])}
        for i,r in enumerate(roster)
    ]


def build_opportunity(p, g, priors, *, model, seed, variant="O1",
                      home_team_id, home_team_source_receipt_sha256):
    """Produce frozen G0 O object + hash-bound supplementary S/J opportunity draws.

    All role/minutes priors must come from a pregame snapshot-backed adapter.
    Historical reconstruction and unknown participation remain noncertified.
    Scenario-level q and conditional minute laws are derived FROM one shared
    conserving ensemble, so G0's exact minute-law LP is satisfiable by design.
    The empirical q is not asserted to equal a fitted Bernoulli prior.
    """
    validate_pregame(p); validate_game_state(g,p)
    component(model)
    req(instant(model["training_cutoff_at"]) <= instant(p["input_freeze_at"]),
        "O_FUTURE_MODEL")
    req(type(seed) is int and seed >= 0, "O_INVALID_SEED")
    validate_priors(p,priors,variant=variant)
    req(home_team_id in p["team_ids"] and
        home_team_source_receipt_sha256 in
        {s["receipt_sha256"] for s in p["sources"]},
        "O_HOME_TEAM_SOURCE_MISSING")
    team_roster = {t: sorted((r for r in p["players"] if r["team_id"]==t),
                             key=lambda x:x["player_id"]) for t in p["team_ids"]}
    req(all(len(v)>=5 for v in team_roster.values()),"O_NOT_ENOUGH_ROSTER_PLAYERS")
    scenarios=[]; supplementary=[]
    for sc in g["scenarios"]:
        sid=sc["scenario_id"]
        players=[]; share_rows=[]; witnesses={}; attempt_counts={}
        for team in p["team_ids"]:
            rng=np.random.default_rng(seed_for(seed,p["game_id"],sid,
                                               f"{VERSION}/{variant}/{team}"))
            res=_one_team(team_roster[team],priors,sc,rng,variant)
            attempt_counts[team]=res["attempts"]
            witnesses[team]=res["lineup_segments"]
            for r,mins,state in zip(team_roster[team],res["minutes"],res["states"]):
                players.append({"player_id":r["player_id"],"team_id":team,
                                "participation":state,"minutes":mins})
            pool=sc["possessions_home"] if team==home_team_id else sc["possessions_away"]
            share_rows.extend(_share_scenario(team_roster[team],priors,res,pool,rng,variant))
        scenarios.append({"scenario_id":sid,"weight":sc["weight"],
                          "overtime_periods":sc["overtime_periods"],
                          "players":sorted(players,key=lambda x:x["player_id"])})
        supplementary.append({"scenario_id":sid,"weight":sc["weight"],
                              "overtime_periods":sc["overtime_periods"],
                              "teams":{t:{"team_id":t,
                                "projected_possessions":sc["possessions_home"] if t==home_team_id
                                else sc["possessions_away"],
                                "lineup_segments":witnesses[t],
                                "sampling_attempts":attempt_counts[t]} for t in p["team_ids"]},
                              "players":sorted(share_rows,key=lambda x:x["player_id"])})
    persons=[]
    for r in sorted(p["players"],key=lambda x:x["player_id"]):
        pid=r["player_id"]; prior=priors[pid]
        played=[(sc["weight"], next(x for x in sc["players"] if x["player_id"]==pid))
                for sc in scenarios if sc["weight"]>0]
        q=math.fsum(w for w,x in played if x["participation"]!="DNP")
        marginal=defaultdict(float)
        for w,x in played:
            if x["participation"]!="DNP":
                marginal[x["minutes"]]+=w
        if q>0:
            support=[{"minutes":float(m),"mass":float(weight/q)}
                     for m,weight in sorted(marginal.items())]
            norm=math.fsum(x["mass"] for x in support)
            support[-1]["mass"]+=1.-norm
        else:
            support=[{"minutes":0.,"mass":1.}]
        excluded=r["legal_eligibility"] is False or r["availability"]=="out"
        evidence=("verified_out" if excluded else
                  "independently_estimated" if prior["participation_basis"]=="verified_pregame_fit"
                  else "unknown")
        # Prior-only/uncertified sources never become an independent participation claim.
        prob=0. if excluded else float(q) if evidence=="independently_estimated" else None
        persons.append({"player_id":pid,"team_id":r["team_id"],
                        "participation_probability":prob,
                        "participation_evidence":evidence,
                        "minutes_law":{"family":"discrete_minutes",
                                       "parameters":{"support":support},
                                       "conditioning":"given_played","units":"minutes"}})
    o=seal({"schema":"nba-sojc-contract/2.0.0","kind":"opportunity",
            "source_snapshot_sha256":p["content_hash"],"game_id":p["game_id"],
            "model":deepcopy(model),"game_state_sha256":g["content_hash"],
            "players":persons,"scenarios":scenarios})
    validate_opportunity(o,p,g)
    sidecar=seal({"schema":VERSION,"kind":"opportunity_scenarios",
                  "source_snapshot_sha256":p["content_hash"],
                  "game_id":p["game_id"],"game_state_sha256":g["content_hash"],
                  "opportunity_sha256":o["content_hash"],"seed":seed,
                  "variant":variant,"model":deepcopy(model),
                  "home_team_id":home_team_id,
                  "home_team_source_receipt_sha256":home_team_source_receipt_sha256,
                  "source_status":"SHADOW_NOT_CERTIFIED",
                  "scenario_sampling":"participation-conditioned-on-feasible-team-rotation",
                  "scenarios":supplementary})
    validate_sidecar(sidecar,p,g,o)
    return o,sidecar


def validate_sidecar(sidecar,p,g,o):
    verify(sidecar)
    req(sidecar["opportunity_sha256"]==o["content_hash"] and
        sidecar["game_state_sha256"]==g["content_hash"] and
        sidecar["source_snapshot_sha256"]==p["content_hash"],
        "O_SIDECAR_JOIN")
    g_by_id={x["scenario_id"]:x for x in g["scenarios"]}
    o_by_id={x["scenario_id"]:x for x in o["scenarios"]}
    req(set(x["scenario_id"] for x in sidecar["scenarios"])==set(g_by_id),
        "O_SIDECAR_COVERAGE")
    for sc in sidecar["scenarios"]:
        sid=sc["scenario_id"]
        req(abs(sc["weight"]-g_by_id[sid]["weight"])<=1e-12,
            "O_SIDECAR_WEIGHT")
        o_players={x["player_id"]:x for x in o_by_id[sid]["players"]}
        req(set(x["player_id"] for x in sc["players"])==set(o_players),
            "O_SIDECAR_ROSTER")
        for x in sc["players"]:
            w=o_players[x["player_id"]]
            req(x["minutes"]==w["minutes"] and
                x["participation"]==w["participation"],"O_SIDECAR_PLAYER_JOIN")
        for team,info in sc["teams"].items():
            chosen=[x for x in sc["players"] if o_players[x["player_id"]]["team_id"]==team]
            req(abs(math.fsum(x["possession_share"] for x in chosen)-1)<1e-10,
                "O_SHARE_CONSERVATION")
            req(abs(math.fsum(x["projected_possession_opportunity"] for x in chosen)-
                    info["projected_possessions"])<1e-7,"O_POSSESSION_CONSERVATION")
            length=48+5*sc["overtime_periods"]
            segments=info["lineup_segments"]
            req(segments and abs(math.fsum(x["end"]-x["start"] for x in segments)-length)<1e-7,
                "O_LINEUP_CLOCK_COVERAGE")
            req(all(len(x["player_indices"])==5 for x in segments),
                "O_FIVE_ON_COURT")
    return True


def freeze_outputs(folder,p,g,o,sidecar):
    """Create-only audited bytes; existing divergent artifacts cannot be replaced."""
    from pathlib import Path
    from v2.nba_architecture.v2_contracts import freeze_once
    root=Path(folder)
    return (freeze_once(root/(o["content_hash"]+".json"),o),
            freeze_once(root/(sidecar["content_hash"]+".json"),sidecar))


def ws2_priors_from_forecasts(p, forecasts, *, source_receipt_sha256,
                              participation_prior_overrides=None):
    """Strict, fail-closed bridge from WS2 v1 conditional forecasts to G0 P3.

    Raw SHA domain and source clocks must match the accepted P snapshot.
    The WS2 forecast does NOT prove fitted participation probabilities. Every
    imported probability remains 'historical_prior', hence reported q is
    unknown even though shadow scenarios can be sampled. There is no
    pregame injury adjustment or inferred eligibility in this adapter.

    Optional missing-participation overrides must themselves carry a matched
    source receipt, availability timestamp and a finite probability. A caller
    must explicitly supply them; never substitute an invented 0 or 1.
    """
    validate_pregame(p)
    req(isinstance(forecasts, (list,tuple)), "O_WS2_FORECASTS_REQUIRED")
    all_receipts={r["receipt_sha256"]:r for r in p["sources"]}
    req(source_receipt_sha256 in all_receipts, "O_WS2_RECEIPT_MISSING")
    source=all_receipts[source_receipt_sha256]
    freeze=instant(p["input_freeze_at"])
    roster={r["player_id"]:r for r in p["players"]}
    fs={}
    for f in forecasts:
        req(isinstance(f,dict) and f.get("schema")=="NBAOpportunityForecast/1.0.0",
            "O_WS2_SCHEMA")
        pid=f.get("player_id")
        req(pid in roster and pid not in fs, "O_WS2_ROSTER_IDENTITY")
        req(f.get("game_id")==p["game_id"] and
            f.get("team_id")==roster[pid]["team_id"] and
            f.get("event_start_at")==p["event_start_at"] and
            f.get("input_freeze_at")==p["input_freeze_at"],
            "O_WS2_GAME_CLOCK_IDENTITY")
        req(f.get("source_sha256")==source["raw_sha256"],
            "O_WS2_RAW_SOURCE_SHA_MISMATCH")
        req(f.get("status")=="UNCERTIFIED/SHADOW", "O_WS2_UNSAFE_PROMOTION")
        for clock in ("source_available_at","source_ingested_at",
                      "forecast_at","training_cutoff_at"):
            req(f.get(clock) is not None, "O_WS2_CLOCK_MISSING")
        req(max(instant(f["source_available_at"]),
                instant(f["source_ingested_at"]),
                instant(source["collector_observed_at"]),
                instant(source["ingested_at"]))<=freeze,
            "O_WS2_POSTFREEZE_SOURCE")
        req(instant(f["training_cutoff_at"])<=freeze and
            instant(f["forecast_at"])<=instant(p["forecast_at"]),
            "O_WS2_FUTURE_MODEL_OR_FORECAST")
        req(f.get("active_roster_eligible") is not False or
            roster[pid]["legal_eligibility"] is False,
            "O_WS2_ROSTER_ASSERTION_NOT_SOURCE_BOUND")
        req(f.get("participation_status")!="confirmed_inactive" or
            roster[pid]["availability"]=="out" or
            roster[pid]["legal_eligibility"] is False,
            "O_WS2_INACTIVE_ASSERTION_NOT_SOURCE_BOUND")
        fs[pid]=f
    req(set(fs)==set(roster), "O_WS2_MISSING_ROSTER_FORECAST")
    overrides=participation_prior_overrides or {}
    req(set(overrides).issubset(roster), "O_WS2_UNKNOWN_OVERRIDE_PLAYER")
    result={}
    for pid,r in roster.items():
        f=fs[pid]
        q=f.get("participation_probability")
        available=instant(f["source_available_at"])
        if q is None:
            override=overrides.get(pid)
            req(isinstance(override,dict) and set(override)==
                {"probability","source_receipt_sha256","available_at"},
                "O_PARTICIPATION_PRIOR_REQUIRED")
            req(override["source_receipt_sha256"] in all_receipts,
                "O_PARTICIPATION_PRIOR_SOURCE")
            available=max(available,instant(override["available_at"]))
            q=override["probability"]
        q=num(q)
        req(q<=1, "O_PARTICIPATION_PRIOR_RANGE")
        if r["legal_eligibility"] is False or r["availability"]=="out":
            req(q==0, "O_WS2_EXCLUDED_PARTICIPATION")
        result[pid]={
            "source_snapshot_sha256":p["content_hash"],
            "source_receipt_sha256":source_receipt_sha256,
            "available_at":available.isoformat().replace("+00:00","Z"),
            "training_cutoff_at":f["training_cutoff_at"],
            "scenario_participation_prior":float(q),
            "participation_basis":"historical_prior",
            "minutes_distribution":deepcopy(f["distribution"]),
            "played_zero_probability":0.,
            "early_exit_probability":0.,
            "early_exit_fraction":1.,
            "role_states":[{"probability":1.,"minutes_multiplier":1.}],
            "possession_intensity":1.,
            "usage_concentration":30.,
            "uncertainty_flags":["WS2_SHADOW","PARTICIPATION_UNVERIFIED",
                                 "NEUTRAL_USAGE_NOT_FITTED"],
        }
    validate_priors(p,result,variant="O1")
    return result
