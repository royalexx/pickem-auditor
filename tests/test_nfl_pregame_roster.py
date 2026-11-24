import copy
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import nfl_pregame_roster as roster


def csv_bytes(rows):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=rows[0])
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


class TestNFLPregameRoster(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.event = "401873078"
        self.contract = {
            "event_id": "726376", "event_id_namespace": "propline",
            "game_date": "2026-11-23", "event_start": "2026-11-24T01:15:00Z",
            "away_team": "CIN", "home_team": "WAS", "team": "CIN", "opponent": "WAS",
            "player": "Joe Burrow", "player_id": "00-0036442", "stat": "completions",
            "forecast_at": "2026-11-24T01:10:00Z", "input_freeze_at": "2026-11-24T01:08:00Z",
            "decision_cutoff_at": "2026-11-24T01:05:00Z",
            "forecast_id": "test-forecast", "contract_id": "test-contract",
        }
        self.schedule = [{"espn": self.event, "gsis": "60340", "game_type": "REG",
                          "gameday": "2026-11-23", "gametime": "20:15",
                          "away_team": "CIN", "home_team": "WAS"}]
        self.players = [{"gsis_id": "00-0036442", "espn_id": "3915511",
                         "display_name": "Joe Burrow"}]
        competitor = [{"homeAway": side, "team": {"abbreviation": team}}
                      for side, team in [("away", "CIN"), ("home", "WSH")]]
        self.payload = {"header": {"id": self.event, "competitions": [{
            "id": self.event, "date": self.contract["event_start"], "competitors": competitor,
            "status": {"type": {"state": "pre", "completed": False}},
        }]}, "rosters": []}
        for index, team in enumerate(("CIN", "WSH")):
            players = [{"active": True, "athlete": {
                "id": str(1000 * (index + 1) + i), "displayName": f"{team} Player {i}"}}
                       for i in range(47)]
            self.payload["rosters"].append({"team": {"abbreviation": team}, "roster": players})
        self.player = self.payload["rosters"][0]["roster"][0]
        self.player["athlete"] = {"id": "3915511", "displayName": "Joe Burrow"}

    def evidence(self, *, roster_at=4, roster_missing=False):
        evidence = {"espn_event_id": self.event, "sources": {}}
        for role, raw, minute in (
            ("schedule", csv_bytes(self.schedule), 1),
            ("crosswalk", csv_bytes(self.players), 2),
            ("roster", json.dumps(self.payload).encode(), roster_at),
        ):
            if roster_missing and role == "roster":
                continue
            requested = datetime(2026, 11, 24, 1, 0, tzinfo=timezone.utc)
            observed = requested.replace(minute=minute)
            url = roster._url(role, self.event)
            evidence["sources"][role] = {
                "requested_url": url, "requested_at": roster.stamp(requested),
                "receipt": roster.preserve(self.root, "NFL", role, raw, captured=observed,
                                           retrieved=observed, url=url),
            }
        return evidence

    def check(self, **kwargs):
        return roster.audit([self.contract], self.evidence(**kwargs), self.root)[0]

    def test_exact_event_and_player(self):
        result = self.check()
        self.assertTrue(result["roster_verified"])
        self.assertFalse(result["integrity_certified_in_original"])
        self.assertEqual(result["nfl_gsis_game_id"], "60340")
        self.assertEqual(result["espn_player_id"], "3915511")
        self.assertEqual((result["forecast_id"], result["contract_id"]),
                         ("test-forecast", "test-contract"))

    def test_inactive(self):
        self.player["active"] = False
        self.assertEqual(self.check()["rejection_reasons"], ["NFL_PLAYER_INACTIVE"])

    def test_ambiguous_event(self):
        self.schedule.append({**self.schedule[0], "espn": "2"})
        self.assertIn("NFL_EVENT_ID_AMBIGUOUS", self.check()["rejection_reasons"])

    def test_conflicting_event(self):
        self.payload["header"]["id"] = "2"
        self.assertIn("NFL_ROSTER_EVENT_CONFLICT", self.check()["rejection_reasons"])

    def test_ambiguous_player_forward_and_reverse_mapping(self):
        for extra in ({"espn_id": "888"}, {"gsis_id": "00-0000002"}):
            with self.subTest(extra=extra):
                self.players = [self.players[0], {**self.players[0], **extra}]
                self.assertIn("NFL_PLAYER_ID_AMBIGUOUS", self.check()["rejection_reasons"])

    def test_ambiguous_player_name_in_roster(self):
        self.payload["rosters"][0]["roster"][1]["athlete"]["displayName"] = "Joe Burrow"
        self.assertIn("NFL_PLAYER_ID_AMBIGUOUS", self.check()["rejection_reasons"])

    def test_conflicting_player(self):
        self.player["athlete"]["displayName"] = "Another Player"
        self.assertIn("NFL_PLAYER_ID_CONFLICT", self.check()["rejection_reasons"])

    def test_missing_roster_preserves_other_reasons(self):
        self.players[0]["display_name"] = "Different Player"
        self.contract["input_freeze_at"] = None
        self.assertEqual(self.check(roster_missing=True)["rejection_reasons"], [
            "NFL_GAME_ACTIVE_ROSTER_MANIFEST_MISSING", "NFL_ORIGINAL_INPUT_FREEZE_MISSING",
            "NFL_PLAYER_ID_CONFLICT", "NFL_ROSTER_SOURCE_MISSING",
        ])

    def test_after_cutoff_even_before_freeze_forecast_and_kickoff(self):
        self.assertEqual(self.check(roster_at=6)["rejection_reasons"],
                         ["NFL_ROSTER_POSSESSED_AFTER_CUTOFF"])

    def test_postgame_payload(self):
        self.payload["header"]["competitions"][0]["status"]["type"]["state"] = "post"
        self.assertIn("NFL_ROSTER_NOT_PREGAME", self.check()["rejection_reasons"])

    def test_incomplete_or_unflagged(self):
        unflagged = copy.deepcopy(self.payload)
        removed = self.payload["rosters"].pop()
        self.assertFalse(self.check()["roster_verified"])
        self.payload = unflagged
        self.payload["rosters"][0]["roster"][0].pop("active")
        self.assertFalse(self.check()["roster_verified"])
        self.assertTrue(removed["roster"])

    def test_immutable_bytes_and_expected_source(self):
        evidence = self.evidence()
        source = evidence["sources"]["roster"]
        raw_path = self.root / source["receipt"]["archive_path"]
        raw_path.write_bytes(b"{}")
        self.assertIn("NFL_ROSTER_RECEIPT_BYTES_INVALID",
                      roster.audit([self.contract], evidence, self.root)[0]["rejection_reasons"])
        source["requested_url"] = "https://example.org/summary"
        self.assertIn("NFL_ROSTER_RECEIPT_INVALID",
                      roster.audit([self.contract], evidence, self.root)[0]["rejection_reasons"])


if __name__ == "__main__":
    unittest.main()
