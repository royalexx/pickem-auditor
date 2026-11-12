"""V4/V4.1 factor-effect and QB-share correction ablation, paired 175-week research.

Metrics are from the same original synthetic contracts. Source candidate
probabilities are RAW (not equally calibrated to legacy online probabilities).
V4.1 uses different adaptive updates, so V4.1-V4 measures combined QB repair
and resulting online-learning feedback, not a fully isolated causal QB effect.
"""
from __future__ import annotations
import collections,csv,gzip,json,pathlib,math
import numpy as np
ROOT=pathlib.Path.cwd()
BASE=ROOT/"reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111"
A=next(iter(sorted(BASE.glob("V4_ADAPTIVE_FACTORS_10YEAR_FULL_*"))),None)
B=next(iter(sorted(BASE.glob("V4_1_QB_REPAIR_10YEAR_FULL_*"))),None)
V2=BASE/"EXP_ALL13_20261111T200951Z"
OUT=BASE/"V4_FACTOR_MEMORY_AND_QB_REPAIR_ABLATION"
OUT.mkdir(parents=True,exist_ok=True)
if A is None or B is None:raise RuntimeError("Missing V4 or V4.1 experiment")
read=lambda path:json.loads(gzip.open(path,"rb").read() if path.suffix==".gz" else path.read_bytes())
a=read(A/"V4_FINAL_DECADE_RESEARCH_REPORT.json");b=read(B/"V4_FINAL_DECADE_RESEARCH_REPORT.json")
assert a["cycles"]==175==b["cycles"]
assert a["total_offered"]==b["total_offered"]==556094
assert a["total_paired"]==b["total_paired"]==407476
market=collections.defaultdict(lambda:collections.defaultdict(float))
year=collections.defaultdict(lambda:collections.defaultdict(float))
wk=collections.defaultdict(lambda:collections.defaultdict(float))
profiles=collections.defaultdict(lambda:collections.defaultdict(float))
games=collections.defaultdict(lambda:collections.defaultdict(float))
global_agg=collections.defaultdict(float)
weights=[]
issues=collections.Counter()
for y in range(2016,2026):
 for w in range(1,19 if y>=2021 else 18):
  name=f"{y}_week_{w:02d}"
  pa=read(A/(name+"_v4_predictions.json.gz"))
  pb=read(B/(name+"_v4_predictions.json.gz"))
  sa=read(A/(name+"_v4_settlements.json.gz"))
  sb=read(B/(name+"_v4_settlements.json.gz"))
  truth=read(V2/(name+"_settlements.json.gz"))
  by={(f["game_id"],f["team"],f["player_id"],f["market"]):f for f in pb["offers"]}
  evidence={(z["game_id"],z["team"],z["player_id"],z["market"]):z
      for z in truth["scored"] if z["status"]=="scored_as_same_contract"
      and all(k in z["model_scores"] for k in ("shared_opportunity","player_history"))}
  if sa["paired"]!=sb["paired"]:issues["paired_week_diff"]+=1
  weights.append({"season":y,"week":w,
    "v4_weights":next(iter(pa["game_context"].values()))["factor_weights_prior"] if pa["game_context"] else None,
    "v41_weights":next(iter(pb["game_context"].values()))["factor_weights_prior"] if pb["game_context"] else None})
  for fa in pa["offers"]:
   k=(fa["game_id"],fa["team"],fa["player_id"],fa["market"])
   fb=by.get(k);obs=evidence.get(k)
   if fb is None:issues["unmatched_offer_identity"]+=1;continue
   if obs is None or fa["status"]!="forecast" or fb["status"]!="forecast":continue
   actual=int(obs["observed_over"]);m=fa["market"]
   diff=(fb["p_over_tuned"]-actual)**2-(fa["p_over_tuned"]-actual)**2
   hits=int((fb["p_over_tuned"]>.5)==bool(actual))-int((fa["p_over_tuned"]>.5)==bool(actual))
   for dest in (market[m],year[y],wk[(y,w)],games[(y,w,fa["game_id"])],global_agg):
    dest["n"]+=1
    dest["V4_brier"]+=(fa["p_over_tuned"]-actual)**2
    dest["V41_brier"]+=(fb["p_over_tuned"]-actual)**2
    dest["delta_brier"]+=diff
    dest["delta_hit"]+=hits
    dest["V4_hit"]+=int((fa["p_over_tuned"]>.5)==bool(actual))
    dest["V41_hit"]+=int((fb["p_over_tuned"]>.5)==bool(actual))
   for variant,label in ((fa,"v4"),(fb,"v41")):
    p=profiles[(label,m)]
    p["n"]+=1
    for j,source in enumerate(("V3","recent","long")):
     q=variant["source_q_over"][j]
     p[source+"_raw_brier"]+=(q-actual)**2
     qtile=variant["source_quantiles"][j]
     p[source+"_quantile_loss"]+=sum((tau-int(obs["actual"]<x))*(obs["actual"]-x)
        for tau,x in zip((.1,.5,.9),qtile))/3
   if m in ("pass attempts","completions","passing yards","qb rushing yards","qb rushing attempts"):
    for dest in (market[m],year[y]):
     dest["qb_related_n"]+=1
     dest["v4_QB_mean"]+=fa["predicted_mean"]
     dest["v41_QB_mean"]+=fb["predicted_mean"]
     dest["QB_truth"]+=obs["actual"]
  if w in (1,9,18):
   print("FACTOR_ABLATION_DONE",y,w,"paired",sa["paired"],flush=True)
