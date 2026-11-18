"""Independently reconcile all raw denominators and replay a scoped witness subset."""
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
import gzip
from hashlib import sha256
import json
from math import log, sqrt
from pathlib import Path
import subprocess
import sys

from witness_oracle import audit_attempt, require, rotation

RENAME = {"two_pa": "fg2a", "two_pm": "fg2m", "three_pa": "fg3a"}
NATIVE_SEEDS = set(range(200000, 200256))


@contextmanager
def decoded(path):
    if path.suffix == ".gz":
        with gzip.open(path, "rb") as handle:
            yield handle
    else:
        with subprocess.Popen(["zstd", "-dc", str(path)], stdout=subprocess.PIPE) as process:
            yield process.stdout
        require(process.returncode == 0, "zstd decode failure")


def shard(path, rows, plans, team_of):
    starts = {sid: rotation(plan, team_of) for sid, plan in plans.items()}
    seeds = set()
    outcomes = defaultdict(Counter)
    points_hist = Counter()
    replayed = 0
    digest = sha256()
    with decoded(path) as lines:
        for number, line in enumerate(lines):
            digest.update(line)
            record = json.loads(line)
            seed = record["seed"]
            require(seed in NATIVE_SEEDS and seed not in seeds, "duplicate or unexpected seed")
            row = rows[seed]
            seeds.add(seed)
            require(len(record["paths"]) == len(row["paths"]) == len(plans), "scenario denominator")
            all_good = True
            for observed, expected in zip(record["paths"], row["paths"], strict=True):
                sid = observed["scenario_id"]
                attempts = observed["attempts"]
                require(sid == expected["scenario_id"] and observed["weight"] == expected["weight"] == .25,
                        "scenario identity or weight changed")
                require(len(attempts) == expected["attempts"], "attempt denominator changed")
                statuses = Counter(attempt["status"] for attempt in attempts)
                accepted = statuses["accepted"]
                require(accepted in (0, 1) and accepted + statuses["score_checkpoint_failure"] == len(attempts),
                        "invalid path status population")
                require(accepted == 1 and attempts[-1]["status"] == "accepted" and len(attempts) <= 128
                        or accepted == 0 and len(attempts) == 128, "stopped early or discarded attempts")
                expected_status = "accepted" if accepted else "exhausted"
                require(observed["status"] == expected["status"] == expected_status, "scenario status alias")
                checkpoints = Counter(str(a["periods"][-1]["period"]) for a in attempts
                                      if a["status"] == "score_checkpoint_failure")
                require(checkpoints == expected["rejected_checkpoints"], "checkpoint denominator mismatch")
                outcomes[sid].update(accepted=accepted, attempts=len(attempts), exhausted=1 - accepted)
                for i, attempt in enumerate(attempts):
                    # All accepted paths and all rejections of one seed per shard.
                    if number and not (accepted and i == len(attempts) - 1):
                        continue
                    players, teams = audit_attempt(plans[sid], attempt, team_of, starts=starts[sid])
                    replayed += 1
                    if attempt["status"] == "accepted":
                        if sid == "synthetic:latest:0":
                            points_hist[players["espn:player:25"]["points"]] += 1
                        for name, actual in (("players", players), ("teams", teams)):
                            require(set(expected["totals"][name]) == set(actual), "box population mismatch")
                            for who, stats in expected["totals"][name].items():
                                require(all(v == actual[who][RENAME.get(k, k)] for k, v in stats.items()),
                                        "reconstructed totals mismatch")
                all_good &= bool(accepted)
            require(record["status"] == row["status"] == (
                "accepted" if all_good else "failed_no_forecast"), "pool disposition mismatch")
            outcomes["ALL"]["complete_seeds"] += all_good
    return seeds, outcomes, points_hist, replayed, digest.hexdigest()


def review(directory):
    directory = Path(directory)
    inputs = json.loads((directory / "inputs.json").read_bytes())
    denominator_file = directory / "denominators.json"
    payload = (denominator_file.read_bytes() if denominator_file.is_file() else
               gzip.decompress((directory / "denominators.json.gz").read_bytes()))
    rows = {row["seed"]: row for row in json.loads(payload)}
    plans = {sc["scenario_id"]: sc["plan"] for sc in inputs["prepared"]["scenarios"]}
    team_of = {p["player_id"]: p["team_id"] for p in inputs["pregame"]["players"]}
    paths = sorted(directory.glob("paths_*.jsonl.zst")) or sorted(directory.glob("paths_*.jsonl.gz"))
    require(len(paths) == 8, "wrong raw shard count")
    require(set(rows) == NATIVE_SEEDS, "declared seed set changed")
    seeds, outcomes, points, checks, hashes = set(), defaultdict(Counter), Counter(), 0, {}
    with ProcessPoolExecutor(max_workers=4) as pool:
        jobs = [pool.submit(shard, path, rows, plans, team_of) for path in paths]
        for path, job in zip(paths, jobs):
            shard_seeds, result, hist, replayed, digest = job.result()
            require(not seeds.intersection(shard_seeds) and len(shard_seeds) == 32, "invalid shard partition")
            seeds.update(shard_seeds)
            points.update(hist)
            for sid, counters in result.items():
                outcomes[sid].update(counters)
            checks += replayed
            hashes[path.name.replace(".gz", "").replace(".zst", "")] = digest
    require(seeds == NATIVE_SEEDS, "incomplete raw study")
    # Independently recover the regulation PTS obstruction to the 0.05 KS limit.
    from scipy.stats import nbinom

    sid = "synthetic:latest:0"
    source = inputs["full_S_reference"]["espn:player:25"]["points"][0]
    require(source["scenario_id"] == sid and sum(points.values()) == 256, "incomplete regulation row")
    observed = 0
    differences = {}
    for k in range(max(points) + 1):
        observed += points[k] / 256
        differences[k] = abs(observed - nbinom.cdf(k, source["shape"], source["success_probability"]))
    threshold = max(differences, key=differences.get)
    slots = sum(len(p["ends"]) for p in plans[sid]["periods"])
    simultaneous_family_size = (len(plans) + 1) * len(team_of) * 8 * (7 * slots + 10)
    halfwidth = sqrt(log(2 * simultaneous_family_size / .05) / (2 * 256))
    return {
        "counts": outcomes,
        "scope": "Raw attempt denominators all seeds; all accepted boxes and one seed's rejections per shard",
        "independent_semantic_path_replays": checks,
        "decoded_sha256_by_shard": hashes,
        "adverse_regulation_result": {
            "player": "espn:player:25", "computed_KS": differences[threshold],
            "at_integer_threshold": threshold, "simultaneous_95_radius": halfwidth,
            "simultaneous_95_KS_lower_bound": differences[threshold] - halfwidth, "limit_KS": 0.05,
        },
    }


if __name__ == "__main__":
    print(json.dumps(review(sys.argv[1]), indent=2, sort_keys=True))
