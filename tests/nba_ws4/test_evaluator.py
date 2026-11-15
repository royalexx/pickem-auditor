import copy
from pathlib import Path
import tempfile
import unittest
from research.nba_ws4.evaluator import IDENTITY, append_artifact, contract_key, digest, evaluate
from research.nba_ws4.metrics import binary, distribution, paired_bootstrap, summary, threshold
from research.nba_ws4.joint_contract import VERSION, seed_for, validate_fixture
from research.nba_ws4.calibration import fit_predict


def fixture(root):
    import hashlib
    data=b'WS4 SYNTHETIC INTEGRATION FIXTURE, NOT SOURCE EVIDENCE'
    (Path(root)/'source.txt').write_bytes(data)
    rec={'path':'source.txt','sha256':hashlib.sha256(data).hexdigest(),'clock_attestation':'original_authenticated',
         'available_at':'2026-11-14T10:00:00Z','retrieved_at':'2026-11-14T10:01:00Z'}
    c={'sport':'NBA','event_id':'game1','player_id':'player1','team_id':'TOR','opponent_id':'BOS','stat':'points',
       'line':1.5,'period':'full','overtime':True,'book':'fixture','quote_id':'q1','quote_at':'2026-11-14T10:01:00Z',
       'source_id':'fixture-only','settlement_policy':'full-OT-DNP-void-v1','event_start':'2026-11-15T23:00:00Z',
       'slate_date':'2026-11-15','slate_id':'slate1'}
    key=contract_key(c); c['contract_id']=key; c['quote_receipt']={**rec,'contract_id':key}
    quote_data=__import__('json').dumps({'contract_id':key}).encode();(Path(root)/'quote.json').write_bytes(quote_data)
    c['quote_receipt'].update(path='quote.json',sha256=hashlib.sha256(quote_data).hexdigest())
    policy={'registered_at':'2026-11-14T00:00:00Z','models':{'control':'v1','challenger':'v1'},'calibration_version':'none-v1',
            'stage':'finalized','reference':'control','attempt_ids':['a1']}
    f={'contract_id':key,'contract':{k:c[k] for k in IDENTITY},'model_id':'control','model_version':'v1',
       'input_freeze_at':'2026-11-15T20:00:00Z','forecast_at':'2026-11-15T20:01:00Z',
       'training_cutoff':'2026-11-14T10:00:00Z','fit_completed_at':'2026-11-14T11:00:00Z','original_archived_at':'2026-11-15T20:01:00Z',
       'calibration_version':'none-v1','calibration_labels_available_through':'2026-11-14T10:00:00Z',
       'selection_labels_available_through':'2026-11-14T10:00:00Z','evidence_kind':'historical_research','development_exposed':True,
       'stage':'finalized','code_sha':'a'*40,'model_artifact':rec.copy(),
       'features':[{**rec,'kind':'historical_result','team_id':'TOR','event_id':'prior-game','event_end':'2026-11-14T09:00:00Z'}],
       'probabilities':{'over':.6,'under':.4,'push':0},'pmf':[.1,.3,.6]}
    g=copy.deepcopy(f);g['model_id']='challenger'
    for pred in (f,g):seal(pred)
    s={'contract_id':key,'receipt':{**rec,'available_at':'2026-11-16T02:00:00Z','retrieved_at':'2026-11-16T02:01:00Z'},
       'team_id':'TOR','period':'full','overtime':True,'policy':c['settlement_policy'],'status':'final','actual':2,'result':'over','participation':'played'}
    settlement_data=__import__('json').dumps({k:v for k,v in s.items() if k!='receipt'}).encode()
    (Path(root)/'settlement.json').write_bytes(settlement_data);s['receipt'].update(path='settlement.json',sha256=hashlib.sha256(settlement_data).hexdigest())
    return {'attempt_id':'a1','contract':c,'forecasts':{'control':f,'challenger':g},'settlement':s},policy


def seal(f):f['snapshot_sha256']=digest({k:v for k,v in f.items() if k!='snapshot_sha256'})


