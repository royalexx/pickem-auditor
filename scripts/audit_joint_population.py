#!/usr/bin/env python3
"""Evidence-based multi-sport joint-model audit, with no production mutation.

coverage: independent market/date exposure and cutoff readiness receipts.
benchmark: truly refit frozen PyMC/NUTS posterior then paired Poisson control
           only when source/time coverage and posterior diagnostics permit.
"""
from __future__ import annotations
import argparse
import json
import math
import os
from collections import Counter
from datetime import date
from pathlib import Path
import population_history as history
import joint_population_bayes as joint
import joint_population_holdout as comparison

ROOT=Path(__file__).resolve().parents[1]
MARKETS={"NHL":("shots on goal","hits","blocked shots","saves"),
         "NBA":("points","assists","rebounds","threes","pra"),
         "NFL":("targets","receptions","receiving yards","passing yards",
                "tackles + assists","carries","passing touchdowns")}

def inspection(root,sport,stat,cutoff,until,max_per_position):
    rows=history.read(root,sport=sport,stat=stat,before=until)
    prior=[r for r in rows if r["game_date"]<cutoff]
    after=[r for r in rows if r["game_date"]>=cutoff]
    sample=joint.training_only_subset(prior,max_per_position=max_per_position)
    allowed={r["player_id"] for r in sample}
    same=[r for r in after if r["player_id"] in allowed]
    return {"sport":sport,"stat":stat,"as_of":cutoff,"until":until,
       "full_market_rows":len(rows),"total_market_players":len({r["player_id"] for r in rows}),
       "training_rows":len(prior),"training_dates":len({r["game_date"] for r in prior}),
       "training_players":len({r["player_id"] for r in prior}),
       "training_subset_rows":len(sample),
       "training_subset_players":len(allowed),
       "holdout_rows":len(after),"holdout_dates":len({r["game_date"] for r in after}),
       "paired_eligible_rows":len(same),"paired_eligible_dates":len({r["game_date"] for r in same}),
       "game_count":len({r["game_id"] for r in rows}),
       "positions":dict(sorted(Counter(r["position"] for r in prior).items())),
       "coverage_status":("fit_ready" if len(sample)>=300 and len(same)>=20 else
                          "insufficient_population_or_holdout"),
       "publication_eligible":False}


def benchmark(root,sport,stat,cutoff,until,line,max_per_position,draws,tune,
              *,folder):
    report=inspection(root,sport,stat,cutoff,until,max_per_position)
    if report["coverage_status"]!="fit_ready":
        raise ValueError("INSUFFICIENT_VALIDATED_POPULATION:"+json.dumps(report))
    rows=history.read(root,sport=sport,stat=stat,before=cutoff,
                      min_records=300)
    prior=joint.training_only_subset(rows,max_per_position=max_per_position)
    data=joint.prepare(prior,min_rows=300)
    idata=joint.fit(data,draws=draws,tune=tune,chains=4,seed=19031)
    d=joint.diagnostics(idata)
    folder.mkdir(parents=True,exist_ok=True)
    folder.joinpath("sampling_diagnostics.json").write_text(
         json.dumps(d,indent=2,sort_keys=True)+"\n")
    if not d.get("posterior_sampling_ok"):
        report.update({"status":"sampling_diagnostics_failed","sampling":d})
        folder.joinpath("audit_receipt.json").write_text(json.dumps(report,indent=2)+"\n")
        print(json.dumps(report,sort_keys=True))
        return 2
    future=history.read(root,sport=sport,stat=stat,after=cutoff,before=until)
    scored=comparison.compare(idata,prior,data,future,cutoff=cutoff,until=until,
                        line=line,checks=d,draws=1200)
    report.update({"status":"holdout_completed",
                   "joint_brier":scored["joint"]["brier"],
                   "poisson_control_brier":scored["control"]["brier"],
                   "joint_log_loss":scored["joint"]["log_loss"],
                   "poisson_control_log_loss":scored["control"]["log_loss"],
                   "joint_minus_poisson":scored["joint_minus_control"],
                   "paired":scored["scored_same_cohort_games"],
                   "bootstrap":scored["paired_date_cluster"],
                   "comparison_result":scored["comparative_result"],
                   "sampling":d})
    folder.joinpath("audit_receipt.json").write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    folder.joinpath("full_holdout.json").write_text(json.dumps(scored,sort_keys=True,indent=2)+"\n")
    print("VERIFIED_PAIRED_POISSON_COMPARISON "+json.dumps(report,sort_keys=True))
    return 0


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,default=ROOT)
    p.add_argument("--sport",choices=history.SPORTS,required=True)
    p.add_argument("--stat",required=True)
    p.add_argument("--cutoff",required=True)
    p.add_argument("--until",required=True)
    p.add_argument("--max-per-position",type=int,default=0)
    p.add_argument("--line",type=float)
    p.add_argument("--draws",type=int,default=1000)
    p.add_argument("--tune",type=int,default=1100)
    p.add_argument("--out",type=Path,default=Path("reports/multisport_audit"))
    a=p.parse_args()
    date.fromisoformat(a.cutoff);date.fromisoformat(a.until)
    if a.cutoff>=a.until: p.error("invalid_window")
    if a.line is None:
        print(json.dumps(inspection(a.root,a.sport,a.stat,a.cutoff,a.until,a.max_per_position),
                         sort_keys=True))
        return 0
    if not math.isfinite(a.line) or float(a.line).is_integer():
        p.error("binary historical reference line must avoid exact-count pushes")
    return benchmark(a.root,a.sport,a.stat,a.cutoff,a.until,a.line,
                     a.max_per_position,a.draws,a.tune,folder=a.out)

if __name__=="__main__":
    raise SystemExit(main())
