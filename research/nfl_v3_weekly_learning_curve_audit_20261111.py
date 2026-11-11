"""NFL V3 chronological 175-week learning curve and context-history effect audit.
Reads only finalized weekly receipts, never re-fits forecasts or mutates old runs.
Research-only: synthetic historical lines, retrospective 2026 sources.
"""
import csv,gzip,json,pathlib,collections,math,argparse
import numpy as np

ROOT=pathlib.Path.cwd()
BASE=ROOT/"reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111"
EXP=BASE/"V3_CONTEXT_10YEAR_FULL_20261111T233046Z"
MARKETS=("pass attempts","completions","passing yards","targets","receptions","receiving yards","carries","rushing yards","tackles + assists","solo tackles","tackle assists","qb rushing attempts","qb rushing yards")
READ=lambda p:json.loads(gzip.open(p,"rb").read() if p.suffix==".gz" else p.read_bytes())

def metric(rows,k):
 n=sum(r["n"] for r in rows if r.get(k) is not None)
 return sum(r["n"]*r[k] for r in rows if r.get(k) is not None)/n if n else None

def stats(rows):
 n=sum(r["n"] for r in rows)
 if not n:return {"n":0,"weeks":len(rows)}
 a={"n":n,"weeks":len(rows)}
 for k in ("brier_new","brier_v2_joint","brier_v2_history","brier_v3_pure",
           "crps_new","crps_v2_joint","crps_v2_history",
           "hit_new","hit_v2_joint","hit_v2_history",
           "logloss_new","logloss_v2_joint","logloss_v2_history",
           "count_mean_bias","p_over","over_0_1","interval_80_covers"):
  a[k]=metric(rows,k)
 for key,left,right in (("delta_brier","brier_new","brier_v2_joint"),
   ("delta_crps","crps_new","crps_v2_joint"),
   ("delta_logloss","logloss_new","logloss_v2_joint"),
   ("delta_hit","hit_new","hit_v2_joint"),
   ("delta_vs_history","brier_new","brier_v2_history")):
  a[key]=a[left]-a[right] if a[left] is not None and a[right] is not None else None
 for threshold in (70,80,90,95):
  h=f"conf{threshold}"
  z=[r for r in rows if r.get(h+"_n",0)>0]
  count=sum(r[h+"_n"] for r in z)
  a[h+"_n"]=count
  a[h+"_claimed"]=sum(r[h+"_n"]*r[h+"_claimed"] for r in z)/count if count else None
  a[h+"_hit"]=sum(r[h+"_n"]*r[h+"_hit"] for r in z)/count if count else None
  a[h+"_gap"]=(a[h+"_hit"]-a[h+"_claimed"]) if count else None
 return a

def weighted_slope(rows,metric_name="delta_brier"):
 zz=[r for r in rows if r["n"]>0 and r.get(metric_name)is not None]
 if len(zz)<3:return None
 xs=np.asarray([r["season"]+(r["week"]-.5)/18 for r in zz],dtype=float)
 ys=np.asarray([r[metric_name] for r in zz]); ww=np.asarray([r["n"] for r in zz])
 mx=np.average(xs,weights=ww);my=np.average(ys,weights=ww)
 return float(np.sum(ww*(xs-mx)*(ys-my))/np.sum(ww*(xs-mx)**2))
