import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import hashlib
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import slate_model_report as report
import nuts_slate_shadow as nuts


def fixture():
    return dict(game_date='2026-11-08',run_id='r',forecast_at='2026-11-08T20:00:00Z',
        event_start='2026-11-08T23:00:00Z',sport='NFL',player='Player',player_id='p',
        stat='receptions',side='over',reference_line=2.,team='BUF',opponent='MIA',
        home_team='BUF',away_team='MIA',matchup_orientation_verified=True,event_id='g',event_id_namespace='test',
        run_type='shadow',engine_a={'q_win_robust':.8,'q_push_robust':.1,'version':'a'},
        engine_b={'q_win':.4,'q_push':.2,'version':'b'},q_model=.68,q_push=.13,
        blend={'version':'production-test','production_policy':True,'available':True},
        books=[{'book':'FanDuel','line':2.,'over':-110,'under':-110}])


def quote():
    r=fixture()
    return {**{k:r[k] for k in ('sport','player','team','opponent','event_start','event_id','event_id_namespace','stat')},
            'book':'FanDuel','line':2.,'over_odds':-110,'under_odds':-110,'retrieved_at':'2026-11-08T19:59:00Z'}


class SlateReportTests(unittest.TestCase):
    def test_all_models_share_exact_side_line_and_nonpush_scale(self):
        row=fixture();item={**row,'status':'forecast','version':'bayes','q_win':.4,'q_push':.2,
                           'generated_at':'2026-11-08T20:01:00Z'}
        result=report.build(row,{'Bayesian_A':{nuts.identity(row):item}},[quote()])
        self.assertAlmostEqual(result['Engine_A'],.8/.9)
        self.assertAlmostEqual(result['Engine_B'],.5)
        self.assertAlmostEqual(result['Consensus'],.68/.87)
        self.assertEqual(result['Bayesian_A'],.5)
        self.assertEqual(result['Market'],.5)
        self.assertIsNone(result['Bayesian_B']);self.assertIsNone(result['NUTS'])
        self.assertEqual(result['NUTS_status'],'unavailable')

    def test_wrong_identity_and_poststart_models_are_not_substituted(self):
        row=fixture();item={**row,'status':'forecast','q_win':.9,'q_push':0,
                           'generated_at':'2026-11-08T23:01:00Z'}
        result=report.build(row,{'NUTS_population':{nuts.identity(row):item}},[quote()])
        self.assertIsNone(result['NUTS'])
        self.assertIn('poststart',result['NUTS_reason'])
        for change in ({'event_id':'other'},{'line':3.},{'retrieved_at':'2026-11-08T20:01:00Z'}):
            self.assertIsNone(report.build(row,{},[{**quote(),**change}])['Market'])

    def test_conflicting_sidecars_fail_closed(self):
        row=fixture()
        with self.assertRaisesRegex(ValueError,'conflicting_model'):
            report.index_sidecars([row,{**row,'q_win':.1}])

    def test_fixed_nuts_priority_not_largest_probability(self):
        row=fixture()
        def child(q):return {**row,'status':'forecast','q_win':q,'q_push':0,'generated_at':'2026-11-08T20:01:00Z'}
        idx={'NUTS_population':{nuts.identity(row):child(.95)},'NUTS_saves':{nuts.identity(row):child(.6)}}
        result=report.build(row,idx,[quote()])
        self.assertEqual(result['NUTS'],.6)

    def test_frozen_report_retry_keeps_original_comparison(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'data').mkdir()
            (root/'data/prop_snapshots.jsonl').write_text(json.dumps(fixture())+'\n')
            (root/'data/odds_quotes.jsonl').write_text(json.dumps(quote())+'\n')
            report.run(root,'2026-11-08',root/'reports')
            original=(root/'data/model_comparisons/2026-11-08.jsonl').read_bytes()
            report.run(root,'2026-11-08',root/'reports')
            self.assertEqual((root/'data/model_comparisons/2026-11-08.jsonl').read_bytes(),original)


