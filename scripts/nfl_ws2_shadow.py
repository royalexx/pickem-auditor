#!/usr/bin/env python3
"""Offline Workstream 1 consumer. No live fetches, inferred offers or overwrites."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import scipy
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v2.contracts import (MarketQuote, SourceReceipt, EventProbabilities, canonical_hash,
                          utc, finite, no_vig_over)
from v2.nfl_marginal_shadow import (MODEL_IDS, PARAMETERS, VERSION, Unavailable,
    fit_laws, fixed_logit, probability_only)
from v2.stat_registry import canonical_stat

SCHEMA = "ws1-nfl-source-control-v1"
TARGET = "2026-11-15"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)+"\n").encode()


def source_packet(source_id, manifest, root, freeze, cache):
    if source_id in cache:
        return cache[source_id]
    receipts = [r for r in manifest["sources"] if r["source_id"] == source_id]
    if len(receipts) != 1:
        raise Unavailable("missing_or_duplicate_source_id")
    receipt = SourceReceipt(**receipts[0])
    if utc(receipt.retrieved_at, "retrieved_at") > freeze:
        raise Unavailable("source_retrieved_after_freeze")
    # Resolve symlinks as well as '..'; archives must stay within manifest root.
    path = (root/receipt.archive_path).resolve()
    if not path.is_relative_to(root.resolve()):
        raise Unavailable("source_path_escapes_manifest_root")
    raw = path.read_bytes()
    if sha(raw) != receipt.content_sha256:
        raise Unavailable("source_bytes_hash_mismatch")
    packet = json.loads(raw)
    if not isinstance(packet, dict):
        raise Unavailable("source_packet_not_object")
    cache[source_id] = packet
    return packet


def quote_object(raw):
    # Local binary market registration; global legacy registry remains untouched.
    copy = dict(raw)
    if copy.get("stat_key") == "anytime touchdown":
        copy["stat_key"] = "rushing touchdowns"
    quote = MarketQuote(**copy)
    if raw["sport"] != "NFL" or raw["league"] != "NFL" or raw["period"] != "full":
        raise Unavailable("not_full_game_nfl")
    return quote


def history_values(item, manifest, root, freeze, trained, cache, target_event):
    q = item["quote"]
    role, position = item.get("role"), item.get("position")
    if not isinstance(role, str) or not role.strip() or not isinstance(position, str) or not position.strip():
        raise Unavailable("missing_asof_role_position")
    peers = defaultdict(list)
    own, seen = [], set()
    ids = item.get("history_source_ids")
    if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)):
        raise Unavailable("history_source_ids_missing_or_duplicate")
    for sid in ids:
        packet = source_packet(sid, manifest, root, freeze, cache)
        rows = packet.get("observations")
        if not isinstance(rows, list):
            raise Unavailable("missing_observations")
        for r in rows:
            if r.get("sport") != "NFL":
                raise Unavailable("history_sport_mismatch")
            # A source bundle may contain other historical markets and roles.
            if (r.get("stat_key"), r.get("period"), r.get("position"), r.get("role")) != (q["stat_key"], q["period"], position, role):
                continue
            for key in ("event_id", "player_id", "observation_id", "team_id"):
                if not isinstance(r.get(key), str) or not r[key].strip():
                    raise Unavailable("missing_history_identity:"+key)
            if r["event_id"] in target_event:
                raise Unavailable("target_slate_event_in_history")
            ended = utc(r.get("game_end_at"), "game_end_at")
            available = utc(r.get("available_at"), "available_at")
            if not ended <= available <= trained:
                raise Unavailable("future_or_unavailable_training_observation")
            # Per-row source availability cannot precede original receipt availability.
            receipt = next(s for s in manifest["sources"] if s["source_id"] == sid)
            if (utc(receipt["first_available_at"], "first_available_at") > trained
                    or utc(receipt["retrieved_at"], "retrieved_at") > trained):
                raise Unavailable("history_source_available_after_training_cutoff")
            ident = (r["event_id"], r["player_id"], r["stat_key"], r["period"])
            if ident in seen:
                raise Unavailable("duplicate_history_player_event_stat")
            seen.add(ident)
            if r.get("appearance") != "appeared":
                # DNP/unknown remains in exclusion counts; cannot manufacture zero.
                continue
            y = finite(r["value"], "historical_value")
            values = own if r["player_id"] == q["player_id"] else peers[r["player_id"]]
            values.append((ended, r["event_id"], y))
    own.sort()
    ordered_peers = [sorted(xs) for _, xs in sorted(peers.items())]
    return ([x[2] for x in own], [[x[2] for x in xs] for xs in ordered_peers],
            {"eligible_own_observation_ids": [[x[1], q["player_id"]] for x in own],
             "history_source_ids": ids, "source_rows_seen": len(seen),
             "eligible_appearance_rows": len(own)+sum(map(len, ordered_peers))})


def original_control(item, manifest, root, freeze, now, cache):
    sid = item.get("control_source_id")
    packet = source_packet(sid, manifest, root, freeze, cache)
    matches = [c for c in packet.get("controls", []) if c.get("quote") == item["quote"]]
    if len(matches) != 1:
        raise Unavailable("missing_or_ambiguous_exact_contract_control")
    c = matches[0]
    if c.get("model_version") != "production-historical-ensemble-60-40-20261108-v1":
        raise Unavailable("wrong_legacy_control_version")
    if utc(c["forecast_at"], "control_forecast_at") > freeze:
        raise Unavailable("control_after_freeze")
    if utc(c["forecast_at"], "control_forecast_at") > now:
        raise Unavailable("control_not_yet_generated")
    p = EventProbabilities(c["q_over"], c["q_under"], c["q_push"])
    if p.over+p.under == 0:
        raise Unavailable("no_conditional_nonpush_control")
    return c, p.over/(p.over+p.under)


def unavailable(reason):
    return {"status": "unavailable", "reason": str(reason)}


def build(manifest, *, root, now, code_commit, manifest_sha256):
    now = utc(now, "forecast_at")
    if manifest.get("schema") != SCHEMA or manifest.get("owner") != "workstream1" or manifest.get("target_date") != TARGET:
        raise Unavailable("canonical_ws1_manifest_schema_owner_or_date_missing")
    freeze = utc(manifest["input_freeze_at"], "input_freeze_at")
    trained = utc(manifest["model_training_cutoff_at"], "model_training_cutoff_at")
    if not trained <= freeze <= now:
        raise Unavailable("invalid_training_freeze_forecast_order")
    if not isinstance(manifest.get("contracts"), list) or not isinstance(manifest.get("sources"), list):
        raise Unavailable("missing_canonical_contract_or_source_universe")
    cache, rows, seen, counts = {}, [], set(), Counter()
    source_ids = [s.get("source_id") for s in manifest["sources"]]
    if any(not isinstance(s, str) or not s for s in source_ids) or len(source_ids) != len(set(source_ids)):
        raise Unavailable("duplicate_or_missing_manifest_source_id")
    target_events = {i["quote"].get("event_id") for i in manifest["contracts"] if isinstance(i, dict) and isinstance(i.get("quote"), dict)}
    for index, item in enumerate(manifest["contracts"]):
        item = item if isinstance(item, dict) else {"invalid_input": item}
        raw_q = item.get("quote", {})
        output = {"input_index": index, "quote": raw_q,
                  "models": {m: unavailable("not_evaluated") for m in MODEL_IDS},
                  "controls": {}, "eligibility": "unavailable"}
        rows.append(output)
        try:
            quote = quote_object(raw_q)
            if quote.quote_id in seen:
                raise Unavailable("duplicate_original_quote_id")
            seen.add(quote.quote_id)
            start = utc(quote.event_start_at, "event_start_at")
            if start.astimezone(ZoneInfo("America/Toronto")).date().isoformat() != TARGET:
                raise Unavailable("wrong_target_event_day")
            if not now < start or not utc(quote.quote_at, "quote_at") <= freeze:
                raise Unavailable("not_pregame_or_quote_after_freeze")
            if quote.quote_kind != "real" or not quote.accepted:
                raise Unavailable("original_quote_rejected_or_synthetic")
            packet = source_packet(item.get("quote_source_id"), manifest, root, freeze, cache)
            if raw_q not in packet.get("quotes", []):
                raise Unavailable("exact_original_quote_not_bound_to_source_bytes")
            # Quote receipt hash may refer to a separate immutable raw provider body.
            receipt_path = quote.quote_archive_path
            if not receipt_path:
                raise Unavailable("original_raw_quote_archive_missing")
            path = (root/receipt_path).resolve()
            if not path.is_relative_to(root.resolve()) or sha(path.read_bytes()) != quote.quote_receipt_sha256:
                raise Unavailable("original_raw_quote_hash_mismatch")
            if item.get("participation_basis") != "conditional_appearance_dnp_void":
                raise Unavailable("unknown_participation_or_dnp_settlement")
            # The manifest supplies a source-bound as-of eligibility statement.
            if {k: item.get(k) for k in ("quote", "role", "position", "participation_basis")} not in packet.get("eligibility", []):
                raise Unavailable("role_participation_not_source_bound")
            output["eligibility"] = "appearance_conditional_shadow"
            output["control_status"] = {}
            try:
                c, legacy_p = original_control(item, manifest, root, freeze, now, cache)
                output["controls"]["frozen_60_40"] = c
                for intensity, model in zip(PARAMETERS["shrinkage"], MODEL_IDS[6:]):
                    prediction = probability_only((1-intensity)*legacy_p+intensity*.5,
                                                  kind="neutral_shrinkage", push=c["q_push"])
                    output["models"][model] = {"status": "forecast", **prediction,
                        "parameters": {"intensity": intensity, "baseline": .5},
                        "untrained_sensitivity": True}
            except (ValueError, KeyError, TypeError, OSError) as exc:
                legacy_p = None
                output["control_status"]["frozen_60_40"] = str(exc)
                for model in (MODEL_IDS[5], *MODEL_IDS[6:]):
                    output["models"][model] = unavailable("original_60_40_control_unavailable:"+str(exc))
            market = no_vig_over(quote)
            if market is None:
                output["control_status"]["market_only"] = "original_coherent_two_sided_odds_unavailable"
                output["models"][MODEL_IDS[5]] = unavailable("market_not_comparable")
            else:
                output["controls"]["market_only"] = probability_only(market, kind="original_no_vig_market")
                output["controls"]["market_only"]["devig_method"] = "proportional_inverse_decimal_odds"
                if legacy_p is not None:
                    output["models"][MODEL_IDS[5]] = {"status": "forecast",
                        **probability_only(fixed_logit(legacy_p, market), kind="fixed_equal_logit"),
                        "parameters": {"model_weight": .5, "market_weight": .5, "clip": PARAMETERS["logit_clip"]},
                        "untrained_sensitivity": True}
            try:
                own, peers, lineage = history_values(item, manifest, root, freeze, trained, cache, target_events)
                laws, reasons, diag = fit_laws(own, peers, stat=raw_q["stat_key"], period=raw_q["period"])
                output["history_lineage"], output["sample_diagnostics"] = lineage, diag
                for model in MODEL_IDS[:5]:
                    output["models"][model] = ({"status": "forecast", **laws[model].record(quote.line)}
                        if model in laws else unavailable(reasons.get(model, "not_applicable")))
            except (ValueError, KeyError, TypeError, OSError) as exc:
                for model in MODEL_IDS[:5]:
                    output["models"][model] = unavailable(str(exc))
        except (ValueError, KeyError, TypeError, OSError) as exc:
            output["eligibility_reason"] = str(exc)
            output["models"] = {m: unavailable(str(exc)) for m in MODEL_IDS}
        # Count actual distinct predictions within each exact contract, not labels.
        signatures = {}
        for model, pred in output["models"].items():
            if pred["status"] == "forecast":
                pred["forecast_id"] = canonical_hash({"manifest": manifest_sha256, "quote": raw_q, "model": model, "forecast_at": now.isoformat(), "code_commit": code_commit, "parameters": PARAMETERS})
                signature = tuple(round(pred.get(k), 14) if pred.get(k) is not None else None
                                  for k in ("q_over", "q_under", "q_push", "p_over_given_no_push", "mean", "variance"))
                if signature in signatures:
                    pred["identical_prediction_to"] = signatures[signature]
                else:
                    signatures[signature] = model
            counts[model+":"+pred["status"]] += 1
        counts["contracts_with_any_forecast"] += int(bool(signatures))
        counts["contracts_fully_unavailable"] += int(not signatures)
        counts["contracts_with_distribution"] += int(any(p["status"] == "forecast" for m,p in output["models"].items() if m in MODEL_IDS[:5]))
        output["distinct_prediction_count"] = len(signatures)
        counts["contracts:"+output["eligibility"]] += 1
    return {"schema": VERSION, "experiment_id": "NFL-WS2-MARGINAL-20261115-v1",
            "status": "UNCERTIFIED_SHADOW" if rows else "blocked_empty_ws1_universe",
            "target_date": TARGET, "forecast_at": now.isoformat(),
            "run_id": canonical_hash({"manifest": manifest_sha256, "forecast_at": now.isoformat(), "code_commit": code_commit}),
            "runtime": {"python": sys.version.split()[0], "scipy": scipy.__version__, "inference": "deterministic_analytic_no_sampling"},
            "input_freeze_at": manifest["input_freeze_at"],
            "model_training_cutoff_at": manifest["model_training_cutoff_at"],
            "source_code_sha256": {name: sha((Path(__file__).resolve().parents[1]/name).read_bytes()) for name in ("scripts/nfl_ws2_shadow.py", "v2/nfl_marginal_shadow.py")},
            "source_manifest_id": manifest.get("manifest_id"), "source_manifest_sha256": manifest_sha256,
            "source_receipts": manifest["sources"], "code_commit": code_commit,
            "model_sha256": canonical_hash({"version": VERSION, "parameters": PARAMETERS, "code_commit": code_commit, "module_sha256": sha((Path(__file__).resolve().parents[1]/"v2/nfl_marginal_shadow.py").read_bytes())}),
            "parameters": PARAMETERS, "coverage": dict(counts), "input_contracts": len(rows),
            "implemented_candidate_versions": list(MODEL_IDS),
            "successful_versions": sorted({m for r in rows for m,p in r["models"].items() if p["status"] == "forecast"}),
            "distinct_versions_somewhere": sorted({m for r in rows for m,p in r["models"].items() if p["status"] == "forecast" and "identical_prediction_to" not in p}),
            "fitted_calibrator": unavailable("no_independently_certified_chronological_training_receipts_admitted"),
            "certification": "local byte and time checks only; original publisher authenticity and WS1 completeness require independent review",
            "production_modified": False, "forecast_rows": rows}


def freeze_report(report, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical(report)
    with path.open("xb") as stream:
        stream.write(raw)
    return {"path": str(path), "sha256": sha(raw), "bytes": len(raw)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc).isoformat()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[1], text=True).strip()
    if args.manifest is None:
        report = {"schema": VERSION, "target_date": TARGET, "attempt_at": now,
                  "status": "blocked_by_data", "reason": "canonical_workstream1_manifest_not_supplied",
                  "input_contracts": None, "forecast_rows": [], "prospective_forecasts": 0,
                  "coverage": "unknown_without_canonical_universe", "code_commit": commit,
                  "parameters": PARAMETERS, "production_modified": False}
    else:
        raw = args.manifest.read_bytes()
        report = build(json.loads(raw), root=args.manifest.parent, now=now,
                       code_commit=commit, manifest_sha256=sha(raw))
    print(json.dumps(freeze_report(report, args.out), sort_keys=True))


if __name__ == "__main__":
    main()
