"""Independently rebuild every J working-model field in memory; never call writer."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import json,math,re,sys,subprocess,unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from scripts.nba_genuine_s import frozen_inputs
from v2.nba_architecture.prospective_s_sources_v1 import build_dataset,next_data
from v2.nba_architecture.pbp_evidence_v1 import read_population
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
P=ROOT/'docs/nba_architecture/complete_predictive_20261120';H=Path(__file__).resolve().parent;OLD=ROOT/'docs/nba_architecture/genuine_s_prospective_20261120/corrected_archive';RESULT={}
parent=json.loads((OLD/'forecast.json').read_bytes());full=json.loads((P/'actual_full_forecast/forecast.json').read_bytes());actual_raw=(P/'fitted_j/event_model.json').read_bytes();actual=json.loads(actual_raw);receipt=json.loads((P/'fitted_j/FIT_RECEIPT.json').read_bytes());approval=json.loads((P/'independent_j_prefit/PREFIT_APPROVAL.json').read_bytes());s3=json.loads((P/'independent_s3_artifact/ARTIFACT_ADMISSION.json').read_bytes());inputs=frozen_inputs(OLD)
def counts(rows,key):
 def value(r):
  c=r['official_counts']
  if key=='two_made':return c['fieldGoalsMade']-c['threePointersMade']
  if key=='two_attempts':return c['fieldGoalsAttempted']-c['threePointersAttempted']
  return c[key]
 return math.fsum(value(r) for r in rows)
def exposure(rows):return math.fsum(r['exact_seconds']/60 for r in rows)
def conversion(own,peers,made,attempted):
 m,n,pm,pn=[counts(pool,key) for pool,key in [(own,made),(own,attempted),(peers,made),(peers,attempted)]]
 q=pm/pn
 return dict(alpha=.5+40*q+m,beta=.5+40*(1-q)+n-m,working_prior_attempts=40.,own_attempts=n,own_makes=m,peer_attempts=pn,peer_makes=pm)
class Review(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.data=build_dataset(inputs['raw_dir'],inputs['spec_path'],inputs['policy_path']);cls.rows=[r for r in cls.data['records'] if r['fit_included']];cls.facts=read_population(P/'raw',P/'PBP_POPULATION.json',inputs['raw_dir'])
 def test_01_exact_activation_input_and_actual_clock_chain(self):
  closed=subprocess.check_output(['git','show','50022b13:v2/nba_joint/real_event_parameters_v1.py'],cwd=ROOT);activated=closed.replace(b'PREFIT_APPROVAL_SHA=None',b"PREFIT_APPROVAL_SHA='27115bb7b49b41e34959b960e7ac1a8c4e0248a7679711a6374f1c62a7db7ebf'")
  self.assertEqual((ROOT/'v2/nba_joint/real_event_parameters_v1.py').read_bytes(),activated);self.assertEqual(digest(activated),receipt['compiler_raw_sha256']);self.assertEqual(digest(actual_raw),receipt['model_raw_sha256']);self.assertEqual(digest(actual_raw),'85f27b2ce96a96e14449da3e10ab0d3bb7e9c4e60d7aa30bc5b311d46c48e46d')
  self.assertEqual(digest((P/'independent_j_prefit/PREFIT_APPROVAL.json').read_bytes()),receipt['approval_raw_sha256'])
  for name,wanted in approval['exact_input_raw_sha256'].items():self.assertEqual(digest((P/name).read_bytes()),wanted,name)
  for name,wanted in approval['reviewed_dependency_raw_sha256'].items():
   if name=='v2/nba_joint/real_event_parameters_v1.py':continue
   self.assertEqual(digest((ROOT/name).read_bytes()),wanted,name)
  for t in (approval['decided_at'],full['forecast_at'],s3['admitted_at'],json.loads((P/'independent_full_law/ADMISSION.json').read_bytes())['model_admitted_at'],actual['data_cutoff_at']):self.assertLessEqual(t,receipt['started_at'])
  self.assertLessEqual(receipt['started_at'],receipt['completed_at']);self.assertLess(receipt['completed_at'],parent['cohort']['start']);self.assertEqual(self.data['payload_sha256'],approval['original_dataset_payload_sha256']);self.assertEqual(self.facts['payload_sha256'],actual['pbp_payload_sha256'])
  command=json.loads((P/'owner_execution/COMPILE_J.command.json').read_bytes());self.assertEqual(command['process_exit_code'],0);self.assertEqual((P/'owner_execution/COMPILE_J.stderr').read_bytes(),b'');self.assertEqual((receipt['PBP_games'],receipt['PBP_actions']),(20,10463));self.assertFalse(receipt['release']);self.assertFalse(receipt['heldout_scoring'])
  self.assertEqual(command['model_raw_sha256'],digest(actual_raw));self.assertEqual(command['fit_receipt_raw_sha256'],digest((P/'fitted_j/FIT_RECEIPT.json').read_bytes()))
  self.assertEqual(command['stdout_raw_sha256'],digest((P/'owner_execution/COMPILE_J.stdout').read_bytes()));self.assertEqual(command['stderr_raw_sha256'],digest((P/'owner_execution/COMPILE_J.stderr').read_bytes()))
  RESULT['actual_fit_receipt']=receipt
 def test_02_independent_complete_model_byte_reconstruction(self):
  named={r['player_id']:r for r in full['law_payload']['rows'] if r['model']};minute={r['player_id']:r for r in parent['minutes']};players=[]
  for pid,row in sorted(named.items()):
   role=s3['exact_current_target_role_map'][pid];own=[r for r in self.rows if r['player_id']==pid];peers=[r for r in self.rows if r['player_id']!=pid and r['role']==role];self.assertGreaterEqual(len(own),5)
   original={r['statistic']:r['forecast']['parameters'] for r in parent['rows'] if r['player_id']==pid and r['forecast']};rates={k:{v:original[k][v] for v in ('alpha','beta')} for k in original};ownexp=exposure(own);peerexp=exposure(peers)
   self.assertLess(abs(ownexp-sum(r['exact_seconds'] for r in own)/60),1e-10)
   rates['turnovers']=dict(alpha=.5+180*(counts(peers,'turnovers')/peerexp)+counts(own,'turnovers'),beta=181.+ownexp)
   q3=sum(r['three_attempts'] for r in self.data['histories']['threes'] if r['player_id']!=pid and r['role']==role);pm3=sum(r['count'] for r in self.data['histories']['threes'] if r['player_id']!=pid and r['role']==role);q=pm3/q3
   conversion3=dict(alpha=40*q+counts(own,'threePointersMade'),beta=40*(1-q)+(counts(own,'threePointersAttempted')-counts(own,'threePointersMade')))
   non3=2*counts(peers,'two_made')+counts(peers,'freeThrowsMade');share=counts(peers,'freeThrowsMade')/non3
   ftshare=dict(alpha=.5+40*share+counts(own,'freeThrowsMade'),beta=.5+40*(1-share)+2*counts(own,'two_made'),unit='POINT_CREDIT_WORKING_PRIOR_NOT_INDEPENDENT_BERNOULLI_EVIDENCE')
   players.append(dict(player_id=pid,name=row['name'],team_id=row['team_id'],role=role,minutes=minute[pid]['forecast']['distribution'],rates=rates,conversion3=conversion3,conversion2=conversion(own,peers,'two_made','two_attempts'),conversion_ft=conversion(own,peers,'freeThrowsMade','freeThrowsAttempted'),ft_non3_point_share=ftshare,genuine_participation_probability=None,legal_eligibility=None))
  residual={}
  for team in sorted({r['team_id'] for r in players}):
   pool=[r for r in self.rows if r['team_id']==team and r['player_id'] not in named];exp=exposure(pool)
   rates={k:dict(alpha=.5+counts(pool,v),beta=1.+exp) for k,v in dict(points='points',threes='threePointersMade',rebounds='reboundsTotal',assists='assists',turnovers='turnovers').items()}
   def simple(m,n):return dict(alpha=.5+counts(pool,m),beta=.5+counts(pool,n)-counts(pool,m))
   residual[team]=dict(kind='ANONYMOUS_GROUP_EXCHANGEABILITY_WORKING_PRIOR',source_rows=len(pool),source_reported_minutes=exp,rates=rates,conversion3=simple('threePointersMade','threePointersAttempted'),conversion2=simple('two_made','two_attempts'),conversion_ft=simple('freeThrowsMade','freeThrowsAttempted'),ft_non3_point_share=dict(alpha=.5+counts(pool,'freeThrowsMade'),beta=.5+2*counts(pool,'two_made')),source_real_player_identity_claim=False,rate_dependence='ONE_SHARED_GROUP_RATE_VECTOR_PER_TEAM_SCENARIO')
  pace=[];totals={k:0 for k in ('fieldGoalsAttempted','fieldGoalsMade','freeThrowsAttempted','freeThrowsMade','reboundsTotal','reboundsOffensive','reboundsDefensive','assists')};series=Counter()
  for fact in self.facts['rows']:
   gid=fact['game_id'];g=next_data((inputs['raw_dir']/('nba-box-'+gid)/'body.raw').read_bytes())['game'];proxy=[]
   for side in ('homeTeam','awayTeam'):
    c=g[side]['statistics'];proxy.append(c['fieldGoalsAttempted']+.44*c['freeThrowsAttempted']-c['reboundsOffensive']+c['turnovers'])
    for k in totals:
     # Independent check: published team credited fields equal all native players.
     self.assertEqual(c[k],sum(p['statistics'][k] for p in g[side]['players']))
     totals[k]+=c[k]
   pace.append(dict(game_id=gid,regulation_equivalent_proxy=sum(proxy)/2*48/(48+5*(g['period']-4))))
   raw=(P/'raw'/('pbp-'+gid)/'body.raw').read_bytes();actions=next_data(raw)['playByPlay']['actions']
   for a in actions:
    if a['actionType']=='Free Throw':
     match=re.search(r'Free Throw 1 of ([23])',a['description'])
     if match:series[int(match[1])]+=1
  values=[r['regulation_equivalent_proxy'] for r in pace];mean=float(np.mean(values));variance=float(np.var(values,ddof=1));self.assertAlmostEqual(mean,math.fsum(values)/20,places=12)
  miss=totals['fieldGoalsAttempted']-totals['fieldGoalsMade']+totals['freeThrowsAttempted']-totals['freeThrowsMade']
  events=dict(assisted_fg=dict(alpha=.5+totals['assists'],beta=.5+totals['fieldGoalsMade']-totals['assists']),credited_rebound=dict(alpha=.5+totals['reboundsTotal'],beta=.5+miss-totals['reboundsTotal'],source_unit='ALL_MISS_PROXY_INCLUDES_NONTERMINAL_FT_NOT_TRUE_LIVE_REBOUND_OPPORTUNITY'),offensive_rebound=dict(alpha=.5+totals['reboundsOffensive'],beta=.5+totals['reboundsDefensive']),shooting_ft_three_series=dict(alpha=.5+series[3],beta=.5+series[2],source_unit='OBSERVED_TWO_OR_THREE_SHOT_SERIES_LENGTH_PROXY_NOT_SOURCE_CLASSIFIED_SHOOTING_FOUL',one_shot_series_excluded=True))
  expected=dict(schema='new-conditional-residual-event-working-model/1',target=parent['cohort']['game_id'],source_candidate_denominator=35,primitive_attempt_denominator=140,named_players=players,residual_groups=residual,zero_prior=dict(alpha=.5,beta=49.5,empirically_updated=False,genuine_probability=None),pace=dict(shape=mean*mean/variance,scale=variance/mean,mean=mean,variance=variance,source='20_REGULATION_EQUIVALENT_FGA_PLUS_0.44_FTA_MINUS_OREB_PLUS_TO_PROXIES',observed_true_possessions=False),events=events,pace_source_rows=pace,source_count_totals=totals,source_ft_series={str(k):series[k] for k in (2,3)},S3_use='WORKING_CONVERSION_PROBABILITY_POSTERIOR_PRIOR_NOT_UNCHANGED_BETA_BINOMIAL_AT_ENDOGENOUS_N',S1_use='WORKING_RATE_PRIORS_ALLOCATION_NEW_EVENT_LAW_NOT_UNCHANGED_S1_MARGINALS',fitting_is_new_prospective=True,posterior_of_joint_event_process=False,source_dataset_sha256=self.data['payload_sha256'],pbp_payload_sha256=self.facts['payload_sha256'],s3_artifact_sha256=digest((P/'fitted_s3/three_conversion.json').read_bytes()),data_cutoff_at=json.loads((P/'PBP_POPULATION.json').read_bytes())['frozen_at'],source_role_semantics=self.data['role_semantics'],genuine_participation_probability=None,source_model_admission='PENDING_SEPARATE_EVENT_MODEL_REVIEW',production_release=False)
  self.assertEqual(canonical(expected),actual_raw);RESULT.update(independently_reconstructed_model_sha256=digest(canonical(expected)),named_players=len(players),residual_pool_rows={k:v['source_rows'] for k,v in residual.items()},all_source_team_credit_sums_reconciled=True,pace=dict(mean=mean,variance=variance),FT_series_counts=dict(series),source_totals=totals)
if __name__=='__main__':
 RESULT['started_at']=datetime.now(timezone.utc).isoformat();r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Review));RESULT.update(completed_at=datetime.now(timezone.utc).isoformat(),test_methods=r.testsRun,failures=len(r.failures),errors=len(r.errors),compiler_writer_calls=0,new_fit_artifacts_created=0,J_scenarios_generated=0,outcome_scores=0)
 (H/'RESULTS.json').write_text(json.dumps(RESULT,indent=2,sort_keys=True)+'\n');sys.exit(not r.wasSuccessful())
