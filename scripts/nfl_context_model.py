"""NFL count-rate challenger: bounded workload and separate player/team effects.

Not a route charting, formation, target-allocation or yardage model. All graphs
remain conditional on appearance. Context cannot alter production rankings.
"""
from __future__ import annotations
import math
import nhl_context_data as common
from nhl_context_model import diagnostics

VERSION="nfl-context-count-v3"


def workload_layout(d):
    """Training-only choice: center players with >=5 workload observations."""
    import numpy as np
    positions=np.asarray([d["positions"].index(d["player_position"][p]) for p in d["players"]])
    counts=np.bincount(d["player_idx"],minlength=len(d["players"]))
    if not np.array_equal(positions[np.asarray(d["player_idx"])],d["position_idx"]):
        raise ValueError("nfl_player_position_indices_inconsistent")
    return positions,counts>=5


def workload_coordinates(raw,rate_z,population,chol,centered):
    """Exact mixed parameterization of the original correlated player prior.

    Centered raw values are total player workload intercepts N(population, L00).
    Sparse players keep standard-normal workload coordinates. Production remains
    conditionally noncentered, preserving the complete bivariate LKJ prior.
    """
    import pytensor.tensor as pt
    z0=pt.where(centered,(raw-population)/chol[0,0],raw)
    z=pt.stack([z0,rate_z],axis=1)
    return z,pt.dot(z,chol.T)


def sampling_progress(trace,draw):
    """ASCII-only progress in campaign logs, including on Windows terminals."""
    if (draw.draw_idx+1)%250==0 or draw.is_last:
        phase="warmup" if draw.tuning else "posterior"
        print(f"NUTS_PROGRESS chain={draw.chain} iteration={draw.draw_idx+1} phase={phase}",flush=True)


def build(d):
    import numpy as np
    import pymc as pm
    import pytensor.tensor as pt
    ix,ti,oi,si,pi=(np.asarray(d[k+"_idx"]) for k in ("player","team","opponent","season","position"))
    x=np.asarray(d["x"]);snaps=np.asarray(d["snaps"])
    player_positions,centered=workload_layout(d)
    with pm.Model() as graph:
        work_prior=[math.log(v/(160-v)) for v in
                    [{"QB":60.,"RB":30.,"WR":45.,"TE":40.}.get(p,45.) for p in d["positions"]]]
        rate={"targets":.12,"receptions":.08,"carries":.35,"pass attempts":.5,"tackles + assists":.1}[d["market"]]
        pw=pm.Normal("population_workload",work_prior,.5,shape=len(d["positions"]))
        pr=pm.Normal("population_log_rate",math.log(rate),.7,shape=len(d["positions"]))
        chol,_,_=pm.LKJCholeskyCov("player_chol",n=2,eta=3,
                                  sd_dist=pm.HalfNormal.dist(.4,shape=2),compute_corr=True)
        population=pw[player_positions]
        raw=pm.Normal("player_workload_raw",mu=pt.where(centered,population,0.),
                      sigma=pt.where(centered,chol[0,0],1.),shape=len(d["players"]))
        rate_z=pm.Normal("player_rate_z",0,1,shape=len(d["players"]))
        z,effect=workload_coordinates(raw,rate_z,population,chol,centered)
        pm.Deterministic("player_z",z)
        player=pm.Deterministic("player_effect",effect)
        ts=pm.HalfNormal("team_sd",.2,shape=2)
        tz=pm.Normal("team_z",0,1,shape=(len(d["teams"]),2))
        team=pm.Deterministic("team_effect",(tz-pt.mean(tz,axis=0))*ts)
        ss=pm.HalfNormal("season_sd",.2,shape=2)
        sz=pm.Normal("season_z",0,1,shape=(len(d["seasons"]),2))
        season=pm.Deterministic("season_effect",(sz-pt.mean(sz,axis=0))*ss)
        # Read allocation describes target production; core workload predictors
        # drive snaps. Do not duplicate dozens of read coefficients in both stages.
        nw=min(7,x.shape[1])
        bw=pm.Normal("beta_workload",0,.2,shape=nw)
        br=pm.Normal("beta_rate",0,.2,shape=x.shape[1])
        sigma=pm.HalfNormal("workload_sigma",.7)
        pm.Normal("observed_logit_snaps",pw[pi]+player[ix,0]+season[si,0]+pt.dot(x[:,:nw],bw),sigma,
                  observed=np.log(snaps/(160-snaps)))
        eta=pr[pi]+player[ix,1]+team[ti,0]+team[oi,1]+season[si,1]+pt.dot(x,br)
        alpha=pm.Gamma("count_dispersion",3,.2)
        pm.NegativeBinomial("observed_count",mu=snaps*pt.exp(eta),alpha=alpha,
                            observed=np.asarray(d["target"]))
    return graph


def fit(d, *, draws=1500,tune=1500,chains=4,cores=2,seed=20261030):
    if not 1<=cores<=chains<=8 or min(draws,tune)<20:raise ValueError("invalid_nfl_sampling_budget")
    import pymc as pm
    graph=build(d)
    with graph:
        trace=pm.sample(draws=draws,tune=tune,chains=chains,cores=cores,random_seed=seed,
                        progressbar=False,callback=sampling_progress,
                        nuts={"target_accept":.97,"max_treedepth":12},return_inferencedata=True)
    trace.posterior.attrs.update(model_version=VERSION,source_digest=d["source_digest"],
                                stochastic_variables=common.encode([v.name for v in graph.free_RVs]))
    return trace


