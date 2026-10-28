"""Phase 2 Bayesian Engine B: mathematics, source gating, persistence."""
import hashlib
import json
import math
import sys
import tempfile
import unittest
from datetime import date,datetime,timezone
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import bayesian_engine as be
import bayesian_usage as bu
import bayesian_b_shadow as shadow


def observations(player,*,n=18,work=20,count=False,negative=False):
    result=[]
    for j in range(n):
        w=work*(.85+.05*(j%6))
        y=(j%5+1) if count else (.72*w+(j%5-2)*1.4)
        if negative and j==0:y=-3.0
        result.append((f'{player}-{j}',float(y),float(w)))
    return result


def peers(count=False,negative=False):
    return [observations(f'peer-{i}',work=17+i,n=16,count=count,negative=negative) for i in range(8)]


class ModelTests(unittest.TestCase):
    def test_poisson_three_way_and_no_market_input(self):
        p=observations('subject',count=True)
        others=peers(count=True)
        a=bu.forecast(p,others,dist='poisson',line=3,side='over',sport='NHL',stat='shots on goal')
        b=bu.forecast(p,others,dist='poisson',line=3,side='under',sport='NHL',stat='shots on goal')
        self.assertAlmostEqual(a['q_win']+b['q_win']+a['q_push'],1,places=10)
        self.assertGreater(a['q_push'],0)
        self.assertEqual(a['q_push'],b['q_push'])
        self.assertEqual(a['conversion']['kind'],'gamma_poisson_exact')
        self.assertEqual(a['version'],'usage-bayes-v1')
        self.assertFalse(a['publication_eligible'])

    def test_half_line_has_no_push(self):
        r=bu.forecast(observations('x',count=True),peers(count=True),dist='poisson',
                      line=2.5,side='over',sport='NHL',stat='shots on goal')
        self.assertEqual(r['q_push'],0)
        self.assertAlmostEqual(r['q_win']+r['q_loss'],1,places=11)

    def test_true_nb_likelihood_and_partition(self):
        ps=peers(count=True)
        obs=observations('x',count=True)
        a=bu.forecast(obs,ps,dist='negbin',var_ratio=1.7,line=3,side='over',
                      sport='NHL',stat='shots on goal')
        b=bu.forecast(obs,ps,dist='negbin',var_ratio=1.7,line=3,side='under',
                      sport='NHL',stat='shots on goal')
        self.assertEqual(a['conversion']['kind'],'negbin_lograte_quadrature')
        self.assertAlmostEqual(a['q_win']+a['q_push']+b['q_win'],1,places=8)
        self.assertGreater(a['q_push'],0)
        self.assertTrue(0<a['conversion_mean']<2)

    def test_normal_conversion_uncertainty_and_push(self):
        ps=peers()
        obs=observations('player')
        a=bu.forecast(obs,ps,dist='normal',line=14,side='over',stat='points',sport='NBA')
        b=bu.forecast(obs,ps,dist='normal',line=14,side='under',stat='points',sport='NBA')
        self.assertAlmostEqual(a['q_win']+a['q_push']+b['q_win'],1,places=8)
        self.assertGreater(a['q_push'],0)
        c=bu.forecast(obs,ps,dist='normal',line=14.5,side='under',stat='points',sport='NBA')
        self.assertEqual(c['q_push'],0)
        self.assertGreater(a['workload_sd'],0)
        self.assertGreater(a['conversion_se'],0)

    def test_high_precision_more_history(self):
        ps=peers(count=True)
        short=bu.forecast(observations('x',n=6,count=True),ps,dist='poisson',
                          line=2.5,side='over',stat='shots on goal',sport='NHL')
        long=bu.forecast(observations('x',n=30,count=True),ps,dist='poisson',
                         line=2.5,side='over',stat='shots on goal',sport='NHL')
        self.assertLess(long['conversion_se'],short['conversion_se'])
        self.assertLess(long['workload']['posterior']['posterior_mean_se'],
                        short['workload']['posterior']['posterior_mean_se'])

    def test_signed_nfl_yards_but_not_negative_counts(self):
        ps=peers(negative=True)
        obs=observations('x',negative=True)
        pred=bu.forecast(obs,ps,dist='normal',line=12.5,side='under',
                          stat='receiving yards',sport='NFL')
        self.assertTrue(0<=pred['q_win']<=1)
        with self.assertRaisesRegex(be.ModelUnavailable,'count_stat_requires_integer_results'):
            bu.forecast(obs,ps,dist='poisson',line=12.5,side='under',
                        stat='shots on goal',sport='NHL')

    def test_no_peers_or_invalid_nb_ratio(self):
        with self.assertRaisesRegex(be.ModelUnavailable,'insufficient_usage_peer'):
            bu.forecast(observations('x',count=True),peers(count=True)[:4],
                         dist='poisson',line=2.5,side='over',stat='shots on goal',sport='NHL')
        with self.assertRaisesRegex(be.ModelUnavailable,'invalid_negbin_variance_ratio'):
            bu.forecast(observations('x',count=True),peers(count=True),
                         dist='negbin',var_ratio=1.04,line=2.5,side='over',
                         stat='shots on goal',sport='NHL')

    def test_source_date_duplicate_and_zero_workload(self):
        rec={'observations':[{'id':str(i),'date':f'2026-10-{10+i:02d}',
             'value':2,'workload':20} for i in range(8)]}
        self.assertEqual(len(bu.verified_pairs(rec,before=date(2026,10,28),
                        stat='shots on goal',sport='NHL')),8)
        with self.assertRaisesRegex(be.ModelUnavailable,'future_usage'):
            bu.verified_pairs(rec,before=date(2026,10,12),stat='shots on goal',sport='NHL')
        rec['observations'][1]['id']=rec['observations'][0]['id']
        with self.assertRaisesRegex(be.ModelUnavailable,'duplicate_usage'):
            bu.verified_pairs(rec,before=date(2026,10,28),stat='shots on goal',sport='NHL')
        rec['observations'][1]['id']='unique'
        rec['observations'][1]['workload']=0
        with self.assertRaisesRegex(be.ModelUnavailable,'production_without_workload'):
            bu.verified_pairs(rec,before=date(2026,10,28),stat='shots on goal',sport='NHL')

    def test_exact_time_cutoff_and_invalid_digest(self):
        bu._peer_index.cache_clear()
        with tempfile.TemporaryDirectory() as root:
            files=Path(root)/'usage'/'snapshots'
            files.mkdir(parents=True)
            for i in range(7):
                obj={'version':'usage-history-v2','sport':'NHL','stat':'shots on goal',
                     'player_id':str(i),'team':'BOS',
                     'retrieved_at':'2026-10-28T17:00:00Z' if i==6 else '2026-10-28T14:00:00Z',
                     'observations':[{'id':f'{i}-{j}','date':f'2026-10-{10+j:02d}',
                                      'value':int(j%4+1),'workload':float(j+19)}
                                      for j in range(6)]}
                encoding=json.dumps(obj,sort_keys=True,allow_nan=False)
                name=hashlib.sha256(encoding.encode()).hexdigest()+'.json'
                (files/name).write_text(encoding)
            now=datetime(2026,10,28,15,tzinfo=timezone.utc)
            first=bu.peers_from_cache(root,sport='NHL',stat='shots on goal',
                        player_id='0',forecast_at=now,source_date=date(2026,10,28))
            self.assertEqual(len(first),5)
            second=bu.peers_from_cache(root,sport='NHL',stat='shots on goal',
                        player_id='0',forecast_at=datetime(2026,10,28,18,tzinfo=timezone.utc),
                        source_date=date(2026,10,28))
            self.assertEqual(len(second),6)
            damaged=next(path for path in files.glob('*.json')
                         if json.loads(path.read_text())['player_id']=='1')
            damaged.write_text(damaged.read_text().replace('"workload": 19.0','"workload": 999.0'))
            bu._peer_index.cache_clear()
            third=bu.peers_from_cache(root,sport='NHL',stat='shots on goal',
                        player_id='9',forecast_at=now,source_date=date(2026,10,28))
            self.assertEqual(len(third),5)
        bu._peer_index.cache_clear()


