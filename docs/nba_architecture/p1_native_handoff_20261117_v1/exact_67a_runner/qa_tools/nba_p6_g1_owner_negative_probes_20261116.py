"""Independent P6 owner-specific *negative probes*, research-only.

Run on immutable temporary checkout of the corresponding owner branch:
    python /path/to/nba_p6_g1_owner_probes_20261116.py P1|P2|P5

This file must NOT be copied into production and must not modify any owner
implementation. A nonzero exit code means the deliberately adversarial case
revealed a gap. The cases are synthetic; no actual holdout data are accessed.
"""
from __future__ import annotations
import json, math, sys, tempfile

def result(family, name, status, **fields):
    return {"family":family,"case":name,"status":status,**fields}

def p1():
    from tests.nba_architecture.test_p1_history import make_entry, build
    from v2.nba_architecture.p1_vault import OfficialOutcomeVault
    evidence=[]
    ordinary=build([make_entry(minutes=26)])
    assert ordinary["certification"]=="HISTORICAL_RECONSTRUCTION_UNCERTIFIED"
    for case,minutes in [("zero_minutes_positive_box",0),
                         ("900_minutes_without_game_duration",900)]:
        try:
            snapshot=build([make_entry(minutes=minutes,
                stats={"points":11,"rebounds":5,"assists":3,"threes":2})])
            vals=[x for x in snapshot["features"] if x["name"].endswith(":minutes")]
            evidence.append(result("P1",case,"ACCEPTED_SUSPECT_INPUT",
                raw_minutes=minutes,retained_minutes=vals[0]["value"],
                certification=snapshot["certification"]))
        except Exception as exc:
            evidence.append(result("P1",case,"REJECTED",code=str(exc)))
    try:
        with tempfile.TemporaryDirectory() as path:
            vault=OfficialOutcomeVault(path)
            record=vault.append(game_id="nba:game",player_id="nba:player",
                team_id="nba:team",state="PLAYED_ZERO_MINUTES",minutes=0,
                stats={"points":11},source_id="official:synthetic",
                source_bytes=b"synthetic offline official result",
                observed_at="2026-11-16T22:00:00Z",official_status="FINAL")
            evidence.append(result("P1","zero_minute_positive_official_vault",
                "ACCEPTED_SUSPECT_INPUT",snapshot_sha256=record["content_hash"]))
    except Exception as exc:
        evidence.append(result("P1","zero_minute_positive_official_vault",
                               "REJECTED",code=str(exc)))
    return evidence

def p2():
    from tests.nba_s_family.test_statistical import histories,manifest,CUTOFF
    from v2.nba_s_family.model import fit
    good=fit(histories("points"),asof_cutoff_utc=CUTOFF,
             source_manifest=manifest(),stat="points",family="S1")
    assert good.artifact_sha256
    rows=histories("points")
    rows[0]["minutes"]=56.0
    try:
        fit(rows,asof_cutoff_utc=CUTOFF,source_manifest=manifest(),
            stat="points",family="S1")
        return [result("P2","56_minute_two_OT_training_exposure","ACCEPTED")]
    except Exception as exc:
        return [result("P2","56_minute_two_OT_training_exposure",
                       "REJECTED_POTENTIALLY_VALID_MULTI_OT",code=str(exc),
                       limitation="Historical fit schema lacks official OT count")]

def p5():
    from tests.nba_c.test_p5_c_family import fixture
    from v2.nba_c.experiment import CachedCohort, make_walk_forward_folds
    from v2.nba_c import scores
    evidence=[]
    for case,date in [("proper_2023_24_date","2023-11-20T00:00:00Z"),
                      ("backdated_2022_date_with_2023_24_game","2022-10-20T00:00:00Z")]:
        row=fixture(date="2022-10-20T00:00:00Z",game="nba:synthetic:holdout")
        row.update(date=date,frozen_at="2023-11-20T17:00:00Z",
            event_start_at="2023-11-20T23:00:00Z",
            official_available_at="2023-11-21T00:00:00Z")
        try:
            c=CachedCohort([row],authorization="SYNTHETIC_UNIT_TEST")
            status="ACCEPTED_HOLDOUT_GUARD_BYPASS" if case.startswith("backdated") else "ACCEPTED"
            evidence.append(result("P5",case,status,game_count=c.game_count))
        except Exception as exc:
            evidence.append(result("P5",case,"REJECTED",code=str(exc)))
        try:
            make_walk_forward_folds([row],min_train_dates=1)
            fold="ACCEPTED"
        except Exception as exc:
            fold="REJECTED:"+str(exc)
        evidence[-1]["chronological_fold_check"]=fold
    pois={k:math.exp(-1-math.lgamma(k+1)) for k in range(30)}
    nb={k:(k+1)/2**(k+2) for k in range(120)}
    exact=[scores.crps(pois,0),scores.crps(nb,0),
           scores.energy_score([((0,0),.5),((2,2),.5)],(0,2)),
           scores.variogram_score([((0,0),.5),((2,2),.5)],(0,2))]
    targets=[.47622238819739127,26/27,2-math.sqrt(2)/2,2]
    if not all(abs(a-b)<1e-11 for a,b in zip(exact,targets)):
        evidence.append(result("P5","independent_math_oracles",
                               "NUMERICAL_MISMATCH",actual=exact,expected=targets))
    else:
        evidence.append(result("P5","independent_math_oracles",
                               "PASS",values=exact))
    return evidence

if __name__=="__main__":
    if len(sys.argv)!=2 or sys.argv[1] not in {"P1","P2","P5"}:
        raise SystemExit("Specify exactly one of P1 P2 P5")
    family=sys.argv[1]
    evidence={"P1":p1,"P2":p2,"P5":p5}[family]()
    print(json.dumps({"suite":"nba-p6-g1-owner-negative-20261116",
                      "family":family,"cases":evidence},sort_keys=True))
    # Exit nonzero only for confirmed fail-open; P2's missing OT metadata is
    # a coverage limitation rather than proven unsafe data acceptance.
    red=any(x["status"] in ("ACCEPTED_SUSPECT_INPUT",
                            "ACCEPTED_HOLDOUT_GUARD_BYPASS",
                            "NUMERICAL_MISMATCH") for x in evidence)
    raise SystemExit(2 if red else 0)
