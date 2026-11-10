"""Offline check: complete immutable history seed, integrity, and idempotency."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "scripts/history_bootstrap.py"
spec = importlib.util.spec_from_file_location("history_bootstrap", MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@unittest.skipUnless(shutil.which("tar") and shutil.which("zstd"),
                     "External tar and zstd required; isolated Deepnote Basic CPU image lacks zstd")
class Bootstrapping(unittest.TestCase):
    def seed(self, root: Path, lines: int = 1492):
        origin = root / 'origin'
        (origin / 'data/season').mkdir(parents=True)
        (origin / 'data/usage').mkdir(parents=True)
        (origin / 'data/season/nfl_2026.sqlite3').write_bytes(b'database')
        (origin / 'data/usage/example.json').write_text('{}')
        (origin / 'data/archive_manifest.json').write_text(json.dumps({'schema': 'pickem-history-archive-v1'}))
        (origin / 'data/handoff-summary.json').write_text('{}')
        (origin / 'data/prop_snapshots.jsonl').write_text(''.join(json.dumps({
            'game_date':'2026-10-26', 'forecast_at':'2026-10-26T21:30:16Z',
            'reference_line': 1.5, 'id': n
        })+'\n' for n in range(lines)))
        packed = root / 'data.tar.zst'
        subprocess.run(['tar','-I','zstd','-cf',str(packed),'-C',str(origin),'data'],check=True)
        raw = packed.read_bytes()
        directory = root / 'archive'
        directory.mkdir()
        parts=[]
        for j in range(90):
            start=(len(raw)*j)//90
            end=(len(raw)*(j+1))//90
            chunk=raw[start:end]
            path=directory / f'part{j:03d}.bin'
            path.write_bytes(chunk)
            parts.append({'path':f'archive/2026-10-26/part{j:03d}.bin',
                          'sha256':hashlib.sha256(chunk).hexdigest(),'bytes':len(chunk)})
        (directory/'manifest.json').write_text(json.dumps({
            'schema':'pickem-history-full-v1',
            'sha256':hashlib.sha256(raw).hexdigest(),
            'bytes':len(raw), 'files':parts
        }))
        return directory

    def test_restore_and_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            source=self.seed(root)
            dst=root/'workspace'
            report=module.bootstrap(source,dst)
            self.assertEqual(report['forecast_rows_original'],1492)
            self.assertEqual(len((dst/'data/prop_snapshots.jsonl').read_text().splitlines()),1492)
            digest=module._sha256(dst/'data/prop_snapshots.jsonl')
            again=module.bootstrap(source,dst)
            self.assertEqual(again['files_restored'],0)
            self.assertEqual(module._sha256(dst/'data/prop_snapshots.jsonl'),digest)

    def test_modified_archive_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=self.seed(root)
            piece=source/'part002.bin';piece.write_bytes(piece.read_bytes()+b'X')
            with self.assertRaises(module.HistoryError):
                module.bootstrap(source,root/'workspace')

    def test_missing_forecast_rows_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=self.seed(root,lines=10)
            with self.assertRaises(module.HistoryError):
                module.bootstrap(source,root/'workspace')

if __name__=='__main__':
    unittest.main()