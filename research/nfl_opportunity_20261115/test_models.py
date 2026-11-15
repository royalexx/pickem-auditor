"""Synthetic fixtures only. These are not Sunday forecasts or source receipts."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from research.nfl_opportunity_20261115.models import (
    GateError, MODELS, OpportunityModel, ROLE_MULTIPLIERS, ROLE_WEIGHTS,
    canonical, freeze_output, load_packet, oup, sha, summary, validate)

NOW='2026-11-15T05:00:00+00:00'

def fixture():
    teams=[]; players=[]; roster=[]; contracts=[]
    for week in range(1,10):
        gid='prior'+str(week)
        end=f'2026-11-{week:02d}T00:00:00+00:00'
        for team,opp in (('A','B'),('B','A')):
            teams.append(dict(game_id=gid,team=team,opponent=opp,season=2026,week=week,
                end_at=end,source_id='history',plays=65,pass_attempts=35,rush_attempts=27,sacks=3,
                pace_seconds=29))
            for suffix,pos in (('q','QB'),('b','RB'),('w','WR'),('d','LB')):
                r=dict(game_id=gid,team=team,player_id=team+suffix,position=pos,
                       season=2026,week=week,end_at=end,source_id='history',state='played')
                if pos=='QB':r.update(pass_attempts=34,completions=22,passing_yards=235,carries=5,rushing_yards=25)
                if pos=='RB':r.update(targets=5,receptions=4,receiving_yards=25,carries=17,rushing_yards=70)
                if pos=='WR':r.update(targets=9,receptions=6,receiving_yards=80,carries=0,rushing_yards=0,routes=32)
                if pos=='LB':r.update(snaps=55,solo=4,with_assist=1,tackle_assists=2)
                players.append(r)
    for team in ('A','B'):
        for suffix,pos in (('q','QB'),('b','RB'),('w','WR'),('d','LB'),('backup','QB')):
            r=dict(game_id='target',team=team,player_id=team+suffix,position=pos,
                   source_id='pregame',status='available',participation_probability=.95)
            if pos=='QB':r.update(expected_starter=suffix=='q',starter_probability=.9 if suffix=='q' else .1)
            roster.append(r)
            stats={'QB':['pass attempts','completions','passing yards','qb rushing attempts','qb rushing yards'],
                   'RB':['targets','receptions','receiving yards','carries','rushing yards'],
                   'WR':['targets','receptions','receiving yards'],
                   'LB':['solo tackles','tackle assists','tackles + assists']}[pos]
            for stat in stats:
                contracts.append(dict(contract_id=team+suffix+stat,game_id='target',team=team,
                    player_id=team+suffix,stat=stat,line=5,period='full_game',source_id='pregame',
                    book='SYNTHETIC_TEST_BOOK',quote_id=team+suffix+stat,dnp_policy='void',frozen_60_40={'over':.4,'under':.5,'push':.1},market=None))
    return dict(manifest={'training_cutoff_at':'2026-11-14T00:00:00+00:00',
                         'input_freeze_at':'2026-11-15T04:00:00+00:00'},
        manifest_sha256='fixture_only_not_a_real_manifest',forecast_at=NOW,
        events=[dict(game_id='target',home='A',away='B',season=2026,week=10,
                     event_start='2026-11-15T18:00:00+00:00',source_id='pregame')],
        team_history=teams,player_history=players,roster=roster,contracts=contracts)

def disk_packet(root, p=None):
    p=fixture() if p is None else p
    sources=[]
    for sid,when in [('history','2026-11-13T00:00:00+00:00'),('pregame','2026-11-15T03:00:00+00:00')]:
        data=b'synthetic fixture source '+sid.encode()
        (root/(sid+'.bin')).write_bytes(data)
        sources.append(dict(source_id=sid,provider='SYNTHETIC_TEST_ONLY',original=True,
            path=sid+'.bin',sha256=sha(data),first_available_at=when,ingested_at=when))
    m=dict(schema='ws1-nfl-pregame-opportunity-v1',producer_workstream=1,day='2026-11-15',
           **p['manifest'],sources=sources,files={})
    for name in ('events','team_history','player_history','roster','contracts'):
        data=canonical(p[name]); (root/(name+'.json')).write_bytes(data)
        m['files'][name]={'path':name+'.json','sha256':sha(data)}
    data=canonical(m); (root/'manifest.json').write_bytes(data)
    return root/'manifest.json',sha(data)

class ModelTests(unittest.TestCase):
    def test_all_models_end_to_end_and_no_baseline_mutation(self):
        p=fixture(); before=canonical(p); validate(p)
        r=OpportunityModel(p,2048).run()
        self.assertEqual(canonical(p),before)
        self.assertEqual(len(r['rows']),len(p['contracts'])*5)
        self.assertEqual({x['model'] for x in r['rows']},set(MODELS))
        self.assertTrue(all(t['conservation_max_error']==0 for t in r['team_opportunities']))
        for row in r['rows']:
            if row['status']=='forecast':
                self.assertAlmostEqual(sum(row['probabilities_conditional'].values()),1)
                self.assertGreater(row['max_mc_standard_error'],0)
                if row['contract']['stat'] in ('receiving yards','passing yards','rushing yards','qb rushing yards'):
                    self.assertGreaterEqual(row['workload_conditional']['sd'],0)
        for model in MODELS[1:]:
            self.assertTrue(any(x['status']=='forecast' and x['model']==model for x in r['rows']))

    def test_backups_never_eligible_even_if_history_present(self):
        p=fixture()
        extra=[]
        for h in p['player_history']:
            if h['player_id']=='Aq':
                h=copy.deepcopy(h);h['player_id']='Abackup';extra.append(h)
        # Keep historical exposure legal by removing starter's passing rows for A.
        p['player_history']=[h for h in p['player_history'] if h['player_id']!='Aq']+extra
        validate(p); r=OpportunityModel(p,1024).run()
        self.assertTrue(all(x['status']=='abstain' for x in r['rows'] if x['contract']['player_id']=='Abackup'))

    def test_qb_beta_expectation_independent_numeric_control(self):
        s=.95; rng=np.random.default_rng(1729)
        old=rng.beta(12+35*s,12+35*(1-s),100000)
        fixed=rng.beta(60*s,60*(1-s),100000)
        self.assertAlmostEqual(old.mean(),(12+35*s)/59,delta=.001)
        self.assertAlmostEqual(fixed.mean(),s,delta=.001)
        self.assertGreater(fixed.mean()-old.mean(),.18)

    def test_three_components_and_fail_closed_missing(self):
        p=fixture(); model=OpportunityModel(p,2048); e=p['events'][0]
        r=next(r for r in p['roster'] if r['player_id']=='Ad')
        env=model.environment(e)
        v,active,d=model.defender(e,r,env['B'])
        np.testing.assert_array_equal(v['tackles + assists'],v['solo']+v['with_assist']+v['tackle_assists'])
        self.assertTrue((v['tackles + assists']<=env['B']['plays']).all())
        next(h for h in reversed(p['player_history']) if h['player_id']=='Ad').pop('with_assist')
        with self.assertRaisesRegex(GateError,'missing_official'):
            OpportunityModel(p,1024).defender(e,r,env['B'])

    def test_future_weeks_target_ids_duplicate_and_ranges(self):
        mutations=[('future_week',lambda p:p['team_history'][0].update(week=10)),
            ('target_event',lambda p:p['team_history'][0].update(game_id='target')),
            ('duplicate_team',lambda p:p['team_history'].append(copy.deepcopy(p['team_history'][0]))),
            ('duplicate_player',lambda p:p['player_history'].append(copy.deepcopy(p['player_history'][0]))),
            ('snap_share_range',lambda p:p['player_history'][3].update(snaps=100)),
            ('duplicate_starting',lambda p:p['roster'][4].update(expected_starter=True)),
            ('nonconservation',lambda p:p['team_history'][0].update(plays=66)),
            ('noncomplementary',lambda p:p['contracts'][0]['frozen_60_40'].update(over=.9))]
        for name,mutate in mutations:
            with self.subTest(name=name):
                p=fixture();mutate(p)
                with self.assertRaises(GateError):validate(p)

    def test_pregame_gate_hashes_and_clocks(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path,pin=disk_packet(root)
            p=load_packet(path,pin,NOW);self.assertEqual(len(p['events']),1)
            with self.assertRaisesRegex(GateError,'manifest_hash'):
                load_packet(path,'0'*64,NOW)
            (root/'history.bin').write_bytes(b'CORRUPT')
            with self.assertRaisesRegex(GateError,'original_source_hash'):
                load_packet(path,pin,NOW)
        for field,value in [('first_available_at','2026-11-15T05:00:00+00:00'),
                            ('ingested_at','2026-11-15T05:00:00+00:00')]:
            with tempfile.TemporaryDirectory() as d:
                root=Path(d);path,pin=disk_packet(root);m=json.loads(path.read_text())
                m['sources'][1][field]=value;data=canonical(m);path.write_bytes(data)
                with self.assertRaises(GateError):load_packet(path,sha(data),NOW)

    def test_forbidden_final_script_and_table_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            p=fixture();p['team_history'][0]['final_score_differential']=14
            path,pin=disk_packet(Path(d),p)
            with self.assertRaisesRegex(GateError,'unknown_feature'):
                load_packet(path,pin,NOW)
        with tempfile.TemporaryDirectory() as d:
            path,pin=disk_packet(Path(d));(Path(d)/'roster.json').write_bytes(b'[]')
            with self.assertRaisesRegex(GateError,'table_hash'):
                load_packet(path,pin,NOW)

    def test_source_after_training_cutoff_and_kickoff(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path,pin=disk_packet(root);m=json.loads(path.read_text())
            m['sources'][0]['ingested_at']='2026-11-15T01:00:00+00:00'
            data=canonical(m);path.write_bytes(data)
            with self.assertRaisesRegex(GateError,'historical_source_after_training'):
                load_packet(path,sha(data),NOW)
        with tempfile.TemporaryDirectory() as d:
            path,pin=disk_packet(Path(d))
            with self.assertRaisesRegex(GateError,'kickoff_passed'):
                load_packet(path,pin,'2026-11-15T18:00:00+00:00')

    def test_dnp_unknown_and_injury_reduction(self):
        p=fixture()
        # A defender's last two prior games show a genuine recorded role reduction.
        for h in p['player_history']:
            if h['player_id']=='Ad' and h['week']>=8:
                h.update(snaps=15,solo=1,with_assist=0,tackle_assists=0)
        m=OpportunityModel(p,2048);e=p['events'][0];r=next(r for r in p['roster'] if r['player_id']=='Ad')
        _,_,d=m.defender(e,r,m.environment(e)['B'])
        self.assertLess(d['onfield_share']['mean'],.3)
        for r in p['roster']:
            if r['player_id']=='Ad':r.update(status='out',participation_probability=0)
        out=OpportunityModel(p,1024).run()
        self.assertTrue(all(x['status']=='abstain' for x in out['rows'] if x['contract']['player_id']=='Ad'))
        h=p['player_history'][3];h.update(state='unknown',snaps=None,solo=None,with_assist=None,tackle_assists=None)
        validate(p)

    def test_conservation_mixture_and_determinism(self):
        p=fixture();m=OpportunityModel(p,2048);e=p['events'][0];env=m.environment(e)
        a=m.run();b=m.run();self.assertEqual(canonical(a),canonical(b))
        for mixture in (False,True):
            v,active,d,errors=m.offense(e,'A',env['A'],mixture)
            for metric,cap in [('targets','pass_attempts'),('carries','rush_attempts')]:
                used=sum(x[metric] for x in v.values() if metric in x)
                self.assertTrue((used<=env['A'][cap]).all())
            self.assertTrue((v['Aq']['completions']<=v['Aq']['pass attempts']).all())
            self.assertTrue((v['Aq']['pass attempts']<=env['A']['pass_attempts']).all())
        self.assertAlmostEqual(sum(ROLE_WEIGHTS),1)
        self.assertGreater(np.average(np.square(ROLE_MULTIPLIERS),weights=ROLE_WEIGHTS)-
                           np.average(ROLE_MULTIPLIERS,weights=ROLE_WEIGHTS)**2,0)

    def test_probability_side_reverse_push_and_zero_receiving(self):
        x=np.array([0,1,2,3]);p=oup(x,1)
        self.assertEqual(p,{'over':.5,'under':.25,'push':.25})
        self.assertEqual(oup(-x,-1),{'over':p['under'],'under':p['over'],'push':p['push']})
        self.assertEqual(oup(x,1.5)['push'],0)
        f=fixture();m=OpportunityModel(f,1024)
        r=next(r for r in f['roster'] if r['player_id']=='Aw')
        self.assertTrue((m.yards(r,'receiving_yards','receptions',np.zeros(1024,dtype=int),np.random.default_rng(2))==0).all())

    def test_immutable_output(self):
        with tempfile.TemporaryDirectory() as d:
            report={'status':'SYNTHETIC_TEST_ONLY','x':1};receipt=freeze_output(report,d)
            self.assertEqual(sha((Path(receipt['directory'])/'report.json').read_bytes()),receipt['report_sha256'])
            with self.assertRaises(FileExistsError):freeze_output(report,d)


class NativeHandoffTests(unittest.TestCase):
    def native(self,root):
        source=b'SYNTHETIC ORIGINAL BYTES FOR TEST ONLY'
        (root/'raw.bin').write_bytes(source)
        m={'schema':'nfl_20261115_source_control_v1','date':'2026-11-15',
            'input_freeze_at':'2026-11-15T04:00:00+00:00',
            'handoff':{'source_control_immutable':True},'runtime':{'source_owner':'NFL_SUNDAY_WS1_ONLY'},
            'sources':{'test':{'archive_path':'raw.bin','sha256':sha(source),
                'source_received_at':'2026-11-15T03:00:00+00:00','source_bytes_verified':True,
                'source_publication_truth_verified':False}},
            'attempted_contracts':2,'market_coverage':{'passing yards':2},'failures':{'IDENTITY_UNVERIFIABLE':1},
            'candidates':[{'candidate_id':'a','quote_id':'q1','stat':'passing yards','book':'test',
                'event_start_at':'2026-11-15T18:00:00+00:00','source_certified':True,
                'position':'QB','eligibility_status':'EXPECTED_STARTER_SOURCE_BACKED',
                'frozen_control':{'Consensus_60_40':{'probability':None,'status':'NOT_ORIGINALLY_FROZEN'}}},
                {'candidate_id':'b','quote_id':'q2','stat':'passing yards','book':'test2',
                 'source_validation_failure':'IDENTITY_UNVERIFIABLE','position':'QB',
                 'event_start_at':'2026-11-15T18:00:00+00:00'}]}
        data=canonical(m);path=root/'manifest.json';path.write_bytes(data)
        return path,sha(data)

    def test_native_rows_all_preserved_and_unfrozen_controls_stay_null(self):
        from research.nfl_opportunity_20261115.native_ws1 import consume
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path,pin=self.native(root);before=path.read_bytes()
            r=consume(path,pin,root,NOW)
            self.assertEqual(r['original_contracts_attempted'],2)
            self.assertEqual(r['forecast_count'],0)
            self.assertEqual(len(r['rows']),10)
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(r['source_checks'][0]['status'],'verified_bytes_and_receipt_clock')
            self.assertFalse(r['source_checks'][0]['publication_truth_verified'])
            self.assertTrue(all(x['status']=='abstain' and x['probabilities'] is None for x in r['rows']))
            self.assertTrue(all(x['frozen_controls_original']['Consensus_60_40']['probability'] is None
                                for x in r['rows'] if x['original_row_index']==0))

    def test_native_corrupt_source_not_recertified(self):
        from research.nfl_opportunity_20261115.native_ws1 import consume
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path,pin=self.native(root);(root/'raw.bin').write_bytes(b'TAMPER')
            r=consume(path,pin,root,NOW)
            self.assertEqual(r['source_checks'][0]['status'],'blocked')
            self.assertTrue(all('ORIGINAL_SOURCE_VERIFICATION_BLOCKED' in x['reason_codes'] for x in r['rows']))

    def test_strict_json_rejects_duplicate_keys_and_nonfinite(self):
        from research.nfl_opportunity_20261115.models import strict_json
        for raw in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
            with self.assertRaises(GateError):strict_json(raw)

class AdditionalIntegrityTests(unittest.TestCase):
    def test_direct_constructor_cannot_bypass_future_or_cutoff_gate(self):
        for mutate in (lambda p:p['team_history'][0].update(week=10),
                       lambda p:p['manifest'].update(training_cutoff_at='2026-11-01T00:00:00+00:00')):
            p=fixture();mutate(p)
            with self.assertRaises(GateError):OpportunityModel(p,1024)

    def test_fractional_official_component_and_wrong_game_join_rejected(self):
        for mutate in (lambda p:p['player_history'][3].update(solo=1.5),
                       lambda p:p['player_history'][0].update(week=2),
                       lambda p:p['player_history'][2].update(routes=2)):
            p=fixture();mutate(p)
            with self.assertRaises(GateError):validate(p)

    def test_exact_duplicate_rejected_but_distinct_book_preserved(self):
        p=fixture();c=copy.deepcopy(p['contracts'][0]);c['contract_id']='another-id'
        p['contracts'].append(c)
        with self.assertRaisesRegex(GateError,'duplicate_exact_contract'):validate(p)
        c.update(book='ANOTHER_TEST_BOOK',quote_id='another-book-quote')
        validate(p)

if __name__=='__main__':unittest.main(verbosity=2)
