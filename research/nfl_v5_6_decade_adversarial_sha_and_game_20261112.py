"""Adversarial forensic NFL V5.6 FULL 175-week immutable replay auditor.

Independent physical conservation of every persisted shared two-team scenario,
SHA-256 chain for every archived prediction and settlement, never-after-the-fact
factor rollover, QB1-only player contract checks and Monte Carlo marginal invariants.

Original frozen forecast code is not called and no forecasts are modified.
No claim of authenticated historical pregame collection.
"""
from __future__ import annotations
import collections,gzip,hashlib,json,pathlib,time
import numpy as np
BASE=pathlib.Path("reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111")
V5=BASE/"V5_6_FULL_175_WEEK_HISTORY_CALIBRATED_RESEARCH_20261112T162027Z"
V3=BASE/"V3_CONTEXT_10YEAR_FULL_20261111T233046Z"
OUTPUT=BASE/"V5_6_175_WEEK_INDEPENDENT_FULL_AUDIT_20261112"
OUTPUT.mkdir(parents=True,exist_ok=True)
def read(p):
 p=pathlib.Path(p);b=p.read_bytes()
 return json.loads(gzip.decompress(b) if p.suffix==".gz" else b)
def canon(z):return json.dumps(z,sort_keys=True,separators=(",",":"),allow_nan=False,default=str).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def hs(path):return sha(path.read_bytes())
def check(expr,msg):
 if not expr:raise AssertionError("NFL_V56_FULL_FORENSIC_FAIL_CLOSED:"+msg)
def eq(a,b,label):
 check(np.array_equal(a,b),label)
def leq(a,b,label):
 check(np.all(a<=b),label)
def finite(a,label):
 check(a.shape==(128,) and np.isfinite(a).all(),label)
