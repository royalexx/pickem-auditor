"""Independent deterministic real-source execution replay and discrepancy sums."""
from pathlib import Path
import collections,json,math,sys,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from v2.nba_joint import residual_events_v1 as e
from v2.nba_joint.residual_audit_v1 import audit_run
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.full_played_s_v1 import FullPlayedLaw
from v2.nba_opportunity import utc
P=ROOT/'docs/nba_architecture/complete_predictive_20261120';A=P/'actual_j_candidate';HERE=Path(__file__).resolve().parent;RESULT={}
class ActualJ(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.model_raw=(P/'fitted_j/event_model.json').read_bytes();cls.model=json.loads(cls.model_raw);cls.raw=(A/'RUN.json').read_bytes();cls.sample=json.loads(cls.raw);cls.full=json.loads((P/'actual_full_forecast/forecast.json').read_bytes());cls.diag=json.loads((A/'DISCREPANCY.json').read_bytes())
 def test_01_real_source_model_exact_execution_replay_and_accounting(self):
  admission=json.loads((P/'independent_j_artifact/ARTIFACT_ADMISSION.json').read_bytes());receipt=json.loads((A/'EXECUTION_RECEIPT.json').read_bytes());cohort=json.loads((A/'COHORT.json').read_bytes());self.assertEqual(digest(self.model_raw),admission['model_raw_sha256']);self.assertEqual(digest((P/'independent_j_artifact/ARTIFACT_ADMISSION.json').read_bytes()),receipt['model_admission_sha256']);self.assertEqual(digest(self.raw),receipt['run_raw_sha256']);self.assertEqual(receipt['implementation_commit'],'20f79e89ae1365235fc2a7549b85d2997dd3338b');self.assertEqual(cohort['frozen_candidates'],self.full['cohort']['frozen_candidates']);self.assertEqual(cohort['freeze_at'],receipt['freeze_at']);self.assertLessEqual(utc(admission['admitted_at']),utc(receipt['freeze_at']));self.assertLessEqual(utc(receipt['freeze_at']),utc(receipt['started_at']));self.assertLessEqual(utc(receipt['started_at']),utc(receipt['completed_at']));self.assertLess(utc(receipt['completed_at']),utc(receipt['event_start_at']))
  seen=collections.defaultdict(list);original=e.event_path
  def observe(fixed,*args,**kw):seen[fixed['index']].append(digest(canonical(fixed)));return original(fixed,*args,**kw)
  with patch.object(e,'event_path',observe):replay=e.simulate(self.model,seed=20261120,n=32,path_budget=4096,event_budget=4096)
  self.assertEqual(canonical(replay),self.raw);self.assertEqual(audit_run(self.sample),json.loads((A/'PHYSICS.json').read_bytes()));self.assertTrue(all(len(set(hashes))==1 for hashes in seen.values()));self.assertEqual((len(self.sample['scenarios']),self.sample['scenario_denominator'],len(self.sample['failed'])),(32,32,0));self.assertEqual(sum(len(s['proposals']) for s in self.sample['scenarios']),58);self.assertEqual(len(seen[18]),27);self.assertEqual(self.sample['scenarios'][18]['fixed']['overtime_count'],1);self.assertTrue(all(p['status']=='REJECT_OT_PATTERN' for p in self.sample['scenarios'][18]['proposals'][:-1]));self.assertEqual({s['fixed']['game_id'] for s in self.sample['scenarios']},{'401910026'});RESULT['real_execution']={'run_raw_sha256':digest(self.raw),'model_raw_sha256':digest(self.model_raw),'scenarios':32,'proposals':58,'OT_rejections':26,'OT_scenario_index':18,'failed':0,'fixed_same_across_each_rejection':True,'all_run_bytes_reproduced':True,'execution_receipt':receipt}
 def test_02_all56_reference_discrepancies_and84abstentions_recomputed(self):
  samples=collections.defaultdict(list);named={p['player_id'] for p in self.model['named_players']};self.assertEqual(len(named),14)
  for scenario in self.sample['scenarios']:
   for team,actors in scenario['fixed']['actors'].items():
    for a in actors:
     pid=a['identity']['player_id']
     if pid:
      for stat in ('points','rebounds','assists','threes'):samples[(pid,stat)].append(scenario['proposals'][-1]['counts'][team][a['index']][stat])
  references={(r['player_id'],r['statistic']):r['model'] for r in self.full['law_payload']['rows']};self.assertEqual(len(references),140);epsilon=math.sqrt(math.log(2*56/.05)/(2*32));self.assertAlmostEqual(epsilon,self.diag['simultaneous_MC_DKW95_half_width'],14);self.assertFalse(self.diag['marginal_fidelity_accepted']);self.assertFalse(self.diag['unchanged_S_marginals_claim']);self.assertEqual((self.diag['supported_rows'],self.diag['abstentions']),(56,84));checked=[]
  for row in self.diag['rows']:
   key=(row['player_id'],row['statistic']);ref=references[key]
   if ref is None:self.assertNotIn(key,samples);self.assertEqual(row['n'],0);continue
   values=samples[key];self.assertEqual(len(values),32);self.assertIn(key[0],named);law=FullPlayedLaw(**ref['rate_parameters'],minutes=ref['minute_parameters'],zero_prior_mean=ref['zero_prior_mean']);limit=max(max(values),128);grid=list(range(limit+1));masses=law.query(grid)['probabilities'];cdf=law.query(grid,kind='cdf')['probabilities'];tail=law.query([limit],kind='sf')['probabilities'][0];hist=collections.Counter(values);tv=(sum(abs(hist[k]/32-masses[k]) for k in grid)+tail)/2;gap=max(abs(sum(v<=k for v in values)/32-cdf[k]) for k in grid);mean=math.fsum(values)/32;sd=math.sqrt(math.fsum((x-mean)**2 for x in values)/31);self.assertAlmostEqual(row['partition_empirical_TV'],tv,12);self.assertAlmostEqual(row['empirical_CDF_max_difference'],gap,12);self.assertAlmostEqual(row['new_J_sample_mean'],mean,12);self.assertAlmostEqual(row['reference_S_mean'],law.moments()['mean'],12);self.assertAlmostEqual(row['sample_mean_MC_standard_error'],sd/math.sqrt(32),12);self.assertAlmostEqual(row['population_CDF_difference_lower_bound'],max(0,gap-epsilon),12);self.assertFalse(row['TV_fidelity_certificate']);checked.append({'player_id':key[0],'statistic':key[1],'empirical_TV':tv,'CDF_gap':gap,'mean_difference':mean-law.moments()['mean']})
  self.assertEqual(len(checked),56);RESULT['discrepancy']={'checked_supported_rows':56,'retained_abstentions':84,'simultaneous_DKW95_half_width':epsilon,'maximum_CDF_gap':max(r['CDF_gap'] for r in checked),'empirical_TV_min':min(r['empirical_TV'] for r in checked),'empirical_TV_max':max(r['empirical_TV'] for r in checked),'mean_difference_min':min(r['mean_difference'] for r in checked),'mean_difference_max':max(r['mean_difference'] for r in checked),'population_fidelity_accepted':False,'rows':checked}
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ActualJ));RESULT.update(methods=result.testsRun,errors=len(result.errors),failures=len(result.failures));(HERE/'ACTUAL_RESULTS.json').write_text(json.dumps(RESULT,sort_keys=True,indent=2)+'\n');sys.exit(not result.wasSuccessful())
