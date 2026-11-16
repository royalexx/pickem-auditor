"""Full-pipeline acceptance requires actual source/G/O/J/quote/correction objects."""
import copy, unittest
from golden_v2 import golden_cases, game_state, opportunity
from test_v2_contracts import evaluation
from test_g0_completion_20261116 import edit
from v2.nba_architecture.v2_contracts import seal,ContractError,marginal_from_joint,validate_pregame
from v2.nba_architecture.families_v2 import validate_forecast,validate_settlement,validate_opportunity,validate_integration

def coherent_case():
 c=copy.deepcopy(golden_cases()['joint_same_draw']);o=c['opportunity']
 for player in o['players']:
  support=sorted({x['minutes'] for sc in o['scenarios'] for x in sc['players'] if x['player_id']==player['player_id'] and x['participation']!='DNP'})
  if not support:support=[0.]
  player['minutes_law']={'family':'discrete_minutes','conditioning':'given_played','units':'minutes','parameters':{'support':[{'minutes':mn,'mass':1/len(support)} for mn in support]}}
 c['opportunity']=edit(o,lambda x:None)
 c['scenarios']=edit(c['scenarios'],lambda x:x.update(opportunity_sha256=c['opportunity']['content_hash']))
 c['points']=marginal_from_joint(c['scenarios'],c['pregame'],c['pregame']['players'][0]['player_id'],'points','2026-11-16T23:03:00Z',42)
 return c

class PipelineCompletion(unittest.TestCase):
 def setUp(self):self.c=coherent_case()
 def validate(self,c=None):
  c=c or self.c
  return validate_forecast(c['points'],c['pregame'],g=c['game_state'],o=c['opportunity'],scenarios=c['scenarios'])
 def test_complete_joint_pipeline(self):self.assertTrue(self.validate())
 def test_j_without_original_o_rejected(self):
  c=self.c
  with self.assertRaises(ContractError):validate_forecast(c['points'],c['pregame'],scenarios=c['scenarios'])
 def test_correctly_resealed_false_o_hash_rejected(self):
  c=self.c;c['scenarios']=edit(c['scenarios'],lambda x:x.update(opportunity_sha256='f'*64))
  c['points']=marginal_from_joint(c['scenarios'],c['pregame'],c['pregame']['players'][0]['player_id'],'points','2026-11-16T23:03:00Z',42)
  with self.assertRaises(ContractError):self.validate()
 def test_conditional_support_rejected(self):
  c=self.c;c['opportunity']=edit(c['opportunity'],lambda x:x['players'][0]['minutes_law']['parameters'].update(support=[{'minutes':12.,'mass':1.}]))
  with self.assertRaises(ContractError):validate_opportunity(c['opportunity'],c['pregame'],c['game_state'])
 def test_discrete_law_mass_rejected(self):
  c=self.c;c['opportunity']=edit(c['opportunity'],lambda x:x['players'][0]['minutes_law']['parameters']['support'][0].update(mass=.2))
  with self.assertRaises(ContractError):validate_opportunity(c['opportunity'],c['pregame'],c['game_state'])
 def test_diagnostic_law_not_complete_forecast(self):
  c=golden_cases()['joint_same_draw']
  with self.assertRaises(ContractError):validate_forecast(c['points'],c['pregame'],g=c['game_state'],o=c['opportunity'],scenarios=c['scenarios'])
 def test_source_bound_uncertain_roster(self):
  c=self.c;p=copy.deepcopy(c['pregame']);r=p['sources'][0]
  p['players'][0].update(availability='questionable',availability_evidence=dict(source_receipt_sha256=r['receipt_sha256'],player_id=p['players'][0]['player_id'],game_id=p['game_id'],field='availability',value='questionable'))
  self.assertTrue(validate_pregame(edit(p,lambda x:None)))
 def test_source_bound_out_still_rejects_played(self):
  c=self.c;p=copy.deepcopy(c['pregame']);r=p['sources'][0]
  p['players'][0].update(availability='out',availability_evidence=dict(source_receipt_sha256=r['receipt_sha256'],player_id=p['players'][0]['player_id'],game_id=p['game_id'],field='availability',value='out'));p=edit(p,lambda x:None)
  self.assertTrue(validate_pregame(p))
  from golden_v2 import j_scenarios
  j=j_scenarios(p);g=game_state(p,j);o=opportunity(p,g,j)
  with self.assertRaises(ContractError):validate_integration(j,p,g,o)
 def test_quote_free_full_settlement(self):
  c=self.c;e=evaluation(c['points'])
  self.assertTrue(validate_settlement(e,c['points'],c['pregame'],g=c['game_state'],o=c['opportunity'],scenarios=c['scenarios']))
 def test_full_offer_settlement_corrections(self):
  c=golden_cases()['prospective_original_offer'];a=evaluation(c['distribution'],c['offer_view']);b=evaluation(c['distribution'],c['offer_view'],revision=2,previous=a['content_hash'],actual=3)
  self.assertTrue(validate_settlement(b,c['distribution'],c['pregame'],view=c['offer_view'],quote=c['offer'],history=[a]))
  with self.assertRaises(ContractError):validate_settlement(b,c['distribution'],c['pregame'],view=c['offer_view'],quote=c['offer'])
  with self.assertRaises(ContractError):validate_settlement(b,c['distribution'],c['pregame'],view=c['offer_view'],quote=c['offer'],history=[a,a])
 def test_forged_view_terms_rejected_at_c(self):
  c=golden_cases()['prospective_original_offer'];view=edit(c['offer_view'],lambda x:x.update(product_terms_sha256='f'*64));e=evaluation(c['distribution'],view,status='void',actual=None,participation='DNP');e=edit(e,lambda x:x.update(void_basis='original_terms_sha256:'+'f'*64))
  with self.assertRaises(ContractError):validate_settlement(e,c['distribution'],c['pregame'],view=view,quote=c['offer'])

