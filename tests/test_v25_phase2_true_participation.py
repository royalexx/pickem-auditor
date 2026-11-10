"""Phase 2 actual participation/role/previous snaps research integrity tests.

No retrospective 2024 real-world historical record in fixtures is called
'pregame certified'. Only earlier season/week feature rows are admissible.
"""
from __future__ import annotations

from copy import deepcopy
import unittest
import numpy as np

from scripts.v25_phase2_participation_snap_forecast import (
    _asof_exposure_validation, _lagged_roster_candidates, _one_team,
)
from scripts.v25_phase2_participation_source_bridge import build_asof_context

ROLES=("WR","TE","RB")
P={
 "schema":"v25-p2-target-only-asof-week-v1","week":3,
 "lagged_roster_context":[
  {"season":2024,"week":2,"team":"A","player_id":"p1","role":"WR",
   "status":"ACT","source_claim":"prior_week_archive_unverified_original_capture"},
 ],
 "lagged_snap_context":[
  {"season":2024,"week":2,"team":"A","player_id":"p1","role":"WR",
   "offense_snaps":32.,"offense_pct":.5,"team_plays":64.,
   "source_claim":"previously_finished_game_postgame_exposure"},
 ],
 "dated_pregame_injury_context":[],
}
def prior():
 return {
  role:{"p_appearance":.78,"mean_snap_share":.5,
        "target_rate_per_snap":.11,
        "active_zero_target_frequency":.13,
        "matched_past_snap_records":200}
  for role in ROLES
 }

class TestParticipationAsOfSources(unittest.TestCase):
 def test_past_only_roster_and_offense_snaps(self):
  roster,snaps,inj=_asof_exposure_validation(deepcopy(P))
  self.assertEqual(len(roster),1)
  self.assertEqual(len(snaps),1)
  self.assertEqual(len(inj),0)

 def test_current_week_roster_is_future_source(self):
  p=deepcopy(P)
  p["lagged_roster_context"][0]["week"]=3
  with self.assertRaisesRegex(ValueError,"current_or_future_roster_snapshot"):
   _asof_exposure_validation(p)

 def test_future_week_snap_is_hard_reject(self):
  p=deepcopy(P)
  p["lagged_snap_context"][0]["week"]=4
  with self.assertRaisesRegex(ValueError,"current_or_future_snap"):
   _asof_exposure_validation(p)

 def test_zero_snap_is_distinct_from_zero_target_and_routes(self):
  p=deepcopy(P)
  p["lagged_snap_context"][0]["offense_snaps"]=0.
  p["lagged_snap_context"][0]["offense_pct"]=0.
  self.assertEqual(_asof_exposure_validation(p)[1][0]["offense_snaps"],0.)
  p["lagged_snap_context"][0]["routes"]=30
  with self.assertRaisesRegex(ValueError,"lagged_snap_contract"):
   _asof_exposure_validation(p)

 def test_injury_after_actual_game_freeze_is_rejected(self):
  p=deepcopy(P)
  p["dated_pregame_injury_context"].append({
   "week":3,"event_id":"evt","team":"A","player_id":"p1","role":"WR",
   "report_status":"Out",
   "date_modified":"2024-09-21T19:00:00+00:00",
   "freeze_at":"2024-09-21T17:00:00+00:00",
   "source_claim":"retrospectively_retrieved_dated_report_not_original_capture",
  })
  with self.assertRaisesRegex(ValueError,"injury_after_forecast"):
   _asof_exposure_validation(p)

 def test_posthoc_injury_is_never_claimed_certified(self):
  p=deepcopy(P)
  p["dated_pregame_injury_context"].append({
   "week":3,"event_id":"evt","team":"A","player_id":"p1","role":"WR",
   "report_status":"Out",
   "date_modified":"2024-09-21T15:00:00+00:00",
   "freeze_at":"2024-09-21T17:00:00+00:00",
   "source_claim":"retrospectively_retrieved_dated_report_not_original_capture",
  })
  self.assertEqual(len(_asof_exposure_validation(p)[2]),1)
  p["dated_pregame_injury_context"][0]["source_claim"]="verified_original_capture"
  with self.assertRaisesRegex(ValueError,"current_injury_must_be_downgraded"):
   _asof_exposure_validation(p)

 def test_latest_cross_team_roster_cannot_persist_on_old_team(self):
  rows=deepcopy(P["lagged_roster_context"])
  rows.append({**rows[0],"team":"B","week":2})
  rows[0]["week"]=1
  pools,_=_lagged_roster_candidates({"week":3},rows,[])
  self.assertNotIn("p1",pools.get("A",{}))
  self.assertIn("p1",pools["B"])

 def test_sampled_attempts_conserved_and_active_zero_separate_from_out(self):
  hist=[]
  for k in range(8):
   hist.append({"season":2023,"week":k+1,
                "team":"A","event_id":"game"+str(k),
                "pass_attempts":32+k%3,
                "players":{"p1":{"role":"WR","targets":6},
                           "p2":{"role":"TE","targets":3},
                           "p3":{"role":"RB","targets":3}}})
  players={}
  for role,pid in (("WR","p1"),("TE","p2"),("RB","p3")):
   players[( "A",pid)]=[{
    "season":2023,"week":7,"team":"A",
    "player_id":pid,"role":role,"offense_snaps":30,
    "offense_pct":.5,"team_plays":60,"targets":2,
    "team_pass_attempts":33}]
  roster={p:{"player_id":p,"role":role,"status":"ACT",
             "stale_weeks":1,"source":"lagged_roster_only"}
          for p,role in (("p1","WR"),("p2","TE"),("p3","RB"))}
  a=_one_team("A",[29]*64,roster,{},players,prior(),hist,122,3,"event","participation_snap")
  b=_one_team("A",[29]*64,roster,{},players,prior(),hist,122,3,"event","participation_no_hurdle")
  for model in (a,b):
   self.assertTrue(model["conservation_ok"])
   self.assertTrue(model["snap_exposure_not_routes"])
   for i in range(64):
    self.assertEqual(
     sum(x[i] for x in model["player_targets"].values())+
      model["unknown_receiver_targets"][i]+model["non_target_attempts"][i],29)
    for p in model["player_targets"]:
     self.assertLessEqual(model["player_targets"][p][i],model["offensive_plays"][i])
  self.assertNotEqual(a["player_targets"],b["player_targets"])
  self.assertFalse(a["player_activity_diagnostics"]["p1"]["source_certified"])

 def test_builder_does_not_send_current_week_rosters_snaps(self):
  data={
   "rosters":[
    {**P["lagged_roster_context"][0],"week":2},
    {**P["lagged_roster_context"][0],"week":3}],
   "snaps":[
    {**P["lagged_snap_context"][0],"week":2},
    {**P["lagged_snap_context"][0],"week":3}],
   "injuries":{},
   "cutoffs":{(3,"evt","A"):__import__("datetime").datetime(
      2024,9,21,17,tzinfo=__import__("datetime").timezone.utc)},
  }
  c=build_asof_context(data,3,[{"event_id":"evt","team":"A","opponent":"B","week":3}])
  self.assertEqual(len(c["lagged_roster_context"]),1)
  self.assertEqual(len(c["lagged_snap_context"]),1)
  self.assertEqual(c["dated_pregame_injury_context"],[])

if __name__=="__main__":
 unittest.main()
