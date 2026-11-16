"""Read-only NFL WS6 + NBA Phase 8C prospective research morning audit.

NEVER regenerates forecasts. Never writes into any input directory, original
first-capture files, WS6 ledgers, production history or other automations.
Distinct postgame outcomes are retrieved only after source-confirmed FINAL.
"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
import argparse
import gzip
import hashlib
import json
import math
import os
import sys

from research.nba_phase7.pilot import registered_slots
from research.nba_phase7.settlement import settle_original
from v2.nba_ws1.store import Receipt, instant

TZ = ZoneInfo("America/Toronto")
WS6_REL = ("reports/nfl_20261115_ws6_real_comparison/"
           "canonical_s2_c2_j1_j2_original_forecast_comparison_v1/"
           "comparison_ledger_1845.jsonl")
WS6_SHA = "242c4404a6b1505844528ee7096f86060f459df6517f0420f618deef8888fbba"
WS1_SHA = "5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71"
NBA_ROOT = "reports/nba_phase7_pilot"
OUTPUT_ROOT = "reports/v25_morning_research_validation"
ESPN_NFL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event="
ESPN_NBA = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event="
EXPECTED_NFL_ROWS = 1845
EXCLUDED_FOR_SCORE = {"tackles + assists"}  # requires original-contract stat-definition parity review
SUPPORTED_NFL_STATS = {
    "completions": "passing",
    "pass attempts": "passing",
    "passing yards": "passing",
    "receptions": "receiving",
    "receiving yards": "receiving",
    "rush attempts": "rushing",
    "rushing yards": "rushing",
    "tackles + assists": "defensive",
}


def h(b):
    return hashlib.sha256(b).hexdigest()


def utcnow():
    return datetime.now(timezone.utc)


def make_once(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf8") as fh:
        json.dump(data, fh, sort_keys=True, indent=2, allow_nan=False)
        fh.write("\n")


def original_input(path, expected):
    raw = Path(path).read_bytes()
    if h(raw) != expected:
        raise ValueError("ORIGINAL_LEDGER_SHA256_CHANGED")
    return raw


def fetch_final(url, event_id, kickoff_at, folder, *, fetch=None):
    """Verify ESPN's event identity/status and archive the actual outcome bytes."""
    try:
        if utcnow() <= instant(kickoff_at):
            return {"status": "NOT_YET_STARTED"}
    except (ValueError, TypeError):
        return {"status": "MISSING_OR_INVALID_ORIGINAL_KICKOFF",
                "event_id": str(event_id)}
    fetch = fetch or _fetch
    try:
        raw = fetch(url)
        source_hash = h(raw)
        data = json.loads(raw)
        header = (data.get("header") or {}).get("competitions") or []
        if len(header) != 1:
            raise ValueError("OUTCOME_COMPETITION_CARDINALITY")
        comp = header[0]
        if str(comp.get("id")) != str(event_id):
            raise ValueError("OUTCOME_EVENT_ID_MISMATCH")
        if instant(comp.get("date")) != instant(kickoff_at):
            raise ValueError("OUTCOME_SCHEDULE_CHANGED")
        state = (comp.get("status") or {}).get("type") or {}
        if state.get("completed") is not True or state.get("name") != "STATUS_FINAL":
            return {"status": "NOT_FINAL", "event_id": str(event_id)}
        path = folder / (str(event_id) + "_" + source_hash + ".json.gz")
        with path.open("xb") as f:
            f.write(gzip.compress(raw, mtime=0))
        return {"status": "FINAL", "data": data,
                "source": {"provider": "ESPN", "url": url,
                           "retrieved_at": utcnow().isoformat(),
                           "raw_sha256": source_hash, "archive": str(path)}}
    except Exception as exc:
        return {"status": "SOURCE_BLOCKED",
                "error": type(exc).__name__ + ":" + str(exc),
                "event_id": str(event_id)}


