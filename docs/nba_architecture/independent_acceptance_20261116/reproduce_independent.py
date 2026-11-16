"""Portable rerun of the unchanged independent campaigns against the reviewed SHA."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

SHA = '59d28dc23be97de2a6a82d22be8338151e31f5b6'
packet = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--checkout', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
checkout = args.checkout.resolve()
out = args.out.resolve()
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checkout, text=True).strip() == SHA
assert subprocess.check_output(['git', 'status', '--porcelain'], cwd=checkout, text=True) == ''
assert not out.exists(), 'Use a fresh output directory to preserve prior evidence'
assert not out.is_relative_to(checkout), 'Write audit outputs outside the implementation checkout'
out.mkdir(parents=True)
manifest = json.loads((packet / 'artifact_manifest.json').read_text())
runs = []
with tempfile.TemporaryDirectory(prefix='g0-independent-campaigns-') as directory:
    for script, output, count in (
        ('prior_campaign.py', 'prior-campaign', 47),
        ('new_oracles.py', 'new-oracles', 1060),
        ('full_boundary_cases.py', 'full-boundaries', 198),
    ):
        raw = (packet / script).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == manifest[script], script
        code = raw.decode().replace('/workspace/work/evidence157', str(out))
        adjusted = Path(directory) / script
        adjusted.write_text(code)
        command = [sys.executable, str(adjusted)]
        if script == 'prior_campaign.py':
            command += ['--out', str(out / output)]
        completed = subprocess.run(command, cwd=checkout, capture_output=True, text=True)
        (out / (script + '.log')).write_text(completed.stdout + completed.stderr)
        assert completed.returncode == 0, (script, completed.returncode)
        result_file = out / output / ('independent_results.json' if script == 'prior_campaign.py' else 'results.json')
        result = json.loads(result_file.read_text())
        assert result['total_cases'] == result['matched'] == count
        runs.append(dict(script=script, source_script_sha256=manifest[script], cases=count, matched=count))
assert subprocess.check_output(['git', 'status', '--porcelain'], cwd=checkout, text=True) == ''
receipt = dict(source_commit=SHA, independent_cases=1305, matched=1305, runs=runs,
               implementation_changed=False, output_directory=str(out))
(out / 'portable-rerun.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
