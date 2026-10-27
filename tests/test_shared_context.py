"""Source-owned baselines and joint lineup allocation across sports."""
import copy
import json
import os
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import usage_baseline as ub
import shared_context as sc
import scouting_engine as se
import pickem_math as pm

NOW=datetime(2026,10,26,18,tzinfo=timezone.utc)

def fact(value,event='injury:Q:2026-10-26'):
    return dict(fact='verified status',value=value,confidence='confirmed',source_url='https://www.nba.com/injury',
                retrieved_at=NOW.isoformat(),event_id=event,effective_at='2026-10-26T10:00:00Z')

def history(sport='NBA',stat='points'):
    games=[]
    for i in range(40):
        absent=i>=20
        games.append(dict(id=str(i),date=(datetime(2026,8,1)+timedelta(days=i)).date().isoformat(),source_url='https://www.nba.com/stats/',
                          active_players=['P','R'] if absent else ['P','Q','R'],roster_complete=True,team_total=100,
                          production={'P':40,'R':60} if absent else {'P':20,'Q':30,'R':50}))
    return dict(sport=sport,team='T',stat=stat,games=games)

def baseline():
    rows=[dict(id=f'g{i}',date=f'2026-10-{i+1:02}',value=10+i%3,workload=20+i%2) for i in range(15)]
    data=dict(sport='NBA',player_id='P',stat='points',game_date='2026-10-27',team='T',source_url='https://www.nba.com/stats/',
              retrieved_at=NOW.isoformat(),version=ub.VERSION,observations=rows,
              a_inputs=dict(baseline_mean=10,baseline_n=10,recent_mean=11,recent_n=5,season_n=15,sd=2,var_ratio=None,prior_n=None,prior_mean=None))
    c=dict(sport='NBA',player_id='P',stat='points',game_date='2026-10-27',team='T',side='over',line=10.5,
           dist='normal',sd=2,baseline_mean=10,baseline_n=10,recent_mean=11,recent_n=5,season_n=15)
    import fetch_slate as fs
    summary=fs.summarize_log([dict(tie=r['id'],when=r['date'],value=r['value'],workload=r['workload']) for r in rows],'points')
    c.update(baseline_mean=summary['baseline_window_mean'],baseline_n=summary['baseline_n'],recent_mean=summary['recent_mean'],recent_n=summary['recent_n'],season_n=summary['season_n'],sd=summary['sd'])
    c['observation_ids']=summary['observation_ids']
    c['scouting']={'historical_usage':ub.key('NBA','P','points','2026-10-27')}
    return c,data

