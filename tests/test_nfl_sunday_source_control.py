"""Adversarial WS1 source/identity/chronology fixtures — no live market calls."""
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from hashlib import sha256

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from nfl_sunday_source_contract import (
    VERSION, SUPPORTED, expected_events, instant, utc, roster_index, eligibility,
    validate_frozen_forecast, build_universe, tackle_total, frozen_control,
    write_immutable, freeze_manifest, canonical,
)

SHA = "a" * 64
FREEZE = "2026-11-15T05:00:00Z"
COMMIT = "9" * 40

def setup(**changes):
    events = [dict(event, espn_event_id=str(440000000 + i),
                   schedule_verified=True) for i, event in enumerate(expected_events())]
    first = events[1]
    player = {"id": "12345", "fullName": "Test Player",
              "position": {"abbreviation": "QB"}, "status": "active"}
    roster = {"KC": {"athletes": [player], "receipt_sha256": "b" * 64}}
    q = {"sport": "NFL", "event_id": "propline-original-1",
         "event_start": first["scheduled_kickoff"], "event_teams": ["KC","ATL"],
         "team": "KC", "opponent": "ATL", "player": "Test Player",
         "stat": "pass attempts", "book": "Book A", "line": 32.5,
         "over_odds": -110, "under_odds": -110,
         "retrieved_at": "2026-11-14T23:00:00Z"}
    receipt = {"sha256": SHA, "source_received_at": "2026-11-15T04:45:00Z",
               "source_bytes_verified": True, "archive_path": "raw/a.bin"}
    params = {
        "events": events, "quotes": [q], "quote_receipts": {"propline": receipt},
        "rosters": roster,
        "depth_qbs": {"KC": {"espn_player_id": "12345"}},
        "injuries": {}, "nfl_rows": [], "freeze_at": FREEZE,
        "code_sha": COMMIT,
    }
    params.update(changes)
    return params

def run(**changes):
    return build_universe(**setup(**changes))

class SundayScheduleTests(unittest.TestCase):
    def test_12_distinct_fixtures(self):
        events=expected_events()
        self.assertEqual(len(events), 12)
        self.assertEqual(len({x["fixture_key"] for x in events}), 12)
    def test_four_windows_and_strict_utc(self):
        events=expected_events()
        starts={x["scheduled_kickoff"] for x in events}
        self.assertEqual(len(starts), 5)  # 09:30, 13:00, 16:05, 16:25, 20:20
        self.assertEqual(events[0]["scheduled_kickoff"], "2026-11-15T14:30:00Z")
    def test_timezone_naive_fails(self):
        with self.assertRaisesRegex(ValueError, "naive"):
            instant("2026-11-15T04:20:00")
    def test_invalid_timestamp_fails(self):
        with self.assertRaises(ValueError):
            instant("not-a-date")

