"""Offline tests for the player-prop provider, name join, and consensus input."""

import json
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))
import fetch_slate as fs
import odds_providers as op
import pickem_math as pm

FIXTURES = Path(__file__).resolve().parent / "fixtures"
NOW = "2026-10-22T16:10:00Z"
SOURCE = "https://api.the-odds-api.com/v4/sports/icehockey_nhl/events/evt-bos-nsh/odds"


def load_json(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def parsed_events():
    return op.quotes_from_api_payload(
        load_json("odds_api_events.json"),
        sport="NHL",
        retrieved_at=NOW,
        source_url=SOURCE,
    )


def slate_row(player, team, opponent="NSH", stat="shots on goal", sport="NHL", baseline=3.0):
    return {
        "player": player,
        "team": team,
        "opponent": opponent,
        "sport": sport,
        "stat": stat,
        "baseline_mean": baseline,
        "flag": False,
    }


class NameAndTeamTests(unittest.TestCase):
    def test_suffix_accent_and_punctuation(self):
        self.assertEqual(op.normalize_player("Jaren Jackson Jr."), "jaren jackson")
        self.assertEqual(op.normalize_player("Jaren Jackson Sr."), "jaren jackson")
        self.assertEqual(op.normalize_player("Robert Griffin III"), "robert griffin")
        self.assertEqual(op.normalize_player("Player II"), "player")
        self.assertEqual(op.normalize_player("A.J. Brown"), "aj brown")
        self.assertEqual(op.normalize_player("José Altuve"), "jose altuve")
        self.assertEqual(op.normalize_player("Tim Stützle"), op.normalize_player("Tim Stutzle"))
        self.assertEqual(op.normalize_player("J.R. Smith"), "jr smith")

    def test_team_names_keep_sport_abbreviations_apart(self):
        self.assertEqual(op.normalize_team("Boston Bruins"), "BOS")
        self.assertEqual(op.normalize_team("Boston Celtics"), "BOS")
        self.assertEqual(op.normalize_team("Tampa Bay Buccaneers"), "TB")
        self.assertEqual(op.normalize_team("Tampa Bay Lightning"), "TBL")
        self.assertEqual(op.normalize_team("Washington Capitals"), "WSH")
        self.assertEqual(op.normalize_team("Washington Commanders"), "WAS")
        self.assertEqual(op.normalize_team("BOS"), "BOS")

    def test_eastern_date_window(self):
        self.assertFalse(op.event_on_date("2026-10-22T03:59:00Z", "2026-10-22"))
        self.assertTrue(op.event_on_date("2026-10-22T04:00:00Z", "2026-10-22"))
        self.assertTrue(op.event_on_date("2026-10-23T03:59:00Z", "2026-10-22"))
        self.assertFalse(op.event_on_date("2026-10-23T04:00:00Z", "2026-10-22"))


class QuoteShapeTests(unittest.TestCase):
    def test_fixture_keeps_every_two_sided_book_line(self):
        quotes = parsed_events()
        self.assertEqual(len(quotes), 8)
        players = {quote["player"] for quote in quotes}
        self.assertNotIn("One Sided", players)
        books = {quote["book"] for quote in quotes}
        self.assertNotIn("Underdog", books)
        self.assertNotIn("Underdog Fantasy", books)
        blob = json.dumps(quotes).lower()
        self.assertNotIn("underdog", blob)
        for quote in quotes:
            self.assertTrue(set(op.QUOTE_FIELDS)<=set(quote))
            self.assertNotIn("apiKey", quote["source_url"])

        stutzle = [quote for quote in quotes if quote["player_norm"] == "tim stutzle"]
        self.assertEqual(len(stutzle), 6)
        lines = {(quote["book"], quote["line"]) for quote in stutzle}
        self.assertIn(("Pinnacle", 2.5), lines)
        self.assertIn(("FanDuel", 2.5), lines)
        self.assertIn(("Caesars", 2.5), lines)
        self.assertIn(("FanDuel", 3.5), lines)
        self.assertIn(("DraftKings", 3.5), lines)
        self.assertIn(("BetMGM", 3.5), lines)
        self.assertTrue(all(quote["team"] == "" for quote in stutzle))

        alex = {(quote["team"], quote["line"], quote["book"]) for quote in quotes if quote["player"] == "Alex Smith"}
        self.assertEqual(alex, {("BOS", 1.5, "Pinnacle"), ("NSH", 4.5, "FanDuel")})
        bos = next(quote for quote in quotes if quote["player"] == "Alex Smith" and quote["team"] == "BOS")
        self.assertEqual(bos["opponent"], "NSH")

    def test_one_sided_record_is_dropped(self):
        quotes = op.quotes_from_records(
            [
                {
                    "player": "One Sided",
                    "team": "BOS",
                    "sport": "NHL",
                    "stat": "shots on goal",
                    "book": "FanDuel",
                    "line": 1.5,
                    "over_odds": -120,
                }
            ]
        )
        self.assertEqual(quotes, [])


class AttachAndConsensusTests(unittest.TestCase):
    def rows(self):
        return [
            slate_row("Tim Stützle", "BOS", "NSH"),
            slate_row("Alex Smith", "BOS", "NSH"),
            slate_row("Alex Smith", "NSH", "BOS"),
            slate_row("Jaren Jackson III", "MEM", "DEN", stat="points", sport="NBA", baseline=20.0),
        ]

    def quotes(self):
        blank = op.quotes_from_records(
            [
                {
                    "sport": "NHL",
                    "player": "Alex Smith",
                    "stat": "shots on goal",
                    "book": "DraftKings",
                    "line": 2.5,
                    "over_odds": -110,
                    "under_odds": -110,
                    "retrieved_at": "2026-10-22T16:00:00Z",
                    "source_url": "https://example.test/odds",
                }
            ]
        )
        suffix = op.quotes_from_records(
            [
                {
                    "sport": "NBA",
                    "player": "Jaren Jackson Jr.",
                    "team": "MEM",
                    "stat": "points",
                    "book": "FanDuel",
                    "line": 18.5,
                    "over_odds": -120,
                    "under_odds": 100,
                    "retrieved_at": "2026-10-22T16:00:00Z",
                    "source_url": "https://example.test/odds",
                }
            ]
        )
        return parsed_events() + blank + suffix

    def test_primary_line_name_join_and_disagreement(self):
        rows = self.rows()
        resolved, unmatched = fs.attach_prices(rows, self.quotes())
        stutzle = next(row for row in rows if row["player"] == "Tim Stützle")
        self.assertEqual(stutzle["book"], "Pinnacle")
        self.assertEqual(stutzle["line"], 2.5)
        self.assertEqual(stutzle["over_odds"], -130)
        self.assertEqual(stutzle["under_odds"], 110)
        self.assertEqual(stutzle["n_books"], 3)
        self.assertTrue(stutzle["lines_disagree"])
        self.assertIn("lines_disagree", stutzle["flag_reasons"])
        self.assertTrue(stutzle["flag"])

        alex_bos = next(row for row in rows if row["player"] == "Alex Smith" and row["team"] == "BOS")
        alex_nsh = next(row for row in rows if row["player"] == "Alex Smith" and row["team"] == "NSH")
        self.assertEqual(alex_bos["line"], 1.5)
        self.assertEqual(alex_bos["book"], "Pinnacle")
        self.assertEqual(alex_nsh["line"], 4.5)
        self.assertEqual(alex_nsh["book"], "FanDuel")
        self.assertFalse(alex_bos["lines_disagree"])
        self.assertFalse(alex_nsh["lines_disagree"])

        jackson = next(row for row in rows if row["team"] == "MEM")
        self.assertEqual(jackson["player"], "Jaren Jackson III")
        self.assertEqual(jackson["line"], 18.5)
        self.assertEqual(jackson["book"], "FanDuel")

        stored = next(quote for quote in resolved if quote["player_norm"] == "tim stutzle" and quote["line"] == 2.5)
        self.assertEqual(stored["team"], "BOS")
        blank_alex = [item for item in unmatched if item["player"] == "Alex Smith"]
        self.assertEqual(len(blank_alex), 1)
        self.assertEqual(blank_alex[0]["team"], "")
        self.assertEqual(blank_alex[0]["reason"], "same name on more than one team")

        fanduel_lines = sorted(
            quote["line"]
            for quote in resolved
            if quote["player_norm"] == "tim stutzle" and quote["book"] == "FanDuel"
        )
        self.assertEqual(fanduel_lines, [2.5, 3.5])

    def test_sharp_line_beats_a_busier_retail_line(self):
        quotes = op.quotes_from_records(
            [
                self._record("Pinnacle", 3.5),
                self._record("FanDuel", 2.5),
                self._record("DraftKings", 2.5),
                self._record("BetMGM", 2.5),
            ]
        )
        price = op.primary_price(quotes)
        self.assertEqual(price["line"], 3.5)
        self.assertEqual(price["book"], "Pinnacle")
        self.assertEqual(price["n_books"], 1)
        self.assertTrue(price["lines_disagree"])

    def test_most_quoted_line_when_no_sharp_book(self):
        quotes = op.quotes_from_records(
            [
                self._record("FanDuel", 2.5),
                self._record("DraftKings", 2.5),
                self._record("BetMGM", 2.5),
                self._record("Caesars", 1.5),
            ]
        )
        price = op.primary_price(quotes)
        self.assertEqual(price["line"], 2.5)
        self.assertEqual(price["n_books"], 3)
        self.assertTrue(price["lines_disagree"])

    def test_consensus_input_matches_pipeline_books(self):
        quotes = [quote for quote in parsed_events() if quote["player_norm"] == "tim stutzle"]
        groups = op.consensus_input(quotes, now=NOW, side="over")
        by_line = {group["line"]: group for group in groups}
        primary = by_line[2.5]
        self.assertEqual(
            primary["book_specs"],
            [
                "Pinnacle:2.5:-130:+110:over",
                "FanDuel:2.5:-125:+105:over",
                "Caesars:2.5:-110:-110:over",
            ],
        )
        self.assertEqual([book["book_side"] for book in primary["books"]], ["over", "over", "over"])
        self.assertEqual(primary["books"][0]["target"], -130)
        self.assertEqual(primary["books"][0]["other"], 110)
        self.assertAlmostEqual(primary["retrieved_minutes_ago"], 10.0)
        self.assertAlmostEqual(by_line[3.5]["retrieved_minutes_ago"], 5.0)

        under = op.consensus_input(quotes, now=NOW, side="under")
        under_primary = next(group for group in under if group["line"] == 2.5)
        self.assertTrue(under_primary["book_specs"][0].endswith(":under"))
        self.assertEqual(under_primary["books"][0]["target"], 110)
        self.assertEqual(under_primary["books"][0]["book_side"], "under")

        for books in (primary["books"], primary["book_specs"]):
            result = pm.evaluate_candidate(
                {
                    "dist": "poisson",
                    "side": "over",
                    "line": 2.5,
                    "baseline_mean": 3.2,
                    "baseline_n": 30,
                    "soft_flags": 0,
                    "mechanisms": 1,
                    "hard_veto": False,
                    "data_veto": False,
                    "research_checklist": False,
                    "books": books,
                    "retrieved_minutes_ago": primary["retrieved_minutes_ago"],
                }
            )
            self.assertTrue(result["ok"])
            self.assertEqual(
                result["market_checks"],
                ["line_match", "side_match", "timestamp_fresh", "hold_ok", "approved_books"],
            )

    def test_quotes_file_keeps_one_row_per_book_line(self):
        quotes_path = SKILL_DIR / "data" / "odds_quotes.jsonl"
        before = quotes_path.read_bytes() if quotes_path.exists() else None
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "odds_quotes.jsonl"
                rows = self.rows()

                def nhl():
                    return rows, None, []

                def odds():
                    return self.quotes(), None, [SOURCE]

                _saved, summary = fs.collect(
                    "2026-10-22",
                    retrieved_at=NOW,
                    fetchers={"nhl": nhl, "nfl": lambda: ([], None), "nba": lambda: ([], None), "odds": odds},
                    clock=lambda: NOW,
                    quotes_path=out,
                )
                self.assertEqual(summary["feeds"]["odds"]["status"], "ok")
                self.assertEqual(summary["feeds"]["odds"]["rows"], 10)
                text = out.read_text(encoding="utf-8")
                stored = [json.loads(line) for line in text.splitlines() if line]
                self.assertEqual(len(stored), 10)
                fanduel = [row for row in stored if row["player_norm"] == "tim stutzle" and row["book"] == "FanDuel"]
                self.assertEqual(sorted(row["line"] for row in fanduel), [2.5, 3.5])
                self.assertIn("same name on more than one team", " ".join(summary["feeds"]["odds"]["notes"]))
                self.assertNotIn("underdog", text.lower())
        finally:
            after = quotes_path.read_bytes() if quotes_path.exists() else None
            self.assertEqual(before, after)

    def _record(self, book, line):
        return {
            "sport": "NHL",
            "player": "Tim Stutzle",
            "team": "BOS",
            "stat": "shots on goal",
            "book": book,
            "line": line,
            "over_odds": -120,
            "under_odds": 100,
            "retrieved_at": "2026-10-22T16:00:00Z",
            "source_url": "https://example.test/odds",
        }


class ProviderTests(unittest.TestCase):
    def test_missing_key_fetches_nothing(self):
        def boom(*_args, **_kwargs):
            raise AssertionError("network")

        provider = op.TheOddsAPIProvider(api_key="", fetch=boom)
        quotes = provider.fetch("2026-10-22", ["NBA", "NHL", "NFL"])
        self.assertEqual(quotes, [])
        self.assertIn("ODDS_API_KEY", provider.note)
        self.assertIn("not configured", provider.note)
        self.assertIn("invented", provider.note)

    def test_live_provider_filters_the_date_and_hides_the_key(self):
        event = load_json("odds_api_events.json")[0]
        calls = []

        def fake(url, timeout=20, headers=None):
            calls.append(url)
            self.assertNotIn("underdog", url.lower())
            if "/events/" in url and "/odds" in url:
                return event
            if url.split("?", 1)[0].endswith("/events"):
                return [
                    {
                        "id": "evt-bos-nsh",
                        "commence_time": "2026-10-23T00:00:00Z",
                        "home_team": "Boston Bruins",
                        "away_team": "Nashville Predators",
                    },
                    {
                        "id": "tomorrow",
                        "commence_time": "2026-10-23T23:00:00Z",
                        "home_team": "Boston Bruins",
                        "away_team": "Nashville Predators",
                    },
                ]
            raise AssertionError(url)

        provider = op.TheOddsAPIProvider(api_key="secret-key", fetch=fake, clock=lambda: NOW)
        quotes = provider.fetch("2026-10-22", ["NHL"])
        self.assertGreater(len(quotes), 0)
        odds_calls = [url for url in calls if "/odds" in url]
        self.assertEqual(len(odds_calls), 1)
        self.assertIn("evt-bos-nsh", odds_calls[0])
        self.assertNotIn("tomorrow", "".join(calls))
        self.assertNotIn("secret-key", json.dumps(quotes))
        self.assertTrue(all("secret-key" not in url for url in provider.source_urls))
        self.assertTrue(all(url.startswith("https://api.the-odds-api.com/") for url in provider.source_urls))
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(odds_calls[0]).query)
        books = query["bookmakers"][0].split(",")
        self.assertEqual(list(op.REQUEST_BOOKMAKERS), books)

    def test_unknown_bookmaker_key_retries_without_inventing_prices(self):
        event = {
            "id": "evt-bos-nsh",
            "sport_key": "icehockey_nhl",
            "home_team": "Boston Bruins",
            "away_team": "Nashville Predators",
            "bookmakers": [
                {
                    "key": "pinnacle",
                    "markets": [
                        {
                            "key": "player_shots_on_goal",
                            "last_update": "2026-10-22T16:00:00Z",
                            "outcomes": [
                                {"name": "Over", "description": "Tim Stutzle", "price": -130, "point": 2.5},
                                {"name": "Under", "description": "Tim Stutzle", "price": 110, "point": 2.5},
                            ],
                        }
                    ],
                }
            ],
        }
        odds_calls = []

        class Denied(Exception):
            def __init__(self, code, body):
                super().__init__(body)
                self.code = code
                self._body = body.encode()

            def read(self):
                return self._body

            def close(self):
                return None

        def fake(url, timeout=20, headers=None):
            if "/odds" in url:
                odds_calls.append(url)
                if len(odds_calls) == 1:
                    raise Denied(400, "Unknown bookmaker circa")
                return event
            return [
                {
                    "id": "evt-bos-nsh",
                    "commence_time": "2026-10-23T00:00:00Z",
                    "home_team": "Boston Bruins",
                    "away_team": "Nashville Predators",
                }
            ]

        provider = op.TheOddsAPIProvider(api_key="secret-key", fetch=fake, clock=lambda: NOW)
        quotes = provider.fetch("2026-10-22", ["NHL"])
        self.assertEqual(len(quotes), 1)
        self.assertEqual(quotes[0]["book"], "Pinnacle")
        self.assertEqual(len(odds_calls), 2)
        second = urllib.parse.parse_qs(urllib.parse.urlsplit(odds_calls[1]).query)["bookmakers"][0].split(",")
        self.assertEqual(list(op.DOCUMENTED_BOOKMAKERS), second)
        self.assertNotIn("circa", second)
        self.assertIn("Retried", provider.note)
        self.assertNotIn("secret-key", provider.note)

    def test_network_failure_names_the_allowlist_and_invents_nothing(self):
        def fake(url, timeout=20, headers=None):
            raise OSError(f"Network access to {url} is not permitted")

        provider = op.TheOddsAPIProvider(api_key="secret-key", fetch=fake, clock=lambda: NOW)
        quotes = provider.fetch("2026-10-22", ["NHL"])
        self.assertEqual(quotes, [])
        self.assertIn(op.ALLOWLIST_NOTE, provider.note)
        self.assertNotIn("secret-key", provider.note)
        self.assertIn("invented", provider.note)

    def test_allowlist_is_documented_outside_the_skill(self):
        provider_text = (SKILL_DIR / "scripts" / "odds_providers.py").read_text(encoding="utf-8")
        readme = (SKILL_DIR / "README.md").read_text(encoding="utf-8")
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(op.ALLOWLIST_NOTE, provider_text)
        self.assertIn(op.ALLOWLIST_NOTE, readme)
        self.assertNotIn("api.the-odds-api.com", skill)
        self.assertNotIn("underdog.com", provider_text.lower())
        self.assertNotIn("underdog", ",".join(op.REQUEST_BOOKMAKERS))


if __name__ == "__main__":
    unittest.main()