class SourceBaselineTests(unittest.TestCase):
    def test_engine_a_source_check_remains_independent_when_b_abstains(self):
        c,data=baseline()
        c.update(id='NBA|P|points|over',soft_flags=0,mechanisms=2,hard_veto=False,data_veto=False,
                 research_checklist=True,q_market=.6,retrieved_minutes_ago=1)
        b=dict(abstain=True,reliable=False,abstain_reason='thin_usage_history',version=se.VERSION)
        with patch.object(ub,'load',return_value=data),patch.object(se,'project_scout',return_value=b):
            result=pm.evaluate_candidate(c,now=NOW)
        self.assertTrue(result['engine_a']['reliable'])
        self.assertFalse(result['engine_b']['reliable'])
        self.assertNotEqual(result['final_rank'],'Tier 1')

    def test_collector_cache_drives_real_pipeline_without_researcher_totals(self):
        import fetch_slate as fs
        c,data=baseline();row={k:c[k] for k in ('sport','team','stat','player_id','game_date')}
        row.update(source_url=data['source_url'],retrieved_at=NOW.isoformat())
        fs.apply_log_summary(row,[dict(tie=r['id'],when=r['date'],value=r['value'],workload=r['workload']) for r in data['observations']])
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'PICKEM_DATA_DIR':d}):
            ub.persist([row],d)
            c['scouting']={'historical_usage':row['historical_usage'],'scenarios':[{'opportunities':999,'conversion':999}]}
            c.update(id='NBA|P|points|over',soft_flags=0,mechanisms=2,hard_veto=False,data_veto=False,
                     research_checklist=True,q_market=.6,retrieved_minutes_ago=1)
            result=pm.evaluate_candidate(c,now=NOW)
            self.assertTrue(result['engine_a']['reliable'])
            self.assertTrue(result['engine_b']['reliable'])
            c['baseline_mean']+=1
            changed=pm.evaluate_candidate(c,now=NOW)
            self.assertFalse(changed['engine_a']['reliable'])
            self.assertNotIn(changed['final_rank'],('Tier 1','Tier 2','Tier 3'))

    def test_packet_numbers_and_injury_narrative_cannot_move_b(self):
        c,data=baseline()
        with patch.object(ub,'load',return_value=data):
            first=se.project_scout(c,now=NOW)
            c['scouting'].update(scenarios=[dict(opportunities=999,conversion=999)],injuries='Invented bonus')
            c['baseline_mean']=999
            self.assertEqual(first,se.project_scout(c,now=NOW))
            self.assertTrue(first['reliable'])
            self.assertEqual(first['baseline_origin'],'collector_observations')

    def test_a_numbers_must_match_collector_records(self):
        c,data=baseline()
        with patch.object(ub,'load',return_value=data):
            self.assertTrue(ub.verify_a(c,NOW))
            c['baseline_mean']*=1.2
            self.assertFalse(ub.verify_a(c,NOW))

    def test_duplicate_and_future_history_rejected(self):
        for change in ('duplicate','future'):
            c,data=baseline()
            if change=='duplicate':data['observations'].append(data['observations'][0])
            else:data['observations'][0]['date']='2026-10-26'
            with patch.object(ub,'load',return_value=data):
                self.assertTrue(se.project_scout(c,now=NOW)['abstain'])

