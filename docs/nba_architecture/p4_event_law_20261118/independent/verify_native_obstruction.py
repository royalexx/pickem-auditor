"""Re-execute the registry-pinned P2/P3 fixture and verify the archived tail inputs."""
import json
import math

from reproduce_obstruction import PLAYER, SCENARIO, reproduce
from research.nba_p4_latest.fixture import build
from v2.nba_joint.latest_upstream import load_upstream, prepare, registry


def verify():
    upstream = prepare()
    p, g, o, sidecar, artifacts, _, roles = build(upstream)
    p2, p3 = load_upstream(upstream)
    p3.validate_sidecar(sidecar, p, g, o)
    scenario, = (row for row in o["scenarios"] if row["scenario_id"] == SCENARIO)
    player, = (row for row in scenario["players"] if row["player_id"] == PLAYER)
    minutes = player["minutes"]
    archive = reproduce()
    live = {}
    for stat, evidence in archive["statistics"].items():
        prediction = p2.predict_conditional(
            artifacts[stat], player_id=PLAYER, role=roles[PLAYER],
            projected_exposure=minutes, statistic=stat,
        )
        if prediction.abstain_reason is not None or artifacts[stat].data["family"] != "S1":
            raise ValueError("Expected native S1 conditional law")
        params = prediction.parameters
        prob = params["beta"] / (params["beta"] + minutes)
        if (params["alpha"] != evidence["shape"]
            or prob != float(evidence["success_probability"])
            or params["tail_mass_upper_bound"] != float(evidence["reference_serialization_tail_bound"])):
            raise ValueError("Live reference differs from frozen reference")
        tail = math.fsum(row["mass"] for row in params["support"] if row["value"] >= evidence["threshold"])
        live[stat] = {
            "alpha": params["alpha"], "beta": params["beta"], "NB_success_probability": prob,
            "serialized_count_tail": tail,
            "omitted_count_tail_upper_bound": params["tail_mass_upper_bound"],
            "artifact_sha256": artifacts[stat].artifact_sha256,
        }
    if live["threes"]["serialized_count_tail"] <= (
        live["points"]["serialized_count_tail"] + live["points"]["omitted_count_tail_upper_bound"]
        + live["threes"]["omitted_count_tail_upper_bound"]
    ):
        raise ValueError("Even conservative serialization allowance should preserve the reversal")
    return {
        "player_id": PLAYER, "scenario_id": SCENARIO, "minutes": minutes,
        "participation": player["participation"], "scenario_weight": scenario["weight"],
        "pregame_content_hash": p["content_hash"], "G_content_hash": g["content_hash"],
        "O_content_hash": o["content_hash"], "P3_sidecar_content_hash": sidecar["content_hash"],
        "owner_commits": {key: owner["commit"] for key, owner in registry()["owners"].items()},
        "live": live,
        "disposition": "Reversal reproduced directly from native P2 S1 conditional kernel",
    }


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2, sort_keys=True))
