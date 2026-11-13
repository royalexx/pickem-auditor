"""C03 fail-closed cohort and raw-source binding regression tests."""
import hashlib
import json
import tempfile
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from scripts.c03_context_cohorts import (
    CohortError, classify, neutralize, verify_context_binding,
    neutral_digest, archive_response, register_research_adjustment,
    settlement_disposition,strict_c03_snapshot_status,archive_original_candidate,
)

FREEZE="2026-11-12T19:00:00Z"
EVENT="2026-11-13T00:00:00Z"
BEFORE="2026-11-12T18:00:00Z"


def original(pid="star",sport="NBA",stat="points",team="WAS"):
    return {"id":sport+"|"+pid+"|"+stat+"|over","sport":sport,"player_id":pid,
            "team":team,"event_id":"e1","stat":stat,"side":"over",
            "line":12.5,"game_date":"2026-11-12",
            "soft_flags":3,"research_soft_flags":2,
            "mechanisms":1,"research_checklist":True,
            "hard_veto":"no","data_veto":"no",
            "research_merge_base":{"hard_veto":"no","data_veto":"no"},
            "scouting":{"historical_usage":"history-digest","event_context":{"events":[1]},
                        "scenarios":[{"future":"untrusted"}]},
            "event_context":{}}


def claim(root,pid,value,kind="subject_status",team="WAS",event="e1",
          received=BEFORE,actual=None):
    obj={"event_id":event,"team_id":team,"player_id":pid,"status":actual or value}
    raw=json.dumps(obj,sort_keys=True).encode()
    receipt=archive_response(raw,archive_root=root,
       source_url="https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary",
       observed_at=received,received_at=received,source_id="r-"+str(len(list(root.glob("raw_http_body/*")))),
       source_namespace="espn",http_status=200)
    return receipt,{"schema":"availability_claim_v2","source_id":receipt["source_id"],
       "kind":kind,"event_id":event,"team_id":team,"player_id":pid,
       "value":value,"value_path":"/status","event_id_path":"/event_id",
       "team_id_path":"/team_id","player_id_path":"/player_id"}