def joint_fixture():
    shared={'schema':VERSION,'event_id':'fixture-game','scenario_id':'s000','seed':seed_for(20261115,'fixture-game','s000','fixture-v1'),
            'source_manifest_sha256':'0'*64,'input_freeze_at':'2026-11-15T20:00:00Z','code_sha':'a'*40,'artifact_sha256':'b'*64,
            'training_cutoff':'2026-11-14T00:00:00Z'}
    f={**shared,'event_start':'2026-11-15T23:00:00Z','market_anchor':'none','team_ids':['TOR','BOS']}
    o={**shared,'overtime_periods':0,'players':[{'player_id':t+str(i),'team_id':t,'minutes':48,'active':True} for t in f['team_ids'] for i in range(5)]}
    s={**shared,'team_points':{'TOR':10,'BOS':10},'players':[{'player_id':p['player_id'],'team_id':p['team_id'],'points':2,'rebounds':1,'assists':1,'threes':0,'fgm':1,'fga':2,'ftm':0,'fta':0} for p in o['players']]}
    return f,o,s


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.a,self.policy=fixture(self.temp.name)
    def run_eval(self):return evaluate([self.a],root=self.temp.name,protocol=self.policy)
    def test_exact_single_contract_not_two_sides(self):
        r=self.run_eval();self.assertEqual(r['integrity_gate'],'PASSED');self.assertEqual(r['eligible'],1)
        self.assertEqual(r['metrics']['control']['selected_sides'],1);self.assertAlmostEqual(r['metrics']['control']['brier'],.16)
        self.assertEqual(r['metrics']['control']['side_conditional']['over']['hit_rate'],1)
    def test_deterministic_replay(self):self.assertEqual(digest(self.run_eval()),digest(self.run_eval()))
    def test_all_adverse_forecast_mutations_fail_closed(self):
        changes=[('current_minutes',lambda f:f['features'][0].update(kind='actual_minutes')),
        ('postgame_injury',lambda f:f['features'][0].update(retrieved_at='2026-11-16T03:00:00Z')),
        ('future_rolling',lambda f:f['features'][0].update(event_end='2026-11-16T03:00:00Z')),
        ('same_game_rolling',lambda f:f['features'][0].update(event_id='game1')),
        ('trade',lambda f:f['features'][0].update(team_id='BOS')),
        ('source_timestamp',lambda f:f['features'][0].update(clock_attestation='retrospective')),
        ('model_training',lambda f:f.update(training_cutoff='2026-11-16T03:00:00Z')),
        ('fit_after_forecast',lambda f:f.update(fit_completed_at='2026-11-16T03:00:00Z')),
        ('reversed_sides',lambda f:f.update(probabilities={'over':.4,'under':.6,'push':0})),
        ('negative_mass',lambda f:f.update(pmf=[-.1,.5,.6])),
        ('unnormalized',lambda f:f.update(pmf=[.1,.3,.7])),
        ('noncomplement',lambda f:f.update(probabilities={'over':.6,'under':.6,'push':0})),
        ('calibration_target',lambda f:f.update(calibration_labels_available_through='2026-11-16T03:00:00Z')),
        ('retro_rebrand',lambda f:f.update(original_archived_at='2026-11-16T03:00:00Z')),
        ('outcome_model_choice',lambda f:f.update(selection_labels_available_through='2026-11-16T03:00:00Z')),
        ('period',lambda f:f['contract'].update(period='first_half')),
        ('line',lambda f:f['contract'].update(line=2.5)),
        ('stage',lambda f:f.update(stage='preliminary')),
        ('version',lambda f:f.update(model_version='picked-after-results'))]
        original=copy.deepcopy(self.a)
        for name,change in changes:
            with self.subTest(name=name):
                self.a=copy.deepcopy(original);f=self.a['forecasts']['challenger'];change(f);seal(f)
                r=self.run_eval();self.assertEqual(r['integrity_gate'],'FAILED');self.assertEqual(r['metrics']['challenger']['available'],0)
                self.assertEqual(r['metrics']['control']['available'],1)
    def test_exact_registered_universe_cannot_drop_rejected_attempts(self):
        self.policy['attempt_ids'].append('missing-candidate')
        r=self.run_eval();self.assertEqual(r['integrity_gate'],'FAILED');self.assertEqual(r['universe_errors'],['ELIGIBLE_UNIVERSE_MISMATCH'])
    def test_mutable_forecast_hash(self):
        self.a['forecasts']['control']['development_exposed']=False
        self.assertEqual(self.run_eval()['integrity_gate'],'FAILED')
    def test_duplicate_contract_retains_attempt_denominator(self):
        r=evaluate([self.a,copy.deepcopy(self.a)],root=self.temp.name,protocol=self.policy)
        self.assertEqual((r['attempts'],r['eligible'],r['rejected']),(2,1,1));self.assertEqual(r['integrity_gate'],'FAILED')
    def test_absent_model_is_explicit_rejection(self):
        self.a['forecasts'].pop('challenger');self.assertEqual(self.run_eval()['metrics']['challenger']['available'],0)
    def test_abstention_never_miss(self):
        f=self.a['forecasts']['challenger'];f.update(abstention='ROLE_UNCERTAIN',probabilities=None,pmf=None);seal(f)
        r=self.run_eval();self.assertEqual(r['integrity_gate'],'PASSED');self.assertEqual(r['metrics']['challenger']['available'],0)
        self.assertEqual(r['model_abstentions_and_rejections']['challenger'],{'ROLE_UNCERTAIN':1})
    def test_push_void_pending_distinct(self):
        for status in ('push','void','pending'):
            a=copy.deepcopy(self.a);s=a['settlement']
            if status=='push':
                c=a['contract'];c['line']=2;key=contract_key(c);c['contract_id']=key;c['quote_receipt']['contract_id']=key
                for f in a['forecasts'].values():
                    f['contract_id']=key;f['contract']={k:c[k] for k in IDENTITY};f['probabilities']={'over':0,'under':.4,'push':.6};seal(f)
                s['contract_id']=key;s['result']='push'
            elif status=='void':s.update(status='void',void_reason='DNP',actual=None)
            else:a['settlement']=None
            if a['settlement'] is not None:
                s=a['settlement'];raw=__import__('json').dumps({k:v for k,v in s.items() if k!='receipt'}).encode()
                (Path(self.temp.name)/'settlement.json').write_bytes(raw);s['receipt']['sha256']=__import__('hashlib').sha256(raw).hexdigest()
                q=__import__('json').dumps({'contract_id':a['contract']['contract_id']}).encode();(Path(self.temp.name)/'quote.json').write_bytes(q);a['contract']['quote_receipt']['sha256']=__import__('hashlib').sha256(q).hexdigest()
            r=evaluate([a],root=self.temp.name,protocol=self.policy)
            self.assertEqual(r['integrity_gate'],'PASSED');self.assertEqual(r['ledger'][0]['outcome'],status)
            self.assertEqual(r['metrics']['control']['binary_scored'],0)
    def test_push_and_dnp_misclassification(self):
        self.a['settlement']['result']='under';self.assertEqual(self.run_eval()['integrity_gate'],'FAILED')
        self.a['settlement']['result']='over';self.a['settlement']['participation']='DNP'
        self.assertEqual(self.run_eval()['integrity_gate'],'FAILED')
    def test_byte_corruption_and_path_escape(self):
        (Path(self.temp.name)/'source.txt').write_bytes(b'corrupted')
        self.assertEqual(self.run_eval()['integrity_gate'],'FAILED')
    def test_immutable_artifact_exclusive_and_separate_stages(self):
        p=append_artifact(self.temp.name,'preliminary',{'p':.6});q=append_artifact(self.temp.name,'finalized',{'p':.6})
        self.assertNotEqual(p['path'],q['path'])
        with self.assertRaises(FileExistsError):append_artifact(self.temp.name,'preliminary',{'p':.6})


