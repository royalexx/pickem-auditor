"""Independent exact native C source transport, pending replay and score mechanics."""
from pathlib import Path
from unittest.mock import patch
import collections,copy,importlib.util,json,math,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from v2.nba_architecture import conditional_c_v1 as c
from v2.nba_architecture.prospective_s_sources_v1 import next_data
from v2.nba_architecture.full_played_s_v1 import FullPlayedLaw
P=ROOT/'docs/nba_architecture/complete_predictive_20261120';HERE=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location('inputs',P/'inputs.py');i=importlib.util.module_from_spec(s);s.loader.exec_module(i);RESULT={}
class IndependentC(unittest.TestCase):
 def test_01_genuine_public698_all_counts_states_clocks(self):
  out=c.read_native_outcomes(**i.outcome_inputs());self.assertEqual(out['source_row_denominator'],698);self.assertEqual(out['state_denominators'],{'PLAYED_REPORTED_POSITIVE':459,'DNP_EXPLICIT':68,'UNKNOWN_PARTICIPATION':5,'SOURCE_LISTED_INACTIVE':166});index={(r['native_game_id'],r['native_team_id'],r['native_player_id']):r for r in out['rows']};self.assertEqual(len(index),698);self.assertFalse(out['complete_eligible_roster_claim']);self.assertEqual(out['historical_new_model_PIT_eligible'],0);self.assertEqual(out['C_reader_raw_sha256'],c.digest(Path(c.__file__).read_bytes()))
  for name in json.loads((P/'PBP_POPULATION.json').read_bytes())['sources']:
   gid=name[4:];g=next_data((P/'raw'/name/'body.raw').read_bytes())['game'];receipt=json.loads((P/'raw'/name/'receipt.json').read_bytes())
   for side in ('homeTeam','awayTeam'):
    t=g[side]
    for inactive,persons in ((False,t['players']),(True,t.get('inactives',[]))):
     for person in persons:
      row=index[(gid,str(t['teamId']),str(person['personId']))];self.assertEqual(row['source_body_sha256'],c.digest((P/'raw'/name/'body.raw').read_bytes()));self.assertEqual(row['observation_at'],receipt['retrieval_completed_at']);self.assertEqual(row['ingested_at'],receipt['ingested_at'])
      for k in ('official_end_at','outcome_released_at','source_published_at','predecessor_sha256','correction_history_complete','exact_true_minutes'):self.assertIsNone(row[k])
      self.assertFalse(row['true_clock_zero_confirmed'])
      if inactive:self.assertIsNone(row['reported_counts']);self.assertIsNone(row['played_conditional_counts'])
      else:
       self.assertEqual(len(row['reported_counts']),14)
       for field,val in row['reported_counts'].items():self.assertEqual(val,person['statistics'][field])
       if row['participation_state']!='PLAYED_REPORTED_POSITIVE':self.assertIsNone(row['played_conditional_counts'])
  (HERE/'native_outcomes.json').write_bytes(c.canonical(out));RESULT['native']={k:v for k,v in out.items() if k not in ('rows','games')}
 def test_02_actual_issued140_pending_postevent_safe_no_generation(self):
  full=(P/'actual_full_forecast/forecast.json').read_bytes();parent=(i.ARCHIVE/'forecast.json').read_bytes()
  with patch('v2.nba_architecture.full_predictive_runtime_v1.issue_forecast',side_effect=AssertionError('NO_NEW_ISSUANCE')),patch('v2.nba_architecture.full_predictive_candidate_v1.build_full_candidate',side_effect=AssertionError('NO_NEW_CANDIDATE')):
   result=c.replay_and_pending(full,parent,full_inputs=i.full_inputs(),outcome_inputs=i.outcome_inputs())
  self.assertEqual((result['attempt_denominator'],result['forecasted_rows'],result['forecast_abstentions'],result['pending_outcomes'],result['scored_rows']),(140,56,84,140,0));self.assertEqual(len({(r['player_id'],r['statistic']) for r in result['rows']}),140);self.assertTrue(all(r['score'] is None and r['outcome_status'].startswith('PENDING') for r in result['rows']));self.assertFalse(result['new_forecast_issued']);self.assertFalse(result['scoring_admitted']);self.assertEqual(result['historical_PIT_eligible'],0);(HERE/'actual_pending_replay.json').write_bytes(c.canonical(result));RESULT['replay']={k:v for k,v in result.items() if k!='rows'}
 def test_03_every_pinned_helper_byte_drift_rejects(self):
  original=Path.read_bytes
  for helper in list(c.SOURCE_HELPER_SHA)+['pbp_evidence_v1.py']:
   target=(Path(c.__file__).parent/helper).resolve()
   def changed(path):return original(path)+(b'\n# simulated byte drift\n' if path.resolve()==target else b'')
   with self.subTest(helper=helper),patch.object(Path,'read_bytes',changed),self.assertRaisesRegex(ValueError,'C_SOURCE_HELPER_CODE|C_UNREVIEWED_NATIVE_READER'):c.read_native_outcomes(**i.outcome_inputs())
 def test_04_immutable_source_profile_and_forecast_mutations_reject(self):
  original=Path.read_bytes;kw=i.outcome_inputs();pop=json.loads((P/'PBP_POPULATION.json').read_bytes());name=next(iter(pop['sources']));targets=[P/'raw'/name/'body.raw',P/'raw'/name/'receipt.json',kw['original_raw_dir']/('nba-box-'+name[4:])/'body.raw',kw['original_raw_dir']/('nba-box-'+name[4:])/'receipt.json',kw['profile_path'],kw['spec_path'],kw['population_path']]
  for target in targets:
   def changed(path):return original(path)+(b' ' if path.resolve()==target.resolve() else b'')
   with self.subTest(target=str(target)),patch.object(Path,'read_bytes',changed),self.assertRaises(ValueError):c.read_native_outcomes(**kw)
  raw=(P/'actual_full_forecast/forecast.json').read_bytes();parent=(i.ARCHIVE/'forecast.json').read_bytes()
  for forged in (raw+b' ',b'{"new_forecast_issued":false,'+raw[1:]):
   with self.assertRaises(ValueError):c.replay_and_pending(forged,parent,full_inputs=i.full_inputs(),outcome_inputs=kw)
 def test_05_score_and_threshold_mechanics_no_actual_outcome_admission(self):
  model=dict(alpha=10.,beta=20.,minutes=dict(mean=20.,variance=8.,ot_probability=.1,ot_continuation=.2));law=FullPlayedLaw(**model);pmf=law.query(list(range(9)))['probabilities'];score=c.score_count(model,7);self.assertEqual(score['status'],'NUMERICAL_SCORE_MECHANICS_ONLY');self.assertAlmostEqual(score['negative_log_score'],-math.log(pmf[7]),7)
  for line in ('0','7','7.5'):
   r=c.threshold_probabilities(model,line);self.assertFalse(r['offered_quote_available']);self.assertFalse(r['rare_tail_relative_precision_accepted']);self.assertAlmostEqual(r['over']+r['under']+r['push'],1,9)
   if line=='7':self.assertAlmostEqual(r['under'],sum(pmf[:7]),8);self.assertAlmostEqual(r['push'],pmf[7],8)
   if line=='7.5':self.assertAlmostEqual(r['under'],sum(pmf[:8]),8);self.assertEqual(r['push'],0)
  self.assertEqual(c.score_count(dict(model,zero_prior_mean=1.),1)['negative_log_score'],'POSITIVE_INFINITY');self.assertEqual(c.score_count(model,1000000)['status'],'NO_SCORE_NUMERICAL_UNRESOLVED')
  for count in (True,-1,1.5):
   with self.subTest(count=count),self.assertRaises(ValueError):c.score_count(model,count)
 def test_06_empirical_crps_exact_brute_force_not_population_tail(self):
  for samples,y in (([0,2,5,5],3),([0,0],100),([1,1,1],1),([10,1,0,7,9],6)):
   n=len(samples);r=c.empirical_scores(samples,y);a=sum(abs(x-y) for x in samples)/n;b=sum(abs(x-z) for x in samples for z in samples);self.assertAlmostEqual(r['empirical_crps'],a-b/(2*n*n));self.assertAlmostEqual(r['fair_ensemble_crps'],a-b/(2*n*(n-1)));self.assertFalse(r['population_zero_probability_claim']);self.assertFalse(r['rare_event_log_score_resolved']);self.assertFalse(r['epsilon_clipped'])
  self.assertEqual(c.empirical_scores([0,2],3)['empirical_negative_log_score'],'POSITIVE_INFINITY_EMPIRICAL_MEASURE')
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(IndependentC));RESULT.update(test_methods=result.testsRun,failures=len(result.failures),errors=len(result.errors));(HERE/'RESULTS.json').write_text(json.dumps(RESULT,sort_keys=True,indent=2)+'\n');sys.exit(not result.wasSuccessful())
