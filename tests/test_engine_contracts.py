"""Offline contracts for the requested engine architecture."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pickem_math as pm

class HistoricalEngineTests(unittest.TestCase):
    def test_context_cannot_move_a(self):
        args = dict(dist='poisson', side='over', line=3, baseline_mean=4, baseline_n=20)
        plain = pm.project(**args)
        adjusted = pm.project(**args, workload_baseline=10, workload_expected=20,
                              opponent_factor=1.2, pace_factor=1.1, funnel_channels=2)
        for field in ('shrunk_mean', 'q_win', 'q_win_robust', 'sample_effective_n'):
            self.assertEqual(plain[field], adjusted[field])

    def test_prior_and_recent_are_weighted_once(self):
        out = pm.project('poisson', 'over', 3, 4, 10, recent_mean=8, recent_n=5,
                         season_n=15, prior_mean=2, prior_n=5)
        self.assertAlmostEqual(out['shrunk_mean'], 4.5)
        self.assertEqual(out['sample_effective_n'], 20)
        self.assertEqual(out['recent_weight'], .25)

    def test_mass_and_side_symmetry(self):
        for dist, params in [('poisson', {}), ('negbin', {'var_ratio': 2}), ('normal', {'sd': 2})]:
            for line in (0, 2, 2.5, 8):
                out = pm.project(dist, 'over', line, 4, 20, **params)
                self.assertAlmostEqual(out['q_win_over'] + out['q_win_under'] + out['q_push'], 1)
                self.assertAlmostEqual(out['q_win_over_robust'] + out['q_win_under_robust'] + out['q_push_robust'], 1)

    def test_overlap_rejected(self):
        with self.assertRaises(pm.PickemError):
            pm.project('poisson', 'over', 3, 4, 20, recent_mean=5, recent_n=5, season_n=20)

from datetime import datetime, timezone, timedelta
import scouting_engine as se
import probability_blend as pb
import tempfile
import json

class ScoutingEngineTests(unittest.TestCase):
    def candidate(self,sport="NBA",stat="points"):
        stamp=datetime.now(timezone.utc).isoformat()
        evidence={k:dict(fact='scouting observation', value='Verified neutral or directional observation',
                        source_url='https://www.nfl.com/news/test',
                        retrieved_at=stamp, confidence='confirmed') for k in se.DIMENSIONS}
        from scouting_checklist import required_checks
        checks=required_checks(sport,stat)
        supporting={k:dict(evidence['opportunity']) for k in checks}
        return dict(sport=sport,stat=stat,side='over', line=3, baseline_mean=999,
                    scouting=dict(evidence=evidence,supporting_stats=supporting,scenarios=[
                        dict(weight=.4, opportunities=6, conversion=.5, dist='poisson',
                             scope='full_game',drivers=[checks[0]], rationale='Lower volume script'),
                        dict(weight=.6, opportunities=10, conversion=.5, dist='poisson',
                             scope='full_game',drivers=[checks[1]], rationale='Higher volume script')]))

    def test_full_game_scenario_mixture_and_independence(self):
        c=self.candidate(); out=se.project_scout(c)
        self.assertFalse(out['abstain'])
        self.assertAlmostEqual(out['mean_b'],4.2)
        expected=.4*pm.side_probs('poisson',3,3,'over')[0]+.6*pm.side_probs('poisson',5,3,'over')[0]
        self.assertAlmostEqual(out['q_win_b'],expected)
        c['baseline_mean']=1
        self.assertEqual(out,se.project_scout(c))
        c['side']='under'; under=se.project_scout(c)
        self.assertAlmostEqual(out['q_win_b']+under['q_win_b']+out['q_push_b'],1)

    def test_missing_stale_and_partial_evidence_abstains(self):
        for dim in se.DIMENSIONS:
            c=self.candidate(); del c['scouting']['evidence'][dim]
            self.assertTrue(se.project_scout(c)['abstain'])
        c=self.candidate(); c['scouting']['scenarios'][0]['scope']='checkdown'
        self.assertTrue(se.project_scout(c)['abstain'])
        c=self.candidate(); c['scouting']['evidence']['injuries']['retrieved_at']=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()
        self.assertTrue(se.project_scout(c)['abstain'])

    def test_invalid_weights_abstain(self):
        c=self.candidate(); c['scouting']['scenarios'][0]['weight']=.5
        self.assertTrue(se.project_scout(c)['abstain'])

def controlled_candidate():
    c=ScoutingEngineTests().candidate()
    c['scouting']['scenario_weight_evidence']={**c['scouting']['evidence']['game_script'],
        'value':{'counts':[40,60],'method':'Observed comparable full-game script frequencies'}}
    for row in c['scouting']['scenarios']:
        row['numeric_inputs']={}
        for key,unit,se in [('opportunities','possessions',.2),('conversion','points_per_possession',.02)]:
            row['numeric_inputs'][key]={**c['scouting']['evidence']['opportunity'],
                'value':dict(estimate=row[key],se=se,n=50,unit=unit,embedded_event_ids=[])}
    return c

class BlendTests(unittest.TestCase):
    def test_fallback_and_validated_mass(self):
        a=pm.project('poisson','over',3,4,20,observation_ids={'baseline':[str(i) for i in range(20)]})
        b={**se.project_scout(controlled_candidate()),'reliable':True,'baseline_origin':'collector_observations'}
        self.assertFalse(pb.combine(a,b)['validated'])
        cfg=dict(scope="global",engine_version=pb.VERSION,weight_a=.7,underpowered=False,
                 validation=dict(score_rule=pb.SCORE_RULE,train_n=300,holdout_n=100,holdout_dates=25,train_end='2025-01-01',
                                 holdout_start='2025-01-02',holdout_end='2025-03-01',
                                 blend_log_loss=.60,a_log_loss=.62,improvement_ci_low=.001))
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'config.json';p.write_text(json.dumps(cfg))
            out=pb.combine(a,b,p)
            self.assertTrue(out['validated'])
            self.assertAlmostEqual(out['q_win'],.7*a['q_win_robust']+.3*b['q_win_b'])
            self.assertLessEqual(out['q_win']+out['q_push'],1)
            cfg['engine_version']='old';p.write_text(json.dumps(cfg))
            self.assertFalse(pb.combine(a,b,p)['validated'])

    def test_fit_requires_chronological_data_and_rejects_duplicates(self):
        with self.assertRaises(ValueError): pb.fit([])
        row=dict(id='x',date='2025-01-01',a_win=.6,a_push=0,b_win=.6,b_push=0,outcome='win')
        with self.assertRaises(ValueError): pb.fit([row,row])

    def test_missing_b_blocks_tier_one(self):
        out=pm.evaluate_candidate(dict(dist='poisson',side='over',line=2.5,
            baseline_mean=3.5,baseline_n=30,soft_flags=0,mechanisms=2,
            hard_veto=False,data_veto=False,research_checklist=True,
            q_market=.62,retrieved_minutes_ago=1))
        self.assertNotEqual(out['final_rank'],'Tier 1')
        self.assertTrue(out['engine_b']['abstain'])
        self.assertEqual(out['tier_basis'],'q_win_robust')

class PacketIntegrationTests(unittest.TestCase):
    def test_packet_validate_merge_evaluate_in_one_command(self):
        import research_packet as rp
        from contextlib import redirect_stdout
        import io
        c=ScoutingEngineTests().candidate('NBA','points')
        stamp=c['scouting']['evidence']['injuries']['retrieved_at']
        fact=dict(fact='availability',value='active',source_url='https://www.nba.com/injury',
                  retrieved_at=stamp, confidence='confirmed',quote='Status confirmed')
        ident='NBA|Test Player|points|over'
        packet=rp.empty_template(stamp[:10])
        packet['index']['by_player']['Test Player']=dict(sport='NBA',team='BOS')
        packet['availability']['Test Player']={'status':fact}
        packet['scouting'][ident]=c['scouting']
        row=dict(id=ident,stat='points',dist='poisson',side='over',line=3,
                 baseline_mean=4,baseline_n=30,soft_flags=0,mechanisms=0,
                 hard_veto=False,data_veto=False,research_checklist=False,
                 q_market=.6,retrieved_minutes_ago=1,market_retrieved_at=stamp)
        with tempfile.TemporaryDirectory() as tmp:
            packet_path=Path(tmp)/'packet.json';prep=Path(tmp)/'prep.jsonl'
            packet_path.write_text(json.dumps(packet));prep.write_text(json.dumps(row)+'\n')
            out=io.StringIO()
            with redirect_stdout(out):
                code=rp.main(['audit','--packet',str(packet_path),'--prep',str(prep)])
            result=json.loads(out.getvalue())
            self.assertEqual(code,0)
            self.assertFalse(result['engine_b']['abstain'])
            self.assertEqual(result['engine_a']['mean'],4)
            self.assertEqual(result['final_rank'],'Watchlist')

    def test_cross_date_packet_cannot_reuse_research(self):
        import research_packet as rp
        import context_feeds as cf
        old=rp.empty_template('2026-10-25');old['scouting']['x']={'scenarios':['stale']}
        new=rp.empty_template('2026-10-26')
        self.assertEqual(cf.merge_packet_no_clobber(old,new)['scouting'],{})

    def test_push_calibration_uses_conditional_probability(self):
        import report
        self.assertAlmostEqual(report.prediction_probability({'q_grade':.6,'q_push':.2}),.75)
        self.assertAlmostEqual(report.market_probability({'q_market_comparable':.56,'q_push':.2}),.7)
        self.assertAlmostEqual(report.market_probability({'q_market':.7,'q_push':.2}),.7)

    def test_validated_blend_changes_grade_with_both_engines(self):
        from unittest.mock import patch
        c=controlled_candidate()
        c['line']=2.5
        c['scouting']['scenarios'][1]['opportunities']=8
        c['scouting']['scenarios'][1]['numeric_inputs']['opportunities']['value']['estimate']=8
        row=dict(id='NBA|P|points|over',stat='points',dist='poisson',side='over',line=2.5,
                 baseline_mean=3.5,baseline_n=30,observation_ids={'baseline':[str(i) for i in range(30)]},soft_flags=0,mechanisms=2,
                 hard_veto=False,data_veto=False,research_checklist=True,
                 q_market=.65,retrieved_minutes_ago=1,scouting={**c['scouting'],'historical_usage':'trusted-test-reference'})
        cfg=dict(scope='NBA|points',engine_version=pb.VERSION,weight_a=.7,underpowered=False,
                 validation=dict(score_rule=pb.SCORE_RULE,train_n=300,holdout_n=100,holdout_dates=25,train_end='2025-01-01',
                     holdout_start='2025-01-02',holdout_end='2025-03-01',
                     blend_log_loss=.60,a_log_loss=.62,improvement_ci_low=.001))
        with tempfile.TemporaryDirectory() as tmp, patch.object(pm,'SKILL_ROOT',Path(tmp)), patch('usage_baseline.verify_a',return_value=True), patch('scouting_engine.project_scout',return_value={**se.project_scout(c),'reliable':True,'baseline_origin':'collector_observations'}):
            path=pb.config_path(Path(tmp),'NBA|points');path.parent.mkdir(parents=True)
            path.write_text(json.dumps(cfg))
            out=pm.evaluate_candidate(row)
            self.assertTrue(out['blend']['validated'])
            self.assertAlmostEqual(out['grade']['q_model'],.7*out['engine_a']['q_win_robust']+.3*out['engine_b']['q_win'])
            self.assertEqual(out['final_rank'],'Tier 1')

class BlendFitValidationTests(unittest.TestCase):
    def test_weights_fit_before_holdout_and_improvement_activates(self):
        rows=[]
        start=datetime(2025,1,1,tzinfo=timezone.utc)
        for day in range(90):
            for i in range(5):
                rows.append(dict(id=f'{day}-{i}',scope='NFL|receptions',
                    date=(start+timedelta(days=day)).date().isoformat(),
                    a_win=.5,a_push=0,b_win=.6,b_push=0,
                    outcome='win' if i<3 else 'loss'))
        cfg=pb.fit(rows)
        self.assertGreater(cfg['validation']['improvement_ci_low'],0)
        changed=[{**r,'outcome':'loss'} if r['date']>=cfg['validation']['holdout_start'] else r for r in rows]
        self.assertEqual(pb.fit(changed)['weight_a'],cfg['weight_a'])
        a=pm.project('poisson','over',3,4,20,observation_ids={'baseline':[str(i) for i in range(20)]})
        b={**se.project_scout(controlled_candidate()),'reliable':True,'baseline_origin':'collector_observations'}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cfg.json';path.write_text(json.dumps(cfg))
            self.assertTrue(pb.combine(a,b,path,scope='NFL|receptions')['validated'])
            self.assertFalse(pb.combine(a,b,path,scope='NBA|points')['validated'])
            cfg['validation']['improvement_ci_low']=-.001
            path.write_text(json.dumps(cfg))
            self.assertFalse(pb.combine(a,b,path,scope='NFL|receptions')['validated'])

class PredictiveDistributionGateTests(unittest.TestCase):
    def test_normal_predictive_negative_mass_blocks(self):
        out=pm.project('normal','over',6.5,8,5,sd=4)
        self.assertLess(out['normal_left_mass'],.02)
        self.assertTrue(out['distribution_block'])
        self.assertTrue(out['sample_block'])

    def test_malformed_scouting_scenarios_abstain(self):
        row=ScoutingEngineTests().candidate()
        row['scouting']['scenarios']=[None,None]
        self.assertTrue(se.project_scout(row)['abstain'])

class FeedDiagnosticsTests(unittest.TestCase):
    def test_https_proxy_can_resolve_when_local_dns_fails(self):
        import fetch_slate as fs
        from unittest.mock import patch
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):return False
        with patch.object(fs.socket,'getaddrinfo',side_effect=OSError('local DNS unavailable')), \
             patch.object(fs.urllib.request,'getproxies',return_value={'https':'http://proxy.test'}):
            ok, detail=fs.probe_host('api-web.nhle.com',opener=lambda *a,**kw:Response())
        self.assertTrue(ok)
        self.assertIn('200',detail)

    def test_default_preflight_detects_missing_odds_credentials(self):
        import fetch_slate as fs
        from unittest.mock import patch
        with patch.object(fs,'probe_import',return_value=(True,'')), \
             patch.object(fs,'probe_host',return_value=(True,'HTTP 200')), \
             patch.dict(fs.os.environ,{'PROPLINE_API_KEY':''}):
            out=fs.preflight()
        self.assertFalse(out['ok'])
        self.assertTrue(any(x['kind']=='credential' and not x['ok'] for x in out['checks']))

    def test_live_nba_pace_schema_joins_on_team_id(self):
        import fetch_slate as fs
        payload={'resultSets':[{'headers':['TEAM_ID','TEAM_NAME','PACE','POSS'],
                               'rowSet':[[1610612738,'Boston Celtics',99.5,800]]}]}
        out=fs.team_pace_table(payload,{'1610612738':'BOS'})
        self.assertEqual(out['BOS']['pace'],99.5)

    def test_invalid_distribution_metadata_rejected(self):
        with self.assertRaises(pm.PickemError):
            pm.project('negbin','over',2.5,4,20,var_ratio='bad')
        with self.assertRaises(pm.PickemError):
            pm.project('poisson','over',2.5,4,20,role_change='no')

class AdvancedScoutingCoverageTests(unittest.TestCase):
    def test_stat_specific_research_requirements(self):
        from scouting_checklist import required_checks
        nfl=required_checks('NFL','receptions')
        self.assertTrue({'targets_routes','passer_progression','coverage_matchup'}.issubset(nfl))
        nba=required_checks('NBA','pra')
        self.assertTrue({'potential_assists','rebound_opportunities','shot_profile_matchup'}.issubset(nba))
        nhl=required_checks('NHL','shots on goal')
        self.assertTrue({'shot_attempts_rates','line_matching','shot_suppression'}.issubset(nhl))

    def test_missing_coverage_prevents_reliable_b(self):
        row=ScoutingEngineTests().candidate('NFL','receptions')
        del row['scouting']['supporting_stats']['coverage_matchup']
        out=se.project_scout(row)
        self.assertFalse(out['reliable'])
        self.assertIn('coverage_matchup',out['coverage']['missing'])
        row['scouting']['supporting_stats']['coverage_matchup']={**row['scouting']['evidence']['matchup'],'confidence':'inferred'}
        self.assertFalse(se.project_scout(row)['reliable'])

    def test_scenario_requires_a_sourced_driver(self):
        row=ScoutingEngineTests().candidate()
        row['scouting']['scenarios'][0]['drivers']=['invented_coefficient']
        self.assertEqual(se.project_scout(row)['abstain_reason'],'scenario_drivers_need_sourced_stats')
