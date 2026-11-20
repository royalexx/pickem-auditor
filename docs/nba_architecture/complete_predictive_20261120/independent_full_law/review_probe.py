"""Independent public-reader/full-law review; no repairs or new fit artifacts."""
from pathlib import Path
from datetime import datetime,timezone
import copy,json,math,subprocess,sys,tempfile,unittest
from unittest.mock import patch
import numpy as np
from scipy.integrate import quad
from scipy.special import betaln
from scipy.stats import nbinom
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from v2.nba_s_family import model as native
from scripts.nba_genuine_s import frozen_inputs
from v2.nba_architecture.full_played_s_v1 import FullPlayedLaw
from v2.nba_architecture.full_predictive_candidate_v1 import build_full_candidate
from v2.nba_architecture.pbp_evidence_v1 import parse_pbp,read_population
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
P=ROOT/'docs/nba_architecture/complete_predictive_20261120';HERE=Path(__file__).resolve().parent
OLD=ROOT/'docs/nba_architecture/genuine_s_prospective_20261120/corrected_archive'
SAVED=json.loads((P/'FULL_S_CANDIDATE.json').read_bytes());PARENT=json.loads((OLD/'forecast.json').read_bytes());RESULT={}

def independent_shape(d):
 p,q=d['ot_probability'],d['ot_continuation'];ek=p/(1-q);ek2=p*(1+q)/(1-q)**2
 el=48+5*ek;el2=48**2+480*ek+25*ek2;share=d['mean']/el
 variance=min(max(1e-6,(d['variance']-share**2*25*(ek2-ek**2))/el2),.95*share*(1-share))
 c=share*(1-share)/variance-1
 return share*c,(1-share)*c

def independent_integral(model,k=None,power=0,kind='pmf',terms=40):
 d=model['minute_parameters'];a,b=independent_shape(d);rate=model['rate_parameters'];A,B=rate['alpha'],rate['beta'];p,q=d['ot_probability'],d['ot_continuation'];total=0.;err=0.
 for i in range(terms+1):
  length=48+5*i;weight=1-p if i==0 else p*(1-q)*q**(i-1)
  def kernel(u):
   if k is None:return (length*u)**power*math.exp(-betaln(a,b))
   prob=B/(B+length*u)
   return float(nbinom.pmf(k,A,prob) if kind=='pmf' else nbinom.cdf(k,A,prob))*math.exp(-betaln(a,b))
  value,error=quad(kernel,0,1,weight='alg',wvar=(a-1,b-1),epsabs=1e-12,epsrel=1e-12,limit=250)
  total+=weight*value;err+=weight*error
 if k is not None:total=(1-model['zero_prior_mean'])*total+(model['zero_prior_mean'] if k==0 or kind=='cdf' else 0)
 return total,err,(1-model['zero_prior_mean'])*p*q**terms

def builder(**overrides):
 kwargs=frozen_inputs(OLD);kwargs['forecast_at']=PARENT['forecast_at']
 args=dict(original_inputs=kwargs,pbp_raw_dir=P/'raw',pbp_population_path=P/'PBP_POPULATION.json',model_card_path=P/'FULL_PLAYED_MODEL_CARD.json',protocol_path=P/'independent_protocol/DECISION.json')
 args.update(overrides);return build_full_candidate((OLD/'forecast.json').read_bytes(),**args)

def source_body(gid='0022600165'):
 raw=(P/'raw'/('pbp-'+gid)/'body.raw').read_bytes();box=(OLD/'inputs/raw'/('nba-box-'+gid)/'body.raw').read_bytes()
 return raw,box

def mutate_page(raw,change):
 import re
 match=re.search(rb'(<script[^>]+id="__NEXT_DATA__"[^>]*>)(.*?)(</script>)',raw,re.S)
 page=json.loads(match[2]);change(page['props']['pageProps'])
 return raw[:match.start(2)]+json.dumps(page,separators=(',',':')).encode()+raw[match.end(2):]

