"""Deterministic schema/value/temporal/metamorphic sweep, no external data."""
import copy,json,random,unittest
from pathlib import Path
from golden_v2 import golden_cases,pregame,game_state,opportunity,j_scenarios
from test_g0_pipeline_completion_20261116 import coherent_case
from test_g0_completion_20261116 import edit
from test_v2_contracts import reissue,evaluation
from v2.nba_architecture.v2_contracts import (ContractError,seal,validate_pregame,validate_distribution,validate_scenarios,validate_offer,validate_offer_view,validate_evaluation,threshold_triplet,canonical)
from v2.nba_architecture.families_v2 import validate_game_state,validate_opportunity,validate_forecast

class MutationSweep(unittest.TestCase):
 def objects(self):
  c=golden_cases()['prospective_original_offer'];j=coherent_case();p=c['pregame']
  return [(p,validate_pregame),(c['distribution'],lambda x:validate_distribution(x,p)),(c['offer'],lambda x:validate_offer(x,p)),(c['offer_view'],lambda x:validate_offer_view(x,c['distribution'],c['offer'],p)),(evaluation(c['distribution'],c['offer_view']),lambda x:validate_evaluation(x,c['distribution'],c['offer_view'])),(j['game_state'],lambda x:validate_game_state(x,j['pregame'])),(j['opportunity'],lambda x:validate_opportunity(x,j['pregame'],j['game_state'])),(j['scenarios'],lambda x:validate_scenarios(x,j['pregame']))]
 def test_every_top_level_required_field_deleted(self):
  for obj,validator in self.objects():
   self.assertTrue(validator(obj))
   for key in obj:
    with self.subTest(kind=obj['kind'],deleted=key):
     bad=copy.deepcopy(obj);bad.pop(key)
     if key!='content_hash':bad.pop('content_hash');bad=seal(bad)
     with self.assertRaises(ContractError):validator(bad)
 def test_every_closed_object_rejects_added_field(self):
  schema=json.loads(Path('v2/nba_architecture/schema-2.0.0.json').read_text())
  def resolve(s):return schema['$defs'][s['$ref'].split('/')[-1]] if '$ref' in s else s
  def paths(obj,s,path=()):
   s=resolve(s)
   if isinstance(obj,dict):
    if s.get('additionalProperties') is False:yield path
    for k,v in obj.items():
     if k in s.get('properties',{}):yield from paths(v,s['properties'][k],path+(k,))
   elif isinstance(obj,list):
    for i,v in enumerate(obj):yield from paths(v,s.get('items',{}),path+(i,))
  for obj,validator in self.objects():
   for path in paths(obj,schema['$defs'][obj['kind']]):
    with self.subTest(kind=obj['kind'],path=path):
     bad=copy.deepcopy(obj);target=bad
     for key in path:target=target[key]
     target['hidden_target_outcome']=12
     bad.pop('content_hash');bad=seal(bad)
     with self.assertRaises(ContractError):validator(bad)
 def test_numerical_boundary_mutations(self):
  c=coherent_case()
  for field in ('weight','overtime_periods'):
   for value in (-1,True,None,'1'):
    with self.subTest(field=field,value=value):
     j=edit(c['scenarios'],lambda x:x['scenarios'][0].update({field:value}))
     with self.assertRaises(ContractError):validate_scenarios(j,c['pregame'])
  for value in (float('nan'),float('inf'),-float('inf')):
   with self.assertRaises(ValueError):canonical({'value':value})
 def test_every_physical_stat_identity_mutated(self):
  c=coherent_case()
  # Negative and fractional counts are always invalid, irrespective of their label.
  for stat in c['scenarios']['scenarios'][0]['players'][0]['stats']:
   for value in (-1,.25,True):
    with self.subTest(stat=stat,value=value):
     j=edit(c['scenarios'],lambda x:x['scenarios'][0]['players'][0]['stats'].update({stat:value}))
     with self.assertRaises(ContractError):validate_scenarios(j,c['pregame'])
 def test_all_source_clocks_cross_freeze(self):
  for clock in ('collector_observed_at','retrieved_at','ingested_at','provider_published_at'):
   p=pregame('original_prospective')
   def mutate(x):
    change={clock:'2026-11-16T23:00:00.000001Z'}
    if clock=='provider_published_at':change['publication_evidence']='source_header_claim'
    x['sources'][0]=reissue(x['sources'][0],**change)
    x['features'][0]['source_receipt_sha256']=x['sources'][0]['receipt_sha256']
   with self.subTest(clock=clock):
    with self.assertRaises(ContractError):validate_pregame(edit(p,mutate))
 def test_consistent_player_rename_preserves_forecast(self):
  c=coherent_case();old=c['pregame']['players'][0]['player_id'];new='espn:player:renamed'
  def rename(x):
   if isinstance(x,dict):return {k:rename(v) for k,v in x.items()}
   if isinstance(x,list):return [rename(v) for v in x]
   return new if x==old else x
  p=edit(rename(c['pregame']),lambda x:None)
  j=rename(c['scenarios']);j['source_snapshot_sha256']=p['content_hash'];g=game_state(p,j);o=rename(c['opportunity']);o.update(source_snapshot_sha256=p['content_hash'],game_state_sha256=g['content_hash']);o=edit(o,lambda x:None)
  j.update(game_state_sha256=g['content_hash'],opportunity_sha256=o['content_hash']);j=edit(j,lambda x:None)
  from v2.nba_architecture.v2_contracts import marginal_from_joint
  d=marginal_from_joint(j,p,new,'points','2026-11-16T23:03:00Z',42)
  self.assertTrue(validate_forecast(d,p,g=g,o=o,scenarios=j))
 def test_legal_overtime_and_early_exit_positive(self):
  c=coherent_case();p=c['pregame'];j=copy.deepcopy(c['scenarios'])
  for sc in j['scenarios']:
   sc['overtime_periods']=1;sid=sc['scenario_id'];j['game_state_witness'][sid]['overtime_periods']=1
   for x in sc['players']:
    if x['participation']=='PLAYED':x['minutes']=53.
   j['opportunity_witness'][sid]=[{k:x[k] for k in ('player_id','team_id','minutes','participation')} for x in sc['players']]
  g=game_state(p,j);o=opportunity(p,g,j)
  for x in o['players']:
   support=sorted({row['minutes'] for sc in o['scenarios'] for row in sc['players'] if row['player_id']==x['player_id'] and row['participation']!='DNP'})
   x['minutes_law']={'family':'discrete_minutes','conditioning':'given_played','units':'minutes','parameters':{'support':[{'minutes':m,'mass':1/len(support)} for m in support]}}
  o=edit(o,lambda x:None);j.update(game_state_sha256=g['content_hash'],opportunity_sha256=o['content_hash']);j=edit(j,lambda x:None)
  from v2.nba_architecture.families_v2 import validate_integration
  self.assertTrue(validate_integration(j,p,g,o))
