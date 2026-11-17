#!/usr/bin/env python3
"""Offline P1 archive reconciliation. Integrity and coverage, never scoring.

Requires the pinned WS1 manifest and immutable warehouse checkout. Does not
convert an archive digest into an original source receipt or infer any DNP.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nba_p1_source_preflight import preflight
from population_history import validate


def reconcile(manifest, root):
    proof = preflight(manifest, Path(root))
    if proof['status'] != 'SOURCE_BYTES_VERIFIED':
        raise ValueError('ARCHIVE_BYTES_NOT_VERIFIED')
    excluded = {x['game_id'] for x in manifest['quarantine']}
    seasons = defaultdict(lambda: dict(rows=0, excluded_rows=0, games=set(), player_games=set(),
                                      zero_minutes=0, over_48=set(), source_urls=set(), source_hashes=set()))
    identities = {}
    player_stats = defaultdict(dict)
    issues = Counter()
    sample = None
    calendar_pre_2022 = dict(rows=0, games=set(), player_games=set())
    for file in manifest['source_manifest']:
        seen = set()
        with gzip.open(Path(root) / file['path'], 'rt', encoding='utf-8') as f:
            for line in f:
                r = json.loads(line)
                try:
                    validate(r)
                except ValueError as e:
                    issues[str(e)] += 1
                    continue
                s = seasons[r['season']]
                if r['game_id'] in excluded:
                    s['excluded_rows'] += 1
                    continue
                key = (r['game_id'], r['player_id'])
                if key in seen:
                    issues['DUPLICATE_PLAYER_GAME_STAT'] += 1
                seen.add(key)
                ident = (r['team'], r['opponent'], r['game_date'], r['workload'])
                if key in identities and identities[key] != ident:
                    issues['CROSS_STAT_IDENTITY_OR_MINUTES'] += 1
                identities[key] = ident
                player_stats[key][r['stat']] = r['value']
                if r['game_date'] < '2022-01-01':
                    calendar_pre_2022['rows'] += 1
                    calendar_pre_2022['games'].add(r['game_id'])
                    calendar_pre_2022['player_games'].add(key)
                s['rows'] += 1
                s['games'].add(r['game_id']); s['player_games'].add(key)
                s['zero_minutes'] += r['workload'] == 0
                if r['workload'] > 48:
                    s['over_48'].add(key)
                s['source_urls'].add(r['source_url']);s['source_hashes'].add(r['source_sha256'])
                if sample is None:
                    sample = dict(shard_path=file['path'], shard_raw_sha256=file['sha256'],
                                  record=r, classification='REAL_ARCHIVE_ROW_NOT_ORIGINAL_OFFICIAL_BYTES')
    for stats in player_stats.values():
        for combo, keys in {'pr':('points','rebounds'),'pa':('points','assists'),
                            'ra':('rebounds','assists'),'pra':('points','rebounds','assists')}.items():
            if combo in stats and all(k in stats for k in keys) and stats[combo] != sum(stats[k] for k in keys):
                issues['COMBINATION_ACCOUNTING'] += 1
    cohorts = {}
    for name, years in {'training_pre_2022_season_end':('2019','2020','2021','2022'),
                        'development_2022_23':('2023',), 'validation_2023_24':('2024',)}.items():
        rows = [seasons[y] for y in years]
        cohorts[name] = dict(season_end_years=list(years),
            rows=sum(s['rows'] for s in rows), games=sum(len(s['games']) for s in rows),
            player_games=sum(len(s['player_games']) for s in rows),
            excluded_rows=sum(s['excluded_rows'] for s in rows),
            zero_minute_category_rows=sum(s['zero_minutes'] for s in rows),
            over_48_player_games=sum(len(s['over_48']) for s in rows),
            authenticated_official_duration_player_games=0,
            authenticated_original_pregame_context_games=0,
            complete_official_correction_chains=0,
            source_status='BLOCKED_ORIGINAL_OFFICIAL_AND_PREGAME_EVIDENCE_MISSING')
    calendar_pre_2022 = dict(rows=calendar_pre_2022['rows'],
                             games=len(calendar_pre_2022['games']),
                             player_games=len(calendar_pre_2022['player_games']),
                             cutoff_exclusive='2022-01-01')
    return dict(schema='nba-p1-archive-reconciliation/1.0.0', source_preflight=proof,
                strict_calendar_pre_2022=calendar_pre_2022,
                cohorts=cohorts, issues=dict(issues), real_archive_sample=sample,
                certification='HISTORICAL_RECONSTRUCTION_UNCERTIFIED',
                missing_denominators=['official_schedule_missing_results','eligible_roster_candidates','DNP','played_zero','unknown_participation'],
                warning='Population source_sha256 hashes canonical parsed source JSON, not original HTTP bytes. Training includes 2021-22; it is not a strict calendar-before-2022 split.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--warehouse-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    report=reconcile(json.loads(a.manifest.read_bytes()),a.warehouse_root)
    with a.output.open('x') as f:
        json.dump(report,f,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps(dict(cohorts=report['cohorts'],issues=report['issues']),sort_keys=True))
    return 2 if report['issues'] else 0

if __name__=='__main__':raise SystemExit(main())
