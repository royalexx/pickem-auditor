"""Phase 1 shadow Engine A safeguards and posterior-predictive mathematics."""
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import bayesian_engine as be
import bayesian_shadow as bs


class PosteriorTests(unittest.TestCase):
    def setUp(self):
        self.peers=[[float((i%4)+j%3+1) for j in range(15)] for i in range(10)]

    def test_exact_gamma_poisson_zero_line(self):
        result=be.forecast([2.,3.,1.,4.,2.],self.peers,dist='poisson',line=0,side='over')
        a,b=result['posterior_parameters']['alpha'],result['posterior_parameters']['beta']
        self.assertAlmostEqual(result['q_push'], (b/(b+1))**a,places=10)
        self.assertAlmostEqual(result['q_win']+result['q_push']+result['q_loss'],1,places=12)

    def test_over_under_and_push_partition(self):
        sample=[0.,1.,2.,4.,2.,3.,2.,1.]
        for dist in ('poisson','negbin','normal'):
            for line in (2,2.5):
                kw={'var_ratio':1.8} if dist=='negbin' else {}
                a=be.forecast(sample,self.peers,dist=dist,line=line,side='over',**kw)
                b=be.forecast(sample,self.peers,dist=dist,line=line,side='under',**kw)
                self.assertAlmostEqual(a['q_win']+b['q_win']+a['q_push'],1,places=8)
                self.assertTrue(0<=a['q_win']<=1)
                self.assertTrue(0<=b['q_win']<=1)
                if dist=='normal' or line!=int(line):self.assertEqual(a['q_push'],0)

    def test_normal_t_heavy_tails_and_sample_precision(self):
        small=be.forecast([7.,11.,8.,13.,9.],self.peers,dist='normal',line=10.5,side='over')
        long=be.forecast([7.,11.,8.,13.,9.]*12,self.peers,dist='normal',line=10.5,side='over')
        self.assertGreater(small['posterior_mean_se'],long['posterior_mean_se'])
        self.assertGreater(small['degrees_freedom'],2)
        self.assertAlmostEqual(be.student_t_cdf(0,6),0.5)
        self.assertAlmostEqual(be.student_t_cdf(-1,6)+be.student_t_cdf(1,6),1.0,places=10)

    def test_partial_pooling_and_other_players_only(self):
        low=be.forecast([12.]*5,self.peers,dist='poisson',line=10.5,side='under')
        high=be.forecast([12.]*50,self.peers,dist='poisson',line=10.5,side='under')
        self.assertLess(low['mean'],high['mean'])
        self.assertGreater(high['mean'],11)
        with self.assertRaisesRegex(be.ModelUnavailable,'insufficient_peer'):
            be.forecast([12.]*5,self.peers[:4],dist='poisson',line=10.5,side='under')

    def test_negative_football_yards_only_normal(self):
        data=[-2.,5.,9.,11.,7.,8.]
        self.assertTrue(be.forecast(data,self.peers,dist='normal',line=6.5,side='over'))
        with self.assertRaisesRegex(be.ModelUnavailable,'noninteger|invalid_subject'):
            be.forecast(data,self.peers,dist='poisson',line=2.5,side='over')

    def test_no_poststart_or_same_day_observations(self):
        record={'observations':[{'id':str(i),'date':'2026-10-%02d'%(10+i),'value':2} for i in range(6)]}
        with self.assertRaisesRegex(be.ModelUnavailable,'future_game'):
            be.validated_values(record,before=date(2026,10,15))
        with self.assertRaisesRegex(be.ModelUnavailable,'duplicate'):
            r={'observations':[{'id':'same','date':'2026-10-10','value':2} for _ in range(6)]}
            be.validated_values(r,before=date(2026,10,20))

    def test_invalid_prior_inputs_never_silently_used(self):
        for bad in (float('nan'),float('inf'),True,None):
            with self.assertRaises((ValueError,TypeError)):
                be.forecast([1.,2.,3.],self.peers,dist='normal',line=bad,side='under')


class SourceSelectionTests(unittest.TestCase):
    def test_time_cutoff_digest_identity_and_dedup(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'usage'/'snapshots').mkdir(parents=True)
            for i in range(7):
                stamp='2026-10-28T12:01:00Z' if i < 6 else '2026-10-28T20:00:00Z'
                obj={'version':'usage-history-v2','sport':'NHL','stat':'shots on goal',
                     'player_id':str(i),'retrieved_at':stamp,
                     'observations':[{'id':f'{i}-{j}','date':'2026-10-%02d'%(10+j),'value':2+j%3}
                                     for j in range(6)]}
                encoded=json.dumps(obj,sort_keys=True,allow_nan=False)
                digest=hashlib.sha256(encoded.encode()).hexdigest()
                (root/'usage'/'snapshots'/(digest+'.json')).write_text(encoded)
            now=datetime(2026,10,28,16,0,tzinfo=timezone.utc)
            result=be.peers_from_cache(root,sport='NHL',stat='shots on goal',
                         player_id='0',cutoff=now,source_date=date(2026,10,28))
            self.assertEqual(len(result),5)
            be._peer_index.cache_clear()
            one=next((root/'usage'/'snapshots').glob('*.json'))
            one.write_text(one.read_text().replace('"value": 2','"value": 999'))
            result=be.peers_from_cache(root,sport='NHL',stat='shots on goal',
                         player_id='99',cutoff=now,source_date=date(2026,10,28))
            self.assertEqual(len(result),5)

    def test_shadow_abstains_when_missing_history_no_retroactive_prediction(self):
        row={'forecast_at':'2026-10-28T14:00:00Z','game_date':'2026-10-28',
             'event_start':'2026-10-28T13:00:00Z','sport':'NHL','player_id':'9',
             'stat':'shots on goal','side':'over','reference_line':2.5,'inputs':{'scouting':{}},
             'engine_a':{'version':'history-v5'}}
        result=bs.evaluate(row,root=Path('/nonexistent'))
        self.assertEqual(result['status'],'unavailable')
        self.assertEqual(result['reason'],'missing_or_poststart_forecast')
        self.assertFalse(result['publication_eligible'])

    def test_sidecar_append_only_and_production_history_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            source=root/'original.jsonl'; before={'game_date':'2026-10-28','run_type':'shadow',
                'sport':'NHL','player':'x','player_id':'p','stat':'shots on goal','side':'over',
                'reference_line':2.5,'forecast_at':'2026-10-28T16:00:00Z'}
            source.write_text(json.dumps(before)+'\n')
            out=root/'sidecar.jsonl';receipt=root/'receipt.json'
            first=bs.run(date='2026-10-28',snapshots=source,data_root=root,output=out,receipt=receipt)
            self.assertEqual(first['unavailable_count'],1)
            second=bs.run(date='2026-10-28',snapshots=source,data_root=root,output=out,receipt=receipt)
            self.assertEqual(second['new_rows'],0)
            self.assertEqual(json.loads(source.read_text()),before)
            out.write_text('{}\n')
            with self.assertRaisesRegex(ValueError,'INVALID_BAYESIAN_SHADOW_SIDECAR'):
                bs.run(date='2026-10-28',snapshots=source,data_root=root,output=out,receipt=receipt)


if __name__=='__main__':
    unittest.main()
