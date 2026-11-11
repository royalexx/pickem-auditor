"""Independent walk-forward ablation: 10-year vs 3-year regression for NFL team
plays and pass-rate matchup prediction. Scores each target only after fitting
on strictly earlier team-games; retrospective research, not authentic pregame.
"""
from __future__ import annotations
import collections,csv,gzip,json,pathlib,sys,math
import numpy as np
ROOT=pathlib.Path.cwd()
sys.path[:0]=[str(ROOT/"research"),str(ROOT/"reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/EXP_ALL13_20261111T200951Z/frozen_code")]
from nfl_decade_context_v3_model_20261111 import MatchupRegressor
from v25_decade_joint_opportunity import normalise_player_source
SRC=ROOT/"reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/source_bundle"
OUT=ROOT/"reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/V3_TEN_VS_THREE_YEAR_MATCHUP_ABLATION"
OUT.mkdir(parents=True,exist_ok=True)
read=lambda p:json.loads(gzip.open(p,"rb").read())
allg={}
for y in range(2014,2026):
 data=read(SRC/f"stats_{y}.json.gz")
 rows=[r for r in data["rows"] if r.get("player_id") and r.get("game_id") and r.get("team")]
 allg[y]=normalise_player_source(rows,rejection_ledger=[],allowed_seasons=tuple(range(2014,2026)))
rows=[];fit_cache={}
for fy in range(2016,2026):
 weeks=sorted({g["week"] for g in allg[fy]})
 for fw in weeks:
  facts=[g for g in allg[fy] if g["week"]==fw]
  for years in (3,10):
   hist=[g for y in range(max(2014,fy-years),fy) for g in allg[y]]
   hist.extend(g for g in allg[fy] if g["week"]<fw)
   assert all(g["season"]<fy or(g["season"]==fy and g["week"]<fw) for g in hist)
   reg=MatchupRegressor(hist);fit=reg.fitted(fy,fw)
   # Only prior observations enter feature estimates.
   off=collections.defaultdict(list);allowed=collections.defaultdict(list)
   for g in hist:
    n=g["pass_attempts"]+g["rush_attempts"]
    pp=g["pass_attempts"]/n if n else .57
    off[g["team"]].append((n,pp));allowed[g["opponent"]].append((n,pp))
   fit_cache[years]=(reg,fit,off,allowed)
  for g in facts:
   total=g["pass_attempts"]+g["rush_attempts"]
   if total<20 or total>115:continue
   rate=g["pass_attempts"]/total
   pred={}
   for years in (3,10):
    reg,fit,off,allowed=fit_cache[years]
    x=reg.feature(g["team"],g["opponent"],off,allowed)
    pred[years]={"plays":float(np.clip(x@fit["plays"],38,84)),
      "pass_share":float(np.clip(x@fit["pass_rate"],.35,.8)),
      "rows":fit["training_rows"]}
   row={"year":fy,"week":fw,"game":g["event_id"],"team":g["team"],
     "actual_plays":total,"actual_pass_share":rate}
   for years in (3,10):
    row["p"+str(years)]=pred[years]["plays"]
    row["r"+str(years)]=pred[years]["pass_share"]
    row["n"+str(years)]=pred[years]["rows"]
   row["se3"]=(pred[3]["plays"]-total)**2
   row["se10"]=(pred[10]["plays"]-total)**2
   row["pr_se3"]=(pred[3]["pass_share"]-rate)**2
   row["pr_se10"]=(pred[10]["pass_share"]-rate)**2
   rows.append(row)
  if fw in (1,9,17):print("MATCHUP_ABLATION_PROGRESS",fy,fw,len(rows),flush=True)

def summarize(a):
 if not a:return {}
 return {"n":len(a),"mse_play_3yr":float(np.mean([x["se3"] for x in a])),
  "mse_play_10yr":float(np.mean([x["se10"] for x in a])),
  "mse_passrate_3yr":float(np.mean([x["pr_se3"] for x in a])),
  "mse_passrate_10yr":float(np.mean([x["pr_se10"] for x in a])),
  "mae_plays_3yr":float(np.mean([abs(x["p3"]-x["actual_plays"]) for x in a])),
  "mae_plays_10yr":float(np.mean([abs(x["p10"]-x["actual_plays"]) for x in a])),
  "mean_error_plays_10yr":float(np.mean([x["p10"]-x["actual_plays"] for x in a])),
  "delta_mse_plays_10_minus_3":float(np.mean([x["se10"]-x["se3"] for x in a])),
  "delta_mse_passrate_10_minus_3":float(np.mean([x["pr_se10"]-x["pr_se3"] for x in a]))}
overall=summarize(rows)
byyear={str(y):summarize([z for z in rows if z["year"]==y]) for y in range(2016,2026)}
rng=np.random.default_rng(12233)
groups=collections.defaultdict(list)
for r in rows:groups[(r["year"],r["week"])].append(r)
clusters=list(groups.values())
bs=[]
for _ in range(4000):
 ix=rng.integers(0,len(clusters),len(clusters))
 sample=[r for i in ix for r in clusters[i]]
 bs.append([np.mean([x["se10"]-x["se3"] for x in sample]),
  np.mean([x["pr_se10"]-x["pr_se3"] for x in sample])])
bs=np.asarray(bs)
audit={"status":"COMPLETE_RESEARCH_ONLY","n_week_clusters":len(clusters),
 "source_capture_pregame_verified":False,
 "all":overall,"byyear":byyear,
 "week_cluster_play_delta_mse_ci95":np.quantile(bs[:,0],[.025,.975]).tolist(),
 "week_cluster_passrate_delta_mse_ci95":np.quantile(bs[:,1],[.025,.975]).tolist(),
 "interpretation":"10-year vs 3-year same ridge method only; no player usage confounding"}
(OUT/"V3_MATCHUP_10Y_VS_3Y_ABLATION.json").write_text(json.dumps(audit,indent=2))
with (OUT/"V3_ALL_MATCHUP_WEEK_RESULTS.csv").open("w",newline="") as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print("MATCHUP_10Y_VS_3Y_DONE",json.dumps(audit),flush=True)
