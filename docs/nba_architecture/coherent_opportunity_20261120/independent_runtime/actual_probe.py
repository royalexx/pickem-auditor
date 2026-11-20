"""Independent exact-source coherent bank replay, projections and reference sums."""
from pathlib import Path
import collections,importlib.metadata,json,math,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from v2.nba_joint import coherent_predictive_v1 as k
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.full_played_s_v1 import FullPlayedLaw
from v2.nba_opportunity import utc
P=ROOT/'docs/nba_architecture/coherent_opportunity_20261120';A=P/'actual';HERE=Path(__file__).resolve().parent;RESULT={}
class Actual(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.raw=(A/'BANK.json').read_bytes();cls.bank=json.loads(cls.raw);cls.model_raw=(P/'fitted/model.json').read_bytes();cls.model=json.loads(cls.model_raw);cls.receipt=json.loads((A/'EXECUTION_RECEIPT.json').read_bytes());cls.marginal=json.loads((A/'MARGINALS.json').read_bytes());cls.full=json.loads((P.parent/'complete_predictive_20261120/actual_full_forecast/forecast.json').read_bytes())
 def test_01_source_admission_clocks_traces_and_all64_exact_reproduction(self):
  r=self.receipt;a_raw=(P/'independent_artifact/ARTIFACT_ADMISSION.json').read_bytes();a=json.loads(a_raw);fit_raw=(P/'fitted/FIT_RECEIPT.json').read_bytes();fit=json.loads(fit_raw)
  self.assertEqual(digest(self.model_raw),r['model_raw_sha256']);self.assertEqual(digest(self.model_raw),a['model_raw_sha256']);self.assertEqual(digest(fit_raw),r['fit_receipt_raw_sha256']);self.assertEqual(digest(fit_raw),a['fit_receipt_raw_sha256']);self.assertEqual(digest(a_raw),r['model_admission_raw_sha256']);self.assertEqual(digest(self.raw),r['bank_raw_sha256']);self.assertEqual(self.bank['payload_sha256'],r['bank_payload_sha256']);self.assertEqual(self.bank['cohort'],json.loads((A/'COHORT.json').read_bytes()));self.assertEqual(self.bank['cohort']['frozen_candidates'],self.full['cohort']['frozen_candidates']);self.assertLessEqual(utc(fit['verified_at']),utc(a['admitted_at']));self.assertLessEqual(utc(a['admitted_at']),utc(r['freeze_at']));self.assertLessEqual(utc(r['freeze_at']),utc(r['started_at']));self.assertLessEqual(utc(r['started_at']),utc(r['completed_at']));self.assertLess(utc(r['completed_at']),utc(self.bank['cohort']['start']));self.assertEqual((len(self.bank['scenarios']),self.bank['scenario_denominator'],len(self.bank['failed'])),(64,64,0))
  for name in ('numpy','scipy'):self.assertEqual(importlib.metadata.version(name),r[name])
  self.assertEqual(set(r['artifact_raw_sha256']),{'BANK.json','COHORT.json','MARGINALS.json','COHERENCE.json','REFERENCE_COMPARISON.json'})
  for name,sha in r['artifact_raw_sha256'].items():self.assertEqual(digest((A/name).read_bytes()),sha)
  for name,sha in r['code_raw_sha256'].items():self.assertEqual(digest((ROOT/name).read_bytes()),sha)
  physics=k.validate_bank(self.bank,A/'trace',self.model)
  with tempfile.TemporaryDirectory() as temp:
   replica=k.generate(self.model,self.bank['cohort'],Path(temp)/'trace',seed=20261120,n=64,path_budget=4096,event_budget=4096);self.assertEqual(canonical(replica),self.raw);self.assertEqual(k.validate_bank(replica,Path(temp)/'trace',self.model),physics)
   for path in (A/'trace').glob('*.gz'):self.assertEqual(path.read_bytes(),(Path(temp)/'trace'/path.name).read_bytes())
  proposals=sum(len(s['proposals']) for s in self.bank['scenarios']);RESULT['execution']={'receipt':r,'model_raw_sha256':digest(self.model_raw),'bank_raw_sha256':digest(self.raw),'all64_bank_bytes_reproduced':True,'all_gzip_trace_bytes_reproduced':True,'scenarios':64,'paths':proposals,'OT_rejections':proposals-64,'OT_counts':dict(collections.Counter(s['fixed']['overtime_count'] for s in self.bank['scenarios'])),'physics':physics}
 def test_02_all280_rows_same_measure336_queries_and_168abstentions(self):
  projected=k.rows(self.bank);self.assertEqual(projected,self.marginal['rows']);self.assertEqual((len(projected),sum(r['samples'] is not None for r in projected)),(280,112));self.assertEqual((self.marginal['primitive_attempts'],self.marginal['primitive_supported'],self.marginal['primitive_abstained']),(140,56,84));self.assertEqual(self.marginal['actual_scores'],0);self.assertEqual(self.marginal['pending_outcomes'],280);view=k.SharedForecast(self.bank);queries=[]
  refs={(r['player_id'],r['statistic']):r for r in self.full['law_payload']['rows']};reference_reasons=collections.defaultdict(set)
  for r in refs.values():
   if r['model'] is None:reference_reasons[r['player_id']].add(r['reason'])
  for r in projected:
   self.assertIsNone(r['genuine_participation_probability']);self.assertIsNone(r['legal_eligibility'])
   if r['samples'] is None:self.assertEqual(r['inherited_abstention_reasons'],sorted(reference_reasons[r['player_id']]));continue
   self.assertEqual(len(r['samples']),64);self.assertEqual(r['scenario_ids'],list(range(64)))
   for kind,value in (('pmf',0),('cdf',10),('oup',10.5)):
    kw=dict(player_id=r['player_id'],statistic=r['statistic'],kind=kind,value=value);s=view.query(channel='S4',**kw);j=view.query(channel='J',**kw);self.assertEqual(s,j);self.assertFalse(s['population_exact_zero_claim']);self.assertFalse(s['count_support_truncated']);self.assertFalse(s['independent_vote']);self.assertFalse(s['score_admitted']);queries.append(s)
  c=json.loads((A/'COHERENCE.json').read_bytes());self.assertEqual(queries,c['queries']);self.assertEqual((len(queries),c['exact_equal_pairs']),(336,336));self.assertEqual(c['zero_sensitivity_gate'],'PENDING');RESULT['coverage']={'all_attempts':280,'supported':112,'abstentions':168,'primitive_attempts':140,'primitive_supported':56,'primitive_abstentions':84,'all_public_query_pairs_exact':336,'actual_scores':0,'pending_outcomes':280}
 def test_03_all56_old_S1_reference_disclosures_independently_recomputed(self):
  saved=json.loads((A/'REFERENCE_COMPARISON.json').read_bytes());samples={(r['player_id'],r['statistic']):r['samples'] for r in self.marginal['rows'] if r['statistic'] in ('points','rebounds','assists','threes')};ref={(r['player_id'],r['statistic']):r['model'] for r in self.full['law_payload']['rows']};epsilon=math.sqrt(math.log(2*56/.05)/(2*64));self.assertAlmostEqual(saved['simultaneous_MC_DKW95_half_width'],epsilon,14);checked=[]
  for row in saved['rows']:
   key=(row['player_id'],row['statistic']);values=samples[key];f=ref[key]
   if f is None:self.assertIsNone(values);self.assertEqual(row['n'],0);continue
   self.assertEqual(len(values),64);law=FullPlayedLaw(**f['rate_parameters'],minutes=f['minute_parameters'],zero_prior_mean=f['zero_prior_mean']);limit=max(max(values),128);grid=list(range(limit+1));pmf=law.query(grid)['probabilities'];cdf=law.query(grid,kind='cdf')['probabilities'];tail=law.query([limit],kind='sf')['probabilities'][0];counter=collections.Counter(values);tv=(sum(abs(counter[i]/64-pmf[i]) for i in grid)+tail)/2;gap=max(abs(sum(x<=i for x in values)/64-cdf[i]) for i in grid);mean=math.fsum(values)/64;sd=math.sqrt(math.fsum((x-mean)**2 for x in values)/63)
   self.assertAlmostEqual(row['partition_empirical_TV'],tv,12);self.assertAlmostEqual(row['empirical_CDF_max_difference'],gap,12);self.assertAlmostEqual(row['new_J_sample_mean'],mean,12);self.assertAlmostEqual(row['reference_S_mean'],law.moments()['mean'],12);self.assertAlmostEqual(row['sample_mean_MC_standard_error'],sd/8,12);self.assertAlmostEqual(row['estimated_CDF_difference_lower_limit_vs_numerical_reference'],max(0,gap-epsilon),12);self.assertFalse(row['true_S_CDF_lower_bound_certified']);self.assertFalse(row['TV_fidelity_certificate']);checked.append({'player_id':key[0],'statistic':key[1],'CDF_gap':gap,'empirical_TV':tv,'mean_difference':mean-law.moments()['mean']})
  self.assertEqual(len(checked),56);self.assertEqual((saved['supported_rows'],saved['abstentions']),(56,84));RESULT['comparison']={'rows':checked,'supported':56,'abstentions':84,'DKW95_half_width':epsilon,'maximum_CDF_gap':max(r['CDF_gap'] for r in checked),'empirical_TV_min':min(r['empirical_TV'] for r in checked),'empirical_TV_max':max(r['empirical_TV'] for r in checked),'mean_difference_min':min(r['mean_difference'] for r in checked),'mean_difference_max':max(r['mean_difference'] for r in checked),'old_S1_match_required':False,'quality_accepted':False}
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Actual));RESULT.update(methods=result.testsRun,errors=len(result.errors),failures=len(result.failures));(HERE/'ACTUAL_RESULTS.json').write_text(json.dumps(RESULT,sort_keys=True,indent=2)+'\n');sys.exit(not result.wasSuccessful())
