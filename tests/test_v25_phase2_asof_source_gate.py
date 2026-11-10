"""Adversarial source/lineage checks for actual Phase 2 participation repair."""
from __future__ import annotations

from copy import deepcopy
import unittest

from scripts.v25_phase2_asof_participation_source_gate import (
    SourceGateError,validate_asof_roster,validate_lagged_participation,
)

SHA="a"*64
BASE={
  "event_id":"2024_01_BAL_KC","team_id":"BAL","freeze_at":"2024-09-05T22:00:00Z",
  "kickoff_at":"2024-09-06T00:20:00Z",
  "expected_players":["00-0030001","00-0030002","00-0030003"],
}
def status(player="00-0030001",availability="available"):
 return dict(
   event_id=BASE["event_id"],team_id=BASE["team_id"],
   player_id=player,role="WR",availability=availability,
   source_type="official_injury_report",
   published_at="2024-09-05T17:00:00Z",
   captured_at="2024-09-05T17:15:00Z",
   content_sha256=SHA,retro_archive_only=False)

def prior(rowtype="snap_counts"):
 return dict(
  player_id="00-0030001",team_id="BAL",event_id="2023_18_BAL_PIT",
  event_start_at="2024-01-06T20:00:00Z",
  result_available_at="2024-01-07T04:00:00Z",
  exposure_kind=rowtype,offense_snaps=43,
  routes=None if rowtype=="snap_counts" else 30,
  source_sha256=SHA,source_captured_at="2024-01-07T05:00:00Z")


class TestPhase2AsOfParticipation(unittest.TestCase):
 def test_no_roster_receipt_is_abstention_not_false_under(self):
  out=validate_asof_roster(**BASE,roster_events=[])
  self.assertEqual(out["n_unknown"],3)
  self.assertFalse(any(p["prediction_eligible"] for p in out["roster"]))
  self.assertFalse(out["invented_activity_from_targets"])

 def test_actual_pregame_released_status_only_and_weak_unknowns(self):
  s=validate_asof_roster(**BASE,roster_events=[
       status(),status("00-0030002","verified_out")])
  self.assertEqual([x["status"] for x in s["roster"]],
                   ["available","verified_out","unknown"])
  self.assertEqual(s["n_explicit_out"],1)
  self.assertEqual(s["n_verified"],2)
  self.assertFalse(s["roster"][-1]["prediction_eligible"])

 def test_future_published_source_rejected(self):
  x=status()
  x["published_at"]="2024-09-05T23:00:00Z"
  x["captured_at"]="2024-09-05T23:01:00Z"
  with self.assertRaisesRegex(SourceGateError,"future_published_roster_status"):
   validate_asof_roster(**BASE,roster_events=[x])

 def test_retroactive_source_capture_never_claims_pregame(self):
  x=status()
  x["captured_at"]="2026-11-10T00:00:00Z"
  with self.assertRaisesRegex(SourceGateError,"retro_captured_roster_cannot_claim_asof"):
   validate_asof_roster(**BASE,roster_events=[x])
  s=validate_asof_roster(**BASE,roster_events=[x],strict_capture=False)
  self.assertEqual(s["n_unknown"],3)
  self.assertEqual(s["rejected_source_reasons"],
                   {"retrospective_record_not_verified_at_forecast":1})

 def test_historical_weekly_roster_without_timestamp_not_evidence(self):
  x=status()
  x["published_at"]=None
  with self.assertRaisesRegex(SourceGateError,"timestamp_missing"):
   validate_asof_roster(**BASE,roster_events=[x])

 def test_synthetic_backdated_timestamp_does_not_override_archive_flag(self):
  x=status()
  x["retro_archive_only"]=True
  with self.assertRaisesRegex(SourceGateError,"retro_archive_not_source_certificate"):
   validate_asof_roster(**BASE,roster_events=[x])

 def test_identical_roster_observations_contradicting_abstain(self):
  a=status(availability="available")
  b=status(availability="verified_out")
  with self.assertRaisesRegex(SourceGateError,"same_timestamp_contradictory"):
   validate_asof_roster(**BASE,roster_events=[a,b])

 def test_current_game_snaps_never_in_forecast(self):
  row=prior()
  row["event_id"]=BASE["event_id"]
  with self.assertRaisesRegex(SourceGateError,"current_game_realized_exposure"):
   validate_lagged_participation(event_id=BASE["event_id"],
       freeze_at=BASE["freeze_at"],history=[row])

 def test_future_snapshot_of_old_game_still_unavailable(self):
  row=prior()
  row["source_captured_at"]="2026-11-10T00:00:00Z"
  with self.assertRaisesRegex(SourceGateError,"not_owned_at_freeze"):
   validate_lagged_participation(event_id=BASE["event_id"],
       freeze_at=BASE["freeze_at"],history=[row])

 def test_previous_snaps_are_not_receiver_routes(self):
  good=validate_lagged_participation(
       event_id=BASE["event_id"],freeze_at=BASE["freeze_at"],
       history=[prior()])
  self.assertEqual(good["prior_snap_exposures"],1)
  self.assertEqual(good["prior_verified_routes"],0)
  self.assertFalse(good["route_challenger_eligible"])
  bad=prior()
  bad["routes"]=25
  with self.assertRaisesRegex(SourceGateError,"snap_count_mislabeled_as_routes"):
   validate_lagged_participation(event_id=BASE["event_id"],
       freeze_at=BASE["freeze_at"],history=[bad])

 def test_genuine_previous_routes_only_when_source_proven(self):
  row=prior("verified_receiver_routes")
  x=validate_lagged_participation(event_id=BASE["event_id"],
      freeze_at=BASE["freeze_at"],history=[row])
  self.assertTrue(x["route_challenger_eligible"])
  row["result_available_at"]="2024-09-06T03:00:00Z"
  with self.assertRaisesRegex(SourceGateError,"future_exposure_publication"):
   validate_lagged_participation(event_id=BASE["event_id"],
       freeze_at=BASE["freeze_at"],history=[row])

if __name__=="__main__":
 unittest.main()
