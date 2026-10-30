#!/usr/bin/env python3
"""Refit the existing hierarchical model on the exact challenger training rows.

This is a fair architecture comparison, not reuse of today's posterior on older
games. Fits are explicit/local, with the same all-effect diagnostic thresholds.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import nhl_context_data as store
import nhl_context_train as lifecycle


def legacy_rows(rows):
    import population_history as history
    stat = {"saves":"saves","shots":"shots on goal","hits":"hits","blocks":"blocked shots"}
    return [history.make(sport="NHL",stat=stat[r["market"]],game_id=r["game_id"],
             game_date=r["game_date"],season=r["season"],player_id=r["player_id"],
             position=r["position"],team=r["team"],opponent=r["opponent"],home=r["home"],
             value=r["target"],workload=r["minutes"],workload_unit="minutes",
             source_url=f"{store.BASE}/gamecenter/{r['game_id']}/boxscore",source_sha256=r["source_sha256"])
            for r in rows]


def fit(challenger_dir, output, *, draws=1500,tune=1500,chains=4,cores=2,seed=20261030):
    import joint_population_bayes as incumbent
    import nhl_context_model as challenger
    import pymc as pm
    design, preflight = lifecycle.load_design(challenger_dir)
    rows = lifecycle.load_json(Path(challenger_dir)/"training_rows.json")
    if store.digest(sorted(rows,key=lambda r:(r["start_time"],r["game_id"],r["player_id"]))) != design["source_digest"]:
        raise ValueError("challenger_training_rows_mismatch")
    if not 1<=cores<=chains<=8 or min(draws,tune)<20:
        raise ValueError("invalid_incumbent_sampling_budget")
    output=Path(output)
    if output.exists():
        raise ValueError("incumbent_output_exists_choose_new_experiment")
    legacy=incumbent.prepare(legacy_rows(rows),min_rows=200)
    graph=incumbent.build(legacy)
    with graph:
        trace=pm.sample(draws=draws,tune=tune,chains=chains,cores=cores,random_seed=seed,
                        nuts={"target_accept":.97,"max_treedepth":12},return_inferencedata=True)
    trace.posterior.attrs["stochastic_variables"]=store.encode([v.name for v in graph.free_RVs])
    quality=challenger.diagnostics(trace)
    output.mkdir(parents=True)
    trace.to_netcdf(output/"posterior.nc")
    lifecycle.write_json(output/"design.json",legacy)
    manifest={"schema":"nhl-context-incumbent-refit-v1","model_version":incumbent.VERSION,
              "challenger_training_digest":design["source_digest"],
              "challenger_design_digest":preflight["design_digest"],
              "cutoff_exclusive":design["cutoff_exclusive"],"diagnostics":quality,
              "legacy_design_digest":store.digest(legacy),
              "posterior_sha256":lifecycle.file_hash(output/"posterior.nc"),
              "draws":draws,"tune":tune,"chains":chains,"cores":cores,"seed":seed,
              "ranking_allowed":False,"code_provenance":lifecycle.code_provenance()}
    lifecycle.write_json(output/"manifest.json",manifest)
    return manifest


def score(challenger_dir, incumbent_dir):
    import arviz as az
    import joint_population_bayes as incumbent
    import nhl_context_model as challenger
    incumbent_dir=Path(incumbent_dir)
    design, preflight=lifecycle.load_design(challenger_dir)
    legacy=lifecycle.load_json(incumbent_dir/"design.json")
    manifest=lifecycle.load_json(incumbent_dir/"manifest.json")
    if (manifest["challenger_training_digest"]!=design["source_digest"]
            or manifest["challenger_design_digest"]!=preflight["design_digest"]
            or manifest["legacy_design_digest"]!=store.digest(legacy)
            or manifest["posterior_sha256"]!=lifecycle.file_hash(incumbent_dir/"posterior.nc")):
        raise ValueError("incumbent_challenger_provenance_mismatch")
    trace=az.from_netcdf(incumbent_dir/"posterior.nc")
    quality=challenger.diagnostics(trace)
    if quality.get("posterior_sampling_ok") is not True:
        raise ValueError("incumbent_all_effects_diagnostics_failed")
    cache=incumbent.posterior_cache(trace)
    expected=lifecycle.load_json(Path(challenger_dir)/"holdout_predictions.json")
    bundles=lifecycle.load_json(Path(challenger_dir)/"frozen_bundles.json")
    lookup={(r["game_id"],r["player_id"]):r for b in bundles for table in ("skaters","goalies") for r in b[table]}
    results=[]
    for prediction in expected:
        row=lookup[(prediction["game_id"],prediction["player_id"])]
        if store.instant(row["start_time"]) < store.instant(manifest["cutoff_exclusive"]):
            raise ValueError("incumbent_holdout_overlaps_training")
        probability=incumbent.forecast(trace,legacy,player_id=row["player_id"],opponent=row["opponent"],
                      season=row["season"],home=row["home"],line=prediction["line"],draws=4000,
                      seed=int(store.digest([row["game_id"],row["player_id"]])[:8],16),
                      diagnostic=quality,cache=cache)
        results.append({**{k:prediction[k] for k in ("game_id","player_id","market","line","target","start_time","training_cutoff_exclusive")},
                        **{k:probability[k] for k in ("q_over","q_under","q_push")},
                        "model_version":incumbent.VERSION,"ranking_allowed":False})
    lifecycle.write_json(incumbent_dir/"holdout_predictions.json",results)
    return {"predictions":len(results),"output":str(incumbent_dir/"holdout_predictions.json"),"ranking_allowed":False}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage",choices=("fit","score"))
    p.add_argument("--challenger-dir",type=Path,required=True)
    p.add_argument("--incumbent-dir",type=Path,required=True)
    p.add_argument("--draws",type=int,default=1500)
    p.add_argument("--tune",type=int,default=1500)
    p.add_argument("--chains",type=int,default=4)
    p.add_argument("--cores",type=int,default=2)
    a=p.parse_args(argv)
    result=(fit(a.challenger_dir,a.incumbent_dir,draws=a.draws,tune=a.tune,chains=a.chains,cores=a.cores)
            if a.stage=="fit" else score(a.challenger_dir,a.incumbent_dir))
    print(json.dumps(result,sort_keys=True,allow_nan=False))
    return 2 if a.stage=="fit" and not result["diagnostics"]["posterior_sampling_ok"] else 0


if __name__=="__main__":raise SystemExit(main())