def _fetch(url):
    req = Request(url, headers={"User-Agent": "pickem-v25-original-forward-scoring/1"})
    with urlopen(req, timeout=22) as resp:
        if resp.status != 200:
            raise ValueError("ESPN_HTTP_NOT_200")
        return resp.read(8 * 1024 * 1024 + 1)


def nfl_box_values(document):
    """Only explicit player-category statistics. No invented DNP or zero."""
    comp = document["header"]["competitions"][0]
    teams = {str(c["team"]["id"]): c["team"].get("abbreviation") for c in comp["competitors"]}
    rows = {}
    for team in (document.get("boxscore") or {}).get("players") or []:
        tid = str(team.get("team", {}).get("id"))
        if tid not in teams:
            raise ValueError("OUTCOME_BOX_TEAM_ID_UNMATCHED")
        for category in team.get("statistics") or []:
            name = category.get("name")
            labels = category.get("labels") or []
            if name not in ("passing", "rushing", "receiving", "defensive"):
                continue
            for appearance in category.get("athletes") or []:
                aid = str((appearance.get("athlete") or {}).get("id", ""))
                data = appearance.get("stats") or []
                if len(data) != len(labels) or not aid:
                    continue
                pair = (aid, name)
                if pair in rows:
                    raise ValueError("DUPLICATE_PLAYER_STAT_SOURCE")
                rows[pair] = {"labels": dict(zip(labels, data)), "team_abbreviation": teams[tid],
                              "team_id": tid}
    return rows, set(teams.values())


def _safe_num(x):
    if isinstance(x, bool):
        raise ValueError("BOOLEAN_OUTCOME")
    v = float(x)
    if not math.isfinite(v):
        raise ValueError("NONFINITE_OUTCOME")
    return v


def nfl_stat_observation(stats, player_id, stat, row_team=None):
    category = SUPPORTED_NFL_STATS.get(stat)
    if category is None:
        return None, "UNSUPPORTED_MARKET", None
    row = stats.get((str(player_id), category))
    if row is None:
        return None, "CATEGORY_OUTCOME_UNLISTED_UNKNOWN_NOT_ZERO", None
    if row_team and row["team_abbreviation"] != row_team:
        return None, "OUTCOME_TEAM_MISMATCH", None
    labels = row["labels"]
    try:
        if category == "passing":
            if stat in ("completions", "pass attempts"):
                comps, att = labels["C/ATT"].split("/")
                return _safe_num(comps if stat == "completions" else att), "OBSERVED", row["team_abbreviation"]
            return _safe_num(labels["YDS"]), "OBSERVED", row["team_abbreviation"]
        if category == "rushing":
            return _safe_num(labels["CAR" if stat == "rush attempts" else "YDS"]), "OBSERVED", row["team_abbreviation"]
        if category == "receiving":
            return _safe_num(labels["REC" if stat == "receptions" else "YDS"]), "OBSERVED", row["team_abbreviation"]
        if category == "defensive":
            return _safe_num(labels["TOT"]), "ESPN_TOTAL_TACKLES_PARITY_UNVERIFIED", row["team_abbreviation"]
    except (KeyError, ValueError, TypeError, IndexError):
        return None, "BOX_SOURCE_STAT_PARSE_FAILED", None
    return None, "UNRECOGNIZED_STAT", None


def discrete_crps(masses, observed):
    """Exact discrete CRPS. No simulated forecast draws or new model fitting."""
    support = []
    for val, probability in masses:
        x = _safe_num(val)
        p = _safe_num(probability)
        if p < 0 or p > 1:
            raise ValueError("PMF_NEGATIVE_OR_GT_ONE")
        support.append((x, p))
    if not support or abs(sum(p for _, p in support) - 1) > 0.00001:
        raise ValueError("PMF_MASS_NONUNIT")
    # E|X-y| - E|X-X'|/2. O(k log k) exact weighted pair sum.
    first = sum(p * abs(x - observed) for x, p in support)
    cumulative_mass = 0.0
    cumulative_weighted = 0.0
    second_half = 0.0
    for x, p in sorted(support):
        second_half += p * (x * cumulative_mass - cumulative_weighted)
        cumulative_mass += p
        cumulative_weighted += x * p
    return max(0.0, first - second_half)


