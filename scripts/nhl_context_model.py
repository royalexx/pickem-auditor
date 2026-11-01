"""Hierarchical NHL context challenger; bounded exposure -> opportunity -> outcome.

Saves: NB shots faced + beta-binomial saves conditional on those shots.
Skaters: NB outcomes with stat-specific pregame opportunity covariates.
All fits and forecasts are research-only, including fits that converge.
"""
from __future__ import annotations

import math

import nhl_context_data as store

VERSION = "nhl-context-challenger-v1"


def _diagnostic_values(result):
    """Flatten variables individually; Dataset.to_array broadcasts dimensions.

    Broadcasting player, team, season and coefficient dimensions together can
    create an enormous Cartesian product during an otherwise small diagnostic.
    """
    import numpy as np
    if hasattr(result,"subtree"):
        groups=[node.to_dataset() for node in result.subtree]
    elif hasattr(result,"data_vars"):
        groups=[result]
    else:
        raise ValueError("unsupported_diagnostic_result")
    values=[]
    for group in groups:
        for variable in group.data_vars.values():
            values.extend(np.asarray(variable,dtype=float).ravel().tolist())
    if not values or not all(math.isfinite(v) for v in values):
        raise ValueError("missing_or_nonfinite_diagnostic_values")
    return values


def build(data):
    import numpy as np
    import pymc as pm
    import pytensor.tensor as pt
    n = len(data["players"])
    nteam, ns, npos = len(data["teams"]), len(data["seasons"]), len(data["positions"])
    ix, ti, oi, si, pos = (np.asarray(data[k], dtype="int64") for k in
                          ("player_idx", "team_idx", "opponent_idx", "season_idx", "position_idx"))
    x = np.asarray(data["x"])
    nc = min(7, x.shape[1])
    exposure = np.asarray(data["minutes"])
    # Continuity correction retains full-game starts without unbounded minutes.
    share = (exposure + .05) / (np.asarray(data["game_minutes"]) + .1)
    logit_share = np.log(share / (1-share))
    saves = data["market"] == "saves"
    workload_prior = [{"F": -.99, "D": -.69, "G": 3.4}[p] for p in data["positions"]]
    rate_prior = ([-.693] if saves else
                  [math.log({"shots": {"F": .15,"D": .08}, "hits": {"F": .10,"D": .10},
                             "blocks": {"F": .035,"D": .09}}[data["market"]][p]) for p in data["positions"]])
    with pm.Model() as model:
        pop_work = pm.Normal("population_workload", workload_prior, .6, shape=npos)
        pop_rate = pm.Normal("population_log_rate", rate_prior, .5, shape=npos)
        chol, _, _ = pm.LKJCholeskyCov("player_chol", n=2, eta=3,
                          sd_dist=pm.HalfNormal.dist(.4, shape=2), compute_corr=True)
        z = pm.Normal("player_z", 0., 1., shape=(n, 2))
        person = pm.Deterministic("player_effect", pt.dot(z, chol.T))
        # Separate shot generation (opponent) and shot suppression (own team).
        # For skaters these are own-team production and opponent allowance.
        team_sd = pm.HalfNormal("team_sd", .2, shape=2)
        team_z = pm.Normal("team_z", 0., 1., shape=(nteam, 2))
        team = pm.Deterministic("team_effect", (team_z - pt.mean(team_z, axis=0)) * team_sd)
        if ns > 1:
            season_sd = pm.HalfNormal("season_sd", .15, shape=2)
            season_z = pm.Normal("season_z", 0., 1., shape=(ns, 2))
            season = pm.Deterministic("season_effect", (season_z-pt.mean(season_z, axis=0))*season_sd)
        else:
            season = pm.Deterministic("season_effect", pt.zeros((1, 2)))
        bw = pm.Normal("beta_workload", 0., .2, shape=3)
        bv = pm.Normal("beta_volume", 0., .25, shape=nc)
        work_sigma = pm.HalfNormal("workload_sigma", 1.)
        work_mu = pop_work[pos] + person[ix, 0] + season[si, 0] + pt.dot(x[:, :3], bw)
        pm.Normal("observed_logit_workload", work_mu, work_sigma, observed=logit_share)
        if saves:
            team_volume = team[oi, 0] + team[ti, 1]
            individual_rate = 0.
        else:
            team_volume = team[ti, 0] + team[oi, 1]
            individual_rate = person[ix, 1]
        log_rate = pop_rate[pos] + individual_rate + team_volume + season[si, 1] + pt.dot(x[:, :nc], bv)
        alpha = pm.Gamma("volume_dispersion", alpha=3., beta=.1)
        mu = exposure * pt.exp(log_rate)
        if saves:
            # Shots and saves have ONE factorized likelihood. Adding a second
            # likelihood for team SOG here would count the same shots twice.
            pm.NegativeBinomial("observed_shots_faced", mu=mu, alpha=alpha,
                                observed=np.asarray(data["shots_against"]))
            pop_save = pm.Normal("population_logit_save", math.log(.91/.09), .35)
            save_eta = pop_save + person[ix, 1]
            if data["feature_set"] == "xg":
                bq = pm.Normal("beta_quality", -.2, .3, shape=2)
                save_eta += pt.dot(x[:, -2:], bq)
            probability = pm.math.sigmoid(save_eta)
            concentration = pm.Gamma("save_concentration", alpha=4., beta=.02)
            pm.BetaBinomial("observed_saves", n=np.asarray(data["shots_against"]),
                            alpha=probability*concentration, beta=(1-probability)*concentration,
                            observed=np.asarray(data["target"]))
        else:
            pm.NegativeBinomial("observed_volume", mu=mu, alpha=alpha,
                                observed=np.asarray(data["target"]))
    return model


