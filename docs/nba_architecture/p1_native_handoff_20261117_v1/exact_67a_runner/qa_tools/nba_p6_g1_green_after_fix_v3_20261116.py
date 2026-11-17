#!/usr/bin/env python3
"""Versioned expectations for IMMUTABLE 20261116 negative probe.

Run from an exact owner checkout with PYTHONPATH=.:tests/nba_architecture.
P2's historical fixture has no two-OT witness: its old explanation is historical,
not the current positive-control verdict. Use independent v3 witnessed tests too.
"""
import hashlib,json,subprocess,sys
from pathlib import Path
probe=Path(__file__).with_name('nba_p6_g1_owner_negative_probes_20261116.py')
assert hashlib.sha256(probe.read_bytes()).hexdigest()=='fa8012e260a21caacb2fcebadc02a2deddaf957bc4425b8128dcae2c83ba9e52'
family=sys.argv[1]
r=subprocess.run([sys.executable,str(probe),family],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
assert r.returncode==0,(r.returncode,r.stderr.decode())
d=json.loads(r.stdout)
if family=='P1':
 assert len(d['cases'])==3 and all(x['status']=='REJECTED' for x in d['cases']),d
elif family=='P5':
 statuses={x['case']:x for x in d['cases']}
 assert statuses['proper_2023_24_date']['code']=='2023_24_HOLDOUT_QUARANTINED'
 assert statuses['backdated_2022_date_with_2023_24_game']['code']=='INVALID_CHRONOLOGY'
 assert statuses['independent_math_oracles']['status']=='PASS'
elif family=='P2':
 assert d['cases'][0]['code']=='HISTORICAL_EXPOSURE_PHYSICS',d
else:raise ValueError('P1/P2/P5 only')
print(json.dumps(dict(family=family,status='PASS',probe_raw_sha256=hashlib.sha256(probe.read_bytes()).hexdigest(),probe_output_sha256=hashlib.sha256(r.stdout).hexdigest(),historical_fixture_unchanged=True,P2_requires_separate_witnessed_regression=True),sort_keys=True))