def score_probability(p, outcome):
    p = _safe_num(p)
    if not 0 <= p <= 1:
        raise ValueError("NONPROBABILITY")
    clipped = min(1 - 1e-12, max(1e-12, p))
    return {"brier": (p - outcome) ** 2,
            "logloss": -(outcome * math.log(clipped) + (1 - outcome) * math.log(1 - clipped))}


def _model_distributions(row, outcome, line):
    result = {}
    for key, name in [("S2_original_source_model", "S2"),
                      ("J1_original_joint_game_model", "J1"),
                      ("J2_original_joint_game_model", "J2"),
                      ("C2_original_market_reference", "C2")]:
        model = row.get(key)
        if not model:
            continue
        try:
            forecast_at = (model.get("forecast_created_at") or model.get("model_forecast_created_at")
                           or model.get("forecast_at"))
            if forecast_at is None or instant(forecast_at) >= instant(row["event_start_at"]):
                raise ValueError("MODEL_FORECAST_NOT_PREGAME")
            if model.get("q_push") is not None and model.get("q_over") is not None and model.get("q_under") is not None:
                if abs(sum(_safe_num(model[x]) for x in ("q_over", "q_under", "q_push")) - 1) > 1e-5:
                    raise ValueError("MODEL_3WAY_MASS")
            p = model.get("p_over_given_no_push")
            if p is None:
                raise ValueError("CONDITIONAL_NONPUSH_PROBABILITY_MISSING")
            metrics = {}
            if outcome != line:
                metrics.update(score_probability(p, int(outcome > line)))
            if name == "S2":
                metrics["crps"] = discrete_crps(model["distribution_support_mass"], outcome)
            elif name in ("J1", "J2"):
                metrics["crps"] = discrete_crps([(float(x), val) for x, val in model["pmf"].items()], outcome)
            result[name] = {"status": "SCORED" if metrics else "PUSH_ONLY", "metrics": metrics}
        except (ValueError, TypeError, KeyError) as exc:
            result[name] = {"status": "MODEL_BLOCKED",
                            "reason": type(exc).__name__ + ":" + str(exc)}
    return result


def _aggregate_contract_scores(rows):
    metrics = defaultdict(list)
    paired = defaultdict(list)
    for row in rows:
        if row.get("state") != "SCORED":
            continue
        for model, score in row.get("scores", {}).items():
            if score.get("status") not in ("SCORED", "PUSH_ONLY"):
                continue
            for metric, value in score["metrics"].items():
                metrics[(row["stat"], model, metric)].append(value)
        for a, b in (("S2", "C2"), ("S2", "J1"), ("S2", "J2"),
                     ("J1", "J2"), ("J1", "C2"), ("J2", "C2")):
            x = row.get("scores", {}).get(a, {}).get("metrics", {})
            y = row.get("scores", {}).get(b, {}).get("metrics", {})
            for m in ("brier", "logloss", "crps"):
                if m in x and m in y:
                    paired[(row["stat"], a, b, m)].append(x[m] - y[m])
    return {
        "model_metrics": [{"stat": k[0], "model": k[1], "metric": k[2],
                           "original_contract_count": len(v), "mean": sum(v) / len(v)}
                          for k, v in sorted(metrics.items())],
        "paired_metrics": [{"stat": k[0], "first_model": k[1], "second_model": k[2],
                            "metric": k[3], "paired_original_contracts": len(v),
                            "mean_first_minus_second": sum(v) / len(v)}
                           for k, v in sorted(paired.items())],
        "independence_warning": "Same player outcomes repeated across books/lines; no IID confidence interval, edge or production signoff"
    }


