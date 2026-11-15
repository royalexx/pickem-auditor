"""Separate WS6-readable accounting and rational-number audit of WS5 outputs."""
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path


def audit(ledger_path):
    ledger_path=Path(ledger_path); ledger=json.loads(ledger_path.read_bytes()); tables={};checks=0
    for name,d in ledger['outputs'].items():
        raw=Path(d['path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==d['sha256'];checks+=1
        rows=[json.loads(x) for x in raw.splitlines()];assert len(rows)==d['rows'];checks+=1
        tables[name]=rows
    quotes=tables['original_quote_benchmarks'];availability=tables['market_availability'];lines=tables['same_line_coverage']
    assert len(quotes)==1845 and len(availability)==3570;checks+=1
    assert len({a['player_stat_id'] for a in availability})==3570;checks+=1
    assert sum(not a['quote_ids'] for a in availability)==2990;checks+=1
    byid={q['quote_id']:q for q in quotes}
    for q in quotes:
        for side,actual in q['raw_implied'].items():
            price=q['original_record'].get(side+'_odds')
            if actual is not None:
                p=Fraction(str(price)); expected=Fraction(100)/(p+100) if p>0 else -p/(100-p)
                assert abs(float(expected)-actual)<1e-14;checks+=1
        if q['reasons']: assert q['conditional_no_push'] is None;checks+=1
        assert q['push_probability'] is None and q['unconditional'] is None;checks+=1
    for a in availability:
        assert all(byid[i]['player_stat_id']==a['player_stat_id'] for i in a['quote_ids']);checks+=1
        if not a['quote_ids']: assert a['market_probability'] is None;checks+=1
    for line in lines:
        linked=[byid[i] for i in line['original_quote_ids']]
        assert all(q['line']==line['line'] and q['normalized_market']==line['normalized_market'] and q['event_id']==line['event_id'] and q['player_id']==line['player_id'] for q in linked);checks+=1
        if not line['accepted_quote_ids']: assert line['conditional_no_push'] is None;checks+=1
    return dict(status='PASS',assertions=checks,quote_rows=len(quotes),availability_rows=len(availability),line_groups=len(lines),
        raw_price_pairs=sum(all(x is not None for x in q['raw_implied'].values()) for q in quotes),
        source_certified_quotes=sum(q['source_certified'] is True for q in quotes),
        availability_states=dict(Counter(q['availability_state'] for q in quotes)),
        eligible_benchmarks=sum(q['conditional_no_push'] is not None for q in quotes),
        note='Independent rational arithmetic and output reconciliation; not independent human/scientific certification')

if __name__=='__main__':
    import sys
    print(json.dumps(audit(sys.argv[1]),sort_keys=True))
