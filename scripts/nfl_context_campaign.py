#!/usr/bin/env python3
"""Local NFL context/base/incumbent campaign. No Actions or ranking writes."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import platform
import sys
import time
import zipfile
from datetime import datetime,timezone
from pathlib import Path

import nfl_context_data as data
import nhl_context_data as common
import nhl_context_train as io
from nhl_context_campaign import Campaign,campaign_lock
from nhl_context_features import pilot_cohort

ROOT=Path(__file__).resolve().parents[1]


def validate(c):
    required={"schema","seasons","train_from","cutoff","until","pilot_games","market","line",
              "draws","tune","chains","cores","predictive_draws"}
    if set(c)!=required or c["schema"]!="nfl-context-campaign-v1":raise ValueError("invalid_nfl_configuration")
    if not common.instant(c["train_from"])<common.instant(c["cutoff"])<common.instant(c["until"])<=datetime.now(timezone.utc):
        raise ValueError("invalid_nfl_campaign_dates")
    if c["market"] not in data.MARKETS:raise ValueError("unsupported_nfl_count_market")
    if (not isinstance(c["seasons"],list) or len(set(c["seasons"]))!=len(c["seasons"]) or
        len(c["seasons"])<3 or any(isinstance(s,bool) or not isinstance(s,int) or not 2018<=s<=2100 for s in c["seasons"])):
        raise ValueError("nfl_requires_two_training_seasons_plus_holdout")
    for name,lo,hi in (("draws",100,10000),("tune",100,10000),("chains",4,8),("cores",1,8),
                       ("predictive_draws",100,100000),("pilot_games",0,10000)):
        if isinstance(c[name],bool) or not isinstance(c[name],int) or not lo<=c[name]<=hi:
            raise ValueError("invalid_nfl_budget:"+name)
    if c["cores"]>c["chains"] or c["pilot_games"]==1:raise ValueError("invalid_nfl_sampling_parallelism")
    import math
    if isinstance(c["line"],bool) or not isinstance(c["line"],(int,float)) or not math.isfinite(c["line"]) or c["line"]<0:
        raise ValueError("invalid_nfl_research_line")
    return c


def freeze(folder,c,bundles):
    folder=Path(folder)
    context=data.examples(bundles,c["market"],context=True)
    base=data.examples(bundles,c["market"],context=False)
    start,end=(common.instant(c[k]) for k in ("train_from","cutoff"))
    training=[r for r in context if start<=common.instant(r["start_time"])<end and common.instant(r["available_at"])<end]
    training=pilot_cohort(training,c["pilot_games"])
    keys={(r["game_id"],r["player_id"]) for r in training}
    basetrain=[r for r in base if (r["game_id"],r["player_id"]) in keys]
    design=data.prepare(training,c["cutoff"]);basedesign=data.prepare(basetrain,c["cutoff"])
    if keys!={(r["game_id"],r["player_id"]) for r in basetrain}:raise ValueError("nfl_ablation_cohort_mismatch")
    eligible=[r for r in context if end<=common.instant(r["start_time"])<common.instant(c["until"]) and
              common.instant(r["available_at"])<common.instant(c["until"])]
    # Both models must be able to predict the same entity identities. Unseen
    # appearances are reported, not assigned fabricated individual effects.
    scored=[];excluded=[]
    for r in eligible:
        if r["player_id"] not in design["players"] or any(r[k] not in design["teams"] for k in ("team","opponent")):
            excluded.append({"game_id":r["game_id"],"player_id":r["player_id"],"reason":"unseen_entity"})
        elif r["position"]!=design["player_position"][r["player_id"]]:
            excluded.append({"game_id":r["game_id"],"player_id":r["player_id"],"reason":"position_changed"})
        else:scored.append(r)
    if len(scored)<30:raise ValueError("insufficient_nfl_common_holdout_rows")
    holdkeys={(r["game_id"],r["player_id"]) for r in scored}
    basehold=[r for r in base if (r["game_id"],r["player_id"]) in holdkeys]
    report={"schema":"nfl-context-preflight-v1","market":c["market"],"training_rows":len(training),
            "training_games":len({r["game_id"] for r in training}),"players":len(design["players"]),
            "teams":len(design["teams"]),"training_seasons":design["seasons"],"holdout_rows":len(scored),
            "eligible_holdout_rows":len(eligible),"excluded_holdout":excluded,
            "source_coverage":[{"season":b["season"],"schedule_games":b["completed_schedule_games"],
                                "joins":b["coverage"],"stat_discrepancies":b["excluded"]} for b in bundles],
            "availability_policy":"retrospective_start_plus_18h","line_type":"fixed_research_threshold",
            "frozen_digest":common.digest(bundles),"design_digest":common.digest(design),
            "base_design_digest":common.digest(basedesign),"ranking_allowed":False}
    for name,value in (("context_design",design),("base_design",basedesign),("training_rows",training),
                       ("base_training_rows",basetrain),("holdout_rows",scored),("base_holdout_rows",basehold),
                       ("frozen_bundles",bundles),("preflight",report)):
        io.write_json(folder/(name+".json"),value)
    # Bind EVERY frozen input to a content hash; fits/evaluation recheck them.
    io.write_json(folder/"frozen_hashes.json",{p.name:io.file_hash(p) for p in sorted(folder.glob("*.json"))})
    return report


def verify_frozen(folder):
    folder=Path(folder)
    for name,h in io.load_json(folder/"frozen_hashes.json").items():
        if io.file_hash(folder/name)!=h:raise ValueError("nfl_frozen_input_changed:"+name)


def fit(folder,kind,c):
    import nfl_context_model as model
    import joint_population_bayes as legacy
    import pymc as pm
    verify_frozen(folder);folder=Path(folder);out=folder.parent/kind
    if out.exists():raise ValueError("nfl_fit_output_exists_choose_new_run_directory")
    d=io.load_json(folder/("base_design.json" if kind=="base" else "context_design.json"))
    began=time.monotonic()
    if kind=="incumbent":
        rows=io.load_json(folder/"training_rows.json")
        d=legacy.prepare(rows,min_rows=200)
        graph=legacy.build(d)
        with graph:
            trace=pm.sample(draws=c["draws"],tune=c["tune"],chains=c["chains"],cores=c["cores"],
                            random_seed=20261030,progressbar=False,nuts={"target_accept":.97,"max_treedepth":12},
                            return_inferencedata=True)
        trace.posterior.attrs["stochastic_variables"]=common.encode([v.name for v in graph.free_RVs])
    else:
        trace=model.fit(d,**{k:c[k] for k in ("draws","tune","chains","cores")})
    diagnostic=model.diagnostics(trace)
    out.mkdir(parents=True);trace.to_netcdf(out/"posterior.nc");io.write_json(out/"design.json",d)
    manifest={"schema":"nfl-context-fit-v1","kind":kind,"elapsed_seconds":time.monotonic()-began,
              "diagnostics":diagnostic,"posterior_sha256":io.file_hash(out/"posterior.nc"),
              "design_sha256":io.file_hash(out/"design.json"),"frozen_hashes_sha256":io.file_hash(folder/"frozen_hashes.json"),
              "code_provenance":io.code_provenance(),
              "nfl_script_sha256":{p.name:io.file_hash(p) for p in sorted((ROOT/"scripts").glob("nfl_context_*.py"))},
              "ranking_allowed":False}
    io.write_json(out/"manifest.json",manifest)
    if not diagnostic["posterior_sampling_ok"]:raise ValueError("nfl_fit_failed_strict_diagnostics:"+kind)
    return manifest


def evaluate(folder,c):
    import arviz as az
    import nfl_context_model as model
    import joint_population_bayes as legacy
    from nhl_context_evaluate import paired_comparison,metrics
    folder=Path(folder);verify_frozen(folder);predictions={}
    rows=io.load_json(folder/"holdout_rows.json")
    for kind in ("context","base","incumbent"):
        out=folder.parent/kind;manifest=io.load_json(out/"manifest.json")
        if (manifest["posterior_sha256"]!=io.file_hash(out/"posterior.nc") or
            manifest["design_sha256"]!=io.file_hash(out/"design.json") or
            manifest["frozen_hashes_sha256"]!=io.file_hash(folder/"frozen_hashes.json")):
            raise ValueError("nfl_posterior_provenance_mismatch")
        trace=az.from_netcdf(out/"posterior.nc");diagnostic=model.diagnostics(trace)
        if not diagnostic["posterior_sampling_ok"]:raise ValueError("nfl_evaluation_requires_convergence:"+kind)
        d=io.load_json(out/"design.json");rs=io.load_json(folder/"base_holdout_rows.json") if kind=="base" else rows
        cache=legacy.posterior_cache(trace) if kind=="incumbent" else model.cache(trace,d)
        result=[]
        for row in rs:
            if kind=="incumbent":
                p=legacy.forecast(trace,d,player_id=row["player_id"],opponent=row["opponent"],season=row["season"],
                    home=row["home"],line=c["line"],draws=c["predictive_draws"],diagnostic=diagnostic,cache=cache,
                    seed=int(common.digest([row["game_id"],row["player_id"]])[:8],16))
                p={**{k:row[k] for k in ("game_id","player_id","start_time","target")},
                   **{k:p[k] for k in ("q_over","q_under","q_push")},"line":c["line"],
                   "market":c["market"],"training_cutoff_exclusive":c["cutoff"],"ranking_allowed":False}
            else:p=model.forecast(cache,d,row,line=c["line"],draws=c["predictive_draws"],diagnostic=diagnostic)
            result.append(p)
        predictions[kind]=result;io.write_json(out/"holdout_predictions.json",result)
    report={"schema":"nfl-context-comparison-v1","context_vs_incumbent":paired_comparison(predictions["context"],predictions["incumbent"]),
            "context_vs_base":paired_comparison(predictions["context"],predictions["base"]),
            "metrics":{k:metrics(v) for k,v in predictions.items()},"ranking_allowed":False,"automatic_promotion":False}
    io.write_json(folder.parent/"comparison.json",report)
    return report


class Runner(Campaign):
    def __init__(self,folder,c):
        self.root=ROOT;self.run=Path(folder).resolve();self.config=validate(c)
        self.run.mkdir(parents=True,exist_ok=True);self.status_path=self.run/"status.json"
        names=["nfl_context_campaign.py","nfl_context_data.py","nfl_context_model.py","population_nfl.py",
               "population_history.py","joint_population_bayes.py","nhl_context_campaign.py",
               "nhl_context_model.py","nhl_context_train.py","nhl_context_data.py","nhl_context_features.py",
               "nhl_context_evaluate.py"]
        source={n:io.file_hash(ROOT/"scripts"/n) for n in names}
        import importlib.metadata as meta
        runtime={n:meta.version(n) for n in ("pymc","numpy","scipy","arviz","arviz-stats","nflreadpy","pytensor","h5netcdf","h5py","polars","tzdata")}
        identity={"config_digest":common.digest(c),"code_digest":common.digest(source),
                  "runtime_digest":common.digest([platform.python_version(),runtime])}
        if self.status_path.exists():
            self.status=io.load_json(self.status_path)
            if any(self.status.get(k)!=v for k,v in identity.items()):
                raise ValueError("nfl_run_identity_changed_choose_new_run_directory")
        else:
            self.status={"schema":"nfl-context-status-v1",**identity,"steps":{},"ranking_allowed":False}
            io.write_json(self.run/"config.json",c);io.write_json(self.run/"code_receipt.json",source)
            io.write_json(self.run/"runtime_receipt.json",runtime);io.write_json(self.status_path,self.status)

    def execute(self):
        frozen=self.run/"frozen";c=self.config
        if not frozen.exists():
            bundles=data.collect(self.run/"source_cache",c["seasons"],c["until"])
        else:bundles=None
        outputs=[frozen/n for n in ("frozen_hashes.json","context_design.json","base_design.json","training_rows.json",
                 "base_training_rows.json","holdout_rows.json","base_holdout_rows.json","frozen_bundles.json","preflight.json")]
        self.step("freeze",lambda:freeze(frozen,c,bundles),outputs)
        verify_frozen(frozen)
        preflight=io.load_json(frozen/"preflight.json")
        compact={k:preflight[k] for k in ("market","training_rows","training_games","players","teams",
                                         "training_seasons","holdout_rows","eligible_holdout_rows")}
        compact["excluded_holdout_rows"]=len(preflight["excluded_holdout"])
        print("NFL_PREFLIGHT "+json.dumps(compact,sort_keys=True),flush=True)
        for kind in ("context","base","incumbent"):
            self.step("fit_"+kind,lambda k=kind:self.command("fit_"+k,"scripts/nfl_context_campaign.py","fit",
                      "--run-dir",self.run,"--kind",k),[self.run/kind/"manifest.json",self.run/kind/"posterior.nc",self.run/kind/"design.json"])
        predictions=[self.run/k/"holdout_predictions.json" for k in ("context","base","incumbent")]
        self.step("evaluate",lambda:self.command("evaluate","scripts/nfl_context_campaign.py","evaluate","--run-dir",self.run),
                  [self.run/"comparison.json",*predictions])
        # Includes frozen designs, rows, source/coverage receipts and predictions.
        # Bulky source snapshots and posteriors remain local; hashes identify them.
        with zipfile.ZipFile(self.run/"review_packet.zip","w",zipfile.ZIP_DEFLATED) as z:
            for p in sorted(self.run.rglob("*.json")):
                z.write(p,p.relative_to(self.run))
        print("REVIEW_PACKET="+str(self.run/"review_packet.zip"),flush=True)
        return io.load_json(self.run/"comparison.json")


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage",choices=("run","fit","evaluate","status"))
    p.add_argument("--config",type=Path,default=ROOT/"config/nfl_context_targets_pilot.json")
    p.add_argument("--run-dir",type=Path,default=ROOT/"reports/nfl_context_targets_pilot_v1")
    p.add_argument("--kind",choices=("context","base","incumbent"))
    a=p.parse_args(argv)
    for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"):os.environ[k]="1"
    os.environ["PYTHONUTF8"]="1";os.environ["PYTHONIOENCODING"]="utf-8"
    compiler=Path(r"C:\msys64\ucrt64\bin")
    if os.name=="nt" and compiler.is_dir():os.environ["PATH"]=str(compiler)+os.pathsep+os.environ.get("PATH","")
    if a.stage=="status":result=io.load_json(a.run_dir/"status.json")
    elif a.stage=="run":
        # Validate imports before creating runtime-pinned receipts or downloading.
        import pymc,arviz,arviz_stats,h5netcdf,h5py,nflreadpy,tzdata
        with campaign_lock(a.run_dir):result=Runner(a.run_dir,io.load_json(a.config)).execute()
    else:
        c=validate(io.load_json(a.run_dir/"config.json"))
        if a.stage=="fit":
            if a.kind is None:p.error("fit requires --kind")
            result=fit(a.run_dir/"frozen",a.kind,c)
        else:result=evaluate(a.run_dir/"frozen",c)
    print(json.dumps(result,sort_keys=True,allow_nan=False),flush=True)
    return 0


if __name__=="__main__":raise SystemExit(main())