def nfl_validation(storage, output, fetch=None):
    target = storage / WS6_REL
    if not target.is_file():
        return {"status": "BLOCKED_MISSING_ORIGINAL_WS6_LEDGER",
                "source_path": str(target), "original_contracts_expected": EXPECTED_NFL_ROWS}
    try:
        raw = original_input(target, WS6_SHA)
        rows = [json.loads(l) for l in raw.splitlines() if l.strip()]
        if len(rows) != EXPECTED_NFL_ROWS:
            raise ValueError("ORIGINAL_CONTRACT_DENOMINATOR_CHANGED")
        keys = [r.get("observation_index") for r in rows]
        if set(keys) != set(range(EXPECTED_NFL_ROWS)):
            raise ValueError("ORIGINAL_OBSERVATION_INDEX_NOT_EXACT")
        if any(r.get("source_sha256") is None or
               r.get("S2_original_source_model", {}).get("source_manifest_sha256", WS1_SHA) != WS1_SHA
               for r in rows if r.get("S2_original_source_model")):
            raise ValueError("ORIGINAL_SOURCE_MANIFEST_IDENTITY")
    except Exception as exc:
        return {"status": "BLOCKED_UNTRUSTED_ORIGINAL_LEDGER",
                "error": type(exc).__name__ + ":" + str(exc)}
    by_game = defaultdict(list)
    for row in rows:
        by_game[str(row["event_id"])].append(row)
    sources = {}
    for gid, game_rows in sorted(by_game.items()):
        original_starts = {r.get("event_start_at") for r in game_rows
                           if r.get("source_identity_verified") is True
                           and isinstance(r.get("event_start_at"), str)}
        if len(original_starts) > 1:
            sources[gid] = {"status": "CONFLICTING_KICKOFF_IDENTITY"}
        elif not original_starts:
            sources[gid] = {"status": "NO_VALID_ORIGINAL_SOURCE_KICKOFF"}
        else:
            kickoff = next(iter(original_starts))
            sources[gid] = fetch_final(ESPN_NFL + gid, gid, kickoff, output / "nfl_sources", fetch=fetch)
    scored = []
    for row in rows:
        gid = str(row["event_id"])
        source = sources[gid]
        base = {"observation_index": row["observation_index"], "event_id": gid,
                "player_id": str(row.get("player_id", "")), "stat": row.get("stat"),
                "line": row.get("line"), "book": row.get("book"),
                "original_quote_id": row.get("original_quote_id"),
                "joint_status": row.get("joint_status"),
                "source_certified": row.get("fully_certified") is True}
        if source["status"] != "FINAL":
            scored.append({**base, "state": "PENDING_OR_BLOCKED", "reason": source["status"]})
            continue
        if row.get("source_rejection") or row.get("source_identity_verified") is not True:
            scored.append({**base, "state": "SOURCE_REJECTED", "reason": row.get("source_rejection")})
            continue
        if row["stat"] in EXCLUDED_FOR_SCORE:
            scored.append({**base, "state": "STAT_PARITY_NOT_CERTIFIED"})
            continue
        try:
            stats, game_teams = nfl_box_values(source["data"])
            expected = set((row.get("original_quote") or {}).get("event_teams") or [])
            if expected and expected != game_teams:
                raise ValueError("OUTCOME_GAME_TEAMS_MISMATCH")
            actual, state, team = nfl_stat_observation(stats, row["player_id"], row["stat"], row.get("team"))
            if actual is None:
                scored.append({**base, "state": "UNRESOLVED_OUTCOME", "reason": state})
                continue
            line = _safe_num(row["line"])
            result = _model_distributions(row, actual, line)
            scored.append({**base, "state": "SCORED", "actual": actual,
                           "outcome_team": team, "scores": result,
                           "conditioning": "conditional_on_observed_category_stat_not_unconditional_player_eligibility",
                           "market_settlement_certified": False})
        except Exception as exc:
            scored.append({**base, "state": "OUTCOME_BLOCKED", "reason": type(exc).__name__ + ":" + str(exc)})
    summary = Counter(x["state"] for x in scored)
    source_summary = Counter(v["status"] for v in sources.values())
    make_once(output / "nfl_contract_audit.json", {"schema": "NFL_WS6_NonPromotional_OriginalContractAudit/1",
             "source_ledger_sha256": WS6_SHA, "models": ["S2", "C2", "J1", "J2"],
             "original_contract_denominator": len(scored), "source_count": dict(source_summary),
             "outcome_states": dict(summary), "rows": scored,
             "market_terms_not_certified": True})
    return {"status": "RESEARCH_CONDITIONAL_PROVISIONAL_NO_PRODUCTION_APPROVAL",
            "forecast_day": "2026-11-15", "original_contract_denominator": len(rows),
            "source_ledger_sha256": WS6_SHA,
            "number_original_events": len(by_game), "source_states": dict(source_summary),
            "outcome_state_denominators": dict(summary), "scores": _aggregate_contract_scores(scored),
            "conditions": ["ESPN FINAL boxscore only", "explicit player category stats only",
                           "no DNP or absent-stat-as-zero inference", "tackles+assists parity unapproved",
                           "C2 conditional nonpush only", "all models conditional on appearance",
                           "books share dependent outcomes; no IID inference"],
            "full_source_certification": False}


