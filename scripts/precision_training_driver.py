#!/usr/bin/env python3
"""Cross-platform (Windows/Unix) stages for audited, local-only joint Bayesian fitting.

This is invoked by a manual-only GitHub self-hosted workflow. No betting
ranking, forecast deployment, source backfill, or cloud data mutation occurs.
"""
from __future__ import annotations
import argparse
import json
import math
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def settings(env=None) -> dict:
    env = os.environ if env is None else env
    from population_history import family
    sport = env["SPORT"]
    stat = env["STAT"]
    mode = env["MODE"]
    family_name = family(sport, stat)
    if mode not in ("holdout", "pregame_fit"):
        raise ValueError("invalid_precision_training_mode")
    begin = date.fromisoformat(env["TRAIN_FROM"])
    cutoff = date.fromisoformat(env["CUTOFF"])
    if not begin < cutoff <= date.today():
        raise ValueError("invalid_or_future_training_dates")
    cohort = int(env["MAX_PER_POSITION"])
    max_seasons = int(env.get("MAX_SEASONS", "4"))
    if not 1 <= max_seasons <= 30:
        raise ValueError("invalid_training_season_limit")
    if not 0 <= cohort <= 10000:
        raise ValueError("invalid_training_only_population_limit")
    until = env["HOLDOUT_UNTIL"]
    line = float(env["LINE"])
    if not math.isfinite(line):
        raise ValueError("invalid_research_line")
    if mode == "holdout":
        ending = date.fromisoformat(until)
        if not cutoff < ending <= date.today():
            raise ValueError("invalid_holdout_date_or_current_game_leakage")
        if line.is_integer() or (family_name == "count" and line < 0):
            raise ValueError("research_line_must_be_valid_noninteger_threshold")
    return {"sport": sport, "stat": stat, "mode": mode, "train_from": begin.isoformat(),
            "cutoff": cutoff.isoformat(), "until": until, "line": line,
            "max_per_position": cohort, "max_seasons": max_seasons,
            "family": family_name}


def run(*args: str, root: Path = ROOT) -> None:
    command = [sys.executable, *args]
    print("RESEARCH_STAGE=" + repr(command), flush=True)
    subprocess.run(command, cwd=root, check=True)


def execute(stage: str, *, root: Path = ROOT, env=None) -> dict:
    root = root.resolve()
    conf = settings(env)
    run_id = (os.environ if env is None else env).get("GITHUB_RUN_ID", "manual")
    fit_id = (os.environ if env is None else env).get("FIT_ID", "").strip()
    if fit_id and (not fit_id.replace("-", "").replace("_", "").isalnum() or len(fit_id) > 90):
        raise ValueError("unsafe_training_fit_id")
    target = root / "reports" / "precision_training" / run_id
    if fit_id:
        target = target / fit_id
    target.mkdir(parents=True, exist_ok=True)
    base = ["--sport", conf["sport"], "--stat", conf["stat"],
            "--train-from", conf["train_from"]]
    if stage == "validate":
        if conf["mode"] == "holdout":
            run("scripts/population_window_check.py", *base, "--as-of", conf["cutoff"],
                "--until", conf["until"], "--max-seasons", str(conf["max_seasons"]),
                "--min-training-seasons", "2", "--min-rows", "2000",
                "--report", str(target / "window_preflight.json"), root=root)
        else:
            from population_history import read
            rows = read(root, sport=conf["sport"], stat=conf["stat"],
                        before=conf["cutoff"], after=conf["train_from"],
                        max_seasons=conf["max_seasons"], min_records=2000)
            if len({r["season"] for r in rows}) < 2:
                raise ValueError("pregame_fit_requires_two_training_seasons")
            print("PREGAME_SOURCE_VALIDATED "+json.dumps(
                {"sport": conf["sport"], "stat": conf["stat"],
                 "rows": len(rows), "seasons": len({r["season"] for r in rows})}),
                flush=True)
    elif stage == "fit":
        runtime_env = os.environ if env is None else env
        cores = int(runtime_env.get("PICKEM_NUTS_CORES", "2"))
        draws = int(runtime_env.get("PICKEM_NUTS_DRAWS", "1000"))
        tune = int(runtime_env.get("PICKEM_NUTS_TUNE", "1200"))
        chains = int(runtime_env.get("PICKEM_NUTS_CHAINS", "4"))
        if not 1 <= cores <= chains <= 8 or not 100 <= draws <= 10000 or not 100 <= tune <= 10000:
            raise ValueError("unsafe_sampling_parallelism_or_budget")
        command=["scripts/joint_population_bayes.py", *base, "--as-of", conf["cutoff"],
            "--max-seasons", str(conf["max_seasons"]), "--min-rows", "2000",
            "--max-per-position", str(conf["max_per_position"]),
            "--draws", str(draws), "--tune", str(tune), "--chains", str(chains),
            "--cores", str(cores), "--progress-file", str(target / "progress.json"),
            "--progress-interval", "45",
            "--out", str(target)]
        if runtime_env.get("PICKEM_STRICT_ALL_EFFECTS")=="1":
            command.append("--strict-all-effects")
        run(*command,root=root)
    elif stage == "holdout":
        if conf["mode"] != "holdout":
            raise ValueError("holdout_stage_requested_for_pregame_fit")
        run("scripts/joint_population_holdout.py", *base,
            "--cutoff", conf["cutoff"], "--until", conf["until"],
            "--line", str(conf["line"]), "--max-seasons", str(conf["max_seasons"]),
            "--draws", "1500", "--training-dir", str(target), root=root)
    else:
        raise ValueError("unknown_training_stage_" + stage)
    return {"stage": stage, "run_id": run_id, **conf}


