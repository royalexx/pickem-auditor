"""Independent read-only Phase5 forensic audit. Does not call production/replay PMF functions.
Uses SciPy probability reference, direct source/forecast fingerprint checks, paired
slate-date/game resampling. No original historical bookmaker offer inference.
"""
import argparse, collections, datetime as dt, hashlib, json, math, pathlib, random, statistics
from scipy.stats import nbinom, poisson

class AuditFailure(RuntimeError): pass
def canon(x):return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def read(path):
 b=pathlib.Path(path).read_bytes()
 return json.loads(b),sha(b)
def jsonl(path):
 b=pathlib.Path(path).read_bytes()
 return [json.loads(r) for r in b.splitlines() if r],sha(b)
def utc(s):
 d=dt.datetime.fromisoformat(s.replace("Z","+00:00"))
 if d.tzinfo is None:raise AuditFailure("NAIVE_DATE")
 return d.astimezone(dt.timezone.utc)
def scipy_pmf(m,k):
 a=m["rate_a"];b=m["rate_b"];pm=m["exposure_pmf"]
 r=m["plugin_rate"];w0=m["plugin_exposure"]
 if k<0:raise AuditFailure("NEGATIVE_COUNT")
 return {"M0":float(poisson.pmf(k,r*w0)),
   "M1":sum(z*float(poisson.pmf(k,r*w)) for w,z in pm),
   "M2":float(nbinom.pmf(k,a,b/(b+w0))),
   "M3":sum(z*float(nbinom.pmf(k,a,b/(b+w))) for w,z in pm),
   "M4":float(nbinom.pmf(k,4.,4/(4+r*w0)))}
def independent_crps(pmf,y):
 mass=0.;total=0.
 for k,x in enumerate(pmf):
  mass+=x
  total+=(mass-float(k>=y))**2
 return total
def delta(rows,mid,metric,unit):
 d=collections.defaultdict(list)
 for r in rows:
  key=r[unit]
  d[key].append(r["scores"][mid][metric]-r["scores"]["M0"][metric])
 return {key:statistics.mean(x) for key,x in d.items()}
def clustered_bootstrap(rows,model,metric,unit,reps=2000):
 d=delta(rows,model,metric,unit)
 vals=list(d.values());n=len(vals);rng=random.Random(4917341+len(model)+len(metric)+len(unit))
 if n<2:return None
 boot=sorted(statistics.mean(rng.choices(vals,k=n)) for _ in range(reps))
 return {"clusters":n,"mean_of_cluster_deltas":statistics.mean(vals),
         "ci95_exploratory":[boot[round(.025*(reps-1))],boot[round(.975*(reps-1))]],
         "lag1_corr":None if n<3 or statistics.pstdev(vals)<1e-12 else
                sum((a-statistics.mean(vals))*(b-statistics.mean(vals)) for a,b in zip(vals[:-1],vals[1:]))/
                max(1e-12,sum((x-statistics.mean(vals))**2 for x in vals))}
