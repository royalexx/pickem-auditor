"""Independent frozen issuance/replay and residual O review, no new forecast/J."""
from pathlib import Path
from fractions import Fraction
from types import ModuleType
from unittest.mock import patch
from datetime import datetime,timezone
import copy,json,math,sys,tempfile,unittest
import numpy as np
import mpmath as mp
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from scripts.nba_genuine_s import frozen_inputs
from v2.nba_architecture.full_predictive_replay_v2 import read_issued_forecast
from v2.nba_architecture import full_predictive_runtime_v1 as issuer
from v2.nba_joint import residual_opportunity_v1 as O
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
P=ROOT/'docs/nba_architecture/complete_predictive_20261120';H=Path(__file__).resolve().parent;OLD=ROOT/'docs/nba_architecture/genuine_s_prospective_20261120/corrected_archive'
parent_raw=(OLD/'forecast.json').read_bytes();parent=json.loads(parent_raw);raw=(P/'actual_full_forecast/forecast.json').read_bytes();issued=json.loads(raw);RESULT={}
inputs=dict(law_snapshot_path=P/'FULL_S_CANDIDATE.json',cohort=json.loads((P/'FULL_FORECAST_COHORT.json').read_bytes()),admission_path=P/'independent_full_law/ADMISSION.json',original_inputs=dict(frozen_inputs(OLD),forecast_at=parent['forecast_at']),pbp_raw_dir=P/'raw',pbp_population_path=P/'PBP_POPULATION.json',model_card_path=P/'FULL_PLAYED_MODEL_CARD.json',protocol_path=P/'independent_protocol/DECISION.json')
minutes={r['player_id']:r['forecast']['distribution'] for r in parent['minutes'] if r['forecast']};named={r['player_id']:dict(player_id=r['player_id'],team_id=r['team_id'],name=r['name'],minutes=minutes[r['player_id']]) for r in issued['law_payload']['rows'] if r['model']};teams={t:[r for r in named.values() if r['team_id']==t] for t in {r['team_id'] for r in named.values()}}
def shape(d):
 p,q=map(mp.mpf,[d['ot_probability'],d['ot_continuation']]);ek=p/(1-q);ek2=p*(1+q)/(1-q)**2;s=mp.mpf(d['mean'])/(48+5*ek);v=min(max(mp.mpf('0.000001'),(mp.mpf(d['variance'])-s*s*25*(ek2-ek*ek))/(2304+480*ek+25*ek2)),mp.mpf('.95')*s*(1-s));c=s*(1-s)/v-1;return s*c,(1-s)*c