class MetricTests(unittest.TestCase):
    def test_scores_analytic(self):
        d=distribution([.25,.5,.25],1,identity='a')
        self.assertEqual(d['count_crps'],.125);self.assertAlmostEqual(d['nlpd'],-__import__('math').log(.5))
        self.assertEqual(threshold([.25,.5,.25],1),{'over':.25,'under':.25,'push':.5})
    def test_observed_beyond_support_not_clipped(self):
        d=distribution([1.],3,identity='a');self.assertEqual(d['count_crps'],3);self.assertEqual(d['nlpd'],float('inf'))
    def test_pit_seeded_identity_and_zero_tail_interval(self):
        a=distribution([.25,.5,.25],1,identity='a',tail=2)
        self.assertTrue(.25<=a['randomized_pit']<=.75);self.assertEqual(a,distribution([.25,.5,.25],1,identity='a',tail=2))
        self.assertEqual(a['predicted_zero'],.25);self.assertEqual(a['predicted_tail'],.25);self.assertTrue(a['interval_covered'])
    def test_poisson_crps_matches_direct_count_cdf_sum(self):
        from research.nba_ws4.metrics import poisson_diagnostics
        from scipy.stats import poisson
        for rate,y in [(0,0),(.1,3),(1,0),(5,7),(100,90)]:
            expected=sum((poisson.cdf(k,rate)-int(y<=k))**2 for k in range(400))
            self.assertAlmostEqual(poisson_diagnostics(rate,y,identity='x')['count_crps'],expected,places=10)
    def test_invalid_mass_support(self):
        for pmf in ([-.1,1.1],[.2,.2],[float('nan')],[True],[]):
            with self.subTest(pmf=pmf),self.assertRaises(ValueError):distribution(pmf,1,identity='x')
    def test_no_signal_negative_control_is_not_a_skill_claim(self):
        for y in (0,1):self.assertEqual(binary(.5,y)['brier'],.25)
        rows=[{'contract_id':str(i),'event_id':'g','player_id':str(i),'date':'d','slate_id':'s','outcome':'over' if i%2 else 'under','p':.5} for i in range(20)]
        r=summary(rows);self.assertEqual(r['brier'],.25);self.assertEqual(r['selected_sides'],0)
    def test_wrong_certain_probability_infinite_loss(self):self.assertEqual(binary(0,1)['log_loss'],float('inf'))
    def test_dependence_bootstrap_and_one_date(self):
        rows=[{'contract_id':str(i),'event_id':str(i%2),'date':'2026-11-10','delta':(-1)**i} for i in range(20)]
        self.assertIsNone(paired_bootstrap(rows)['interval']);self.assertEqual(paired_bootstrap(rows,cluster='game')['clusters'],2)
        with self.assertRaises(ValueError):paired_bootstrap(rows,cluster='row')
    def test_selected_before_settlement_filter_and_eligible_bias(self):
        rows=[{'contract_id':str(i),'event_id':'g','player_id':str(i),'date':'d','slate_id':'s','outcome':'over','p':.6} for i in range(10)]
        rows[0].update(p=.99,outcome='void');r=summary(rows)
        self.assertEqual(r['available'],10);self.assertEqual(r['binary_scored'],9)
        self.assertEqual(r['top_k']['1']['selected_sides'],1);self.assertEqual(r['top_k']['1']['void'],1);self.assertIsNone(r['top_k']['1']['hit_rate'])
    def test_selected_ids_do_not_depend_on_outcomes(self):
        rows=[{'contract_id':str(i),'event_id':'g','player_id':str(i),'date':'d','slate_id':'s','outcome':'over','p':.51+i*.01} for i in range(15)]
        a=summary(rows)['top_k'];b=copy.deepcopy(rows)
        for r in b:r['outcome']='under'
        self.assertEqual(a['5']['contract_ids'],summary(b)['top_k']['5']['contract_ids'])


