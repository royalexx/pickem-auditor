"""Independent source-byte controls and the initial 1-CDF tail counterexample."""
from pathlib import Path
import json,sys,tempfile
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from v2.nba_architecture.pbp_evidence_v1 import read_population
from v2.nba_architecture.full_played_s_v1 import FullPlayedLaw
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
P=ROOT/'docs/nba_architecture/complete_predictive_20261120';H=Path(__file__).resolve().parent;OLD=ROOT/'docs/nba_architecture/genuine_s_prospective_20261120/corrected_archive'
current=json.loads((P/'FULL_S_CANDIDATE.json').read_bytes());initial=json.loads((P/'FULL_S_CANDIDATE_INITIAL.json').read_bytes());rows={(r['player_id'],r['statistic']):r for r in initial['rows']}
controls=[]
with tempfile.TemporaryDirectory() as temp:
 raw=Path(temp)/'raw';raw.mkdir();population=json.loads((P/'PBP_POPULATION.json').read_bytes())
 for name in population['sources']:
  dest=raw/name;dest.mkdir()
  for filename in ('body.raw','receipt.json'):(dest/filename).symlink_to((P/'raw'/name/filename).resolve())
 name=next(iter(population['sources']));body=raw/name/'body.raw';receipt=raw/name/'receipt.json';data=body.read_bytes();body.unlink();body.write_bytes(data+b' ')
 for mode in ('body_changed','body_and_receipt_self_resealed'):
  if mode.endswith('resealed'):
   r=json.loads(receipt.read_bytes());r['raw_sha256']=digest(body.read_bytes());r['bytes']=len(body.read_bytes());receipt.unlink();receipt.write_bytes(canonical(r))
  try:read_population(raw,P/'PBP_POPULATION.json',OLD/'inputs/raw')
  except ValueError as e:assert str(e)=='PBP_FROZEN_BYTES';controls.append(dict(mutation=mode,rejected=str(e)))
  else:raise AssertionError('tampered source accepted')
tails=[]
for row in current['rows']:
 model=row['model']
 if not model:continue
 old=rows[row['player_id'],row['statistic']]['model'];law=FullPlayedLaw(**model['rate_parameters'],minutes=model['minute_parameters']);larger=law.query([128],kind='sf',ot_terms=128)
 assert model['probability_beyond_display']>=0
 assert model['probability_beyond_display_method']=='DIRECT_NB_SURVIVAL_INTEGRAL_NOT_ONE_MINUS_CDF'
 assert model['probability_beyond_display_is_numerical_estimate']
 for kind in ('pmf','cdf','sf'):assert model['numerical'][kind]['value_interpretation']=='NUMERICAL_ESTIMATE_NOT_STRUCTURAL_ZERO_OR_ONE'
 low=model['probability_beyond_display'];high=larger['probabilities'][0];bound=model['numerical']['sf']['omitted_OT_probability_bound'];assert abs(high-low)<=bound+1e-12
 tails.append(dict(player=row['name'],statistic=row['statistic'],initial_one_minus_CDF=old['probability_beyond_display'],direct_SF32=low,direct_SF128=high,default_omitted_OT_absolute_bound=bound,default_bound_may_exceed_estimate=bound>low))
out=dict(initial_raw_sha256=digest((P/'FULL_S_CANDIDATE_INITIAL.json').read_bytes()),current_raw_sha256=digest((P/'FULL_S_CANDIDATE.json').read_bytes()),source_mutations=controls,tail_checks=tails,source_or_model_admission_granted=False)
print(json.dumps(out,indent=2,sort_keys=True));(H/'TAIL_SOURCE_RESULTS.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
