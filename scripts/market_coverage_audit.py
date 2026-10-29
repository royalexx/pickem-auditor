#!/usr/bin/env python3
"""Report requested, sourced and absent player markets; never fabricate prices."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from odds_providers import SPORTS, PROPLINE_SUPPORTED_MARKETS

def audit(quotes, slate, *, odds_disabled=False, raw_inventory=None):
    raw_inventory=raw_inventory or {}
    by_quote=Counter((str(q.get('sport')),str(q.get('stat'))) for q in quotes
                     if isinstance(q,dict))
    by_slate=Counter((str(r.get('sport')),str(r.get('stat'))) for r in slate
                     if isinstance(r,dict))
    listed=[]
    for sport,provider_key,markets in SPORTS:
        for market,stat in markets:
            supported=market in PROPLINE_SUPPORTED_MARKETS
            n=by_quote.get((sport,stat),0)
            inventory=raw_inventory.get(sport) if isinstance(raw_inventory.get(sport),dict) else {}
            raw_count=((inventory.get("raw_bookmaker_market_counts") or {}).get(market,0)
                       if inventory else None)
            events=inventory.get("pregame_event_count")
            status=("odds_disabled" if odds_disabled else
                    "provider_unsupported" if not supported else
                    "two_sided_quotes_collected" if n else
                    "raw_market_missing_from_provider_payload" if raw_count==0 and events else
                    "raw_market_present_but_unpaired_or_filtered" if isinstance(raw_count,int) and raw_count>0 else
                    "no_two_sided_quotes_in_normalized_feed")
            listed.append(dict(sport=sport,market=market,stat=stat,provider_supported=supported,
                quote_rows=n,raw_market_occurrences=raw_count,
                provider_pregame_events=events,
                source_rows=by_slate.get((sport,stat),0),status=status))
    listed.append(dict(sport="NHL",market="player_hits",stat="hits",
        provider_supported=False,quote_rows=by_quote.get(("NHL","hits"),0),
        source_rows=by_slate.get(("NHL","hits"),0),
        status="provider_unsupported_no_live_hits_in_propline",
        action="independent_verified_two_sided_source_required;never_invent_market"))
    return dict(schema="market-coverage-v1",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        source_quote_rows=len(quotes),source_slate_rows=len(slate),
        raw_market_inventory_available=bool(raw_inventory),
        market_rows=listed,
        absent_supported=[dict(sport=r['sport'],market=r['market'],stat=r['stat'])
                          for r in listed if r['provider_supported'] and r['quote_rows']==0
                          and not odds_disabled and r.get("provider_pregame_events",0)],
        nhl_missing_market_diagnosis=[dict(market=r["market"],stat=r["stat"],
                              status=r["status"],raw_market_occurrences=r.get("raw_market_occurrences"))
                   for r in listed if r["sport"]=="NHL" and not r["quote_rows"]],
        limitation="Missing normalized quotes do not distinguish provider omission from one-sided book markets, parser drops, or absence of a scheduled game.",
        publication_eligible=False)

def load_raw_inventory(path):
    p=Path(path)
    if not p.is_file():return {}
    try:
        meta=json.loads(p.read_text())
        notes=(((meta.get("feeds") or {}).get("odds") or {}).get("notes") or [])
        marker="MARKET_SOURCE_INVENTORY_JSON="
        for note in notes:
            if marker in str(note):
                obj=json.loads(str(note).rsplit(marker,1)[1])
                if isinstance(obj,dict):return obj
    except (OSError,ValueError,TypeError):pass
    return {}

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--quotes',default='data/odds_quotes.jsonl')
    p.add_argument('--slate',default='data/slate_fetch.jsonl')
    p.add_argument('--out',default='reports/market_coverage.json')
    p.add_argument('--meta',default='data/slate_fetch.meta.json')
    p.add_argument('--odds-disabled',action='store_true')
    args=p.parse_args(argv)
    def read(path):
        f=Path(path)
        if not f.exists():return []
        return [json.loads(s) for s in f.read_text().splitlines() if s.strip()]
    result=audit(read(args.quotes),read(args.slate),odds_disabled=args.odds_disabled,
                 raw_inventory=load_raw_inventory(args.meta))
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:result[k] for k in
          ('schema','source_quote_rows','source_slate_rows','absent_supported')}))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