def fit(data, *, draws=1500, tune=1500, chains=4, cores=2, seed=20261030, progressbar=True):
    if not 1 <= cores <= chains <= 8 or min(draws, tune) < 20:
        raise ValueError("invalid_context_sampling_budget")
    import pymc as pm
    model = build(data)
    with model:
        idata = pm.sample(draws=draws, tune=tune, chains=chains, cores=cores,
                          random_seed=seed, progressbar=progressbar,
                          nuts={"target_accept": .97, "max_treedepth": 12},
                          return_inferencedata=True)
    idata.posterior.attrs.update(model_version=VERSION, source_digest=data["source_digest"],
                                 stochastic_variables=store.encode([v.name for v in model.free_RVs]),
                                 market=data["market"], feature_set=data["feature_set"])
    return idata


def diagnostics(idata):
    """Every stochastic coefficient/effect, bulk+tail ESS, energy and tree depth."""
    import json
    import numpy as np
    try:
        from arviz_stats import rhat, ess
        keys = json.loads(idata.posterior.attrs["stochastic_variables"])
        if not keys or any(k not in idata.posterior for k in keys):
            raise ValueError("missing_stochastic_diagnostic_variables")
        posterior = idata.posterior.to_dataset() if hasattr(idata.posterior,"to_dataset") else idata.posterior
        ds = posterior[keys]
        # Also check the actual derived player/team effects and LKJ correlation
        # that forecasts use. Do not include identically-one correlation
        # diagonals or the pinned single-season zero effect.
        for name in ("player_effect","team_effect","opponent_rate","player_chol_stds"):
            if name in posterior:
                ds[name]=posterior[name]
                keys.append(name)
        if "season_sd" in posterior:
            ds["season_effect"]=posterior["season_effect"]
            keys.append("season_effect")
        if "season_rate_sd" in posterior:
            for name in ("season_workload","season_rate"):
                ds[name]=posterior[name]
                keys.append(name)
        corr=posterior["player_chol_corr"]
        ds["estimated_player_correlation"]=corr.isel({corr.dims[-2]:0,corr.dims[-1]:1},drop=True)
        keys.append("estimated_player_correlation")
        rs = _diagnostic_values(rhat(ds))
        bulk = _diagnostic_values(ess(ds, method="bulk"))
        tail = _diagnostic_values(ess(ds, method="tail"))
        energy = np.asarray(idata.sample_stats["energy"], dtype=float)
        bfmi = np.mean(np.diff(energy, axis=1)**2, axis=1)/np.var(energy, axis=1)
        if not np.isfinite(bfmi).all():
            raise ValueError("nonfinite_energy_diagnostics")
        divergences = int(np.asarray(idata.sample_stats["diverging"]).sum())
        depth_hits = int((np.asarray(idata.sample_stats["tree_depth"]) >= 12).sum())
        chains = int(idata.posterior.sizes["chain"])
        result = {"max_rhat": max(rs), "min_bulk_ess": min(bulk), "min_tail_ess": min(tail),
                  "minimum_bfmi": float(bfmi.min()), "divergences": divergences,
                  "max_treedepth_hits": depth_hits, "chains": chains, "all_stochastic_effects": True,
                  "checked_variables": keys}
        passed = (chains >= 4 and max(rs) <= 1.01 and min(bulk) >= 400 and min(tail) >= 400
                  and bfmi.min() >= .30 and divergences == 0 and depth_hits == 0)
        return {**result, "posterior_sampling_ok": bool(passed), "ranking_allowed": False,
                "status": "sampling_diagnostics_pass" if passed else "sampling_diagnostics_failed"}
    except (KeyError, ValueError, ImportError, TypeError, AttributeError, NotImplementedError) as exc:
        return {"status": "diagnostics_unavailable", "error": str(exc)[:200],
                "posterior_sampling_ok": False, "ranking_allowed": False}