def cache(trace,d):
    import numpy as np
    if trace.posterior.attrs.get("source_digest")!=d["source_digest"] or trace.posterior.attrs.get("model_version")!=VERSION:
        raise ValueError("nfl_posterior_design_mismatch")
    n=int(trace.posterior.sizes["chain"])*int(trace.posterior.sizes["draw"])
    arrays={k:np.asarray(trace.posterior[k]).reshape((n,)+np.asarray(trace.posterior[k]).shape[2:])
            for k in ("population_workload","population_log_rate","player_effect","team_effect","season_effect",
                      "season_sd","beta_workload","beta_rate","workload_sigma","count_dispersion")}
    if any(not np.isfinite(a).all() for a in arrays.values()):raise ValueError("nonfinite_nfl_posterior")
    return {"n":n,"arrays":arrays,"source_digest":d["source_digest"]}


def forecast(c,d,row, *, line,draws=4000,diagnostic):
    """Forecast a pregame row; observed target is optional and only used to score."""
    import numpy as np
    from scipy.special import expit,logsumexp
    from scipy.stats import nbinom
    if not diagnostic.get("posterior_sampling_ok"):raise ValueError("nfl_posterior_not_converged")
    if c["source_digest"]!=d["source_digest"]:raise ValueError("nfl_cache_mismatch")
    if isinstance(line,bool) or not isinstance(line,(int,float)) or not math.isfinite(line) or line<0:
        raise ValueError("invalid_nfl_line")
    if isinstance(draws,bool) or not isinstance(draws,int) or not 100<=draws<=100000:
        raise ValueError("invalid_nfl_predictive_budget")
    target=row.get("target")
    if target is not None and (isinstance(target,bool) or not isinstance(target,(int,float)) or
                               not math.isfinite(target) or target<0 or not float(target).is_integer()):
        raise ValueError("invalid_nfl_observed_count")
    if common.instant(row["start_time"])<common.instant(d["cutoff"]) or row["feature_time"]!=row["start_time"]:
        raise ValueError("nfl_forecast_time_mismatch")
    if row["stat"]!=d["market"] or row["feature_names"]!=d["feature_names"]:
        raise ValueError("nfl_forecast_market_or_features_mismatch")
    if row["player_id"] not in d["players"] or row["team"] not in d["teams"] or row["opponent"] not in d["teams"]:
        raise ValueError("unseen_nfl_entity_requires_population_mapping")
    if d["player_position"][row["player_id"]]!=row["position"]:raise ValueError("nfl_position_mismatch")
    rng=np.random.default_rng(int(common.digest([row["game_id"],row["player_id"]])[:8],16))
    pick=rng.integers(0,c["n"],draws);a={k:v[pick] for k,v in c["arrays"].items()}
    ix=d["players"].index(row["player_id"]);ti=d["teams"].index(row["team"]);oi=d["teams"].index(row["opponent"])
    pi=d["positions"].index(row["position"])
    s=(a["season_effect"][:,d["seasons"].index(row["season"])] if row["season"] in d["seasons"]
       else rng.normal(0,a["season_sd"]))
    raw=np.asarray(row["x"],dtype=float)
    if np.isnan(raw[:7] if d.get("read_features") else raw).any():raise ValueError("missing_core_nfl_forecast_feature")
    x=(np.where(np.isnan(raw),d["center"],raw)-d["center"])/d["scale"]
    if not np.isfinite(x).all():raise ValueError("nonfinite_nfl_forecast_features")
    work=a["population_workload"][:,pi]+a["player_effect"][:,ix,0]+s[:,0]+(a["beta_workload"]*x[:a["beta_workload"].shape[1]]).sum(1)
    snaps=160*expit(rng.normal(work,a["workload_sigma"]))
    rate=a["population_log_rate"][:,pi]+a["player_effect"][:,ix,1]+a["team_effect"][:,ti,0]+a["team_effect"][:,oi,1]+s[:,1]+(a["beta_rate"]*x).sum(1)
    mu=snaps*np.exp(rate);alpha=a["count_dispersion"];p=alpha/(alpha+mu);floor=math.floor(line)
    over=nbinom.sf(floor,alpha,p);under=nbinom.cdf(floor-1 if float(line).is_integer() else floor,alpha,p)
    push=nbinom.pmf(floor,alpha,p) if float(line).is_integer() else np.zeros(draws)
    if not np.isfinite(np.concatenate([over,under,push])).all():raise ValueError("nonfinite_nfl_forecast")
    outcome=nbinom.rvs(alpha,p,random_state=rng)
    return {"game_id":row["game_id"],"player_id":row["player_id"],"market":d["market"],"line":line,
            "start_time":row["start_time"],"training_cutoff_exclusive":d["cutoff"],"target":target,
            "q_over":float(over.mean()),"q_under":float(under.mean()),"q_push":float(push.mean()),
            "expected_snaps":float(snaps.mean()),"expected_value":float(mu.mean()),
            "predictive_interval_90":np.quantile(outcome,[.05,.95]).tolist(),
            "log_predictive_density":(None if target is None else
                float(logsumexp(nbinom.logpmf(target,alpha,p))-math.log(draws))),
            "model_version":VERSION,"conditional_on":"appearance","ranking_allowed":False}
