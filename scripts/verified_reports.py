"""Import manually verified game-day reports; never infer status from omissions.

The reviewer must read the cited source. Schema validation cannot establish that
a webpage supports a statement. No opportunities, conversion or uplifts accepted.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

from research_packet import _validate_fact, _parse_time, AVAILABILITY_STATUS


def apply_reports(packet, report, now=None):
    now = now or datetime.now(timezone.utc)
    if report.get('date') != packet.get('date'):
        raise ValueError('report slate date mismatch')
    if not isinstance(report.get('reviewer'), str) or not report['reviewer'].strip():
        raise ValueError('named reviewer required')
    entries = report.get('entries')
    if not isinstance(entries, list) or not entries:
        raise ValueError('nonempty report entries required')
    result = deepcopy(packet)
    seen = set()
    allowed = {'player','player_id','sport','team','game','status','source_url',
               'quote','retrieved_at','published_at','source_kind','basis',
               'source_read','event_id','effective_at','starting_confirmed',
               'conflict_resolution','starting_role'}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) - allowed:
            raise ValueError('report contains unsupported fields or numeric adjustments')
        name = entry.get('player')
        if name in seen:
            raise ValueError('duplicate player report')
        seen.add(name)
        meta = (packet.get('index', {}).get('by_player') or {}).get(name)
        if not meta or any(meta.get(k) in (None, '') for k in ('player_id','sport','team','game')) or any(str(entry.get(k)) != str(meta.get(k)) for k in
                           ('player_id','sport','team','game')):
            raise ValueError('report player/team/game identity mismatch')
        if entry.get('source_read') is not True:
            raise ValueError('reviewer must read the source, not a search snippet')
        if entry.get('basis') not in ('explicit_game_report','coach_confirmation','official_inactives'):
            raise ValueError('explicit game-day evidence required; projected lines and roster membership are insufficient')
        status = entry.get('status')
        if status not in AVAILABILITY_STATUS:
            raise ValueError('unknown availability status')
        if entry['basis'] == 'official_inactives' and status != 'out':
            raise ValueError('absence from an inactive list cannot establish active status')
        if entry.get('source_kind') not in ('league','team','beat'):
            raise ValueError('source kind required')
        if not isinstance(entry.get('quote'), str) or not entry['quote'].strip():
            raise ValueError('short supporting source quote required')
        for key in ('retrieved_at', 'published_at'):
            text = entry.get(key)
            if not isinstance(text, str):
                raise ValueError('source timestamps required')
            stamp = datetime.fromisoformat(text.replace('Z','+00:00'))
            if stamp.tzinfo is None or stamp > now:
                raise ValueError('source timestamps must have a timezone and not be future')
        if _parse_time(entry['published_at']) > _parse_time(entry['retrieved_at']):
            raise ValueError('publication cannot follow retrieval')
        fact = dict(fact='reviewed game-day availability', value=status,
                    confidence='confirmed', source_url=entry['source_url'],
                    quote=entry['quote'], retrieved_at=entry['retrieved_at'],
                    published_at=entry['published_at'], report_type='game_day_report',
                    primary_source_kind=entry['source_kind'])
        for field in ('event_id','effective_at'):
            if field in entry:
                fact[field] = entry[field]
        issues = []
        _validate_fact('report', fact, issues, require_fresh=True, now=now)
        if issues:
            raise ValueError('; '.join(i.message for i in issues))
        stable = f"{entry['sport']}|{entry['player_id']}"
        existing = result.get('availability', {})
        previous = (existing.get(stable) or existing.get(name) or {}).get('status')
        conflicts = [c for c in result.get('_source_conflicts', [])
                     if c.get('player') in (name, stable) and c.get('resolution') == 'unresolved']
        if (previous and previous.get('value') != status) or conflicts:
            if not str(entry.get('conflict_resolution') or '').strip():
                raise ValueError('conflicting status requires a sourced resolution explanation')
            result.setdefault('_source_conflicts', []).append({
                'player': name, 'field':'status', 'previous':previous,
                'resolution':'reviewed_game_report','resolution_fact':fact,
                'rationale':entry['conflict_resolution']})
            for conflict in conflicts:
                conflict.update(resolution='reviewed_game_report', resolution_fact=fact,
                                rationale=entry['conflict_resolution'])
        result.setdefault('availability', {})[name] = {
            'status':fact, 'primary_source':{**fact,'fact':'source classification',
                                           'value':entry['source_kind']}}
        # Keep stable identity lookup authoritative too, when present.
        if stable in result['availability']:
            result['availability'][stable] = deepcopy(result['availability'][name])
        if 'starting_confirmed' in entry:
            if entry['starting_confirmed'] is not True or status != 'active':
                raise ValueError('starting confirmation requires explicit active starter evidence')
            if entry['sport'] == 'NHL' and entry.get('starting_role') == 'goalie':
                result.setdefault('player_context', {}).setdefault(name, {})['goalie_confirmed'] = {
                    **fact,'fact':'explicit starting goalie confirmation','value':True}
            elif entry['sport'] == 'NFL' and entry.get('starting_role') == 'quarterback':
                result.setdefault('player_context', {}).setdefault(name, {})['expected_starting_qb'] = {
                    **fact,'fact':'explicit starting quarterback confirmation','value':True}
            else:
                raise ValueError('starter report supported only for NFL QB or NHL goalie')
        result.setdefault('_verified_report_log', []).append({
            'player':name,'reviewer':report['reviewer'],'imported_at':now.isoformat(),
            'basis':entry['basis'],'fact':fact})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', required=True)
    parser.add_argument('--reports')
    parser.add_argument('--template', action='store_true', help='Write an unverified template; never imports facts')
    parser.add_argument('--player', action='append', help='Exact indexed name for template generation; repeatable')
    parser.add_argument('--out', required=True, help='Reviewed packet destination; preserves the input')
    args = parser.parse_args()
    output = Path(args.out)
    if output.resolve() == Path(args.packet).resolve():
        parser.error('use a distinct output path to preserve the source packet')
    packet = json.loads(Path(args.packet).read_text())
    if args.template:
        if args.reports or not args.player:
            parser.error('--template requires --player and cannot use --reports')
        entries=[]
        for name in args.player:
            meta=packet.get('index', {}).get('by_player', {}).get(name)
            if not meta:parser.error('player must match an indexed name exactly')
            entries.append(dict(player=name, **{k:meta.get(k) for k in ('player_id','sport','team','game')},
                status=None,source_url=None,quote=None,retrieved_at=None,published_at=None,
                source_kind=None,basis=None,source_read=False))
        updated={'date':packet['date'],'reviewer':None,'entries':entries}
    else:
        if not args.reports:parser.error('--reports required unless generating a template')
        updated = apply_reports(packet, json.loads(Path(args.reports).read_text()))
    temporary = output.with_suffix('.tmp')
    temporary.write_text(json.dumps(updated, indent=2)+'\n')
    temporary.replace(output)
    print(json.dumps({'status':'unverified_template' if args.template else 'reports_imported','output':str(output),
                      'publication_approved':False,'next':'read sources and fill template' if args.template else 'research_packet.py audit'}))


if __name__ == '__main__':
    main()