class Review(unittest.TestCase):
 def test_01_actual_issuance_and_post_event_safe_exact_replay(self):
  r=json.loads((P/'actual_full_forecast/ISSUANCE_RECEIPT.json').read_bytes());a=json.loads((P/'independent_full_law/ADMISSION.json').read_bytes())
  self.assertEqual(digest(raw),r['forecast_raw_sha256']);self.assertEqual(issued['payload_sha256'],r['forecast_payload_sha256']);self.assertLessEqual(a['model_admitted_at'],issued['input_freeze_at']);self.assertLessEqual(issued['input_freeze_at'],issued['forecast_at']);self.assertLess(issued['forecast_at'],r['calculation_completed_at']);self.assertLess(r['calculation_completed_at'],issued['event_start_at'])
  self.assertEqual((r['candidates'],r['attempts'],r['forecasted'],r['abstentions']),(35,140,56,84));self.assertTrue(issued['new_forecast_issued']);self.assertFalse(issued['production_release'])
  # This dependency raises if transport tries to regenerate any pre-event candidate.
  with patch.object(issuer,'build_full_candidate',side_effect=AssertionError('TRANSPORT_REGENERATED_FORECAST')):
   verified=read_issued_forecast(raw,parent_raw,**inputs)
  self.assertEqual(verified['status'],'VERIFIED_FROZEN_FORECAST_POST_EVENT_SAFE');self.assertFalse(verified['new_forecast_issued']);RESULT['actual_verified_issue']=verified
 def test_02_issued_byte_and_snapshot_mutations_and_write_once(self):
  for key,value in [('production_release',True),('forecast_at','2026-11-23T01:00Z'),('genuine_participation_probability',1.),('schema','wrong')]:
   bad=copy.deepcopy(issued);bad[key]=value
   with self.subTest(key=key),self.assertRaisesRegex(ValueError,'FROZEN_FORECAST_BYTES'):read_issued_forecast(canonical(bad),parent_raw,**inputs)
  with tempfile.TemporaryDirectory() as temp:
   temp=Path(temp);snapshot=temp/'snapshot';snapshot.write_bytes((P/'FULL_S_CANDIDATE.json').read_bytes()+b' ')
   args=dict(inputs);args['law_snapshot_path']=snapshot
   with self.assertRaisesRegex(ValueError,'LAW_SNAPSHOT_BYTES'):read_issued_forecast(raw,parent_raw,**args)
  before={p.name:p.read_bytes() for p in (P/'actual_full_forecast').iterdir()}
  with self.assertRaises(FileExistsError):issuer.issue_forecast(P/'actual_full_forecast',parent_raw)
  self.assertEqual(before,{p.name:p.read_bytes() for p in (P/'actual_full_forecast').iterdir()})
 def test_03_independent_capacity_upper_brackets_all_wrap_limits(self):
  mp.mp.dps=70;certificates=[]
  for tid,players in sorted(teams.items()):
   c=O.capacity_certificate(players);ids=sorted(p['player_id'] for p in players);byid={p['player_id']:p for p in players};n=len(ids);upper=[]
   self.assertEqual(c['queries'],49)
   for row in c['wrap_limits']:
    j=ids.index(row['wrapping_player']);total=mp.mpf(0)
    for i,pid in enumerate(ids):
     probability=(Fraction(-j,n)+Fraction(i,n))%1
     if probability==0:bound=mp.mpf(1)
     else:
      # Coarse upward bracket leaves >.9 share capacity slack. Its CDF is
      # checked independently at70 digits rather than trusting a1e-8 PPF claim.
      bound=mp.mpf(math.ceil(row['shares'][pid]*1000))/1000;a,b=shape(byid[pid]['minutes']);cdf=mp.betainc(a,b,0,bound,regularized=True)
      self.assertGreater(cdf,mp.mpf(probability.numerator)/probability.denominator)
     total+=bound
    self.assertLess(total,5);upper.append(float(total))
   certificates.append(dict(team_id=tid,public_upper=c['conservative_numeric_upper_share'],independent_upward_grid_upper=max(upper),queries=c['queries'],capacity_slack=5-max(upper)))
  RESULT['capacity_certificates']=certificates
 def test_04_draws_preserve_exact_sampled_minutes_and_contiguous_witness(self):
  rng=np.random.default_rng(20261120);checks=[];max_error=0.;adjustments=0
  for tid,players in sorted(teams.items()):
   for length in (48.,53.,58.):
    for z in (None,0.,.001,.01,.05,.1,1.):
     for _ in range(8):
      draw=O.draw_team(players,length,rng,fixed_zero_weight=z);audit=O.audit_team(draw,length);self.assertEqual(audit['violations'],0);self.assertFalse(draw['renormalized_named_exposures']);self.assertIsNone(draw['genuine_participation_probability'])
      ordered=sorted(players,key=lambda p:p['player_id']);u=draw['uniform_draw'];integrated=[0.]*len(draw['actors']);previous=0.
      for s in draw['segments']:
       self.assertEqual(s['start'],previous);previous=s['end']
       for i in s['player_indices']:integrated[i]+=s['end']-s['start']
      self.assertEqual(previous,length);error=max(abs(a-b) for a,b in zip(integrated,draw['minutes']));max_error=max(max_error,error);self.assertLess(error,1e-7)
      adjustments+=len(draw['witness_boundary_roundoff_adjustments'])
      for i,player in enumerate(ordered):
       v=(u+i/len(ordered))%1;pz=draw['actors'][i]['zero_weight_model_draw'];m=draw['minutes'][i]
       if v<=pz:self.assertEqual(m,0.)
       else:
        a,b=shape(player['minutes']);cdf=mp.betainc(a,b,0,mp.mpf(m)/length,regularized=True);self.assertLess(abs(float(cdf)-(v-pz)/(1-pz)),1e-10)
      checks.append(dict(team_id=tid,length=length,zero_scenario='PRIOR_DRAW' if z is None else z,minute_error=error))
  RESULT.update(draws_checked=len(checks),max_actor_witness_error_minutes=max_error,disclosed_boundary_adjustments=adjustments)
 def test_05_old_bad_boundaries_and_repaired_rejections(self):
  old=ModuleType('review_old_O');old.__file__=str(H/'OLD_O.py');exec(compile((H/'OLD_O.py').read_bytes(),old.__file__,'exec'),old.__dict__);players=copy.deepcopy(next(iter(teams.values())));mixed=copy.deepcopy(players);mixed[-1]['team_id']='DIFFERENT_TEAM';family=copy.deepcopy(players);family[0]['minutes']['family']='truncated_lognormal'
  prior=old.draw_team(mixed,49,np.random.default_rng(1),fixed_zero_weight=.01);self.assertEqual(old.audit_team(prior,49)['violations'],0);old.capacity_certificate(family)
  controls=[]
  for label,p,length in [('mixed_team',mixed,48),('unsupported_family',family,48),('duration49',players,49),('boolean_duration',players,True)]:
   with self.subTest(label=label),self.assertRaises(ValueError) as error:O.draw_team(p,length,np.random.default_rng(1),fixed_zero_weight=.01)
   controls.append(dict(mutation=label,rejected=str(error.exception)))
  draw=O.draw_team(players,48,np.random.default_rng(1),fixed_zero_weight=.01);draw['actors'][-1]['player_id']='fabricated-real-id'
  with self.assertRaisesRegex(ValueError,'FAKE_PLAYER_ID'):O.audit_team(draw,48)
  base=O.draw_team(players,48,np.random.default_rng(1),fixed_zero_weight=.01)
  for label,idx,change in [('unknown_kind',-1,dict(kind='UNKNOWN')),('missing_named_id',0,dict(player_id=None)),('residual_slot_bool',-1,dict(residual_slot_index=True)),('wrong_residual_group',-1,dict(residual_group='FAKE_GROUP'))]:
   bad=copy.deepcopy(base);bad['actors'][idx].update(change)
   with self.subTest(label=label),self.assertRaises(ValueError) as error:O.audit_team(bad,48)
   controls.append(dict(mutation=label,rejected=str(error.exception)))
  RESULT['O_boundary_controls']=controls
if __name__=='__main__':
 RESULT.update(started_at=datetime.now(timezone.utc).isoformat(),reviewed_source_sha256={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in [ROOT/'v2/nba_joint/residual_opportunity_v1.py',ROOT/'v2/nba_architecture/full_predictive_replay_v2.py',ROOT/'v2/nba_architecture/full_predictive_runtime_v1.py']})
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Review));RESULT.update(completed_at=datetime.now(timezone.utc).isoformat(),test_methods=result.testsRun,failures=len(result.failures),errors=len(result.errors),new_forecasts_issued=0,J_count_draws=0,new_fit_artifacts_created=0)
 (H/'RESULTS.json').write_text(json.dumps(RESULT,indent=2,sort_keys=True)+'\n');sys.exit(not result.wasSuccessful())
