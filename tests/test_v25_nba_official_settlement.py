"""Independent synthetic NBA final-identity and provider-byte tests.

These fixtures never count as authentic original official settlement.
"""
from __future__ import annotations
import copy
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from v2.p0_integrity.contracts import record,sha256
from research.v25_remediation import nba_official_settlement as a

START="2026-11-22T20:30:00Z"
FINAL="2026-11-22T23:45:00Z"
URL=a.BASE+"401999001"
def summary(*,status="STATUS_FINAL",completed=True,team_id="1",
            event_id="401999001",player_id="99",dnp=False,teams=None):
    competitors=teams or [
      {"team":{"id":"1","abbreviation":"ATL"}},
      {"team":{"id":"2","abbreviation":"BOS"}}]
    raw={"header":{"competitions":[{"id":event_id,
       "status":{"type":{"name":status,"completed":completed}},
       "competitors":competitors}]},
      "boxscore":{"players":[
       {"team":{"id":team_id,"abbreviation":"ATL"},
        "statistics":[{"labels":["MIN","PTS","REB","AST","3PT"],
         "athletes":[{"athlete":{"id":player_id},"didNotPlay":dnp,
                     "stats":["29:30","14","6","5","2-7"]}]}]},
       {"team":{"id":"2","abbreviation":"BOS"},
        "statistics":[{"labels":["MIN","PTS","REB","AST","3PT"],
         "athletes":[{"athlete":{"id":"88"},"stats":["31:00","12","4","5","1-6"]}]}]}
       ]}}
    return json.dumps(raw,sort_keys=True,separators=(",",":")).encode()

def frozen(stat="points",player="espn:player:99",team="espn:team:1"):
    f={"sport":"NBA","event_id":"espn:game:401999001",
       "event_start_at":START,"team_id":team,"opponent_id":"espn:team:2",
       "player_id":player,"stat_key":stat,"period":"full",
       "admission_class":"A","eligible":False,"quote_id":None,
       "abstention_reasons":["PARTICIPATION_UNRESOLVED",
             "CONDITIONAL_ON_PLAYING_ONLY","ELIGIBILITY_UNVERIFIED"],
       "uncertainty":{"family":"S0","pipeline":"S_ONLY"}}
    return {"forecast":f,"feature":{"reconstruction_class":"original"}}

class ProviderFinalTests(unittest.TestCase):
    def verify(self,body):
        return a.parse_verified_nba_final(
           body,original_event_id="espn:game:401999001",
           expected_team_ids={"espn:team:1","espn:team:2"})

    def test_exact_final_game_and_team_player_source(self):
        parsed=self.verify(summary())
        self.assertEqual(parsed["played"]["99"]["points"],14)
        self.assertEqual(parsed["played"]["99"]["threes"],2)
        self.assertEqual(parsed["teams"],{"1":"ATL","2":"BOS"})

    def test_nonfinal_and_wrong_event_fail_closed(self):
        for body in (summary(status="STATUS_IN_PROGRESS",completed=False),
                     summary(event_id="401999002"),
                     summary(teams=[{"team":{"id":"1","abbreviation":"ATL"}},
                                    {"team":{"id":"3","abbreviation":"BOS"}}])):
            with self.subTest(body=body[:50]):
                with self.assertRaises(a.FinalBlocked):self.verify(body)

    def test_absent_and_dnp_do_not_become_zero(self):
        parsed=self.verify(summary(dnp=True))
        self.assertNotIn("99",parsed["played"])
        self.assertEqual(parsed["played"]["88"]["points"],12)

    def test_raw_source_corruption_and_identity_rejected(self):
        with self.assertRaises(a.FinalBlocked):
            self.verify(b"broken")
        with self.assertRaises(a.FinalBlocked):
            self.verify(summary(team_id="unknown"))

    def test_observation_before_event_rejected_and_no_mutation(self):
        with patch.object(a,"_archive_final") as archive:
            with self.assertRaisesRegex(a.FinalBlocked,
                                        "OFFICIAL_OBSERVATION_NOT_AFTER_EVENT"):
                a.admit_one_final([frozen()],summary(),
                   observed_at="2026-11-22T19:00:00Z",url=URL)
            archive.assert_not_called()

    def test_source_byte_archive_and_provenance_preserved(self):
        with TemporaryDirectory() as d:
            with patch.object(a,"ROOT",Path(d)),patch.object(
                a,"_first_same_raw_receipt",return_value=None),patch.object(
                a,"verify_source_bytes",return_value=True),patch.object(
                a,"append_immutable") as store:
                source=a._archive_final(summary(),"espn:game:401999001",
                                        URL,FINAL)
                self.assertEqual(source["provenance_class"],
                                 "collector_possession")
                self.assertEqual(source["collected_at"],FINAL)
                raw_path=Path(d)/source["archive_path"]
                self.assertEqual(raw_path.read_bytes(),summary())
                store.assert_called_once()

    def test_independent_played_only_outcome_and_missing_player(self):
        source=record("SourceReceipt",
          receipt_id="existing-official-source",source_id=URL,
          source_kind="nba_espn_final_summary",
          source_available_at=FINAL,collected_at=FINAL,
          source_sha256=a.digest(summary()),
          archive_path="some/verified/raw.json",
          provenance_class="collector_possession")
        receipts=[]
        def save(root,kind,obj):
            receipts.append((kind,obj))
            return {"status":"APPENDED","sha256":sha256(obj)}
        rows=[frozen(stat="points"),frozen(stat="threes"),
              frozen(stat="rebounds",player="espn:player:777")]
        with patch.object(a,"_archive_final",return_value=source),patch.object(
            a,"recover_official_outcomes",return_value={"by_stat_identity":{}}),patch.object(
            a,"append_immutable",side_effect=save):
            result=a.admit_one_final(rows,summary(),observed_at=FINAL,url=URL)
        self.assertEqual(len(receipts),2)
        self.assertTrue(all(x["actual_value"]>=0 and x["participation"]=="PLAYED"
                            for _,x in receipts))
        self.assertEqual({x["stat_key"] for _,x in receipts},{"points","threes"})
        self.assertEqual(result["unresolved"][0]["reason"],
                         "NOT_IN_OFFICIAL_PLAYED_BOX_DNP_NOT_ASSUMED")

    def test_existing_official_outcome_is_not_revised_by_rerun(self):
        source=record("SourceReceipt",
          receipt_id="existing-official-source",source_id=URL,
          source_kind="nba_espn_final_summary",
          source_available_at=FINAL,collected_at=FINAL,
          source_sha256=a.digest(summary()),
          archive_path="some/verified/raw.json",
          provenance_class="collector_possession")
        row=frozen()
        f=row["forecast"]
        key=tuple(f[k] for k in ("sport","event_id","team_id","player_id",
                                 "stat_key","period"))
        with patch.object(a,"_archive_final",return_value=source),patch.object(
            a,"recover_official_outcomes",return_value={"by_stat_identity":{key:[{"outcome_id":"prior"}]}}),patch.object(
            a,"append_immutable") as save:
            out=a.admit_one_final([row],summary(),observed_at=FINAL,url=URL)
            self.assertEqual(out["outcome_rows"][0]["status"],
                             "PRIOR_OFFICIAL_OUTCOME_PRESERVED")
            save.assert_not_called()


if __name__=="__main__":
    unittest.main()