class C03CohortTests(unittest.TestCase):
    def test_neutral_drops_every_research_numeric_dependency(self):
        a=original()
        b=original()
        b["event_context"]={"events":[{"player_id":"bench"}]}
        b["hard_veto"]="yes"; b["data_veto"]="yes"
        b["availability_issue"]="STATUS_NOT_VERIFIED"
        b["weather_issue"]="clouds"
        b["spread"]=-8.5
        b["soft_flags"]=3
        n1=neutralize(a); n2=neutralize(b)
        self.assertEqual(n1,n2)
        self.assertEqual(n2["soft_flags"],1)
        self.assertEqual(n2["mechanisms"],0)
        self.assertEqual(n2["scouting"],{"historical_usage":"history-digest"})
        self.assertEqual(neutral_digest(n1),neutral_digest(n2))

    def test_verified_out_teammate_is_b_neutral_and_player_out_d(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);r,c=claim(root,"bench","out",kind="teammate_status")
            a=original();a["event_context"]={"events":[{"player_id":"bench"}]}
            result=classify(a,source_receipts=[r],claims=[c],
                            archive_root=root,input_freeze_at=FREEZE,event_start_at=EVENT)
            self.assertEqual(result["cohort"],"B")
            self.assertEqual(result["neutral_candidate"],neutralize(original()))
            self.assertEqual(result["binding"]["schema"],"pickem_context_cohort_v2")
            self.assertTrue(verify_context_binding(result["binding"],archive_root=root,
                       original_candidate=a,neutral_candidate=result["neutral_candidate"],
                       input_freeze_at=FREEZE,event_start_at=EVENT)[0])
            active=original(pid="bench")
            active["event_context"]={"subject_status":{"value":"out"}}
            r2,c2=claim(root,"bench","out")
            self.assertEqual(classify(active,source_receipts=[r2],claims=[c2],
                archive_root=root,input_freeze_at=FREEZE,event_start_at=EVENT)["cohort"],"D")

    def test_conflict_late_tamper_and_wrong_identity(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a=original();a["event_context"]={"subject_status":{"value":"active"}}
            r,c=claim(root,"star","active")
            good=classify(a,source_receipts=[r],claims=[c],archive_root=root,
                          input_freeze_at=FREEZE,event_start_at=EVENT)
            self.assertEqual(good["cohort"],"B")
            r2,c2=claim(root,"star","out")
            self.assertEqual(classify(a,source_receipts=[r,r2],claims=[c,c2],
                archive_root=root,input_freeze_at=FREEZE,event_start_at=EVENT)["reason"],
                "AVAILABILITY_CONFLICT")
            late,_=claim(root,"star","active",received="2026-11-12T20:00:00Z")
            self.assertEqual(classify(a,source_receipts=[late],claims=[c],
                archive_root=root,input_freeze_at=FREEZE,event_start_at=EVENT)["cohort"],"D")
            wrong,wrong_claim=claim(root,"star","active",team="NYG")
            self.assertEqual(classify(a,source_receipts=[wrong],claims=[wrong_claim],
                archive_root=root,input_freeze_at=FREEZE,event_start_at=EVENT)["reason"],
                "SOURCE_IDENTITY_MISMATCH")
            path=root/r["archive_path"]
            path.write_bytes(b"tampered")
            self.assertFalse(verify_context_binding(good["binding"],archive_root=root,
                       original_candidate=a,neutral_candidate=good["neutral_candidate"],
                       input_freeze_at=FREEZE,event_start_at=EVENT)[0])

    def test_unknown_questionable_and_backup(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a=original();a["event_context"]={"subject_status":{"value":"questionable"}}
            r,c=claim(root,"star","questionable")
            self.assertEqual(classify(a,source_receipts=[r],claims=[c],archive_root=root,
                input_freeze_at=FREEZE,event_start_at=EVENT)["reason"],"STATUS_UNCERTAIN")
            self.assertEqual(classify(a,source_receipts=[],claims=[],archive_root=root,
                input_freeze_at=FREEZE,event_start_at=EVENT)["reason"],"SOURCE_RECEIPT_MISSING")
            qb=original(sport="NFL",stat="pass attempts")
            self.assertEqual(classify(qb,source_receipts=[],claims=[],archive_root=root,
                input_freeze_at=FREEZE,event_start_at=EVENT)["reason"],"STARTING_QB_UNVERIFIED")

    def test_nhl_goalie_membership_not_starter(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            goalie=original(sport="NHL",stat="goalie saves",team="WSH")
            roster,roster_claim=claim(root,"star","member",kind="roster_membership",team="WSH")
            out=classify(goalie,source_receipts=[roster],claims=[roster_claim],
                 archive_root=root,input_freeze_at=FREEZE,event_start_at=EVENT)
            self.assertEqual(out["reason"],"NHL_STARTING_GOALIE_UNVERIFIED")
            starter,starter_claim=claim(root,"star","starter",kind="named_nhl_starting_goalie",team="WSH")
            out=classify(goalie,source_receipts=[roster,starter],
                 claims=[roster_claim,starter_claim],
                 archive_root=root,input_freeze_at=FREEZE,event_start_at=EVENT)
            self.assertEqual(out["cohort"],"B")

    def test_settlement_void_and_early_exit(self):
        played=settlement_disposition(
            participated=True,official_state="settled",actual_stat=0,line=1.5,
            void_terms_verified=True,provider_void_on_dnp=True)
        self.assertEqual(played["status"],"under")
        self.assertTrue(played["scoreable"])
        early=settlement_disposition(
            participated=True,official_state="settled",actual_stat=1,line=1,
            void_terms_verified=True,provider_void_on_dnp=True)
        self.assertEqual(early["status"],"push")
        dnp=settlement_disposition(
            participated=False,official_state="dnp",actual_stat=None,line=1.5,
            void_terms_verified=True,provider_void_on_dnp=True)
        self.assertEqual(dnp["status"],"VOID")
        unknown=settlement_disposition(
            participated=False,official_state="postponed",actual_stat=None,line=1.5,
            void_terms_verified=False,provider_void_on_dnp=None)
        self.assertEqual(unknown["status"],"UNVERIFIED_VOID_RULE")

    def test_unattested_context_cannot_pass_strict_certification(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            a=original();a["event_context"]={"events":[{"player_id":"bench"}]}
            r,c=claim(root,"bench","out",kind="teammate_status")
            plan=classify(a,source_receipts=[r],claims=[c],archive_root=root,
                          input_freeze_at=FREEZE,event_start_at=EVENT)
            binding=plan["binding"]
            binding["original_candidate_receipt"]=archive_original_candidate(a,root,possessed_at=BEFORE)
            row={"c03_context_binding":binding,"c03_original_candidate":a,
                 "inputs":plan["neutral_candidate"],"input_freeze_at":FREEZE,
                 "event_start":EVENT}
            with patch("phase0r_contract.strict_snapshot_status",return_value=(True,"ok")):
                ok,reason=strict_c03_snapshot_status(row,archive_root=root)
            self.assertFalse(ok)
            self.assertEqual(reason,"C03_LIVE_TRANSPORT_NOT_ATTESTED")

    def test_research_adjustment_shadow_only(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            baseline=classify(original(),source_receipts=[],claims=[],archive_root=root,
                              input_freeze_at=FREEZE,event_start_at=EVENT)
            self.assertEqual(baseline["cohort"],"A")
            with self.assertRaises(CohortError):
                register_research_adjustment(baseline,{"probability":.9},archive_root=root)
            self.assertEqual(baseline["status"],"source_input_certifiable_not_Tier_eligible")


if __name__=="__main__":
    unittest.main()