class JointAllocationTests(unittest.TestCase):
    def setup_case(self,sport='NBA',stat='points'):
        c,data=baseline();c.update(sport=sport,stat=stat)
        with patch.object(ub,'load',return_value=data):b=ub.project(c,NOW)
        c['observation_ids']={'baseline':[str(i) for i in range(10)],'recent':[str(i) for i in range(10,15)],'prior':[]}
        b['terms']['observation_ids']=[str(i) for i in range(15)]
        b['terms']['recent_observation_ids']=[str(i) for i in range(10,15)]
        b['mean_b']=20
        b['terms']['observed_production']={str(i):20 for i in range(15)}
        a=pm.project('normal','over',10.5,20,15,sd=2,observation_ids={'baseline':[str(i) for i in range(15)]})
        blend=dict(q_win=.6,q_push=0,weights={'a':.7,'b':.3})
        context=dict(events=[dict(player_id='Q',availability=fact('out'),effective_at='2026-10-26T10:00:00Z')])
        return c,a,b,blend,context

    def test_volume_vacuum_is_one_conserved_joint_change_across_sports(self):
        for sport,stat in [('NBA','points'),('NBA','threes'),('NFL','tackles + assists'),('NHL','shots on goal')]:
            c,a,b,blend,ctx=self.setup_case(sport,stat)
            with tempfile.TemporaryDirectory() as d,patch.object(sc,'history_path',return_value=Path(d)/'history.json'):
                (Path(d)/'history.json').write_text(json.dumps(history(sport,stat)))
                out=sc.apply(c,a,b,blend,ctx,NOW)
            self.assertTrue(out['eligible'],out)
            self.assertTrue(out['applied']);self.assertEqual(out['factor'],2)
            self.assertAlmostEqual(sum(out['allocation_shares'].values()),1)
            self.assertEqual(len(out['ledger']),1)
            self.assertEqual(out['components']['a']['mean'],40)
            self.assertLessEqual(out['q_win']+out['q_push'],1)

    def test_out_is_ineligible_not_an_under_probability(self):
        c,a,b,blend,ctx=self.setup_case();c['side']='under';ctx['subject_status']=fact('out')
        out=sc.apply(c,a,b,blend,ctx,NOW)
        self.assertFalse(out['eligible']);self.assertIsNone(out['q_win']);self.assertIsNone(out['projection'])

    def test_duplicate_injury_and_baseline_overlap_blocked(self):
        c,a,b,blend,ctx=self.setup_case()
        ctx['events']*=2
        self.assertFalse(sc.apply(c,a,b,blend,ctx,NOW)['eligible'])
        ctx['events']=ctx['events'][:1];ctx['events'][0]['effective_at']='2026-10-01T00:00:00Z'
        ctx['events'][0]['availability']['effective_at']='2026-10-01T00:00:00Z'
        out=sc.apply(c,a,b,blend,ctx,NOW)
        self.assertFalse(out['eligible']);self.assertIn('overlaps baseline',out['detail'])

    def test_no_researcher_factors_or_partial_rosters(self):
        c,a,b,blend,ctx=self.setup_case();ctx['factor']=1.5
        self.assertFalse(sc.apply(c,a,b,blend,ctx,NOW)['eligible'])
        data=history();data['games'][0]['production']['P']=99
        with self.assertRaises(ValueError):sc.validate_history(data)
        data=history();data['games'][0]['roster_complete']=False
        with self.assertRaises(ValueError):sc.validate_history(data)

    def test_simultaneous_absences_require_joint_samples(self):
        c,a,b,blend,ctx=self.setup_case()
        ctx['events'].append(dict(player_id='R',availability=fact('out','injury:R:2026-10-26'),effective_at='2026-10-26T10:00:00Z'))
        with tempfile.TemporaryDirectory() as d,patch.object(sc,'history_path',return_value=Path(d)/'history.json'):
            (Path(d)/'history.json').write_text(json.dumps(history()))
            result=sc.apply(c,a,b,blend,ctx,NOW)
        self.assertFalse(result['eligible']);self.assertFalse(result['applied'])

    def test_attempt_drive_and_passing_edges_explain_one_adjustment(self):
        c,a,b,blend,ctx=self.setup_case()
        data=history()
        for row in data['games']:
            absent='Q' not in row['active_players']
            row['features']={'three_point_attempts':{'P':12 if absent else 8},
                             'drives':{'P':10 if absent else 5},
                             'passes_to':{'R>P':7 if absent else 3}}
        with tempfile.TemporaryDirectory() as d,patch.object(sc,'history_path',return_value=Path(d)/'history.json'):
            (Path(d)/'history.json').write_text(json.dumps(data))
            out=sc.apply(c,a,b,blend,ctx,NOW)
        self.assertTrue(out['applied'])
        self.assertEqual(out['observed_role_changes']['three_point_attempts|P']['delta'],4)
        self.assertEqual(out['observed_role_changes']['passes_to|R>P']['delta'],4)
        self.assertEqual(out['factor'],2)
        self.assertEqual(len(out['ledger']),1)

    def test_real_pipeline_checks_source_history_and_out_gate(self):
        c,data=baseline()
        c.update(id='NBA|P|points|over',soft_flags=0,mechanisms=2,hard_veto=False,data_veto=False,
                 research_checklist=True,q_market=.6,retrieved_minutes_ago=1)
        with patch.object(ub,'load',return_value=data):
            result=pm.evaluate_candidate(c,now=NOW)
            self.assertTrue(result['engine_a']['reliable'])
            self.assertTrue(result['engine_b']['reliable'])
            c['event_context']={'subject_status':fact('out')}
            out=pm.evaluate_candidate(c,now=NOW)
            self.assertEqual(out['final_rank'],'Unranked')
            self.assertIsNone(out['shared_context']['q_win'])

if __name__=='__main__':unittest.main()
