"""Second discovery campaign: each attack reseals its contract payload."""
import copy, math, random, unittest
from golden_v2 import golden_cases, pregame, distribution, game_state, opportunity, j_scenarios
from test_v2_contracts import evaluation, reissue
from v2.nba_architecture.v2_contracts import (ContractError, seal, receipt,
 validate_pregame, validate_distribution, validate_scenarios, validate_evaluation,
 marginal_from_joint, instant, threshold_triplet)
from v2.nba_architecture.families_v2 import validate_opportunity, validate_integration

def edit(x, f):
 x=copy.deepcopy(x); x.pop('content_hash'); f(x); return seal(x)

class CompletionAttacks(unittest.TestCase):
 def setUp(self):
  self.c=golden_cases()['joint_same_draw']; self.p=self.c['pregame'];self.j=self.c['scenarios'];self.g=self.c['game_state'];self.o=self.c['opportunity']
 def test_submicrosecond_timestamp_cannot_silently_reverse_order(self):
  with self.assertRaises(ContractError): instant('2026-11-16T23:00:00.0000009Z')
 def test_feature_prior_date_bound_to_receipt(self):
  p=pregame()
  with self.assertRaises(ContractError):validate_pregame(edit(p,lambda x:x['features'][0].update(prior_game_date='2022-10-16')))
 def test_prior_stat_cannot_use_quote_receipt(self):
  p=copy.deepcopy(self.p); r=p['sources'][1];p['features'][0].update(source_id=r['source_id'],source_receipt_sha256=r['receipt_sha256'],kind='prior_boxscore',prior_game_date='2026-11-15')
  with self.assertRaises(ContractError):validate_pregame(edit(p,lambda x:None))
 def test_revision_gap(self):
  p=pregame();r=p['sources'][0];new=reissue(r,source_revision=3,supersedes_receipt_sha256=r['receipt_sha256'])
  with self.assertRaises(ContractError):validate_pregame(edit(p,lambda x:x['sources'].append(new)))
 def test_boolean_team_score(self):
  j=edit(self.j,lambda x:x['scenarios'][0]['team_points'].update({'espn:team:2':False}))
  with self.assertRaises(ContractError):validate_scenarios(j,self.p)
 def test_extra_team_total(self):
  j=edit(self.j,lambda x:x['scenarios'][0]['team_points'].update({'espn:team:extra':0}))
  with self.assertRaises(ContractError):validate_scenarios(j,self.p)
 def test_witness_hidden_feature(self):
  j=edit(self.j,lambda x:x['game_state_witness']['synthetic:draw:0'].update(actual_rotation=48))
  with self.assertRaises(ContractError):validate_scenarios(j,self.p)
 def test_conditional_marginal_cannot_include_target_dnp(self):
  j=edit(self.j,lambda x:x.update(conditioning='conditional_on_participation'))
  with self.assertRaises(ContractError):marginal_from_joint(j,self.p,self.p['players'][5]['player_id'],'points','2026-11-16T23:03:00Z',42)
 def test_empty_probability_zero_bin_is_permissible(self):
  d=edit(self.c['points'],lambda x:x['pmf'].append({'value':999,'mass':0.}))
  self.assertTrue(validate_distribution(d,self.p,self.j))
 def test_scenario_reorder_preserves_marginal(self):
  # Same mathematical mixture, harmless order changes must not alter validity.
  j=edit(self.j,lambda x:x['scenarios'].reverse())
  d=marginal_from_joint(j,self.p,self.p['players'][0]['player_id'],'pra','2026-11-16T23:03:00Z',42)
  self.assertEqual(d['pmf'],self.c['pra']['pmf'])
 def test_correction_parent_required_as_object(self):
  c=golden_cases()['prospective_original_offer'];e=evaluation(c['distribution'],c['offer_view'],revision=2,previous='f'*64)
  with self.assertRaises(ContractError):validate_evaluation(e,c['distribution'],c['offer_view'])
 def test_offer_free_contract_line_rejected(self):
  c=golden_cases()['historical_offer_free'];e=evaluation(c['distribution'],line=2.5)
  with self.assertRaises(ContractError):validate_evaluation(e,c['distribution'])
 def test_nonvoid_cannot_carry_void_basis(self):
  c=golden_cases()['prospective_original_offer'];e=evaluation(c['distribution'],c['offer_view'])
  with self.assertRaises(ContractError):validate_evaluation(edit(e,lambda x:x.update(void_basis='made up')),c['distribution'],c['offer_view'])
 def test_weights_tiny_roundoff_and_reorder(self):
  # 32 deterministic mixtures expose float summation artifacts at marginal checks.
  rng=random.Random(20261116)
  for _ in range(32):
   weights=[rng.random() for i in range(7)];total=math.fsum(weights);weights=[w/total for w in weights]
   j=copy.deepcopy(self.j);template=copy.deepcopy(j['scenarios'][0]);j['scenarios']=[];j['game_state_witness']={};j['opportunity_witness']={}
   for i,w in enumerate(weights):
    row=copy.deepcopy(template);sid=f'synthetic:draw:{i}';row.update(scenario_id=sid,weight=w);j['scenarios'].append(row)
    j['game_state_witness'][sid]={'weight':w,'overtime_periods':0};j['opportunity_witness'][sid]=[{k:p[k] for k in ('player_id','team_id','minutes','participation')} for p in row['players']]
   j=edit(j,lambda x:None)
   d=marginal_from_joint(j,self.p,self.p['players'][0]['player_id'],'points','2026-11-16T23:03:00Z',42)
   self.assertTrue(validate_distribution(d,self.p,j))