def resample_seasons(rows,rng,reps=3500):
 group=collections.defaultdict(list)
 for r in rows:group[r["season"]].append(r)
 keys=sorted(group)
 if len(keys)<3:return None
 slopes=[]
 contrasts=[]
 for _ in range(reps):
  chosen=rng.choice(keys,len(keys),replace=True)
  pool=[r for key in chosen for r in group[int(key)]]
  slope=weighted_slope(pool)
  if slope is not None:slopes.append(slope)
  early=[r for r in pool if r["season"]<=2020]
  late=[r for r in pool if r["season"]>=2021]
  if early and late:
   contrasts.append(stats(late)["delta_brier"]-stats(early)["delta_brier"])
 return {"method":"season-block bootstrap, 10 seasons, historical development-exposed data",
   "slope_ci95":np.quantile(slopes,[.025,.975]).tolist(),
   "prob_slope_negative":float(np.mean(np.array(slopes)<0)),
   "late_minus_early_brier_delta_ci95":np.quantile(contrasts,[.025,.975]).tolist() if contrasts else None}

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--out",required=True,type=pathlib.Path)
 ap.add_argument("--partial",action="store_true")
 args=ap.parse_args()
 rows=[];mr=[];skipped=[]
 for year in range(2016,2026):
  for week in range(1,19 if year>=2021 else 18):
   path=EXP/f"{year}_week_{week:02d}_v3_settlements.json.gz"
   if not path.exists():
    skipped.append([year,week])
    continue
   v=READ(path)
   assert v["year"]==year and v["week"]==week
   s=v["all"];paired=v["paired"]
   assert s["n"]==paired
   row={"season":year,"week":week,"n":paired,
    "historic_seasons_at_week1":min(10,year-2014),
    "offered":v["offered"],"scored_original":v["scored_original"],
    "paired":paired}
   row.update({k:x for k,x in s.items() if isinstance(x,(float,int)) or x is None})
   row["delta_brier"]=row["brier_new"]-row["brier_v2_joint"]
   row["delta_crps"]=row["crps_new"]-row["crps_v2_joint"]
   rows.append(row)
   for market in MARKETS:
    k=v["markets"].get(market,{})
    if not k or not k.get("n",0):continue
    rr={"season":year,"week":week,"market":market,"n":int(k["n"])}
    rr.update({name:x for name,x in k.items() if isinstance(x,(int,float)) or x is None})
    rr["delta_brier"]=rr["brier_new"]-rr["brier_v2_joint"]
    rr["delta_crps"]=rr["crps_new"]-rr["crps_v2_joint"]
    mr.append(rr)
 if skipped and not args.partial:raise RuntimeError("full_175_weeks_not_finished missing="+str(skipped[:5]))
 assert len(rows)+len(skipped)==175
 args.out.mkdir(parents=True,exist_ok=True)
 early=[r for r in rows if r["season"]<=2020]
 late=[r for r in rows if r["season"]>=2021]
 first3=[r for r in rows if r["season"]<=2018]
 last3=[r for r in rows if r["season"]>=2023]
 within_first=[r for r in rows if r["week"]<=5]
 within_late=[r for r in rows if r["week"]>=14]
 byyear={str(year):stats([r for r in rows if r["season"]==year]) for year in range(2016,2026)}
 bymarket={m:stats([r for r in mr if r["market"]==m]) for m in MARKETS}
 bymarket_trends={}
 for m in MARKETS:
  z=[r for r in mr if r["market"]==m]
  bymarket_trends[m]={"slope_brier_delta_per_season":weighted_slope(z),
   "first_half":stats([r for r in z if r["season"]<=2020]),
   "last_half":stats([r for r in z if r["season"]>=2021]),
   "yearly":{str(y):stats([r for r in z if r["season"]==y]) for y in range(2016,2026)}}
 overall=stats(rows)
 base=overall["delta_brier"]
 slope=weighted_slope(rows)
 bs=resample_seasons(rows,np.random.default_rng(1762025))
 result={"status":"COMPLETE_RESEARCH_ONLY" if not skipped else "PARTIAL_RESEARCH_ONLY",
   "weeks_done":len(rows),"weeks_missing":len(skipped),"missing_week_samples":skipped[:15],
   "source_is_authentic_pregame":False,
   "synthetic_lines_not_bookmaker":True,
   "final_production_promotion":False,
   "overall":overall,"yearly":byyear,"market_overall":bymarket,
   "market_longitudinal":bymarket_trends,
   "older_first_half":stats(early),"newer_second_half":stats(late),
   "recent_minus_early_delta_brier":(stats(late)["delta_brier"]-stats(early)["delta_brier"]) if early and late else None,
   "first_three_years":stats(first3),"last_three_years":stats(last3),
   "first_five_weeks_of_season":stats(within_first),"weeks_14_plus_of_season":stats(within_late),
   "linear_brier_delta_slope_per_year":slope,"season_cluster_bootstrap":bs,
   "weeks_v3_outperforms":sum(r["delta_brier"]<0 for r in rows),
   "weeks_v2_outperforms":sum(r["delta_brier"]>0 for r in rows),
   "interpretation":["Negative delta Brier favors V3, negative time slope means growth in V3 relative advantage.",
      "Greater year separation does not prove that more historical training caused the effect: NFL regime changes, opponent schedule and calibration confound.",
      "75% of V3 scenario ensemble is the original V2 distribution and uses only up to three prior seasons.",
      "Models use 128 simulation draws; high-confidence comparisons have finite resolution.",
      "Potential conditional-participation selection and original sources collected retroactively in 2026 prevent production conclusions."]}
 (args.out/"V3_WEEKLY_LEARNING_CURVE_AUDIT.json").write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False))
 def csvfile(name,objs):
  fields=sorted(set().union(*(x.keys() for x in objs)))
  with (args.out/name).open("w",newline="") as f:
   ww=csv.DictWriter(f,fieldnames=fields);ww.writeheader();ww.writerows(objs)
 csvfile("V3_ALL_175_WEEKLY_TREND.csv",rows)
 csvfile("V3_ALL_WEEK_MARKET_TRENDS.csv",mr)
 with (args.out/"V3_YEARLY_TREND.csv").open("w",newline="") as f:
  keys=["season","n","weeks","brier_new","brier_v2_joint","delta_brier","delta_crps","hit_new","hit_v2_joint","conf80_n","conf80_hit","conf80_claimed","conf80_gap"]
  ww=csv.DictWriter(f,fieldnames=keys);ww.writeheader()
  for y,rec in byyear.items():ww.writerow({"season":y,**{k:rec.get(k) for k in keys if k!="season"}})
 print("V3_LEARNING_CURVE_AUDIT",json.dumps({"status":result["status"],"weeks":len(rows),
   "overall_delta":base,"slope_per_year":slope,"first_half":result["older_first_half"],
   "second_half":result["newer_second_half"],"years":[{"season":y,"delta":v.get("delta_brier"),"n":v["n"],"conf80_gap":v.get("conf80_gap")} for y,v in byyear.items()],
   "cluster":bs,"market":[{"market":k,"delta":v.get("delta_brier"),"slope":bymarket_trends[k]["slope_brier_delta_per_season"]} for k,v in bymarket.items()]},sort_keys=True),flush=True)

if __name__=="__main__":main()
