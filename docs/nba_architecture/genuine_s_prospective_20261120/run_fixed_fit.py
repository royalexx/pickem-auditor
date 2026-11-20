"""One actual, create-only, independently pre-approved prospective baseline."""
import json
from pathlib import Path
from v2.nba_s_family.prospective_fit_v1 import fit_prospective

root=Path(__file__).resolve().parent
print(json.dumps(fit_prospective(root/'raw',root/'PREFIT_POPULATION.json',
    root/'policy/nba_rule5.raw',root/'independent_prefit/PREFIT_APPROVAL.json',
    root/'fitted'),sort_keys=True,indent=2))
