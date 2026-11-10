"""NHL/NBA Phase 1: real original source gate, denominator and settlement red-team."""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"scripts"))
sys.path.insert(0, str(ROOT/"tests"))

from phase0_pre_eval import pin
from test_phase0r_pre_eval import START, build_row
from usage_baseline import key as usage_key
from v2.contracts import ContractError
from v2.nhl_nba_phase1 import (_observations, _legacy_baseline,
                               _market_reference, _original_archives,
                               _settlement_index, run_phase1)


def fixture(root):
    data = root/"input"
    data.mkdir(parents=True)
    usage = data/"usage"
    usage.mkdir()
    usage_id = usage_key("NHL","8470001","shots on goal","2026-11-09")
    (usage/(usage_id+".json")).write_text(json.dumps({
        "sport":"NHL", "player_id":"8470001", "stat":"shots on goal",
        "retrieved_at":"2026-11-09T14:00:00Z",
        "source_url":"https://api.nhle.com/stats/rest/en/skater/summary",
        "observations":[{"id":"old-game","date":"2026-11-02",
                         "value":5,"workload":20}],
    }))
    quote = {
        "sport":"NHL","event_id":"event-1",
        "event_id_namespace":"propline",
        "event_start":"2026-11-09T18:00:00Z",
        "player":"Example Player","player_norm":"example player",
        "stat":"shots on goal","book":"Pinnacle",
        "line":4.5,"over_odds":-110,"under_odds":-110,
        "retrieved_at":"2026-11-09T14:10:00Z",
        "source_url":"https://api.prop-line.com/v1/sports/icehockey_nhl/odds",
    }
    (data/"odds_quotes.jsonl").write_text(json.dumps(quote)+"\n")
    (data/"research_2026-11-09.json").write_text('{"internal_research":true}')
    (root/"config").mkdir(parents=True)
    (root/"config"/"production_consensus.json").write_text('{"weights":{"a":0.6,"b":0.4}}')
    rows=[]
    for side in ("over","under"):
        candidate = {
            "id":f"NHL|Example Player|shots on goal|{side}",
            "sport":"NHL","stat":"shots on goal",
            "player_id":"8470001","player":"Example Player",
            "team":"BUF","opponent":"KC","game_date":"2026-11-09",
            "event_id":"event-1","event_id_namespace":"propline",
            "line":4.5,"side":side,
            "books":[{"book":"Pinnacle","line":4.5,"book_side":side,
                      "target":-110,"other":-110}],
            "market_retrieved_at":"2026-11-09T14:10:00Z",
        }
        with pin(candidate, data_root=data,
                 archive_root=data/"source_archives",policy_root=root,
                 clock=lambda:START) as (evidence, _frozen, frozen):
            row = build_row(frozen, evidence)
            row.update({
                "sport":"NHL","player":"Example Player",
                "player_id":"8470001","stat":"shots on goal","side":side,
                "team":"BUF","opponent":"KC",
                "event_id_namespace":"propline",
                "q_model":None,"blend":{"production_policy":True,
                   "preliminary":True,"available":True,"weights":{"a":.6,"b":.4}}
            })
            row["market"]["books"]=[{
                "book":"Pinnacle","line":4.5,"over":-110,"under":-110,
                "retrieved_at":"2026-11-09T14:10:00Z"}]
            rows.append(row)
    archived=[]
    for file in sorted((data/"source_archives").rglob("*")):
        if file.is_file():
            raw=file.read_bytes()
            archived.append({
                "path":file.relative_to(data/"source_archives").as_posix(),
                "sha256":hashlib.sha256(raw).hexdigest(),
                "bytes":len(raw),
                "content_b64":base64.b64encode(raw).decode(),
            })
    packet={
        "predictions_are_frozen":True, "phase":"afternoon",
        "run_id":"original-run","settlements":[],
        "forecasts":rows,"phase0_source_input_archive":archived,
    }
    ledger={
        "all_prepared_contracts_attempted":True,
        "all_prepared_contracts_in_coverage_denominator":True,
        "attempts":[{
            "id":r["inputs"]["id"],"sport":"NHL","player_id":"8470001",
            "stat":"shots on goal","side":r["side"],"line":4.5,
            "status":"forecast",
        } for r in rows],
    }
    return packet,ledger


