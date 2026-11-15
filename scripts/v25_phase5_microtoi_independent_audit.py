# INDEPENDENT CHECK: fresh comparison code, no import from candidate/replay modules.
# Original 2026 retrieval is NOT historical authenticated pregame source.
from pathlib import Path
import json,hashlib,datetime as dt,math,collections
from scipy.stats import poisson,nbinom
root=Path("reports/phase5_nhl_sog_historical/20261114T222036350236Z")
orig=root/"replay_20261114T222703744622Z/4c5d4d3f4dc840db3b42"
candidates=sorted(root.glob("microtoi_posthoc_sensitivity_v2_*/**/phase5_microtoi_sensitivity_receipt.json"))
assert len(candidates)==1,("NEED_EXACTLY_ONE_CANDIDATE_RECEIPT",len(candidates))
cand=candidates[0].parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
known={
 "obs":"d321e8f3af9d127589c6cbcb9e9477717ebd61eb062f30e587a7a9268468671a",
 "sched":"d9139bffcdeea57a37068b364a58621e20fdd02833b47bb71a3fbdec64a9aa1e",
 "sealed":"12c267b7ca629d75a69f8cfd429a5a55e8510f4be7cb914ec5860c18097553dc",
 "scored":"75f1343ca3125cd9665f1ff917b91268c9aa8cb1d78223d7c47842ba79568629",
}
assert sha(root/"observations.jsonl")==known["obs"]
assert sha(root/"schedule.jsonl")==known["sched"]
assert sha(orig/"sealed_forecasts.jsonl")==known["sealed"]
assert sha(orig/"scored_played.jsonl")==known["scored"]
rec=json.loads((cand/"phase5_microtoi_sensitivity_receipt.json").read_text())
assert rec["prospective_40_date_trial"]=="UNCHANGED"
assert rec["inference_gate"]=="CLOSED_NO_PROMOTION_NO_MARKET_ASSERTION"
def jsonls(path):
    with path.open(encoding="utf8") as f:
        for line in f:
            if line.strip():yield json.loads(line)
def structural(f):
    return (f["fit"],f["distribution_params"],f["count_pmfs"],
            f["game_id"],f["player_id"],f["date"],f["season"],f["team"],f["cutoff_utc"])
old={}
for r in jsonls(orig/"sealed_forecasts.jsonl"):
    k=(r["game_id"],r["player_id"])
    assert k not in old
    old[k]=structural(r)
added=[]
common=0
by_season=collections.Counter()
for r in jsonls(cand/"sealed_forecasts.jsonl"):
    k=(r["game_id"],r["player_id"])
    assert "actual_sog" not in r and "actual_toi" not in r
    when=dt.datetime.fromisoformat(r["cutoff_utc"].replace("Z","+00:00"))
    avail=dt.datetime.fromisoformat(r["fit"]["last_feature_release_bound"].replace("Z","+00:00"))
    assert avail<when,"SOURCE_TIME_LEAKAGE"
    if k in old:
        assert structural(r)==old.pop(k),"SHARED_FORECAST_CHANGED"
        common+=1
    else:
        added.append(r);by_season[r["season"]]+=1
        assert r["date"]>"2026-03-03","NEW_COHORT_BEFORE_MICRO_TOI_OBSERVED"
assert not old,"ORIGINAL_FORECAST_LOST"
models=("M0","M1","M2","M3","M4")
absmax=0.
tested=0
for r in added:
    m=r["distribution_params"]
    rate=m["plugin_rate"];w0=m["plugin_exposure"]
    a=m["rate_a"];b=m["rate_b"];pi=m["exposure_pmf"]
    for k in (0,1,2,5,8):
        expected={
          "M0":poisson.pmf(k,rate*w0),
          "M1":sum(weight*poisson.pmf(k,rate*w) for w,weight in pi),
          "M2":nbinom.pmf(k,a,b/(b+w0)),
          "M3":sum(weight*nbinom.pmf(k,a,b/(b+w)) for w,weight in pi),
          "M4":nbinom.pmf(k,4,4/(4+rate*w0)),
        }
        for model in models:
            err=abs(float(expected[model])-r["count_pmfs"][model][k])
            absmax=max(absmax,err)
            assert err<1e-10,(model,k,err)
        tested+=1
    for model in models:
        assert abs(math.fsum(r["count_pmfs"][model])-1)<2e-10
        assert all(v>=0 and math.isfinite(v) for v in r["count_pmfs"][model])
new_keys={(r["game_id"],r["player_id"]) for r in added}
new_score=[]
for r in jsonls(cand/"scored_played.jsonl"):
    if (r["game_id"],r["player_id"]) in new_keys:new_score.append(r)
check_nll=0.
forecast_map={(r["game_id"],r["player_id"]):r for r in added}
for r in new_score:
    src=forecast_map[(r["game_id"],r["player_id"])]
    for model in models:
        p=src["count_pmfs"][model][r["actual_sog"]]
        err=abs(-math.log(max(p,1e-300))-r["scores"][model]["nll"])
        check_nll=max(check_nll,err)
        assert err<1e-9,(model,err)
assert len(new_score)==rec["cohort_comparison"]["added_scored"]
assert rec["cohort_comparison"]["identical_common_scored"]==17723
receipt={
 "schema":"independent_phase5_microtoi_pairwise_source_scipy_audit_v1",
 "status":"PASS_RESEARCH_ONLY" if absmax<1e-10 else "FAIL",
 "source_class":"november_2026_retrieval_no_original_pregame_authentication",
 "frozen_original_sealed_sha":known["sealed"],
 "candidate_sealed_sha":sha(cand/"sealed_forecasts.jsonl"),
 "candidate_scored_sha":sha(cand/"scored_played.jsonl"),
 "candidate_run":rec["candidate_run_id"],
 "original_common_forecasts_byte_equivalent_fields":common,
 "added_forecasts":len(added),
 "added_played_scored":len(new_score),
 "added_forecasts_by_season":dict(by_season),
 "scipy_PMF_reference_checks":tested*len(models),
 "max_abs_pmf_difference":absmax,
 "max_abs_added_nll_difference":check_nll,
 "date_guard":"added dates > March 3 2026",
 "prospective_trial":"unchanged",
 "promotion":"blocked",
 "limitations":["posthoc source-based repair","retrospective event-time only",
                "no original pregame odds","no untouched future evaluation"]
}
out=cand/"independent_microtoi_paired_numerical_audit_v1.json"
payload=json.dumps(receipt,sort_keys=True,separators=(",",":")).encode()
if out.exists():
    assert out.read_bytes()==payload,"IMMUTABLE_AUDIT_RECEIPT_CHANGED"
else:
    with out.open("xb") as f:f.write(payload)
print("INDEPENDENT_MICROTOI_AUDIT",json.dumps(receipt,sort_keys=True),flush=True)
print("INDEPENDENT_MICROTOI_AUDIT_SHA256",sha(out),flush=True)