class NutsLifecycleTests(unittest.TestCase):
    def test_approved_cache_works_when_actions_access_is_forbidden(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/'123'/'nfl-receptions';folder.mkdir(parents=True)
            m=dict(schema='multisport_joint_fit_manifest_v1',model_version='multisport-joint-bayes-v1',
                   family='count',sport='NFL',stat='receptions',max_per_position=0,
                   diagnosed_all_player_and_opponent_effects=True,sampler_chains=4,
                   sampler_retained_draws_per_chain=2000,source_digest='hash',players=['p'],
                   diagnostics=dict(posterior_sampling_ok=True,divergences=0,max_rhat=1.005,
                                    min_bulk_ess=500,minimum_bfmi=.6))
            (folder/'manifest.json').write_text(json.dumps(m));(folder/'posterior.nc').write_bytes(b'copied-fixture')
            receipt={'run_id':123,'models':[{'folder':'nfl-receptions',
                'posterior_sha256':nuts.checksum(folder/'posterior.nc'),
                'manifest_sha256':nuts.checksum(folder/'manifest.json')}]}
            (folder.parent/'artifact_receipt.json').write_text(json.dumps(receipt))
            calls=[]
            def forbidden(request,**kwargs):
                calls.append(request.get_method())
                raise HTTPError('https://api.github.com',403,'forbidden',{},None)
            found,events=nuts.discover(root,wanted={('NFL','receptions')},token='fixture',opener=forbidden)
            self.assertEqual(found,[folder]);self.assertEqual(calls,['GET'])
            self.assertEqual(events[0]['verified_cached_models'],1)
            self.assertEqual((folder/'posterior.nc').read_bytes(),b'copied-fixture')

    def test_active_failed_and_unrelated_runs_are_ignored(self):
        base={'id':1,'name':nuts.WORKFLOW,'status':'completed','conclusion':'success'}
        values=[base,{**base,'id':2,'status':'in_progress'},
                {**base,'id':3,'conclusion':'failure'},{**base,'id':4,'name':'other'}]
        self.assertEqual(nuts.completed_runs(values),[base])

    def test_manifest_strict_gate_is_not_relaxed_for_narrow_failures(self):
        m=dict(schema='multisport_joint_fit_manifest_v1',model_version='multisport-joint-bayes-v1',
               family='count',max_per_position=0,diagnosed_all_player_and_opponent_effects=True,
               sampler_chains=4,sampler_retained_draws_per_chain=2000,source_digest='hash',players=['p'],
               diagnostics=dict(posterior_sampling_ok=True,divergences=0,max_rhat=1.005,
                                min_bulk_ess=500,minimum_bfmi=.6))
        self.assertTrue(nuts.strict_manifest(m))
        for change in ({'min_bulk_ess':389.4},{'max_rhat':1.0101},{'divergences':1},
                       {'minimum_bfmi':.29},{'posterior_sampling_ok':False}):
            self.assertFalse(nuts.strict_manifest({**m,'diagnostics':{**m['diagnostics'],**change}}))


if __name__=='__main__':unittest.main()

class DeploymentRegressionTests(unittest.TestCase):
    def test_nfl_january_uses_previous_season(self):
        from datetime import datetime,timezone
        row={**fixture(),'game_date':'2027-01-10','forecast_at':'2027-01-10T20:00:00Z','event_start':'2027-01-10T23:00:00Z'}
        m=dict(sport='NFL',stat='receptions',players=['p'],opponents=['MIA'],seasons=['2026'],last_game='2026-10-01',training_cutoff_exclusive='2026-10-02')
        self.assertEqual(nuts.candidate_context(row,m,datetime(2027,1,10,21,tzinfo=timezone.utc))['season'],'2026')

    def test_targets_failed_attempt_followed_by_success_is_reportable(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'data/nfl_context').mkdir(parents=True)
            parent={**fixture(),'stat':'targets'}
            (root/'data/prop_snapshots.jsonl').write_text(json.dumps(parent)+'\n')
            failed={**parent,'parent_forecast_at':parent['forecast_at'],'forecast_at':'2026-11-08T20:01:00Z','line_origin':'market','status':'unavailable','reason':'cache_missing'}
            good={**failed,'forecast_at':'2026-11-08T20:02:00Z','generated_at':'2026-11-08T20:03:00Z','status':'forecast','q_win':.8,'q_push':0.}
            (root/'data/nfl_context/2026-11-08.jsonl').write_text('\n'.join(map(json.dumps,[failed,good]))+'\n')
            result=report.run(root,'2026-11-08',root/'reports')
            data=json.loads((root/'reports/slate_model_comparisons.json').read_text())
            self.assertEqual(data['picks'][0]['NUTS'],.8)
            with (root/'data/nfl_context/2026-11-08.jsonl').open('a') as f:f.write(json.dumps({**good,'q_win':.9})+'\n')
            with self.assertRaisesRegex(ValueError,'conflicting_model'):report.run(root,'2026-11-08',root/'reports')
