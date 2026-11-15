"""Offline synthetic unit fixtures for WS4 real-data historical adapter arithmetic.

These fixtures only test mathematical constraints; they are not real forecasts.
The live original-contract audit separately inspects genuine archived source bytes.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys
import tempfile
import unittest

J = pathlib.Path(__file__).resolve().parents[1] / "joint_models"
sys.path.insert(0, str(J))
from ws4_original_contract_adapter import (
    AdapterError, checked, parse_time, qb_starter_share, team_rates
)


class PointInTimeAndIdentityTests(unittest.TestCase):
    def test_timezone_strict(self):
        with self.assertRaises(AdapterError):
            parse_time("2026-11-15T14:00:00")

    def test_exact_utc_source(self):
        self.assertEqual(parse_time("2026-11-15T14:00:00Z").isoformat(),
                         "2026-11-15T14:00:00+00:00")

    def test_manifest_hash_tamper(self):
        with tempfile.TemporaryDirectory() as root:
            f = pathlib.Path(root) / "raw.json"
            f.write_bytes(b"test-source")
            digest = hashlib.sha256(f.read_bytes()).hexdigest()
            self.assertEqual(checked(f, digest)[1], digest)
            f.write_bytes(b"changed-source")
            with self.assertRaises(AdapterError):
                checked(f, digest)


class AuthenticatedHistoricalShrinkageTests(unittest.TestCase):
    @staticmethod
    def team_rows():
        rows=[]
        for name in ("LA","DAL"):
            for i in range(160):
                rows.append({"team":name,"plays":65,"passes":35,
                             "rushes":25,"game_id":str(i)})
        return rows

    def test_exact_team_count_accounting_with_empirical_pool(self):
        result=team_rates("LA",self.team_rows(),"2026-11-15T14:30:00Z")
        self.assertEqual(result["n_team_games"],160)
        self.assertEqual(result["n_pooled_team_games"],320)
        self.assertEqual(result["prior_equivalent_games"],4)
        self.assertAlmostEqual(result["plays_mean"],65)
        self.assertAlmostEqual(result["pass_rate"],35/60)
        self.assertAlmostEqual(result["sack_rate"],5/65)

    def test_lar_translates_only_historical_key(self):
        result=team_rates("LAR",self.team_rows(),"2026-11-15T14:30:00Z")
        self.assertEqual(result["historical_team_key"],"LA")
        self.assertEqual(result["original_team_key"],"LAR")
        self.assertEqual(result["n_team_games"],160)

    def test_no_unseen_team_fake_rate(self):
        with self.assertRaisesRegex(AdapterError,"TEAM_HISTORICAL_POOL_TOO_SMALL"):
            team_rates("XYZ",self.team_rows(),"2026-11-15T14:30:00Z")

    def test_invalid_sack_residual_fail_closed(self):
        rows=self.team_rows()
        rows[0]["plays"]=1
        with self.assertRaisesRegex(AdapterError,"TEAM_PLAY_ACCOUNTING_INVALID"):
            team_rates("LA",rows,"2026-11-15T14:30:00Z")

    @staticmethod
    def qb_rows():
        rows=[]
        for i in range(105):
            game="2025_"+str(i)
            rows.append({"position":"QB","team":"LA","game_id":game,
                         "player_id":"00-0030000","attempts":30})
            rows.append({"position":"QB","team":"LA","game_id":game,
                         "player_id":"00-0030001","attempts":10})
        return rows

    def test_qb_share_based_on_all_team_attempts(self):
        result=qb_starter_share("LAR","00-0030000",self.qb_rows())
        self.assertEqual(result["historical_team_key"],"LA")
        self.assertEqual(result["n_qb_games_on_target_team"],105)
        self.assertEqual(result["n_pooled_max_attempt_qb_games"],105)
        self.assertEqual(result["prior_equivalent_games"],3)
        self.assertAlmostEqual(result["starter_attempt_share"],0.75)

    def test_sparse_qb_uses_observed_position_pool(self):
        result=qb_starter_share("LAR","00-0031000",self.qb_rows())
        self.assertEqual(result["n_qb_games_on_target_team"],0)
        self.assertAlmostEqual(result["starter_attempt_share"],0.75)
        self.assertTrue(result["not_confirmed_game_day_starter"])

    def test_no_empirical_role_prior_abstains(self):
        with self.assertRaisesRegex(AdapterError,"POOLED_QB_ROLE_HIST_TOO_SMALL"):
            qb_starter_share("LAR","00-0030000",self.qb_rows()[:40])


if __name__=="__main__":
    unittest.main()
