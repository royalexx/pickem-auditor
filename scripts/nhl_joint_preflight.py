#!/usr/bin/env python3
"""Zero-leakage NHL heldout source audit and Gamma-Poisson baseline preflight.

Independent of PyMC, sportsbook odds or future exposure. Runs immediately
while an expensive fully Bayesian NUTS evaluation is being fitted.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from collections import Counter,defaultdict
from datetime import date
from pathlib import Path
from statistics import mean

import historical_nhl_warehouse as wh
from joint_nhl_holdout import poisson_control


def summarize(rows):
    if not rows:
        return {"n":0,"brier":None,"log_loss":None,"over_rate":None,"avg_predicted":None}
    return {"n":len(rows),
       "over_rate":mean(y for p,y in rows),
       "avg_predicted":mean(p for p,y in rows),
       "brier":mean((p-y)**2 for p,y in rows),
       "log_loss":mean(-math.log(max(1e-12,p if y else 1-p)) for p,y in rows)}


def preflight(root,cutoff,until):
    date.fromisoformat(cutoff);date.fromisoformat(until)
    if cutoff>=until:raise ValueError("invalid_holdout_date_order")
    train=wh.read_history(root,before=cutoff,min_games=1)
    inclusive_future=wh.read_history(root,before=until,min_games=1)
    holdout=[r for r in inclusive_future if cutoff<=r["game_date"]<until]
    if not holdout:raise ValueError("missing_future_heldout_skater_games")
    players={r["player_id"] for r in train}
    train_keys={(r["game_id"],r["player_id"]) for r in train}
    if any((r["game_id"],r["player_id"]) in train_keys for r in holdout):
        raise ValueError("overlapping_training_and_holdout")
    paired=[];by_position=defaultdict(list);by_date=defaultdict(list)
    excluded=Counter()
    for r in holdout:
        if r["player_id"] not in players:
            excluded["unknown_player"]+=1
            continue
        q=poisson_control(train,player=r["player_id"],position=r["position"])
        y=int(r["shots"]>=3)
        paired.append((q,y))
        by_position[r["position"]].append((q,y))
        by_date[r["game_date"]].append((q,y))
    digest=hashlib.sha256(("".join(wh.encode(r)+"\n" for r in train)).encode()).hexdigest()
    return {"schema":"nhl_bayesian_cohort_preflight_v1",
        "fixed_line":2.5,"sport":"NHL","stat":"shots on goal",
        "season":"2018-19","train_cutoff_exclusive":cutoff,
        "holdout_end_exclusive":until,
        "train_rows":len(train),"train_players":len(players),
        "train_games":len({r["game_id"] for r in train}),
        "train_dates":len({r["game_date"] for r in train}),
        "holdout_rows":len(holdout),"holdout_dates":len({r["game_date"] for r in holdout}),
        "holdout_games":len({r["game_id"] for r in holdout}),
        "holdout_scored":len(paired),
        "holdout_excluded":dict(excluded),
        "source_digest":digest,
        "prior":"per-player Gamma-Poisson shrinkage to own position with five equivalent games",
        "baseline":summarize(paired),
        "position_baselines":{k:summarize(v) for k,v in sorted(by_position.items())},
        "daily_baselines":{k:summarize(v) for k,v in sorted(by_date.items())},
        "historical_sportsbook_line_claim":False,
        "publication_eligible":False,
        "calibrated":False}


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,default=wh.ROOT)
    parser.add_argument("--cutoff",default="2018-10-20")
    parser.add_argument("--until",default="2018-10-28")
    parser.add_argument("--out",type=Path,default=Path("reports/nhl_cohort_preflight.json"))
    args=parser.parse_args(argv)
    result=preflight(args.root,args.cutoff,args.until)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="daily_baselines"},sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