class QuotedUniverseTests(unittest.TestCase):

    def test_team_derived_only_from_unique_verified_game_roster(self):
        p=setup()
        p["quotes"][0].update(team="",opponent="",event_teams=["ATL","KC"])
        m=build_universe(**p)
        r=m["candidates"][0]
        self.assertEqual((r["team"],r["opponent"]),("KC","ATL"))
        self.assertEqual(r["team_identity_basis"],
                         "independent_unique_espn_roster_on_provider_event_pair")
        self.assertTrue(r["source_certified"])
        self.assertEqual(r["original_quote"]["team"],"")
    def test_same_name_on_both_event_rosters_abstains(self):
        p=setup()
        p["quotes"][0].update(team="",opponent="",event_teams=["ATL","KC"])
        p["rosters"]["ATL"]={"receipt_sha256":"c"*64,
           "athletes":[{"id":"9999","fullName":"Test Player",
                        "position":{"abbreviation":"QB"}}]}
        m=build_universe(**p)
        self.assertEqual(m["source_certified_quotes"],0)
        self.assertEqual(m["failures"]["CROSS_TEAM_ROSTER_IDENTITY_UNVERIFIABLE"],1)
    def test_claimed_team_not_in_event_pair_abstains(self):
        p=setup()
        p["quotes"][0].update(team="KC",opponent="ATL",event_teams=["NYJ","BUF"])
        m=build_universe(**p)
        self.assertEqual(m["source_certified_quotes"],0)
        self.assertIn("PROVIDER_TEAM_EVENT_PAIR_CONFLICT",m["failures"])
    def test_no_espn_player_has_unverifiable_source_status(self):
        p=setup()
        p["quotes"][0].update(team="",opponent="",event_teams=["ATL","KC"])
        p["rosters"]={}
        m=build_universe(**p)
        self.assertEqual(m["source_certified_quotes"],0)
        self.assertFalse(m["candidates"][0]["forecast_eligible"])
    def test_single_offer_preserves_original_prices(self):
        m=run()
        self.assertEqual(m["attempted_contracts"], 1)
        self.assertEqual(m["quote_observations"], 1)
        self.assertEqual(m["source_certified_quotes"], 1)
        self.assertEqual(m["forecast_eligible_contracts"], 0)
        item=m["candidates"][0]
        self.assertEqual(item["over_odds"], -110)
        self.assertEqual(item["line"], 32.5)
        self.assertEqual(item["player_id"], "12345")
        self.assertEqual(item["eligibility_status"], "EXPECTED_STARTER_SOURCE_BACKED")
        self.assertTrue(item["source_certified"])
        self.assertFalse(item["production_ranking_allowed"])
        self.assertIsNone(item["frozen_control"]["NUTS_strict"]["probability"])
    def test_all_levels_and_books_have_distinct_id(self):
        p=setup()
        first=p["quotes"][0]
        p["quotes"]=[first, {**first,"line":33.5},
                     {**first,"book":"Book B"}, {**first,"over_odds":-105,
                     "under_odds":-115,"book":"Book C"}]
        m=build_universe(**p)
        self.assertEqual(m["attempted_contracts"], 4)
        self.assertEqual(m["unique_candidate_ids"], 4)
    def test_duplicate_quote_poisoned_both(self):
        p=setup()
        p["quotes"]=p["quotes"]*2
        m=build_universe(**p)
        self.assertEqual(m["attempted_contracts"],2)
        self.assertEqual(m["source_certified_quotes"],0)
        self.assertEqual(m["failures"]["QUOTE_IDENTITY_COLLISION"],2)
    def test_conflicting_price_poisoned_both(self):
        p=setup()
        p["quotes"].append({**p["quotes"][0],"over_odds":-115})
        m=build_universe(**p)
        self.assertEqual(m["failures"]["QUOTE_IDENTITY_COLLISION"],2)
    def test_missing_player_not_laundered(self):
        p=setup(rosters={})
        m=build_universe(**p)
        r=m["candidates"][0]
        self.assertEqual(r["source_validation_failure"],
                         "PLAYER_ROSTER_IDENTITY_UNVERIFIABLE")
        self.assertIsNone(r["player_id"])
    def test_roster_name_ambiguity_not_resolved(self):
        p=setup()
        p["rosters"]["KC"]["athletes"].append({
            "id":"222","fullName":"Test Player",
            "position":{"abbreviation":"QB"}})
        m=build_universe(**p)
        self.assertEqual(m["candidates"][0]["eligibility_status"],
                         "IDENTITY_UNVERIFIABLE")
    def test_missing_source_raw_bytes_fail(self):
        p=setup()
        p["quote_receipts"]["propline"]["source_bytes_verified"]=False
        self.assertEqual(build_universe(**p)["source_certified_quotes"],0)
    def test_malformed_source_hash_fail(self):
        p=setup()
        p["quote_receipts"]["propline"]["sha256"]="0"*20
        self.assertEqual(build_universe(**p)["failures"]["SOURCE_HASH_MISSING"],1)
    def test_bad_source_clock_fail(self):
        p=setup()
        p["quote_receipts"]["propline"]["source_received_at"]="2026-11-15T06:00:00Z"
        self.assertEqual(build_universe(**p)["failures"]["SOURCE_AFTER_FREEZE"],1)
    def test_started_game_fail(self):
        p=setup(freeze_at="2026-11-15T19:00:00Z")
        self.assertEqual(build_universe(**p)["failures"]["EVENT_STARTED"],1)
    def test_source_missing_event_mapped_failure(self):
        p=setup()
        p["events"][1]["espn_event_id"]=None
        self.assertEqual(build_universe(**p)["failures"]["SCHEDULE_SOURCE_UNVERIFIED"],1)
    def test_kickoff_change_reject(self):
        p=setup()
        p["quotes"][0]["event_start"]="2026-11-15T19:00:00Z"
        self.assertEqual(build_universe(**p)["failures"]["EVENT_KICKOFF_CONFLICT"],1)
    def test_event_collision_wrong_opponent_reject(self):
        p=setup()
        p["quotes"][0]["opponent"]="NYJ"
        self.assertEqual(build_universe(**p)["failures"]["PROVIDER_OPPONENT_EVENT_PAIR_CONFLICT"],1)
    def test_missing_tackle_book_settlement_not_certified(self):
        p=setup()
        p["quotes"][0]["stat"]="tackles + assists"
        m=build_universe(**p)
        self.assertEqual(m["candidates"][0]["settlement_semantics"],
                         "THREE_COMPONENT_SOURCE_DEFINED_BOOK_RULES_UNVERIFIED")
        self.assertEqual(m["forecast_eligible_contracts"],0)
    def test_unsupported_td_captured_as_unavailable(self):
        p=setup()
        p["quotes"][0]["stat"]="passing touchdowns"
        m=build_universe(**p)
        self.assertEqual(m["failures"]["MARKET_UNSUPPORTED_BY_SOURCE_CONTRACT"],1)
        self.assertEqual(m["attempted_contracts"],1)
    def test_negative_line_reject(self):
        p=setup()
        p["quotes"][0]["line"]=-1
        self.assertEqual(build_universe(**p)["failures"]["LINE_INVALID"],1)
    def test_missing_provider_event_reject(self):
        p=setup()
        p["quotes"][0]["event_id"]=""
        self.assertEqual(build_universe(**p)["source_certified_quotes"],0)
    def test_missing_independent_qb1_abstains(self):
        p=setup(depth_qbs={})
        r=build_universe(**p)["candidates"][0]
        self.assertEqual(r["eligibility_status"],"STARTER_UNVERIFIABLE")
        self.assertIsNone(r["participation_risk_probability"])
        self.assertFalse(r["forecast_eligible"])
    def test_verified_backup_excluded(self):
        p=setup(depth_qbs={"KC":{"espn_player_id":"another-id"}})
        r=build_universe(**p)["candidates"][0]
        self.assertEqual(r["eligibility_status"],"BACKUP_INELIGIBLE")
    def test_injury_status_uncertain_no_guessed_probability(self):
        p=setup(injuries={"KC":{"12345":"questionable"}})
        r=build_universe(**p)["candidates"][0]
        self.assertEqual(r["eligibility_status"],"UNCERTAIN_PARTICIPATION")
        self.assertIsNone(r["participation_risk_probability"])
    def test_verified_out_excluded(self):
        p=setup(injuries={"KC":{"12345":"out"}})
        self.assertEqual(build_universe(**p)["candidates"][0]["eligibility_status"],
                         "VERIFIED_OUT")
    def test_control_columns_null_frozen(self):
        m=frozen_control()
        self.assertEqual(set(m),{"Engine_A","Engine_B","Bayesian_A",
                                 "Bayesian_B","NUTS_strict","Consensus_60_40","Market"})
        self.assertTrue(all(x["probability"] is None for x in m.values()))

