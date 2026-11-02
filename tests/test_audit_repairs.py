"""Adversarial regression cases from the fresh audit, with offline integration."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import scouting_engine as se
import probability_blend as pb
import pickem_math as pm
import context_feeds as cf
import jobs
import test_engine_contracts as fixtures
from test_engine_contracts import controlled_candidate
from test_nfl_season_store import NOW, profiles, fact
from nfl_season_store import candidate_context


def receiving():
    c=fixtures.ScoutingEngineTests().candidate('NFL','receptions')
    c.update(player_id='RB',team='A')
    p=c['scouting'];p['season_context']=candidate_context(profiles(),'A','D','RB')
    p['confirmed_passer']=fact('Q')
    for f in list(p['evidence'].values())+list(p['supporting_stats'].values()):
        f['retrieved_at']=NOW.isoformat()
    for row,n in zip(p['scenarios'],[20,30]):
        row.pop('opportunities')
        row['season_projection']=dict(mode='receiving',passer_id='Q',expected_pass_attempts=n)
    return c


class TypeAndReliabilityTests(unittest.TestCase):
    def test_receiving_cannot_use_tackle_engine(self):
        c=receiving();c.update(player_id='M',team='D')
        c['scouting']['season_context']=candidate_context(profiles(),'D','R','M')
        for row in c['scouting']['scenarios']:
            row.pop('conversion');row['season_projection']=dict(mode='tackles',expected_defensive_plays=60)
        self.assertEqual(se.project_scout(c,now=NOW)['abstain_reason'],'season_projection_stat_mode_mismatch')

    def test_receptions_cannot_exceed_targets(self):
        c=receiving()
        for row in c['scouting']['scenarios']:row['conversion']=2
        self.assertEqual(se.project_scout(c,now=NOW)['abstain_reason'],'conversion_exceeds_one_per_opportunity')

    def test_combined_tackle_data_cannot_score_solo_tackles(self):
        c=receiving();c['stat']='tackles'
        for row in c['scouting']['scenarios']:
            row.pop('conversion');row['season_projection']=dict(mode='tackles',expected_defensive_plays=60)
        self.assertEqual(se.project_scout(c,now=NOW)['abstain_reason'],'season_projection_stat_mode_mismatch')

    def test_complete_checklist_does_not_prove_reliability(self):
        result=se.project_scout(fixtures.ScoutingEngineTests().candidate())
        self.assertTrue(result['coverage']['complete'])
        self.assertFalse(result['reliable'])
        self.assertIn('uncontrolled_numeric_inputs',result['quality']['reasons'])
        self.assertIn('unsourced_scenario_weights',result['quality']['reasons'])

    def test_sourced_estimates_are_usable_and_integrate_uncertainty(self):
        c=controlled_candidate();out=se.project_scout(c)
        self.assertFalse(out['reliable'])
        self.assertIn('researcher_numeric_baseline_not_eligible',out['quality']['reasons'])
        for row in out['terms']['scenarios']:
            self.assertGreater(row['mean_se'],0)
            self.assertNotEqual(row['q_win'],row['q_win_point'])
            self.assertLessEqual(row['q_win']+row['q_push'],1)
        c['side']='under';under=se.project_scout(c)
        self.assertAlmostEqual(out['q_win_b']+under['q_win_b']+out['q_push_b'],1)

    def test_numeric_units_uncertainty_and_sample_size_checked(self):
        for key,value in [('unit','targets'),('se',0),('n',0),('estimate',True)]:
            c=controlled_candidate();c['scouting']['scenarios'][0]['numeric_inputs']['conversion']['value'][key]=value
            self.assertTrue(se.project_scout(c)['abstain'],(key,value))
        c=controlled_candidate();c['scouting']['scenarios'][0]['numeric_inputs']['conversion']['value']['n']=3
        out=se.project_scout(c)
        self.assertFalse(out['abstain']);self.assertFalse(out['reliable'])

    def test_scalar_cannot_hide_an_extra_adjustment(self):
        c=controlled_candidate();c['scouting']['scenarios'][0]['conversion']=.9
        self.assertTrue(se.project_scout(c)['abstain'])

    def test_unsourced_or_false_scenario_frequencies_cannot_qualify(self):
        c=controlled_candidate();c['scouting']['scenario_weight_evidence']['value']['counts']=[10,90]
        self.assertEqual(se.project_scout(c)['abstain_reason'],'invalid_scenario_weight_evidence')
        c=controlled_candidate();c['scouting']['scenario_weight_evidence']['value']['counts']=[4,6]
        self.assertFalse(se.project_scout(c)['reliable'])

    def test_sparse_season_samples_remain_diagnostics(self):
        out=se.project_scout(receiving(),now=NOW)
        self.assertFalse(out['abstain']);self.assertFalse(out['reliable'])
        self.assertIn('thin_defense_comparison',out['quality']['reasons'])

    def test_a_requires_verified_disjoint_observations_to_be_reliable(self):
        a=pm.project('poisson','over',3,4,30)
        self.assertFalse(pm._engine_a_block(a)['reliable'])
        a=pm.project('poisson','over',3,4,30,observation_ids={'baseline':[str(i) for i in range(30)]})
        self.assertTrue(pm._engine_a_block(a)['reliable'])
        for ids in ({'baseline':[' ']*30},{'baseline':[str(i) for i in range(30)],'other':['x']}):
            with self.assertRaises(pm.PickemError):pm.project('poisson','over',3,4,30,observation_ids=ids)


class ExecutedEffectTests(unittest.TestCase):
    def scenario(self):
        c=controlled_candidate();row=c['scouting']['scenarios'][0]
        row.pop('opportunities');row.pop('conversion')
        return c,row

    def adjustment(self, row, factors, event='injury:P:2026-10-26'):
        evidence={**controlled_candidate()['scouting']['evidence']['injuries'],
                  'event_id':event,'value':dict(factors=factors,factor_se={k:.01 for k in factors},n=60)}
        return dict(factors=factors,evidence=evidence)

    def test_joint_change_executes_once_and_generates_ledger(self):
        c,row=self.scenario();row['adjustments']=[self.adjustment(row,{'opportunities':1.2,'conversion':1.1})]
        out=se.project_scout(c)
        self.assertFalse(out['reliable'])
        result=out['terms']['scenarios'][0]
        self.assertAlmostEqual(result['mean'],6*.5*1.2*1.1)
        self.assertEqual(len(result['effect_ledger']),1)
        self.assertEqual(result['effect_ledger'][0]['applied_by'],'controlled_numeric_transform')

    def test_same_injury_across_two_inputs_rejected(self):
        c,row=self.scenario();row['adjustments']=[self.adjustment(row,{'opportunities':1.2}),self.adjustment(row,{'conversion':1.1})]
        result=se.project_scout(c)
        self.assertTrue(result['abstain']);self.assertIn('duplicate causal effect',result['abstain_detail'])

    def test_embedded_baseline_injury_cannot_be_applied_again(self):
        c,row=self.scenario();row['numeric_inputs']['opportunities']['value']['embedded_event_ids']=['injury:P:2026-10-26']
        row['adjustments']=[self.adjustment(row,{'conversion':1.1})]
        result=se.project_scout(c)
        self.assertTrue(result['abstain']);self.assertIn('embedded',result['abstain_detail'])

    def test_annotations_cannot_replace_controlled_changes(self):
        c,row=self.scenario();row['applied_effects']=[dict(event_id='injury:x',inputs=['conversion'])]
        self.assertTrue(se.project_scout(c)['abstain'])


class OperationalCalibrationTests(unittest.TestCase):
    def rows(self):
        rows=[]
        for day in range(90):
            dt=datetime(2025,1,1,tzinfo=timezone.utc)+timedelta(days=day)
            for i in range(5):
                rows.append(dict(id=f'{day}-{i}',scope='NFL|receptions',date=dt.date().isoformat(),
                                 a_win=.6,a_push=.2,b_win=.3,b_push=.6,
                                 outcome=['win','win','win','push','loss'][i]))
        return rows

    def test_push_mass_is_scored_and_retained(self):
        cfg=pb.fit(self.rows())
        self.assertEqual(cfg['weight_a'],.99)
        self.assertEqual(cfg['validation']['score_rule'],pb.SCORE_RULE)
        self.assertGreater(cfg['validation']['holdout_pushes'],0)
        self.assertEqual(cfg['validation']['train_n']+cfg['validation']['holdout_n'],450)

    def test_forecasts_without_proven_pre_game_times_are_excluded(self):
        row=dict(run_at='anything',game_date='2025-01-01',sport='NFL',player='P',stat='receptions',side='over',reference_line=3,
                 outcome='win',engine_a=dict(version='history-v5',reliable=True,observation_ids_verified=True,q_win_robust=.6,q_push_robust=.1),
                 engine_b=dict(version='scouting-v7',baseline_origin='collector_observations',reliable=True,abstain=False,q_win=.7,q_push=.1))
        self.assertEqual(pb.from_snapshots([row],'NFL|receptions'),[])
        row.update(forecast_at='2025-01-01T12:00:00Z',event_start='2025-01-01T18:00:00Z')
        self.assertEqual(len(pb.from_snapshots([row],'NFL|receptions')),1)
        row['forecast_at']=row['event_start']
        self.assertEqual(pb.from_snapshots([row],'NFL|receptions'),[])

    def test_weekly_uses_current_fitter_and_never_reports_legacy_weights(self):
        with tempfile.TemporaryDirectory() as d,patch.object(jobs.calibration_report,'main',return_value=0),patch.object(pb,'fit_scopes',return_value={}) as fit:
            path=Path(d)/'snapshots.jsonl'
            result=jobs.run_weekly(snapshot_path=path,root=Path(d))
            fit.assert_called_once_with([],Path(d))
            self.assertEqual(result['calibration_status'],'underpowered_or_unvalidated')

    def test_stale_configs_remain_archived_but_never_auto_promote(self):
        with tempfile.TemporaryDirectory() as d:
            path=pb.config_path(d,'NFL|receptions');path.parent.mkdir(parents=True)
            original=json.dumps(dict(scope='NFL|receptions',engine_version='old'))
            path.write_text(original)
            status=pb.fit_scopes([],d)
            self.assertEqual(path.read_text(),original)
            self.assertEqual(status['NFL|receptions']['status'],'underpowered_or_unvalidated')
            self.assertTrue(status['NFL|receptions']['production_unchanged'])

    def test_gaps_calls_engine_validation_for_incompatible_packet(self):
        c=receiving();c['scouting']['scenarios'][0]['conversion']=2
        packet={'scouting':{'NFL|P|receptions|over':c['scouting']}}
        gaps=cf.gap_paths_for_shortlist(packet,['NFL|P|receptions|over'],now=NOW)
        self.assertTrue(any(g['reason']=='conversion_exceeds_one_per_opportunity' for g in gaps))

    def test_gaps_detects_stale_b_facts(self):
        c=controlled_candidate();packet={'scouting':{'NBA|P|points|over':c['scouting']}}
        now=datetime.now(timezone.utc)+timedelta(hours=2)
        gaps=cf.gap_paths_for_shortlist(packet,['NBA|P|points|over'],now=now)
        self.assertTrue(any(g['reason']=='invalid_matchup' for g in gaps))


if __name__=='__main__':unittest.main()
