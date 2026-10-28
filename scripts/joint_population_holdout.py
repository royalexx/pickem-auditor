#!/usr/bin/env python3
"""Dated, same-population, per-stat shadow comparison of full joint posterior
versus a transparent historical control. No fabricated betting lines.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from collections import Counter,defaultdict
from datetime import date
from pathlib import Path
from statistics import mean
import population_history as history
import joint_population_bayes as joint
from joint_nhl_holdout import paired_date_bootstrap


def simple_control(training,*,player,position,stat_family,line):
    own=[r["value"] for r in training if r["player_id"]==player]
    peer=[r["value"] for r in training if r["position"]==position]
    if not peer:raise ValueError("missing_position_control_population")
    if stat_family=="count":
        # Gamma-Poisson (five equivalent population games).
        center=max(.02,mean(peer));alpha=5*center+sum(own)
        beta=5+len(own)
        from scipy.stats import nbinom
        return float(nbinom.sf(math.floor(line),alpha,beta/(beta+1)))
    import numpy as np
    from scipy.stats import t
    # Regularized Student-t location and scale for signed yardage.
    location=(5*mean(peer)+sum(own))/(5+len(own))
    sigma=float(np.std(peer,ddof=1)) if len(peer)>1 else 20.
    sigma=max(sigma,5.)
    return float(t.sf(line,df=4,loc=location,
                      scale=sigma*math.sqrt(1+1/(5+len(own)))))


def control_cache(training):
    """Historical source-owned summaries, never heldout values.

    Avoid rescanning multi-season player-game histories for each forecast:
    former naive O(training_rows * heldout_rows) becomes roughly linear.
    """
    players=defaultdict(lambda:[0,0.])
    positions=defaultdict(lambda:[0,0.,0.])
    for row in training:
        player=players[row["player_id"]]
        player[0]+=1
        player[1]+=row["value"]
        position=positions[row["position"]]
        position[0]+=1
        position[1]+=row["value"]
        position[2]+=row["value"]**2
    return {"players":dict(players),"positions":dict(positions)}


def cached_control(cache, *, player, position, stat_family, line):
    own_n,own_sum=cache["players"].get(player,(0,0.))
    if position not in cache["positions"]:
        raise ValueError("missing_position_control_population")
    peer_n,peer_sum,peer_sum_squares=cache["positions"][position]
    center=peer_sum/peer_n
    if stat_family=="count":
        from scipy.stats import nbinom
        alpha=5*max(.02,center)+own_sum
        beta=5+own_n
        return float(nbinom.sf(math.floor(line),alpha,beta/(beta+1)))
    if stat_family!="continuous":
        raise ValueError("unsupported_baseline_stat_family")
    import math as _math
    from scipy.stats import t
    location=(5*center+own_sum)/(5+own_n)
    sample_var=((peer_sum_squares-peer_sum*peer_sum/peer_n)/(peer_n-1)
                if peer_n>1 else 400.)
    sigma=max(_math.sqrt(max(0.,sample_var)),5.)
    return float(t.sf(line,df=4,loc=location,
                      scale=sigma*_math.sqrt(1+1/(5+own_n))))


def _scores(observations):
    if not observations:return {"n":0,"brier":None,"log_loss":None}
    return {"n":len(observations),
        "brier":mean((p-y)**2 for p,y in observations),
        "log_loss":mean(-(y*math.log(max(p,1e-12))+
                          (1-y)*math.log(max(1-p,1e-12))) for p,y in observations)}


def reliability(observations, *, probability_key, buckets=10):
    """Descriptive-only bin calibration; no postgame refitting."""
    values=defaultdict(list)
    for observation in observations:
        prob=observation[probability_key]
        observed=observation["actual_over"]
        if not math.isfinite(prob) or not 0<=prob<=1 or observed not in (0,1):
            raise ValueError("invalid_reliability_observation")
        index=min(buckets-1,int(prob*buckets))
        values[index].append((prob,observed))
    count=sum(len(x) for x in values.values())
    return {
        "n":count,
        "ece":(sum(len(items)/count*abs(mean(p for p,y in items)-
                        mean(y for p,y in items))
                   for items in values.values()) if count else None),
        "bins":[{"range":[i/buckets,(i+1)/buckets],
                 "n":len(items),"mean_probability":mean(p for p,y in items),
                 "observed_frequency":mean(y for p,y in items)}
                for i,items in sorted(values.items())],
        "status":"descriptive_only_not_calibrated"
    }


def position_slices(observations):
    groups=defaultdict(list)
    for row in observations:
        groups[row["position"]].append(row)
    summary={}
    for position,rows in sorted(groups.items()):
        bayes=_scores([(r["joint_over"],r["actual_over"]) for r in rows])
        baseline=_scores([(r["control_over"],r["actual_over"]) for r in rows])
        summary[position]={
            "n":len(rows),"days":len({r["game_date"] for r in rows}),
            "joint":bayes,"control":baseline,
            "joint_minus_control":{"brier":bayes["brier"]-baseline["brier"],
                                   "log_loss":bayes["log_loss"]-baseline["log_loss"]},
            "status":"descriptive_underpowered" if len(rows)<100 else "descriptive_only"
        }
    return summary


def compare(idata,train,design,future,*,cutoff,until,line,checks,draws=1500):
    date.fromisoformat(cutoff);date.fromisoformat(until)
    if cutoff>=until:raise ValueError("invalid_chronological_holdout")
    if not math.isfinite(line) or float(line).is_integer():
        raise ValueError("binary_research_threshold_must_avoid_exact_stat_pushes")
    if checks.get("posterior_sampling_ok") is not True:
        raise ValueError("posterior_not_accepted_for_validation")
    identities={(r["game_id"],r["player_id"]) for r in train}
    selected=[r for r in future if cutoff<=r["game_date"]<until]
    if any((r["game_id"],r["player_id"]) in identities for r in selected):
        raise ValueError("retrospective_source_overlap")
    if not selected:raise ValueError("holdout_without_verified_future_games")
    heldout=sorted(selected,key=lambda r:(r["game_date"],r["game_id"],r["player_id"]))
    allowed=set(design["players"])
    pairs=[];excluded=Counter();record=[]
    sampled_cache=joint.posterior_cache(idata)
    simple_baseline=control_cache(train)
    for row in heldout:
        if row["player_id"] not in allowed:
            excluded["unseen_or_training_excluded_player"]+=1;continue
        if row["opponent"] not in design["opponents"]:
            excluded["unseen_opponent"]+=1;continue
        if row["season"] not in design["seasons"] and len(design["seasons"])<2:
            excluded["unidentified_next_season_effect"]+=1;continue
        seed=int.from_bytes(hashlib.sha256(
            (joint.VERSION+row["game_id"]+row["player_id"]+
             row["stat"]).encode()).digest()[:8],"big")
        q=joint.forecast(idata,design,player_id=row["player_id"],
            opponent=row["opponent"],season=row["season"],home=row["home"],
            line=line,seed=seed,draws=draws,diagnostic=checks,cache=sampled_cache)
        p=q["q_over"]
        base=cached_control(simple_baseline,player=row["player_id"],position=row["position"],
                  stat_family=design["family"],line=line)
        actual=int(row["value"]>line)
        pairs.append((p,base,actual,row["game_date"]))
        record.append({"game_date":row["game_date"],"game_id":row["game_id"],
                       "player_id":row["player_id"],"position":row["position"],
                       "observed":row["value"],"actual_over":actual,
                       "joint_over":p,"control_over":base,"mc_se":q["numerical_mc_se"],
                       "source_sha256":row["source_sha256"]})
    model=_scores([(p,y) for p,c,y,d in pairs])
    control=_scores([(c,y) for p,c,y,d in pairs])
    dates=len({r[3] for r in pairs})
    uncertainty=paired_date_bootstrap(pairs)
    deltas={"brier":(model["brier"]-control["brier"] if pairs else None),
            "log_loss":(model["log_loss"]-control["log_loss"] if pairs else None)}
    eligible=dates>=20 and len(pairs)>=300
    if eligible and uncertainty.get("status")!="exploratory_insufficient_dates":
        intervals=[uncertainty.get("brier_delta_ci95"),uncertainty.get("log_loss_delta_ci95")]
        if all(bounds is not None and bounds[1]<0 for bounds in intervals):
            comparison="joint_better_on_heldout"
        elif all(bounds is not None and bounds[0]>0 for bounds in intervals):
            comparison="control_better_on_heldout"
        else:comparison="inconclusive"
    else:comparison="underpowered"
    return {
       "schema":"multisport_joint_stat_holdout_v1","sport":design["sport"],
       "stat":design["stat"],"family":design["family"],
       "fixed_research_line":line,"historical_bookmaker_line":False,
       "training_cutoff_exclusive":cutoff,"heldout_end_exclusive":until,
       "training_digest":design["source_digest"],"training_last_game":design["last_game"],
       "all_completed_player_games":len(heldout),"scored_same_cohort_games":len(pairs),
       "heldout_dates":dates,"excluded":dict(excluded),
       "joint":model,"control":control,"joint_minus_control":deltas,
       "paired_date_cluster":uncertainty,"comparative_result":comparison,
       "by_position":position_slices(record),
       "reliability":{"joint":reliability(record,probability_key="joint_over"),
                      "control":reliability(record,probability_key="control_over")},
       "observations":record,"model_version":joint.VERSION,
       "posterior_diagnostics":checks,
       "publication_eligible":False,"calibrated":False,"ranking_allowed":False}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument("--sport",choices=history.SPORTS,required=True)
    p.add_argument("--stat",required=True)
    p.add_argument("--line",type=float,required=True)
    p.add_argument("--cutoff",required=True)
    p.add_argument("--until",required=True)
    p.add_argument("--max-seasons",type=int,default=7)
    p.add_argument("--train-from",help="Must equal the frozen model lower training cutoff")
    p.add_argument("--training-dir",type=Path,default=Path("reports/joint_population"))
    p.add_argument("--draws",type=int,default=1500)
    a=p.parse_args(argv)
    if not (math.isfinite(a.line) and 50<=a.draws<=100000):
        p.error("invalid_research_line_or_posterior_draws")
    import arviz as az
    manifest=json.loads((a.training_dir/"manifest.json").read_text())
    if (manifest["training_cutoff_exclusive"]!=a.cutoff or
        manifest["sport"]!=a.sport or manifest["stat"]!=a.stat or
        manifest["model_version"]!=joint.VERSION or
        manifest.get("training_from_inclusive")!=a.train_from or
        manifest.get("max_training_seasons",7)!=a.max_seasons):
        raise ValueError("frozen_posterior_manifest_mismatch")
    training=history.read(a.root,sport=a.sport,stat=a.stat,before=a.cutoff,
                          after=a.train_from,max_seasons=a.max_seasons,min_records=300)
    training=joint.training_only_subset(training,
        max_per_position=manifest.get("max_per_position",0))
    if not training:raise ValueError("frozen_training_cohort_empty")
    design=joint.prepare(training,min_rows=min(300,len(training)))
    if design["source_digest"]!=manifest["source_digest"]:
        raise ValueError("retrospective_fit_source_digest_drift")
    future=history.read(a.root,sport=a.sport,stat=a.stat,
                        before=a.until,after=a.cutoff)
    posterior=az.from_netcdf(a.training_dir/"posterior.nc")
    report=compare(posterior,training,design,future,cutoff=a.cutoff,
                   until=a.until,line=a.line,checks=manifest["diagnostics"],draws=a.draws)
    a.training_dir.mkdir(parents=True,exist_ok=True)
    (a.training_dir/"stat_holdout.json").write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in ("observations","by_position")},sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