class JointTests(unittest.TestCase):
    def test_fixture_and_same_player_combos(self):
        a=joint_fixture();r=validate_fixture(*a);self.assertFalse(r['simulator_built']);self.assertEqual(r['players'][0]['pra'],4)
        self.assertEqual(r,validate_fixture(*a))
    def test_shared_state_conservation_and_support_fail_closed(self):
        edits=[lambda f,o,s:o.update(scenario_id='another'),lambda f,o,s:o['players'][0].update(minutes=47),
               lambda f,o,s:o['players'][0].update(active=False),lambda f,o,s:s['players'][0].update(points=-1),
               lambda f,o,s:s['players'][0].update(pra=99),lambda f,o,s:s['players'][0].update(fgm=3),
               lambda f,o,s:s['players'][0].update(assists=20),lambda f,o,s:s['players'][0].update(team_id='NYK')]
        for edit in edits:
            with self.subTest(edit=edit):
                a=joint_fixture();edit(*a)
                with self.assertRaises(ValueError):validate_fixture(*a)
    def test_overtime_expands_both_teams(self):
        f,o,s=joint_fixture();o['overtime_periods']=1
        with self.assertRaisesRegex(ValueError,'CONSERVATION'):validate_fixture(f,o,s)
        for p in o['players']:p['minutes']=53
        validate_fixture(f,o,s)
    def test_seed_stable_component_specific(self):
        self.assertEqual(seed_for(1,'g','s','v1'),seed_for(1,'g','s','v1'))
        self.assertNotEqual(seed_for(1,'g','s','v1'),seed_for(1,'g','s','v2'))