def vector(team,key):return np.asarray(team[key])
def main():
 start=time.monotonic();issues=[];stats=collections.Counter()
 vr=read(V5/"V5_COMPLETE_OR_PARTIAL_RESEARCH_REPORT.json")
 checkpoint=read(V5/"V5_RESUME_CHECKPOINT.json")
 orig=read(V3/"FINAL_V3_VS_V2_10YEAR_REPORT.json")
 method=read(V5/"V5_METHOD_AND_SOURCE_RECEIPT.json")
 check(vr["status"]=="COMPLETE_RESEARCH_ONLY" and vr["weeks_completed"]==175,
       "incomplete_archive")
 check(orig["cycles"]==175 and len(orig["weekly_archive"])==175,
       "bad_original_season_archive")
 check(vr["research_only"] and not vr["production_authorized"],
       "production_promotion_forbidden")
 check(method["research_only"] and not method["production_authorized"],
       "method_prod")
 check(method["baseline_research_sha256"]==orig["result_sha256"],"v3_model_changed")
 check(method["model_sha256"]==hs(pathlib.Path("research/nfl_v5_6_empirical_coverage_joint_model_20261112.py")),
       "model_code_changed_since_prior_freeze")
 check(method["runner_sha256"]==hs(pathlib.Path("research/nfl_v5_6_prior_coverage_decade_replay_20261112.py")),
       "original_runner_code_changed_since_prior_freeze")
 check(vr["method_sha256"]==sha(canon(method)),"method_receipt_inconsistent")
 check(vr["result_sha256"]==sha(canon({k:v for k,v in vr.items() if k!="result_sha256"})),
       "final_report_self_hash")
 check(checkpoint["verified_contiguous_weeks"]==175 and checkpoint["remaining"]==0,
       "checkpoint_incomplete")
 check(len(vr["receipts"])==175,"missing_week_receipts")
 previous=None
 last_sha=None
 last_state=None
 for i,(item,receipt) in enumerate(zip(orig["weekly_archive"],vr["receipts"])):
  y,w=item["year"],item["week"];stem=f"{y}_week_{w:02d}"
  check((receipt["season"],receipt["week"])==(y,w),"receipt_out_of_order_"+stem)
  pp=V5/(stem+"_v5_preweek.json.gz")
  ff=V5/(stem+"_v5_forecast.json.gz")
  ss=V5/(stem+"_v5_settlement.json.gz")
  check(pp.is_file() and ff.is_file() and ss.is_file(),"missing_stage_"+stem)
  ph=hs(pp);fh=hs(ff);sh=hs(ss)
  check(receipt["input_sha256"]==ph and receipt["forecast_sha256"]==fh and
   receipt["settlement_sha256"]==sh,"receipt_SHA_"+stem)
  p,f,z=read(pp),read(ff),read(ss)
  check(z["preweek_sha256"]==ph and z["forecast_sha256"]==fh,
        "settlement_not_bound_to_frozen_forecast_"+stem)
  check((p["season"],p["week"])==(y,w) and (f["season"],f["week"])==(y,w) and
   (z["season"],z["week"])==(y,w),"week_identity_"+stem)
  check(f["input_sha256"]==sha(canon(p)),"forecast_wrong_packet_"+stem)
  check(f["factor_preimage_sha256"]==sha(canon(p["factor_preimage"])),
        "forecast_factor_state_mismatch_"+stem)
  check(previous is None or canon(previous)==canon(p["factor_preimage"]),
        "factor_rollover_not_same_prior_settlement_"+stem)
  check(p["original_v3_prediction_sha256"]==item["forecast_sha256"],
        "original_weekly_v3_sha_"+stem)
  check(p["research_only"] and not p["pregame_certified"] and
        f["research_only"] and not f["pregame_certified"] and
        not f["production_authorized"] and
        f["forecasts_did_not_receive_current_week_settlements"] and
        z["score_only_after_frozen_forecast"],"chrono_provenance_flags_"+stem)
  check(len(p["history"])>0 and
        all((a["season"],a["week"])<(y,w) for a in p["history"]),
        "target_or_future_week_training_"+stem)
  check(all((a["season"],a["week"])<(y,w) for a in p["pbp_prior"]),
        "target_or_future_week_playbyplay_"+stem)
  check(min(a["season"] for a in p["history"])>=max(2014,y-10),
        "beyond_history_cutoff_"+stem)
  stats["frozen_prior_history_rows"]+=len(p["history"])
  stats["frozen_prior_pbp_rows"]+=len(p["pbp_prior"])
  check(z["paired"]==z["all"]["n"],"settlement_denominator_"+stem)
  check(z["paired"]==receipt["paired"],"settlement_receipt_denominator_"+stem)
  # Backfill and rejection of forecast that was accidentally generated
  # for a backup: QB1 eligibility must match the frozen QB1 schedule identity.
  contracted=collections.defaultdict(dict)
  for c in p["contracts"]:
   contracted[(c["game_id"],c["team"],c["player_id"])][c["market"]]=c
  offers=collections.defaultdict(dict)
  check(len(f["offers"])==len(p["contracts"]),"offer_count_"+stem)
  for o in f["offers"]:
   tkey=(o["game_id"],o["team"],o["player_id"])
   key=o["market"]
   check(key in contracted[tkey],"future_offer_player_or_market_"+stem)
   c=contracted[tkey][key]
   check(c["line"]==o["line"] and c["role"]==o["role"] and
    c["opponent"]==o["opponent"],"modified_offer_or_market_"+stem)
   check(key not in offers[tkey],"duplicate_offered_market_"+stem)
   offers[tkey][key]=o
   if o["status"]!="forecast":
    check(o.get("p_over") is None and o.get("p_under") is None,
      "abstention_has_probability_"+stem)
    stats["joint_model_abstentions"]+=1;continue
   d=np.asarray(o["draws"],dtype=float)
   finite(d,"nonfinite_or_wrong_scenario_count_"+stem)
   line=float(o["line"])
   for k,real in (("p_over",np.mean(d>line)),("p_under",np.mean(d<line)),
       ("p_push",np.mean(d==line))):
    check(abs(float(o[k])-real)<1e-12,"market_marginal_not_scenario_"+stem+"_"+k)
   check(abs(o["p_over"]+o["p_under"]+o["p_push"]-1)<1e-12,
      "probabilities_do_not_sum_one_"+stem)
   check(abs(o["predicted_mean"]-np.mean(d))<1e-10,
      "forecast_mean_not_joint_scenario_"+stem)
   check(not o["independent_legacy_model_scenario_substitution"] and
    o["origin"]=="V5_SINGLE_GAME_SIMULATION",
    "legacy_marginal_substituted_"+stem)
   stats["forecast_offers"]+=1
   if key in ("pass attempts","completions","passing yards",
      "qb rushing attempts","qb rushing yards"):
    qb=p["qb1"].get(o["game_id"]+"|"+o["team"])
    check(qb is not None and str(qb["player_id"])==str(o["player_id"]),
       "nonstarter_qb_prop_"+stem)
    stats["eligible_qb1_market_offers"]+=1
   if (key=="tackles + assists" and "solo tackles" in offers[tkey] and
       "tackle assists" in offers[tkey]):
    q,r=offers[tkey]["solo tackles"],offers[tkey]["tackle assists"]
    if q["status"]=="forecast" and r["status"]=="forecast":
     eq(d,np.asarray(q["draws"])+np.asarray(r["draws"]),
        "individual_tackle_breakdown_"+stem)
  for (gid,team,player),markets in offers.items():
   if all(markets.get(key,{}).get("status")=="forecast" for key in
      ("targets","receptions")):
    leq(np.asarray(markets["receptions"]["draws"]),
         np.asarray(markets["targets"]["draws"]),
         "named_receiver_catches_more_than_targets_"+stem)
   if all(markets.get(key,{}).get("status")=="forecast" for key in
      ("pass attempts","completions")):
    leq(np.asarray(markets["completions"]["draws"]),
         np.asarray(markets["pass attempts"]["draws"]),
         "named_qb_more_completions_than_attempts_"+stem)
   if all(markets.get(key,{}).get("status")=="forecast" for key in
      ("solo tackles","tackle assists","tackles + assists")):
    eq(np.asarray(markets["tackles + assists"]["draws"]),
       np.asarray(markets["solo tackles"]["draws"])+
       np.asarray(markets["tackle assists"]["draws"]),
       "individual_combined_tackle_conservation_"+stem)
  # FULL immutable two-team game state vector conservation:
  for gid,g in f["games"].items():
   check(g["single_shared_game_state_verified"] and
         not g["cross_player_fallback_used"],"legacy_game_substituted_"+stem)
   a,b=g["teams"]
   check(a!=b and set(g["joint_state"])==set((a,b)),"not_both_teams_"+stem)
   selection=np.asarray(g["source_profile_indices"])
   check(selection.shape==(128,) and np.isin(selection,[0,1,2]).all(),
        "per_leg_inconsistent_profile_mask_"+stem)
   check(np.allclose(g["whole_game_profile_weights_prior"],
        p["factor_preimage"]["weights"],atol=1e-12),
        "profile_weights_differ_from_week_prior_"+stem)
   stats["two_team_games"]+=1
   stats["joint_game_scenarios"]+=128
   teams=g["joint_state"]
   for team,oppname in ((a,b),(b,a)):
    s=teams[team];opp=teams[oppname]
    vec={k:vector(s,k) for k in s if isinstance(s[k],list)}
    for k,v in vec.items():
     finite(v,"nonfinite_joint_"+stem+"_"+k)
     # Negative receiving/rushing/pass yardage is legal on loss-of-yard plays.
     # Count pools and opportunity budgets must stay nonnegative.
     if "yards" in k:
      stats["negative_yard_component_values"]+=int(np.sum(v<0))
      if np.any(v<0):stats["team_state_negative_yard_components"]+=1
     else:
      check(np.all(v>=0),"negative_count_or_budget_"+stem+"_"+k)
    def v(k):return vec[k]
    eq(v("plays"),v("pass_attempts")+v("rush_attempts"),"team_play_pool_"+stem)
    eq(v("qb1_attempts")+v("nonstarter_attempts"),
       v("pass_attempts"),"qb_distribution_"+stem)
    leq(v("qb1_completions"),v("qb1_attempts"),"qb_complete_cap_"+stem)
    leq(v("team_completions"),v("pass_attempts"),"team_complete_cap_"+stem)
    leq(v("team_target_count"),v("pass_attempts"),"target_cap_"+stem)
    leq(v("team_completions"),v("team_target_count"),"catch_cap_"+stem)
    eq(v("known_targets")+v("unassigned_targets"),
       v("team_target_count"),"known_and_unassigned_targets_"+stem)
    eq(v("known_receptions")+v("unassigned_receptions"),
       v("team_completions"),"known_and_unassigned_receptions_"+stem)
    eq(v("known_receiving_yards")+v("unassigned_receiving_yards"),
       v("team_passing_yards"),"receiving_yard_pool_"+stem)
    eq(v("qb1_known_receiving_yards")+v("qb1_unassigned_receiving_yards"),
       v("qb1_passing_yards"),"qb_receiving_yards_"+stem)
    eq(v("qb1_rush_attempts")+v("known_rb_carries")+
       v("unassigned_carries"),v("rush_attempts"),"rushing_pool_"+stem)
    eq(v("opponent_plays"),vector(opp,"plays"),"cross_def_plays_"+stem)
    eq(v("opponent_rush_attempts"),vector(opp,"rush_attempts"),
       "cross_def_rushing_"+stem)
    eq(v("opponent_completions"),vector(opp,"team_completions"),
       "cross_def_receiving_"+stem)
    eq(v("defensive_eligible_events"),
       vector(opp,"rush_attempts")+vector(opp,"team_completions"),
       "opponent_creates_tackle_opportunities_"+stem)
    eq(v("defensive_tackle_events"),
       v("solo_event_budget")+v("assisted_event_budget"),
       "tackle_event_budget_"+stem)
    leq(v("defensive_tackle_events"),v("defensive_eligible_events"),
       "tackle_budget_cap_"+stem)
    eq(v("credited_solos")+v("unassigned_solo"),v("solo_event_budget"),
       "solo_tackle_credit_pool_"+stem)
    eq(v("credited_assists")+v("unassigned_assist"),
       2*v("assisted_event_budget"),"assist_credit_pool_"+stem)
    if s["eligible_qb1"] is not None:
     scheduled_qb=p["qb1"].get(gid+"|"+team)
     check(scheduled_qb is not None and
           str(scheduled_qb["player_id"])==str(s["eligible_qb1"]),
           "game_qb1_not_frozen_"+stem)
    stats["conserved_team_scenarios"]+=128
  previous=z["factor_weights_updated_only_after_settlement"]
  last_sha=sh;last_state=previous
  stats["settled_paired_contracts"]+=z["paired"]
  stats["settled_weeks"]+=1
  if (i+1)%20==0 or i==174:
   print("V56_FULL_FORENSIC_SHA_AND_GAME_CHECKED",i+1,
    "games",stats["two_team_games"],"game_scenarios",stats["joint_game_scenarios"],
    "seconds",round(time.monotonic()-start,1),flush=True)
 check(stats["settled_paired_contracts"]==407476,
      "full_archive_denominator_not_reconciled")
 check(last_sha==checkpoint["latest_settlement_sha256"],
      "checkpoint_final_settlement_hash")
 check(canon(last_state)==canon(checkpoint["last_prior_only_weight_receipt"]),
      "checkpoint_final_weight_state")
 check(len(vr["receipts"])==stats["settled_weeks"],"receipt_count")
 result={"schema":"NFL_V56_175_WEEK_ADVERSARIAL_FROZEN_GAME_AUDIT_v1",
  "status":"PASS_RESEARCH_ONLY",
  "checked_weeks":175,
  "model_code_frozen":True,
  "original_runner_code_frozen":True,
  "final_report_self_sha256_verified":True,
  "all_individual_preweek_forecast_settlement_SHA_verified":True,
  "no_future_week_data_in_history_packet_verified":True,
  "preweek_weight_equals_previous_actual_settlement_verified":True,
  "qb1_only_all_forecast_markets_checked":True,
  "single_mask_for_both_offenses_and_defenses":True,
  "all_persisted_team_game_state_pool_conservation_checked":True,
  "individual_offered_probability_equals_joint_CDF_checked":True,
  "model_did_not_use_V3_scenario_substitution":True,
  "no_original_source_timestamp_authentication":True,
  "no_prospective_betting_price_validation":True,
  "synthetic_offer_cohort_post_hoc_selection_bias_not_resolved":True,
  "actual_live_per_game_eligibility_not_independently_certified":True,
  "stats":dict(stats),
  "reference_final_report_sha256":vr["result_sha256"],
  "elapsed_seconds":round(time.monotonic()-start,1),
  "notes":[
   "Validates only the frozen recorded inputs and outputs; cannot authenticate external data's original first-seen time.",
   "All 175 weekly forecast packets exclude current/future week rows by season/week labels.",
   "The selected synthetic contract population can depend on postgame observed player appearance, a retrospective cohort bias.",
   "V5.6 fully coherent internal box-score pools do not establish realistic empirical behavior or prop calibration.",
   "V4.1 later post-hoc QB share repair may violate full physical conservation and is not a coherent joint baseline."]}
 path=OUTPUT/"INDEPENDENT_175_WEEK_SHA_CHRONOLOGY_AND_GAME_CONSERVATION.json"
 path.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
 print("V56_FULL_FORENSIC_COMPLETE",json.dumps({
  "status":result["status"],"checked_weeks":175,
  "stats":result["stats"],"receipt":str(path),
  "elapsed_seconds":result["elapsed_seconds"]}),flush=True)
if __name__=="__main__":main()
