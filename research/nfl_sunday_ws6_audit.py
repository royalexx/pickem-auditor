#!/usr/bin/env python3
"""WS6: read-only NFL Sunday provenance, contract, model and settlement auditor.

Consumes Workstream 1's ORIGINAL archived evidence. Does not collect sources,
predict, change production, or retroactively certify self-reported timestamps.
All output directories are create-once; inputs are never changed.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import re

SLATE = "2026-11-15"
LEGACY = ("engine_a", "engine_b", "bayesian_a", "bayesian_b",
          "nuts", "frozen_60_40", "market_no_vig")
EXPECTED_SCHEMA = "nfl_sunday_ws1_original_v1"
VALID_FINAL = {"official_final", "dnp", "void", "unmatched", "source_rejected"}
SHA = re.compile(r"^[a-f0-9]{64}$")
COMMIT = re.compile(r"^[a-f0-9]{40}$")


class IntegrityError(ValueError):
    pass


def fail(code):
    raise IntegrityError(code)


def object_unique(pairs):
    d = {}
    for key, value in pairs:
        if key in d:
            fail("DUPLICATE_JSON_KEY:" + key)
        d[key] = value
    return d


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"),
                      object_pairs_hook=object_unique,
                      parse_constant=lambda v: fail("NONFINITE_JSON:" + v))


def load_jsonl(path):
    result = []
    with Path(path).open(encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if line.strip():
                try:
                    result.append(json.loads(line, object_pairs_hook=object_unique,
                                             parse_constant=lambda v: fail("NONFINITE_JSON:" + v)))
                except (ValueError, TypeError) as e:
                    fail("BAD_JSONL:" + str(path) + ":" + str(n) + ":" + str(e))
    return result


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    indent=2, allow_nan=False) + "\n", encoding="utf-8")


def dump_lines(path, rows):
    with Path(path).open("x", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, ensure_ascii=False,
                               separators=(",", ":"), allow_nan=False) + "\n")


def instant(value, field):
    if not isinstance(value, str) or not value.strip():
        fail("MISSING_CLOCK:" + field)
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.utcoffset() is None:
            fail("NAIVE_CLOCK:" + field)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        fail("INVALID_CLOCK:" + field)


def required(row, keys):
    if not isinstance(row, dict):
        fail("NOT_AN_OBJECT")
    for k in keys:
        if k not in row or row[k] is None or row[k] == "":
            fail("MISSING_FIELD:" + k)


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        fail("BAD_NUMBER:" + name)
    return float(value)


def digest(value, name):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        fail("BAD_SHA256:" + name)


def checked_source(root, rel_path, expected):
    digest(expected, "source")
    if not isinstance(rel_path, str) or not rel_path or rel_path.startswith("/") or "\\" in rel_path or ".." in rel_path.split("/"):
        fail("UNSAFE_SOURCE_PATH")
    base = Path(root).resolve()
    target = (base / rel_path).resolve()
    if not target.is_relative_to(base) or not target.is_file():
        fail("SOURCE_BYTES_UNAVAILABLE:" + rel_path)
    if file_sha(target) != expected:
        fail("SOURCE_HASH_MISMATCH")
    return rel_path


def key_of(row):
    required(row, ("event_id", "player_id", "stat_key", "period", "line",
                   "book", "product_type", "quote_id", "contract_id"))
    return (str(row["event_id"]), str(row["player_id"]), str(row["stat_key"]),
            str(row["period"]), number(row["line"], "line"),
            str(row["book"]), str(row["product_type"]), str(row["quote_id"]),
            str(row["contract_id"]))


def probability(row):
    a, b, p = [number(row.get(k), k) for k in ("q_over", "q_under", "q_push")]
    if any(x < 0 or x > 1 for x in (a, b, p)) or abs(math.fsum((a, b, p)) - 1) > 1e-10:
        fail("PROBABILITY_INTEGRITY")
    distribution = row.get("distribution")
    if distribution is not None and distribution.get("kind") == "discrete":
        masses = distribution.get("masses")
        if not isinstance(masses, list) or not masses:
            fail("INVALID_DISCRETE_DISTRIBUTION")
        xseen, mass = set(), []
        for pair in masses:
            if not isinstance(pair, list) or len(pair) != 2:
                fail("INVALID_MASS_PAIR")
            x, m = number(pair[0], "support"), number(pair[1], "mass")
            if x in xseen or m < 0 or m > 1:
                fail("BAD_MASS_SUPPORT")
            xseen.add(x)
            mass.append((x, m))
        if abs(math.fsum(m for _, m in mass) - 1) > 1e-10:
            fail("MASS_NOT_NORMALIZED")
        line = number(row["line"], "line")
        check = (sum(m for x, m in mass if x > line),
                 sum(m for x, m in mass if x < line),
                 sum(m for x, m in mass if x == line))
        if any(abs(x - y) > 1e-8 for x, y in zip(check, (a, b, p))):
            fail("DISTRIBUTION_THRESHOLD_MISMATCH")
    return a, b, p


def verify_quote(q, root, events):
    required(q, ("quote_kind", "accepted", "event_start_at", "source_available_at",
                 "captured_at", "quote_at", "source_archive_path", "source_sha256",
                 "settlement_policy"))
    key_of(q)
    if q["quote_kind"] != "real":
        fail("NON_ORIGINAL_OFFER")
    if q["settlement_policy"] != "strict_gt_lt_equal_push":
        fail("SETTLEMENT_POLICY_MISMATCH")
    if q["event_id"] not in events:
        fail("NOT_IN_FROZEN_SCHEDULE")
    start = instant(q["event_start_at"], "event_start_at")
    if start != instant(events[q["event_id"]]["start_at"], "schedule_start_at"):
        fail("EVENT_START_IDENTITY_MISMATCH")
    if not (instant(q["source_available_at"], "source_available_at")
            <= instant(q["captured_at"], "captured_at")
            < start):
        fail("SOURCE_NOT_PROVEN_PREGAME")
    if instant(q["quote_at"], "quote_at") > instant(q["captured_at"], "captured_at"):
        fail("QUOTE_TIME_AFTER_CAPTURE")
    checked_source(root, q["source_archive_path"], q["source_sha256"])
    if q["accepted"] is not True:
        fail("QUOTE_REJECTED:" + str(q.get("reject_reason") or "unspecified"))
    if q.get("player_eligible_pregame") is not True:
        fail("PLAYER_ELIGIBILITY_UNVERIFIED")
    if q.get("source_kind") not in ("provider_publication", "archive_possession"):
        fail("SOURCE_KIND_UNVERIFIED")
    if q["source_kind"] == "archive_possession" and q["source_available_at"] != q["captured_at"]:
        fail("POSSESSION_CLOCK_MISMATCH")


def verify_forecast(f, q, root, source_hash):
    required(f, ("model_id", "model_version", "model_code_commit", "model_artifact_sha256",
                 "input_manifest_sha256", "forecast_at", "input_freeze_at",
                 "model_training_cutoff_at", "forecast_attested_at"))
    if key_of(f) != key_of(q):
        fail("FORECAST_CONTRACT_IDENTITY_MISMATCH")
    if f["input_manifest_sha256"] != source_hash:
        fail("INPUT_MANIFEST_HASH_MISMATCH")
    if not COMMIT.fullmatch(str(f["model_code_commit"])):
        fail("MODEL_COMMIT_UNVERIFIED")
    digest(f["model_artifact_sha256"], "model_artifact")
    src, freeze, train = (instant(f["forecast_at"], "forecast_at"),
                          instant(f["input_freeze_at"], "input_freeze_at"),
                          instant(f["model_training_cutoff_at"], "model_training_cutoff_at"))
    att = instant(f["forecast_attested_at"], "forecast_attested_at")
    if not (train <= freeze <= src <= att < instant(q["event_start_at"], "event_start_at")):
        fail("FORECAST_NOT_PROVEN_PREGAME")
    if (instant(q["captured_at"], "captured_at") > freeze
            or instant(q["quote_at"], "quote_at") > src):
        fail("FORECAST_USES_UNFROZEN_SOURCE")
    probability(f)
    if f.get("selected") is True and f.get("selected_side") not in ("over", "under"):
        fail("SELECTED_SIDE_UNDEFINED")
    # A hash and self-stated timestamp are NOT an external trusted time attestation.
    # A separate verification of original capture/transport is required to certify.
    return "STRUCTURALLY_VALID_ATTESTATION_PENDING"


def crps_discrete(distribution, observed):
    if not isinstance(distribution, dict) or distribution.get("kind") != "discrete":
        return None
    arr = sorted((number(x, "support"), number(p, "mass"))
                 for x, p in distribution["masses"])
    first = math.fsum(p * abs(x - observed) for x, p in arr)
    cum, weighted, pair = 0.0, 0.0, 0.0
    for x, p in arr:
        pair += p * (x * cum - weighted)
        cum += p
        weighted += p * x
    return max(0.0, first - pair)


def group_score(rows):
    if not rows:
        return {"count": 0}
    n = len(rows)
    return {
        "count": n,
        "multiclass_brier_half": sum(r["brier3"] for r in rows) / n,
        "multiclass_logloss": sum(r["logloss3"] for r in rows) / n,
        "binary_nonpush_count": sum(r["binary_brier"] is not None for r in rows),
        "binary_nonpush_brier": (sum(r["binary_brier"] for r in rows if r["binary_brier"] is not None)
                                 / max(1, sum(r["binary_brier"] is not None for r in rows))),
        "binary_nonpush_logloss": (sum(r["binary_logloss"] for r in rows if r["binary_logloss"] is not None)
                                  / max(1, sum(r["binary_logloss"] is not None for r in rows))),
        "predicted_over_mean": sum(r["q_over"] for r in rows) / n,
        "realized_over_rate": sum(r["outcome"] == "over" for r in rows) / n,
        "selected_over_fraction": (sum(r["selected"] and r["selected_side"] == "over" for r in rows)
                                   / max(1, sum(r["selected"] for r in rows))),
        "selected_count": sum(r["selected"] for r in rows),
        "directional_accuracy_nonpush": (sum(r["predicted_side"] == r["outcome"] for r in rows
                                            if r["outcome"] != "push")
                                          / max(1, sum(r["outcome"] != "push" for r in rows))),
        "crps_supported_count": sum(r["crps"] is not None for r in rows),
        "crps_mean": (sum(r["crps"] for r in rows if r["crps"] is not None)
                      / max(1, sum(r["crps"] is not None for r in rows))),
    }


def bootstrap_paired(all_rows, challenger, control, seed=15026, repetitions=2000):
    by_key = defaultdict(dict)
    for r in all_rows:
        by_key[r["contract_id"]][r["model_id"]] = r
    pairs = [(d[challenger], d[control]) for d in by_key.values()
             if challenger in d and control in d]
    if not pairs:
        return {"paired_n": 0, "status": "UNAVAILABLE"}
    clusters = defaultdict(list)
    for a, b in pairs:
        if a["event_id"] != b["event_id"] or a["outcome"] != b["outcome"]:
            fail("PAIRED_CONTRACT_OR_OUTCOME_MISMATCH")
        clusters[a["event_id"]].append(a["brier3"] - b["brier3"])
    names = sorted(clusters)
    diff = sum(sum(v) for v in clusters.values()) / sum(len(v) for v in clusters.values())
    if len(names) < 3:
        return {"paired_n": len(pairs), "game_clusters": len(names),
                "mean_brier_difference": diff, "status": "TOO_FEW_GAME_CLUSTERS"}
    rng = random.Random(seed)
    vals = []
    for _ in range(repetitions):
        chosen = [clusters[names[rng.randrange(len(names))]] for _ in names]
        vals.append(sum(sum(c) for c in chosen) / sum(len(c) for c in chosen))
    vals.sort()
    return {"paired_n": len(pairs), "game_clusters": len(names),
            "mean_brier_difference": diff,
            "game_cluster_bootstrap_95": [vals[int(0.025 * repetitions)],
                                          vals[min(repetitions - 1, int(0.975 * repetitions))]],
            "status": "DESCRIPTIVE_ONE_DATE_NOT_PROMOTION_GRADE"}


def freeze(args):
    root, out = Path(args.root), Path(args.output)
    if out.exists():
        fail("OUTPUT_ALREADY_EXISTS")
    manifest_path, quote_path = root / args.manifest, root / args.quotes
    manifest, quotes = load_json(manifest_path), load_jsonl(quote_path)
    required(manifest, ("schema", "slate_date", "schedule_complete", "events",
                        "expected_contract_count", "quotes_sha256"))
    if manifest["schema"] != EXPECTED_SCHEMA or manifest["slate_date"] != SLATE:
        fail("WRONG_SLATE_OR_SOURCE_SCHEMA")
    if file_sha(quote_path) != manifest["quotes_sha256"]:
        fail("QUOTE_LEDGER_HASH_MISMATCH")
    if manifest["schedule_complete"] is not True or not manifest["events"]:
        fail("FULL_SCHEDULE_NOT_ATTESTED")
    events = {}
    for e in manifest["events"]:
        required(e, ("event_id", "start_at", "home_id", "away_id"))
        instant(e["start_at"], "event_start_at")
        if e["event_id"] in events or e["home_id"] == e["away_id"]:
            fail("DUPLICATE_OR_BAD_EVENT")
        events[e["event_id"]] = e
    original = {}
    rejects, seen_id = [], set()
    for i, q in enumerate(quotes):
        qid = q.get("quote_id")
        if not qid or qid in seen_id:
            rejects.append({"row": i, "quote_id": qid, "reason": "MISSING_OR_DUPLICATE_QUOTE_ID"})
            continue
        seen_id.add(qid)
        try:
            verify_quote(q, root, events)
            key = key_of(q)
            if key in (key_of(v) for v in original.values()):
                fail("DUPLICATE_ORIGINAL_CONTRACT")
            if q["contract_id"] in original:
                fail("CONTRACT_ID_REUSED")
            original[q["contract_id"]] = q
        except (IntegrityError, ValueError, TypeError, KeyError) as ex:
            rejects.append({"row": i, "quote_id": qid, "reason": str(ex)})
    count_ok = len(original) == manifest["expected_contract_count"]
    source_hash = file_sha(manifest_path)
    forecasts = {}
    model_counts = Counter()
    model_versions = defaultdict(set)
    failures = []
    files = {}
    for path in args.forecasts:
        p = root / path
        files[path] = file_sha(p)
        for i, f in enumerate(load_jsonl(p)):
            mid, cid = f.get("model_id"), f.get("contract_id")
            model_counts[str(mid)] += 1
            model_versions[str(mid)].add(str(f.get("model_version")))
            if cid not in original:
                failures.append({"file": path, "row": i, "model_id": mid,
                                 "contract_id": cid, "reason": "NOT_IN_ORIGINAL_SOURCE_UNIVERSE"})
                continue
            try:
                verify_forecast(f, original[cid], root, source_hash)
                k = (cid, mid)
                if k in forecasts:
                    fail("DUPLICATE_MODEL_FORECAST")
                forecasts[k] = f
            except (IntegrityError, ValueError, TypeError, KeyError) as ex:
                failures.append({"file": path, "row": i, "model_id": mid,
                                 "contract_id": cid, "reason": str(ex)})
    configured = set(LEGACY) | set(manifest.get("expected_models", [])) | set(model_counts)
    ledger = []
    for cid, q in sorted(original.items()):
        models = {}
        for mid in sorted(configured):
            f = forecasts.get((cid, mid))
            if f is not None:
                models[mid] = {
                    "model_version": f["model_version"],
                    "model_code_commit": f["model_code_commit"],
                    "model_artifact_sha256": f["model_artifact_sha256"],
                    "forecast_at": f["forecast_at"], "input_freeze_at": f["input_freeze_at"],
                    "model_training_cutoff_at": f["model_training_cutoff_at"],
                    "forecast_attested_at": f["forecast_attested_at"],
                    "q_over": f["q_over"], "q_under": f["q_under"], "q_push": f["q_push"],
                    "selected": f.get("selected", False),
                    "selected_side": f.get("selected_side"),
                    "distribution": f.get("distribution"),
                    "status": "STRUCTURALLY_VALID_ATTESTATION_PENDING",
                }
            else:
                models[mid] = None
        market = None
        if (q.get("product_type") == "sportsbook_two_sided" and
                q.get("over_decimal_odds") is not None and q.get("under_decimal_odds") is not None):
            o, u = (number(q["over_decimal_odds"], "over_odds"),
                    number(q["under_decimal_odds"], "under_odds"))
            if o > 1 and u > 1:
                market = (1 / o) / ((1 / o) + (1 / u))
        ledger.append({"contract_id": cid, "quote": q, "models": models,
                       "market_no_vig_over_conditional_nonpush": market,
                       "research_only": True, "tier_eligible": False})
    out.mkdir(parents=True, exist_ok=False)
    dump_lines(out / "comparison_ledger.jsonl", ledger)
    dump_lines(out / "quote_rejections.jsonl", rejects)
    dump_lines(out / "forecast_rejections.jsonl", failures)
    register = {mid: {"rows_submitted": model_counts[mid], "versions": sorted(model_versions[mid]),
                      "valid_rows": sum((cid, mid) in forecasts for cid in original),
                      "missing_or_invalid": len(original) - sum((cid, mid) in forecasts for cid in original),
                      "classification": "PROSPECTIVE_SHADOW_UNCERTIFIED"} for mid in sorted(configured)}
    dump(out / "model_registry.json", register)
    report = {"slate": SLATE, "source_manifest_sha256": source_hash,
              "source_quote_file_sha256": file_sha(quote_path),
              "forecast_input_sha256": files, "event_count": len(events),
              "quotes_total": len(quotes), "accepted_original_contracts": len(original),
              "quote_rejections": len(rejects), "expected_contract_count": manifest["expected_contract_count"],
              "full_universe_count_matches_manifest": count_ok,
              "forecast_rows_submitted": sum(model_counts.values()),
              "forecast_rows_valid_structure": len(forecasts),
              "forecast_rejections": len(failures),
              "uncertified_reason": "External authenticated pregame possession and provider time not independently verified",
              "comparison_status": "UNVERIFIED_SHADOW_ONLY",
              "no_release": True, "no_tier": True,
              "model_registry": "model_registry.json", "source_owner": "Workstream 1"}
    dump(out / "integrity_report.json", report)
    dump(out / "freeze_index.json", {
        "original_manifest_sha256": source_hash,
        "comparison_ledger_sha256": file_sha(out / "comparison_ledger.jsonl"),
        "model_registry_sha256": file_sha(out / "model_registry.json"),
        "integrity_report_sha256": file_sha(out / "integrity_report.json"),
        "classification": "SHADOW_ONLY_NOT_EXTERNALLY_CERTIFIED"})
    print(json.dumps(report, sort_keys=True))
    return 0 if count_ok and not failures and not rejects else 2


def score(args):
    root, out, frozen = Path(args.root), Path(args.output), Path(args.frozen)
    if out.exists():
        fail("OUTPUT_ALREADY_EXISTS")
    idx = load_json(frozen / "freeze_index.json")
    ledger_file = frozen / "comparison_ledger.jsonl"
    if file_sha(ledger_file) != idx["comparison_ledger_sha256"]:
        fail("FROZEN_COMPARISON_HASH_CHANGED")
    ledger = load_jsonl(ledger_file)
    outcomes_file = root / args.outcomes
    outcome_sha = file_sha(outcomes_file)
    outcomes, invalid = {}, []
    for i, o in enumerate(load_jsonl(outcomes_file)):
        try:
            required(o, ("event_id", "player_id", "stat_key", "period", "status",
                         "official_provider", "official_source_path", "official_source_sha256",
                         "official_retrieved_at", "event_start_at"))
            if o["status"] not in VALID_FINAL:
                fail("OUTCOME_NOT_FINAL")
            if o["official_provider"] not in ("nfl_gsis", "nfl_official"):
                fail("OUTCOME_PROVIDER_NOT_OFFICIAL")
            if instant(o["official_retrieved_at"], "official_retrieved_at") <= instant(o["event_start_at"], "event_start_at"):
                fail("RESULT_NOT_COLLECTED_AFTER_KICKOFF")
            if o["status"] == "official_final":
                required(o, ("actual_stat", "official_final_at"))
                number(o["actual_stat"], "actual_stat")
                if instant(o["official_final_at"], "official_final_at") <= instant(o["event_start_at"], "event_start_at"):
                    fail("OFFICIAL_FINAL_BEFORE_EVENT")
            checked_source(root, o["official_source_path"], o["official_source_sha256"])
            k = (o["event_id"], o["player_id"], o["stat_key"], o["period"])
            if k in outcomes:
                fail("DUPLICATE_OFFICIAL_OUTCOME")
            outcomes[k] = o
        except (IntegrityError, ValueError, TypeError, KeyError) as ex:
            invalid.append({"row": i, "reason": str(ex)})
    settled, metric_rows = [], []
    for qrow in ledger:
        q = qrow["quote"]
        key = (q["event_id"], q["player_id"], q["stat_key"], q["period"])
        o = outcomes.get(key)
        if o is None:
            status, actual = "missing_official_outcome", None
        elif instant(o["event_start_at"], "official_event_start") != instant(q["event_start_at"], "quote_event_start"):
            status, actual = "outcome_event_identity_rejected", None
        elif o["status"] != "official_final":
            status, actual = o["status"], None
        else:
            actual = float(o["actual_stat"])
            line = number(q["line"], "line")
            status = "over" if actual > line else "under" if actual < line else "push"
        settled.append({"contract_id": q["contract_id"], "event_id": q["event_id"],
                        "settlement": status, "actual_stat": actual,
                        "official_source_sha256": o.get("official_source_sha256") if o else None})
        if status not in ("over", "under", "push"):
            continue
        for mid, m in qrow["models"].items():
            if not m:
                continue
            ps = (m["q_over"], m["q_under"], m["q_push"])
            outcome_idx = {"over": 0, "under": 1, "push": 2}[status]
            y = tuple(float(i == outcome_idx) for i in range(3))
            brier3 = 0.5 * sum((p - t) ** 2 for p, t in zip(ps, y))
            loss3 = -math.log(max(1e-15, ps[outcome_idx]))
            mass = ps[0] + ps[1]
            binary_brier = binary_logloss = None
            if status != "push" and mass > 0:
                pp = ps[0] / mass
                yy = float(status == "over")
                binary_brier = (pp - yy) ** 2
                binary_logloss = -(yy * math.log(max(pp, 1e-15))
                                   + (1 - yy) * math.log(max(1 - pp, 1e-15)))
            metric_rows.append({
                "contract_id": q["contract_id"], "event_id": q["event_id"],
                "model_id": mid, "stat_key": q["stat_key"],
                "date": q["event_start_at"][:10],
                "outcome": status, "q_over": ps[0], "q_under": ps[1], "q_push": ps[2],
                "brier3": brier3, "logloss3": loss3,
                "binary_brier": binary_brier, "binary_logloss": binary_logloss,
                "crps": crps_discrete(m.get("distribution"), actual),
                "predicted_side": "over" if ps[0] >= ps[1] else "under",
                "selected": m.get("selected") is True,
                "selected_side": m.get("selected_side")})
    models = defaultdict(list)
    bymarket = defaultdict(list)
    selection = defaultdict(list)
    for r in metric_rows:
        models[r["model_id"]].append(r)
        bymarket[(r["model_id"], r["stat_key"])].append(r)
        selection[(r["model_id"], "selected" if r["selected"] else "not_selected")].append(r)
    paired = {}
    for challenger in models:
        if challenger != "frozen_60_40":
            paired[challenger + "__vs_frozen_60_40"] = bootstrap_paired(metric_rows, challenger, "frozen_60_40")
        if challenger != "market_no_vig":
            paired[challenger + "__vs_market_no_vig"] = bootstrap_paired(metric_rows, challenger, "market_no_vig")
    dates = sorted(set(r["date"] for r in metric_rows))
    out.mkdir(parents=True, exist_ok=False)
    dump_lines(out / "settlement_ledger.jsonl", settled)
    dump_lines(out / "invalid_official_outcomes.jsonl", invalid)
    report = {"slate": SLATE, "frozen_comparison_sha256": idx["comparison_ledger_sha256"],
              "official_input_sha256": outcome_sha, "original_contracts": len(ledger),
              "settled_over_under_push": dict(Counter(x["settlement"] for x in settled)),
              "invalid_official_rows": len(invalid), "model_metrics": {k: group_score(v) for k, v in models.items()},
              "per_market": {a + ":" + b: group_score(v) for (a, b), v in bymarket.items()},
              "selected_vs_not": {a + ":" + b: group_score(v) for (a, b), v in selection.items()},
              "matched_paired_game_clusters": paired, "evaluated_dates": dates,
              "date_cluster_inference": "UNAVAILABLE_SINGLE_DATE" if len(dates) < 3 else "REQUIRES_PRECOMMITTED_DATE_BOOTSTRAP",
              "multiplicity": {"observed_model_comparisons": len(paired),
                               "promotion_inference": "PROHIBITED"},
              "source_certification": "UNVERIFIED_PREGAME_ATTESTATION",
              "official_settlement_certification": "REQUIRES_INDEPENDENT_PROVIDER_REVIEW",
              "research_only": True, "tier_release": False,
              "notes": "Push excluded only from binary nonpush metrics, retained in three-class score. Half-Brier uses 0.5 sum_k(p_k-y_k)^2. One Sunday cannot support promotion."}
    dump(out / "score_report.json", report)
    dump(out / "score_index.json", {"frozen_comparison_sha256": idx["comparison_ledger_sha256"],
                                    "official_input_sha256": outcome_sha,
                                    "settlement_ledger_sha256": file_sha(out / "settlement_ledger.jsonl"),
                                    "score_report_sha256": file_sha(out / "score_report.json")})
    print(json.dumps({"settlement_counts": report["settled_over_under_push"],
                      "model_counts": {k: len(v) for k, v in models.items()},
                      "invalid_official_rows": len(invalid), "no_promotion": True}, sort_keys=True))
    return 0 if not invalid else 2


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("freeze", help="Read frozen WS1 source/WS2-5 outputs, never original outcomes")
    f.add_argument("--root", required=True)
    f.add_argument("--manifest", required=True)
    f.add_argument("--quotes", required=True)
    f.add_argument("--forecasts", nargs="*", default=[])
    f.add_argument("--output", required=True)
    s = sub.add_parser("score", help="Later official-only settlement of already frozen comparison")
    s.add_argument("--root", required=True)
    s.add_argument("--frozen", required=True)
    s.add_argument("--outcomes", required=True)
    s.add_argument("--output", required=True)
    args = p.parse_args(argv)
    try:
        return freeze(args) if args.cmd == "freeze" else score(args)
    except (OSError, IntegrityError, TypeError, KeyError, ValueError) as e:
        print(json.dumps({"status": "FAIL_CLOSED", "reason": str(e), "no_release": True}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
