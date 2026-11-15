"""WS5 source-only eleven-market audit. No collector or downstream forecast imports."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

VERSION = 'ws5-direct-same-line-v1'
METHOD = 'multiplicative-american-v1'
CANONICAL_SHA = '5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71'
PIN_SHA = 'c3ec93c78fcae413f66afe431f817f4d986f0fd1e884c665caefc5c7a3ed230c'
MARKETS = ('pass_attempts','pass_completions','passing_yards','rush_attempts',
 'rushing_yards','receiving_targets','receptions','receiving_yards','tackles_assists',
 'rushing_receiving_yards','passing_rushing_yards')
LABELS = dict(zip(('pass attempts','completions','passing yards','rush attempts',
 'rushing yards','targets','receptions','receiving yards','tackles + assists',
 'rushing + receiving yards','passing + rushing yards'), MARKETS))
STATES = ('ORIGINAL_OFFER_SOURCE_CERTIFIED','ORIGINAL_OFFER_UNCERTIFIED',
 'ONLY_ONE_SIDE_AVAILABLE','NO_ORIGINAL_OFFER','UNSUPPORTED_SETTLEMENT_DEFINITION',
 'SOURCE_REJECTED_OR_STALE','GAME_STARTED_BEFORE_OBSERVATION')


def sha(b): return hashlib.sha256(b).hexdigest()
def encoded(x): return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def stamp(x):
    if not isinstance(x,str): raise ValueError('missing_time')
    t = datetime.fromisoformat(x.replace('Z','+00:00'))
    if t.tzinfo is None: raise ValueError('naive_time')
    return t

def implied(price):
    if isinstance(price,bool) or not isinstance(price,(int,float)) or not math.isfinite(price) or abs(price)<100:
        raise ValueError('invalid_american_price')
    return 100/(price+100) if price>0 else -price/(100-price)

def devig(over,under):
    a,b = implied(over),implied(under)
    return {'over':a/(a+b),'under':b/(a+b)}

def checked(root, desc):
    p = (root/desc['path']).resolve()
    if not p.is_relative_to(root.resolve()): raise ValueError('path_escape')
    b = p.read_bytes()
    if sha(b)!=desc['sha256']: raise ValueError('source_hash_mismatch')
    return b

def read_jsonl(b): return [json.loads(x) for x in b.splitlines() if x]

def quote(wrapper, metadata, player_stat, cutoff, duplicates=False):
    r = wrapper['original_record']; raw = metadata.get('original_market_record',{})
    m = wrapper.get('normalized_market'); reasons=[]
    out = dict(benchmark_version=VERSION, quote_id=r.get('quote_id'), candidate_id=r.get('candidate_id'),
        player_stat_id=wrapper.get('player_stat_id'), normalized_market=m,
        original_record=r, provider_metadata=metadata, book=r.get('book'), player=r.get('player'),
        event_id=r.get('event_id'), player_id=r.get('player_id'), period=r.get('period'), line=r.get('line'),
        original_provider_market_label=metadata.get('exact_market_label'),
        original_provider_market_description=raw.get('description'), provider_market_key=metadata.get('provider_market_key'),
        source_sha256=r.get('source_sha256'), source_received_at=r.get('source_received_at'),
        quote_reported_at=r.get('original_quote_reported_at'), event_start_at=r.get('event_start_at'),
        forecast_cutoff_at=cutoff, source_certified=r.get('source_certified'),
        settlement_status=r.get('settlement_semantics'), margin_method=METHOD,
        probability_semantics='conditional_on_nonpush', push_probability=None, unconditional=None,
        raw_implied={'over':None,'under':None}, conditional_no_push=None, consensus_id=None)
    for side in ('over','under'):
        try: out['raw_implied'][side]=implied(r.get(side+'_odds'))
        except ValueError: pass
    if isinstance(r.get('line'),bool) or not isinstance(r.get('line'),(int,float)) or not math.isfinite(r['line']): reasons.append('INVALID_LINE')
    if m not in MARKETS or LABELS.get(r.get('stat'))!=m: reasons.append('UNSUPPORTED_MARKET_OR_CROSS_MARKET_CONFLICT')
    if duplicates: reasons.append('DUPLICATE_QUOTE_ID')
    if not r.get('source_certified') or r.get('source_validation_failure'): reasons.append('SOURCE_REJECTED_OR_UNCERTIFIED')
    q=r.get('original_quote',{})
    for k in ('book','player','stat','line','over_odds','under_odds'):
        if q.get(k)!=r.get(k): reasons.append('ORIGINAL_IDENTITY_CONFLICT_'+k)
    if str(q.get('event_id'))!=str(r.get('provider_event_id')): reasons.append('EVENT_IDENTITY_CONFLICT')
    if not metadata or metadata.get('source_sha256')!=r.get('source_sha256') or str(metadata.get('provider_event_id'))!=str(r.get('provider_event_id')) or metadata.get('exact_bookmaker_title')!=r.get('book'):
        reasons.append('RAW_METADATA_IDENTITY_CONFLICT')
    if player_stat is None: reasons.append('NO_ELIGIBLE_PLAYER_STAT_CROSSWALK')
    elif any((player_stat.get(a)!=r.get(b)) for a,b in [('game_id','event_id'),('espn_player_id','player_id'),('period','period'),('normalized_market','normalized_market')] if a!='normalized_market') or player_stat.get('normalized_market')!=m:
        reasons.append('PLAYER_GAME_STAT_PERIOD_CONFLICT')
    if r.get('period')!='full_game' or metadata.get('period_as_reported') not in (None,'full_game'):
        reasons.append('PERIOD_MISMATCH')
    # Null provider period is preserved as uncertified; never silently certify it.
    if metadata.get('period_as_reported') is None: reasons.append('PROVIDER_PERIOD_UNCERTIFIED')
    if r.get('settlement_semantics') not in ('FULL_GAME_OFFICIAL_STAT_OVERTIME_INCLUDED_V1',):
        reasons.append('SETTLEMENT_UNCERTIFIED')
    if m=='tackles_assists' and metadata.get('combined_tackle_accounting_certified') is not True:
        reasons.append('COMBINED_TACKLE_ACCOUNTING_UNCERTIFIED')
    if any(v is None for v in out['raw_implied'].values()): reasons.append('INCOMPLETE_PRICES')
    try:
        received,start,freeze = map(stamp,(r['source_received_at'],r['event_start_at'],cutoff))
        if received>=start: reasons.append('GAME_STARTED_BEFORE_OBSERVATION')
        if received>freeze: reasons.append('QUOTE_AFTER_FORECAST_CUTOFF')
        if freeze>=start: reasons.append('GAME_STARTED_AT_FORECAST_CUTOFF')
        if (freeze-received).total_seconds()>86400: reasons.append('STALE_AT_CUTOFF')
        if stamp(q['event_start'])!=start: reasons.append('KICKOFF_CONFLICT')
    except (KeyError,TypeError,ValueError): reasons.append('INVALID_CHRONOLOGY')
    sides = {}
    for o in raw.get('outcomes',[]):
        if o.get('description')==r.get('player') and o.get('point')==r.get('line') and str(o.get('name')).lower() in ('over','under'):
            sides.setdefault(o['name'].lower(),[]).append(o)
    for side in ('over','under'):
        if r.get(side+'_odds') is not None and (len(sides.get(side,[]))!=1 or sides[side][0].get('price')!=r[side+'_odds']):
            reasons.append('RAW_PRICE_PAIR_CONFLICT')
    if len(sides)==2 and all(len(v)==1 for v in sides.values()):
        if sides['over'][0].get('player_id')!=sides['under'][0].get('player_id'): reasons.append('RAW_PLAYER_ID_CONFLICT')
    if 'GAME_STARTED_BEFORE_OBSERVATION' in reasons: state=STATES[6]
    elif any(x in reasons for x in ('SOURCE_REJECTED_OR_UNCERTIFIED','STALE_AT_CUTOFF','DUPLICATE_QUOTE_ID','RAW_PRICE_PAIR_CONFLICT','INVALID_CHRONOLOGY','QUOTE_AFTER_FORECAST_CUTOFF','GAME_STARTED_AT_FORECAST_CUTOFF')): state=STATES[5]
    elif 'INCOMPLETE_PRICES' in reasons: state=STATES[2]
    elif 'COMBINED_TACKLE_ACCOUNTING_UNCERTIFIED' in reasons: state=STATES[4]
    elif reasons: state=STATES[1]
    else: state=STATES[0]
    out.update(availability_state=state,reasons=sorted(set(reasons)))
    if not reasons: out['conditional_no_push']=devig(r['over_odds'],r['under_odds'])
    return out


def consensus(quotes):
    groups=defaultdict(list)
    for q in quotes:
        key=tuple(q.get(k) for k in ('event_id','player_id','normalized_market','period','line','settlement_status','source_received_at'))
        groups[key].append(q)
    rows=[]
    for key,items in sorted(groups.items(),key=lambda x:str(x[0])):
        valid=[q for q in items if q['conditional_no_push'] is not None]
        # One observation per book: repeated snapshots never increase its weight.
        books=Counter(q['book'] for q in valid)
        valid=[q for q in valid if books[q['book']]==1]
        ident=sha(encoded(key))
        for q in items: q['consensus_id']=ident
        p=sum(q['conditional_no_push']['over'] for q in valid)/len(valid) if valid else None
        rows.append(dict(consensus_id=ident,event_id=key[0],player_id=key[1],normalized_market=key[2],
            period=key[3],line=key[4],settlement_status=key[5],source_received_at=key[6],
            original_quote_ids=[q['quote_id'] for q in items],original_books=[q['book'] for q in items],
            accepted_quote_ids=[q['quote_id'] for q in valid],book_count=len(valid),
            conditional_no_push=None if p is None else dict(over=p,under=1-p),push_probability=None,unconditional=None,
            method='equal-book-arithmetic-same-line-v1',cross_line_inference=None,
            status='UNAVAILABLE' if not valid else ('SINGLE_BOOK_REFERENCE' if len(valid)==1 else 'DIRECT_SAME_LINE_CONSENSUS')))
    return rows


def exclusive(path,b):
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open('xb') as f: f.write(b)
    except FileExistsError:
        if path.read_bytes()!=b: raise ValueError('immutable_output_conflict')
    return dict(path=str(path),sha256=sha(b),size=len(b))

def run(root,pin_path,out,cutoff):
    pin=json.loads(checked(root,dict(path=pin_path,sha256=PIN_SHA)))
    original=json.loads(checked(root,pin['previous_canonical_manifest']))
    if pin['previous_canonical_manifest']['sha256']!=CANONICAL_SHA: raise ValueError('wrong_original_manifest')
    expanded=json.loads(checked(root,pin['expanded_manifest']))
    for r in original['sources'].values():
        checked(root,dict(path='reports/nfl_20261115_prospective/'+r['archive_path'],sha256=r['sha256']))
    tables={k:read_jsonl(checked(root,v)) for k,v in pin['tables'].items() if k in ('original_contracts','player_stats','crosswalk')}
    # Metadata tables are versioned by WS1 alongside the pin, with exact content-addressed filenames.
    base=Path(pin_path).parent
    for name, expected_hash in (('quote_metadata_crosswalk','71d661422fdc122da398fb713242ba450022f659ab004eeb2268ac6abddd653c'),('raw_market_catalog','a6dc1df790946d166339694087fd47d6b2d9e695e1cdaa6a0b4c846ca96a4650')):
        paths=list((root/base).glob(name+'_*.jsonl'))
        if len(paths)!=1: raise ValueError('ambiguous_metadata_table')
        h=paths[0].stem.removeprefix(name+'_')
        if h != expected_hash: raise ValueError('unpinned_metadata_table')
        tables[name]=read_jsonl(checked(root,dict(path=str(paths[0].relative_to(root)),sha256=h)))
    originals = {r['quote_id']:r for r in original['candidates']}
    for w in tables['original_contracts']:
        if w['original_record'] != originals.get(w['quote_id']): raise ValueError('original_record_modified')
    stats={r['player_stat_id']:r for r in tables['player_stats']}
    if len(stats)!=len(tables['player_stats']): raise ValueError('duplicate_player_stat')
    links={r['quote_id']:r['provider_metadata_id'] for r in tables['quote_metadata_crosswalk']}
    catalog={r['metadata_id']:r for r in tables['raw_market_catalog']}
    counts=Counter(w['quote_id'] for w in tables['original_contracts'])
    quotes=[quote(w,catalog.get(links.get(w['quote_id']),{}),stats.get(w['player_stat_id']),cutoff,counts[w['quote_id']]>1) for w in tables['original_contracts']]
    lines=consensus(quotes); linked=defaultdict(list)
    for q in quotes: linked[q['player_stat_id']].append(q)
    availability=[]
    for ps in tables['player_stats']:
        qs=linked[ps['player_stat_id']]; states=sorted(set(q['availability_state'] for q in qs)) or [STATES[3]]
        availability.append(dict(player_stat=ps,player_stat_id=ps['player_stat_id'],normalized_market=ps['normalized_market'],
            quote_ids=[q['quote_id'] for q in qs],availability_states=states,original_contract_count=len(qs),
            applicable_benchmark_count=sum(q['conditional_no_push'] is not None for q in qs),
            market_probability=None))
    coverage=[]
    for m in MARKETS:
        qs=[q for q in quotes if q['normalized_market']==m]; aa=[a for a in availability if a['normalized_market']==m]
        coverage.append(dict(market=m,original_quotes=len(qs),eligible_player_stats=len(aa),
            without_original_contract=sum(not a['quote_ids'] for a in aa),
            benchmark_quotes=sum(q['conditional_no_push'] is not None for q in qs),
            original_line_groups=sum(x['normalized_market']==m for x in lines),
            quote_states=dict(Counter(q['availability_state'] for q in qs))))
    outputs={}
    for name,rows in [('market_availability',availability),('original_quote_benchmarks',quotes),('same_line_coverage',lines)]:
        b=b''.join(encoded(r) for r in rows); outputs[name]=exclusive(out/(name+'_'+sha(b)+'.jsonl'),b);outputs[name]['rows']=len(rows)
    ledger=dict(schema=VERSION,status='SHADOW_ONLY',forecast_cutoff_at=cutoff,source_manifest_sha256=CANONICAL_SHA,
        feature_pin_sha256=PIN_SHA,expanded_manifest_sha256=pin['expanded_manifest']['sha256'],
        implementation_sha256=sha(Path(__file__).read_bytes()),coverage=coverage,outputs=outputs,
        source_rejection_reasons=dict(Counter(x for q in quotes for x in q['reasons'])),
        probability_semantics='conditional_on_nonpush',push_probability=None,unconditional=None,
        margin_method=METHOD,downstream_predictions_consumed=False,sportsbook_requests=0,
        quote_receipt_sha256=sorted(set(q['source_sha256'] for q in quotes)),
        quote_received_at=sorted(set(q['source_received_at'] for q in quotes)),
        ws6_join_keys=['player_stat_id','quote_id','consensus_id'],
        verification='automated source-byte and accounting audit; independent human review pending')
    b=encoded(ledger); result=exclusive(out/('LEDGER_'+sha(b)+'.json'),b)
    print(json.dumps(dict(ledger=result,coverage=coverage,reasons=ledger['source_rejection_reasons'])))
    return ledger

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--pin',required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--cutoff',required=True);a=p.parse_args()
    run(a.root.resolve(),a.pin,a.out,a.cutoff)
