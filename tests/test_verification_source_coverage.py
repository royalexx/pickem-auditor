import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from pick_verification import verification_coverage

class EvidenceCoverageTests(unittest.TestCase):
    def test_explicit_roster_missing_is_visible_and_not_approved(self):
        decisions=[
          {"sport":"NBA","decision":"blocked","blockers":["GAME_SPECIFIC_ACTIVE_STATUS_MISSING","ENGINE_RANK_NOT_ELIGIBLE_UNRANKED"]},
          {"sport":"NHL","decision":"blocked","blockers":["STARTING_GOALIE_NOT_EXPLICITLY_CONFIRMED"]},
          {"sport":"NHL","decision":"verified","blockers":[]}]
        attempts=[
          {"purpose":"explicit game-active roster","status":"retrieved","resolved_players":0},
          {"purpose":"explicit game-active roster","status":"retrieved","resolved_players":1},
          {"purpose":"explicit game-active roster","status":"source_failed"}]
        result=verification_coverage(decisions,attempts)
        self.assertEqual(result["blocker_counts"]["GAME_SPECIFIC_ACTIVE_STATUS_MISSING"],1)
        self.assertEqual(result["by_sport"]["NBA"]["missing_game_active_status"],1)
        self.assertEqual(result["by_sport"]["NHL"]["verified"],1)
        self.assertEqual(result["source_attempts"]["explicit game-active roster"]["zero_active_roster_events"],1)
        self.assertEqual(result["source_attempts"]["explicit game-active roster"]["explicit_players"],1)
        self.assertEqual(result["source_attempts"]["explicit game-active roster"]["source_failed"],1)
if __name__=='__main__':
    unittest.main()
