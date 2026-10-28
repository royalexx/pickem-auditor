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
        # Distinct season, opponent, home effects are inferred and shrunk.
        season_toi_sd=pm.HalfNormal("season_toi_sd",.18)
        season_rate_sd=pm.HalfNormal("season_rate_sd",.20)
        opponent_rate_sd=pm.HalfNormal("opponent_rate_sd",.20)
        season_toi_z=pm.Normal("season_toi_z",0.,1.,shape=n_season)
        season_rate_z=pm.Normal("season_rate_z",0.,1.,shape=n_season)
        opponent_z=pm.Normal("opponent_z",0.,1.,shape=n_opponent)
        season_toi=pm.Deterministic("season_toi",season_toi_z*season_toi_sd)
        season_rate=pm.Deterministic("season_rate",season_rate_z*season_rate_sd)
        opponent_rate=pm.Deterministic("opponent_rate",opponent_z*opponent_rate_sd)
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
                        nuts={"target_accept":.95},
                        compute_convergence_checks=True,
                        return_inferencedata=True)
    return idata


def diagnostics(idata):
    import numpy as np
    try:
        from arviz_stats import rhat, ess
        selected=["population_log_toi","population_log_shot_rate",
                  "player_chol_stds","toi_sigma","overdispersion",
                  "season_toi_sd","season_rate_sd","opponent_rate_sd"]
        selected=[n for n in selected if n in idata.posterior]
        rh=rhat(idata,var_names=selected)
        ef=ess(idata,var_names=selected,method="bulk")
        max_r=float(np.asarray(rh.to_array()).max())
        min_e=float(np.asarray(ef.to_array()).min())
        divergent=int(np.asarray(idata.sample_stats["diverging"]).sum())
    except (ValueError,TypeError,AttributeError,KeyError,ImportError) as exc:
        return {"status":"diagnostics_unavailable","error":type(exc).__name__,
                "publication_eligible":False,"validated":False}
    healthy=(max_r<=MAX_RHAT and min_e>=MIN_ESS_BULK and divergent==0)
    return {"status":"sampling_diagnostics_pass" if healthy else "sampling_diagnostics_failed",
            "max_rhat":max_r,"min_bulk_ess":min_e,
            "divergences":divergent,"posterior_sampling_ok":healthy,
            "publication_eligible":False,"validated":False}


def forecast(idata,data,*,player_id,opponent,season,home,line,draws=5000,seed=1903,
             fit_diagnostics=None):
    """Posterior predictive count probability; conditional on appearing.

    Never enter the ranked production pipeline. Reject all missing/nonconverged
    training when attempting even a diagnostic forecast.
    """
    import numpy as np
    if not isinstance(line,(int,float)) or isinstance(line,bool) or not math.isfinite(line) or line<0:
        raise ValueError("invalid_shot_line")
    if (fit_diagnostics or {}).get("posterior_sampling_ok") is not True:
        raise ValueError("joint_mcmc_diagnostics_not_approved")
    if not 1<=draws<=100000:raise ValueError("invalid_predictive_draws")
    positions=data["player_position"]
    player=str(player_id)
    position=positions.get(player)
    if position not in ("F","D"):
        raise ValueError("new_player_requires_verified_position")
    if not isinstance(home,bool):
        raise ValueError("invalid_home_flag")
    if opponent not in data["opponents"]:
        raise ValueError("unknown_opponent_code")
    posterior=idata.posterior
    seed=int(seed)
    rng=np.random.default_rng(seed)
    count=posterior.sizes["chain"]*posterior.sizes["draw"]
    if count<20:raise ValueError("insufficient_posterior_draws")
    indices=rng.integers(0,count,size=draws)
    pi=data["players"].index(player)
    oi=data["opponents"].index(opponent)
    season_index=data["seasons"].index(season) if season in data["seasons"] else None
    pos=0 if position=="F" else 1
    def samples(name):
        vals=np.asarray(posterior[name])
        return vals.reshape((count,)+vals.shape[2:])[indices]
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
    count_shots=rng.negative_binomial(alpha,alpha/(alpha+mu))
    over=float(np.mean(count_shots>line))
    push=float(np.mean(count_shots==line)) if float(line).is_integer() else 0.
    under=float(np.mean(count_shots<line))
    return {"schema":"nhl_joint_bayesian_forecast_v1","status":"shadow_only",
            "model_version":VERSION,"player_id":player,"opponent":opponent,"season":season,
            "home":home,"line":line,"q_over":over,"q_under":under,"q_push":push,
            "draws":draws,"posterior_samples":count,
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
    p.add_argument("--draws",type=int,default=1000)
    p.add_argument("--tune",type=int,default=1000)
    p.add_argument("--chains",type=int,default=4)
    p.add_argument("--seed",type=int,default=1729)
    p.add_argument("--out",type=Path,default=Path("reports/joint_nhl"))
    args=p.parse_args(argv)
    rows=warehouse.read_history(args.root,before=args.as_of,
                  max_seasons=args.max_seasons,min_games=args.min_rows)
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
                     "diagnostics":quality,"publication_eligible":False,
                     "status":"shadow_only"})
    (args.out/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:v for k,v in manifest.items() if k not in ("players","player_position","opponents")},sort_keys=True))
    return 0 if quality.get("posterior_sampling_ok") else 2


if __name__=="__main__":
    raise SystemExit(main())
