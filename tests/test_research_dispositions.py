import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from research_dispositions import dispositions
import context_feeds as cf
import pickem_math as pm
import research_packet as rp
from scouting_checklist import required_checks

class DispositionTests(unittest.TestCase):
 def test_diagnostic_tier_does_not_publish(self):
  r={'id':'a','final_rank':'Unranked','grade':{'probability_rank':'NUMERIC_TIER_2','data_veto':True},'research_issues':['STATUS_NOT_VERIFIED']}
  d=dispositions(['a'],[r])['candidates'][0]
  self.assertEqual(d['disposition'],'blocked');self.assertFalse(d['publication_eligible'])
  self.assertIn('STATUS_NOT_VERIFIED',d['blockers'])
  self.assertIn('SOURCED_CAUSAL_MECHANISM_REQUIRED',d['remaining_review'])
 def test_exclusion_overrides_rank(self):
  d=dispositions(['a'],[{'id':'a','final_rank':'Tier 2'}],excluded={'a':'GAME_STARTED'})['candidates'][0]
  self.assertEqual(d['final_rank'],'Unranked');self.assertFalse(d['publication_eligible'])
 def test_missing_and_duplicate_audit_rejected(self):
  for rows in [[],[{'id':'a'},{'id':'a'}]]:
   with self.assertRaises(ValueError):dispositions(['a'],rows)
 def test_goalie_alias_requires_starter_not_skater_lines(self):
  p=rp.empty_template('2026-10-26');p['index']['by_player']['P']={'team':'TOR','sport':'NHL','game':'TOR@CGY'}
  gaps=cf.gap_paths_for_shortlist(p,['NHL|P|goalie saves|under'])
  paths=[g['path'] for g in gaps]
  self.assertIn('lineup.TOR.goalie_confirmed',paths);self.assertNotIn('lineup.TOR.pp1',paths)
  self.assertIn('expected_starter',required_checks('NHL','goalie saves'))
 def test_historical_scout_questions_remain_review_not_numeric_inputs(self):
  p=rp.empty_template('2026-10-26');rid='NHL|P|shots on goal|over'
  p['scouting'][rid]={'historical_usage':{'ref':'fixture'}}
  with patch('scouting_engine.project_scout',return_value={'abstain':False,'reliable':True}):
   gaps=cf.gap_paths_for_shortlist(p,[rid])
  scout=[g for g in gaps if g['path'].startswith('scouting.')]
  self.assertTrue(scout);self.assertTrue(all(g['requirement']=='supporting_research' and g['requires_review'] for g in scout))
 def test_availability_blocker_survives_scan(self):
  row=dict(id='NHL|P|shots on goal|over',dist='poisson',side='over',line=1.5,baseline_mean=3,baseline_n=30,q_market=.55,retrieved_minutes_ago=5,hard_veto=False,data_veto=True,research_checklist=False,stat='shots on goal',outdoor=False,availability_issue='STATUS_NOT_VERIFIED')
  scan=pm.scan_candidates([row])
  self.assertEqual(scan['research_candidates'][0]['verification_gaps'],['STATUS_NOT_VERIFIED'])
