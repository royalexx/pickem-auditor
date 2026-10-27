import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import unittest
from datetime import datetime,timezone
from copy import deepcopy
import research_packet as rp
import context_feeds as cf
from research_resolver import resolve

NOW=datetime(2026,10,26,23,tzinfo=timezone.utc)
class ESPNGoalieTests(unittest.TestCase):
 def packet(self):
  p=rp.empty_template('2026-10-26');p['index']['by_player']['Goalie']={'sport':'NHL','team':'TOR','game':'TOR@CGY','player_id':'nhl-1'}
  p['availability']['Goalie']={'status':None,'primary_source':None};p['_keep']='preserved'
  p['player_context']={'Goalie':{'other_fact':{'value':1}}};return p
 def scoreboard(self,status='confirmed',state='pre'):
  return {'events':[{'id':'1','date':'2026-10-27T00:30:00Z','status':{'type':{'state':state}},'competitions':[{'competitors':[{'team':{'abbreviation':'TOR'},'probables':[{'name':'probableStartingGoalie','athlete':{'id':'espn-2','displayName':'Goalie'},'status':{'type':status}}]},{'team':{'abbreviation':'CGY'}}]}]}]}
 def run_case(self,board=None,packet=None):
  def fetch(url,**kwargs):
   if 'scoreboard' in url:return board or self.scoreboard()
   return {'header':{'id':'1','competitions':[{'status':{'type':{'state':'pre'}}}]}}
  return resolve(packet or self.packet(),['NHL|Goalie|goalie saves|over'],fetch,now=NOW)
 def test_explicit_confirmed_sets_named_starter_and_active(self):
  p,r=self.run_case()
  self.assertEqual(p['availability']['Goalie']['status']['value'],'active')
  self.assertTrue(p['player_context']['Goalie']['goalie_confirmed']['value'])
  self.assertNotIn('goalie_confirmed',p.get('lineup',{}).get('TOR',{}))
  self.assertEqual(r['resolved_goalies'],['Goalie'])
  self.assertEqual(p['_keep'],'preserved');self.assertIn('other_fact',p['player_context']['Goalie'])
  gaps=cf.gap_paths_for_shortlist(p,['NHL|Goalie|goalie saves|over'],now=NOW)
  self.assertNotIn('lineup.TOR.goalie_confirmed',[g['path'] for g in gaps])
 def test_probable_is_not_confirmed(self):
  for status in ('probable','unconfirmed',None):
   p,r=self.run_case(self.scoreboard(status));self.assertIsNone(p['availability']['Goalie']['status']);self.assertEqual(r['resolved_goalies'],[])
 def test_started_game_not_backfilled(self):
  p,r=self.run_case(self.scoreboard(state='in'));self.assertEqual(r['resolved_goalies'],[])
 def test_wrong_team_or_player_does_not_transfer(self):
  for change in ('team','player'):
   b=self.scoreboard();c=b['events'][0]['competitions'][0]['competitors'][0]
   if change=='team':c['team']['abbreviation']='CGY'
   else:c['probables'][0]['athlete']['displayName']='Different Goalie'
   p,r=self.run_case(b);self.assertEqual(r['resolved_goalies'],[])
 def test_conflicting_out_requires_resolution(self):
  p=self.packet();p['availability']['Goalie']['status']=cf.confirmed_fact('status','out','https://www.nhl.com/news',NOW.isoformat())
  p,r=self.run_case(packet=p);self.assertIsNone(p['availability']['Goalie']['status']);self.assertEqual(r['resolved_goalies'],[])
  self.assertEqual(p['_source_conflicts'][-1]['resolution'],'unresolved')
 def test_two_confirmed_starters_do_not_pick_first(self):
  b=self.scoreboard();ls=b['events'][0]['competitions'][0]['competitors'][0]['probables'];ls.append(deepcopy(ls[0]))
  p,r=self.run_case(b);self.assertEqual(r['resolved_goalies'],[])