def summarize(x):
 n=x.get("n",0)
 if not n:return {"n":0}
 d={"n":int(n)}
 for k,v in x.items():
  if k in ("n",):continue
  d[k]=float(v/n)
 return d
out={"status":"COMPLETE_RESEARCH_ONLY",
 "source_is_authentic_historical_pregame":False,
 "match_contracts_identical":not bool(issues),
 "issues":dict(issues),"overall":summarize(global_agg),
 "season":{str(k):summarize(v) for k,v in sorted(year.items())},
 "market":{k:summarize(v) for k,v in sorted(market.items())},
 "profile_market_raw_score":{label+"|"+m:summarize(v) for (label,m),v in sorted(profiles.items())},
 "weights_first":weights[:3],"weights_last":weights[-3:],
 "year_group_first_2016_20":{},
 "year_group_last_2021_25":{},
 "limitations":["Pure-profile raw probabilities are not calibrated and must not be compared to online-calibrated baseline as equal evidence",
 "V4.1 changes QB projection and the resulting prior-only factor/stack weights, so this is an adaptive-policy contrast rather than isolating only one line of code",
 "Original lines and sources are retrospective synthetic research, no real odds/PnL",
 "All contract cluster bootstrap treats each game/week as correlated, not independent legs"]}
def groupsum(vals):
 d=collections.defaultdict(float)
 for v in vals:
  for k,z in v.items():d[k]+=z
 return summarize(d)
out["year_group_first_2016_20"]=groupsum([year[y] for y in range(2016,2021)])
out["year_group_last_2021_25"]=groupsum([year[y] for y in range(2021,2026)])
rng=np.random.default_rng(13541)
def boot(clusters,reps=2500):
 ss=list(clusters.values())
 num=np.asarray([v["n"] for v in ss]);bd=np.asarray([v["delta_brier"] for v in ss])
 hd=np.asarray([v["delta_hit"] for v in ss])
 vals=[];hits=[]
 for _ in range(reps):
  ix=rng.integers(0,len(ss),len(ss))
  vals.append(float(np.sum(bd[ix])/np.sum(num[ix])))
  hits.append(float(np.sum(hd[ix])/np.sum(num[ix])))
 return {"clusters":len(ss),
  "brier_delta_ci95":np.quantile(vals,[.025,.975]).tolist(),
  "hit_delta_ci95":np.quantile(hits,[.025,.975]).tolist()}
out["cluster_week"]=boot(wk)
out["cluster_game"]=boot(games)
(OUT/"V4_V41_PAIRED_175_WEEK_QB_AND_HISTORY_FACTORS.json").write_text(json.dumps(out,indent=2,sort_keys=True,default=str))
with (OUT/"V4_V41_13_MARKET_ABLATION.csv").open("w",newline="") as f:
 fields=["market","n","V4_brier","V41_brier","delta_brier","delta_hit","V4_hit","V41_hit","qb_related_n","v4_QB_mean","v41_QB_mean","QB_truth"]
 ww=csv.DictWriter(f,fieldnames=fields);ww.writeheader()
 for m,v in sorted(market.items()):ww.writerow({"market":m,**{k:summarize(v).get(k) for k in fields if k!="market"}})
print("V41_V4_PAIRED_ABLATION_COMPLETE",json.dumps({"issues":dict(issues),"n":int(global_agg["n"]),
 "overall":out["overall"],"permarket":{k:{"brier":v["delta_brier"],"hit":v["delta_hit"],"n":v["n"],"v4_QB_mean":v.get("v4_QB_mean"),
 "v41_QB_mean":v.get("v41_QB_mean")} for k,v in out["market"].items()},
 "first":out["year_group_first_2016_20"],"last":out["year_group_last_2021_25"],
 "cluster":out["cluster_week"]},sort_keys=True),flush=True)
