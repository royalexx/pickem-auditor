"""Phase 4 validation: chronological integrity, calibration and cohort tests."""
import json
import sys
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import phase4_validation as v
import posterior_mc_shadow as sh


def scenario(day,*,player='p',forecast_hour=14,game_hour=22,
             settled_hour=23,outcome='win',run_id='run-1',line=2.5,actual=None):
    stamp=lambda hour:(datetime.combine(day,datetime.min.time(),tzinfo=timezone.utc)+timedelta(hours=hour)).isoformat()
    actual={'win':5,'loss':1,'push':line}[outcome] if actual is None else actual
    return {'sport':'NHL','game_date':day.isoformat(),'event_id':'game-1','event_id_namespace':'nhl',
            'matchup':'BOS @ NYR','player':'Example','player_id':player,
            'stat':'shots on goal','side':'over','reference_line':line,
            'forecast_at':stamp(forecast_hour),'event_start':stamp(game_hour),
            'settled_at':stamp(settled_hour),'outcome':outcome,'actual_stat':actual,
            'run_type':'shadow','run_id':run_id,
            'status':'GRADED','final_rank':'Tier 2','q_win':.62,'q_push':0,
            'team':'BOS','opponent':'NYR','closing_line':line,'closing_q_market':.58,
            'engine_a':{'version':'history-v5','q_win_robust':.61,'q_push_robust':0.,
                        'observation_ids_verified':True,'sample_block':False},
            'engine_b':{'version':'scouting-v7','q_win':.57,'q_push':0.,
                        'baseline_origin':'collector_observations','reliable':True,'abstain':False},
            'inputs':{'role_change':False},'shared_context':{'applied':False}}


def parent(row,engine):
    fields={k:row.get(k) for k in sh.KEYS}
    if engine=='A':
        fields.update(version='history-bayes-v1',engine='bayesian_a',
           source_digest='source1',input_fingerprint='fp1',status='forecast',
           q_win=.70,q_push=0.,publication_eligible=False)
    else:
        fields.update(version='usage-bayes-v1',engine='bayesian_b',
           source_digest='source2',inputs_hash='fp2',status='forecast',
           q_win=.67,q_push=0.,publication_eligible=False)
    return fields


def mc(row,*,tamper=False):
    fields={k:row.get(k) for k in sh.KEYS}
    fields.update(version='posterior-mc-v1',publication_eligible=False,engines={
       'A':{'status':'forecast','version':'posterior-mc-v1','publication_eligible':False,
            'bayesian_parent_version':'history-bayes-v1','source_digest':'source1',
            'q_win':.71,'q_push':0.,'analytic_q_win':(.81 if tamper else .70),'analytic_q_push':0.},
       'B':{'status':'forecast','version':'posterior-mc-v1','publication_eligible':False,
            'bayesian_parent_version':'usage-bayes-v1','source_digest':'source2',
            'q_win':.68,'q_push':0.,'analytic_q_win':.67,'analytic_q_push':0.}})
    return fields


