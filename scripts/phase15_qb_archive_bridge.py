#!/usr/bin/env python3
"""Read-only Phase 1.5 QB team-volume vs QB-share opportunity attribution.

Consumes SHA-locked *research-only* 2024 week forecasts plus the archived
postgame oracle. Date-level research freezes are NOT live pregame certification.
Never feeds realized exposures back into training or production predictions.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

from phase15_diagnostics import (Phase15Error, number, bootstrap_interval, mean,
                                 sha256_file)


def read(path):
    raw = Path(path).read_bytes()
    try:
        return json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Phase15Error("unreadable_archive:" + str(path)) from exc


def identity(row):
    fields = ("game_id", "team", "player_id", "market", "research_line")
    if any(row.get(n) in (None, "") for n in fields):
        raise Phase15Error("missing_frozen_qb_identity")
    return (str(row["game_id"]), str(row["team"]), str(row["player_id"]),
            str(row["market"]), format(number(row["research_line"], "research_line"), ".15g"))


def sh2(pred_team, pred_share, act_team, act_share, y):
    def loss(t, share):
        return (t * share - y) ** 2
    a = loss(pred_team, pred_share)
    b = loss(act_team, pred_share)
    c = loss(pred_team, act_share)
    d = loss(act_team, act_share)
    return {"team_volume": .5 * ((a-b)+(c-d)),
            "qb_allocation_share": .5 * ((a-c)+(b-d)),
            "base_squared_error": a, "oracle_squared_error": d}


def process(root: Path, vault: Path, *, replicates=1000, seed=20261110):
    root = Path(root)
    vault = Path(vault)
    oracle = read(vault)
    if not isinstance(oracle.get("weeks"), dict):
        raise Phase15Error("missing_oracle_weeks")
    rows = []
    rejected = Counter()
    source_hashes = {"oracle_sha256": sha256_file(vault), "weeks": {}}
    all_qb_forecasts = Counter()
    # Keep a team/game-level conservation ledger rather than treating all
    # candidate QBs as mutually exclusive starters with independent pools.
    predicted_qb_pool = defaultdict(float)
    predicted_team_pool = defaultdict(list)
    pair_cache = []
    for week in range(1, 19):
        frozen_path = root / "FROZEN" / ("week_%02d.json" % week)
        revealed_path = root / "REVEALED" / ("week_%02d.json" % week)
        fbytes = frozen_path.read_bytes()
        fs = hashlib.sha256(fbytes).hexdigest()
        frozen = read(frozen_path)
        revealed = read(revealed_path)
        source_hashes["weeks"][str(week)] = {
            "frozen_sha256": fs, "revealed_sha256": sha256_file(revealed_path)}
        if revealed.get("frozen_sha") != fs:
            raise Phase15Error("tampered_frozen_hash:week_" + str(week))
        if (frozen.get("week") != week or revealed.get("week") != week
                or frozen.get("stage") != "before_week_outcomes"
                or frozen.get("future_2024_week_data_accessed_by_forecaster") is not False
                or not frozen.get("research_only")
                or not isinstance(frozen.get("models_input_sha"), dict)
                or not frozen["models_input_sha"]):
            raise Phase15Error("unverified_week_replay_lock:week_" + str(week))
        if (int(frozen.get("latest_revealed_week", 9999)) >= week
                or int(frozen.get("training_label_week_limit", 9999)) >= week):
            raise Phase15Error("training_week_leak:week_" + str(week))
        originals = {}
        for r in frozen.get("predictions", []):
            if r.get("market") != "pass attempts":
                continue
            ident = identity(r)
            if ident in originals:
                raise Phase15Error("duplicated_frozen_qb")
            originals[ident] = r
            pool_key = (week, ident[0], ident[1])
            all_qb_forecasts[pool_key] += 1
            predicted_qb_pool[pool_key] += number(r.get("simulated_mean"), "qb_pred", low=0)
            predicted_team_pool[pool_key].append(number(r.get("team_xgb_pass_mean"), "team_pred", low=1e-12))
        teams = {}
        if str(week) not in oracle["weeks"]:
            raise Phase15Error("missing_oracle_week")
        for r in oracle["weeks"][str(week)].get("team_games", []):
            k = (str(r.get("game_id")), str(r.get("team")))
            if k in teams:
                raise Phase15Error("duplicate_oracle_team")
            teams[k] = r
        seen_revealed = set()
        for x in revealed.get("full_research_rows", []):
            if x.get("market") != "pass attempts":
                continue
            ident = identity(x)
            if ident in seen_revealed:
                raise Phase15Error("duplicated_revealed_qb")
            seen_revealed.add(ident)
            if ident not in originals:
                raise Phase15Error("graded_qb_not_frozen")
            r = originals[ident]
            for field in ("simulated_mean", "team_xgb_pass_mean", "p_over_hurdle"):
                if not math.isclose(number(r.get(field), field),
                                    number(x.get(field), field), rel_tol=0, abs_tol=1e-9):
                    raise Phase15Error("frozen_qb_prediction_mutated:" + field)
            if not isinstance(x.get("graded"), bool):
                raise Phase15Error("graded_status_not_boolean")
            if not x["graded"]:
                rejected["not_graded"] += 1
                continue
            t = teams.get((ident[0], ident[1]))
            if t is None:
                rejected["no_team_oracle"] += 1
                continue
            actual_team = number(t.get("pass_attempts"), "team_actual", low=0)
            if actual_team == 0:
                rejected["zero_team_actual"] += 1
                continue
            pred_team = number(r.get("team_xgb_pass_mean"), "team_pred", low=1e-12)
            pred_qb = number(r.get("simulated_mean"), "qb_pred", low=0)
            y = number(x.get("actual_stat"), "qb_actual", low=0)
            if y > actual_team + 1e-6:
                raise Phase15Error("qb_attempts_exceed_team_attempts")
            pred_share = pred_qb / pred_team
            actual_share = y / actual_team
            if pred_share > 1 + 1e-6:
                raise Phase15Error("predicted_qb_share_exceeds_one")
            oracle_diag = sh2(pred_team, pred_share, actual_team, actual_share, y)
            row = {"week": str(week), "game": str(week)+"|"+ident[0],
                   "player_id": ident[2], "team":ident[1], "pred_team":pred_team,
                   "actual_team":actual_team, "pred_qb":pred_qb,"actual_qb":y,
                   "pred_share":pred_share, "actual_share":actual_share,
                   "qb_forecast_count_for_team_game": all_qb_forecasts[(week, ident[0], ident[1])],
                   **oracle_diag}
            rows.append(row)
        if not set(originals).issuperset(seen_revealed):
            raise Phase15Error("revealed_outside_frozen")
    if not rows:
        raise Phase15Error("empty_verified_qb_cohort")
    # All actual team outcomes are postgame and allowed only in this audit.
    if abs(mean([r["team_volume"]+r["qb_allocation_share"] for r in rows])
           - mean([r["base_squared_error"]-r["oracle_squared_error"] for r in rows])) > 1e-7:
        raise Phase15Error("qb_shapley_conservation_failed")
    team_pool_summary = []
    for team_key, total_qb_mean in predicted_qb_pool.items():
        team_means = predicted_team_pool[team_key]
        inconsistent = max(team_means) - min(team_means) > 1e-6
        team_pool_summary.append({
            "sum_predicted_candidate_qb_attempts": total_qb_mean,
            "reference_team_attempts": team_means[0],
            "candidate_qbs": all_qb_forecasts[team_key],
            "team_mean_inconsistent": inconsistent,
            "predicted_qb_total_exceeds_team": total_qb_mean > min(team_means) + 1e-6,
        })
    graded_actual_by_pool = defaultdict(float)
    for r in rows:
        pool_key = (int(r["week"]), r["game"].split("|", 1)[1], r["team"])
        graded_actual_by_pool[pool_key] += r["actual_qb"]
    # Oracle team accounting should never count more completed QB attempts
    # than the official team's total passing attempts.
    actual_team_by_pool = {}
    for week in range(1, 19):
        for t in oracle["weeks"][str(week)].get("team_games", []):
            actual_team_by_pool[(week, str(t.get("game_id")), str(t.get("team")))] = number(
                t.get("pass_attempts"), "team_actual", low=0)
    for pool_key, graded_sum in graded_actual_by_pool.items():
        if graded_sum > actual_team_by_pool[pool_key] + 1e-6:
            raise Phase15Error("graded_qb_attempt_pool_exceeds_team_total")
    result = {"schema":"pickem-phase15-qb-opportunity-oracle-v1",
              "mode":"offline_date_level_freeze_not_certified_pregame",
              "cohort":"independent_2024_research_archive_not_necessarily_untouched",
              "tier_certified":False,"production_changes":False,
              "n":len(rows),"games":len({r["game"] for r in rows}),
              "weeks":len({r["week"] for r in rows}),
              "excluded":dict(rejected),
              "team_game_candidate_pool_diagnostic": {
                  "team_game_groups": len(team_pool_summary),
                  "multi_candidate_groups": sum(x["candidate_qbs"] > 1 for x in team_pool_summary),
                  "predicted_qb_total_exceeds_team_groups": sum(
                      x["predicted_qb_total_exceeds_team"] for x in team_pool_summary),
                  "inconsistent_team_volume_forecast_groups": sum(
                      x["team_mean_inconsistent"] for x in team_pool_summary),
                  "note": ("All forecast QB candidates counted. Not a lineup projection: "
                           "bench QBs may be mutually exclusive; group sums are a "
                           "physical-coherence diagnostic, not bets or starter probabilities.")
              },
              "mean_predicted_team_attempts":mean([r["pred_team"] for r in rows]),
              "mean_actual_team_attempts":mean([r["actual_team"] for r in rows]),
              "mean_predicted_qb_attempts":mean([r["pred_qb"] for r in rows]),
              "mean_actual_qb_attempts":mean([r["actual_qb"] for r in rows]),
              "mean_predicted_qb_share":mean([r["pred_share"] for r in rows]),
              "mean_actual_qb_share":mean([r["actual_share"] for r in rows]),
              "mean_squared_error":mean([r["base_squared_error"] for r in rows]),
              "mean_oracle_squared_error":mean([r["oracle_squared_error"] for r in rows]),
              "mean_shapley_error_reduction":{}, "clustered_intervals":{},
              "forecast_qb_count":dict(sorted(Counter(str(v) for v in all_qb_forecasts.values()).items())),
              "by_qb_forecast_multiplicity":{},
              "source_hashes":source_hashes,
              "limitations":[
                 "Frozen dates lack authenticated intraday offer and freeze timestamps.",
                 "2024 research-line experiments are synthetic, not sportsbook evaluation.",
                 "Historical cohort used for model research and may have design exposure.",
                 "Actual team attempts and QB share enter only this retrospective oracle.",
                 "Shares calculated as model QB mean / model team mean; not proof of conditional role probabilities.",
                 "Many QB forecast candidates are mutually exclusive starter/backup scenarios; naive grouped means may overstate true game pool.",
                 "Observed share Shapley attribution mechanically absorbs any player-level bias not represented by predicted team totals.",
                 "Shapley squared-error gain is observational, not causal or directly achievable.",
                 "QB-only evidence does not establish causes for receiver, rusher or defender markets."
              ]}
    for label in ("team_volume", "qb_allocation_share"):
        result["mean_shapley_error_reduction"][label] = mean([r[label] for r in rows])
        result["clustered_intervals"][label] = {
           cluster:bootstrap_interval(rows, lambda r, k=label:r[k],cluster=cluster,
                          replicates=replicates,seed=seed)
           for cluster in ("game", "week")}
    for segment in ("1", "2plus"):
        sub = [r for r in rows if (r["qb_forecast_count_for_team_game"]==1) == (segment=="1")]
        result["by_qb_forecast_multiplicity"][segment] = {
            "n":len(sub), "mean_predicted_qb_attempts":mean([r["pred_qb"] for r in sub]),
            "mean_actual_qb_attempts":mean([r["actual_qb"] for r in sub]),
            "mean_pred_share":mean([r["pred_share"] for r in sub]),
            "mean_actual_share":mean([r["actual_share"] for r in sub]),
            "mean_qb_error":mean([r["pred_qb"]-r["actual_qb"] for r in sub])}
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root",type=Path,required=True)
    ap.add_argument("--oracle",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--bootstrap",type=int,default=1000)
    args=ap.parse_args(argv)
    if not 0 <= args.bootstrap <= 20000:
        ap.error("bootstrap must be in [0,20000]")
    result=process(args.root,args.oracle,replicates=args.bootstrap)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n")
    print(json.dumps({k:result[k] for k in ("schema","n","games","weeks",
                                           "mean_shapley_error_reduction","tier_certified")}))


if __name__=="__main__":
    main()
