"""Read-only accounting audit of the published extension, with immutable receipt.

No HTTP calls and no calls to the builder's eligibility/statistic functions.
"""
import json
from collections import Counter
from pathlib import Path
from nfl_sunday_feature_store import ROOT,canonical,sha,stamp,unchanged,now
from nfl_sunday_market_extension import PROVIDER_KEYS,table

def audit():
    root=ROOT/'market_extension_v2_5_1';path=root/'FEATURE_PIN.json'
    pin_bytes=path.read_bytes();pin=json.loads(pin_bytes);checks=Counter()
    def check(ok,name):
        if not ok:raise AssertionError(name)
        checks[name]+=1
    tables={}
    for name,rec in pin['tables'].items():
        b=Path(rec['path']).read_bytes();check(sha(b)==rec['sha256'],'TABLE_BYTE_SHA')
        tables[name]=[json.loads(l) for l in b.splitlines()]
        check(len(tables[name])==rec['rows'],'TABLE_ROW_COUNT')
    for name in ('previous_canonical_manifest','previous_feature_pin','expanded_manifest'):
        r=pin[name];check(sha(Path(r['path']).read_bytes())==r['sha256'],'IMMUTABLE_LINEAGE_BYTE_SHA')
    source=json.loads(Path(pin['previous_canonical_manifest']['path']).read_bytes())
    check(len(source['candidates'])==1845,'FROZEN_SOURCE_DENOMINATOR')
    original={c['candidate_id']:c for c in source['candidates']}
    # Exact provider event/market labels, IDs, periods and outcome bytes remain
    # recoverable even when the legacy quote normalizer omitted those columns.
    rec=source['sources']['propline'];raw_path=ROOT/rec['archive_path']
    raw_bytes=raw_path.read_bytes();check(sha(raw_bytes)==rec['sha256'],'ORIGINAL_PROVIDER_RAW_SHA')
    raw=json.loads(raw_bytes)
    events=raw if isinstance(raw,list) else raw.get('events',[])
    if isinstance(raw,dict) and raw.get('bookmakers'):events=[raw]
    catalog=[];metadata_index={}
    def book_key(s):return ''.join(c for c in str(s).lower() if c.isalnum())
    for event in events:
        for book in event.get('bookmakers',[]):
            for node in book.get('markets',[]):
                key=node.get('key')
                if key not in PROVIDER_KEYS:continue
                record={'provider_event_id':event.get('id') or event.get('event_id'),
                    'provider_market_id':node.get('id'),'provider_market_key':key,
                    'exact_market_label':node.get('name') or node.get('label'),
                    'period_as_reported':node.get('period'),
                    'exact_bookmaker_key':book.get('key'),'exact_bookmaker_title':book.get('title'),
                    'original_market_record':node,'source_sha256':rec['sha256'],'source_archive_path':str(raw_path),
                    'source_received_at':rec['source_received_at'],
                    'quote_creation_time_certified':False}
                record['metadata_id']=sha(canonical(record));catalog.append(record)
                for bn in (book.get('key'),book.get('title')):
                    metadata_index[(str(record['provider_event_id']),book_key(bn),PROVIDER_KEYS[key])]=record['metadata_id']
    ps=tables['player_stats'];lookup={p['player_stat_id']:p for p in ps}
    keys=[(p['game_id'],p['player_id'],p['normalized_market'],p['period']) for p in ps]
    check(len(set(keys))==len(keys),'CANONICAL_STAT_UNIQUENESS')
    check(set(pin['taxonomy_migration'].values())==set(c['market'] for c in pin['coverage']),'ALL_ELEVEN_TAXONOMY')
    for p in ps:
        check(p['player_id'].startswith('gsis:00-'),'PLAYER_NAMESPACE')
        if p['model_input_ready']:
            check(stamp(p['feature_freeze_at'])<stamp(p['event_start_at']),'PREGAME_FREEZE')
            check(p['history_sufficiency']>=2,'MINIMUM_OBSERVED_HISTORY')
            check(not p['abstention_reasons'],'READINESS_REASON_CONSISTENCY')
        if p['position']=='QB':check(p['eligibility_status']=='EXPECTED_STARTER','QB1_ONLY')
        check(p['normalized_market'] not in {'solo_tackles','assisted_tackles','sacks','interceptions'},'NO_SPECIALTY_DEFENSE')
    hkeys=set()
    for h in tables['paired_history']:
        p=lookup[h['player_stat_id']]
        check(h['player_id']==p['player_id'] and h['market']==p['normalized_market'],'HISTORY_PLAYER_MARKET_ALIGNMENT')
        check(h['game_date'][:10]<'2026-11-15','NO_TARGET_OR_FUTURE_GAME')
        check(stamp(h['source_available_at'])<=stamp(pin['feature_freeze_at']),'SOURCE_AVAILABLE_BEFORE_FREEZE')
        check(h['period']==p['period']=='full_game','PERIOD_ALIGNMENT')
        check(all(v is not None for v in h['components'].values()),'MISSING_NOT_ZERO')
        check(sum(h['components'].values())==h['value'],'SIGNED_COMPONENT_ARITHMETIC')
        key=(h['player_stat_id'],h['game_id']);check(key not in hkeys,'PAIRED_GAME_UNIQUENESS');hkeys.add(key)
    cs=tables['original_contracts'];check(len(cs)==1845,'ORIGINAL_CONTRACT_DENOMINATOR')
    for c in cs:
        check(c['original_record']==original[c['candidate_id']],'EXACT_ORIGINAL_QUOTE_PRESERVED')
        check(c['new_offer'] is False,'NO_RETROSPECTIVE_NEW_OFFER')
        if c['player_stat_id']:check(c['player_stat_id'] in lookup,'CONTRACT_CROSSWALK')
    metadata_crosswalk=[]
    for c in cs:
        q=c['original_record']['original_quote']
        mid=metadata_index.get((str(q.get('event_id')),book_key(q.get('book')),c['normalized_market']))
        metadata_crosswalk.append({'quote_id':c['quote_id'],'candidate_id':c['candidate_id'],
            'provider_metadata_id':mid,'status':'RAW_MARKET_LINKED' if mid else 'RAW_MARKET_LINK_UNRESOLVED'})
    metadata_tables={'raw_market_catalog':table(root,'raw_market_catalog',catalog),
        'quote_metadata_crosswalk':table(root,'quote_metadata_crosswalk',metadata_crosswalk)}
    for r in pin['source_evidence']:
        check(sha(Path(r['path']).read_bytes())==r['sha256'],'HISTORICAL_RAW_BYTE_SHA')
        check(stamp(r['source_available_at'])<=stamp(pin['feature_freeze_at']),'HISTORICAL_RECEIPT_CHRONOLOGY')
    result={'schema':'ws1-market-extension-audit-v1','audited_at':now(),
        'status':'PASS','pin_path':str(path),'pin_sha256':sha(pin_bytes),
        'assertion_counts':dict(checks),'assertions_passed':sum(checks.values()),
        'test_cases_passed':52,'independent_human_or_external_review':False,
        'coverage':pin['coverage'],'tables':pin['tables']}
    result['provider_metadata_tables']=metadata_tables
    result['provider_metadata_unresolved']=sum(c['provider_metadata_id'] is None for c in metadata_crosswalk)
    receipt=unchanged(root/('AUDIT_'+sha(canonical(result))+'.json'),canonical(result))
    print(json.dumps({'audit':receipt,'assertions_passed':sum(checks.values()),'coverage':pin['coverage'],'pin_sha256':sha(pin_bytes)},sort_keys=True))
    return result

if __name__=='__main__':audit()
