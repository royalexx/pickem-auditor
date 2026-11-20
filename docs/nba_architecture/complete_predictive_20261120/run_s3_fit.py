"""One exact independently pre-approved prospective S3 batch."""
from pathlib import Path
import json
from v2.nba_s_family.prospective_s3_fit_v1 import fit_new_s3

p=Path(__file__).resolve().parent
old=p.parent/'genuine_s_prospective_20261120'
print(json.dumps(fit_new_s3(old/'raw',old/'PREFIT_POPULATION.json',old/'policy/nba_rule5.raw',
    p/'independent_s3_prefit/PREFIT_APPROVAL.json',p/'fitted_s3'),sort_keys=True,indent=2))