def nba_validation(storage, output, fetch=None):
    slots = registered_slots()
    capture_root = storage / NBA_ROOT
    state = Counter()
    reports = []
    for slot in slots:
        gid = slot["game"]["game_id"].split(":")[-1]
        root = capture_root / ("slot_%02d_" % slot["slot"] + gid)
        first_file = root / "FIRST_CAPTURE.json"
        record = {"slot": slot["slot"], "event_id": gid, "game_id": slot["game"]["game_id"]}
        if not first_file.is_file():
            record["status"] = "NO_GENUINE_PREGAME_CAPTURE"
            reports.append(record); state[record["status"]] += 1
            continue
        try:
            first = json.loads(first_file.read_text())
            if first["receipt_kind"] != "original_capture":
                raise ValueError("NO_ORIGINAL_CAPTURE")
            path = (root / first["attempt"] / "game_day_ledger.json").resolve()
            if not path.is_relative_to(root.resolve()):
                raise ValueError("PATH_ESCAPE")
            raw = path.read_bytes()
            if h(raw) != first["ledger_sha256"]:
                raise ValueError("IMMUTABLE_CAPTURE_HASH_MISMATCH")
            ledger = json.loads(raw)
            if ledger["game"]["game_id"] != slot["game"]["game_id"] or (
                instant(ledger["input_freeze_at"]) > instant(slot["scheduled_freeze_at"])):
                raise ValueError("PREGAME_FREEZE_IDENTITY_OR_DEADLINE")
            if ledger["game"]["event_start_at"] != slot["game"]["event_start_at"]:
                raise ValueError("SCHEDULE_REVISED_AFTER_REGISTRATION")
            original = ledger["denominators"]
            record.update(original_candidate_count=original["original_candidate_players"],
                          eligibility_known=original.get("confirmed_eligible", 0),
                          F_accepted=original.get("F_accepted", 0),
                          F_status=ledger.get("F_status"),
                          original_ledger_sha256=h(raw))
            result = fetch_final(ESPN_NBA + gid, gid, slot["game"]["event_start_at"],
                                 output / "nba_sources", fetch=fetch)
            if result["status"] != "FINAL":
                record.update(status=result["status"])
                reports.append(record);state[record["status"]] += 1
                continue
            source = result["source"]
            receipt = Receipt.capture(json.dumps(result["data"]).encode(),
                                      source=ESPN_NBA + gid, observed_at=source["retrieved_at"],
                                      origin="original_capture")
            # Use exactly original fetched raw data bytes as receipt; JSON serialization
            # is a new postgame representation (not identical original response bytes).
            # Avoid false raw SHA equivalence by storing a separate normalized source.
            record["normalized_settlement_receipt"] = receipt.raw_sha256
            outcome = settle_original(ledger, json.dumps(result["data"]).encode(), receipt)
            record.update(status="SOURCE_QUALIFIED_POSTGAME_CANDIDATE_OBSERVATIONS",
                          participation=outcome["denominator"],
                          source=source,
                          joint_F_scoring="BLOCKED_NO_VERIFIED_UNCONDITIONAL_F_ARTIFACT",
                          independent_scoring_status=outcome["review_status"])
        except Exception as exc:
            record.update(status="BLOCKED_INVALID_ORIGINAL_OR_SETTLEMENT",
                          reason=type(exc).__name__ + ":" + str(exc))
        reports.append(record);state[record["status"]] += 1
    make_once(output / "nba_participation_audit.json", {
        "schema": "NBA_V25_Phase8C_ProspectiveParticipationAudit/1",
        "original_slots": 10, "states": dict(state), "slots": reports,
        "positive_participation_model_fitted": False,
        "F_acceptance_not_inferred": True,
        "candidate_universe_not_legal_active_list": True})
    return {"status": "PARTICIPATION_SETTLEMENT_RESEARCH_ONLY", "original_slot_count": 10,
            "slot_state_denominators": dict(state),
            "source_qualified_F_model_scores": 0, "P1_P2_training_approved": False}


