#!/usr/bin/env python3
"""Research-only, paired NHL sampler benchmark; never changes production models.

Every backend sees the same immutable historical cohort, cutoff, priors, seed,
chain count, tune and draw budget. The benchmark reports diagnostics even when
the pilot is too short for the strict production ESS threshold. A backend is
NEVER approved by timing alone.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Must be set before importing JAX.
os.environ.setdefault("JAX_PLATFORMS", "cpu")
os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import joint_population_bayes as joint
import population_history as history

BACKENDS = ("pymc", "nutpie", "numpyro")
MARKETS = ("hits", "shots on goal", "blocked shots", "saves")


def validate_options(opts):
    if opts.sampler not in BACKENDS or opts.stat not in MARKETS:
        raise ValueError("unsupported_nhl_benchmark")
    if not (12 <= opts.max_per_position <= 500):
        raise ValueError("benchmark_requires_bounded_population")
    if opts.draws < 100 or opts.tune < 100 or opts.chains < 2 or opts.cores < 1 or opts.cores > opts.chains:
        raise ValueError("invalid_sampler_benchmark_budget")
    from datetime import date
    if not ("2018-10-01" < opts.as_of <= date.today().isoformat()):
        raise ValueError("invalid_training_cutoff")


def select_data(opts):
    def show_progress(event):
        if event["event"]=="shard_start":
            print(f"HISTORY_LOAD starting {event['shard']}", flush=True)
        elif event["event"]=="shard_progress":
            print(f"HISTORY_LOAD {event['shard']} validated {event['validated_rows']} rows", flush=True)
        elif event["event"]=="shard_done":
            print(f"HISTORY_LOAD finished {event['shard']}: "
                  f"{event['validated_rows']} validated, {event['selected_rows']} eligible "
                  f"in {event['seconds']}s", flush=True)
    print("HISTORY_LOAD starting verified NHL history; sampling has NOT started",
          flush=True)
    rows = history.read(ROOT, sport="NHL", stat=opts.stat,
                        before=opts.as_of, after="2018-10-01",
                        max_seasons=12, min_records=2000,
                        progress=show_progress)
    print(f"HISTORY_LOAD complete: {len(rows)} eligible rows; selecting cohort",
          flush=True)
    cohort = joint.training_only_subset(rows, max_per_position=opts.max_per_position)
    data = joint.prepare(cohort, min_rows=300)
    print(f"HISTORY_LOAD model input ready: {data['rows']} rows / "
          f"{len(data['players'])} players", flush=True)
    return data


def sample(data, opts):
    import pymc as pm
    kwargs = dict(draws=opts.draws, tune=opts.tune, chains=opts.chains,
                  cores=opts.cores, random_seed=19031,
                  nuts_sampler=opts.sampler,
                  progressbar=False, compute_convergence_checks=False,
                  return_inferencedata=True, nuts={"target_accept":opts.target_accept})
    if opts.sampler == "numpyro":
        # Explicitly refuse CUDA even if a hosted machine happens to expose it.
        import jax
        if any(device.platform != "cpu" for device in jax.devices()):
            raise RuntimeError("GPU_NOT_ALLOWED_IN_CPU_BENCHMARK")
    with joint.build(data):
        return pm.sample(**kwargs)


def execute(opts):
    validate_options(opts)
    target = Path(opts.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": "nhl_sampler_research_benchmark_v1",
        "sport": "NHL", "stat": opts.stat, "backend": opts.sampler,
        "as_of_exclusive": opts.as_of, "max_per_position": opts.max_per_position,
        "draws_per_chain": opts.draws, "tune_per_chain": opts.tune,
        "chains": opts.chains, "cores": opts.cores,
        "target_accept": opts.target_accept, "seed": 19031,
        "production_use": False, "publication_eligible": False,
        "backend_approved": False, "pilot_diagnostics_pass": False, "host": platform.platform(),
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "status": "failed",
    }
    try:
        begin = time.perf_counter()
        data = select_data(opts)
        report.update(source_digest=data["source_digest"], training_rows=data["rows"],
                      players=len(data["players"]), seasons=len(data["seasons"]),
                      opponents=len(data["opponents"]), positions=len(data["positions"]))
        build_seconds = time.perf_counter() - begin
        import pymc as pm
        report["pymc_version"] = pm.__version__
        fit_start = time.perf_counter()
        result = sample(data, opts)
        elapsed = time.perf_counter() - fit_start
        report["source_and_cohort_seconds"] = round(build_seconds, 3)
        report["compile_and_sampling_seconds"] = round(elapsed, 3)
        report["total_seconds"] = round(time.perf_counter() - begin, 3)
        report["diagnostics"] = joint.diagnostics(result, all_effects=True)
        diag = report["diagnostics"]
        report["minimum_bulk_ess_per_second"] = (
            round(diag["min_bulk_ess"] / elapsed, 6)
            if elapsed > 0 and diag.get("min_bulk_ess") is not None else None
        )
        report["status"] = "completed"
        # A pilot may not meet stringent ESS>=400 even with correct sampling;
        # do not mistake a completed benchmark for a converged production fit.
        report["pilot_diagnostics_pass"] = bool(diag.get("posterior_sampling_ok"))
        report["backend_approved"] = False  # Pilot never qualifies production
        report["production_use"] = False
        return 0
    except KeyboardInterrupt:
        report["status"] = "interrupted"
        report["error"] = ("KeyboardInterrupt: the process was stopped during "
                           "history loading or sampling; no benchmark speedup was measured")
        report["traceback"] = traceback.format_exc()[-6000:]
        return 130
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"[:600]
        report["traceback"] = traceback.format_exc()[-6000:]
        return 2
    finally:
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        temp = target.with_suffix(target.suffix + ".tmp")
        temp.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        temp.replace(target)
        print("NHL_BENCHMARK_RESULT " + json.dumps({k: report.get(k) for k in
              ("backend", "stat", "status", "training_rows", "players", "total_seconds",
               "minimum_bulk_ess_per_second", "pilot_diagnostics_pass", "backend_approved", "error")}, sort_keys=True),
              flush=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sampler", choices=BACKENDS, required=True)
    p.add_argument("--stat", choices=MARKETS, default="hits")
    p.add_argument("--as-of", default="2026-10-29")
    p.add_argument("--max-per-position", type=int, default=12)
    p.add_argument("--draws", type=int, default=400)
    p.add_argument("--tune", type=int, default=400)
    p.add_argument("--chains", type=int, default=4)
    p.add_argument("--cores", type=int, default=2)
    p.add_argument("--target-accept", type=float, default=0.99)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    if not 0.7 <= args.target_accept <= 0.999:
        p.error("target_accept must be between 0.7 and 0.999")
    return execute(args)


if __name__ == "__main__":
    raise SystemExit(main())
