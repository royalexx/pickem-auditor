"""Integration tests for WS1 router (requires pinned WS6 scorer in Deepnote)."""
from __future__ import annotations
import copy,hashlib,pathlib,tempfile,unittest,json
from research.ws1_nfl_postgame_20261116.recover_research_settlement import (
    classify_metadata,validate_quote,iso,hashfile,dump_json,
    FROZEN_EXPECTED,RAW,QUOTES
)
from research.ws6_nfl_sunday_20261115.independent_postgame_20261116 import (
    assess,verify_joint_contract_identity,get_stat
)
def quote():
    return {"quote_id":"q","event_id":"401873055","player":"Player A",
            "book":"BetMGM","stat":"pass attempts","line":30.5,
            "kickoff_utc":"2026-11-15T18:00:00Z","over_odds":-115,"under_odds":-105}
def linked():
    return {"quote_id":"q","event_id":"401873055",
            "source_sha256":FROZEN_EXPECTED[str(RAW)],
            "source_received_at":"2026-11-15T04:32:39Z",
            "original_record":{"player":"Player A","book":"BetMGM",
              "stat":"pass attempts","line":30.5,"over_odds":-115,
              "under_odds":-105,"event_start":"2026-11-15T18:00:00Z"}}
def ws5():
    return {"quote_id":"q","reasons":[],
            "original_provider_market_description":"Player A Passing Attempts",
            "source_certified":True,"settlement_status":"UNCERTIFIED"}

class RouterTests(unittest.TestCase):
    def test_consistent_internal_join_not_certification(self):
        self.assertEqual(validate_quote(quote(),linked(),ws5()),[])
        self.assertIn("ORIGINAL_SETTLEMENT_TERMS_UNVERIFIED",classify_metadata(quote(),ws5()))
    def test_provider_wrong_player_description(self):
        c=classify_metadata(quote(),dict(ws5(),original_provider_market_description="Player B Passing Attempts"))
        self.assertIn("CLAIMED_PROVIDER_DESCRIPTION_PLAYER_MISMATCH",c)
    def test_missing_source_receipt(self):
        self.assertIn("MISSING_ARCHIVED_ORIGINAL_SOURCE_LINK",validate_quote(quote(),None,ws5()))
    def test_wrong_event(self):
        self.assertIn("EVENT_ID_MISMATCH",validate_quote(quote(),dict(linked(),event_id="401873056"),ws5()))
    def test_wrong_original_player(self):
        z=linked();z["original_record"]["player"]="Player B"
        self.assertIn("ORIGINAL_PLAYER_LABEL_MISMATCH",validate_quote(quote(),z,ws5()))
    def test_wrong_original_book(self):
        z=linked();z["original_record"]["book"]="FanDuel"
        self.assertIn("BOOK_MISMATCH",validate_quote(quote(),z,ws5()))
    def test_wrong_market(self):
        z=linked();z["original_record"]["stat"]="completions"
        self.assertIn("MARKET_MISMATCH",validate_quote(quote(),z,ws5()))
    def test_alt_line_collision(self):
        z=linked();z["original_record"]["line"]=31.5
        self.assertIn("ORIGINAL_LINE_MISMATCH",validate_quote(quote(),z,ws5()))
    def test_tampered_over_under_price(self):
        z=linked();z["original_record"]["over_odds"]=-150
        self.assertIn("ORIGINAL_PRICE_PAIR_MISMATCH",validate_quote(quote(),z,ws5()))
    def test_wrong_kickoff(self):
        z=linked();z["original_record"]["event_start"]="2026-11-15T21:00:00Z"
        self.assertIn("ORIGINAL_EVENT_START_MISMATCH",validate_quote(quote(),z,ws5()))
    def test_delayed_receipt_after_kickoff(self):
        z=linked();z["source_received_at"]="2026-11-15T20:00:00Z"
        self.assertIn("SOURCE_RECEIPT_NOT_PREGAME",validate_quote(quote(),z,ws5()))
    def test_original_raw_sha_tamper(self):
        z=linked();z["source_sha256"]="0"*64
        self.assertIn("ORIGINAL_RAW_RECEIPT_SHA_MISMATCH",validate_quote(quote(),z,ws5()))
    def test_unaware_timestamp_invalid(self):
        self.assertIsNone(iso("2026-11-15T18:00:00"))
        self.assertIsNotNone(iso("2026-11-15T18:00:00Z"))
    def test_sha_guard_and_missing_archive(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/"a.json";p.write_bytes(b"content")
            self.assertEqual(hashfile(p,hashlib.sha256(b"content").hexdigest()),
                             hashlib.sha256(b"content").hexdigest())
            with self.assertRaisesRegex(RuntimeError,"TAMPERED_FROZEN_SOURCE"):
                hashfile(p,"0"*64)
            with self.assertRaisesRegex(RuntimeError,"MISSING_FROZEN_SOURCE"):
                hashfile(pathlib.Path(td)/"not-present")
    def test_joint_period_and_market_rejected(self):
        original=quote()
        original["stat"]="pass attempts"
        good={"quote_id":"q","event_id":"401873055","normalized_market":"pass_attempts",
              "period":"full_game","line":30.5,"original_record":{"player":"Player A"}}
        self.assertTrue(verify_joint_contract_identity(original,good))
        with self.assertRaisesRegex(ValueError,"MARKET_PERIOD_MISMATCH"):
            verify_joint_contract_identity(original,dict(good,period="first_half"))
        with self.assertRaisesRegex(ValueError,"MARKET_IDENTITY_MISMATCH"):
            verify_joint_contract_identity(original,dict(good,normalized_market="pass_completions"))
    def test_push_not_scored_as_binary_loss(self):
        p=assess(.4,.2,35,35)
        self.assertEqual(p["direction"],"PUSH");self.assertIsNone(p["brier"])
    def test_missing_boxscore_not_zero(self):
        self.assertEqual(get_stat("missing","1","P","pass_attempts",{})[1],"EVENT_MISSING")
    def test_output_is_create_once(self):
        with tempfile.TemporaryDirectory() as td:
            path=pathlib.Path(td)/"file.json"
            expected=dump_json(path,{"status":"BLOCKED"})
            self.assertEqual(dump_json(path,{"status":"BLOCKED"}),expected)
            with self.assertRaises(Exception):
                dump_json(path,{"status":"APPROVED"})

if __name__=="__main__":unittest.main()