class StatAndManifestTests(unittest.TestCase):
    def test_tackle_exact_three_component_sum(self):
        self.assertEqual(tackle_total(dict(def_tackles_solo=4,
                                           def_tackles_with_assist=2,
                                           def_tackle_assists=3)),9)
    def test_tackle_missing_component_not_zero(self):
        self.assertIsNone(tackle_total(dict(def_tackles_solo=4,
                                            def_tackle_assists=3)))
    def test_tackle_malformed_and_bool_rejected(self):
        for value in (True, -1, 0.5, float("nan"), 201, "2"):
            with self.subTest(value=value):
                self.assertIsNone(tackle_total(dict(def_tackles_solo=value,
                  def_tackles_with_assist=1,def_tackle_assists=1)))
    def test_manifest_immutable_and_hash_verified(self):
        with tempfile.TemporaryDirectory() as d:
            m={"schema":VERSION,"events":[],"date":"2026-11-15"}
            r=freeze_manifest(d,m)
            target=Path(r["path"])
            self.assertTrue(target.is_file())
            self.assertEqual(r["file_sha256"],sha256(target.read_bytes()).hexdigest())
            self.assertEqual(freeze_manifest(d,m),r)
            with self.assertRaises(ValueError):
                write_immutable(target, {"tamper": True})
    def test_invalid_forecast_timing(self):
        r=dict(candidate_id="1",event_id="2",player_id="3",
           stat="pass attempts",period="full_game",line=32.5,quote_id="q",
           source_sha256=SHA,source_received_at="2026-11-15T04:00:00Z",
           model_training_cutoff_at="2026-11-15T04:00:00Z",
           input_freeze_at="2026-11-15T05:00:00Z",
           forecast_at="2026-11-15T05:05:00Z",
           event_start_at="2026-11-15T18:00:00Z")
        self.assertTrue(validate_frozen_forecast(r)[0])
        for field, val in (("forecast_at","2026-11-15T19:00:00Z"),
                           ("source_received_at","2026-11-15T06:00:00Z"),
                           ("model_training_cutoff_at","2026-11-15T06:00:00Z"),
                           ("input_freeze_at","2026-11-15T05:00:00")):
            with self.subTest(field=field):
                self.assertFalse(validate_frozen_forecast({**r,field:val})[0])
    def test_forecast_without_model_cutoff_rejected(self):
        ok,reason=validate_frozen_forecast(dict(candidate_id="1"))
        self.assertFalse(ok)
        self.assertIn("MISSING_FORECAST_FIELDS",reason)


