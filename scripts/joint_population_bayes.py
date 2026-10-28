#!/usr/bin/env python3
"""Shadow-only, fully joint hierarchical workload and production populations.

Supports NHL shots/hits/blocks/saves; NBA scoring, counting and combinations;
NFL count attempts/receptions/targets/carries/TDs and signed yardage (Student-t).
Unknown population means, player workload-rate correlation, season/opponent
effects and likelihood dispersion are jointly sampled with NUTS. Never ranks.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
import population_history as history

VERSION="multisport-joint-bayes-v1"
MAX_RHAT=1.01
MIN_ESS=400


def training_only_subset(rows, *, max_per_position=0):
    """Optional tractable cohort selected solely from pre-cutoff training games.

    Never select players by heldout appearance or results. A subset must be
    compared to the baseline ONLY on identical heldout player-game records.
    """
    if max_per_position==0:
        return rows
    if not isinstance(max_per_position,int) or max_per_position<1:
        raise ValueError("invalid_training_only_cohort_limit")
    observed={}
    for r in rows:
        observed.setdefault(r["position"],Counter())[r["player_id"]]+=1
    keep=set()
    for pos,counts in sorted(observed.items()):
        ranked=sorted(counts,key=lambda p:(-counts[p],p))
        keep.update(ranked[:max_per_position])
    return [r for r in rows if r["player_id"] in keep]


def prepare(rows,*,min_rows=300):
    if len(rows)<min_rows:raise ValueError("insufficient_joint_population_sample")
    sport,stat=rows[0]["sport"],rows[0]["stat"]
    ident=set()
    for row in rows:
        history.validate(row)
        if (row["sport"],row["stat"])!=(sport,stat):raise ValueError("mixed_stat_or_sport_in_fit")
        key=(row["game_id"],row["player_id"])
        if key in ident:raise ValueError("duplicate_population_player_game")
        ident.add(key)
    players=sorted({r["player_id"] for r in rows})
    positions=sorted({r["position"] for r in rows})
    seasons=sorted({r["season"] for r in rows})
    opponents=sorted({r["opponent"] for r in rows})
    if len(players)<12 or len(opponents)<2:raise ValueError("thin_joint_population")
    if len(positions)>16:raise ValueError("unbounded_position_hierarchy")
    maps=[{key:i for i,key in enumerate(group)}
          for group in (players,positions,seasons,opponents)]
    player_position={}
    for r in rows:
        player_position.setdefault(r["player_id"],Counter())[r["position"]]+=1
    return {
        "sport":sport,"stat":stat,"family":history.family(sport,stat),
        "players":players,"positions":positions,"seasons":seasons,"opponents":opponents,
        "player_idx":[maps[0][r["player_id"]] for r in rows],
        "position_idx":[maps[1][r["position"]] for r in rows],
        "season_idx":[maps[2][r["season"]] for r in rows],
        "opponent_idx":[maps[3][r["opponent"]] for r in rows],
        "home":[int(r["home"]) for r in rows],
        "workload":[float(r["workload"]) for r in rows],
        "value":[r["value"] for r in rows],
        "player_position":{p:c.most_common(1)[0][0] for p,c in player_position.items()},
        "workload_unit":rows[0]["workload_unit"],
        "first_game":min(r["game_date"] for r in rows),
        "last_game":max(r["game_date"] for r in rows),
        "rows":len(rows),"games":len({r["game_id"] for r in rows}),
        "source_digest":hashlib.sha256(
            ("".join(history.canonical_json(r)+"\n" for r in rows)).encode()).hexdigest()
    }


def build(data):
    import numpy as np
    import pymc as pm
    import pytensor.tensor as pt
    shape=len(data["positions"])
    nplayer=len(data["players"]);nseason=len(data["seasons"]);nopp=len(data["opponents"])
    p=np.asarray(data["player_idx"],dtype="int64")
    group=np.asarray(data["position_idx"],dtype="int64")
    s=np.asarray(data["season_idx"],dtype="int64")
    o=np.asarray(data["opponent_idx"],dtype="int64")
    home=np.asarray(data["home"],dtype=float)
    workload=np.asarray(data["workload"],dtype=float)
    outcome=np.asarray(data["value"],dtype=float)
    if len(set(r for r in data["workload"]))<5:
        raise ValueError("missing_workload_variation_for_joint_fit")
    # Broad *fixed* population hyper-prior centers, not fitted plug-in priors.
    base={"NHL":2.9,"NBA":3.1,"NFL":3.7}[data["sport"]]
    with pm.Model() as model:
        population_workload=pm.Normal("population_workload",base,1.0,shape=shape)
        # Log rate for count markets; signed rate for continuous NFL yards.
        population_rate=pm.Normal("population_rate",
            -1.4 if data["family"]=="count" else 0.,2.5 if data["family"]=="count" else 5.,
            shape=shape)
        chol,corr,stds=pm.LKJCholeskyCov("player_chol",n=2,eta=2,
            sd_dist=pm.HalfNormal.dist(.6,shape=2),compute_corr=True)
        random=pm.Normal("player_z",0,1,shape=(nplayer,2))
        player=pm.Deterministic("player_effect",pt.dot(random,chol.T))
        if nseason>1:
            sd_work=pm.HalfNormal("season_workload_sd",.2)
            sd_rate=pm.HalfNormal("season_rate_sd",.2 if data["family"]=="count" else 1.)
            raw_work=pm.Normal("season_workload_z",0,1,shape=nseason)
            raw_rate=pm.Normal("season_rate_z",0,1,shape=nseason)
            season_work=pm.Deterministic("season_workload",
                            (raw_work-pt.mean(raw_work))*sd_work)
            season_rate=pm.Deterministic("season_rate",
                            (raw_rate-pt.mean(raw_rate))*sd_rate)
        else:
            season_work=pm.Deterministic("season_workload",pt.zeros((nseason,)))
            season_rate=pm.Deterministic("season_rate",pt.zeros((nseason,)))
        opp_sd=pm.HalfNormal("opponent_rate_sd",
                            .22 if data["family"]=="count" else 1.)
        opp_z=pm.Normal("opponent_rate_z",0,1,shape=nopp)
        opp_rate=pm.Deterministic("opponent_rate",
                    (opp_z-pt.mean(opp_z))*opp_sd)
        home_effect=pm.Normal("home_effect",0,.18 if data["family"]=="count" else 1.)
        workload_sigma=pm.HalfNormal("workload_sigma",.45)
        pm.Normal("observed_log_workload",
            mu=population_workload[group]+player[p,0]+season_work[s],
            sigma=workload_sigma,observed=np.log(workload))
        rate=population_rate[group]+player[p,1]+season_rate[s]+opp_rate[o]+home*home_effect
        if data["family"]=="count":
            alpha=pm.Gamma("count_dispersion",alpha=3.,beta=.35)
            pm.NegativeBinomial("observed_volume",mu=workload*pt.exp(rate),
                                alpha=alpha,observed=outcome.astype("int64"))
        else:
            sigma=pm.HalfNormal("yardage_sigma",60.)
            pm.StudentT("observed_volume",nu=4,mu=workload*rate,
                        sigma=sigma,observed=outcome)
    return model


def fit(data,*,draws=1000,tune=1200,chains=4,seed=19031):
    if draws<20 or tune<20 or chains<2:
        raise ValueError("invalid_multisport_nuts_budget")
    import pymc as pm
    with build(data):
        return pm.sample(draws=draws,tune=tune,chains=chains,cores=min(chains,2),
                        random_seed=seed,progressbar=False,
                        nuts={"target_accept":.99},compute_convergence_checks=True,
                        return_inferencedata=True)


def _to_values(result):
    import numpy as np
    if hasattr(result,"to_array"):groups=[result]
    elif hasattr(result,"subtree"):groups=[node.to_dataset() for node in result.subtree]
    else:raise ValueError("unsupported_arviz_results")
    values=[]
    for group in groups:
        if getattr(group,"data_vars",None):
            values.extend(np.asarray(group.to_array(),dtype=float).ravel().tolist())
    if not values or not all(math.isfinite(v) for v in values):
        raise ValueError("missing_or_invalid_posterior_diagnostic")
    return values


def diagnostics(idata):
    import numpy as np
    try:
        from arviz_stats import rhat,ess
        keys=["population_workload","population_rate","player_chol_stds",
              "workload_sigma","opponent_rate_sd","home_effect"]
        if "count_dispersion" in idata.posterior:keys.append("count_dispersion")
        if "yardage_sigma" in idata.posterior:keys.append("yardage_sigma")
        if "season_rate_sd" in idata.posterior:keys.extend(["season_rate_sd","season_workload_sd"])
        all_r=_to_values(rhat(idata.posterior,var_names=keys))
        all_e=_to_values(ess(idata.posterior,var_names=keys,method="bulk"))
        # LKJ correlation diagonals are IDENTICALLY 1 in every posterior
        # draw. Including those constants in ArviZ R-hat/ESS returns NaN
        # and silently vetoes an otherwise converged model. Diagnose only
        # the uncertain off-diagonal correlation, never waive its Rhat/ESS.
        corr=np.asarray(idata.posterior["player_chol_corr"])
        if corr.ndim!=4 or corr.shape[-2:]!=(2,2):
            raise ValueError("malformed_player_effect_correlation_posterior")
        import xarray as xr
        offdiag=xr.Dataset({"estimated_player_correlation":(
            ("chain","draw"),corr[...,0,1])})
        all_r.extend(_to_values(rhat(offdiag,var_names=["estimated_player_correlation"])))
        all_e.extend(_to_values(ess(offdiag,var_names=["estimated_player_correlation"],method="bulk")))
        divergences=int(np.asarray(idata.sample_stats["diverging"]).sum())
        # BFMI from each chain; global minimum >= .30 required for approval.
        energy=np.asarray(idata.sample_stats["energy"],dtype=float)
        bfmi=np.mean(np.diff(energy,axis=-1)**2,axis=-1)/np.var(energy,axis=-1)
        if not np.all(np.isfinite(bfmi)):
            raise ValueError("invalid_nuts_energy")
    except (ImportError,AttributeError,KeyError,TypeError,ValueError) as exc:
        return {"status":"diagnostics_unavailable","error":str(exc)[:180],
                "posterior_sampling_ok":False,"publication_eligible":False}
    r_max=max(all_r);ess_min=min(all_e);energy_min=float(min(bfmi))
    passed=(r_max<=MAX_RHAT and ess_min>=MIN_ESS and
            divergences==0 and energy_min>=.30)
    return {"status":"sampling_diagnostics_pass" if passed else "sampling_diagnostics_failed",
        "max_rhat":r_max,"min_bulk_ess":ess_min,
        "divergences":divergences,"minimum_bfmi":energy_min,
        "posterior_sampling_ok":passed,"publication_eligible":False}


def posterior_cache(idata):
    import numpy as np
    posterior=idata.posterior
    count=posterior.sizes["chain"]*posterior.sizes["draw"]
    return {"count":count,
        "arrays":{key:np.asarray(posterior[key]).reshape((count,)+posterior[key].shape[2:])
                  for key in posterior.data_vars}}


def forecast(idata,data,*,player_id,opponent,season,home,line,seed=193,
             draws=1500,diagnostic=None,cache=None):
    if (diagnostic or {}).get("posterior_sampling_ok") is not True:
        raise ValueError("unapproved_joint_posterior_diagnostics")
    if isinstance(line,bool) or not isinstance(line,(int,float)) or not math.isfinite(line):
        raise ValueError("invalid_population_market_line")
    if not isinstance(home,bool) or not 50<=draws<=100000:
        raise ValueError("invalid_population_prediction_context")
    import numpy as np
    from scipy.stats import nbinom,t
    player=str(player_id)
    if player not in data["player_position"]:
        raise ValueError("unseen_player_requires_hierarchical_new_player_model")
    if opponent not in data["opponents"]:
        raise ValueError("unseen_opponent_requires_explicit_prior")
    new_season=season not in data["seasons"]
    if new_season and len(data["seasons"])<2:
        raise ValueError("unseen_season_requires_identified_multiseason_prior")
    idx=data["players"].index(player);group=data["positions"].index(data["player_position"][player])
    oid=data["opponents"].index(opponent)
    sid=data["seasons"].index(season) if not new_season else None
    frozen=cache if cache is not None else posterior_cache(idata)
    rng=np.random.default_rng(seed)
    picks=rng.integers(0,frozen["count"],size=draws)
    def sample(name):return frozen["arrays"][name][picks]
    person=sample("player_effect")[:,idx,:]
    # New seasons require multi-season training to identify population
    # season variance. Never look up their heldout realized offset.
    if new_season:
        season_workload=rng.normal(0,sample("season_workload_sd"))
        season_rate=rng.normal(0,sample("season_rate_sd"))
    else:
        season_workload=sample("season_workload")[:,sid]
        season_rate=sample("season_rate")[:,sid]
    exposure=np.exp(rng.normal(sample("population_workload")[:,group]+
        person[:,0]+season_workload,sample("workload_sigma")))
    rate=sample("population_rate")[:,group]+person[:,1]+season_rate+(
        sample("opponent_rate")[:,oid])+(1 if home else 0)*sample("home_effect")
    if data["family"]=="count":
        if line<0:raise ValueError("negative_count_line")
        mu=exposure*np.exp(rate);alpha=sample("count_dispersion")
        if np.any(~np.isfinite(mu)) or np.any(mu<=0):raise ValueError("invalid_predictive_volume")
        threshold=math.floor(line)
        p=alpha/(alpha+mu)
        over_events=nbinom.sf(threshold,alpha,p)
        push_events=nbinom.pmf(threshold,alpha,p) if float(line).is_integer() else np.zeros(draws)
    else:
        scale=sample("yardage_sigma")
        over_events=t.sf(line,df=4,loc=exposure*rate,scale=scale)
        push_events=np.zeros(draws)
    if not np.all(np.isfinite(over_events)) or not np.all(np.isfinite(push_events)):
        raise ValueError("invalid_predictive_probabilities")
    over=float(np.mean(over_events));push=float(np.mean(push_events))
    return {"schema":"multi_sport_joint_shadow_forecast_v1",
            "sport":data["sport"],"stat":data["stat"],"family":data["family"],
            "model_version":VERSION,"player_id":player,"opponent":opponent,
            "season":season,"home":home,"line":float(line),
            "q_over":over,"q_push":push,"q_under":max(0,1-over-push),
            "draws":draws,
            "numerical_mc_se":float(np.std(over_events,ddof=1)/math.sqrt(draws)),
            "source_digest":data["source_digest"],"training_through":data["last_game"],
            "status":"shadow_only","conditional_on_appearance":True,
            "calibrated":False,"publication_eligible":False,"ranking_allowed":False}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument("--sport",choices=history.SPORTS,required=True)
    p.add_argument("--stat",required=True)
    p.add_argument("--as-of",required=True)
    p.add_argument("--max-seasons",type=int,default=7)
    p.add_argument("--max-per-position",type=int,default=0,
        help="Optional train-only cohort size per position; 0 fits full population")
    p.add_argument("--min-rows",type=int,default=8000)
    p.add_argument("--draws",type=int,default=1000)
    p.add_argument("--tune",type=int,default=1200)
    p.add_argument("--chains",type=int,default=4)
    p.add_argument("--out",type=Path,default=Path("reports/joint_population"))
    a=p.parse_args(argv)
    rows=history.read(a.root,sport=a.sport,stat=a.stat,before=a.as_of,
                      max_seasons=a.max_seasons,min_records=a.min_rows)
    full_population_size=len(rows)
    rows=training_only_subset(rows,max_per_position=a.max_per_position)
    if a.max_per_position and len(rows)<300:
        raise ValueError("insufficient_training_only_joint_cohort")
    data=prepare(rows,min_rows=300 if a.max_per_position else a.min_rows)
    posterior=fit(data,draws=a.draws,tune=a.tune,chains=a.chains)
    checks=diagnostics(posterior)
    a.out.mkdir(parents=True,exist_ok=True)
    posterior.to_netcdf(a.out/"posterior.nc")
    manifest={k:data[k] for k in ("sport","stat","family","players","positions","seasons",
             "opponents","player_position","source_digest","first_game","last_game",
             "rows","games","workload_unit")}
    manifest.update({"schema":"multisport_joint_fit_manifest_v1","model_version":VERSION,
                     "unfiltered_train_rows":full_population_size,
                     "max_per_position":a.max_per_position,
                     "training_cutoff_exclusive":a.as_of,"diagnostics":checks,
                     "publication_eligible":False,"calibrated":False})
    (a.out/"manifest.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n")
    print(json.dumps({k:v for k,v in manifest.items() if k not in
                    ("players","player_position","opponents")},sort_keys=True))
    return 0 if checks.get("posterior_sampling_ok") else 2


if __name__=="__main__":
    raise SystemExit(main())
