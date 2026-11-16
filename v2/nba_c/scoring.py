"""Independent after-event scorer for accepted G0 v2.0.0 envelopes.

Pregame forecast ingestion never takes an outcome; this separate function
accepts an official evaluation only after G0 settlement validation.
"""
from __future__ import annotations
import hashlib
from v2.nba_architecture.v2_contracts import (
    validate_distribution, validate_evaluation, validate_scenarios, verify,
)
from .scores import diagnostics, energy_score, variogram_score, ScoreError


def score_official(distribution, pregame, evaluation, *,
                   scenarios=None, offer_view=None, previous=None,
                   central=.90, tail_threshold=30):
    validate_distribution(distribution,pregame,scenarios)
    validate_evaluation(evaluation,distribution,offer_view,previous)
    if evaluation["status"] not in ("settled","push"):
        return {"status":evaluation["status"],"scored":False,
                "distribution_sha256":distribution["content_hash"],
                "evaluation_sha256":evaluation["content_hash"],
                "reason":"NO_OFFICIAL_COUNT"}
    if evaluation["participation"] not in ("PLAYED","PLAYED_ZERO_MINUTES"):
        raise ScoreError("NO_PLAYED_OFFICIAL_OUTCOME")
    # No random-seed dependence on iteration order, platform or Python hash().
    src=(distribution["content_hash"]+"|"+evaluation["content_hash"]).encode()
    seed=int.from_bytes(hashlib.sha256(src).digest()[:8],"big")
    report=diagnostics(distribution["pmf"],evaluation["actual"],seed=seed,
                       central=central,tail_threshold=tail_threshold)
    report.update(status=evaluation["status"],scored=True,
                  distribution_sha256=distribution["content_hash"],
                  evaluation_sha256=evaluation["content_hash"],
                  game_id=distribution["game_id"],
                  stat=distribution["stat"],
                  source_profile=distribution["source_profile"],
                  original_pregame_certified=False)
    return report


def joint_score_official(scenarios, pregame, official_evaluations, distributions,
                         *, components, max_pair_terms=8192, seed=20261116):
    """components: ordered sequence of (player_id, stat) from SAME scenarios.

    Each official evaluation and its corresponding marginal must validate.
    No synthetic independent-player coupling or S/O/J pseudo-votes.
    """
    validate_scenarios(scenarios,pregame)
    if len(components)<2 or len(set(components))!=len(components):
        raise ScoreError("INVALID_JOINT_COMPONENTS")
    actual=[]
    for pid,stat in components:
        key=(pid,stat)
        if key not in distributions or key not in official_evaluations:
            raise ScoreError("MISSING_MATCHED_JOINT_EVIDENCE")
        d=distributions[key]
        ev=official_evaluations[key]
        if d["pipeline_mode"]!="S_O_J" or d["player_id"]!=pid or d["stat"]!=stat:
            raise ScoreError("JOINT_DISTRIBUTION_IDENTITY")
        validate_distribution(d,pregame,scenarios)
        validate_evaluation(ev,d)
        if ev["status"]!="settled" or ev["participation"] not in ("PLAYED","PLAYED_ZERO_MINUTES"):
            raise ScoreError("JOINT_OFFICIAL_OUTCOME_NOT_SETTLED")
        actual.append(ev["actual"])
    paths=[]
    for sc in scenarios["scenarios"]:
        by_player={p["player_id"]:p["stats"] for p in sc["players"]}
        paths.append((tuple(by_player[pid][stat] for pid,stat in components),
                      sc["weight"]))
    return {"energy":energy_score(paths,actual,max_pair_terms=max_pair_terms,seed=seed),
            "variogram_0_5":variogram_score(paths,actual,power=.5),
            "n_official_games":1,"scenario_paths_are_not_games":len(paths),
            "source_profile":pregame["source_profile"],
            "components":list(components)}