class ShadowTests(unittest.TestCase):
    def setUp(self):
        self.row={'forecast_at':'2026-10-28T19:00:00Z','event_start':'2026-10-28T23:00:00Z',
            'game_date':'2026-10-28','run_type':'shadow','sport':'NHL','player':'Example',
            'player_id':'88','team':'BOS','stat':'shots on goal','side':'over',
            'reference_line':2.5,'run_id':'shadow-1',
            'inputs':{'dist':'poisson','scouting':{'historical_usage':'opaque'}},
            'engine_b':{'version':'scouting-v7','reliable':True,
                         'baseline_origin':'collector_observations','q_win':.52,'q_push':0.,
                         'terms':{'distribution':{'dist':'poisson','var_ratio':None}}},
            'engine_a':{'version':'history-v5'}}

    def test_good_shadow_stays_unpublished(self):
        source={'content_sha256':'source-digest'}
        vals=observations('player',count=True)
        peers_data=peers(count=True)
        with patch.object(shadow.ub,'verify_a',return_value=True),\
             patch.object(shadow.ub,'load',return_value=source),\
             patch.object(shadow.bu,'verified_pairs',return_value=vals),\
             patch.object(shadow.bu,'peers_from_cache',return_value=peers_data):
            ans=shadow.evaluate(self.row,root=Path('/tmp/faux-collector'))
        self.assertEqual(ans['status'],'forecast')
        self.assertEqual(ans['baseline_q_win'],.52)
        self.assertTrue(ans['baseline_reliable'])
        self.assertFalse(ans['publication_eligible'])
        self.assertAlmostEqual(ans['q_win']+ans['q_push']+ans['q_loss'],1,places=8)
        self.assertTrue(ans['inputs_hash'])

    def test_use_engine_b_distribution_even_if_a_differs(self):
        # A may use Normal while B's source-only count distribution is NB.
        row={**self.row,'stat':'saves','reference_line':3.5,
             'inputs':{**self.row['inputs'],'dist':'normal','var_ratio':None},
             'engine_b':{**self.row['engine_b'],
                         'terms':{'distribution':{'dist':'negbin','var_ratio':1.8}}}}
        with patch.object(shadow.ub,'verify_a',return_value=True),\
             patch.object(shadow.ub,'load',return_value={'content_sha256':'source'}),\
             patch.object(shadow.bu,'verified_pairs',return_value=observations('x',count=True)),\
             patch.object(shadow.bu,'peers_from_cache',return_value=peers(count=True)):
            result=shadow.evaluate(row,root=Path('/tmp/faux-collector'))
        self.assertEqual(result['status'],'forecast')
        self.assertEqual(result['distribution'],'negbin')
        self.assertEqual(result['distribution_source'],'scouting_v7_collector')

    def test_no_fabricated_b_distribution(self):
        row={**self.row,'engine_b':{**self.row['engine_b'],'terms':{}}}
        with patch.object(shadow.ub,'verify_a',return_value=True),\
             patch.object(shadow.ub,'load',return_value={'content_sha256':'source'}),\
             patch.object(shadow.bu,'verified_pairs',return_value=observations('x',count=True)),\
             patch.object(shadow.bu,'peers_from_cache',return_value=peers(count=True)):
            result=shadow.evaluate(row,root=Path('/tmp/faux-collector'))
        self.assertEqual(result['status'],'unavailable')
        self.assertEqual(result['reason'],'missing_collector_engine_b_distribution')

    def test_poststart_and_missing_data_abstain(self):
        row=dict(self.row,event_start='2026-10-28T18:00:00Z')
        got=shadow.evaluate(row,root=Path('/nonexistent'))
        self.assertEqual(got['status'],'unavailable')
        self.assertEqual(got['reason'],'poststart_or_date_mismatched_snapshot')
        self.assertFalse(got['publication_eligible'])
        other=dict(self.row)
        other['inputs']={'dist':'poisson','scouting':{}}
        self.assertEqual(shadow.evaluate(other,root=Path('/nonexistent'))['status'],'unavailable')

    def test_reject_checksum_conflict(self):
        with patch.object(shadow.ub,'verify_a',return_value=True),\
             patch.object(shadow.ub,'load',return_value={'content_sha256':'first'}):
            other=dict(self.row)
            other['engine_b']={**self.row['engine_b'],'terms':{'history_digest':'different'}}
            result=shadow.evaluate(other,root=Path('/tmp/cache'))
        self.assertEqual(result['reason'],'engine_b_source_digest_mismatch')

    def test_sidecar_immutable_and_original_forecasts_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            src=root/'snapshots.jsonl'
            src.write_text(json.dumps(self.row)+'\n')
            before=src.read_bytes()
            out=root/'shadow.jsonl'
            receipt=root/'receipt.json'
            first=shadow.run(date='2026-10-28',snapshots=src,data_root=root,output=out,receipt=receipt)
            self.assertEqual(first['new_rows'],1)
            self.assertEqual(first['unavailable_count'],1)
            second=shadow.run(date='2026-10-28',snapshots=src,data_root=root,output=out,receipt=receipt)
            self.assertEqual(second['new_rows'],0)
            self.assertEqual(src.read_bytes(),before)
            self.assertTrue(out.read_text().startswith('{"'))
            out.write_text('{}\n')
            with self.assertRaisesRegex(ValueError,'INVALID_BAYESIAN_B_SHADOW_SIDECAR'):
                shadow.run(date='2026-10-28',snapshots=src,data_root=root,output=out,receipt=receipt)


if __name__=='__main__':
    unittest.main()
