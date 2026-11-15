"""Consume immutable WS1 native quotes; never collect prices or reconstruct C1."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from . import shadow as s

SCHEMA = "nfl_20261115_source_control_v1"
CANONICAL_SHA = "5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71"
QUOTE_IDENTITY = ("provider_event_id", "event_id", "event_id_namespace", "player_id",
    "player_id_namespace", "nflverse_player_id", "book", "stat", "period", "line",
    "over_odds", "under_odds", "team", "opponent")
EXACT = ("event_id", "book", "player_id", "stat", "line", "period")


def digest(value):
    return s.sha(json.dumps(value, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False).encode())


MARKETS = {"player_receptions": "receptions", "player_reception_yds": "receiving yards",
    "player_rush_yds": "rushing yards", "player_pass_yds": "passing yards",
    "player_pass_attempts": "pass attempts", "player_pass_completions": "completions",
    "player_rush_attempts": "rush attempts", "player_tackles_assists": "tackles + assists"}


def raw_pairs(payload):
    """Pair within one original market only; never bridge books/markets/periods."""
    index = {}
    for event in payload:
        for book in event.get("bookmakers", []):
            for market in book.get("markets", []):
                if market.get("key") not in MARKETS or market.get("period") not in (None, "full_game"):
                    continue
                groups = {}
                for outcome in market.get("outcomes", []):
                    side = str(outcome.get("name", "")).lower()
                    if side not in ("over", "under") or not s.finite(outcome.get("point")):
                        continue
                    key = (outcome.get("description"), outcome["point"])
                    groups.setdefault(key, {}).setdefault(side, []).append(outcome)
                for (player, line), sides in groups.items():
                    if set(sides) != {"over", "under"} or any(len(v) != 1 for v in sides.values()):
                        continue
                    a, b = sides["over"][0], sides["under"][0]
                    key = (str(event["id"]), book["title"], MARKETS[market["key"]], player, line)
                    index.setdefault(key, []).append({"over_odds": a["price"], "under_odds": b["price"],
                        "event_start": event["commence_time"], "market_period": market.get("period"),
                        "provider_over_player_id": a.get("player_id"),
                        "provider_under_player_id": b.get("player_id"),
                        "event_last_update": event.get("last_update"),
                        "book_last_update": book.get("last_update"),
                        "market_last_update": market.get("last_update"),
                        "over_last_seen_at": a.get("last_seen_at"),
                        "under_last_seen_at": b.get("last_seen_at")})
    return index


def market(row, manifest, receipts, now, pairs=None):
    if row.get("source_validation_failure"):
        raise ValueError(row["source_validation_failure"])
    if row.get("source_certified") is not True:
        raise ValueError("WS1_source_not_certified")
    if any(row.get(k) in (None, "") for k in (*EXACT, "quote_id", "candidate_id")):
        raise ValueError("missing_exact_identity")
    if row.get("sport") != "NFL" or row.get("period") != "full_game":
        raise ValueError("unsupported_sport_or_period")
    if not s.finite(row["line"]):
        raise ValueError("invalid_line")
    start = s.timestamp(row["event_start_at"])
    freeze = s.timestamp(row["input_freeze_at"])
    received = s.timestamp(row["source_received_at"])
    if not received <= freeze <= now < start:
        raise ValueError("started_game" if now >= start else "invalid_source_chronology")
    if freeze != s.timestamp(manifest["input_freeze_at"]):
        raise ValueError("conflicting_source_freeze")
    receipt = receipts.get(row["source_sha256"])
    if not receipt or receipt["archive_path"] != row["source_archive_path"]:
        raise ValueError("quote_source_not_in_manifest")
    if receipt["source_received_at"] != row["source_received_at"]:
        raise ValueError("quote_receipt_time_conflict")
    q = row["original_quote"]
    for key in ("book", "player", "stat", "line", "over_odds", "under_odds", "sport"):
        if q.get(key) != row.get(key):
            raise ValueError("original_quote_identity_conflict_"+key)
    if str(q["event_id"]) != row["provider_event_id"]:
        raise ValueError("provider_event_identity_conflict")
    if s.timestamp(q["event_start"]) != start or row["scheduled_kickoff"] != row["event_start_at"]:
        raise ValueError("quote_kickoff_conflict")
    if set(q["event_teams"]) != {row["team"], row["opponent"]}:
        raise ValueError("quote_team_identity_conflict")
    events = [e for e in manifest["events"] if e["espn_event_id"] == row["event_id"]]
    if len(events) != 1 or not events[0]["schedule_verified"] or s.timestamp(events[0]["scheduled_kickoff"]) != start:
        raise ValueError("schedule_identity_conflict")
    if {events[0]["home"], events[0]["away"]} != set(q["event_teams"]):
        raise ValueError("schedule_team_conflict")
    if row.get("roster_receipt_sha256") not in receipts:
        raise ValueError("missing_roster_receipt")
    ident = {k: row.get(k) for k in QUOTE_IDENTITY}
    quote_id = digest({"identity": ident, "quote_source_sha256": row["source_sha256"]})
    if quote_id != row["quote_id"] or digest({"quote_id": quote_id,
            "event": row["event_id"], "player": row["player_id"]}) != row["candidate_id"]:
        raise ValueError("quote_or_candidate_identity_hash_conflict")
    raw_match = None
    if pairs is not None:
        found = pairs.get((row["provider_event_id"], row["book"], row["stat"], row["player"], row["line"]), [])
        if len(found) != 1:
            raise ValueError("missing_or_duplicate_raw_market_pair")
        raw_match = found[0]
        if any(raw_match[k] != q[k] for k in ("over_odds", "under_odds", "event_start")):
            raise ValueError("raw_market_price_or_event_conflict")
        if raw_match["provider_over_player_id"] != raw_match["provider_under_player_id"]:
            raise ValueError("raw_two_sides_player_conflict")
    odds = [q.get(k) for k in ("over_odds", "under_odds")]
    if not all(s.finite(v) and abs(v) >= 100 for v in odds):
        raise ValueError("invalid_original_prices")
    a, b = map(s.implied, odds)
    return a/(a+b), {"over": a, "under": b}, raw_match


def consume(path, expected_sha, *, source_root, now):
    path, root = Path(path), Path(source_root).resolve()
    raw = path.read_bytes()
    if s.sha(raw) != expected_sha:
        raise ValueError("WS1_manifest_file_hash_mismatch")
    manifest = json.loads(raw)
    canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False).encode()
    if raw != canonical+b"\n" or path.stem != s.sha(canonical):
        raise ValueError("WS1_manifest_canonical_or_content_address_mismatch")
    if manifest.get("schema") != SCHEMA or manifest.get("date") != s.DAY:
        raise ValueError("wrong_WS1_schema_or_date")
    if s.timestamp(manifest["input_freeze_at"]) > s.timestamp(now):
        raise ValueError("future_WS1_freeze")
    verified, receipts = {}, {}
    for name, receipt in manifest["sources"].items():
        source = (root/receipt["archive_path"]).resolve()
        if not source.is_relative_to(root):
            raise ValueError("WS1_source_path_escape")
        if s.sha(source.read_bytes()) != receipt["sha256"]:
            raise ValueError("WS1_original_source_bytes_hash_mismatch")
        verified[name] = receipt["sha256"]
        receipts[receipt["sha256"]] = receipt
    pairs = None
    if "propline" in manifest["sources"]:
        provider = manifest["sources"]["propline"]
        pairs = raw_pairs(json.loads((root/provider["archive_path"]).read_bytes()))
    report = s.build({"input_freeze_at": manifest["input_freeze_at"]}, {}, [], [], now=now)
    originals = manifest["candidates"]
    ids = Counter(r.get("candidate_id") for r in originals)
    quotes = Counter(r.get("quote_id") for r in originals)
    keys = Counter(tuple(r.get(k) for k in EXACT) for r in originals)
    rows, controls = [], Counter()
    for index, original in enumerate(originals):
        for name, block in original.get("frozen_control", {}).items():
            if isinstance(block, dict) and block.get("probability") is not None:
                controls[name] += 1
        reason, probability, implied = None, None, None
        try:
            if ids[original.get("candidate_id")] != 1 or quotes[original.get("quote_id")] != 1 or keys[tuple(original.get(k) for k in EXACT)] != 1:
                raise ValueError("duplicate_or_conflicting_exact_contract")
            probability, implied, raw_match = market(original, manifest, receipts, s.timestamp(now), pairs)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            reason = str(exc)
        for candidate in s.CONFIG:
            result = {"input_index": index, "contract_id": original.get("candidate_id"),
                "quote_id": original.get("quote_id"), "event_id": original.get("event_id"),
                "identity": {k: original.get(k) for k in (*EXACT, "quote_id")},
                "candidate": candidate, "model_id": report["registry"][candidate]["model_id"],
                "input_freeze_at": original.get("input_freeze_at"),
                "WS1_forecast_eligibility_reason": original.get("forecast_eligibility_reason"),
                "status": "abstain", "reason": reason or ("prior_training_gate_blocked" if candidate in ("C5", "C6") else "NO_ORIGINAL_FROZEN_CONTROL")}
            if candidate == "C2" and probability is not None:
                result.update(status="forecast", reason=None, forecast_at=now,
                    event_start_at=original["event_start_at"],
                    conditional_no_push={"over": probability, "under": 1-probability},
                    unconditional=None, push_policy="market_push_unidentified",
                    reference_type="conditional_on_nonpush_sportsbook_reference",
                    raw_quote_timestamps=raw_match, original_prices={k: original[k] for k in ("over_odds", "under_odds")},
                    unnormalized_implied=implied, source_sha256=[original["source_sha256"]],
                    quote_source_sha256=original["source_sha256"],
                    quote_received_at=original["source_received_at"],
                    original_quote_reported_at=original.get("original_quote_reported_at"),
                    quote_timestamp_semantics=original.get("original_quote_reported_time_semantics"),
                    source_publication_at=original.get("source_publication_at"),
                    settlement_semantics=original.get("settlement_semantics"),
                    model_market_gap=None, original_quote=original["original_quote"])
            rows.append(result)
    report.update(forecasts=rows, input_manifest_sha256=expected_sha,
        WS1_canonical_sha256=s.sha(canonical), WS1_schema=SCHEMA,
        original_input_rows=len(originals), original_unique_candidate_ids=len(ids),
        original_WS1_code_sha=manifest.get("code_sha"),
        verified_original_source_sha256=verified,
        original_nonnull_control_counts=dict(controls),
        original_source_rows_sha256=s.sha(s.canonical(originals)),
        status="UNCERTIFIED_SHADOW_MARKET_REFERENCE",
        dependency_graph={"C2": [expected_sha, *sorted(set(verified.values()))],
            "C1": ["NO_ORIGINAL_FROZEN_CONTROL"],
            "C3": ["C1", "C2"], "C4": ["C1"], "C4_sensitivity_050": ["C1"],
            "C4_sensitivity_090": ["C1"], "C7": ["C1", "C2"],
            "C5": ["C1", "verified_chronological_history"],
            "C6": ["C1", "C2", "verified_chronological_history"]})
    report["coverage"] = {name: {"input_contracts": len(originals),
        "forecast_contracts": sum(r["candidate"] == name and r["status"] == "forecast" for r in rows),
        "abstentions": dict(Counter(r["reason"] for r in rows if r["candidate"] == name and r["status"] == "abstain"))} for name in s.CONFIG}
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.manifest_sha256 != CANONICAL_SHA:
        raise ValueError("not_corrected_canonical_handoff")
    if not args.out.resolve().is_relative_to((Path.cwd()/"calibration_models").resolve()):
        raise ValueError("output_must_be_in_owned_calibration_models_directory")
    result = consume(args.manifest, args.manifest_sha256, source_root=args.source_root,
                     now=datetime.now(timezone.utc).isoformat())
    s.finalize_emission(result)
    digest_out = s.write_exclusive(args.out, result)
    print(json.dumps({"output_sha256": digest_out, "coverage": result["coverage"]}, sort_keys=True))


if __name__ == "__main__":
    main()