def audit(root,source,config):
 root=pathlib.Path(root);source=pathlib.Path(source)
 meta,meta_hash=read(root/"manifest.json")
 report,report_hash=read(root/"score_report.json")
 forecast,fc_hash=jsonl(root/"sealed_forecasts.jsonl")
 scored,sc_hash=jsonl(root/"scored_played.jsonl")
 originals,observations_hash=jsonl(source/"observations.jsonl")
 scheduled,events_hash=jsonl(source/"schedule.jsonl")
 source_manifest,src_hash=read(source/"source_manifest.json")
 config_raw=pathlib.Path(config).read_bytes();config_doc=json.loads(config_raw)
 if meta["obs_input_sha256"]!=observations_hash or meta["schedule_input_sha256"]!=events_hash:
  raise AuditFailure("SOURCE_HASH_MISMATCH")
 if meta["config_sha256"]!=sha(canon(config_doc)):
  raise AuditFailure("CONFIG_HASH_MISMATCH")
 if report["manifest_sha256"]!=meta_hash or report["forecast_sha256"]!=fc_hash:
  raise AuditFailure("SEALED_OUTPUT_HASH_MISMATCH")
 if report["matched_played"]!=len(scored) or report["forecasted"]!=len(forecast):
  raise AuditFailure("DENOMINATOR_DISAGREEMENT")
 if source_manifest["observations_file"]["sha256"]!=observations_hash or source_manifest["schedule_file"]["sha256"]!=events_hash:
  raise AuditFailure("ORIGINAL_SOURCE_MANIFEST_MISMATCH")
 # Independent byte-for-byte verification of the source-native official game-log
 # archive, including every SOG, MM:SS TOI, game and historical team identity.
 source_rows={}
 for receipt in source_manifest["game_log_receipts"]:
  rawpath=source/"raw_official_https"/(receipt["sha256"]+".json")
  raw=rawpath.read_bytes()
  if sha(raw)!=receipt["sha256"]:
   raise AuditFailure("OFFICIAL_RAW_GAME_LOG_SOURCE_SHA_MISMATCH")
  data=json.loads(raw)
  rows=data.get("gameLog",[])
  if len(rows)!=receipt["n"] or not isinstance(rows,list):
   raise AuditFailure("OFFICIAL_RAW_GAME_LOG_ROW_COUNT_MISMATCH")
  for row in rows:
   key=(receipt["pid"],str(row["gameId"]))
   if key in source_rows:
    raise AuditFailure("DUPLICATE_ORIGINAL_GAME_LOG_ROW")
   source_rows[key]=row
 for obs in originals:
  key=(obs["player_id"],obs["game_id"])
  row=source_rows.get(key)
  if row is None:
   raise AuditFailure("DERIVED_PLAYED_GAME_WITHOUT_ORIGINAL_HTTP")
  toi=row.get("toi","")
  try:
   minute,second=map(int,toi.split(":"))
   w=minute+second/60.
  except (ValueError,AttributeError) as exc:
   raise AuditFailure("RAW_OFFICIAL_TOI_FORMAT_INVALID") from exc
  if (row.get("gameDate")!=obs["game_date"]
      or row.get("teamAbbrev")!=obs["team"]
      or row.get("shots")!=obs["sog"]
      or abs(w-obs["toi_minutes"])>1e-10):
   raise AuditFailure("DERIVED_SOG_TOI_TEAM_OR_DATE_DRIFT")
  if obs["position_group"]!=source_manifest["initial_player_ids_with_roles"][obs["player_id"]]:
   raise AuditFailure("HISTORICAL_ROLE_COHORT_DRIFT")
 if not meta["retrospective_source_possession_only"] or not report["original_source_capture_does_not_precede_historical_games"]:
  raise AuditFailure("FALSE_PREGAME_CLAIM")
 valid={"20232024","20242025","20252026"}
 if set(source_manifest["coverage_seasons"])!=valid:raise AuditFailure("SEASON_COVERAGE_MISMATCH")
 by_game={(str(x["game_id"]),str(x["player_id"])):x for x in originals}
 if len(by_game)!=len(originals):raise AuditFailure("DUPLICATE_ORIGINAL_SOURCE")
 by_event={str(x["game_id"]):x for x in scheduled}
 if len(by_event)!=len(scheduled):raise AuditFailure("DUPLICATE_ORIGINAL_EVENT")
 forecast_index={(x["game_id"],x["player_id"]):x for x in forecast}
 fkeys=set(forecast_index)
 skeys={(x["game_id"],x["player_id"]) for x in scored}
 if len(fkeys)!=len(forecast) or len(skeys)!=len(scored) or not skeys<=fkeys:
  raise AuditFailure("DUPLICATE_OR_UNMATCHED_PAIRED_KEYS")
 if any(key not in by_game for key in skeys):raise AuditFailure("SCORE_NOT_OFFICIAL_PLAYED_RESULT")
 for x in scored:
  if by_game[(x["game_id"],x["player_id"])]["sog"]!=x["actual_sog"]:
   raise AuditFailure("OFFICIAL_SOG_JOIN_MISMATCH")
 failures=collections.Counter();maxp=0.;maxscore=0.
 rand=random.Random(1082026);sample=rand.sample(forecast,min(250,len(forecast)))
 for x in forecast:
  if "actual_sog" in x or "actual_toi" in x:raise AuditFailure("TARGET_LABEL_IN_FORECAST")
  if x["season"] not in valid:raise AuditFailure("ILLEGAL_SEASON")
  if x["date"]!=by_event[x["game_id"]]["game_date"]:raise AuditFailure("EVENT_DATE_MISMATCH")
  if not utc(x["fit"]["last_feature_release_bound"])<utc(x["cutoff_utc"]):
   raise AuditFailure("MODEL_FEATURE_RELEASE_VIOLATES_CUTOFF")
  if not x["fit"]["last_played_date"]<x["date"]:
   raise AuditFailure("MODEL_OWN_PRIOR_GAME_DATE_INVALID")
  if len(x["count_pmfs"])!=5:raise AuditFailure("INCOMPLETE_MODEL")
  if any(min(x["count_pmfs"][mid]) < -1e-13 or abs(sum(x["count_pmfs"][mid])-1)>2e-10
         for mid in ("M0","M1","M2","M3","M4")):
   raise AuditFailure("NUMERIC_NORMALIZATION_FAILED")
  if abs(x["fit"]["model_means"]["M0"]-x["fit"]["model_means"]["M4"])>1e-12:
   raise AuditFailure("NB2_DIFFERENT_MEAN")
 for x in sample:
  m=x["distribution_params"]
  if abs(sum(w for _,w in m["exposure_pmf"])-1)>1e-11:
   raise AuditFailure("EXPOSURE_GRID_NOT_NORMALIZED")
  for k in (0,1,2,4,8,12):
   refs=scipy_pmf(m,k)
   for model in refs:
    p=x["count_pmfs"][model][k]
    maxp=max(maxp,abs(p-refs[model]))
    if abs(p-refs[model])>2e-10:
     raise AuditFailure("REFERENCE_PMF_DIVERGENCE:"+str((model,k,refs[model],p)))
 for x in scored:
  orig=forecast_index.get((x["game_id"],x["player_id"]))
  if orig is None:raise AuditFailure("ORIGINAL_FORECAST_MISSING")
  y=x["actual_sog"];m=orig["distribution_params"]
  for model in ("M0","M1","M2","M3","M4"):
   p=orig["count_pmfs"][model]
   yprob=scipy_pmf(m,y)[model]
   if yprob<=0:raise AuditFailure("REFERENCE_OUTCOME_MASS_ZERO")
   logloss=-math.log(yprob)
   maxscore=max(maxscore,abs(logloss-x["scores"][model]["nll"]))
   if abs(logloss-x["scores"][model]["nll"])>1e-8:
    raise AuditFailure("NLL_MISMATCH:"+model)
   if y<len(p):
    owncrps=independent_crps(p,y)
    if abs(owncrps-x["scores"][model]["crps"])>1e-8:
     raise AuditFailure("CRPS_MISMATCH:"+model)
 n=len(scored)
 if n==0:raise AuditFailure("NO_SCORED_EVENTS")
 raw_means={mid:{met:statistics.mean(r["scores"][mid][met] for r in scored) for met in ("crps","nll")}
            for mid in ("M0","M1","M2","M3","M4")}
 for mid in raw_means:
  for metric,num in raw_means[mid].items():
   if abs(num-report["overall"]["models"][mid][metric])>1e-10:
    raise AuditFailure("AGGREGATE_SCORE_MISMATCH")
 cluster={mid:{metric:{unit:clustered_bootstrap(scored,mid,metric,unit)
              for unit in ("date","game_id")} for metric in ("crps","nll")}
          for mid in ("M1","M2","M3","M4")}
 bins={}
 for mid in ("M0","M1","M2","M3","M4"):
  pit=[r["scores"][mid]["pit"] for r in scored]
  bins[mid]={"randomized_PIT_deciles":[sum(.1*i<=v<.1*(i+1) if i<9 else .9<=v<=1 for v in pit)
                                        for i in range(10)],
     "predicted_zero":statistics.mean(r["scores"][mid]["zero"] for r in scored),
     "observed_zero":statistics.mean(r["actual_sog"]==0 for r in scored),
     "predicted_tail6":statistics.mean(r["scores"][mid]["tail6"] for r in scored),
     "observed_tail6":statistics.mean(r["actual_sog"]>=6 for r in scored)}
 bydate=collections.defaultdict(list)
 for r in scored:bydate[r["date"]].append(r)
 model_deltas={}
 for mid in ("M1","M2","M3","M4"):
  model_deltas[mid]={metric:{"overall_matched":raw_means[mid][metric]-raw_means["M0"][metric],
      "date_equal":statistics.mean(statistics.mean(x["scores"][mid][metric]-x["scores"]["M0"][metric] for x in rr)
                                  for rr in bydate.values())}
      for metric in ("crps","nll")}
 receipt={"audit_schema":"phase5_independent_scipy_source_score_audit_v1",
    "status":"PASS_NUMERIC_AND_ARTIFACT_CHECKS_RESEARCH_ONLY",
    "experiment_id":meta["experiment_id"],"run_id":report["run_id"],
    "source_manifest_sha256":src_hash,"source_file_obs_sha256":observations_hash,
    "source_file_schedule_sha256":events_hash,
    "sealed_forecast_sha256":fc_hash,"score_report_sha256":report_hash,
    "scored_outcomes_sha256":sc_hash,
    "matched_player_games":len(scored),"forecasted_player_games":len(forecast),
    "source_native_played_rows_rechecked":len(originals),
    "original_signed_http_log_count_rechecked":len(source_manifest["game_log_receipts"]),
    "distinct_slate_dates":len(bydate),"distinct_games":len({r["game_id"] for r in scored}),
    "independent_scipy_pmf_checked_forecasts":len(sample),
    "reference_max_abs_pmf_error":maxp,"reference_max_abs_nll_error":maxscore,
    "recomputed_matched_scores":raw_means,"paired_deltas":model_deltas,
    "clustered_uncertainty":cluster,"calibration":bins,
    "source_limitations":["retrospective re-fetch not certified as-of pregame",
       "data freeze/cutoff only event-time proxy","no authenticated 2023-26 original sportsbook offers",
       "opening day 2023 108-player F/D cohort, not full NHL population"],
    "inference_claims":"none: exploratory date/game bootstrap sensitivity only"}
 out=root/"independent_scipy_adversarial_audit.json"
 with out.open("xb") as f:f.write(canon(receipt))
 return receipt
if __name__=="__main__":
 a=argparse.ArgumentParser()
 a.add_argument("--root",required=True);a.add_argument("--source",required=True)
 a.add_argument("--config",required=True)
 args=a.parse_args()
 print(json.dumps(audit(args.root,args.source,args.config),sort_keys=True))
