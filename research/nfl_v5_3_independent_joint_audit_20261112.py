"""Independent archived-forecast V5 shared-game audit.
Does NOT invoke the V5 model or reuse its validator. Verifies frozen hashes,
per-scenario two-team conservation, prop CDF consistency, accounted player
opportunity caps and no legacy distribution substitutions.
"""
from __future__ import annotations
import argparse,collections,gzip,hashlib,json,pathlib
import numpy as np
ROOT=pathlib.Path.cwd()
BASE=ROOT/"reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111"
def read(p):
 b=p.read_bytes()
 return json.loads(gzip.decompress(b) if p.suffix==".gz" else b)
def canon(v):return json.dumps(v,sort_keys=True,separators=(",",":"),allow_nan=False,default=str).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def check(msg,passed,issues):
 if not passed:issues.append(msg)
def independent_game_check(game,offers,issues):
 names=game["teams"]
 check("two_distinct_teams",len(names)==2 and names[0]!=names[1],issues)
 if len(names)!=2:return
 n=len(game["source_profile_indices"])
 check("single_mask_128",n==128,issues)
 choice=game["source_profile_indices"]
 check("mask_only_three_profiles",set(choice).issubset({0,1,2}),issues)
 check("one_game_distribution",bool(game.get("single_shared_game_state_verified")),issues)
 check("no_player_level_fallback",game.get("cross_player_fallback_used") is False,issues)
 S={t:{key:(np.asarray(v) if isinstance(v,list) else v)
      for key,v in game["joint_state"][t].items()} for t in names}
 for team in names:
  other=names[1] if team==names[0] else names[0]
  a=S[team];b=S[other]
  def eq(left,right,label):
   check(team+"_"+label,np.array_equal(left,right),issues)
  def leq(left,right,label):
   check(team+"_"+label,np.all(left<=right),issues)
  for key,val in a.items():
   if isinstance(val,np.ndarray):
    check(team+"_"+key+"_shape",val.shape==(n,),issues)
    check(team+"_"+key+"_finite",np.isfinite(val).all(),issues)
  eq(a["plays"],a["pass_attempts"]+a["rush_attempts"],"offensive_plays")
  eq(a["qb1_attempts"]+a["nonstarter_attempts"],a["pass_attempts"],"QB_pass_allocation")
  leq(a["qb1_completions"],a["qb1_attempts"],"QB_completion_cap")
  eq(a["known_targets"]+a["unassigned_targets"],a["team_target_count"],"target_allocation")
  leq(a["team_target_count"],a["pass_attempts"],"pass_attempt_limit")
  eq(a["known_receptions"]+a["unassigned_receptions"],a["team_completions"],"receptions")
  leq(a["team_completions"],a["team_target_count"],"reception_cap")
  eq(a["known_receiving_yards"]+a["unassigned_receiving_yards"],
      a["team_passing_yards"],"passing_yards")
  eq(a["qb1_known_receiving_yards"]+a["qb1_unassigned_receiving_yards"],
      a["qb1_passing_yards"],"QB_passing_yards")
  eq(a["qb1_rush_attempts"]+a["known_rb_carries"]+a["unassigned_carries"],
      a["rush_attempts"],"rush_pool")
  eq(a["opponent_plays"],b["plays"],"defense_same_plays_as_opponent")
  eq(a["opponent_pass_attempts"],b["pass_attempts"],"defense_same_passing")
  eq(a["opponent_rush_attempts"],b["rush_attempts"],"defense_same_rushing")
  eq(a["opponent_completions"],b["team_completions"],"defense_same_completions")
  eq(a["opponent_auxiliary_credit_opportunities"],
      b["auxiliary_credited_tackle_opportunities"],"auxiliary_opponent_source")
  eq(a["defensive_eligible_events"],
      b["rush_attempts"]+b["team_completions"]+
      b["auxiliary_credited_tackle_opportunities"],"tackle_events_from_offense")
  leq(a["defensive_tackle_events"],a["defensive_eligible_events"],"defense_no_more_events")
  eq(a["defensive_tackle_events"],
      a["solo_event_budget"]+a["assisted_event_budget"],"defense_solo_or_assist_event")
  eq(a["credited_solos"]+a["unassigned_solo"],
      a["solo_event_budget"],"defense_solo_credits")
  eq(a["credited_assists"]+a["unassigned_assist"],
      2*a["assisted_event_budget"],"defense_assist_credits")
  if "scenario_active_defender_count" in a:
   leq(a["scenario_active_defender_count"],
       a["source_roster_defender_count"],"eligible_defender_count")
  for key in ("known_targets","known_receptions","known_rb_carries",
      "credited_solos","credited_assists"):
   sub=[]
   for f in offers:
    if f["team"]!=team or f["status"]!="forecast":continue
    if key=="known_targets" and f["market"]!="targets":continue
    if key=="known_receptions" and f["market"]!="receptions":continue
    if key=="known_rb_carries" and f["market"]!="carries":continue
    if key=="credited_solos" and f["market"]!="solo tackles":continue
    if key=="credited_assists" and f["market"]!="tackle assists":continue
    sub.append(np.asarray(f["draws"]))
   if sub:
    leq(np.sum(sub,axis=0),a[key],"offered_"+key+"_not_exceed_game_pool")
  for f in offers:
   if f["team"]!=team or f["status"]!="forecast":continue
   qb=a["eligible_qb1"]
   field={"pass attempts":"qb1_attempts","completions":"qb1_completions",
     "passing yards":"qb1_passing_yards","qb rushing attempts":"qb1_rush_attempts",
     "qb rushing yards":"qb1_rushing_yards"}.get(f["market"])
   if field and qb==f["player_id"]:
    eq(np.asarray(f["draws"]),a[field],"QB_prop_equals_one_game_state")
