#!/usr/bin/env python3
"""Schedule frozen SOG first, followed by NFL, then remaining NHL/NBA markets.

The underlying frozen statistical catalog and original market identities remain
immutable. This routing overlay only changes order of *future* market indices.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "scripts"))
import precision_campaign_catalog as frozen_catalog

SCHEMA = "precision_market_route_nfl_first_v1"


def catalog() -> tuple[dict, ...]:
    frozen_catalog.catalog_check()
    original = tuple(frozen_catalog.get_market(i) for i in range(31))
    if (len(original) != 31 or original[0]["sport"] != "NHL"
            or original[0]["stat"] != "shots on goal"):
        raise ValueError("unexpected_frozen_market_zero")
    # Never remove, duplicate, or relabel any model identity.
    nfl = tuple(m for m in original[1:] if m["sport"] == "NFL")
    rest = tuple(m for m in original[1:] if m["sport"] != "NFL")
    result = (original[0], *nfl, *rest)
    if (len(result) != len(original)
            or {m["fit_id"] for m in result} != {m["fit_id"] for m in original}
            or len({m["fit_id"] for m in result}) != len(result)
            or len(nfl) != 16):
        raise ValueError("routed_market_identity_or_count_mismatch")
    return result


def get_market(index: int) -> dict:
    if type(index) is not int or not 0 <= index < 31:
        raise ValueError("invalid_routed_market_index")
    markets = catalog()
    market = dict(markets[index])
    source_index = market["index"]
    market.update(index=index, source_index=source_index,
                  next_index=index + 1 if index + 1 < len(markets) else None,
                  routing_schema=SCHEMA, market_count=len(markets))
    return market


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--github-env", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)
    market = get_market(args.index)
    digest = hashlib.sha256(json.dumps([
        (m["sport"], m["stat"], m["source_index"])
        for m in (get_market(i) for i in range(31))
    ], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    market["routing_sha256"] = digest
    if args.github_env:
        entries = {
            "SPORT": market["sport"], "STAT": market["stat"],
            "TRAIN_FROM": market["train_from"], "FIT_ID": market["fit_id"],
            "NEXT_INDEX": ("" if market["next_index"] is None else str(market["next_index"])),
            "MARKET_INDEX": str(market["index"]),
            "MARKET_COUNT": str(market["market_count"]),
            "ROUTE_SOURCE_INDEX": str(market["source_index"]),
            "ROUTING_SCHEMA": SCHEMA,
            "ROUTING_SHA256": digest
        }
        with args.github_env.open("a", encoding="utf-8") as output:
            for key, value in entries.items():
                if "\n" in value or "\r" in value:
                    raise ValueError("invalid_routed_environment_value")
                output.write(f"{key}={value}\n")
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(market, indent=2, sort_keys=True) + "\n",
                                encoding="utf-8")
    print("FROZEN_MARKET_ROUTED " + json.dumps(market, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
