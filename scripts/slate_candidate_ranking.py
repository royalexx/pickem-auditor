#!/usr/bin/env python3
"""Evidence-backed per-sport top-ten research priorities, never approved picks.

This is a *screening* heuristic, not a learned probability, calibrated hit
rate, or change to any production forecast. Full-slate selection prevents the
30-item research triage queue from silently omitting strong candidates.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import date as calendar_date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlparse

from nfl_volume_market_policy import nfl_volume_market_allowed
from research_triage import latest_batch
from usage_baseline import key as usage_key, local_day, validate_rows

VERSION = "slate-evidence-priority-v1"
SPORTS = ("NBA", "NHL", "NFL")
MODEL_NAMES = ("Engine_A", "Engine_B", "Bayesian_A", "Bayesian_B")
RESEARCH_REASONS = {"STATUS_NOT_VERIFIED", "VENUE_OR_FORECAST_UNVERIFIED",
                    "CONTEXT_UNRESOLVED", "RESEARCH_UNVERIFIED",
                    "POST_SHADOW_PRODUCTION_PENDING"}
MIN_CONSENSUS = 0.58
MIN_EDGE_PP = 3.0


def probability(x):
    return type(x) in (int, float) and math.isfinite(x) and 0 <= x <= 1


def when(x):
    if not isinstance(x, str):
        return None
    try:
        dt = datetime.fromisoformat(x.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except ValueError:
        return None


def _safe_source(url):
    try:
        parsed = urlparse(url)
        return url if parsed.scheme == "https" and parsed.hostname and "." in parsed.hostname else None
    except (ValueError, TypeError):
        return None


def _outcome(value, line, side):
    if side == "over":
        return "win" if value > line else ("push" if value == line else "loss")
    return "win" if value < line else ("push" if value == line else "loss")


def _window(games, line, side):
    outcomes = Counter(_outcome(g["value"], line, side) for g in games)
    played = len(games)
    settled = outcomes["win"] + outcomes["loss"]
    return {"games": played, "wins": outcomes["win"], "losses": outcomes["loss"],
            "pushes": outcomes["push"],
            "hit_rate_excluding_pushes": round(outcomes["win"]/settled, 4) if settled else None}


def historical_evidence(row, data_root):
    """Verify same-subject, same-stat, pre-forecast observation provenance."""
    absent = {"status": "unavailable", "reason": "verified_exact_stat_usage_history_not_available",
              "last_5": None, "last_10": None, "opportunity": None}
    sport, stat, player_id, day = (row.get(x) for x in
                                    ("sport", "stat", "player_id", "game_date"))
    if not sport or not stat or not player_id or not day:
        return {**absent, "reason": "usage_identity_incomplete"}
    try:
        file = Path(data_root)/"usage"/(usage_key(sport, player_id, stat, day)+".json")
        payload = json.loads(file.read_text(encoding="utf-8"))
        digest = payload.pop("content_sha256", None)
        encoded = json.dumps(payload, sort_keys=True, allow_nan=False).encode()
        if not isinstance(digest, str) or digest != hashlib.sha256(encoded).hexdigest():
            raise ValueError("usage_digest_mismatch")
        if (payload.get("sport") != sport or str(payload.get("player_id")) != str(player_id)
                or payload.get("team") != row.get("team")
                or payload.get("game_date") != day):
            raise ValueError("usage_subject_mismatch")
        from usage_baseline import source_stat
        if source_stat(payload.get("stat")) != source_stat(stat):
            raise ValueError("usage_stat_mismatch")
        captured, cutoff = when(payload.get("retrieved_at")), when(row.get("forecast_at"))
        if captured is None or cutoff is None or captured > cutoff:
            raise ValueError("usage_captured_after_forecast_or_undated")
        c = {"sport": sport, "stat": stat, "game_date": day}
        clean = validate_rows(payload.get("observations"), c, cutoff)
        # No prior-season padding: descriptive hits must be current-season only.
        # Only observations in the subject's current sports season qualify for
        # displayed "current-season" rates. Prior-season borrowing belongs
        # exclusively to the original forecasting engine, not this narrative.
        season_day = local_day(day)
        season_start_year = season_day.year if season_day.month >= 7 else season_day.year-1
        season_start = calendar_date(season_start_year, 7, 1)
        games = [{"day": d, "id": ident, "value": value, "workload": volume}
                 for d, ident, value, volume in clean if d >= season_start]
        if not games:
            return {**absent, "reason": "no_current_season_observations"}
        recent = games[-5:]
        prior = games[-10:-5]
        def exposure(items):
            if not items or any(x["workload"] is None for x in items):
                return None
            return sum(x["workload"] for x in items)/len(items)
        last5 = exposure(recent)
        previous5 = exposure(prior) if len(prior) == 5 else None
        units = {"NBA": "minutes", "NHL": "ice-time units", "NFL": "collector workload units"}.get(sport)
        trend = round(100*(last5/previous5-1), 1) if (
            last5 is not None and previous5 and previous5 > 0) else None
        url = _safe_source(payload.get("source_url"))
        if url is None:
            raise ValueError("usage_public_source_missing")
        return {"status": "verified_historical", "source_url": url,
                "source_digest": digest, "history_collected_at": captured.isoformat(),
                "history_through": games[-1]["day"].isoformat(), "current_season_games": len(games),
                "last_5": _window(recent, row["reference_line"], row["side"]),
                "last_10": _window(games[-10:], row["reference_line"], row["side"])
                           if len(games) >= 10 else None,
                "opportunity": {"recent_games": len(recent), "units": units,
                                "last_5_mean": round(last5, 2) if last5 is not None else None,
                                "previous_5_mean": round(previous5, 2) if previous5 is not None else None,
                                "change_pct": trend,
                                "status": "measured_historical_exposure" if last5 is not None
                                          else "exposure_not_recorded"}}
    except (OSError, TypeError, ValueError, KeyError, IndexError, OverflowError):
        return {**absent, "reason": "usage_missing_or_failed_integrity_or_date_checks"}


def _score(consensus, floor, edge_pp, spread, history):
    """Bounded transparent heuristic, explicitly not a P(win) estimate.

    Consensus 40%, lowest available model 25%, relative market edge 25%,
    model agreement 5%, historical opportunity evidence 5%.
    """
    edge_factor = max(0.0, min(edge_pp/25.0, 1.0))
    agreement_factor = 1.0-min(spread/0.30, 1.0)
    opportunity_factor = (1.0 if history["status"] == "verified_historical"
                          and history["opportunity"] is not None
                          and history["opportunity"]["last_5_mean"] is not None else 0.0)
    terms = {"production_consensus": 40.0*consensus,
             "conservative_model_floor": 25.0*floor,
             "market_edge": 25.0*edge_factor,
             "model_agreement": 5.0*agreement_factor,
             "observed_opportunity_evidence": 5.0*opportunity_factor}
    return round(sum(terms.values()), 3), {k: round(v, 3) for k, v in terms.items()}


def candidate(row, comparison, *, data_root):
    if not nfl_volume_market_allowed(row.get("sport"),row.get("stat")):
        return None, "nfl_market_excluded_volume_only_policy"
    if (comparison.get("production_consensus_available") is not True
            or row.get("reason") not in RESEARCH_REASONS
            or not (row.get("engine_a") or {}).get("reliable")
            or not (row.get("engine_b") or {}).get("reliable")
            or (row.get("market") or {}).get("market_valid") is False):
        return None, "production_or_primary_research_gate"
    # The comparison layer itself verifies exact frozen side/line/fixture/prices.
    market_meta = (comparison.get("models") or {}).get("Market") or {}
    if market_meta.get("status") != "forecast" or len(market_meta.get("books") or []) < 2:
        return None, "fewer_than_two_matched_frozen_books"
    if (any(row.get(k) != comparison.get(k) for k in ("sport", "player", "player_id", "team", "opponent", "stat", "side"))
            or row.get("reference_line") != comparison.get("line")
            or row.get("run_id") != comparison.get("run_id")
            or row.get("forecast_at") != comparison.get("forecast_at")):
        return None, "comparison_snapshot_identity_mismatch"
    vals = {name: comparison.get(name) for name in MODEL_NAMES}
    consensus, market = comparison.get("Consensus"), comparison.get("Market")
    if (not all(probability(x) for x in (consensus, market, vals["Engine_A"], vals["Engine_B"]))
            or any(v is not None and not probability(v) for v in vals.values())):
        return None, "invalid_probability_or_provenance"
    if consensus < MIN_CONSENSUS:
        return None, "below_consensus_watch_floor"
    edge = 100*(consensus-market)
    if edge < MIN_EDGE_PP:
        return None, "below_market_edge_watch_floor"
    observed = [v for v in vals.values() if v is not None]
    conservative = min(observed)
    spread = max(observed)-conservative
    hist = historical_evidence(row, data_root)
    score, components = _score(consensus, conservative, edge, spread, hist)
    warnings = ["game_specific_active_status_not_verified",
                "probabilities_not_empirically_calibrated_for_tiers"]
    if spread > .15:
        warnings.append("material_model_disagreement_review_role_and_sample")
    if edge >= 8.0:
        warnings.append("large_market_gap_requires_independent_price_and_assumption_review")
    if hist["status"] != "verified_historical":
        warnings.append("exact_line_hit_history_unavailable")
    if hist.get("opportunity") is None or hist["opportunity"]["last_5_mean"] is None:
        warnings.append("historical_exposure_not_verified")
    if not all(vals.get(k) is not None for k in ("Bayesian_A", "Bayesian_B")):
        warnings.append("one_or_more_bayesian_challengers_unavailable")
    messages = [
        f"Consensus {consensus:.1%}; lowest available A/B/Bayesian model {conservative:.1%}; "
        f"paired-book market {market:.1%} (edge {edge:+.1f} pp).",
        f"Model spread {100*spread:.1f} pp across {len(observed)} available families; "
        "disagreement receives a bounded penalty, not a veto."]
    if hist["status"] == "verified_historical":
        sample = hist["last_5"]
        messages.append(f"Exact {row['side']} {row['reference_line']} hit history: "
                        f"{sample['wins']}/{sample['games']} over last five current-season games "
                        f"({sample['pushes']} pushes); descriptive only and overlaps Engine A inputs.")
        if hist["last_10"] is not None:
            past = hist["last_10"]
            messages.append(f"At the same line across last ten current-season games: "
                            f"{past['wins']}/{past['games']} wins, {past['pushes']} pushes; "
                            "small samples are descriptive, not independently calibrated.")
        opp = hist["opportunity"]
        if opp["last_5_mean"] is not None:
            text = (f"Observed workload {opp['last_5_mean']:.1f} {opp['units']} over last "
                    f"{opp['recent_games']} games")
            if opp["change_pct"] is not None:
                text += f"; {opp['change_pct']:+.1f}% against preceding five games"
            messages.append(text + "; not a verified projection of tonight's role.")
        else:
            messages.append("Recent workload could not be authenticated from the collected observations.")
    else:
        messages.append("No integrity-checked same-line game history available; do not claim a hit rate.")
        messages.append("Recent workload/opportunity evidence unavailable; game-specific role unverified.")
    if (row.get("shared_context") or {}).get("applied"):
        messages.append("Source-owned lineup redistribution applied to the frozen forecast; "
                        "not independently verified here.")
    messages.append("Pregame lineup, injury, opportunity and market refresh checks remain required.")
    return {"game_date": row["game_date"], "sport": row["sport"],
            "player": row["player"], "player_id": row.get("player_id"),
            "team": row.get("team"), "opponent": row.get("opponent"), "stat": row["stat"],
            "side": row["side"], "line": row["reference_line"], "run_id": row["run_id"],
            "forecast_at": row["forecast_at"], "event_start": row.get("event_start"),
            "research_priority_score": score, "score_components": components,
            "production_consensus": consensus, "conservative_model_floor": conservative,
            "market": market, "market_edge_pp": round(edge, 2),
            "model_spread_pp": round(100*spread, 2), "model_probabilities": vals,
            "NUTS": comparison.get("NUTS"), "NUTS_status": comparison.get("NUTS_status"),
            "NUTS_model": comparison.get("NUTS_model"),
            "history": hist, "explanations": messages, "warnings": warnings,
            "verification_status": "pending", "publication_eligible": False,
            "research_only": True, "tier": None}, None


def full_universe_review(row, comparison, *, data_root):
    """One descriptive evidence check per frozen contract, including rejects.

    This record NEVER changes the forecast or converts an unverified matchup
    observation into an Engine B adjustment. It explicitly reports missing
    player/opponent/weather evidence across the whole slate, not just top ten.
    """
    inputs = row.get("inputs") if isinstance(row.get("inputs"), dict) else {}
    history = historical_evidence(row, data_root)
    numeric_keys = {
        "NFL": ("def_matchup_factor", "def_matchup_ratio",
                "def_forced_checkdown_rate", "def_first_read_suppression_rate",
                "def_rb_target_funnel_share"),
        "NHL": ("shots_against_per_game", "shots_against_ratio"),
        "NBA": (),
    }
    observed = {
        key: inputs[key] for key in numeric_keys.get(row.get("sport"), ())
        if type(inputs.get(key)) in (int, float)
        and math.isfinite(inputs[key])
    }
    player_observed = {
        key: inputs[key] for key in
        ("snap_share", "target_share", "routes_per_game", "route_share",
         "offense_snaps_per_game", "defense_snaps_per_game",
         "pace_per_game", "pace_ratio", "ice_time_per_game",
         "minutes", "possessions")
        if type(inputs.get(key)) in (int, float)
        and math.isfinite(inputs[key])
    }
    # No unobserved opponent tendency, injury, role, or weather is inferred.
    # Collector input values are descriptions and require independent source
    # checks before they become verified contextual facts.
    return {
        "game_date": row.get("game_date"), "run_id": row.get("run_id"),
        "sport": row.get("sport"), "player": row.get("player"),
        "player_id": row.get("player_id"), "team": row.get("team"),
        "opponent": row.get("opponent"), "stat": row.get("stat"),
        "side": row.get("side"), "line": row.get("reference_line"),
        "forecast_at": row.get("forecast_at"),
        "original_block_reason": row.get("reason"),
        "model_consensus": comparison.get("Consensus"),
        "model_columns": {name: comparison.get(name) for name in
                          ("Engine_A", "Engine_B", "Bayesian_A", "Bayesian_B",
                           "Market", "NUTS")},
        "player_tendency": history,
        "player_context_inputs": player_observed,
        "opponent_tendency": {
            "status": ("collector_hints_require_independent_verification"
                       if observed else "not_source_supported"),
            "source_fields": observed,
            "missing_opponent_causal_evidence": not bool(observed)},
        "availability": "game_specific_status_not_verified",
        "weather": "venue_aware_weather_verification_required",
        "scenario_validation": "pending_source_verified_matchup_and_role_scenarios",
        "rank_eligibility": "research_only_not_betting_approval",
    }


def build(snapshots, comparisons, date, *, data_root):
    """Rank the entire frozen batch, not only queued research subjects."""
    if len(snapshots) != len(comparisons):
        raise ValueError("comparison_count_mismatch")
    pool, excluded = [], Counter()
    full_reviews = []
    for row, comp in zip(snapshots, comparisons):
        if row.get("game_date") != date or comp.get("game_date") != date:
            raise ValueError("cross_date_comparison")
        full_reviews.append(full_universe_review(row, comp, data_root=data_root))
        x, reason = candidate(row, comp, data_root=data_root)
        if x:
            pool.append(x)
        else:
            excluded[reason] += 1
    pool.sort(key=lambda x: (-x["research_priority_score"], -x["conservative_model_floor"],
                             -x["market_edge_pp"], x["sport"], x["player"], x["stat"], x["side"]))
    top = {}
    for sport in SPORTS:
        picked, players, fixtures, identities = [], Counter(), Counter(), set()
        for row in (r for r in pool if r["sport"] == sport):
            fixture = tuple(sorted((str(row["team"]), str(row["opponent"]))))
            ident = (str(row["player_id"] or row["player"]), row["stat"], row["line"])
            # Avoid opposite-side duplicates, excessive correlated player bets
            # and a slate dominated by one game; all other rows remain in pool.
            if ident in identities or players[ident[0]] >= 2 or fixtures[fixture] >= 4:
                continue
            picked.append({**row, "sport_rank": len(picked)+1})
            identities.add(ident)
            players[ident[0]] += 1
            fixtures[fixture] += 1
            if len(picked) == 10:
                break
        top[sport] = picked
    return {"schema": VERSION, "date": date, "ranking_kind": "research_only",
            "ranking_not_a_probability": True, "ranking_not_calibrated": True,
            "min_consensus": MIN_CONSENSUS, "min_edge_pp": MIN_EDGE_PP,
            "score_formula": ("40*Consensus + 25*min(A,B,BayesianA,BayesianB available) "
                              "+ 25*clip((Consensus-Market)*100/25,0,1) "
                              "+ 5*(1-clip(model_spread/0.30,0,1)) "
                              "+ 5*verified_historical_workload_available"),
            "candidate_pool_count": len(pool), "excluded": dict(excluded),
            "top_10_by_sport": top, "top_counts": {s: len(top[s]) for s in SPORTS},
            "full_universe_evaluated": len(snapshots),
            "full_universe_before_top10": True,
            "full_universe_reviews": full_reviews,
            "full_universe_review_count": len(full_reviews),
            "publication_eligible": False, "original_forecasts_unchanged": True}


def render_markdown(report):
    lines = ["# Research priorities — "+report["date"], "",
             "**Not approved picks.** This is a transparent, uncalibrated "
             "verification-priority score. No probability or Tier is changed.",
             "", "Selection: at least 58% production consensus, +3 pp market edge, "
             "two matched archived books, both reliable production engines, and "
             "a research-pending primary reason. At most two markets per player "
             "and four per fixture among the ten; all other candidates remain "
             "in the archived comparison. NUTS is reported but does not alter the score.",
             ""]
    for sport, items in report["top_10_by_sport"].items():
        lines.extend(["## "+sport, ""])
        if not items:
            lines.extend(["No candidates met the research screen.", ""])
        for item in items:
            lines.append(f"### {item['sport_rank']}. {item['player']} — "
                         f"{item['side']} {item['line']} {item['stat']} "
                         f"({item['team']} vs {item['opponent']})")
            lines.append(f"Priority score: **{item['research_priority_score']:.1f}/100** "
                         "(NOT a hit probability). NUTS: "+(
                             "N/A" if item["NUTS"] is None else f"{item['NUTS']:.1%}")+".")
            for explanation in item["explanations"]:
                lines.append("- "+explanation)
            lines.append("Warnings: "+", ".join(item["warnings"])+".")
            lines.append("")
    return "\n".join(lines)+"\n"


def write(report, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    # The compact top-ten remains compatible with existing review consumers.
    # The complete matching-contract review is a separate exhaustive artifact.
    compact = {k: v for k, v in report.items() if k != "full_universe_reviews"}
    (out/"slate_top10_evidence.json").write_text(
        json.dumps(compact, indent=2, allow_nan=False, ensure_ascii=False)+"\n", encoding="utf-8")
    (out/"slate_top10_evidence.md").write_text(render_markdown(compact), encoding="utf-8")
    (out/"slate_full_universe_research.json").write_text(
        json.dumps({
            "schema":"slate-full-universe-player-opponent-review-v1",
            "date":report["date"],
            "run_id":report["full_universe_reviews"][0]["run_id"]
                     if report["full_universe_reviews"] else None,
            "contracts_reviewed":report["full_universe_review_count"],
            "top10_is_only_a_display_limit":True,
            "requires_external_source_checks":True,
            "reviews":report["full_universe_reviews"]},
            ensure_ascii=False, allow_nan=False, separators=(",",":"))+"\n",
        encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", required=True)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--out-dir", type=Path, required=True)
    args = p.parse_args()
    snapshots = [json.loads(s) for s in (args.root/"data/prop_snapshots.jsonl").read_text().splitlines() if s.strip()]
    batch, run = latest_batch(snapshots, args.date)
    data = json.loads((args.out_dir/"slate_model_comparisons.json").read_text())
    if data.get("metadata", {}).get("run_id") != run:
        raise ValueError("comparison_run_mismatch")
    report = build(batch, data["picks"], args.date, data_root=args.root/"data")
    write(report, args.out_dir)
    print(json.dumps({"schema": VERSION, "top_counts": report["top_counts"],
                      "candidate_pool_count": report["candidate_pool_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
