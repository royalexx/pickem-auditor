#!/usr/bin/env python3
"""Recover sourced, identity-matched research facts from a saved same-day packet.

Only authoritative provenance is transferable. Unknown, invalid, expired, or
contradictory facts remain unresolved. This is NOT a source of new information
or a way to reclassify an older postgame fact as a pregame forecast.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

from research_packet import _validate_fact, _parse_time


def _usable(value, now):
    problems = []
    v = _validate_fact('recovery', value, problems, require_fresh=True, now=now)
    return bool(v and not problems and v.confidence == 'confirmed')


def _newer(left, right):
    """Both valid facts; return the later retrieved observation."""
    return left if _parse_time(left['retrieved_at']) >= _parse_time(right['retrieved_at']) else right


def recover(current: dict, saved: dict, *, now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    if current.get('date') != saved.get('date') or not current.get('date'):
        raise ValueError('recovery requires identical nonempty slate dates')
    result = deepcopy(current)
    receipt = {'date':current['date'], 'recovered_facts':0, 'kept_current':0,
               'expired_or_invalid':0,'identity_rejected':0,
               'conflicts':[], 'publication_eligible':False}
    ci=(current.get('index') or {}).get('by_player') or {}
    si=(saved.get('index') or {}).get('by_player') or {}
    matched={p for p in ci.keys() & si.keys() if ci[p] == si[p]}
    receipt['identity_rejected']=len(set(si)-matched)
    same_games={v['game'] for p,v in ci.items() if p in matched and v.get('game')}
    same_teams={v['team'] for p,v in ci.items() if p in matched and v.get('team')}
    # A shared game/venue can be reused if it was part of a verified player
    # identity. Other games' facts must not migrate into this fixture.
    scopes={'weather':same_games,'environment':same_games,'lineup':same_teams,
            'availability':matched, 'player_context':matched}

    def merge_leaf(section, owner, key, old):
        if not _usable(old,now):
            receipt['expired_or_invalid']+=1
            return
        dest=result.setdefault(section,{}).setdefault(owner,{})
        cur=dest.get(key)
        if not _usable(cur,now):
            dest[key]=deepcopy(old)
            receipt['recovered_facts']+=1
            return
        if cur.get('value') != old.get('value'):
            # A newer retrieval is not sufficient to resolve contradictory
            # source observations (especially availability and starter flags).
            dest[key]=None
            receipt['conflicts'].append({'path':f'{section}.{owner}.{key}',
                                         'reason':'contradictory_fresh_sources',
                                         'source_urls':[cur['source_url'],old['source_url']]})
            return
        dest[key]=deepcopy(_newer(cur,old))
        receipt['kept_current']+=1

    for sec, owners in scopes.items():
        for owner, entry in (saved.get(sec) or {}).items():
            if owner not in owners or not isinstance(entry,dict): continue
            for key,old in entry.items():
                # Source-bearing facts only; never migrate a scalar inferred
                # from a downloaded but unverifiable text blob.
                merge_leaf(sec,owner,key,old)

    for key, saved_scout in (saved.get('scouting') or {}).items():
        bits=key.split('|')
        if len(bits)!=4 or bits[1] not in matched or not isinstance(saved_scout,dict):continue
        scout=result.setdefault('scouting',{}).setdefault(key,{})
        for section in ('evidence','supporting_stats'):
            for field,fact in (saved_scout.get(section) or {}).items():
                if not _usable(fact,now):
                    receipt['expired_or_invalid']+=1
                    continue
                present=scout.setdefault(section,{}).get(field)
                if not _usable(present,now):
                    scout[section][field]=deepcopy(fact)
                    receipt['recovered_facts']+=1
                elif present.get('value') == fact.get('value'):
                    scout[section][field]=deepcopy(_newer(present,fact))
                else:
                    scout[section][field]=None
                    receipt['conflicts'].append({'path':f'scouting.{key}.{section}.{field}',
                                                 'reason':'contradictory_fresh_sources'})
        # Historical usage remains collector-owned and is never replayed here.
    for key, mechs in (saved.get('mechanisms') or {}).items():
        bits=key.split('|')
        if len(bits)!=4 or bits[1] not in matched or not isinstance(mechs,list):continue
        accepted=[]
        for m in mechs:
            if not isinstance(m,dict) or not m.get('event_id') or not isinstance(m.get('sources'),list):continue
            if not all(_usable(f,now) for f in m['sources']) or not m['sources']:continue
            accepted.append(deepcopy(m))
        if accepted and not result.setdefault('mechanisms',{}).get(key):
            result['mechanisms'][key]=accepted
            receipt['recovered_facts']+=len(accepted)
    if receipt['conflicts']:
        result.setdefault('_recovery_conflicts',[]).extend(receipt['conflicts'])
    return result,receipt


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--current',required=True)
    ap.add_argument('--prior',required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--now',help='ISO-8601 UTC clock for an offline reproduction')
    a=ap.parse_args()
    current=json.loads(Path(a.current).read_text(encoding='utf-8'))
    prior=json.loads(Path(a.prior).read_text(encoding='utf-8'))
    now=_parse_time(a.now) if a.now else datetime.now(timezone.utc)
    updated,receipt=recover(current,prior,now=now)
    dst=Path(a.out);dst.parent.mkdir(parents=True,exist_ok=True)
    if dst.resolve() in (Path(a.current).resolve(),Path(a.prior).resolve()):
        ap.error('output must differ from inputs to preserve source packets')
    dst.write_text(json.dumps(updated,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2,sort_keys=True))
    return 0 if not receipt['conflicts'] else 2


if __name__=='__main__':raise SystemExit(main())
