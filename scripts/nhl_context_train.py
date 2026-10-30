#!/usr/bin/env python3
"""Native Windows/Unix context challenger lifecycle, all stages explicit.

plan -> collect (nhl_context_data.py) -> freeze -> fit -> evaluate.
Never launches a large fit by default, changes production, or promotes a fit.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import nhl_context_data as store
import nhl_context_features as features


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix+".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+"\n", encoding="utf-8")
    os.replace(temp, path)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def code_provenance():
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=store.ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git","status","--porcelain"],cwd=store.ROOT,
                                   capture_output=True,text=True,check=True).stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        sha = None
        dirty = None
    versions={}
    for name in ("numpy","scipy","pymc","pytensor","arviz","arviz-stats","h5netcdf","h5py"):
        try:versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:versions[name]=None
    return {"git_code_sha": sha, "worktree_dirty":dirty,"python": platform.python_version(), "platform": platform.platform(),
            "package_versions":versions,
            "script_sha256": {p.name: file_hash(p) for p in sorted(Path(__file__).parent.glob("nhl_context_*.py"))}}


def plan(root, *, train_from, until, output):
    """Reuse IDs only; old saves/minutes cannot recreate absent team context."""
    import population_history as history
    start, end = store.instant(train_from), store.instant(until)
    if not start < end <= datetime.now(timezone.utc):
        raise ValueError("invalid_collection_window")
    warmup = (start-timedelta(days=120)).date().isoformat()
    rows = history.read(root, sport="NHL", stat="saves", after=warmup,
                        before=end.date().isoformat(), max_seasons=None, min_records=1)
    ids = sorted({r["game_id"] for r in rows})
    write_json(output, ids)
    report = {"schema": "nhl-context-collection-plan-v1", "games": len(ids), "warmup_from": warmup,
              "until_exclusive": until, "id_source": "existing_NHL_saves_population",
              "schedule_completeness_verified": False,
              "estimated_requests_core_max": 2*len(ids), "requests_with_attempts": 2*len(ids),
              "uses_sportsbook_api": False, "ranking_allowed": False}
    write_json(Path(output).with_suffix(".plan.json"), report)
    return report


def audit_collection(root, *, expected_ids, output, verify_raw=False):
    expected = load_json(expected_ids)
    if not isinstance(expected,list) or len(set(map(str,expected)))!=len(expected):
        raise ValueError("invalid_expected_game_id_list")
    bundles = store.read_bundles(root)
    present={b["game_id"] for b in bundles}
    missing=sorted(set(map(str,expected))-present)
    by_season={}
    shot_differences=[]
    for b in bundles:
        if verify_raw:
            store.verify_bundle_source(root,b)
        season=by_season.setdefault(b["season"],{"games":0,"teams":{},"with_attempts":0})
        season["games"]+=1
        season["with_attempts"]+=int(all(r["attempts_for"] is not None for r in b["teams"]))
        for row in b["teams"]:
            season["teams"][row["team"]]=season["teams"].get(row["team"],0)+1
            if row.get("team_minus_skater_shots",0):
                shot_differences.append({"game_id":b["game_id"],"team":row["team"],
                    "team_shots":row["shots_for"],"team_minus_skater_shots":row["team_minus_skater_shots"]})
    report={"schema":"nhl-context-collection-audit-v1","expected_games":len(expected),
            "present_games":len(present),"missing_game_ids":missing,"by_season":by_season,
            "complete_against_provided_ids":not missing,"schedule_source_independently_verified":False,
            "raw_sources_reconciled":bool(verify_raw),
            "team_skater_shot_differences":shot_differences,
            "ranking_allowed":False}
    write_json(output,report)
    return report


def freeze(root, *, train_from, cutoff, market, feature_set, policy, output,
           min_rows=200, pilot_games=0, xg_path=None, training_game_ids_path=None):
    start, end = store.instant(train_from), store.instant(cutoff)
    if not start < end <= datetime.now(timezone.utc) or pilot_games < 0:
        raise ValueError("invalid_training_window_or_cohort")
    output = Path(output)
    if (output/"design.json").exists() or (output/"posterior.nc").exists():
        raise ValueError("frozen_experiment_already_exists_choose_new_output")
    bundles = store.read_bundles(root)
    xg_rows = load_json(xg_path) if xg_path else []
    # Keep the raw input universe fixed alongside the design. A later warehouse
    # backfill cannot change a previous holdout's rolling features or coverage.
    rows, omitted = features.examples(bundles, market=market, policy=policy,
                                      feature_set=feature_set, xg_rows=xg_rows)
    train = [r for r in rows if start <= store.instant(r["start_time"]) < end
             and store.instant(r["target_available_at"]) < end]
    if training_game_ids_path:
        allowed=load_json(training_game_ids_path)
        if not isinstance(allowed,list) or len(set(allowed))!=len(allowed):
            raise ValueError("invalid_training_game_allowlist")
        allowed=set(allowed)
        train=[r for r in train if r["game_id"] in allowed]
        if {r["game_id"] for r in train}!=allowed:
            raise ValueError("planned_training_games_missing_eligible_observations")
    elif pilot_games:
        train=features.pilot_cohort(train,pilot_games)
    design = features.prepare(train, cutoff=cutoff, feature_set=feature_set, min_rows=min_rows)
    future_seasons=sorted({r["season"] for r in rows if store.instant(r["start_time"])>=end})
    unseen_seasons=sorted(set(future_seasons)-set(design["seasons"]))
    if unseen_seasons and len(design["seasons"])<2:
        raise ValueError("unseen_holdout_season_requires_two_training_seasons_before_sampling")
    design.update(pilot_games=pilot_games, train_from=train_from,
                  xg_vintages=sorted({(r["provider"],r["model_version"]) for r in xg_rows}))
    output.mkdir(parents=True, exist_ok=True)
    write_json(output/"design.json", design)
    write_json(output/"frozen_bundles.json", bundles)
    write_json(output/"frozen_xg.json", xg_rows)
    write_json(output/"training_rows.json", train)
    report = {"schema": "nhl-context-preflight-v1", "market": market, "feature_set": feature_set,
              "rows": len(train), "games": design["games"], "players": len(design["players"]),
              "seasons": design["seasons"], "teams": len(design["teams"]),
              "train_from": train_from, "cutoff_exclusive": cutoff,
              "pilot_subset": bool(pilot_games), "availability_policy": policy,
              "pilot_selection":"latest_with_prior_season_anchor" if pilot_games else "all_eligible_training_games",
              "explicit_training_game_allowlist":bool(training_game_ids_path),
              "available_future_seasons":future_seasons,"unseen_future_seasons":unseen_seasons,
              "retrospective_availability_approximation": policy != "recorded",
              "source_digest": design["source_digest"], "design_digest": store.digest(design),
              "frozen_bundles_digest": store.digest(bundles), "frozen_xg_digest": store.digest(xg_rows),
              "omitted_rows": len(omitted), "omission_reasons": {}, "ranking_allowed": False,
              "code_provenance": code_provenance()}
    for row in omitted:
        report["omission_reasons"][row["reason"]] = report["omission_reasons"].get(row["reason"],0)+1
    write_json(output/"preflight.json", report)
    return report


def load_design(folder):
    folder = Path(folder)
    design, report = load_json(folder/"design.json"), load_json(folder/"preflight.json")
    if store.digest(design) != report["design_digest"]:
        raise ValueError("frozen_design_hash_mismatch")
    return design, report


def fit(folder, *, draws=1500, tune=1500, chains=4, cores=2, seed=20261030):
    import nhl_context_model as model
    folder = Path(folder)
    if (folder/"posterior.nc").exists():
        raise ValueError("posterior_already_exists_choose_new_experiment")
    design, preflight = load_design(folder)
    provenance = code_provenance()
    began = time.perf_counter()
    idata = model.fit(design, draws=draws, tune=tune, chains=chains, cores=cores, seed=seed)
    quality = model.diagnostics(idata)
    idata.to_netcdf(folder/"posterior.nc")
    manifest = {"schema": "nhl-context-fit-v1", "model_version": model.VERSION,
                "market": design["market"], "feature_set": design["feature_set"],
                "source_digest": design["source_digest"], "design_digest": preflight["design_digest"],
                "posterior_sha256": file_hash(folder/"posterior.nc"), "diagnostics": quality,
                "elapsed_seconds": time.perf_counter()-began,
                "sampler": "pymc_cpu_nuts", "pymc_version": __import__("pymc").__version__,
                "draws": draws, "tune": tune, "chains": chains, "cores": cores, "seed": seed,
                "code_provenance": provenance, "ranking_allowed": False, "calibrated": False,
                "status": "research_challenger"}
    write_json(folder/"manifest.json", manifest)
    return manifest


def holdout_rows(examples, *, cutoff, until):
    """Score only outcomes available by the exclusive evaluation endpoint."""
    begin, end = store.instant(cutoff), store.instant(until)
    eligible, unavailable = [], []
    for row in examples:
        if begin <= store.instant(row["start_time"]) < end:
            if store.instant(row["target_available_at"]) < end:
                eligible.append(row)
            else:
                unavailable.append({"game_id": row["game_id"], "player_id": row["player_id"],
                                    "reason": "target_not_available_by_holdout_end"})
    return eligible, unavailable


def evaluate(folder, *, until, line, draws=4000, incumbent_path=None):
    import arviz as az
    import nhl_context_model as model
    import nhl_context_evaluate as scoring
    folder = Path(folder)
    design, preflight = load_design(folder)
    manifest = load_json(folder/"manifest.json")
    if file_hash(folder/"posterior.nc") != manifest["posterior_sha256"]:
        raise ValueError("posterior_hash_mismatch")
    if manifest["design_digest"] != preflight["design_digest"]:
        raise ValueError("manifest_design_mismatch")
    end, cutoff = store.instant(until), store.instant(design["cutoff_exclusive"])
    if not cutoff < end <= datetime.now(timezone.utc):
        raise ValueError("invalid_holdout_window")
    bundles, xg = load_json(folder/"frozen_bundles.json"), load_json(folder/"frozen_xg.json")
    if store.digest(bundles) != preflight["frozen_bundles_digest"] or store.digest(xg) != preflight["frozen_xg_digest"]:
        raise ValueError("frozen_holdout_inputs_mismatch")
    idata = az.from_netcdf(folder/"posterior.nc")
    quality = model.diagnostics(idata)
    if quality.get("posterior_sampling_ok") is not True:
        raise ValueError("holdout_requires_all_effects_convergence")
    cache = model.posterior_cache(idata, design)
    examples, omissions = features.examples(bundles, market=design["market"],
                           policy=design["availability_policy"], feature_set=design["feature_set"], xg_rows=xg)
    training = load_json(folder/"training_rows.json")
    if store.digest(sorted(training,key=lambda r:(r["start_time"],r["game_id"],r["player_id"]))) != design["source_digest"]:
        raise ValueError("frozen_training_rows_hash_mismatch")
    forecasts, controls, excluded = [], [], []
    eligible, unavailable = holdout_rows(examples, cutoff=design["cutoff_exclusive"], until=until)
    for row in eligible:
        try:
            f = model.forecast(idata, design, matchup=row, player_id=row["player_id"],
                               features=row["features"], line=line, draws=draws,
                               diagnostic=quality, cache=cache, observed_value=row["target"],
                               seed=int(store.digest([row["game_id"],row["player_id"]])[:8],16))
        except ValueError as exc:
            excluded.append({"game_id": row["game_id"], "player_id": row["player_id"], "reason": str(exc)})
            continue
        shared = {"game_id": row["game_id"], "player_id": row["player_id"], "market": design["market"],
                  "start_time": row["start_time"], "target": row["target"], "line": line,
                  "training_cutoff_exclusive": design["cutoff_exclusive"]}
        forecasts.append({**f, **shared})
        controls.append({**scoring.baseline(training, player_id=row["player_id"], position=row["position"],
                                           line=line, target=row["target"]), **shared})
    report = {"schema": "nhl-context-holdout-v1", "line_type": "fixed_research_threshold_not_sportsbook",
              "until_exclusive": until, "training_cutoff_exclusive": design["cutoff_exclusive"],
              "eligible_feature_rows": len(eligible), "scored_rows": len(forecasts),
              "excluded_forecasts": excluded, "feature_omissions_total": len(omissions),
              "unavailable_holdout_targets": unavailable,
              "availability_policy": design["availability_policy"], "ranking_allowed": False,
              "transparent_control_comparison": scoring.paired_comparison(forecasts, controls),
              "incumbent_posterior_comparison": None,
              "promotion_evidence_complete": False}
    if incumbent_path:
        incumbent = load_json(incumbent_path)
        report["incumbent_posterior_comparison"] = scoring.paired_comparison(forecasts, incumbent)
    write_json(folder/"holdout_predictions.json", forecasts)
    write_json(folder/"holdout_control.json", controls)
    write_json(folder/"holdout_report.json", report)
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="stage", required=True)
    q = sub.add_parser("plan")
    q.add_argument("--root", type=Path, default=store.ROOT)
    q.add_argument("--train-from", required=True)
    q.add_argument("--until", required=True)
    q.add_argument("--out", type=Path, required=True)
    q = sub.add_parser("freeze")
    q.add_argument("--root", type=Path, default=store.ROOT)
    q.add_argument("--train-from", required=True)
    q.add_argument("--cutoff", required=True)
    q.add_argument("--market", choices=features.MARKETS, default="saves")
    q.add_argument("--feature-set", choices=("base","context","xg"), default="context")
    q.add_argument("--policy", choices=("recorded","retrospective_next_day"), required=True)
    q.add_argument("--out", type=Path, required=True)
    q.add_argument("--min-rows", type=int, default=200)
    q.add_argument("--pilot-games", type=int, default=0)
    q.add_argument("--xg", type=Path)
    q.add_argument("--training-game-ids",type=Path)
    q = sub.add_parser("audit-collection")
    q.add_argument("--root",type=Path,default=store.ROOT)
    q.add_argument("--expected-game-ids",type=Path,required=True)
    q.add_argument("--out",type=Path,required=True)
    q.add_argument("--verify-raw",action="store_true")
    q = sub.add_parser("fit")
    q.add_argument("--folder", type=Path, required=True)
    q.add_argument("--draws", type=int, default=1500)
    q.add_argument("--tune", type=int, default=1500)
    q.add_argument("--chains", type=int, default=4)
    q.add_argument("--cores", type=int, default=2)
    q.add_argument("--seed", type=int, default=20261030)
    q = sub.add_parser("evaluate")
    q.add_argument("--folder", type=Path, required=True)
    q.add_argument("--until", required=True)
    q.add_argument("--line", type=float, required=True)
    q.add_argument("--draws", type=int, default=4000)
    q.add_argument("--incumbent-predictions", type=Path)
    a = p.parse_args(argv)
    if a.stage == "plan":
        result = plan(a.root, train_from=a.train_from, until=a.until, output=a.out)
    elif a.stage == "audit-collection":
        result = audit_collection(a.root,expected_ids=a.expected_game_ids,output=a.out,verify_raw=a.verify_raw)
    elif a.stage == "freeze":
        result = freeze(a.root, train_from=a.train_from, cutoff=a.cutoff, market=a.market,
                        feature_set=a.feature_set, policy=a.policy, output=a.out, min_rows=a.min_rows,
                        pilot_games=a.pilot_games, xg_path=a.xg,training_game_ids_path=a.training_game_ids)
    elif a.stage == "fit":
        result = fit(a.folder, draws=a.draws, tune=a.tune, chains=a.chains, cores=a.cores, seed=a.seed)
    else:
        result = evaluate(a.folder, until=a.until, line=a.line, draws=a.draws, incumbent_path=a.incumbent_predictions)
    print(json.dumps(result, sort_keys=True, allow_nan=False), flush=True)
    failed=(a.stage=="fit" and not result["diagnostics"]["posterior_sampling_ok"] or
            a.stage=="audit-collection" and not result["complete_against_provided_ids"])
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
