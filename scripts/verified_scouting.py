#!/usr/bin/env python3
"""Import reviewer-read, sourced scouting evidence without numerical uplift.

This command preserves the collector-owned historical Engine B forecast; it only
fills qualitative explanations, supporting facts, and distinct mechanism events.
A recorded reviewer attestation is NOT machine proof a web source says the fact.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from research_packet import _validate_fact, _parse_time, MECHANISM_TYPES, _mechanism_identity
from scouting_checklist import required_checks

DIMENSIONS=frozenset(('matchup','opportunity','injuries','game_script'))


def _fact(entry,now):
    if entry.get('source_read') is not True:
        raise ValueError('reviewer must read source, not rely on a search snippet')
    if not str(entry.get('quote') or '').strip():
        raise ValueError('evidence requires a short exact supporting quote')
    if entry.get('confidence') != 'confirmed':
        raise ValueError('only confirmed sourced facts may be imported')
    fact={k:entry.get(k) for k in ('fact','value','confidence','source_url','retrieved_at','quote')}
    issue=[]
    _validate_fact('scouting',fact,issue,require_fresh=True,now=now)
    if issue:
        raise ValueError('; '.join(x.message for x in issue))
    return fact


def apply(packet,reports,*,now=None):
    now=now or datetime.now(timezone.utc)
    if packet.get('date')!=reports.get('date'):raise ValueError('scouting/slate date mismatch')
    if not str(reports.get('reviewer') or '').strip():raise ValueError('named reviewer required')
    entries=reports.get('entries')
    if not isinstance(entries,list) or not entries:raise ValueError('nonempty entries required')
    out=deepcopy(packet)
    for entry in entries:
        if not isinstance(entry,dict):raise ValueError('scouting entry must be object')
        candidate_id=entry.get('candidate_id')
        bits=candidate_id.split('|') if isinstance(candidate_id,str) else []
        if len(bits)!=4 or bits[3] not in ('over','under'):
            raise ValueError('invalid sport|player|stat|side candidate ID')
        sport,player,stat,side=bits
        meta=(packet.get('index',{}).get('by_player') or {}).get(player)
        if not isinstance(meta,dict) or meta.get('sport')!=sport:
            raise ValueError('scouting player does not match slate identity')
        if any(str(entry.get(k))!=str(meta.get(k)) for k in ('team','game','player_id')):
            raise ValueError('scouting team/game/player_id mismatch')
        if candidate_id not in (packet.get('scouting') or {}):
            raise ValueError('candidate does not exist in current research packet')
        scout=out['scouting'][candidate_id]
        kind=entry.get('kind')
        if kind in ('evidence','supporting_stat'):
            field=entry.get('field')
            if kind=='evidence' and field not in DIMENSIONS:
                raise ValueError('invalid evidence dimension')
            if kind=='supporting_stat' and field not in required_checks(sport,stat):
                raise ValueError('not a required supporting statistic')
            fact=_fact(entry,now)
            slot='evidence' if kind=='evidence' else 'supporting_stats'
            old=(scout.get(slot) or {}).get(field)
            if old is not None and old.get('value') != fact['value']:
                raise ValueError('contradictory research evidence requires separate source reconciliation')
            scout.setdefault(slot,{})[field]=fact
        elif kind=='mechanism':
            if entry.get('type') not in MECHANISM_TYPES or entry.get('supports_side')!=side:
                raise ValueError('unsupported causal mechanism type or mismatched side')
            if not entry.get('event_id') or not str(entry.get('description') or '').strip():
                raise ValueError('stable causal event_id and nonempty description required')
            sources=entry.get('sources')
            if not isinstance(sources,list) or not sources:
                raise ValueError('mechanism requires source readings')
            normalized={'type':entry['type'],'supports_side':side,'event_id':entry['event_id'],
                        'description':entry['description'],'sources':[_fact(f,now) for f in sources]}
            existing=out.setdefault('mechanisms',{}).setdefault(candidate_id,[])
            if any(_mechanism_identity(m)==_mechanism_identity(normalized) for m in existing):
                raise ValueError('duplicate mechanism event; sources do not add independent events')
            existing.append(normalized)
        else:
            raise ValueError('unknown scouting entry kind')
        out.setdefault('_verified_scouting_log',[]).append({
            'candidate_id':candidate_id,'kind':kind,'reviewer':reports['reviewer'],
            'imported_at':now.isoformat()})
    return out


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--packet',required=True)
    ap.add_argument('--reports',required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--now',help='ISO-8601 for retrospective testing only')
    a=ap.parse_args()
    for path in (a.packet,a.reports):
        if Path(a.out).resolve()==Path(path).resolve():
            ap.error('output must differ from inputs')
    source=json.loads(Path(a.packet).read_text(encoding='utf-8'))
    entries=json.loads(Path(a.reports).read_text(encoding='utf-8'))
    updated=apply(source,entries,now=_parse_time(a.now) if a.now else datetime.now(timezone.utc))
    Path(a.out).write_text(json.dumps(updated,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'ok':True,'imported':len(entries['entries']),
                      'publication_eligible':False,'requires':'research_packet.py audit'}))
    return 0

if __name__=='__main__':raise SystemExit(main())
