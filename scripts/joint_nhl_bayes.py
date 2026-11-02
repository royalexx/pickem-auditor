#!/usr/bin/env python3
"""Joint hierarchical NHL workload/shots NUTS model. Experimental shadow only.

Population means, scales, player random effects, season/opponent effects,
dispersion and workload<->conversion correlation are sampled TOGETHER.
A player on a dated training game must not see later observations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import historical_nhl_warehouse as warehouse

VERSION = "nhl-joint-bayes-v1"
MIN_TRAIN = 200
MIN_PLAYERS = 12
MIN_SEASONS = 1
MAX_RHAT = 1.01
MIN_ESS_BULK = 400


def subset_training_players(rows, *, max_per_position=0):
    """Pre-cutoff-only deterministic representative cohort, for pilot runs.

    A subset run cannot claim to validate all NHL player populations.
    Selection uses *only* the training observations provided here.
    """
    if not isinstance(max_per_position,int) or isinstance(max_per_position,bool) or max_per_position<0:
        raise ValueError("invalid_training_subset_size")
    if max_per_position==0:
        return rows
    positions=default_player_positions(rows)
    counts=Counter(r["player_id"] for r in rows)
    allowed=set()
    for pos in ("F","D"):
        ranking=sorted((pid for pid in counts if positions[pid]==pos),
                       key=lambda pid:(-counts[pid],pid))
        allowed.update(ranking[:max_per_position])
    return [r for r in rows if r["player_id"] in allowed]


def prepare(rows, *, min_rows=MIN_TRAIN):
    if len(rows) < min_rows:
        raise ValueError("insufficient_joint_model_history")
    seen = set()
    for row in rows:
        warehouse._check_row(row)
        key=(row["game_id"],row["player_id"])
        if key in seen:raise ValueError("duplicate_joint_model_player_game")
        seen.add(key)
    players=sorted({r["player_id"] for r in rows})
    seasons=sorted({r["season"] for r in rows})
    opponents=sorted({r["opponent"] for r in rows})
    if len(players)<MIN_PLAYERS or len(seasons)<MIN_SEASONS or len(opponents)<2:
        raise ValueError("insufficient_joint_model_population")
    pid={key:i for i,key in enumerate(players)}
    sid={key:i for i,key in enumerate(seasons)}
    oid={key:i for i,key in enumerate(opponents)}
    player_positions=default_player_positions(rows)
    if any(player_positions[p] not in ("F","D") for p in players):
        raise ValueError("invalid_player_position")
    result={
        "players":players,"seasons":seasons,"opponents":opponents,
        "player_idx":[pid[r["player_id"]] for r in rows],
        "position_idx":[0 if r["position"]=="F" else 1 for r in rows],
        "season_idx":[sid[r["season"]] for r in rows],
        "opponent_idx":[oid[r["opponent"]] for r in rows],
        "home":[int(r["home"]) for r in rows],
        "minutes":[float(r["toi_minutes"]) for r in rows],
        "shots":[int(r["shots"]) for r in rows],
        "player_position":player_positions,
        "first_game":rows[0]["game_date"],
        "last_game":rows[-1]["game_date"],
        "rows":len(rows),
        "unique_games":len({r["game_id"] for r in rows}),
        "source_digest":hashlib.sha256(
            ("".join(warehouse.encode(r)+"\n" for r in rows)).encode()).hexdigest()}
    return result


def default_player_positions(rows):
    counts={}
    for row in rows:
        counts.setdefault(row["player_id"],Counter())[row["position"]]+=1
    return {pid:counts[pid].most_common(1)[0][0] for pid in sorted(counts)}


def build(data):
    """Real PyMC joint posterior: not empirical Bayes or independent engines."""
    try:
        import numpy as np
        import pymc as pm
        import pytensor.tensor as pt
    except ImportError as exc:
        raise RuntimeError("install requirements-joint-bayes.txt for offline fitting") from exc
    n_player=len(data["players"])
    n_season=len(data["seasons"])
    n_opponent=len(data["opponents"])
    ix=np.asarray(data["player_idx"],dtype="int64")
    pos=np.asarray(data["position_idx"],dtype="int64")
    season=np.asarray(data["season_idx"],dtype="int64")
    opp=np.asarray(data["opponent_idx"],dtype="int64")
    minutes=np.asarray(data["minutes"],dtype="float64")
    shots=np.asarray(data["shots"],dtype="int64")
    home=np.asarray(data["home"],dtype="float64")
    with pm.Model() as model:
        # Entire population prior is inferred, with correlated person effects.
        population_log_toi=pm.Normal("population_log_toi",mu=[2.65,2.80],sigma=.75,shape=2)
        population_log_shot_rate=pm.Normal("population_log_shot_rate",
                                          mu=[-2.25,-2.85],sigma=1.,shape=2)
        chol,corr,scale=pm.LKJCholeskyCov(
            "player_chol",n=2,eta=2,
            sd_dist=pm.HalfNormal.dist(.65,shape=2),compute_corr=True)
        latent=pm.Normal("player_z",mu=0.,sigma=1.,shape=(n_player,2))
        player_effect=pm.Deterministic("player_effect",pt.dot(latent,chol.T))
        # A single observed season cannot identify a *season-level*
        # variance, and its offset is confounded with population means.
        # Pin that offset to zero; infer centered nonzero effects only
        # when observations span at least two independent seasons.
        if n_season>1:
            season_toi_sd=pm.HalfNormal("season_toi_sd",.18)
            season_rate_sd=pm.HalfNormal("season_rate_sd",.20)
            season_toi_z=pm.Normal("season_toi_z",0.,1.,shape=n_season)
            season_rate_z=pm.Normal("season_rate_z",0.,1.,shape=n_season)
            season_toi=pm.Deterministic("season_toi",
                (season_toi_z-pt.mean(season_toi_z))*season_toi_sd)
            season_rate=pm.Deterministic("season_rate",
                (season_rate_z-pt.mean(season_rate_z))*season_rate_sd)
        else:
            season_toi=pm.Deterministic("season_toi",pt.zeros((n_season,)))
            season_rate=pm.Deterministic("season_rate",pt.zeros((n_season,)))
        opponent_rate_sd=pm.HalfNormal("opponent_rate_sd",.20)
        opponent_z=pm.Normal("opponent_z",0.,1.,shape=n_opponent)
        opponent_rate=pm.Deterministic("opponent_rate",
                                      (opponent_z-pt.mean(opponent_z))*opponent_rate_sd)
        home_rate=pm.Normal("home_rate",0.,.15)
        toi_sigma=pm.HalfNormal("toi_sigma",.40)
        overdisp=pm.Gamma("overdispersion",alpha=3.,beta=.35)
        log_toi=population_log_toi[pos]+player_effect[ix,0]+season_toi[season]
        pm.Normal("observed_log_toi",mu=log_toi,sigma=toi_sigma,observed=np.log(minutes))
        log_rate=(population_log_shot_rate[pos]+player_effect[ix,1]+
                  season_rate[season]+opponent_rate[opp]+home*home_rate)
        mu_shots=minutes*pt.exp(log_rate)
        pm.NegativeBinomial("observed_shots",mu=mu_shots,alpha=overdisp,observed=shots)
    return model


def fit(data, *, draws=1000, tune=1000, chains=4, seed=1729):
    if draws<20 or tune<20 or chains<2:
        raise ValueError("invalid_joint_posterior_sampling_budget")
    import pymc as pm
    model=build(data)
    with model:
        idata=pm.sample(draws=draws,tune=tune,chains=chains,cores=min(chains,2),
                        random_seed=seed,progressbar=False,
                        nuts={"target_accept":.99},
                        compute_convergence_checks=True,
                        return_inferencedata=True)
    return idata


def _diagnostic_values(result):
    """Support ArviZ Stats 1.x nested DataTree and older flat Dataset outputs."""
    import numpy as np
    if hasattr(result,"to_array"):
        groups=[result]
    elif hasattr(result,"subtree"):
        groups=[node.to_dataset() for node in result.subtree]
    else:
        raise ValueError("unrecognized_arviz_diagnostic_result")
    # Flatten each variable separately; to_array() broadcasts unrelated
    # player/season/opponent dimensions and can exhaust memory.
    values=[]
    for group in groups:
        if not getattr(group,"data_vars",None):
            continue
        for variable in group.data_vars.values():
            values.extend(np.asarray(variable,dtype=float).ravel().tolist())
    if not values:
        raise ValueError("empty_arviz_diagnostic_result")
    return values


def diagnostics(idata):
    import numpy as np
    try:
        from arviz_stats import rhat, ess
        selected=["population_log_toi","population_log_shot_rate",
                  "player_chol_stds","toi_sigma","overdispersion","home_rate",
                  "season_toi_sd","season_rate_sd","opponent_rate_sd"]
        # A posterior with healthy population hyperparameters but stuck local
        # effects is not an approved converged posterior.
        local=("player_effect","season_toi","season_rate","opponent_rate")
        if any(name not in idata.posterior for name in local):
            raise ValueError("missing_local_nhl_posterior_effects")
        chains=int(idata.posterior.sizes.get("chain",0))
        selected=[n for n in selected if n in idata.posterior] + list(local)
        if not selected:raise ValueError("missing_population_diagnostic_parameters")
        rh=rhat(idata.posterior,var_names=selected)
        ef=ess(idata.posterior,var_names=selected,method="bulk")
        tail=ess(idata.posterior,var_names=selected,method="tail")
        rh_values=_diagnostic_values(rh)
        ess_values=_diagnostic_values(ef)
        tail_values=_diagnostic_values(tail)
        divergent=int(np.asarray(idata.sample_stats["diverging"]).sum())
        depth=idata.sample_stats.get("reached_max_treedepth")
        depth_hits=(int(np.asarray(depth).sum()) if depth is not None else None)
        import joint_nhl_posterior_audit as joint_geometry
        extra=joint_geometry.geometry_stats(idata)
    except (ValueError,TypeError,AttributeError,KeyError,ImportError) as exc:
        return {"status":"diagnostics_unavailable","error":type(exc).__name__+':'+str(exc)[:160],
                "posterior_sampling_ok":False,
                "publication_eligible":False,"validated":False}
    finite=all(math.isfinite(v) for v in (rh_values+ess_values+tail_values))
    max_r=max(rh_values) if finite else None
    min_e=min(ess_values) if finite else None
    min_tail=min(tail_values) if finite else None
    healthy=(finite and chains==4 and max_r<=MAX_RHAT and min_e>=MIN_ESS_BULK
             and min_tail>=MIN_ESS_BULK and divergent==0
             and depth_hits==0 and extra["correlation_and_energy_check_pass"])
    return {"status":"sampling_diagnostics_pass" if healthy else "sampling_diagnostics_failed",
            "max_rhat":max_r,"min_bulk_ess":min_e,"min_tail_ess":min_tail,
            "max_treedepth_hits":depth_hits,
            "diagnosed_all_effects":True,"sampler_chains":chains,
            "divergences":divergent,
            "joint_geometry":extra,
            "posterior_sampling_ok":bool(healthy),
            "publication_eligible":False,"validated":False}


def predictive_cache(idata):
    """Flatten posterior arrays once for a whole frozen chronological cohort."""
    import numpy as np
    posterior=idata.posterior
    count=int(posterior.sizes["chain"])*int(posterior.sizes["draw"])
    if count<20:
        raise ValueError("insufficient_posterior_draws")
    required=("population_log_toi","population_log_shot_rate",
              "player_effect","season_toi","season_rate","opponent_rate",
              "toi_sigma","home_rate","overdispersion")
    if ("season_toi_sd" in posterior) != ("season_rate_sd" in posterior):
        raise ValueError("inconsistent_season_hierarchy")
    if "season_toi_sd" in posterior:
        required+=("season_toi_sd","season_rate_sd")
    arrays={}
    for name in required:
        raw=np.asarray(posterior[name],dtype=float)
        arrays[name]=raw.reshape((count,)+raw.shape[2:])
        if not np.all(np.isfinite(arrays[name])):
            raise ValueError("nonfinite_posterior_"+name)
    return {"count":count,"arrays":arrays}


def forecast(idata,data,*,player_id,opponent,season,home,line,draws=5000,seed=1903,
             fit_diagnostics=None,posterior_cache=None):
    """Posterior predictive count probability; conditional on appearing.

    Never enter the ranked production pipeline. Reject all missing/nonconverged
    training when attempting even a diagnostic forecast.
    """
    if not isinstance(line,(int,float)) or isinstance(line,bool) or not math.isfinite(line) or line<0:
        raise ValueError("invalid_shot_line")
    if (fit_diagnostics or {}).get("posterior_sampling_ok") is not True:
        raise ValueError("joint_mcmc_diagnostics_not_approved")
    if not 1<=draws<=100000:raise ValueError("invalid_predictive_draws")
    import numpy as np
    positions=data["player_position"]
    player=str(player_id)
    position=positions.get(player)
    if position not in ("F","D"):
        raise ValueError("new_player_requires_verified_position")
    if not isinstance(home,bool):
        raise ValueError("invalid_home_flag")
    if opponent not in data["opponents"]:
        raise ValueError("unknown_opponent_code")
    cache=posterior_cache if posterior_cache is not None else predictive_cache(idata)
    count=cache["count"]
    seed=int(seed)
    rng=np.random.default_rng(seed)
    indices=rng.integers(0,count,size=draws)
    pi=data["players"].index(player)
    oi=data["opponents"].index(opponent)
    season_index=data["seasons"].index(season) if season in data["seasons"] else None
    if season_index is None and "season_toi_sd" not in cache["arrays"]:
        raise ValueError("unseen_season_without_identified_multiseason_prior")
    pos=0 if position=="F" else 1
    def samples(name):
        return cache["arrays"][name][indices]
    pop_toi=samples("population_log_toi")[:,pos]
    pop_rate=samples("population_log_shot_rate")[:,pos]
    person=samples("player_effect")[:,pi,:]
    season_toi=(samples("season_toi")[:,season_index] if season_index is not None else
                rng.normal(0,samples("season_toi_sd")))
    season_rate=(samples("season_rate")[:,season_index] if season_index is not None else
                 rng.normal(0,samples("season_rate_sd")))
    opponent_rate=samples("opponent_rate")[:,oi]
    toi=np.exp(rng.normal(pop_toi+person[:,0]+season_toi,samples("toi_sigma")))
    mu=toi*np.exp(pop_rate+person[:,1]+season_rate+opponent_rate+
                  (1 if home else 0)*samples("home_rate"))
    alpha=samples("overdispersion")
    if np.any(~np.isfinite(mu)) or np.any(mu<=0) or np.any(alpha<=0):
        raise ValueError("nonfinite_or_nonpositive_posterior_likelihood")
    from scipy.stats import nbinom
    p=alpha/(alpha+mu)
    threshold=math.floor(line)
    # Integrate the conditional count outcome rather than drawing an
    # additional noisy observed game. This is Rao-Blackwellization,
    # with smaller MC error and fewer draws per player/game.
    over_each=nbinom.sf(threshold,alpha,p)
    if float(line).is_integer():
        under_each=nbinom.cdf(threshold-1,alpha,p)
        push_each=nbinom.pmf(threshold,alpha,p)
    else:
        under_each=nbinom.cdf(threshold,alpha,p)
        push_each=np.zeros(draws)
    if not (np.all(np.isfinite(over_each)) and np.all(np.isfinite(under_each))
            and np.all(np.isfinite(push_each))):
        raise ValueError("invalid_conditional_predictive_probability")
    over=float(np.mean(over_each))
    under=float(np.mean(under_each))
    push=float(np.mean(push_each))
    mc_se=float(np.std(over_each,ddof=1)/math.sqrt(draws)) if draws>1 else None
    return {"schema":"nhl_joint_bayesian_forecast_v1","status":"shadow_only",
            "model_version":VERSION,"player_id":player,"opponent":opponent,"season":season,
            "home":home,"line":line,"q_over":over,"q_under":under,"q_push":push,
            "draws":draws,"posterior_samples":count,
            "mc_standard_error_q_over":mc_se,
            "predictive_method":"latent_posterior_mc_conditional_nb_integrated",
            "source_digest":data["source_digest"],
            "training_through":data["last_game"],
            "conditional_on_appearance":True,"publication_eligible":False,
            "calibrated":False,"ranking_allowed":False}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,default=warehouse.ROOT)
    p.add_argument("--as-of",required=True,help="Only completed games strictly before this date")
    p.add_argument("--max-seasons",type=int,default=8)
    p.add_argument("--min-rows",type=int,default=2000)
    p.add_argument("--max-per-position",type=int,default=0,
                   help="0=entire population; otherwise select top N historical F and D from train-only data")
    p.add_argument("--draws",type=int,default=1000)
    p.add_argument("--tune",type=int,default=1000)
    p.add_argument("--chains",type=int,default=4)
    p.add_argument("--seed",type=int,default=1729)
    p.add_argument("--out",type=Path,default=Path("reports/joint_nhl"))
    args=p.parse_args(argv)
    rows=warehouse.read_history(args.root,before=args.as_of,
                  max_seasons=args.max_seasons,min_games=args.min_rows)
    source_unfiltered_rows=len(rows)
    rows=subset_training_players(rows,max_per_position=args.max_per_position)
    data=prepare(rows,min_rows=args.min_rows)
    idata=fit(data,draws=args.draws,tune=args.tune,chains=args.chains,seed=args.seed)
    quality=diagnostics(idata)
    args.out.mkdir(parents=True,exist_ok=True)
    idata.to_netcdf(args.out/"posterior.nc")
    manifest={k:v for k,v in data.items() if k in
            ("players","seasons","opponents","player_position","rows","unique_games",
             "source_digest","first_game","last_game")}
    manifest.update({"schema":"nhl_joint_bayesian_fit_v1","version":VERSION,
                     "training_cutoff_exclusive":args.as_of,
                     "draws":args.draws,"tune":args.tune,"chains":args.chains,
                     "max_per_position":args.max_per_position,
                     "unfiltered_source_rows":source_unfiltered_rows,
                     "pilot_subset":bool(args.max_per_position),
                     "diagnostics":quality,"publication_eligible":False,
                     "status":"shadow_only"})
    (args.out/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:v for k,v in manifest.items() if k not in ("players","player_position","opponents")},sort_keys=True))
    return 0 if quality.get("posterior_sampling_ok") else 2


if __name__=="__main__":
    raise SystemExit(main())
