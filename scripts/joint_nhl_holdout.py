#!/usr/bin/env python3
"""Frozen-parameter NHL heldout evaluation; no sportsbook-line reconstruction."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import mean

import historical_nhl_warehouse as wh
import joint_nhl_bayes as joint


def poisson_control(training, *, player, position):
    own=[r["shots"] for r in training if r["player_id"]==player]
    peers=[r["shots"] for r in training if r["position"]==position]
    if not peers:
        raise ValueError("missing_historical_poisson_position")
    center=mean(peers)
    # Transparent Gamma-Poisson partial-pooling control: equivalent 5 games.
    alpha=5*max(.02,center)+sum(own)
    beta=5+len(own)
    p0=(beta/(beta+1))**alpha
    p1=p0*alpha/(beta+1)
    p2=p1*(alpha+1)/(2*(beta+1))
    return max(0,min(1,1-p0-p1-p2))


def _metrics(rows):
    if not rows:
        return {"n":0,"log_loss":None,"brier":None}
    return {"n":len(rows),
            "log_loss":mean(-math.log(max(1e-12,min(1-1e-12,p if y else 1-p))) for p,y in rows),
            "brier":mean((p-y)**2 for p,y in rows)}


def paired_date_bootstrap(paired, *, repeats=2000, seed=1801):
    """Date-clustered paired proper-score differences on matched observations.

    Estimates from fewer than twenty dates are explicitly exploratory. Never
    interpret this resampling as prospective calibration or model approval.
    """
    by_date=defaultdict(list)
    for predicted,control,label,day in paired:
        def logloss(p):
            prob=p if label else 1-p
            return -math.log(max(1e-12,min(1-1e-12,prob)))
        by_date[day].append(((predicted-label)**2-(control-label)**2,
                             logloss(predicted)-logloss(control)))
    days=sorted(by_date)
    if not days:
        return {"n_dates":0,"n_observations":0,"status":"no_paired_evidence",
                "brier_delta_ci95":None,"log_loss_delta_ci95":None}
    if repeats<100:
        raise ValueError("insufficient_cluster_bootstrap_replicates")
    rng=random.Random(seed)
    samples=[[],[]]
    for _ in range(repeats):
        pairs=[v for day in rng.choices(days,k=len(days)) for v in by_date[day]]
        samples[0].append(mean(x[0] for x in pairs))
        samples[1].append(mean(x[1] for x in pairs))
    intervals=[]
    for series in samples:
        sorted_values=sorted(series)
        intervals.append([sorted_values[int((repeats-1)*.025)],
                          sorted_values[int((repeats-1)*.975)]])
    return {"n_dates":len(days),
            "n_observations":sum(map(len,by_date.values())),
            "status":"exploratory_insufficient_dates" if len(days)<20 else "descriptive_date_cluster_bootstrap",
            "brier_delta_ci95":intervals[0],"log_loss_delta_ci95":intervals[1],
            "label":"challenger minus same-cohort control; negative favors challenger",
            "approved_for_model_promotion":False}


def evaluate(idata, training, design, observed, *, cutoff, until,
             diagnostics, draws=1200, max_games=5000):
    date.fromisoformat(cutoff);date.fromisoformat(until)
    if not cutoff<until:
        raise ValueError("invalid_holdout_period")
    if diagnostics.get("posterior_sampling_ok") is not True:
        raise ValueError("posterior_diagnostics_failed")
    train_ids={(r["game_id"],r["player_id"]) for r in training}
    candidate=[r for r in observed if cutoff<=r["game_date"]<until]
    if any((r["game_id"],r["player_id"]) in train_ids for r in candidate):
        raise ValueError("training_holdout_data_overlap")
    candidates=sorted(candidate,key=lambda r:(r["game_date"],r["game_id"],r["player_id"]))
    if len(candidates)>max_games:
        raise ValueError("holdout_game_budget_exceeded_use_smaller_dates")
    skipped=defaultdict(int);paired=[];bins=defaultdict(list)
    position_pairs=defaultdict(list);scored=[]
    allowed_players=dataset_player_ids(training)
    allowed_opponents=dataset_model_opponents(training)
    # Build the frozen posterior lookup once instead of converting every
    # xarray variable for every held-out player-game.
    frozen_cache=joint.predictive_cache(idata)
    for row in candidates:
        if row["player_id"] not in allowed_players:
            skipped["unseen_player"]+=1;continue
        if row["opponent"] not in allowed_opponents:
            skipped["unseen_opponent"]+=1;continue
        seed=int.from_bytes(hashlib.sha256(
            (joint.VERSION+"|"+row["game_id"]+"|"+row["player_id"]).encode()).digest()[:8],"big")
        result=joint.forecast(idata,design,player_id=row["player_id"],
            opponent=row["opponent"],season=row["season"],home=bool(row["home"]),
            line=2.5,draws=draws,seed=seed,fit_diagnostics=diagnostics,
            posterior_cache=frozen_cache)
        p=result["q_over"]
        baseline=poisson_control(training,player=row["player_id"],position=row["position"])
        label=int(row["shots"]>=3)
        paired.append((p,baseline,label,row["game_date"]))
        position_pairs[row["position"]].append((p,baseline,label,row["game_date"]))
        scored.append({"game_date":row["game_date"],"game_id":row["game_id"],
            "player_id":row["player_id"],"position":row["position"],
            "source_sha256":row["source_sha256"],
            "observed_shots":row["shots"],"actual_over_2_5":label,
            "bayesian_q_over":p,"control_q_over":baseline,
            "numerical_mc_se":result.get("mc_standard_error_q_over")})
        bins[int(p*10) if p<1 else 9].append((p,label))
    model=_metrics([(p,y) for p,b,y,d in paired])
    control=_metrics([(b,y) for p,b,y,d in paired])
    reliability=[{"bin":f"{i/10:.1f}-{(i+1)/10:.1f}",
                  "n":len(items),"mean_predicted":mean(v[0] for v in items),
                  "actual_over_rate":mean(v[1] for v in items)}
                 for i,items in sorted(bins.items())]
    day_count=len(set(v[3] for v in paired))
    sufficient=len(paired)>=200 and day_count>=20
    return {"schema":"nhl_joint_frozen_holdout_v1",
        "model_version":joint.VERSION,
        "training_last_game":max(r["game_date"] for r in training),
        "holdout_cutoff":cutoff,"holdout_end_exclusive":until,
        "event":"skater records conditional on playing",
        "stat":"shots on goal","fixed_evaluation_line":2.5,
        "historical_sportsbook_line_claim":False,
        "posterior_diagnostic_status":diagnostics["status"],
        "sampled_posterior":model,
        "gamma_poisson_control":control,
        "paired_mean_log_loss_delta":(model["log_loss"]-control["log_loss"]) if paired else None,
        "paired_mean_brier_delta":(model["brier"]-control["brier"]) if paired else None,
        "paired_by_game_date":paired_date_bootstrap(paired),
        "by_position":{
            pos:{"n":len(rows),
                 "sampled_posterior":_metrics([(p,y) for p,b,y,d in rows]),
                 "gamma_poisson_control":_metrics([(b,y) for p,b,y,d in rows]),
                 "paired_date_bootstrap":paired_date_bootstrap(rows,seed=1801+(pos=="D"))}
            for pos,rows in sorted(position_pairs.items())},
        "scored_observations":scored,
        "n_holdout_game_dates":day_count,
        "model_covered_rows":len(paired),"all_holdout_rows":len(candidates),
        "excluded":dict(skipped),
        "reliability":reliability,
        "status":"descriptive_holdout" if sufficient else "underpowered_holdout",
        "calibrated_for_production":False,"publication_eligible":False,
        "rankings_changed":False}


def dataset_player_ids(rows):
    return {r["player_id"] for r in rows}


def dataset_model_opponents(rows):
    return {r["opponent"] for r in rows}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,default=wh.ROOT)
    p.add_argument("--cutoff",required=True)
    p.add_argument("--until",required=True)
    p.add_argument("--training-dir",type=Path,default=Path("reports/joint_nhl"))
    p.add_argument("--draws",type=int,default=1200)
    p.add_argument("--max-per-position",type=int,default=0)
    p.add_argument("--max-games",type=int,default=5000)
    args=p.parse_args(argv)
    import arviz as az
    idata=az.from_netcdf(args.training_dir/"posterior.nc")
    meta=json.loads((args.training_dir/"manifest.json").read_text())
    if meta.get("training_cutoff_exclusive")!=args.cutoff:
        raise ValueError("training_manifest_cutoff_mismatch")
    training=wh.read_history(args.root,before=args.cutoff,max_seasons=8)
    if args.max_per_position!=meta.get("max_per_position",0):
        raise ValueError("heldout_player_subset_must_match_frozen_fit")
    training=joint.subset_training_players(training,max_per_position=args.max_per_position)
    data=joint.prepare(training)
    if meta.get("source_digest")!=data["source_digest"]:
        raise ValueError("training_manifest_history_changed")
    # Read only later observed games; they were unseen during NUTS fitting.
    future=wh.read_history(args.root,before=args.until)
    report=evaluate(idata,training,data,future,cutoff=args.cutoff,until=args.until,
                    diagnostics=meta["diagnostics"],draws=args.draws,
                    max_games=args.max_games)
    out=args.training_dir/"holdout_validation.json"
    out.write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+"\n")
    print(json.dumps({k:v for k,v in report.items()
                      if k not in ("reliability","scored_observations")},sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