def posterior_cache(idata, data):
    import numpy as np
    if idata.posterior.attrs.get("source_digest") != data["source_digest"] or idata.posterior.attrs.get("model_version") != VERSION:
        raise ValueError("posterior_design_provenance_mismatch")
    count = int(idata.posterior.sizes["chain"])*int(idata.posterior.sizes["draw"])
    keys = ["population_workload", "population_log_rate", "player_effect", "team_effect", "season_effect",
            "beta_workload", "beta_volume", "workload_sigma", "volume_dispersion"]
    if len(data["seasons"]) > 1:
        keys += ["season_sd"]
    if data["market"] == "saves":
        keys += ["population_logit_save", "save_concentration"]
    if data["feature_set"] == "xg":
        keys += ["beta_quality"]
    arrays = {}
    for key in keys:
        raw = np.asarray(idata.posterior[key], dtype=float)
        arrays[key] = raw.reshape((count,)+raw.shape[2:])
        if not np.isfinite(arrays[key]).all():
            raise ValueError("nonfinite_context_posterior:" + key)
    return {"count": count, "arrays": arrays, "source_digest": data["source_digest"]}


def forecast(idata, data, *, matchup, player_id, features, line, diagnostic,
             draws=4000, seed=1847, cache=None, observed_value=None):
    """Distribution conditional on appearance/start, never starter-probability weighted.

    For saves, conditional NB/binomial thinning is exact: given a draw of save
    probability p, saves ~ NB(mu_shots*p, alpha). Integrate that count CDF and
    marginalize workload, game length and beta-distributed game save ability.
    """
    if diagnostic.get("posterior_sampling_ok") is not True:
        raise ValueError("context_posterior_not_converged")
    if isinstance(line, bool) or not isinstance(line, (int, float)) or not math.isfinite(line) or line < 0:
        raise ValueError("invalid_context_prop_line")
    if not isinstance(draws, int) or isinstance(draws, bool) or not 100 <= draws <= 100000:
        raise ValueError("invalid_predictive_budget")
    if store.instant(matchup["start_time"]) < store.instant(data["cutoff_exclusive"]):
        raise ValueError("forecast_precedes_training_cutoff")
    if features["computed_before"] != matchup["start_time"] or features["names"] != data["feature_names"] or features["availability_policy"] != data["availability_policy"]:
        raise ValueError("forecast_feature_contract_mismatch")
    if not isinstance(matchup["home"], bool) or matchup["team"] == matchup["opponent"]:
        raise ValueError("invalid_forecast_matchup")
    player_id = str(player_id)
    if player_id not in data["players"] or any(matchup[k] not in data["teams"] for k in ("team", "opponent")):
        raise ValueError("unseen_entity_requires_verified_population_mapping")
    identity={"game_id":matchup["game_id"],"player_id":player_id,"team":matchup["team"],
              "opponent":matchup["opponent"],"home":matchup["home"],
              "position":data["positions"][data["player_position"][player_id]]}
    if features.get("identity") != identity:
        raise ValueError("forecast_feature_identity_mismatch")
    import numpy as np
    from scipy.special import expit
    from scipy.stats import nbinom
    cache = posterior_cache(idata, data) if cache is None else cache
    if cache["source_digest"] != data["source_digest"]:
        raise ValueError("posterior_cache_provenance_mismatch")
    rng = np.random.default_rng(seed)
    # Keep chain/draw pairing intact across ALL posterior parameters.
    pick = rng.integers(0, cache["count"], size=draws)
    a = {k: v[pick] for k, v in cache["arrays"].items()}
    x = (np.asarray(features["values"])-data["center"])/data["scale"]
    if not np.isfinite(x).all():
        raise ValueError("nonfinite_forecast_features")
    pi = data["players"].index(player_id)
    pos = data["player_position"][player_id]
    ti, oi = (data["teams"].index(matchup[k]) for k in ("team", "opponent"))
    if matchup["season"] in data["seasons"]:
        season = a["season_effect"][:, data["seasons"].index(matchup["season"])]
    elif len(data["seasons"]) > 1:
        season = rng.normal(0., a["season_sd"])
    else:
        raise ValueError("unseen_season_requires_multiseason_training")
    work = (a["population_workload"][:, pos] + a["player_effect"][:, pi, 0] + season[:, 0]
            + np.sum(a["beta_workload"]*x[:3], axis=1))
    duration = rng.choice([length for _, length in data["training_game_durations"]], size=draws)
    # Invert the same continuity-corrected transform used in training.
    played = np.clip(expit(rng.normal(work, a["workload_sigma"]))*(duration+.1)-.05, .01, duration)
    saves = data["market"] == "saves"
    team_rate = a["team_effect"][:, oi, 0] + a["team_effect"][:, ti, 1] if saves else (
                a["team_effect"][:, ti, 0] + a["team_effect"][:, oi, 1])
    rate = a["population_log_rate"][:, pos] + team_rate + season[:, 1]
    if not saves:
        rate += a["player_effect"][:, pi, 1]
    rate += np.sum(a["beta_volume"] * x[:a["beta_volume"].shape[1]], axis=1)
    mu = played*np.exp(rate)
    shots_mu = mu.copy()
    if saves:
        eta = a["population_logit_save"] + a["player_effect"][:, pi, 1]
        if data["feature_set"] == "xg":
            eta += np.sum(a["beta_quality"]*x[-2:], axis=1)
        mean_save = expit(eta)
        probability = rng.beta(mean_save*a["save_concentration"], (1-mean_save)*a["save_concentration"])
        mu *= probability
    alpha = a["volume_dispersion"]
    if not np.isfinite(mu).all() or np.any(mu <= 0) or np.any(alpha <= 0):
        raise ValueError("invalid_context_predictive_likelihood")
    p = alpha/(alpha+mu)
    threshold = math.floor(line)
    over = nbinom.sf(threshold, alpha, p)
    under = nbinom.cdf(threshold-1 if float(line).is_integer() else threshold, alpha, p)
    push = nbinom.pmf(threshold, alpha, p) if float(line).is_integer() else np.zeros(draws)
    if not np.isfinite(np.concatenate([over, under, push])).all():
        raise ValueError("nonfinite_context_probabilities")
    # The interval is uncertainty in conditional over probability, not a
    # calibrated confidence band and not the predictive outcome interval.
    outcome = nbinom.rvs(alpha, p, random_state=rng)
    qover, qunder, qpush = float(over.mean()), float(under.mean()), float(push.mean())
    log_density = None
    if observed_value is not None:
        store.count(observed_value)
        from scipy.special import logsumexp
        log_density = float(logsumexp(nbinom.logpmf(observed_value, alpha, p))-math.log(draws))
    return {"schema": "nhl-context-forecast-v1", "model_version": VERSION, "market": data["market"],
            "player_id": player_id, "game_id": matchup["game_id"], "line": line,
            "q_over": qover, "q_under": qunder, "q_push": qpush,
            "q_over_given_no_push": qover/(qover+qunder),
            "expected_value": float(mu.mean()), "expected_minutes": float(played.mean()),
            "expected_shots_faced": float(shots_mu.mean()) if saves else None,
            "log_predictive_density": log_density,
            "predictive_interval_90": np.quantile(outcome, [.05,.95]).tolist(),
            "conditional_probability_interval_90": np.quantile(over, [.05,.95]).tolist(),
            "integration_mc_se": float(over.std(ddof=1)/math.sqrt(draws)),
            "integration_mc_se_is_mcmc_ess_adjusted": False,
            "conditional_on": "starting" if saves else "appearance", "draws": draws,
            "availability_policy": data["availability_policy"], "source_digest": data["source_digest"],
            "training_cutoff_exclusive": data["cutoff_exclusive"],
            "status": "research_challenger", "ranking_allowed": False, "calibrated": False}
