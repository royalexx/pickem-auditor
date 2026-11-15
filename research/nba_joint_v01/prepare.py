"""Bounded input retrieval. Original bytes append-only; never a pregame capture."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import time
import urllib.request
import numpy as np

WAREHOUSE = '97a8bb566826afe5a3e5a7b8c632043d8a1dca24'
FRANCHISES = set('ATL BOS BKN CHA CHI CLE DAL DEN DET GS HOU IND LAC LAL MEM MIA MIL MIN NO NY OKC ORL PHI PHX POR SAC SA TOR UTAH WSH'.split())


def population(folder):
    rows = {}
    ledger = []
    quarantine={r['game_id'] for r in json.loads(Path('docs/nba_ws1/coverage.json').read_text())['quarantine']}
    for path in sorted(Path(folder).glob('*.jsonl.gz')):
        for line in gzip.open(path, 'rt'):
            r = json.loads(line)
            if r['game_id'] in quarantine:
                ledger.append({'game_id':r['game_id'],'player_id':r['player_id'],'stat':r['stat'],'reason':'WS1_SCOPE_QUARANTINE'});continue
            if r['team'] not in FRANCHISES or r['opponent'] not in FRANCHISES:
                ledger.append({'game_id': r['game_id'], 'player_id': r['player_id'], 'stat': r['stat'], 'reason': 'NON_FRANCHISE'}); continue
            k = (r['game_id'], r['player_id'])
            if k not in rows:
                rows[k] = {**r, 'stats': {}}
                rows[k].pop('stat'); rows[k].pop('value')
            x = rows[k]
            if any(x[f] != r[f] for f in ('team', 'opponent', 'game_date', 'workload', 'source_sha256', 'home')):
                raise ValueError('POPULATION_JOIN_CONFLICT')
            if r['stat'] in x['stats']: raise ValueError('DUPLICATE_POPULATION_STAT')
            x['stats'][r['stat']] = r['value']
    return sorted(rows.values(), key=lambda r: (r['game_date'], r['game_id'], r['player_id'])), ledger


def main():
    root = Path('work/joint_input'); cache = root/'raw'; cache.mkdir(exist_ok=True)
    rows, ledger = population(root)
    quarantine = {r['game_id'] for r in json.loads(Path('docs/nba_ws1/coverage.json').read_text())['quarantine']}
    games = {}
    for r in rows:
        if r['game_id'] not in quarantine: games[r['game_id']] = (r['game_date'], r['season'])
    train = sorted((d, g) for g, (d, s) in games.items() if s == '2024' and d < '2024-04-15')
    selected_train = [train[i] for i in np.linspace(0, len(train)-1, 32).astype(int)]
    byday = {}
    for g, (d, s) in sorted(games.items()):
        if s == '2025': byday.setdefault(d, g)
    selected_test = sorted(byday.items())[:24]
    original = json.loads(Path('work/ws4_original_replay.json').read_text()) if Path('work/ws4_original_replay.json').exists() else {'records': []}
    # WS4 event_id is the ORIGINAL market provider ID, not ESPN's game ID.
    # Resolve ONLY via WS4's independently checked official source hash/path.
    official={h:Path(p).name.split('_')[1] for p,h in original.get('source_hashes',{}).items() if '/official_source_raw/nba_' in p and 'boxscore' in p}
    selected_original = sorted({(r['date'],official[r['source_hash']]) for r in original['records']})
    tasks = [('train', *x) for x in selected_train] + [('test', *x) for x in selected_test] + [('original', *x) for x in selected_original]

    def get(task):
        split, day, gid = task
        path = cache/(gid+'.json')
        url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event='+gid
        result = dict(split=split, day=day, game_id=gid, url=url, origin='retrospective_retrieval')
        for attempt in range(2):
            try:
                if not path.exists():
                    req = urllib.request.Request(url, headers={'User-Agent': 'NBA-WS5-Bounded-Research/0.1'})
                    with urllib.request.urlopen(req, timeout=25) as response: raw = response.read()
                    with path.open('xb') as f: f.write(raw)
                raw = path.read_bytes(); data = json.loads(raw)
                c = data['header']['competitions'][0]
                if str(c['id']) != gid or not c['status']['type']['completed']: raise ValueError('NOT_MATCHED_FINAL')
                result.update(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), retrieved_at=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(), event_start_at=c['date'])
                return result
            except Exception as exc:
                if attempt: return {**result, 'error': str(exc)}
                time.sleep(.2)
    with ThreadPoolExecutor(max_workers=6) as pool: receipts = list(pool.map(get, tasks))
    manifest = dict(schema='nba-joint-inputs/1', warehouse=WAREHOUSE, shards=[{'path':str(p), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(root.glob('*.jsonl.gz'))], raw=receipts, quarantine=sorted(quarantine), population_exclusion_rows=len(ledger))
    with (root/'manifest.json').open('x') as f: json.dump(manifest, f, indent=2, sort_keys=True)
    print(json.dumps({'attempted':len(receipts), 'succeeded':sum('error' not in x for x in receipts), 'errors':[x for x in receipts if 'error' in x]}))


if __name__ == '__main__': main()
