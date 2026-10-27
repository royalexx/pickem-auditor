import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import unittest
from datetime import datetime,timezone
import context_feeds as cf
import pickem_math as pm
import research_packet as rp
from research_tasks import reconcile,build

class ResearchWorkflowTests(unittest.TestCase):
    def row(self,**extra):
        return dict(id='NHL|Player|shots on goal|over',dist='poisson',side='over',line=1.5,
                    baseline_mean=3.0,baseline_n=30,q_market=.55,retrieved_minutes_ago=5,
                    hard_veto=False,data_veto=False,research_checklist=False,stat='shots on goal',**extra)
    def test_missing_venue_enters_research_not_publication(self):
        r=self.row();scan=pm.scan_candidates([r]);self.assertEqual(scan['shortlist'],[])
        self.assertEqual(len(scan['research_candidates']),1)
        self.assertFalse(scan['research_candidates'][0]['publication_eligible'])
        self.assertIn('VENUE_UNCONFIRMED',scan['research_candidates'][0]['verification_gaps'])
        self.assertEqual(pm.evaluate_candidate(dict(r,mechanisms=2,soft_flags=0))['final_rank'],'Unranked')
    def test_sample_failure_does_not_become_research_edge(self):
        r=self.row();r['baseline_n']=2
        self.assertEqual(pm.scan_candidates([r])['research_candidates'],[])
    def fact(self,value,kind=None,published=None):
        r=cf.confirmed_fact('availability',value,'https://team.test','2026-10-26T22:00:00Z')
        if kind:r['report_type']=kind
        if published:r['published_at']=published
        return r
    def packet(self,fact):
        p=rp.empty_template('2026-10-26');p['availability']['P']={'status':fact,'primary_source':None};return p
    def test_new_download_of_old_report_does_not_override_game_day(self):
        active=self.fact('active','game_day_report','2026-10-26T21:00:00Z')
        old=self.fact('questionable','practice_report','2026-10-25T21:00:00Z')
        merged=cf.merge_packet_no_clobber(self.packet(active),self.packet(old))
        self.assertEqual(merged['availability']['P']['status']['value'],'active')
        self.assertEqual(len(merged['_source_conflicts']),1)
    def test_unknown_report_scope_conflict_abstains(self):
        merged=cf.merge_packet_no_clobber(self.packet(self.fact('active')),self.packet(self.fact('out')))
        self.assertIsNone(merged['availability']['P']['status'])
        self.assertEqual(merged['_source_conflicts'][0]['resolution'],'unresolved')
        refreshed=cf.merge_packet_no_clobber(merged,self.packet(self.fact('active')))
        self.assertIsNone(refreshed['availability']['P']['status'])
    def test_same_count_wrong_ids_is_failure(self):
        with self.assertRaises(ValueError):reconcile([{'id':'a'}],[{'id':'b'}])
        with self.assertRaises(ValueError):reconcile([{'id':'a'},{'id':'b'}],[{'id':'a'},{'id':'a'}])
        self.assertTrue(reconcile([{'id':'a'}],[{'id':'a'}])['ids_match'])
    def test_tasks_deduplicate_shared_paths(self):
        p=rp.empty_template('2026-10-26');p['index']['by_player']['P']={'team':'TOR','game':'TOR@CGY'}
        ids=['NHL|P|shots on goal|over','NHL|P|shots on goal|under']
        tasks=build(p,{'research_candidates':[{'id':i} for i in ids]},[],now=datetime.now(timezone.utc))
        paths=[r['path'] for r in tasks['tasks']]
        self.assertEqual(len(paths),len(set(paths)))
        self.assertFalse(tasks['research_complete'])
