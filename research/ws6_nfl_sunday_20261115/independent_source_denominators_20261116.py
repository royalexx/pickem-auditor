"""Independent source and forecast coverage census, no scoring model reuse."""
import collections,datetime as dt,hashlib,json,math,pathlib
from research.ws6_nfl_sunday_20261115.independent_postgame_20261116 import frozen_write,dump
BASE=pathlib.Path("reports/nfl_20261115_prospective")
p=BASE/"ensemble_20261115_research_shadow/comparison_original_quotes_1845.jsonl"
o=BASE/"ws6_independent_postgame_20261116_v1/source_denominators_v1.json"
data=p.read_bytes(); rr=[json.loads(x) for x in data.splitlines() if x]
assert len(rr)==1845
boolkeys=["source_identity_verified","research_shadow_eligible",
          "provider_metadata_identity_certified","product_rules_certified"]
counts={k:collections.Counter(str(r.get(k,"ABSENT")) for r in rr) for k in boolkeys}
unique={"quote_ids":len(set(r.get("quote_id") for r in rr)),
        "candidate_ids":len(set(r.get("candidate_id") for r in rr)),
        "players":len(set(r.get("player") for r in rr)),
        "events":len(set(r.get("event_id") for r in rr if r.get("event_id"))),
        "source_observations":len(rr)}
by_book=collections.Counter(r.get("book") for r in rr)
by_market=collections.Counter(r.get("stat") for r in rr)
pair_obs=collections.Counter()
forecast_status=collections.Counter()
rejection=collections.Counter()
timeproblems=[]
for r in rr:
    k=(r.get("event_id"),r.get("player"),r.get("stat"),r.get("line"))
    pair_obs[k]+=1
    if r.get("source_identity_verified") is not True:rejection["SOURCE_IDENTITY_NOT_VERIFIED"]+=1
    if r.get("research_shadow_eligible") is not True:rejection["RESEARCH_SHADOW_NOT_ELIGIBLE"]+=1
    if r.get("provider_metadata_identity_certified") is not True:rejection["ORIGINAL_PROVIDER_METADATA_NOT_CERTIFIED"]+=1
    if r.get("product_rules_certified") is not True:rejection["PRODUCT_RULES_NOT_CERTIFIED"]+=1
    for m,d in r.get("models",{}).items():
        at=d.get("forecast_at");kick=r.get("kickoff_utc")
        try:
            xx=dt.datetime.fromisoformat(str(at).replace("Z","+00:00"))
            kk=dt.datetime.fromisoformat(str(kick).replace("Z","+00:00"))
            if xx.tzinfo is None or kk.tzinfo is None:st="NAIVE_TIMESTAMP"
            else:st="TIMELY" if xx<kk else "POST_KICKOFF"
        except Exception:st="INVALID_TIMESTAMP"
        forecast_status[(m,st)]+=1
        if st!="TIMELY" and len(timeproblems)<30:
            timeproblems.append({"quote_id":r.get("quote_id"),"model":m,
                "forecast_at":at,"kickoff_utc":kick,"failure":st})
out={"schema":"WS6_INDEPENDENT_QUOTE_MODEL_DENOMINATORS_V1","status":"RESEARCH_SOURCE_CENSUS_NOT_MARKET_CERTIFICATION",
     "raw_ledger_sha256":hashlib.sha256(data).hexdigest(),
     "quotes":unique,"boolean_flags":{k:dict(v) for k,v in counts.items()},
     "book_observations":dict(by_book),"markets":dict(by_market),
     "contract_unique_by_event_player_stat_line":len(pair_obs),
     "same_contract_book_duplicate_observations":len(rr)-len(pair_obs),
     "original_source_failure_flags_not_disjoint":dict(rejection),
     "actual_model_forecast_timestamps":{f"{m}|{status}":v for (m,status),v in sorted(forecast_status.items())},
     "timestamp_failure_examples":timeproblems,
     "cautions":["Boolean source flags refer to recorded original audit, not an independent retest of provider offer equivalence.",
       "No payout or no-vig economics certified.","Observed forecasts and attempted original quote observations have distinct denominators.",
       "A model may be absent because it explicitly abstained rather than failed source certification.",
       "Source rejection flags overlap; do not add them as unique failed quotes."]}
dump(o,out)
print(json.dumps({"sha256":hashlib.sha256(o.read_bytes()).hexdigest(),
 "quote_counts":unique,"flags":out["boolean_flags"],"books":by_book,"markets":by_market,
 "unique_contract_lines":len(pair_obs),"book_duplicate_excess":len(rr)-len(pair_obs),
 "source_failure_flags":dict(rejection),"timestamp":out["actual_model_forecast_timestamps"],
 "timestamp_examples":timeproblems},default=dict))
