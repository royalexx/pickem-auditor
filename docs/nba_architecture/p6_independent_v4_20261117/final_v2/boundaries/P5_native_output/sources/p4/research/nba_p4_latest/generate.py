"""Create-only versioned synthetic artifact population using actual P2 fit.

No historical archive is opened. Raw synthetic source bytes remain separate
from their parsed documents and source-manifest digests.
"""
from copy import deepcopy
import json
from pathlib import Path

from v2.nba_architecture.v2_contracts import digest, receipt, seal
from v2.nba_joint.latest_upstream import FIXTURES, ROOT, load_upstream, prepare, raw_sha


def main():
    root = prepare()
    p2, p3 = load_upstream(root)
    old = json.loads((ROOT / 'research/nba_p4_integration/fixtures/inputs.json').read_bytes())
    p = deepcopy(old['pregame'])
    p.pop('content_hash')
    # This is a NEW fixture. The old source labels and old artifacts stay intact.
    raw_context = p2.canonical({'synthetic': True, 'game_id': p['game_id'],
        'home_team_id': p['team_ids'][0], 'team_ids': p['team_ids'],
        'availability': 'unknown', 'roster_completeness': 'unproven'})
    source = {k: v for k, v in p['sources'][0].items() if k != 'receipt_sha256'}
    source['raw_sha256'] = raw_sha(raw_context)
    source['source_id'] = 'synthetic:source:latest-context'
    source = receipt(source)
    p['sources'] = [source]
    feature = deepcopy(p['features'][0])
    feature.update(source_id=source['source_id'], source_receipt_sha256=source['receipt_sha256'],
                   name='home_team_id', value=p['team_ids'][0])
    p['features'] = [feature]
    p = seal(p)
    g = deepcopy(old['game_state']); g.pop('content_hash')
    g['source_snapshot_sha256'] = p['content_hash']
    g = seal(g)
    manifest, rows_by_stat, raw_sources = {}, {}, {}
    for stat, value in [('points', 18), ('rebounds', 7), ('assists', 4), ('threes', 2)]:
        rows = []
        for player in p['players']:
            for day in (10, 11, 12):
                game_id = f'synthetic:prior:{day}'
                available = f'2026-11-{day:02d}T22:00:00Z'
                raw = p2.canonical({'synthetic': True, 'game_id': game_id,
                    'player_id': player['player_id'], 'team_id': player['team_id'],
                    'stat': stat, 'count': value, 'minutes': 30., 'three_attempts': 6,
                    'overtime_periods': 0})
                receipt_hash = raw_sha(b'new-synthetic-fixture-receipt:' + raw)
                # P2's current fixture API says P1_VERIFIED. This is a literal
                # compatibility token inside an explicitly synthetic trust root.
                # It is never an external source-authentication claim.
                manifest[receipt_hash] = {'raw_sha256': raw_sha(raw),
                    'available_at': available, 'status': 'P1_VERIFIED',
                    'games': {game_id: {'overtime_periods': 0,
                        'game_start_at': f'2026-11-{day:02d}T18:00:00Z',
                        'players': {player['player_id']: player['team_id']},
                        'duration_receipt_sha256': receipt_hash}}}
                raw_sources[receipt_hash] = raw.decode('ascii')
                rows.append({'game_id': game_id, 'player_id': player['player_id'],
                    'team_id': player['team_id'], 'stat': stat, 'role': 'rotation',
                    'game_start_at': f'2026-11-{day:02d}T18:00:00Z',
                    'outcome_available_at': f'2026-11-{day:02d}T21:00:00Z',
                    'source_receipt_sha256': receipt_hash, 'source_raw_sha256': raw_sha(raw),
                    'count': value, 'minutes': 30., 'three_attempts': 6})
        rows_by_stat[stat] = rows
    artifacts = {}
    for name, stat, family in [('points','points','S1'), ('rebounds','rebounds','S1'),
            ('assists','assists','S2'), ('threes','threes','S1'),
            ('three_conversion','threes','S3')]:
        artifacts[name] = p2.fit(rows_by_stat[stat], asof_cutoff_utc=p['training_cutoff_at'],
            source_manifest=manifest, stat=stat, family=family, seed=17)
    priors = deepcopy(old['priors'])
    for player in p['players']:
        prior = priors[player['player_id']]
        prior.update(source_snapshot_sha256=p['content_hash'], team_id=player['team_id'],
            source_receipt_sha256=source['receipt_sha256'], source_bindings=[source['receipt_sha256']])
    roles = {r['player_id']: 'rotation' for r in p['players']}
    data = {'provenance': 'SYNTHETIC_ENGINEERING_ONLY_NO_EXTERNAL_SOURCE_AUTHENTICATION',
        'pregame': p, 'game_state': g, 'priors': priors, 'O_model': old['O_model'],
        'source_manifest': manifest, 'roles': roles}
    files = {'inputs.json': p2.canonical(data),
        'raw_sources.json': p2.canonical(raw_sources), 'context.raw': raw_context,
        **{k + '.json': v.payload for k, v in artifacts.items()}}
    trust = {'basis': 'synthetic_engineering_only', 'source_authentication': False,
        'artifacts': {k: raw_sha(v.payload) for k, v in artifacts.items()},
        'source_manifest_sha256': digest(manifest), 'roles_sha256': digest(roles),
        'pregame_sha256': p['content_hash'],
        'raw_sources_sha256': raw_sha(files['raw_sources.json']),
        'context_raw_sha256': raw_sha(raw_context)}
    files['trust.json'] = p2.canonical(trust)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for name, raw in files.items():
        with (FIXTURES / name).open('xb') as out:
            out.write(raw)
    print(json.dumps({'files': {k: raw_sha(v) for k,v in files.items()},
        'synthetic': True, 'historical_outcomes_accessed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