def audit(folder,out):
 issues=[];counts=collections.Counter();weeks=[];sha_log=[]
 for path in sorted(folder.glob("*_v5_forecast.json.gz")):
  stem=path.name.split("_v5_forecast")[0]
  pre=folder/(stem+"_v5_preweek.json.gz")
  sett=folder/(stem+"_v5_settlement.json.gz")
  if not pre.exists() or not sett.exists():
   issues.append(stem+"_missing_preweek_or_settlement");continue
  p=read(pre);f=read(path);s=read(sett)
  check(stem+"_input_binding",f["input_sha256"]==sha(canon(p)),issues)
  check(stem+"_prior_factor_binding",f["factor_preimage_sha256"]==sha(canon(p["factor_preimage"])),issues)
  if "tilt_preimage" in p:
   check(stem+"_prior_tilt_binding",
     f.get("tilt_preimage_sha256")==sha(canon(p["tilt_preimage"])),issues)
   check(stem+"_historical_v4_forecast_receipt",
     f.get("historical_reference_source_sha256")==
       p.get("v4_anchor_forecast_sha256"),issues)
  check(stem+"_settlement_binding",s["forecast_sha256"]==sha(path.read_bytes()),issues)
  check(stem+"_no_future_history",
        all(g["season"]<p["season"] or(g["season"]==p["season"] and g["week"]<p["week"])
            for g in p["history"]),issues)
  check(stem+"_no_future_pbp",
        all(g["season"]<p["season"] or(g["season"]==p["season"] and g["week"]<p["week"])
            for g in p["pbp_prior"]),issues)
  per=collections.defaultdict(list)
  for z in f["offers"]:per[z["game_id"]].append(z)
  for gid,game in f["games"].items():
   before=len(issues)
   independent_game_check(game,per[gid],issues)
   counts["game_scenarios"]+=len(game["source_profile_indices"])
   counts["game_integrity_failures"]+=int(len(issues)>before)
  counts["games"]+=len(f["games"]);counts["weeks"]+=1
  counts["offers"]+=len(f["offers"]);counts["paired"]+=s["paired"]
  for z in f["offers"]:
   if z["status"]!="forecast":
    counts["abstained"]+=1;continue
   draws=np.asarray(z["draws"],dtype=float)
   n=len(draws)
   if n==0:issues.append(stem+"_empty_draws");continue
   qover=float((draws>z["line"]).mean())
   qunder=float((draws<z["line"]).mean())
   qpush=float((draws==z["line"]).mean())
   if not(np.isclose(qover,z["p_over"]) and np.isclose(qunder,z["p_under"])
          and np.isclose(qpush,z["p_push"])
          and np.isclose(qover+qunder+qpush,1)):
    issues.append(stem+"_bad_prop_cdf_"+z["game_id"]+"_"+z["market"])
   if z.get("independent_legacy_model_scenario_substitution") is not False:
    issues.append(stem+"_legacy_substitution_used")
   if z.get("posthoc_probability_override") is True:
    issues.append(stem+"_posthoc_probability_override")
   if "full_game_strength_candidates_q_over" in z:
    check(stem+"_tilt_candidates",len(z["full_game_strength_candidates_q_over"])==3,
      issues)
   counts["forecast_contracts"]+=1
  weeks.append({"stem":stem,"paired":s["paired"],"issues_total":len(issues)})
  sha_log.append({"stem":stem,"forecast_sha256":sha(path.read_bytes()),
                 "settlement_sha256":sha(sett.read_bytes())})
 result={"status":"PASS" if not issues else "FAIL","research_only":True,
     "synthetic_lines":True,"source_original_pregame_verified":False,
     "counts":dict(counts),"issue_count":len(issues),"issues":issues[:100],
     "weekly":weeks,"hashes":sha_log}
 out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(result,indent=2,sort_keys=True))
 print("V5_INDEPENDENT_SCENARIO_AUDIT",json.dumps({k:v for k,v in result.items()
   if k not in ("hashes","weekly")},sort_keys=True),flush=True)
 return result
if __name__=="__main__":
 parser=argparse.ArgumentParser()
 parser.add_argument("--study",required=True,type=pathlib.Path)
 parser.add_argument("--out",required=True,type=pathlib.Path)
 args=parser.parse_args()
 r=audit(args.study,args.out)
 if r["status"]!="PASS":raise SystemExit(2)
