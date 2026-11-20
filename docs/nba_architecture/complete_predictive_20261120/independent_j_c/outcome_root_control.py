"""Direct second-source-path mutation must not extend the frozen C outcome root."""
from pathlib import Path
import importlib.util,json,tempfile
H=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('independent_J_C_review_inputs',H/'review_probe.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as t:
 bad=Path(t)/'unreviewed_profile';bad.write_bytes((m.P/'independent_c_profile/DECISION.json').read_bytes()+b' ')
 args=dict(m.ARGS);outcomes=dict(args['outcome_inputs']);outcomes['profile_path']=bad;args['outcome_inputs']=outcomes
 try:m.C.read_J_for_C(**args)
 except ValueError as error:
  assert str(error)=='C_UNREVIEWED_EVIDENCE_PROFILE'
  result=dict(mutation='Independent outcome source path supplied an unreviewed profile',rejected=str(error),new_J_runs=0,new_forecasts_issued=0,new_fit_artifacts_created=0,output_scores=0)
 else:raise AssertionError('unreviewed C source profile accepted')
print(json.dumps(result,indent=2,sort_keys=True));(H/'OUTCOME_ROOT_CONTROL.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