def provenance(*, root: Path = ROOT, env=None) -> dict:
    env = os.environ if env is None else env
    root = root.resolve()
    run_id = env.get("GITHUB_RUN_ID", "manual")
    fit_id = env.get("FIT_ID", "").strip()
    if fit_id and (not fit_id.replace("-", "").replace("_", "").isalnum() or len(fit_id) > 90):
        raise ValueError("unsafe_training_fit_id")
    dest = root / "reports" / "precision_training" / run_id
    if fit_id:
        dest = dest / fit_id
    dest.mkdir(parents=True, exist_ok=True)
    try:
        sha = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                             text=True, check=True, capture_output=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        sha = None
    payload = {"schema": "precision_native_windows_cloud_provenance_v1",
               "code_sha": sha, "source_commit": env.get("SOURCE_HEAD"),
               "github_run_id": run_id,
               "fit_id": fit_id or None,
               "runner_execution": "windows_native_self_hosted",
               "validation_stage": env.get("VALIDATE_RESULT"),
               "fit_stage": env.get("FIT_RESULT"),
               "sampler": "pymc_cpu_nuts",
               "sampler_chains": env.get("PICKEM_NUTS_CHAINS", "4"),
               "sampler_parallel_chains": env.get("PICKEM_NUTS_CORES", "2"),
               "sampler_draws": env.get("PICKEM_NUTS_DRAWS", "1000"),
               "sampler_tune": env.get("PICKEM_NUTS_TUNE", "1200"),
               "strict_all_effects": env.get("PICKEM_STRICT_ALL_EFFECTS")=="1",
               "inputs": {name.lower(): env.get(name) for name in
                          ("SPORT","STAT","MODE","TRAIN_FROM","CUTOFF",
                           "HOLDOUT_UNTIL","LINE","MAX_PER_POSITION","MAX_SEASONS")},
               "ranking_allowed": False, "calibrated": False,
               "publication_eligible": False}
    (dest/"cloud_provenance.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True), flush=True)
    return payload


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage", choices=("validate","fit","holdout","provenance"))
    p.add_argument("--root", type=Path, default=ROOT)
    a = p.parse_args(argv)
    if a.stage == "provenance":
        provenance(root=a.root)
    else:
        print(json.dumps(execute(a.stage,root=a.root), sort_keys=True),flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