class LastBoundaryAttacks(unittest.TestCase):
 def test_opportunity_player_hidden_payload(self):
  c=golden_cases()['joint_same_draw'];o=edit(c['opportunity'],lambda x:x['scenarios'][0]['players'][0].update(actual_stats=100))
  with self.assertRaises(ContractError):validate_opportunity(o,c['pregame'],c['game_state'])
 def test_superseded_feature_revision(self):
  p=pregame();r=p['sources'][0];new=reissue(r,source_revision=2,supersedes_receipt_sha256=r['receipt_sha256'])
  with self.assertRaises(ContractError):validate_pregame(edit(p,lambda x:x['sources'].append(new)))
 def test_threshold_rejects_negative_mass(self):
  with self.assertRaises(ContractError):threshold_triplet([{'value':0,'mass':-1},{'value':1,'mass':2}],.5)
 def test_minutes_law_support_physically_bounded(self):
  from test_g0_pipeline_completion_20261116 import coherent_case
  c=coherent_case();o=edit(c['opportunity'],lambda x:x['players'][0]['minutes_law']['parameters'].update(support=[{'minutes':48.,'mass':.5},{'minutes':100.,'mass':.5}]))
  with self.assertRaises(ContractError):validate_opportunity(o,c['pregame'],c['game_state'])

class IngestionAndTransitionMatrix(unittest.TestCase):
 def test_duplicate_json_keys_and_nonfinite(self):
  from v2.nba_architecture.v2_contracts import parse_contract,canonical
  c=golden_cases()['prospective_original_offer']['pregame'];raw=canonical(c).decode()
  self.assertEqual(parse_contract(raw),c)
  for invalid in ('{"a":1,"a":2}', '{"nested":{"a":1,"a":2}}', '{"x":NaN}', '{"x":Infinity}', '[1]', 'garbage'):
   with self.subTest(raw=invalid):
    with self.assertRaises(ContractError):parse_contract(invalid)
 def test_full_transition_matrix(self):
  from v2.nba_architecture.v2_contracts import participation_state
  for eligible in (None,True,False):
   for availability in ('unknown','active_reported','questionable','out'):
    for prob in (None,0.,.2,.8,1.):
     for state,minutes in (('DNP',0.),('PLAYED_ZERO_MINUTES',0.),('PLAYED',1.),('DNP',1.),('PLAYED',0.)):
      for weight in (0.,.5):
       roster={'legal_eligibility':eligible,'availability':availability}
       valid=(state=='PLAYED' and minutes>0 or state!='PLAYED' and minutes==0)
       valid=valid and (not(eligible is False or availability=='out') or state=='DNP')
       if weight>0:valid=valid and (prob!=0 or state=='DNP') and (prob!=1 or state!='DNP')
       with self.subTest(eligible=eligible,availability=availability,prob=prob,state=state,minutes=minutes,weight=weight):
        if valid:participation_state(roster,state,minutes,prob,weight)
        else:
         with self.assertRaises(ContractError):participation_state(roster,state,minutes,prob,weight)

class DataBoundaryAttack(unittest.TestCase):
 def test_model_fit_after_declared_data_cutoff(self):
  c=golden_cases()['prospective_original_offer'];d=edit(c['distribution'],lambda x:x['lineage']['S'].update(training_cutoff_at='2026-11-16T21:00:00Z'))
  with self.assertRaises(ContractError):validate_distribution(d,c['pregame'])

class DefensiveAccountingAttacks(unittest.TestCase):
 def test_block_requires_opponent_missed_fga(self):
  c=golden_cases()['joint_same_draw'];j=edit(c['scenarios'],lambda x:x['scenarios'][0]['players'][1]['stats'].update(blocks=1))
  with self.assertRaises(ContractError):validate_scenarios(j,c['pregame'])
 def test_steal_requires_opponent_turnover(self):
  c=golden_cases()['joint_same_draw'];j=edit(c['scenarios'],lambda x:x['scenarios'][0]['players'][1]['stats'].update(steals=1))
  with self.assertRaises(ContractError):validate_scenarios(j,c['pregame'])

class DefensiveAccountingPositive(unittest.TestCase):
 def test_block_and_steal_with_opportunities(self):
  c=golden_cases()['joint_same_draw']
  def mutate(j):
   row=j['scenarios'][0]['players'];row[1]['stats'].update(blocks=1,steals=1);row[6]['stats'].update(fga=1,two_pa=1,turnovers=1)
  self.assertTrue(validate_scenarios(edit(c['scenarios'],mutate),c['pregame']))

class CallingConventionMetamorphic(unittest.TestCase):
 def test_keyword_context_cannot_bypass_model_cutoff(self):
  c=golden_cases()['prospective_original_offer'];d=edit(c['distribution'],lambda x:x['lineage']['S'].update(training_cutoff_at='2026-11-16T21:00:00Z'))
  with self.assertRaises(ContractError):validate_distribution(d,p=c['pregame'])

class FullKeywordPositive(unittest.TestCase):
 def test_all_keyword_distribution_call(self):
  c=golden_cases()['prospective_original_offer']
  self.assertTrue(validate_distribution(d=c['distribution'],p=c['pregame']))

class CalendarBoundaryAttack(unittest.TestCase):
 def test_local_date_cannot_be_unrelated_to_freeze(self):
  p=pregame('original_prospective')
  with self.assertRaises(ContractError):validate_pregame(edit(p,lambda x:x.update(decision_local_date='2030-01-01')))
