"""WS4 v0.3 source-to-parameter adapter: bounded ORIGINAL QB pass-attempt canary.

No collector, target outcomes, 2026 future box scores, invented player histories,
line substitution, retrospectively timed forecast or production promotion.
Builds one source-certified-but-availability-uncertified shadow original-contract
event. Unmodelled roles/statistics remain explicitly unforecasted.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import pathlib
from collections import Counter, defaultdict
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
JOINT_DIR = pathlib.Path(__file__).resolve().parent
SCHEMA = "PA_WS4_JOINT_INPUT_v1"
CANONICAL_WS1 = "5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71"
CROSSWALK_SHA = "a8a86df9be83cdf88d0dadb47f09fb4a3c5db326e19b46cf20bdade38e3e024d"
HISTORY_2025_SHA = "ba1169df7f3a41b486f33b839cc0870f65f30ffac2e29978ea031d7350b3a1bb"
ARCHIVE_SNAPSHOT_AT = "2026-11-11T18:30:57.993938+00:00"
TEAM_HISTORY_PRIOR_GAMES = 4
STARTER_SHARE_PRIOR_GAMES = 3
MIN_TEAM_HISTORY_GAMES = 6
MIN_GLOBAL_QB_SHARE_GAMES = 100
TIME_MARGIN_SECONDS = 90


class AdapterError(ValueError):
    pass


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now():
    return dt.datetime.now(dt.timezone.utc)


def parse_time(s):
    t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    if not t.tzinfo or t.utcoffset() is None:
        raise AdapterError("NAIVE_SOURCE_TIME")
    return t.astimezone(dt.timezone.utc)


def checked(path, expected=None):
    data = pathlib.Path(path).read_bytes()
    h = digest(data)
    if expected and h != expected:
        raise AdapterError("IMMUTABLE_SHA_MISMATCH:" + str(path))
    return data, h


def source_receipt(source, root):
    if not isinstance(source, dict) or not source.get("archive_path"):
        raise AdapterError("MISSING_PREEXISTING_WS1_RECEIPT")
    body, actual = checked(root / source["archive_path"], source["sha256"])
    if source.get("source_bytes_verified") is not True:
        raise AdapterError("WS1_SOURCE_UNVERIFIED")
    if parse_time(source["source_received_at"]) >= now():
        raise AdapterError("SOURCE_FUTURE")
    return json.loads(body), {
        "source_uri": source["url"],
        "sha256": actual,
        "available_at": source["source_received_at"],
    }


def expected_qb_from_archived_depth(team, all_sources, root):
    source = all_sources.get("espn_" + team + "_depthcharts")
    raw, receipt = source_receipt(source, root)
    candidates = []
    for chart in raw.get("depthchart", raw.get("depthCharts", [])):
        for key, item in (chart.get("positions") or {}).items():
            if str(key).lower() not in ("qb", "quarterback"):
                continue
            order = item.get("athletes") or []
            if not order:
                continue
            player = order[0].get("athlete") or order[0]
            if player.get("id"):
                candidates.append(str(player["id"]))
    if len(set(candidates)) != 1 or not candidates:
        raise AdapterError("INDEPENDENT_QB1_DEPTH_ID_AMBIGUOUS:" + team)
    return candidates[0], receipt


def load_inputs(root):
    pin = json.loads((root / "source_control/HANDOFF_PIN.json").read_bytes())
    if pin["source_control_manifest_sha256"] != CANONICAL_WS1:
        raise AdapterError("WRONG_WS1_HANDOFF_PIN")
    src_path = root / pin["source_control_manifest_relative_path"]
    body, src_sha = checked(src_path, CANONICAL_WS1)
    m = json.loads(body)
    if m.get("schema") != "nfl_20261115_source_control_v1":
        raise AdapterError("UNKNOWN_WS1_SCHEMA")
    if (len(m["candidates"]), m["source_certified_quotes"], m["research_shadow_eligible_quotes"]) != (1845, 1767, 1753):
        raise AdapterError("WS1_ELIGIBILITY_COUNTS_CHANGED")

    crosspath = JOINT_DIR / "historical_sources" / ("nflverse_players_" + CROSSWALK_SHA + ".csv")
    crossbytes, _ = checked(crosspath, CROSSWALK_SHA)
    crossreceipt_path = JOINT_DIR / "historical_sources" / ("crosswalk_receipt_" + CROSSWALK_SHA + ".json")
    crossreceipt = json.loads(crossreceipt_path.read_text())
    if crossreceipt.get("sha256") != CROSSWALK_SHA:
        raise AdapterError("ID_CROSSWALK_RECEIPT_MISMATCH")
    mapper = defaultdict(set)
    for record in csv.DictReader(io.StringIO(crossbytes.decode("utf-8-sig"))):
        if record.get("espn_id") and record.get("gsis_id"):
            mapper[str(record["espn_id"])].add(str(record["gsis_id"]))
    hist_dir = pathlib.Path(__file__).resolve().parents[2] / "NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111" / "source_bundle"
    histpath = hist_dir / "stats_2025.json.gz"
    histbytes, _ = checked(histpath, HISTORY_2025_SHA)
    historical = json.loads(gzip.decompress(histbytes))["rows"]
    if not historical or any(r.get("season") != 2025 or r.get("season_type") != "REG" for r in historical):
        raise AdapterError("UNEXPECTED_HISTORICAL_SEASON")
    team_file = pathlib.Path(__file__).resolve().parents[3] / "pickem_runs" / "blind_historical_campaign_20261109" / "2024" / "source_bundles.json"
    team_bytes, team_sha = checked(team_file)
    bundles = json.loads(team_bytes)
    if len(bundles) != 1 or bundles[0].get("season") != 2024:
        raise AdapterError("UNEXPECTED_TEAM_HISTORY")
    teams = bundles[0]["teams"]
    if len(teams) != 544:
        raise AdapterError("TEAM_HISTORY_DENOMINATOR_CHANGED")
    return m, mapper, historical, teams, crossreceipt, team_sha


def team_rates(team_name, team_hist, recorded_at):
    valid = []
    for r in team_hist:
        try:
            plays, pa, ru = int(r["plays"]), int(r["passes"]), int(r["rushes"])
        except (KeyError, TypeError, ValueError):
            continue
        sacks = plays - pa - ru
        if plays <= 0 or pa < 0 or ru < 0 or sacks < 0:
            raise AdapterError("TEAM_PLAY_ACCOUNTING_INVALID")
        valid.append((r["team"], plays, pa, ru, sacks))
    pool = valid
    mine = [x for x in pool if x[0] == team_name]
    if len(mine) < MIN_TEAM_HISTORY_GAMES:
        raise AdapterError("TEAM_HISTORICAL_POOL_TOO_SMALL:" + team_name)
    if len(pool) < 300:
        raise AdapterError("GLOBAL_TEAM_POOL_TOO_SMALL")
    global_mean = sum(x[1] for x in pool) / len(pool)
    global_pass = sum(x[2] for x in pool) / sum(x[2] + x[3] for x in pool)
    global_sack = sum(x[4] for x in pool) / sum(x[1] for x in pool)
    k = TEAM_HISTORY_PRIOR_GAMES
    n = len(mine)
    mean = (sum(x[1] for x in mine) + k * global_mean) / (n + k)
    non_sack = sum(x[2] + x[3] for x in mine)
    totplays = sum(x[1] for x in mine)
    pass_rate = (sum(x[2] for x in mine) + k * global_mean * (1-global_sack) * global_pass) / (non_sack + k * global_mean * (1-global_sack))
    sack_rate = (sum(x[4] for x in mine) + k * global_mean * global_sack) / (totplays + k * global_mean)
    if not (40 < mean < 100 and 0 < pass_rate < 1 and 0 < sack_rate < .4):
        raise AdapterError("TEAM_PARAMETER_OUT_OF_SUPPORT")
    return {
        "plays_mean": float(mean), "pass_rate": float(pass_rate),
        "sack_rate": float(sack_rate),
        "n_team_games": n, "n_pooled_team_games": len(pool),
        "prior_equivalent_games": k, "team_observed_plays": totplays,
        "historical_season": 2024, "first_available_to_this_adapter_at": recorded_at,
        "definition": "plays=passes+rushes+residual_sacks; pass_rate conditional on non-sack modeled plays",
    }


def qb_starter_share(team_name, qb_gsis, historical):
    game = defaultdict(lambda: {"total": 0, "qb": 0, "maxqb": 0})
    for r in historical:
        if r["position"] != "QB":
            continue
        att = int(r.get("attempts", 0) or 0)
        if att < 0:
            raise AdapterError("NEGATIVE_QB_ATTEMPTS")
        key = (r["team"], r["game_id"])
        game[key]["total"] += att
        game[key]["maxqb"] = max(game[key]["maxqb"], att)
        if r["team"] == team_name and r["player_id"] == qb_gsis:
            game[key]["qb"] += att
    pool = [x["maxqb"] / x["total"] for x in game.values() if x["total"] > 0]
    if len(pool) < MIN_GLOBAL_QB_SHARE_GAMES:
        raise AdapterError("POOLED_QB_ROLE_HIST_TOO_SMALL")
    prior = sum(pool) / len(pool)
    mine = [x["qb"] / x["total"] for (t, _), x in game.items()
            if t == team_name and x["total"] > 0 and x["qb"] > 0]
    k = STARTER_SHARE_PRIOR_GAMES
    share = (sum(mine) + k * prior) / (len(mine) + k)
    if not (0 < share <= 1):
        raise AdapterError("INVALID_SHRUNK_QB_SHARE")
    return {
        "starter_attempt_share": float(share),
        "n_qb_games_on_target_team": len(mine),
        "n_pooled_max_attempt_qb_games": len(pool),
        "prior_equivalent_games": k,
        "role_prior": float(prior),
        "estimation": "2025 individual QB attempts / all team QB attempts, empirical maximum-QB-share role pool, posterior mean",
        "not_verified_injury_exit_probability": True,
        "not_confirmed_game_day_starter": True,
    }


def build_canary(source_root=ROOT):
    m, ids, hist, teams_hist, cross_receipt, teams_sha = load_inputs(source_root)
    frozen_at = now()
    recorded_at = frozen_at.isoformat()
    event_map = {x["espn_event_id"]: x for x in m["events"] if x["schedule_verified"]}
    ledger = []
    available = []
    for index, row in enumerate(m["candidates"]):
        code = row.get("source_validation_failure") or "NOT_SELECTED_CANARY"
        start = parse_time(row["event_start_at"]) if row.get("event_start_at") else None
        if not start or start <= frozen_at + dt.timedelta(seconds=TIME_MARGIN_SECONDS):
            code = "KICKOFF_CLOSED_OR_UNKNOWN"
        elif not row.get("source_certified"):
            code = row.get("source_validation_failure") or "ORIGINAL_QUOTE_NOT_CERTIFIED"
        elif not row.get("research_shadow_eligible"):
            code = row.get("eligibility_reason") or "PREGAME_ROLE_UNCERTIFIED"
        elif row.get("stat") == "pass attempts" and row.get("position") == "QB" and row.get("eligibility_status") == "EXPECTED_STARTER_SOURCE_BACKED":
            code = "POTENTIAL_QB_ATTEMPT_CANARY"
            available.append((start, index, row))
        else:
            code = "MARKET_OR_ROLE_NOT_IN_BOUNDED_CANARY"
        ledger.append({
            "original_row_index": index, "candidate_id": row.get("candidate_id"),
            "quote_id": row.get("quote_id"), "event_id": row.get("event_id"),
            "player_id": row.get("player_id"), "book": row.get("book"),
            "line": row.get("line"), "stat": row.get("stat"),
            "period": row.get("period"), "event_start_at": row.get("event_start_at"),
            "status": "ABSTAIN" if code != "POTENTIAL_QB_ATTEMPT_CANARY" else "PENDING",
            "reason": code,
        })
    available.sort(key=lambda x: (x[0], x[1]))
    errors = []
    for _, ix, c in available:
        eid = c["event_id"]
        event = event_map[eid]
        try:
            team_packets = []
            receipts = []
            param_receipts = []
            for team_name in (event["away"], event["home"]):
                expected_id, qb_receipt = expected_qb_from_archived_depth(team_name, m["sources"], source_root)
                gsis = ids.get(expected_id)
                if not gsis or len(gsis) != 1:
                    raise AdapterError("QB_GSIS_CROSSWALK_NOT_UNIQUE:" + team_name)
                stats = team_rates(team_name, teams_hist, recorded_at)
                qb_stats = qb_starter_share(team_name, next(iter(gsis)), hist)
                depth_src = m["sources"]["espn_" + team_name + "_depthcharts"]
                qb_name = next((q["player"] for q in m["candidates"] if
                    q.get("player_id") == expected_id and q.get("team") == team_name), expected_id)
                team_packets.append({
                    "team_id": team_name,
                    "plays_mean": stats["plays_mean"],
                    "pass_rate": stats["pass_rate"],
                    "sack_rate": stats["sack_rate"],
                    "starter_qb_id": expected_id,
                    "starter_status": "EXPECTED_STARTER_SOURCE_BACKED",
                    "starter_source_receipts": [qb_receipt],
                    "starter_attempt_share": qb_stats["starter_attempt_share"],
                    # Unrepresented rushers/receivers remain anonymous residual categories.
                    # No fake downstream target, yardage, tackle, or TD rate is published.
                    "players": [{"player_id": expected_id, "role": "QB", "participation": 1.0}],
                    "pregame_game_role": "UNKNOWN",
                })
                receipts.append(qb_receipt)
                param_receipts.append({
                    "team_id": team_name, "qb_espn_id": expected_id,
                    "qb_gsis_id": next(iter(gsis)), "qb_label": qb_name,
                    "team_parameters": stats, "qb_parameters": qb_stats,
                    "depth_raw_source_sha256": depth_src["sha256"],
                })
            if c["player_id"] not in [t["starter_qb_id"] for t in team_packets]:
                raise AdapterError("ORIGINAL_QUOTE_QB_NOT_VERIFIED_DEPTH_QB")
            srcbook = m["sources"].get("propline")
            _, odds_receipt = source_receipt(srcbook, source_root)
            receipts.append(odds_receipt)
            hist_receipt = {
                "source_uri": "reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/source_bundle/stats_2025.json.gz",
                "sha256": HISTORY_2025_SHA,
                "available_at": recorded_at,
            }
            history_teams_receipt = {
                "source_uri": "pickem_runs/blind_historical_campaign_20261109/2024/source_bundles.json",
                "sha256": teams_sha,
                "available_at": recorded_at,
            }
            crosswalk_receipt = {
                "source_uri": cross_receipt["uri"],
                "sha256": CROSSWALK_SHA,
                "available_at": cross_receipt["source_received_at"],
            }
            receipts.extend([hist_receipt, history_teams_receipt, crosswalk_receipt])
            raw_quote_at = c.get("source_received_at")
            if not raw_quote_at or parse_time(raw_quote_at) > frozen_at:
                raise AdapterError("ORIGINAL_QUOTE_NOT_AVAILABLE_AT_FREEZE")
            input_packet = {
                "schema": SCHEMA,
                "source_certification_status": "SOURCE_CERTIFIED_RESEARCH_SHADOW",
                "model_training_cutoff_at": ARCHIVE_SNAPSHOT_AT,
                "input_freeze_at": recorded_at,
                "events": [{
                    "event_id": eid, "event_start_at": event["scheduled_kickoff"],
                    "teams": team_packets, "source_receipts": receipts,
                    "scenario_source_receipts": [history_teams_receipt],
                }],
                "contracts": [{
                    "contract_id": c["candidate_id"],
                    "original_quote_id": c["quote_id"],
                    "original_quote_at": raw_quote_at,
                    "original_quote_receipt_sha256": c["source_sha256"],
                    "event_id": eid, "team_id": c["team"],
                    "player_id": c["player_id"],
                    "stat_key": "pass_attempts", "period": c["period"],
                    "line": float(c["line"]),
                }],
            }
            input_packet["input_manifest_sha256"] = digest(canonical(input_packet))
            if parse_time(input_packet["input_freeze_at"]) >= parse_time(event["scheduled_kickoff"]):
                raise AdapterError("POST_KICKOFF_INPUT")
            ledger[ix]["status"] = "READY_J1_ONLY"
            ledger[ix]["reason"] = "QB_PASS_ATTEMPTS_HISTORICAL_PRIORS_ROLE_CONDITIONAL"
            for j, row in enumerate(ledger):
                if row["status"] == "PENDING":
                    row["status"] = "ABSTAIN"
                    row["reason"] = "NOT_SELECTED_CANARY_EVENT"
            return {
                "input": input_packet,
                "parameters": param_receipts,
                "ledger": ledger,
                "selected_original_index": ix,
                "selected_event_start": event["scheduled_kickoff"],
                "data_receipts": {
                    "ws1_manifest_file_sha256": CANONICAL_WS1,
                    "historical_stats_2025_file_sha256": HISTORY_2025_SHA,
                    "historical_teams_2024_file_sha256": teams_sha,
                    "nflverse_id_master_sha256": CROSSWALK_SHA,
                    "crosswalk_first_received_at": cross_receipt["source_received_at"],
                    "model_training_cutoff_conservative_snapshot_at": ARCHIVE_SNAPSHOT_AT,
                    "built_at": recorded_at,
                },
                "limitations": [
                    "UNCERTIFIED_SHADOW; ESPN QB1 is depth-order expected, not active-starter confirmed",
                    "Only original QB passing-attempt contract is modeled; all other positions and markets explicitly abstain",
                    "Team pace/pass/sack rates from completed 2024 games; current 2026 form not provided",
                    "QB attempt shares from completed 2025 games with a pooled maximum-attempt-QB role prior",
                    "Non-offered downstream receiver/rush/defense opportunities are anonymous residuals",
                    "J2 early exits and J3 favorite/underdog market scenario rates unavailable",
                    "NFL official no-play, substitutions, OT and sportsbook full-game product semantics unverified",
                ],
                "errors_encountered_before_selection": errors,
            }
        except (AdapterError, KeyError, ValueError, TypeError, ZeroDivisionError) as exc:
            ledger[ix]["status"] = "ABSTAIN"
            ledger[ix]["reason"] = "HISTORICAL_PARAMETER_UNAVAILABLE:" + str(exc)
            errors.append({"original_row_index": ix, "reason": str(exc)})
    for row in ledger:
        if row["status"] == "PENDING":
            row["status"] = "ABSTAIN"
            row["reason"] = "NO_VALID_EVENT_PARAMETERS"
    return {
        "input": None, "parameters": [], "ledger": ledger,
        "data_receipts": {"ws1_manifest_file_sha256": CANONICAL_WS1,
                          "historical_stats_2025_file_sha256": HISTORY_2025_SHA,
                          "historical_teams_2024_file_sha256": teams_sha,
                          "nflverse_id_master_sha256": CROSSWALK_SHA,
                          "built_at": recorded_at},
        "errors_encountered_before_selection": errors,
        "limitations": ["NO_PROSPECTIVE_J1_COULD_BE_CONSTRUCTED"],
    }
