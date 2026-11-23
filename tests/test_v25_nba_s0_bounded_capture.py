"""P1 original pregame capture cap: deterministic adversarial regression tests."""
import copy
import unittest
from research.nba_p1_original.feature_store import STATS
from research.nba_p1_original.rolling import (
    AcquisitionError,_bounded_canary_subset,WindowPolicy
)


def fixture():
    rows=[]
    for n in range(1,10):
        pid=f"espn:player:{n:03d}"
        history=[{"participation":"played"},{"participation":"played"}]
        if n==8:
            history=[{"participation":"dnp"},{"participation":"played"}]
        availability="UNVERIFIED_AVAILABILITY" if n!=7 else "RULED_OUT_SOURCE_REPORTED"
        for stat in STATS:
            rows.append({"player_id":pid,"stat_key":stat,
                "features":{"prior_player_history":copy.deepcopy(history),
                    "availability_status":availability,
                    "current_name":"Synthetic "+str(n),
                    "position":"G","official_nba_player_id":None}})
    manifest={"feature_rows":len(rows),"player_candidates_accepted":9,
        "player_candidates_total":9,"player_candidates_rejected":0,
        "source_listed_count":9,"unknown_availability":8,
        "questionable_count":0,"ruled_out_count":1,
        "name_supported_count":9,"position_supported_count":9,
        "official_player_ids_verified_count":0,"rejected":[]}
    return rows,manifest


class BoundedOriginalCaptureTests(unittest.TestCase):
    def test_default_p1_is_full_not_mutated(self):
        r,s=fixture()
        full,original=_bounded_canary_subset(r,s,None)
        self.assertIs(full,r)
        self.assertIs(original,s)
        self.assertEqual(len(full),9*len(STATS))

    def test_explicit_canary_only_selects_prior_played_and_not_ruled_out(self):
        r,s=fixture()
        chosen,m=_bounded_canary_subset(r,s,6)
        self.assertEqual(len(chosen),6*len(STATS))
        self.assertEqual(m["feature_rows"],6*len(STATS))
        self.assertEqual(m["player_candidates_accepted"],6)
        self.assertEqual(m["player_candidates_rejected"],3)
        self.assertEqual(m["source_listed_count"],6)
        self.assertEqual(m["bounded_canary_selection"]["selected_player_ids"],
                         [f"espn:player:{i:03d}" for i in range(1,7)])
        self.assertTrue(m["bounded_canary_selection"]["no_target_outcome_data_used"])
        self.assertEqual(len(s["rejected"]),0)
        self.assertEqual(s["player_candidates_accepted"],9)

    def test_ineligible_histories_or_ruled_out_not_selected(self):
        rows,summary=fixture()
        chosen,m=_bounded_canary_subset(rows,summary,24)
        ids={x["player_id"] for x in chosen}
        self.assertNotIn("espn:player:007",ids)
        self.assertNotIn("espn:player:008",ids)
        self.assertIn("espn:player:009",ids)
        self.assertEqual(len(ids),7)

    def test_non_bundle_input_fails_closed(self):
        rows,summary=fixture()
        rows.pop()
        with self.assertRaisesRegex(AcquisitionError,"INCOMPLETE_CANARY_PLAYER_STAT_BUNDLE"):
            _bounded_canary_subset(rows,summary,6)

    def test_limits_fail_closed(self):
        rows,summary=fixture()
        for limit in (0,-1,25,1.0,False,"6"):
            with self.subTest(limit=limit):
                with self.assertRaisesRegex(AcquisitionError,"CANARY_PLAYER_LIMIT_BOUNDS"):
                    _bounded_canary_subset(rows,summary,limit)

    def test_window_policy_not_relaxed(self):
        w=WindowPolicy()
        self.assertEqual((w.early_open_minutes,w.early_deadline_minutes), (70,50))
        self.assertEqual((w.final_open_minutes,w.final_deadline_minutes), (35,20))


if __name__=="__main__":
    unittest.main()
