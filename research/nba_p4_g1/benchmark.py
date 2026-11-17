"""Reproducible, synthetic-only P4 CPU/scenario benchmark.

Usage from repository root:
  OPENBLAS_NUM_THREADS=1 python -m research.nba_p4_g1.benchmark --counts 8 32 64

No official outcomes, collectors, model fitting, or sportsbook contracts loaded.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import json
import os
import resource
import sys
import time
from pathlib import Path

from v2.nba_architecture.v2_contracts import seal, digest
from v2.nba_joint.p4 import simulate_p4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "nba_architecture"))
from test_p4_joint import fixture, PARAMETERS  # noqa: E402


def make_n(n):
    if type(n) is not int or n < 2 or n % 2:
        raise ValueError("EVEN_SCENARIO_COUNT_REQUIRED")
    p, g, o, s = fixture()
    old_g = g["scenarios"]
    old_o = o["scenarios"]
    gs = []
    os = []
    for i in range(n):
        sid = f"synthetic:bench:{i}"
        gg = deepcopy(old_g[i % 2])
        gg["scenario_id"] = sid
        gg["weight"] = 1.0 / n
        # Synthetic alternating team pace states, not inferred basketball data.
        gg["pace_regulation"] = 95.0 if i % 2 else 103.0
        gg["possessions_home"] = 90.0 if i % 2 else 108.0
        gg["possessions_away"] = 106.0 if i % 2 else 91.0
        oo = deepcopy(old_o[i % 2])
        oo["scenario_id"] = sid
        oo["weight"] = 1.0 / n
        gs.append(gg); os.append(oo)
    gd = {k: deepcopy(v) for k, v in g.items() if k != "content_hash"}
    gd["scenarios"] = gs
    new_g = seal(gd)
    od = {k: deepcopy(v) for k, v in o.items() if k != "content_hash"}
    od["game_state_sha256"] = new_g["content_hash"]
    od["scenarios"] = os
    return p, new_g, seal(od), s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--counts", nargs="+", type=int, default=[8, 32, 64])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--output", default="")
    args = ap.parse_args()
    rows = []
    for n in args.counts:
        p, g, o, s = make_n(n)
        for variant in ("J0", "J1", "J2"):
            begin, cpu = time.perf_counter(), time.process_time()
            r = simulate_p4(
                p, g, o, s, variant=variant, seed=args.seed,
                event_parameters=PARAMETERS,
                role_sigma=.10 if variant == "J2" else 0.,
                efficiency_sigma=.08 if variant == "J2" else 0.,
            )
            elapsed = time.perf_counter() - begin
            row = {
                "n": n, "variant": variant, "seconds": elapsed,
                "cpu_seconds": time.process_time() - cpu,
                "scenario_seconds": elapsed / n,
                "player_draws": r["performance"]["n_player_draws"],
                "bundle_sha256": r["bundle"]["content_hash"],
                "input_sha256": digest({
                    "pregame": p["content_hash"],
                    "G": g["content_hash"], "O": o["content_hash"],
                    "S": s["content_hash"]}),
                "five_on_court": all(x["five_on_court"] for x in r["audit_rows"]),
                "peak_rss_linux_kib": resource.getrusage(
                    resource.RUSAGE_SELF).ru_maxrss,
            }
            rows.append(row)
            print(json.dumps(row, sort_keys=True), flush=True)
    receipt = {"purpose": "NBA_P4_SYNTHETIC_ENGINEERING_BENCHMARK",
               "no_predictive_accuracy_claim": True,
               "seed": args.seed,
               "counts": args.counts,
               "runtime": sys.version,
               "numpy": __import__("numpy").__version__,
               "scipy": __import__("scipy").__version__,
               "rows": rows}
    if args.output:
        with open(args.output, "x", encoding="utf-8") as out:
            out.write(json.dumps(receipt, sort_keys=True,
                                 separators=(",", ":")) + "\n")
    print("BENCHMARK_RECEIPT_SHA256", digest(receipt), flush=True)


if __name__ == "__main__":
    main()
