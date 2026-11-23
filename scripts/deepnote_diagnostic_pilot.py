"""Run the three deterministic synthetic Deepnote diagnostic fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import traceback
from pathlib import Path

if __package__:
    from .deepnote_diagnostic_report import publish_report
else:
    from deepnote_diagnostic_report import publish_report


def _encode(data):
    return (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _save(path, data):
    content = _encode(data)
    with path.open("xb") as stream:
        stream.write(content)
    return hashlib.sha256(content).hexdigest()


def run_fixture(case, git_sha, output_dir, run_id, notebook_id, deepnote_run_id=None):
    """Store fixtures and report. The deliberately failed case re-raises its real error."""
    sport, market = {"normal": ("NBA", "points"), "failure": ("NHL", "shots_on_goal"),
                     "drift": ("NFL", "receptions")}[case]
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    # Sixty synthetic games, one observation per independent game, no authentic offers.
    # The simulated away stratum alone receives the injected forecast perturbation.
    observations = [{"game": f"synthetic-game-{i:02d}", "stratum": "away" if i % 2 else "home",
                     "outcome": int(i != 7 if i % 2 else i % 5 != 0), "forecast_at": "2026-01-01T00:00:00Z",
                     "event_start_at": "2026-01-02T00:00:00Z"} for i in range(60)]
    predictions = []
    scores = []
    for row in observations:
        baseline = 0.75
        probability = baseline - 0.035 if case == "drift" and row["stratum"] == "away" else baseline
        predictions.append({"id": row["game"], "over": probability,
                            "under": 1 - probability, "push": 0.0})
        outcome = row["outcome"]
        base_loss = (baseline - outcome) ** 2
        loss = (probability - outcome) ** 2
        scores.append({"game": row["game"], "stratum": row["stratum"], "reference": base_loss,
                       "candidate": loss, "delta": loss - base_loss})
    if case == "failure":
        predictions[7].update(over=1.02, under=-0.02)

    source = root / "synthetic-input.json"
    output = root / "synthetic-output.json"
    input_sha = _save(source, observations)
    output_sha = _save(output, predictions)
    delta = statistics.mean(item["delta"] for item in scores)
    halfwidth = 1.96 * statistics.stdev(item["delta"] for item in scores) / math.sqrt(len(scores))
    report = {
        "run_id": run_id, "deepnote_run_id": deepnote_run_id, "notebook_id": notebook_id,
        "git_sha": git_sha, "model": "synthetic-reference-perturbation", "model_version": "1",
        "status": "success", "sport": sport, "market": market,
        "tests": {"passed": 2, "failed": 0, "skipped": 0},
        "counts": {"total": 60, "eligible": 60, "missing": 0, "rejected": 0,
                   "unmatched": 0, "abstained": 0},
        "provenance": {"input_uri": f"artifact-{input_sha}", "input_sha256": input_sha,
                       "output_uri": f"artifact-{output_sha}", "output_sha256": output_sha,
                       "cohort": "synthetic", "input_freeze_at": "2026-01-01T00:00:00Z"},
        "metrics": {"brier": statistics.mean(item["candidate"] for item in scores)},
        "gates": {"synthetic_fixture": "passed", "probability_bounds": "passed",
                  "production_release": "not_applicable"},
        "comparisons": {"paired_brier": {"baseline_id": "synthetic-constant-0.75",
                                        "delta": delta, "ci_low": delta - halfwidth,
                                        "ci_high": delta + halfwidth}},
        "distribution_diagnostics": {"forecast_rows": len(predictions), "push_mass_max": 0},
        "constraint_diagnostics": {"mass_tolerance": 1e-12},
        "parameters": {"paired_unit": "synthetic_game", "confidence_method": "normal_95_percent"},
        "issues": [],
        "probabilities": predictions,
        "samples": [predictions[7]] if case == "failure" else [],
        "paired_scores": scores,
        "full_predictive_distributions": predictions,
        "independent_validation": {"status": "not_applicable", "reason": "transport fixture"},
        "synthetic_execution_log": [
            f"{row['game']}: fixture row retained with paired baseline score and event chronology"
            for row in observations for _ in range(3)
        ],
    }
    artifacts = {"source_observations": source, "predictions": output}
    try:
        if not all(0 <= row["over"] <= 1 and 0 <= row["under"] <= 1 for row in predictions):
            raise AssertionError("Synthetic validation fixture: invalid probability in game 07")
    except AssertionError as error:
        report.update(status="error", tests={"passed": 1, "failed": 1, "skipped": 0})
        report["gates"]["probability_bounds"] = "failed"
        report["metrics"]["brier"] = None
        report["comparisons"] = {}
        report["paired_scores"] = []
        report["issues"].append({"code": "FIXTURE_PROBABILITY_BOUNDS", "severity": "error",
                                 "stage": "probability_validation", "test": "probability_bounds",
                                 "message": str(error), "traceback": traceback.format_exc()})
        publish_report(report, root, artifacts=artifacts)
        raise
    return publish_report(report, root, artifacts=artifacts)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("case", choices=("normal", "failure", "drift"))
    cli.add_argument("--git-sha", required=True)
    cli.add_argument("--output-dir", required=True)
    cli.add_argument("--run-id", required=True)
    cli.add_argument("--notebook-id", required=True)
    cli.add_argument("--deepnote-run-id")
    args = cli.parse_args()
    run_fixture(args.case, args.git_sha, args.output_dir, args.run_id, args.notebook_id,
                args.deepnote_run_id)
