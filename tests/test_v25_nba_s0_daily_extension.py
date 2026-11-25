"""NBA S0 V2.5 daily coverage and UTC/backlog regression tests."""
from datetime import datetime,timezone
from unittest.mock import Mock, patch
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from research.v25_remediation import nba_s0_prospective as s0
from research.v25_remediation import nba_official_settlement as official
from research.v25_remediation import nba_s0_ou_sidecar as ou

CODE="4b5629bedd255b658422785456963a3fb441a52e"

class DailyExtensionTests(unittest.TestCase):
    def test_expand_up_to_ten_without_changing_default_capture(self):
        p1={"attempts":[],"counts":{},"games_discovered":1,
            "daily_manifest_sha256":"a"*64}
        with patch.object(s0,"attest_project_storage"),patch.object(
                s0,"load_predeclared_model",return_value={"artifact_sha256":"b"*64}),patch.object(
                s0,"run_daily",return_value=p1) as collector:
            r=s0.run_once(day="2026-11-23",code_commit=CODE,feature_player_limit=10,max_forecasts=40)
            self.assertEqual(r["frozen_handoff_count"],0)
            collector.assert_called_once_with(day="2026-11-23",wait=False,feature_player_limit=10)
            collector.reset_mock()
            s0.run_once(day="2026-11-23",code_commit=CODE)
            collector.assert_called_once_with(day="2026-11-23",wait=False,feature_player_limit=6)
            collector.reset_mock()
            for bad in (0,11,True,"10"):
                with self.assertRaisesRegex(s0.IntegrationBlocked,"INVALID_RESEARCH_STARTER_COVERAGE_CAP"):
                    s0.run_once(day="2026-11-23",code_commit=CODE,feature_player_limit=bad)
            collector.assert_not_called()

    def test_old_games_do_not_consume_official_ingest_budget(self):
        def f(game,event_start):
            return {"forecast":{"event_id":"espn:game:"+game,
              "event_start_at":event_start,
              "sport":"NBA","team_id":"espn:team:2","opponent_id":"espn:team:9",
              "player_id":"espn:player:3134903","stat_key":"points","period":"full"}}
        old=f("100","2026-11-18T01:00:00Z")
        new=f("200","2026-11-22T01:00:00Z")
        scope={"events":{"espn:game:100":[old],"espn:game:200":[new]},
               "rejections":[],"corrupt_or_incomplete":[]}
        oldkey=tuple(old["forecast"][k] for k in
            ("sport","event_id","team_id","player_id","stat_key","period"))
        with patch.object(official,"attest_project_storage"),patch.object(
               official,"_original_frozen_scope",return_value=scope),patch.object(
               official,"recover_official_outcomes",return_value={"by_stat_identity":{oldkey:[{"outcome":{}}]}}),patch.object(
               official,"capture_final",return_value={"raw":b"original","observed_at":"2026-11-23T13:00:00Z"}),patch.object(
               official,"parse_verified_nba_final",return_value={"raw_sha256":"a"*64}),patch.object(
               official,"atomic_bytes",return_value={"status":"APPENDED","sha256":"b"*64,"relative_path":"test"}) as stored:
            result=official.run_morning(max_games=1,fetch_only=True,
                clock=lambda:datetime(2026,11,23,14,tzinfo=timezone.utc))
            attempts=result["report"]["official_attempts"]
            self.assertEqual(len(attempts),1)
            self.assertEqual(attempts[0]["event_id"],"espn:game:200")
            self.assertEqual(attempts[0]["status"],"OFFICIAL_FINAL_FETCH_VERIFIED_ONLY")
            stored.assert_called_once()

    def test_absent_key_does_not_fetch_or_invent_lines(self):
        fake={"forecast":{"event_id":"espn:game:999",
            "event_start_at":"2026-11-24T01:00:00Z"}}
        with patch.object(ou,"attest_project_storage"),patch.object(
            ou,"qualified_forecasts",return_value=([fake],{})),patch.object(
            ou,"http_raw") as fetch:
            r=ou.capture_original_ou(day="2026-11-23",key="",
                clock=lambda:datetime(2026,11,23,17,tzinfo=timezone.utc))
            self.assertEqual(r["status"],"NO_AUTHENTIC_PROPLINE_CREDENTIAL")
            self.assertEqual(r["matched_quotes"],0)
            fetch.assert_not_called()

    def test_quota_probe_and_bulk_request_are_once_per_day_across_event_sets(self):
        def forecast(event):
            return {"forecast":{"event_id":event,"event_start_at":"2026-11-24T01:00:00Z",
                                "stat_key":"points"},"feature":{"features":{"current_name":"Fixture Player"}}}
        at=datetime(2026,11,23,21,tzinfo=timezone.utc)
        provider=Mock()
        provider.PropLineProvider._daily_quota_check.return_value=(10,None)
        with (TemporaryDirectory() as tmp,patch.object(ou,"ROOT",Path(tmp)),
              patch.object(ou,"attest_project_storage"),patch.object(ou,"odds_helpers",return_value=provider),
              patch.object(ou,"qualified_forecasts",side_effect=[([forecast("a")],{}),([forecast("b")],{})]),
              patch.object(ou,"http_raw",side_effect=[(b"{}",at.isoformat()),(b"[]",at.isoformat())]) as fetch,
              patch.object(ou,"event_crosswalk",return_value={"a":{}}),
              patch.object(ou,"original_source",return_value={"receipt_id":"r","source_sha256":"a"*64})):
            first=ou.capture_original_ou(day="2026-11-23",key="fixture",clock=lambda:at)
            second=ou.capture_original_ou(day="2026-11-23",key="fixture",clock=lambda:at)
        self.assertEqual(first["status"],"QUOTES_CAPTURED_OR_ABSTAINED")
        self.assertEqual(second["status"],"DAILY_OU_SCOPE_ALREADY_CLAIMED")
        provider.PropLineProvider._daily_quota_check.assert_called_once()
        self.assertEqual(sum(c.kwargs.get("key")=="fixture" for c in fetch.call_args_list),1)

    def test_legacy_day_claim_prevents_another_authenticated_call(self):
        f={"forecast":{"event_id":"new","event_start_at":"2026-11-24T01:00:00Z"}}
        with (TemporaryDirectory() as tmp,patch.object(ou,"ROOT",Path(tmp)),
              patch.object(ou,"attest_project_storage"),patch.object(ou,"odds_helpers") as provider,
              patch.object(ou,"qualified_forecasts",return_value=([f],{}))):
            path=Path(tmp)/ou.BASE/"claims"/"legacy.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"day":"2026-11-23","events":["old"]}))
            r=ou.capture_original_ou(day="2026-11-23",key="fixture",
                clock=lambda:datetime(2026,11,23,21,tzinfo=timezone.utc))
        self.assertEqual(r["status"],"DAILY_OU_SCOPE_ALREADY_CLAIMED")
        provider.assert_not_called()

if __name__=="__main__":unittest.main()
