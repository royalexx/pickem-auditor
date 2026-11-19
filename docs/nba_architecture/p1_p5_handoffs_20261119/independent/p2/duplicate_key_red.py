"""Exact c1ea2dc8 P2 consumer red: duplicate probability-count claim accepted."""
import json,pathlib,subprocess,tempfile
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,export_requests
ROOT=pathlib.Path(__file__).resolve().parents[5];CAP=ROOT/'docs/nba_architecture/p1_overnight_20261119/raw/pregame-20261118T234000059565Z-aae5f441';C=json.loads((ROOT/'docs/nba_architecture/p1_prospective_20261118/COHORT.json').read_bytes());source=canonical(export_requests(CAP,C));blob=subprocess.check_output(['git','show','c1ea2dc8bfdbbd48f3da54a6ff695161b7448f66:v2/nba_architecture/subset_p2_v1.py']);handle=tempfile.NamedTemporaryFile(suffix='.py');handle.write(blob);handle.flush();namespace={'__name__':'v2.nba_architecture.review_c1ea','__package__':'v2.nba_architecture','__file__':handle.name};exec(compile(blob,'c1ea2dc8:subset_p2_v1.py','exec'),namespace);run_p2=namespace['run_p2'];read_p2=namespace['read_p2'];value=run_p2(source,CAP,C);wire=b'{"forecasted_rows":1,'+canonical(value)[1:]
try:accepted=read_p2(wire,source_raw=source,capture_dir=CAP,cohort=C)
except ValueError:print('rejected duplicate claim');raise SystemExit(0)
print('ACCEPTED_AMBIGUOUS_DUPLICATE',accepted['forecasted_rows']);raise AssertionError('duplicate keys must not bypass source-bound consumer semantics')