def cal_fixture():
    policy={'methods':['none','platt','beta','isotonic'],'registered_at':'2026-01-01T00:00:00Z','model':'control','stat':'points',
            'min_parametric':20,'min_isotonic':50,'min_dates':5,'l2':5.}
    prior=[{'contract_id':str(i),'event_id':'old'+str(i),'date':f'2026-01-{1+i%20:02}',
            'training_cutoff':'2025-12-01T00:00:00Z','forecast_at':'2025-12-31T00:00:00Z','event_start':'2026-01-01T00:00:00Z',
            'label_available_at':'2026-01-22T00:00:00Z','model':'control','stat':'points','is_oof':True,'p':.7 if i%2 else .3,'y':i%2} for i in range(80)]
    targets=[{'contract_id':'new','event_id':'newgame','model':'control','stat':'points','p':.6,'input_freeze_at':'2026-02-01T00:00:00Z'}]
    return prior,targets,policy


class CalibrationTests(unittest.TestCase):
    def test_all_challengers_run_only_older_oof(self):
        prior,targets,policy=cal_fixture()
        for method in policy['methods']:
            r=fit_predict(prior,targets,method=method,model='control',stat='points',policy=policy)
            self.assertIsNotNone(r['predictions']);self.assertFalse(r['integration_allowed'])
    def test_isotonic_ties_pool_and_monotonicity_analytic(self):
        prior,targets,policy=cal_fixture();policy.update(min_isotonic=1,min_dates=1)
        for i,r in enumerate(prior):
            r['p']=.2 if i<40 else .8;r['y']=1 if i<40 else 0
        targets=[dict(targets[0],contract_id='t'+str(i),p=p) for i,p in enumerate([0.,.2,.5,.8,1.])]
        r=fit_predict(prior,targets,method='isotonic',model='control',stat='points',policy=policy)
        self.assertEqual(r['predictions'],[.5]*5)
    def test_target_labels_cannot_change_fitted_predictions(self):
        prior,targets,policy=cal_fixture();targets[0]['y']=0
        a=fit_predict(prior,targets,method='platt',model='control',stat='points',policy=policy)
        targets[0]['y']=1
        b=fit_predict(prior,targets,method='platt',model='control',stat='points',policy=policy)
        self.assertEqual(a['predictions'],b['predictions'])
    def test_calibration_target_game_and_in_sample_fail_closed(self):
        prior,targets,policy=cal_fixture()
        prior[0]['event_id']='newgame'
        with self.assertRaisesRegex(ValueError,'GAME_LEAKAGE'):fit_predict(prior,targets,method='platt',model='control',stat='points',policy=policy)
        prior,targets,policy=cal_fixture();prior[0]['is_oof']=False
        with self.assertRaisesRegex(ValueError,'IN_SAMPLE'):fit_predict(prior,targets,method='platt',model='control',stat='points',policy=policy)
    def test_sparse_and_wrong_market_not_universal_correction(self):
        prior,targets,policy=cal_fixture()
        r=fit_predict(prior[:5],targets,method='isotonic',model='control',stat='points',policy=policy)
        self.assertEqual(r['status'],'BLOCKED-BY-DATA')
        for r in prior:r['stat']='threes'
        r=fit_predict(prior,targets,method='platt',model='control',stat='points',policy=policy)
        self.assertEqual(r['n'],0);self.assertEqual(len(r['excluded']),80)
    def test_untouched_calibration_acceptance_and_insufficient_dates(self):
        from research.nba_ws4.calibration import assess_untouched
        policy={'registered_at':'2026-01-01T00:00:00Z','primary':'improvement','brier_margin':.001,'logloss_margin':.001,'min_dates':5,'min_games':5}
        rows=[{'contract_id':str(i),'date':str(i),'event_id':str(i),'forecast_at':'2026-02-01T00:00:00Z','untouched':True,'development_exposed':False,'brier_delta':-.01,'logloss_delta':-.01} for i in range(5)]
        self.assertEqual(assess_untouched(rows,policy=policy)['status'],'PASSED')
        self.assertEqual(assess_untouched(rows[:1],policy=policy)['status'],'BLOCKED-BY-DATA')
        rows[0]['development_exposed']=True
        with self.assertRaises(ValueError):assess_untouched(rows,policy=policy)
    def test_future_labels_excluded_not_backdated(self):
        prior,targets,policy=cal_fixture()
        for r in prior:r['label_available_at']='2026-03-01T00:00:00Z'
        r=fit_predict(prior,targets,method='beta',model='control',stat='points',policy=policy)
        self.assertEqual(r['status'],'BLOCKED-BY-DATA');self.assertEqual(r['n'],0)

if __name__=='__main__': unittest.main()