class ExcludedPositive(unittest.TestCase):
 def test_verified_out_has_legal_dnp_path(self):
  c=coherent_case();p=copy.deepcopy(c['pregame']);r=p['sources'][0];pid=p['players'][0]['player_id']
  p['players'][0].update(availability='out',availability_evidence=dict(source_receipt_sha256=r['receipt_sha256'],player_id=pid,game_id=p['game_id'],field='availability',value='out'));p=edit(p,lambda x:None)
  j=copy.deepcopy(c['scenarios']);j['source_snapshot_sha256']=p['content_hash']
  for sc in j['scenarios']:
   a,b=sc['players'][0],sc['players'][5]
   b.update(minutes=a['minutes'],participation=a['participation'],stats=a['stats'])
   from golden_v2 import zero_stats
   a.update(minutes=0.,participation='DNP',stats=zero_stats())
   j['opportunity_witness'][sc['scenario_id']]=[{k:x[k] for k in ('player_id','team_id','minutes','participation')} for x in sc['players']]
  g=game_state(p,j);o=opportunity(p,g,j)
  for player in o['players']:
   support=sorted({row['minutes'] for sc in o['scenarios'] for row in sc['players'] if row['player_id']==player['player_id'] and row['participation']!='DNP'}) or [0.]
   player['minutes_law']={'family':'discrete_minutes','conditioning':'given_played','units':'minutes','parameters':{'support':[{'minutes':m,'mass':1/len(support)} for m in support]}}
  o['players'][0].update(participation_evidence='verified_out',participation_probability=0.)
  o=edit(o,lambda x:None);j.update(game_state_sha256=g['content_hash'],opportunity_sha256=o['content_hash']);j=edit(j,lambda x:None)
  d=marginal_from_joint(j,p,pid,'points','2026-11-16T23:03:00Z',42)
  self.assertTrue(validate_forecast(d,p,g=g,o=o,scenarios=j));self.assertEqual(d['pmf'],[{'value':0,'mass':1.}])

class ExactEightMarketReference(unittest.TestCase):
 def test_all_markets_are_same_draw_sums(self):
  from v2.nba_architecture.v2_contracts import STATS,COMPOSITES,threshold_triplet
  c=coherent_case();j=copy.deepcopy(c['scenarios']);sc=j['scenarios'][0];st=sc['players'][1]['stats']
  st.update(two_pa=1,fga=1,oreb=1,rebounds=1,assists=1,pr=1,pa=1,ra=2,pra=2)
  j=edit(j,lambda x:None);p=c['pregame'];pid=p['players'][1]['player_id']
  # The player has (P,R,A,3)=(0,1,1,0) with weight .4 and (0,0,0,0) with weight .6.
  expected={'points':{0:1.},'rebounds':{0:.6,1:.4},'assists':{0:.6,1:.4},'threes':{0:1.},'pr':{0:.6,1:.4},'pa':{0:.6,1:.4},'ra':{0:.6,2:.4},'pra':{0:.6,2:.4}}
  for stat in STATS:
   d=marginal_from_joint(j,p,pid,stat,'2026-11-16T23:03:00Z',42)
   self.assertEqual({r['value']:r['mass'] for r in d['pmf']},expected[stat])
   for line in (0,1,1.5,2):
    got=threshold_triplet(d['pmf'],line)
    self.assertAlmostEqual(got['over'],sum(m for k,m in expected[stat].items() if k>line))
    self.assertAlmostEqual(sum(got.values()),1.)

class EarlyExitPositive(unittest.TestCase):
 def test_full_pipeline_early_exit_exposure(self):
  c=coherent_case();j=copy.deepcopy(c['scenarios']);o=copy.deepcopy(c['opportunity'])
  for sc in j['scenarios']:
   sc['players'][0]['minutes']=24.;sc['players'][5].update(minutes=24.,participation='PLAYED')
   j['opportunity_witness'][sc['scenario_id']]=[{k:x[k] for k in ('player_id','team_id','minutes','participation')} for x in sc['players']]
  for sc in o['scenarios']:
   sc['players'][0]['minutes']=24.;sc['players'][5].update(minutes=24.,participation='PLAYED')
  for idx in (0,5):o['players'][idx]['minutes_law']['parameters']['support']=[{'minutes':24.,'mass':1.}]
  o=edit(o,lambda x:None);j=edit(j,lambda x:x.update(opportunity_sha256=o['content_hash']))
  d=marginal_from_joint(j,c['pregame'],c['pregame']['players'][0]['player_id'],'points','2026-11-16T23:03:00Z',42)
  self.assertTrue(validate_forecast(d,c['pregame'],g=c['game_state'],o=o,scenarios=j))
