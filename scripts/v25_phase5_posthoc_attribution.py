"""Post-hoc descriptive SOG likelihood ablations from sealed historical forecasts.
DO NOT treat these as preregistered, independent holdout, or eligible model-selection evidence.
All ablations use existing immutable M0..M4 model parameters and the same scored games.
"""
from pathlib import Path
import argparse, collections, hashlib, json, math, statistics, random
import numpy as np
from scipy.stats import poisson

def canon(x):return json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def jl(path):
 b=Path(path).read_bytes();return [json.loads(s) for s in b.splitlines() if s],sha(b)
def pmf_poisson(mu,max_k=180):
 if not math.isfinite(mu) or mu<0:raise ValueError("INVALID_POISSON_MEAN")
 k=np.arange(max_k+1,dtype=float)
 return np.asarray(poisson.pmf(k,mu),dtype=float)
def score(p,y):
 if y>=len(p):raise ValueError("UNSUPPORTED_OUTCOME")
 mass=float(np.sum(p))
 if abs(mass-1)>1e-10:raise ValueError("PMF_MASS_LOST")
 cdf=np.cumsum(p)
 if float(p[y])<=0:raise ValueError("OUTCOME_PMF_ZERO")
 return {"crps":float(np.sum((cdf-(np.arange(len(p))>=y).astype(float))**2)),
         "nll":float(-math.log(float(p[y]))),"mean":float(np.dot(np.arange(len(p)),p)),
         "variance":float(np.dot((np.arange(len(p))-np.dot(np.arange(len(p)),p))**2,p))}
def exposure_mix(pi,rate):
 k=np.arange(181,dtype=float)
 w=np.array([p[0] for p in pi],dtype=float)
 p=np.array([p[1] for p in pi],dtype=float)
 if abs(float(np.sum(p))-1)>1e-10:raise ValueError("INVALID_EXPOSURE_MIX")
 values=np.asarray(poisson.pmf(k[:,None],(rate*w)[None,:]))@p
 return values
def calculate(root):
 root=Path(root)
 predictions,fs=jl(root/"sealed_forecasts.jsonl")
 scored,ss=jl(root/"scored_played.jsonl")
 idx={(x["game_id"],x["player_id"]):x for x in predictions}
 if len(idx)!=len(predictions):raise ValueError("DUPLICATE_FROZEN_FORECAST")
 results=[];ids=("S1_shrunk_mean_fixed_poisson",
                   "S2_plugin_rate_expected_exposure_poisson",
                   "S3_shrunk_rate_expected_exposure_poisson",
                   "S4_shrunk_rate_exposure_mixture_poisson")
 for row in scored:
  key=(row["game_id"],row["player_id"])
  m=idx[key]["distribution_params"];y=row["actual_sog"]
  plugin=m["plugin_rate"];w0=m["plugin_exposure"]
  a=m["rate_a"];b=m["rate_b"];pi=m["exposure_pmf"]
  lam=a/b;ew=math.fsum(w*p for w,p in pi)
  probs={
   ids[0]:pmf_poisson(lam*w0),
   ids[1]:pmf_poisson(plugin*ew),
   ids[2]:pmf_poisson(lam*ew),
   ids[3]:exposure_mix(pi,lam)}
  s={model:score(p,y) for model,p in probs.items()}
  for model,z in s.items():
   if model in (ids[0],ids[2],ids[3]) and not math.isfinite(z["crps"]):
    raise ValueError("POSTHOC_SCORE_NONFINITE")
  if abs(s[ids[0]]["mean"]-m["rate_a"]/m["rate_b"]*w0)>1e-8:raise ValueError("SHRUNK_POISSON_MEAN_DRIFT")
  if abs(s[ids[1]]["mean"]-plugin*ew)>1e-8:raise ValueError("EXPOSURE_POISSON_MEAN_DRIFT")
  if abs(s[ids[3]]["mean"]-lam*ew)>1e-8:raise ValueError("MIXTURE_SHRUNK_MEAN_DRIFT")
  results.append({"date":row["date"],"game_id":row["game_id"],
    "season":row["season"],"group":row["group"],"scores":s,
    "baseline_scores":row["scores"]})
 def avg(model,metric):
  if model in ids:
   return statistics.mean(r["scores"][model][metric] for r in results)
  return statistics.mean(r["baseline_scores"][model][metric] for r in results)
 metrics={model:{metric:avg(model,metric) for metric in ("crps","nll")}
          for model in ("M0","M1","M2","M3","M4")+ids}
 pairs={
  "rate_shrinkage_mean_fixed_S1_vs_M0":("S1_shrunk_mean_fixed_poisson","M0"),
  "gamma_rate_uncertainty_M2_vs_S1":("M2",ids[0]),
  "exposure_mean_shift_S2_vs_M0":(ids[1],"M0"),
  "exposure_uncertainty_M1_vs_S2":("M1",ids[1]),
  "shrunk_exposure_mean_S3_vs_S1":(ids[2],ids[0]),
  "exposure_uncertainty_S4_vs_S3":(ids[3],ids[2]),
  "gamma_rate_uncertainty_with_exposure_M3_vs_S4":("M3",ids[3]),
  "whole_exposure_effect_M3_vs_M2":("M3","M2")}
 comparisons={}
 for label,(c,b) in pairs.items():
  comparisons[label]={}
  for metric in ("crps","nll"):
   by=collections.defaultdict(list)
   for r in results:
    new=r["scores"] if c in ids else r["baseline_scores"]
    old=r["scores"] if b in ids else r["baseline_scores"]
    by[r["date"]].append(new[c][metric]-old[b][metric])
   d=[statistics.mean(x) for x in by.values()]
   comparisons[label][metric]={"matched_pooled_delta":avg(c,metric)-avg(b,metric),
      "date_equal_delta":statistics.mean(d),"n_dates":len(d)}
 report={"schema":"phase5_sog_posthoc_descriptive_mean_dispersion_decomposition_v1",
   "experiment_id":"EXP-P5-NHL-SOG-HIST-20261114",
   "status":"POSTHOC_DESCRIPTIVE_ABLATION_NOT_PREREGISTERED",
   "source_sealed_forecast_sha256":fs,"source_scored_sha256":ss,
   "matched_rows":len(results),"mean_dispersion_abatement":comparisons,
   "model_metrics":metrics,
   "interpretation_rule":"No statistical promotion, no use of 2026-27 prospective outcomes, no historical quote inference",
   "may_not_be_used_for_confirmation":True}
 out=root/"posthoc_mechanism_decomposition.json"
 data=canon(report)
 with out.open("xb") as f:f.write(data)
 print("PHASE5_POSTHOC_DECOMPOSITION",json.dumps(report,sort_keys=True),flush=True)
 print("PHASE5_POSTHOC_SHA256",sha(data),flush=True)
 return report
if __name__=="__main__":
 ap=argparse.ArgumentParser();ap.add_argument("--root",required=True);a=ap.parse_args()
 calculate(a.root)