class LiveSourceAdapterTests(unittest.TestCase):
    def test_espn_depth_order_first_qb_no_fake_rank(self):
        from nfl_sunday_capture import depth_qb
        payload={"depthchart":[{"name":"3WR 1TE","positions":{
            "qb":{"athletes":[{"id":"12345"},{"id":"222"}]}}}]}
        x=depth_qb(payload)
        self.assertEqual(x["espn_player_id"],"12345")
        self.assertTrue(x["source_only_expected"])
    def test_conflicting_qb_depth_orders_abstains(self):
        from nfl_sunday_capture import depth_qb
        payload={"depthchart":[
            {"positions":{"qb":{"athletes":[{"id":"12345"}]}}},
            {"positions":{"qb":{"athletes":[{"id":"999"}]}}}
        ]}
        self.assertIsNone(depth_qb(payload))
    def test_injured_reserve_structured_status_ineligible(self):
        from nfl_sunday_source_contract import eligibility
        player=dict(espn_player_id="12345",position="QB",
                    roster_status={"type":"injured-reserve","name":"Injured Reserve"})
        label,risk,_=eligibility(player,"pass attempts",{"espn_player_id":"12345"})
        self.assertEqual((label,risk),("VERIFIED_OUT",1.0))
    def test_protected_raw_sha_mismatch_rejected(self):
        from nfl_sunday_rebind import load_raw
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/"raw").mkdir()
            body=b'{"safe":true}'
            (root/"raw/source.bin").write_bytes(body)
            receipt={"archive_path":"raw/source.bin",
                     "sha256":"0"*64,"size_bytes":len(body),
                     "source_bytes_verified":True}
            with self.assertRaisesRegex(ValueError,"RAW_SOURCE_SHA_MISMATCH"):
                load_raw(root,receipt)
    def test_raw_archive_path_traversal_rejected(self):
        from nfl_sunday_rebind import load_raw
        with tempfile.TemporaryDirectory() as d:
            receipt={"archive_path":"../x","sha256":SHA,"size_bytes":1,
                     "source_bytes_verified":True}
            with self.assertRaisesRegex(ValueError,"RAW_SOURCE_PATH_UNSAFE"):
                load_raw(d,receipt)

if __name__ == "__main__":
    unittest.main()