class FrozenNhlNbaContractTests(unittest.TestCase):
    def test_original_pair_replays_and_pending_is_not_zero_accuracy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            packet,ledger=fixture(root)
            report=run_phase1(packet,ledger,archive_root=root/"replay",
                bundle_sha256="a"*64,code_commit="a"*40)
            self.assertEqual((report["retained_paired_contracts"],
                              report["original_forecast_rows"]),(1,2))
            self.assertEqual(report["settlement_states"],
                             {"pending_official_settlement":1})
            self.assertIsNone(report["models"]["naive_recent_exposure_rate"]["brier"])
            self.assertEqual(report["models"]["frozen_v1_60_40"][
                "contract_status_counts"],{"unavailable":1})
            self.assertEqual(report["models"]["real_no_vig_market"][
                "contract_status_counts"],{"available":1})
            self.assertEqual(report["models"]["naive_recent_exposure_rate"][
                "contract_status_counts"],{"counterfactual_shadow":1})

    def test_rejects_forged_certified_quote_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            packet,ledger=fixture(root)
            q=packet["forecasts"][0]
            q["source_receipts"][0]["content_sha256"]="0"*64
            with self.assertRaisesRegex(ContractError,"uncertified_original_forecast"):
                run_phase1(packet,ledger,archive_root=root/"replay",
                           bundle_sha256="a"*64,code_commit="a"*40)

    def test_rejects_missing_or_mismatched_rejection_universe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            packet,ledger=fixture(root)
            ledger["attempts"][0]["status"]="unavailable"
            with self.assertRaisesRegex(ContractError,"rejected_candidate_in_frozen_forecasts"):
                run_phase1(packet,ledger,archive_root=root/"replay",
                           bundle_sha256="a"*64,code_commit="a"*40)

    def test_future_history_is_rejected(self):
        docs={"observations":[{"id":"future","date":"2026-11-10",
                                "value":5,"workload":20}]}
        with self.assertRaisesRegex(ContractError,"unproven_same_day_history_order"):
            _observations(docs,START)

    def test_original_date_only_history_is_allowed_only_before_freeze(self):
        docs={"observations":[{"id":"past","date":"2026-11-02",
                                "value":3,"workload":20}]}
        rows=_observations(docs,START)
        self.assertEqual(rows[0]["time_precision"],
                         "original_calendar_day_only_ordering")

    def test_bad_and_duplicate_immutable_sources_fail_closed(self):
        blob=b'{"ok":true}'
        entry={"path":"usage/x.bin","content_b64":base64.b64encode(blob).decode(),
               "bytes":len(blob),"sha256":hashlib.sha256(blob).hexdigest()}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ContractError,"duplicate_or_unsafe"):
                _original_archives({"phase0_source_input_archive":[entry,entry]},
                                   Path(tmp)/"archive")
            bad={**entry,"sha256":"0"*64}
            with self.assertRaisesRegex(ContractError,"hash_or_length"):
                _original_archives({"phase0_source_input_archive":[bad]},
                                   Path(tmp)/"archive2")

    def test_market_no_vig_uses_real_two_sided_book(self):
        m={"market":{"books":[{"book":"FanDuel","line":4.5,
             "over":100,"under":-150,"retrieved_at":"2026-11-09T14:10:00Z"},
             {"book":"Pinnacle","line":4.5,"over":-110,"under":-110,
              "retrieved_at":"2026-11-09T14:10:00Z"}]}}
        r=_market_reference(m)
        self.assertEqual(r["book"],"Pinnacle")
        self.assertAlmostEqual(r["p_over_nonpush"],.5)

    def test_preliminary_consensus_is_not_original_v1(self):
        row={"reference_line":4.5,"q_model":.6,"q_push":0,
             "blend":{"production_policy":True,"available":True,
                      "preliminary":True,"weights":{"a":.6,"b":.4}}}
        other=deepcopy(row);other["q_model"]=.4
        self.assertEqual(_legacy_baseline(row,other)["status"],"unavailable")
        row["blend"]["preliminary"]=False
        other["blend"]["preliminary"]=False
        self.assertEqual(_legacy_baseline(row,other)["status"],"available")

    def test_official_settlement_requires_source_period_and_integer(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)
            body=b'{"source":"api-web.nhle.com","captured":true}'
            (source/"source.json").write_bytes(body)
            item={"sport":"NHL","event_id":"event-1","player_id":"8470001",
                  "stat":"shots on goal","period":"full","status":"settled",
                  "actual":3,"source_url":"https://api-web.nhle.com/v1/gamecenter",
                  "settled_at":"2026-11-09T21:00:00Z",
                  "retrieved_at":"2026-11-09T21:01:00Z",
                  "source_sha256":hashlib.sha256(body).hexdigest(),
                  "source_archive_path":"source.json"}
            self.assertEqual(len(_settlement_index([item],
                source_archive_root=source)),1)
            with self.assertRaisesRegex(ContractError,"duplicate_official"):
                _settlement_index([item,item],source_archive_root=source)
            with self.assertRaisesRegex(ContractError,"settlement_period_mismatch"):
                _settlement_index([{**item,"period":"regulation"}],
                                  source_archive_root=source)
            with self.assertRaisesRegex(ContractError,"noninteger"):
                _settlement_index([{**item,"actual":2.5}],
                                  source_archive_root=source)
            with self.assertRaisesRegex(ContractError,"source_archive_unverified"):
                _settlement_index([{**item,"source_sha256":"0"*64}],
                                  source_archive_root=source)
            with self.assertRaisesRegex(ContractError,"source_archive_required"):
                _settlement_index([item])

    def test_no_synthetic_settlement_or_postgame_features_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            packet,ledger=fixture(root)
            packet["settlements"]=[{"status":"settled"}]
            with self.assertRaisesRegex(ContractError,"non_original_afternoon"):
                run_phase1(packet,ledger,archive_root=root/"replay",
                           bundle_sha256="a"*64,code_commit="a"*40)


if __name__=="__main__":
    unittest.main()