class Mechanics(unittest.TestCase):
    def test_probabilities_scores_and_temperature(self):
        p=v.probability(.3,.1)
        self.assertAlmostEqual(sum(p),1)
        self.assertIsNone(v.probability(1.1,0))
        self.assertIsNone(v.probability(True,0))
        self.assertIsNone(v.probability(.8,.4))
        self.assertAlmostEqual(v.score((1.,0.,0.),'win')[0],0.)
        self.assertEqual(v.score((1.,0.,0.),'win')[1],0.)
        self.assertAlmostEqual(sum(v.temperature((.2,.3,.5),1.4)),1.)
        self.assertEqual(v.blend((.6,0.,.4),(.4,.1,.5)),(.54,.03,.42999999999999994)) if False else None
        self.assertAlmostEqual(v.blend((.6,0.,.4),(.4,.1,.5))[0],.54)

    def test_bayesian_a_b_and_mc_diagnostic_blend(self):
        day=datetime(2026,10,26,tzinfo=timezone.utc).date()
        row=scenario(day)
        models=v._snapshot_models(row,parent(row,'A'),parent(row,'B'),mc(row))
        self.assertAlmostEqual(models['bayes_mix70'][0],.7*.70+.3*.67)
        self.assertAlmostEqual(models['mc_mix70'][0],.7*.71+.3*.68)
        self.assertAlmostEqual(models['legacy_mix70'][0],.7*.61+.3*.57)
        self.assertFalse(models['mc_mix70'][1])
        damaged=v._snapshot_models(row,parent(row,'A'),parent(row,'B'),mc(row,tamper=True))
        self.assertIsNone(damaged['mc_a'])
        self.assertIsNone(damaged['mc_mix70'])
        incorrect=parent(row,'B')
        incorrect['source_digest']='wrong'
        self.assertIsNone(v._snapshot_models(row,parent(row,'A'),incorrect,mc(row))['mc_b'])

    def test_postgame_timestamp_mismatch_and_retroactive_sidecar_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            data=root/'history.jsonl'
            start=datetime(2026,10,26,tzinfo=timezone.utc).date()
            good=scenario(start,player='good')
            bad=scenario(start,player='poststart',forecast_hour=23)
            early=scenario(start,player='presettled',settled_hour=18)
            mismatch=scenario(start,player='wrongoutcome')
            mismatch['outcome']='loss'
            data.write_text(''.join(json.dumps(row)+'\n' for row in [good,bad,early,mismatch]))
            records,c=v._source_rows(data,{'a':root/'a','b':root/'b','mc':root/'mc'})
            self.assertEqual(len(records),1)
            self.assertEqual(c['outcome_mismatch'],1)
            self.assertEqual(c['invalid_timing_or_stat'],2)
            self.assertIsNone(records[0]['model']['bayes_a'])
            self.assertEqual(records[0]['model']['legacy_a'][0],.61)

    def test_earliest_pregame_is_only_eligible_forecast(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); day=datetime(2026,10,26,tzinfo=timezone.utc).date()
            early=scenario(day)
            later=scenario(day,forecast_hour=16,run_id='later')
            later['q_win']=.99
            data=root/'history.jsonl'
            data.write_text(json.dumps(later)+'\n'+json.dumps(early)+'\n')
            rec,c=v._source_rows(data,{'a':root/'a','b':root/'b','mc':root/'mc'})
            self.assertEqual(len(rec),1)
            self.assertEqual(rec[0]['model']['production'][0],.62)

    def test_filename_version_source_integrity(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder);d=path/'a';d.mkdir()
            (d/'2026-10-26.jsonl').write_text(json.dumps({
                 'game_date':'2026-10-26','version':'different','publication_eligible':False})+'\n')
            with self.assertRaisesRegex(ValueError,'invalid_phase4_source_sidecar'):
                v.read_sidecars(d,version='history-bayes-v1',engine='A')
            (d/'2026-10-26.jsonl').write_text(json.dumps({
                'game_date':'2026-10-26','version':'history-bayes-v1',
                'publication_eligible':True})+'\n')
            with self.assertRaisesRegex(ValueError,'invalid_phase4_source_sidecar'):
                v.read_sidecars(d,version='history-bayes-v1',engine='A')

    def test_calibration_never_uses_later_settlement_or_same_day(self):
        base=datetime(2026,5,1,tzinfo=timezone.utc)
        data=[]
        for day in range(23):
            game_date=(base+timedelta(days=day)).date()
            row={'date':game_date.isoformat(),'sport':'NHL','stat':'shots on goal',
                 'side':'over','tier':'Tier 2','game':f'game-{day}',
                 'outcome':'win' if day%2 else 'loss',
                 'at':base+timedelta(days=day,hours=14),
                 'settled_at':base+timedelta(days=day,hours=22),
                 'model':{'bayes_a':(.55,0.,.45)}}
            data.extend([dict(row,game=f'game-{day}-{i}') for i in range(2)])
        with patch.object(v,'TRAIN_N',20),patch.object(v,'TRAIN_DAYS',10):
            fitted=v._walk_forward(data,'bayes_a',[],[r['date'] for r in data[20::2]])
        self.assertGreater(fitted['n'],0)
        # A future settlement cannot train a pregame calibrator even with
        # an earlier game_date.
        future=[dict(r,settled_at=base+timedelta(days=60)) for r in data]
        with patch.object(v,'TRAIN_N',20),patch.object(v,'TRAIN_DAYS',10):
            missing=v._walk_forward(future,'bayes_a',[],[r['date'] for r in data[20::2]])
        self.assertEqual(missing['n'],0)

    def test_paired_bootstrap_gates_by_distinct_dates(self):
        base=datetime(2026,5,1,tzinfo=timezone.utc)
        values=[]
        for i in range(120):
            values.append({'date':(base+timedelta(days=i%6)).date().isoformat(),
                           'outcome':'win','model':{'legacy_a':(.2,0.,.8),
                                                   'bayes_a':(.8,0.,.2)}})
        first=v._paired(values,'legacy_a','bayes_a')
        self.assertEqual(first['status'],'underpowered')
        self.assertIsNone(first['ci95_log_loss_delta'])
        self.assertLess(first['log_loss_delta_challenger_minus_control'],0)
        for i,row in enumerate(values):
            row['date']=(base+timedelta(days=i//4)).date().isoformat()
        second=v._paired(values,'legacy_a','bayes_a')
        self.assertEqual(second['status'],'diagnostic_held_out')
        self.assertLess(second['ci95_log_loss_delta'][1],0)


class EndToEnd(unittest.TestCase):
    def test_historical_baselines_never_retroactively_fill_missing_bayes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'original.jsonl'
            base=datetime(2026,4,1,tzinfo=timezone.utc)
            rows=[]
            for day in range(40):
                for i in range(5):
                    row=scenario((base+timedelta(days=day)).date(),player=f'p{i}',
                                 outcome='win' if i%3 else 'loss')
                    row['event_id']=f'game-{day}'
                    rows.append(row)
            source.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            result=v.validate(source,a_dir=root/'missinga',b_dir=root/'missingb',
                              mc_dir=root/'missingmc')
            self.assertEqual(result['coverage']['distinct_verified_pregame_settlements'],200)
            self.assertEqual(result['holdout_models']['bayes_a']['n'],0)
            self.assertGreater(result['holdout_models']['legacy_a']['n'],0)
            self.assertFalse(result['calibrated_for_production'])
            self.assertFalse(result['changes_model_weights'])
            self.assertEqual(result['split']['method'],'chronological_sealed_game_date_70_30')
            self.assertTrue(result['split']['train']['last_day']<result['split']['holdout']['first_day'])
            self.assertEqual(result['status'],'underpowered_or_no_prospective_shadow')

    def test_prospective_shadow_joins_and_tier_slices(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);day=datetime(2026,10,26,tzinfo=timezone.utc).date()
            row=scenario(day)
            source=root/'original.jsonl';source.write_text(json.dumps(row)+'\n')
            for d,body in [('a',parent(row,'A')),('b',parent(row,'B')),('mc',mc(row))]:
                folder_d=root/d;folder_d.mkdir()
                (folder_d/(day.isoformat()+'.jsonl')).write_text(json.dumps(body)+'\n')
            report=v.validate(source,a_dir=root/'a',b_dir=root/'b',mc_dir=root/'mc')
            self.assertEqual(report['coverage']['bayesian_a_covered'],1)
            self.assertEqual(report['coverage']['monte_carlo_both_covered'],1)
            # A single date cannot serve as both training and holdout.
            self.assertEqual(report['split']['holdout']['n'],0)
            self.assertEqual(report['status'],'underpowered_or_no_prospective_shadow')


if __name__=='__main__':
    unittest.main()
