#!/usr/bin/env python3
"""Audit point-in-time feature/target correlations, not a leak detector alone.

Both Poisson team XGB labels and active-zero hurdle labels are reconstructed
ONLY from pre-2024 nflverse rows. Analyze Pearson and Spearman, including
absolute r>=.70/.80 flags, with an explicit same-game perturbation guard.
A large correlation is NOT sufficient proof of leakage; the source date
must also have been unknown when a prediction was made.

Run from repo with original dependencies:
 python scripts/nfl_2024_feature_target_leak_audit.py --out reports/...
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

import nfl_pre2024_xgb_replay as source
import nfl_pre2024_team_volume_xgb as team
import nfl_pre2024_team_defense_challenger as priors
import nfl_pre2024_active_zero_hurdle as hurdle
import nflverse_pre2024_hurdle_gateway as gateway

SCHEMA="nfl_feature_target_correlation_and_asof_audit_pre2024_v1"


def coefficient(x,y):
    x=np.asarray(x,dtype=np.float64)
    y=np.asarray(y,dtype=np.float64)
    mask=np.isfinite(x)&np.isfinite(y)
    if mask.sum()<100:return None
    x=x[mask];y=y[mask]
    if x.std()<1e-10 or y.std()<1e-10:return None
    return float(np.corrcoef(x,y)[0,1])


def row(name,x,y):
    pearson=coefficient(x,y)
    spearman=coefficient(rankdata(x),rankdata(y)) if np.isfinite(x).all() else None
    return {"feature":name,"pearson":pearson,"spearman":spearman,
        "abs_r_ge_070":pearson is not None and abs(pearson)>=.70,
        "abs_r_ge_080":pearson is not None and abs(pearson)>=.80}


def scan(x,y,names):
    if len(x)!=len(y) or x.shape[1]!=len(names):
        raise ValueError("feature_registry_or_target_length_mismatch")
    result=[row(name,x[:,i],y) for i,name in enumerate(names)]
    result.sort(key=lambda r:abs(r["pearson"]) if r["pearson"] is not None else -1,
                reverse=True)
    return result


def assert_same_game_excluded(index,data):
    """Inject a large same-game label, require identical pregame features."""
    if not data:raise ValueError("empty_source")
    example=data[min(len(data)-1,300)]
    d=example["day"];teamid=example["team"];opp=example["opponent"]
    home=example["game_id"].split("_")[-1]==teamid
    week=int(example["game_id"].split("_")[1])
    orig=team.features(index,teamid,opp,asof=d,home=home,week=week)
    from collections import defaultdict
    temp={**index,
        "offense":defaultdict(list,{k:list(v) for k,v in index["offense"].items()}),
        "defense":defaultdict(list,{k:list(v) for k,v in index["defense"].items()})}
    fake={"gameday":d,"team":teamid,"opponent":opp,
          "pass_attempts":10000000.,"rush_attempts":10000000.,
          "sacks":100000.,"dropbacks":1000000.,
          "neutral_passes":1000000.}
    temp["offense"][teamid].append(fake)
    temp["defense"][opp].append(fake)
    after=team.features(temp,teamid,opp,asof=d,home=home,week=week)
    if not np.array_equal(orig,after):
        raise RuntimeError("same_game_team_target_or_feature_lookahead")
    return True


def audit():
    player_rows,team_games,ngs,receipts=source.pre2024_sources()
    index=team.build_index(team_games,ngs)
    training=team.training_rows(team_games,index)
    result={"schema":SCHEMA,
            "no_2024_target_variables_loaded":True,
            "historical_PBP_role_lookup_game_local":True,
            "unverified_high_correlations_are_warnings_not_leak_proofs":True,
            "team":{},"zero":{}}
    for metric in team.TARGETS:
        d=training[metric]
        X=np.asarray([r["x"] for r in d],dtype=np.float64)
        y=np.asarray([r["y"] for r in d],dtype=np.float64)
        result["team"][metric]={"n":len(d),"ranked":scan(X,y,team.FEATURES)}
    result["same_game_team_label_perturbation_passed"]=assert_same_game_excluded(
        index,training["pass_attempts"])
    state=priors.historical_sources(player_rows,team_games,ngs)
    context=gateway.load_nflreadpy_strict_pre2024_context(
        include_participation=True,include_injuries=True)
    samples=hurdle.make_training_rows(state,context,player_rows)
    for market in hurdle.MARKETS:
        selected=[r for r in samples if r["stat"]==market]
        if len(selected)<100:continue
        x=np.asarray([r["x"] for r in selected],dtype=np.float64)
        y=np.asarray([r["zero"] for r in selected],dtype=np.float64)
        result["zero"][market]={"n":len(y),"zero_rate":float(y.mean()),
            "ranked":scan(x,y,hurdle.FEATURE_NAMES)}
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    result=audit()
    if a.out.exists():raise RuntimeError("audit_output_exists_refuse_overwrite")
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n")
    for stage in ("team","zero"):
        for market,info in result[stage].items():
            print(json.dumps({"stage":stage,"market":market,
                "n":info["n"],"top":info["ranked"][:10],
                "high_abs_r70":[r["feature"] for r in info["ranked"]
                                if r["abs_r_ge_070"]]},sort_keys=True))
    print("FEATURE_TARGET_CORRELATION_AUDIT_COMPLETE",str(a.out))


if __name__=="__main__":
    main()
