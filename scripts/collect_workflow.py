#!/usr/bin/env python3
"""Collect all supported sports, prepare common inputs, and scan; never approve picks."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def run_stage(name, args, directory, environment, input_path=None):
    output = directory / (name + '.json' if name != 'prep' else 'prep.jsonl')
    with output.open('w') as out, (directory / (name + '.stderr.log')).open('w') as err:
        source = input_path.open() if input_path else None
        try:
            result = subprocess.run([sys.executable, *args], cwd=ROOT, env=environment,
                                    stdin=source, stdout=out, stderr=err, check=False)
        finally:
            if source:
                source.close()
    return {'name': name, 'returncode': result.returncode, 'output': str(output)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', required=True, help='Slate date YYYY-MM-DD, America/Toronto')
    parser.add_argument('--data-dir', default=str(ROOT / 'data'))
    args = parser.parse_args(argv)
    datetime.strptime(args.date, '%Y-%m-%d')
    data = Path(args.data_dir).resolve()
    run = data / 'collection_runs' / (args.date + '-' + uuid4().hex)
    run.mkdir(parents=True)
    environment = dict(os.environ, PICKEM_DATA_DIR=str(run))
    manifest = {'date': args.date, 'started_at': datetime.now(timezone.utc).isoformat(),
                'status': 'running', 'research_complete': False, 'stages': [],
                'sources': {'NFL': 'nflreadpy', 'NHL': 'nhl-api-py and NHL REST', 'NBA': 'ESPN'}}
    path = run / 'manifest.json'

    def save():
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(manifest, indent=2) + '\n')
        temp.replace(path)

    save()
    slate = run / 'slate_fetch.jsonl'
    stages = [
        ('collect', ['scripts/fetch_slate.py', '--date', args.date, '--out', str(slate)], None),
        ('prep', ['scripts/fetch_slate.py', 'prep', '--stdout', '--slate', str(slate)], None),
        ('scan', ['scripts/pickem_math.py', 'scan', '--stdin'], run / 'prep.jsonl'),
        ('research_queue', ['scripts/research_tasks.py', '--resolve', '--packet', str(run / ('research_' + args.date + '.json')), '--scan', str(run / 'scan.json'), '--prep', str(run / 'prep.jsonl')], None),
    ]
    try:
        for name, command, source in stages:
            result = run_stage(name, command, run, environment, source)
            manifest['stages'].append(result)
            save()
            if result['returncode']:
                manifest['status'] = 'blocked'
                manifest['failed_stage'] = name
                return result['returncode']
        collection = json.loads((run / 'collect.json').read_text())
        scan = json.loads((run / 'scan.json').read_text())
        manifest['coverage'] = collection.get('coverage', {})
        manifest['scan_counts'] = scan.get('counts', {})
        manifest['context'] = collection.get('context', {})
        manifest['status'] = 'research_required'
        return 0
    except (OSError, ValueError) as exc:
        manifest['status'] = 'failed'
        manifest['error_type'] = type(exc).__name__
        raise
    finally:
        manifest['finished_at'] = datetime.now(timezone.utc).isoformat()
        save()
        print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    raise SystemExit(main())
