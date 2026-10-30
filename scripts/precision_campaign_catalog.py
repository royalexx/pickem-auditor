#!/usr/bin/env python3
"""Deterministic sequential research-only full-population PyMC market schedule."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from population_history import COUNT, CONTINUOUS, family, slug

START = {"NHL": "2018-10-01", "NBA": "2023-10-01", "NFL": "2018-09-01"}
MARKETS = tuple(
    (sport, stat, START[sport])
    for sport in ("NHL", "NBA", "NFL")
    for stat in (*COUNT[sport], *CONTINUOUS.get(sport, ()))
)

def catalog_check() -> None:
    assert len(MARKETS) == 31, "unexpected_historical_market_count"
    identities = [(s, st) for s, st, _ in MARKETS]
    assert len(set(identities)) == len(identities)
    for sport, stat, _ in MARKETS:
        assert family(sport, stat) in ("count", "continuous")
        assert START[sport][:4].isdigit()

def get_market(index: int) -> dict:
    catalog_check()
    if not isinstance(index, int) or isinstance(index, bool) or index < 0 or index >= len(MARKETS):
        raise ValueError("invalid_precision_campaign_market_index")
    sport, stat, start = MARKETS[index]
    market_id = sport.lower() + "-" + slug(stat).replace("_", "-")
    return {"index": index, "market_count": len(MARKETS),
            "sport": sport, "stat": stat, "train_from": start,
            "fit_id": market_id, "next_index": index+1 if index+1 < len(MARKETS) else None}

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--index", type=int, required=True)
    p.add_argument("--github-env", type=Path)
    args = p.parse_args(argv)
    market = get_market(args.index)
    if args.github_env:
        entries = {
            "SPORT": market["sport"], "STAT": market["stat"],
            "TRAIN_FROM": market["train_from"], "FIT_ID": market["fit_id"],
            "NEXT_INDEX": ("" if market["next_index"] is None else str(market["next_index"])),
            "MARKET_INDEX": str(market["index"]),
            "MARKET_COUNT": str(market["market_count"])
        }
        with args.github_env.open("a", encoding="utf-8") as env:
            for key, val in entries.items():
                if "\n" in val or "\r" in val:
                    raise ValueError("invalid_market_environment_value")
                env.write(f"{key}={val}\n")
    print(json.dumps(market, sort_keys=True), flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
