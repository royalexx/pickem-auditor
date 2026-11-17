"""Materialize pinned owner source into work/, without editing owner paths.

Usage: python -m research.nba_p4_integration.prepare
Requires the exact pinned objects in the local repository. Does not fetch.
"""
import subprocess
from pathlib import Path
from v2.nba_joint.integration import PINS

ROOT = Path(__file__).resolve().parents[2]


def prepare():
    root = ROOT / 'work/upstream'
    sources = [(PINS['P2']['commit'], 'v2/nba_s_family/model.py'),
               (PINS['P2']['commit'], 'v2/nba_s_family/__init__.py'),
               (PINS['P3']['commit'], 'v2/nba_o_family.py'),
               (PINS['P3']['commit'], 'tests/nba_architecture/test_p3_o_family.py'),
               (PINS['P3']['commit'], 'tests/nba_architecture/golden_v2/joint_same_draw.json'),
               (PINS['P2']['commit'], 'tests/nba_s_family/test_statistical.py')]
    for commit, path in sources:
        raw = subprocess.check_output(['git', 'show', f'{commit}:{path}'], cwd=ROOT)
        destination = root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    for path in subprocess.check_output(['git', 'ls-tree', '-r', '--name-only',
            PINS['P6']['commit'], 'tests/nba_architecture'], cwd=ROOT, text=True).splitlines():
        if Path(path).name.startswith('test_p6_'):
            raw = subprocess.check_output(['git', 'show', f"{PINS['P6']['commit']}:{path}"], cwd=ROOT)
            destination = ROOT / 'work/qa' / Path(path).name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
    return root / 'v2'


if __name__ == '__main__':
    print(prepare())