class Review(unittest.TestCase):
 def test_01_exact_sources_counts_clocks_and_scope(self):
  result=read_population(P/'raw',P/'PBP_POPULATION.json',OLD/'inputs/raw')
  self.assertEqual((result['game_denominator'],result['rejected_games']),(20,0));self.assertEqual(result['payload_sha256'],SAVED['evidence_payload_sha256'])
  self.assertEqual(sum(r['facts']['action_denominator'] for r in result['rows']),10463)
  self.assertTrue(all(r['facts']['all_credited_event_counts_reconciled'] for r in result['rows']))
  self.assertTrue(all(r['facts']['exact_wallclock_end_at'] is None and r['facts']['on_court_lineup_completeness'] is None for r in result['rows']))
  self.assertEqual((SAVED['candidate_denominator'],SAVED['attempt_denominator'],SAVED['full_model_candidates'],SAVED['abstentions'],SAVED['sensitivity_attempt_denominator']),(35,140,56,84,700))
  self.assertEqual({(r['player_id'],r['statistic']) for r in SAVED['rows']},{(r['player_id'],r['statistic']) for r in PARENT['rows']})
  self.assertEqual(digest(canonical({k:v for k,v in SAVED.items() if k not in ('payload_sha256','computed_started_at','computed_completed_at')})),SAVED['payload_sha256'])
  self.assertLess(SAVED['parent_forecast_at'],SAVED['source_evidence_available_at']);self.assertLessEqual(SAVED['source_evidence_available_at'],SAVED['computed_started_at']);self.assertLessEqual(SAVED['computed_started_at'],SAVED['computed_completed_at'])
  for row in SAVED['rows']:
   self.assertIsNone(row['participation_probability']);self.assertIsNone(row['legal_eligibility'])
   if row['model']:
    self.assertEqual(len(row['sensitivity']),5);self.assertTrue(all(s['scenario_is_not_identified_bound'] for s in row['sensitivity']))
    self.assertIsNone(row['model']['genuine_zero_state_probability']);self.assertFalse(row['model']['production_release'])
   else:self.assertEqual(row['sensitivity'],[])
  RESULT['source_evidence']=dict(games=20,actions=10463,event_credit_reconciled_fields=14,exact_end_or_complete_lineup_claimed=False,payload_sha256=result['payload_sha256'])

 def test_02_all56_moments_and_prior_sensitivity(self):
  checks=[]
  for row in SAVED['rows']:
   model=row['model']
   if not model:continue
   first=independent_integral(model,power=1)[0];second=independent_integral(model,power=2)[0];A,B=model['rate_parameters']['alpha'],model['rate_parameters']['beta']
   mu=A/B*first;var=mu+A*(A+1)/B**2*second-mu**2
   for scenario in row['sensitivity']:
    z=scenario['chosen_zero_weight'];actual=scenario['moments'];expected=(1-z)*mu;variance=(1-z)*var+z*(1-z)*mu**2
    self.assertAlmostEqual(actual['mean'],expected,places=9);self.assertAlmostEqual(actual['variance'],variance,places=7)
   checks.append(dict(player=row['name'],statistic=row['statistic'],independent_positive_mean=mu,independent_positive_variance=var,mean_error=abs(model['moments']['mean']-.99*mu),variance_error=abs(model['moments']['variance']-(.99*var+.0099*mu**2))))
  RESULT['all56_moment_checks']=checks

 def test_03_low_and_high_exposure_independent_adaptive_quad(self):
  checks=[]
  for row in SAVED['rows']:
   if not row['model'] or row['name'] not in ('Cody Williams','Kris Murray','LaMelo Ball'):continue
   model=row['model'];law=FullPlayedLaw(**model['rate_parameters'],minutes=model['minute_parameters'])
   ks=[0,1,5,10,30,100];actual=law.query(ks)
   cdf=law.query([0,5,30],kind='cdf')
   for i,k in enumerate(ks):
    expected,error,tail=independent_integral(model,k=k);difference=abs(expected-actual['probabilities'][i]);self.assertLess(difference,2e-9)
    try:
     analytic=law.analytic_pmf(k);self.assertLess(abs(analytic['probability']-expected),2e-9)
    except ValueError as unresolved:
     self.assertEqual(str(unresolved),'FULL_S_ANALYTIC_REFERENCE_UNRESOLVED')
     RESULT.setdefault('honest_scipy_analytic_reference_failures',[]).append(dict(player=row['name'],statistic=row['statistic'],count=k,reason=str(unresolved)))
    if k<=30:
     log=law.logpmf(k);self.assertLess(abs(math.exp(log['log_probability'])-expected),2e-9)
    checks.append(dict(player=row['name'],statistic=row['statistic'],count=k,actual=actual['probabilities'][i],independent_quad=expected,absolute_difference=difference,error_estimate=error,OT_tail_bound=tail))
   for i,k in enumerate((0,5,30)):
    expected=independent_integral(model,k=k,kind='cdf')[0];self.assertLess(abs(cdf['probabilities'][i]-expected),2e-9)
  RESULT['independent_query_checks']=checks

 def test_04_actual_public_builder_replay(self):
  with patch.object(native,'fit',wraps=native.fit) as observed:
   own=builder()
  self.assertEqual(observed.call_count,4)
  self.assertEqual(own['payload_sha256'],SAVED['payload_sha256']);self.assertFalse(own['new_forecast_issued'])
  RESULT['native_fit_in_memory_exact_byte_verification_replays']=observed.call_count
  RESULT['own_public_replay']=dict(payload_sha256=own['payload_sha256'],computed_started_at=own['computed_started_at'],computed_completed_at=own['computed_completed_at'])

 def test_05_source_and_scope_mutations(self):
  results=[];raw,box=source_body()
  mutations={
   'duplicate_action_id':lambda p:p['playByPlay']['actions'][1].update(actionId=p['playByPlay']['actions'][0]['actionId']),
   'wrong_game':lambda p:p['playByPlay'].update(gameId='0022609999'),
   'backwards_clock':lambda p:p['playByPlay']['actions'][1].update(clock='PT13M00.00S'),
   'actor_team':lambda p:next(a for a in p['playByPlay']['actions'] if a['personId'] and a['teamId']).update(teamId=999),
   'bad_final':lambda p:p['playByPlay']['actions'][-1].update(scoreHome='999')}
  for label,change in mutations.items():
   with self.subTest(label=label),self.assertRaises(ValueError) as error:parse_pbp(mutate_page(raw,change),box,'0022600165')
   results.append(dict(mutation=label,rejected=str(error.exception)))
  with tempfile.TemporaryDirectory() as tmp:
   tmp=Path(tmp)
   for name,source in [('card',P/'FULL_PLAYED_MODEL_CARD.json'),('protocol',P/'independent_protocol/DECISION.json'),('population',P/'PBP_POPULATION.json')]:
    dest=tmp/name;dest.write_bytes(source.read_bytes()+b' ')
    kw={'card':'model_card_path','protocol':'protocol_path','population':'pbp_population_path'}[name]
    with self.subTest(input=name),self.assertRaises(ValueError) as error:builder(**{kw:dest})
    results.append(dict(mutation=name+'_bytes',rejected=str(error.exception)))
   # Exact pinned population prevents source receipt self-resealing or silent drop.
   for mode in ('drop','reseal'):
    population=json.loads((P/'PBP_POPULATION.json').read_bytes())
    if mode=='drop':population['sources'].pop(next(iter(population['sources'])))
    else:population['sources'][next(iter(population['sources']))]['body_sha256']='0'*64
    dest=tmp/mode;dest.write_bytes(canonical(population))
    with self.subTest(input=mode),self.assertRaises(ValueError) as error:builder(pbp_population_path=dest)
    results.append(dict(mutation=mode+'_population',rejected=str(error.exception)))
  RESULT['mutation_controls']=results

 def test_06_parameter_domains_structural_zero_and_rare_tail_failure(self):
  model=next(r['model'] for r in SAVED['rows'] if r['name']=='Cody Williams' and r['statistic']=='threes')
  d=model['minute_parameters'];rates=model['rate_parameters'];law=FullPlayedLaw(**rates,minutes=d)
  for key in ('alpha','beta'):
   for value in (0.,-1.,float('nan'),float('inf'),True):
    args=dict(rates);args[key]=value
    with self.subTest(key=key,value=str(value)),self.assertRaises(ValueError):FullPlayedLaw(**args,minutes=d)
  for value in (-.01,1.01,float('nan'),True):
   with self.subTest(z=str(value)),self.assertRaises(ValueError):FullPlayedLaw(**rates,minutes=d,zero_prior_mean=value)
  for values in ([],[-1],[True],[1.0]):
   with self.subTest(counts=values),self.assertRaises(ValueError):law.query(values)
  with self.assertRaises(ValueError):FullPlayedLaw(**rates,minutes=dict(d,family='truncated_lognormal'))
  zero=FullPlayedLaw(**rates,minutes=d,zero_prior_mean=1.)
  self.assertEqual(zero.query([0,1,100])['probabilities'],[1.,0.,0.]);self.assertEqual(zero.logpmf(1)['log_probability'],-math.inf)
  rare=[]
  for k in (100,1000):
   value=law.logpmf(k);self.assertTrue(math.isfinite(value['log_probability']));self.assertLessEqual(value['omitted_OT_relative_probability_bound'],1e-8);rare.append(dict(count=k,**value))
  for k in (10000,1000000):
   with self.subTest(k=k),self.assertRaisesRegex(ValueError,'UNRESOLVED_NO_SCORE'):law.logpmf(k)
   rare.append(dict(count=k,status='UNRESOLVED_NO_SCORE'))
  RESULT['rare_queries']=rare

if __name__=='__main__':
 RESULT.update(started_at=datetime.now(timezone.utc).isoformat(),reviewed_checkout=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),source_sha256={n:digest((ROOT/'v2/nba_architecture'/n).read_bytes()) for n in ('full_played_s_v1.py','pbp_evidence_v1.py','full_predictive_candidate_v1.py')},candidate_raw_sha256=digest((P/'FULL_S_CANDIDATE.json').read_bytes()))
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Review))
 RESULT.update(completed_at=datetime.now(timezone.utc).isoformat(),test_methods=result.testsRun,failures=len(result.failures),errors=len(result.errors),new_fit_artifacts_created=0,scoring_calls=0)
 (HERE/'RESULTS.json').write_text(json.dumps(RESULT,indent=2,sort_keys=True)+'\n');sys.exit(not result.wasSuccessful())
