"""Regression checks for proven 2024 NFL false-Under / lookahead defects."""
import unittest
from collections import defaultdict
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import nfl_pre2024_hybrid_bayesian_mc as mc
import nfl_pre2024_pbp_ngs_sources as pbp
import nfl_pre2024_team_volume_xgb as teamxgb


class GameLocalRoleTests(unittest.TestCase):
    def _plays(self,gid,week):
        out=[]
        for n in range(6):
            out.append({"season":2023,"season_type":"REG","week":week,
                "game_id":gid,"play_id":n+1,
                "posteam":"KC","defteam":"BAL","pass_attempt":1,
                "rush_attempt":0,"qb_dropback":1,
                "receiver_player_id":"receiver","air_yards":3.,
                "qtr":1,"score_differential":0})
        return out

    def test_future_position_must_not_reclassify_earlier_game_targets(self):
        a,b="2023_01_BAL_KC","2023_02_BAL_KC"
        games,coverage=pbp.aggregate_games(
            self._plays(a,1)+self._plays(b,2),
            {a:"2023-09-10",b:"2023-09-17"},
            player_position={(a,"receiver"):"WR",(b,"receiver"):"RB"})
        by={x["game_id"]:x for x in games}
        self.assertEqual(by[a]["rb_targets"],0.)
        self.assertEqual(by[b]["rb_targets"],6.)
        self.assertEqual(coverage["pbp_plays"],12)

    def test_global_flat_role_lookup_rejected(self):
        a="2023_01_BAL_KC"
        with self.assertRaisesRegex(ValueError,"cross_game_player_role"):
            pbp.aggregate_games(self._plays(a,1),{a:"2023-09-10"},
                                player_position={"receiver":"RB"})

    def test_same_week_team_features_never_use_current_game(self):
        old=teamxgb.CUTOFF
        try:
            teamxgb.CUTOFF=date(2024,10,1)
            base={"offense":defaultdict(list),"defense":defaultdict(list),
                  "ngs":defaultdict(list)}
            earlier={"game_id":"2024_02_BAL_KC","season":2024,
                     "gameday":"2024-09-15","team":"KC","opponent":"BAL",
                     "pass_attempts":30.,"rush_attempts":25.,
                     "dropbacks":33.,"sacks":2.}
            base["offense"]["KC"].append(earlier)
            base["defense"]["BAL"].append(earlier)
            p=teamxgb.features(base,"KC","BAL",asof="2024-09-22",home=True,week=3)
            # Inject a (forbidden) same-week outcome into the full index;
            # even then, as-of filtering MUST keep today's features identical.
            today={**earlier,"gameday":"2024-09-22",
                   "pass_attempts":250.,"rush_attempts":0.}
            base["offense"]["KC"].append(today)
            base["defense"]["BAL"].append(today)
            q=teamxgb.features(base,"KC","BAL",asof="2024-09-22",home=True,week=3)
            self.assertEqual(p.tolist(),q.tolist())
        finally:
            teamxgb.CUTOFF=old


class PrimaryQBGuardTests(unittest.TestCase):
    def state(self,pa=34.,a=32.,b=2.,future=None):
        s={"player":defaultdict(list),"team_offense":defaultdict(list)}
        s["team_offense"][("pass_attempts","KC")].append(
            {"gameday":"2024-09-05","value":pa})
        s["player"][("pass attempts","a")].append(
            {"gameday":"2024-09-05","team":"KC","value":a})
        s["player"][("pass attempts","b")].append(
            {"gameday":"2024-09-05","team":"KC","value":b})
        if future:
            s["team_offense"][("pass_attempts","KC")].append(
                {"gameday":"2024-09-12","value":40.})
            s["player"][("pass attempts","a")].append(
                {"gameday":"2024-09-12","team":"KC","value":1.})
            s["player"][("pass attempts","b")].append(
                {"gameday":"2024-09-12","team":"KC","value":39.})
        return s

    def test_one_qb_selected_when_historical_workload_dominant(self):
        old=mc.CUTOFF
        try:
            mc.CUTOFF=date(2024,9,12)
            choices=[("a","QB",29.,[]),("b","QB",20.,[])]
            q=mc._primary_qb_from_prior_game(self.state(), "KC", choices)
            self.assertIsNotNone(q)
            self.assertEqual(q[0],"a")
        finally:mc.CUTOFF=old

    def test_ambiguous_split_abstains_instead_of_fake_qb_under(self):
        old=mc.CUTOFF
        try:
            mc.CUTOFF=date(2024,9,12)
            choices=[("a","QB",29.,[]),("b","QB",20.,[])]
            self.assertIsNone(mc._primary_qb_from_prior_game(
                self.state(pa=35,a=20,b=15),"KC",choices))
        finally:mc.CUTOFF=old

    def test_future_qb_switch_cannot_change_previous_week_selection(self):
        old=mc.CUTOFF
        try:
            mc.CUTOFF=date(2024,9,12)
            choices=[("a","QB",29.,[]),("b","QB",20.,[])]
            original=mc._primary_qb_from_prior_game(self.state(),"KC",choices)
            future=mc._primary_qb_from_prior_game(self.state(future=True),"KC",choices)
            self.assertEqual(original,future)
            self.assertEqual(future[0],"a")
        finally:mc.CUTOFF=old

    def test_missing_prior_team_context_abstains(self):
        old=mc.CUTOFF
        try:
            mc.CUTOFF=date(2024,9,12)
            s={"player":defaultdict(list),"team_offense":defaultdict(list)}
            self.assertIsNone(mc._primary_qb_from_prior_game(
                s,"KC",[("a","QB",20.,[])]))
        finally:mc.CUTOFF=old


class ChallengerTierSuspension(unittest.TestCase):
    def test_challenger_tier1_tier2_blocked_even_if_p99(self):
        from nfl_challenger_policy import CHALLENGER_FAMILY, BLOCK_REASON
        from tier_quality import assess
        for tier in ("Tier 1","Tier 2"):
            x=assess(tier,.99,blend_validated=True,model_family=CHALLENGER_FAMILY)
            self.assertFalse(x["eligible"])
            self.assertEqual(x["reason"],BLOCK_REASON)
        self.assertTrue(assess("Tier 3",.78,model_family=CHALLENGER_FAMILY)["eligible"])

    def test_unrelated_production_consensus_not_indiscriminately_demoted(self):
        from tier_quality import assess
        self.assertTrue(assess("Tier 2",.85,model_family="production_consensus")["eligible"])


if __name__=="__main__":
    unittest.main()
