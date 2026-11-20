"""Old public J-C transport fails to read a changed RNG helper's bytes."""
from pathlib import Path
from types import ModuleType
from unittest.mock import patch
import json,sys
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from scripts.nba_genuine_s import frozen_inputs
from v2.nba_architecture.p1_subset_handoff_v1 import digest
P=ROOT/'docs/nba_architecture/complete_predictive_20261120';H=Path(__file__).resolve().parent;OLD=ROOT/'docs/nba_architecture/genuine_s_prospective_20261120/corrected_archive'
parent=(OLD/'forecast.json').read_bytes();original=dict(frozen_inputs(OLD),forecast_at=json.loads(parent)['forecast_at'])
full_inputs=dict(law_snapshot_path=P/'FULL_S_CANDIDATE.json',cohort=json.loads((P/'FULL_FORECAST_COHORT.json').read_bytes()),admission_path=P/'independent_full_law/ADMISSION.json',original_inputs=original,pbp_raw_dir=P/'raw',pbp_population_path=P/'PBP_POPULATION.json',model_card_path=P/'FULL_PLAYED_MODEL_CARD.json',protocol_path=P/'independent_protocol/DECISION.json')
outcome_inputs=dict(raw_dir=P/'raw',population_path=P/'PBP_POPULATION.json',original_raw_dir=original['raw_dir'],spec_path=original['spec_path'],profile_path=P/'independent_c_profile/DECISION.json')
args=dict(run_raw=(P/'actual_j_candidate/RUN.json').read_bytes(),receipt_raw=(P/'actual_j_candidate/EXECUTION_RECEIPT.json').read_bytes(),model_raw=(P/'fitted_j/event_model.json').read_bytes(),model_admission_raw=(P/'independent_j_artifact/ARTIFACT_ADMISSION.json').read_bytes(),full_raw=(P/'actual_full_forecast/forecast.json').read_bytes(),parent_raw=parent,full_inputs=full_inputs,outcome_inputs=outcome_inputs)
old=ModuleType('review_old_J_C');old.__package__='v2.nba_architecture'
# Keep normal module-relative helper resolution while executing only the
# preserved OLD_J_C snapshot. Its emitted self-file digest is not an admission.
old.__file__=str(ROOT/'v2/nba_architecture/conditional_j_c_v1.py');exec(compile((H/'OLD_J_C.py').read_bytes(),str(H/'OLD_J_C.py'),'exec'),old.__dict__)
target=(ROOT/'v2/nba_joint/common.py').resolve();read=Path.read_bytes;checks=[]
def changed(path):
 data=read(path)
 if path.resolve()==target:checks.append(str(path));return data+b'\n# REVIEW_SIMULATED_UNREVIEWED_HELPER_BYTES\n'
 return data
with patch.object(Path,'read_bytes',new=changed):result=old.read_J_for_C(**args)
assert not checks;assert result['all_market_attempts']==280 and result['actual_scores']==0
summary=dict(old_reader_snapshot_raw_sha256=digest((H/'OLD_J_C.py').read_bytes()),simulated_changed_helper=str(target.relative_to(ROOT)),helper_byte_reads_during_old_validation=len(checks),old_transport_returned_success=True,attempts=result['all_market_attempts'],supported=result['all_market_supported'],abstained=result['all_market_abstained'],scores=result['actual_scores'],no_implementation_file_writes=True,no_new_forecast_or_J_run=True)
print(json.dumps(summary,indent=2,sort_keys=True));(H/'CLOSURE_COUNTEREXAMPLE.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
