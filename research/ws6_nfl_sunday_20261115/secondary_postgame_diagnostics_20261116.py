"""WS6 secondary source/role and per-stat research diagnostics; add-only."""
from __future__ import annotations
import collections,csv,hashlib,io,json,math,pathlib
from functools import lru_cache
import numpy as np
from research.ws6_nfl_sunday_20261115.independent_postgame_20261116 import (
    OUT,JR,COMPARE,EPSN,MAP,load,rows,official_sources,get_stat,crps_sample,interval_draw,source,frozen_write,dump
)
THIS=OUT/"secondary_diagnostics_v1.json"
@lru_cache(maxsize=32)
def cached_verified_simulation(path_string,sha):
    path=pathlib.Path(path_string)
    source(path,sha)
    return load(path)
JLEDGER=JR/"759dc467ef3bdc589b3588c7adb59254076e5d071dbf35bf167c408447e56431.ledger.json"
def score():
    c=rows(COMPARE);orig={r["quote_id"]:r for r in c}
    files,official=official_sources({str(r["event_id"]) for r in c if r.get("event_id")})
    jr=load(JLEDGER)
    vals=collections.defaultdict(list)
    missing=collections.Counter()
    missing_detail=[]
    bookmaker_dup=collections.Counter()
    modelrows=collections.defaultdict(list)
    for rec in jr:
        if rec.get("status")!="FORECAST" or rec.get("model_id")!="J2":continue
        o=orig.get(rec["quote_id"])
        if o is None:raise ValueError("QUOTE_MISMATCH")
        modelrows[(rec["event_id"],rec["player_id"],rec["normalized_market"])].append(rec)
    top=[]; per=collections.defaultdict(list)
    for (event,pid,stat),rr in modelrows.items():
        means=set(round(float(r["mean"]),7) for r in rr)
        if len(means)!=1:raise ValueError("CONFLICTING_MEANS_FOR_SAME_STAT")
        r=sorted(rr,key=lambda x:(x["line"],x["quote_id"]))[0]
        o=orig[r["quote_id"]]
        y,status,player=get_stat(event,str(pid),o["player"],stat,files)
        if status!="OBSERVED":
            missing[status]+=1
            if len(missing_detail)<30:missing_detail.append({"event":event,"player":o["player"],"stat":stat,"reason":status})
            continue
        fn=JR/(r["forecast_file_sha256"]+".json")
        obj=cached_verified_simulation(str(fn),r["forecast_file_sha256"])
        series=obj["draw_records"]["J2"]["series"]
        key="|".join((r["team"],str(r["player_id"]),stat))
        points=series.get(key)
        crps=None;intervals={};first_keys=[]
        if points is None:
            missing["DRAW_SERIES_KEY_MISSING"]+=1
            first_keys=[k for k in series.keys() if k.startswith(str(r["team"])+"|"+str(pid)+"|")][:10]
            if len(missing_detail)<40:missing_detail.append({"event":event,"player":o["player"],"stat":stat,"reason":"DRAW_SERIES_KEY_MISSING","expected_key":key,"other_player_series":first_keys})
        else:
            crps=crps_sample(points,y)
            intervals={str(p):interval_draw(points,y,p)[0] for p in (.5,.8,.9,.95)}
        err=y-float(r["mean"]);variance=max(float(r.get("variance") or 0),0)
        std_err=err/math.sqrt(variance) if variance>1e-12 else None
        item={"event":event,"player":o["player"],"player_id":str(pid),"team":player["team"],
              "market":stat,"realized":y,"pregame_mean":r["mean"],"pregame_variance":variance,
              "actual_minus_forecast":err,"absolute_error":abs(err),"standardized_error":std_err,
              "quantiles":r.get("quantiles"),"prediction_source_sha256":r["forecast_file_sha256"],
              "forecast_at":obj["forecast_created_at"],
              "n_bookmaker_quotes":len(rr),"distribution_draws_available":points is not None,
              "crps":crps,"intervals":intervals}
        per[stat].append(item);top.append(item)
    topstd=sorted([x for x in top if x["standardized_error"] is not None],key=lambda z:abs(z["standardized_error"]),reverse=True)[:25]
    topabs=sorted(top,key=lambda z:z["absolute_error"],reverse=True)[:25]
    per_market={}
    for market,group in sorted(per.items()):
        per_market[market]={"unique_player_stats":len(group),
          "signed_mean_error":float(np.mean([x["actual_minus_forecast"] for x in group])),
          "mae":float(np.mean([x["absolute_error"] for x in group])),
          "crps":float(np.mean([x["crps"] for x in group if x["crps"] is not None])) if any(x["crps"] is not None for x in group) else None,
          "draw_backed":sum(x["crps"] is not None for x in group),
          "intervals":{str(p):{"n":sum(str(p) in x["intervals"] for x in group),
            "observed_coverage":float(np.mean([x["intervals"][str(p)] for x in group if str(p) in x["intervals"]])) if any(str(p) in x["intervals"] for x in group) else None}
              for p in (.5,.8,.9,.95)}}
    # Joint QB pass attempt forecast is *starter-level*, not identical to team pass pool.
    qbs=[];others=0
    for x in per.get("pass_attempts",[]):
        ee=files[x["event"]]["_ids"]
        official_team_qbs=[{"player":p["name"],"attempts":p["stats"]["pass_attempts"]}
            for p in ee.values() if p["team"]==x["team"] and "pass_attempts" in p["stats"]]
        total=sum(z["attempts"] for z in official_team_qbs)
        qbs.append({"event":x["event"],"starter":x["player"],"team":x["team"],
            "predicted_starter_attempts":x["pregame_mean"],"actual_starter_attempts":x["realized"],
            "actual_team_attempts":total,"other_qb_attempts":total-x["realized"],
            "official_qbs":official_team_qbs})
    out={"schema":"WS6_POSTGAME_SECONDARY_DIAGNOSTICS_V1","status":"RESEARCH_ONLY_UNCERTIFIED",
         "basis":"Frozen J2 v0.4 player-stat distributions deduplicated BEFORE scoring; original ESPN observed categories only.",
         "j2_player_stat_forecast_groups":len(modelrows),"j2_observed_player_stat_groups":len(top),
         "not_boxed_or_missing_distribution":dict(missing),"quarantined_examples":missing_detail,
         "per_stat":per_market,"quarterback_attempt_comparisons":qbs,
         "top25_absolute_point_errors":topabs,
         "top25_standardized_point_errors":topstd,
         "limitations":["ESPN defensive TOT not independent GSIS solo+assists parity",
                        "Missing official category not imputed zero",
                        "Starter passing attempts is not the complete team passing opportunity model",
                        "Point mean of an outcome is not the authentic frozen participation/share/efficiency component",
                        "No mixed-scale CRPS comparisons across markets",
                        "Outlier residuals are observational, not causal or proof of model changes"]}
    dump(THIS,out)
    print(json.dumps({"sha256":source(THIS),"count":len(top),"groups":len(modelrows),
          "missing":dict(missing),"per_market":per_market,
          "qb_attempts":qbs,"top25_standardized":topstd,"top25_absolute":topabs},allow_nan=False))
if __name__=="__main__":score()