def main(storage="/work", date=None):
    now = utcnow().astimezone(TZ)
    today = now.date().isoformat()
    if date is not None and today != date:
        raise ValueError("RUN_DATE_DIFFERENT_FROM_REAL_CURRENT_DATE")
    date = today
    base = Path(storage)
    if not base.is_dir():
        raise ValueError("PROJECT_STORAGE_UNAVAILABLE")
    result_dir = base / OUTPUT_ROOT / date
    if result_dir.exists():
        prior = result_dir / "final.json"
        if prior.is_file():
            saved = json.loads(prior.read_text())
            return {"status": "ALREADY_COMPLETED_APPEND_ONLY", "date": date,
                    "report": str(prior), "previous_status": saved.get("status")}
        return {"status": "BLOCKED_PREVIOUS_PARTIAL_RUN_PRESERVE_FOR_REVIEW",
                "date": date, "path": str(result_dir)}
    result_dir.mkdir(parents=True, exist_ok=False)
    (result_dir / "nfl_sources").mkdir()
    (result_dir / "nba_sources").mkdir()
    make_once(result_dir / "start.json",
              {"schema": "MorningV25ResearchStart/1", "started": utcnow().isoformat(),
               "target_yesterday": (now.date() - timedelta(days=1)).isoformat(),
               "no_pregame_model_changes": True})
    summary = {"schema": "MorningV25ResearchAudit/1", "date": date,
               "target_yesterday": (now.date() - timedelta(days=1)).isoformat(),
               "started_at": utcnow().isoformat(), "research_only": True,
               "production_changed": False, "NFL": None, "NBA": None}
    try:
        summary["NFL"] = nfl_validation(base, result_dir)
    except Exception as exc:
        summary["NFL"] = {"status": "BLOCKED", "error": type(exc).__name__ + ":" + str(exc)}
    try:
        summary["NBA"] = nba_validation(base, result_dir)
    except Exception as exc:
        summary["NBA"] = {"status": "BLOCKED", "error": type(exc).__name__ + ":" + str(exc)}
    manifest = []
    for file in sorted(result_dir.rglob("*")):
        if file.is_file():
            manifest.append({"path": str(file.relative_to(result_dir)),
                             "sha256": h(file.read_bytes())})
    make_once(result_dir / "manifest.json", {"files": manifest})
    summary["manifest_sha256"] = h((result_dir / "manifest.json").read_bytes())
    summary["status"] = "RESEARCH_AUDIT_COMPLETED_WITH_EXPLICIT_UNCERTAINTY"
    summary["finished_at"] = utcnow().isoformat()
    make_once(result_dir / "final.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--storage", default="/work")
    parser.add_argument("--date")
    args = parser.parse_args()
    print(json.dumps(main(storage=args.storage, date=args.date),
                     indent=2, sort_keys=True), flush=True)
