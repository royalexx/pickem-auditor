"""Regression tests for audit-identified safety and correctness defects."""
import sys
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'scripts'))
import research_packet as rp
import fetch_slate as fs
import pickem_math as pm
import reads_engine as re
import jobs
import context_feeds as cf
import schedule_gate

NOW=datetime(2026,10,22,16,10,tzinfo=timezone.utc)
def fact(value, url='https://www.nhl.com/article'):
    return {'fact':'verified', 'value':value, 'source_url':url,
            'retrieved_at':'2026-10-22T16:10:00+00:00', 'confidence':'confirmed', 'quote':'official report'}

class AuditRegressionTests(unittest.TestCase):
    def test_probability_unit_mismatch_cannot_agree(self):
        check=pm.crosscheck({'mean':6,'q_win':.90},
                            {'mean_b':5,'q_win_b':.60,'se_b':4,'abstain':False},
                            {'line':3.5,'side':'over'})
        self.assertEqual(check['b_vote'],'disagree')
        self.assertLessEqual(check['tolerance'],1)

    def test_mechanisms_are_events_not_urls(self):
        a=rp.ValidatedFact('a','a','https://nba.com/1',NOW,'confirmed')
        b=rp.ValidatedFact('b','b','https://nba.com/2',NOW,'confirmed')
        one=[{'type':'role','description':'new starting role','event_id':'injury-slot',
              'supports_side':'over','sources':[a,b]}]
        self.assertEqual(rp._distinct_mechanism_sources(one,'over'),1)
        two=one+[{'type':'pace','description':'faster opponent',
                   'supports_side':'over','event_id':'opponent-tempo','sources':[a]}]
        self.assertEqual(rp._distinct_mechanism_sources(two,'over'),2)

    def test_fake_source_url_rejected(self):
        issues=[]
        rp._validate_fact('fake',fact(1,url='foo-not-a-url'),issues,require_fresh=True,now=NOW)
        self.assertTrue(any('absolute public HTTP' in v.message for v in issues))

    def test_out_and_unknown_availability_fail_closed(self):
        packet={'index':{'by_player':{'P':{'team':'BOS','sport':'NBA'}}},
                'availability':{'P':{'status':fact('out')}}, 'mechanisms':{}}
        validated, issues=rp.validate_packet(packet,now=NOW)
        self.assertEqual(issues,[])
        base={'id':'NBA|P|points|over','baseline_n':20,'baseline_mean':12,
              'data_veto':'no','hard_veto':'no'}
        merged=rp.merge_into_pipeline(validated,[base])[0]
        self.assertEqual(merged['hard_veto'],'yes')
        packet['availability'].clear()
        valid,_=rp.validate_packet(packet,now=NOW)
        self.assertEqual(rp.merge_into_pipeline(valid,[base])[0]['data_veto'],'yes')

    def test_unknown_goalie_and_qb_gated(self):
        self.assertIn('STARTING_GOALIE_UNCONFIRMED',pm.derive_vetoes_and_flags(
            {'side':'under','stat':'saves'})['data_veto_reasons'])
        self.assertIn('STARTING_QB_UNCONFIRMED',pm.derive_vetoes_and_flags(
            {'side':'over','stat':'passing yards'})['data_veto_reasons'])

    def test_role_window_disagreement_never_mutates_n(self):
        packet={'index':{'by_player':{'P':{'team':'BOS','sport':'NBA'}}},
                'availability':{'P':{'status':fact('active')}},
                'role_changes':{'P':{'confirmed_by_primary_source':True,
                                   'old_role_n':fact(10), 'new_role_n':fact(5)}}}
        valid,issues=rp.validate_packet(packet,now=NOW)
        self.assertEqual(issues,[])
        row={'id':'NBA|P|points|over','baseline_mean':14,'baseline_n':30,
             'recent_mean':16,'recent_n':3,'data_veto':'no'}
        out=rp.merge_into_pipeline(valid,[row])[0]
        self.assertEqual(out['baseline_n'],30)
        self.assertEqual(out['recent_n'],3)
        self.assertEqual(out['data_veto'],'yes')

    def test_partial_read_abstains(self):
        row={'sport':'NFL','stat':'receptions','side':'over','line':3.5,
             'dist':'poisson','team_pass_attempts_expected':34,
             'team_bucket_throw_share':.20,'checkdown_target_share':.4,
             'checkdown_player_games':10,'checkdown_team_games':10,
             'conversion':.8,'def_matchup_factor':1.0}
        self.assertEqual(re.project_reads(row)['abstain_reason'],'partial_bucket_not_total_stat')

    def test_prep_errors_without_quotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            slate=Path(tmp)/'slate.jsonl'
            slate.write_text(json.dumps({'sport':'NBA','player':'X','stat':'points'})+'\n')
            with self.assertRaises(SystemExit) as cm:
                fs.run_prep(['--slate',str(slate),'--stdout'])
            self.assertEqual(cm.exception.code,2)

    def test_same_date_two_snapshot_slots_distinct(self):
        self.assertNotEqual(jobs.shadow_run_id('2026-10-22','09:00'),
                            jobs.shadow_run_id('2026-10-22','14:00'))

    def test_nfl_schedule_is_timezone_aware(self):
        games=cf.games_from_schedules('2026-10-25',nfl_schedule=[{
            'gameday':'2026-10-25','away_team':'NE','home_team':'NYJ',
            'gametime':'13:00'}])
        self.assertEqual(games[0]['commence_time'],'2026-10-25T17:00:00+00:00')
        self.assertIsNone(cf._parse_iso('2026-10-25T13:00:00'))

    def test_daylight_gate(self):
        summer=datetime(2026,6,1,14,2,tzinfo=timezone.utc)
        winter=datetime(2026,12,7,14,2,tzinfo=timezone.utc)
        self.assertEqual(schedule_gate.scheduled_job('0 13 * * *',summer),'snapshot')
        self.assertEqual(schedule_gate.scheduled_job('0 14 * * *',summer),'skip')
        self.assertEqual(schedule_gate.scheduled_job('0 13 * * *',winter),'skip')
        self.assertEqual(schedule_gate.scheduled_job('0 14 * * *',winter),'snapshot')

    def test_ambiguous_name_is_vetoed(self):
        packet={'index':{'by_player':{'A':{'sport':'NFL','team':'NWE','game':'NWE@BUF'}}}}
        valid,issues=rp.validate_packet(packet,now=NOW)
        self.assertFalse(issues)
        row={'id':'NBA|A|points|over','team':'BOS','data_veto':'no'}
        out=rp.merge_into_pipeline(valid,[row])[0]
        self.assertEqual(out.get('identity_issue'),'AMBIGUOUS_PLAYER_OR_GAME')
