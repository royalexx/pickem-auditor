"""Bridge output must be audit-compatible, never silently reinterpret prior weights."""
import sys
import json
import tempfile
import unittest
from pathlib import Path
from datetime import date,datetime,timezone
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import posterior_mc as mc
import posterior_mc_shadow as runner
import nba_prior_bridge as bridge
import bayesian_engine as base

def record(pid,stat='threes'):
    y=lambda i:float(2+(i%2)) if stat=='threes' else float(21+i%3)
    return {'sport':'NBA','stat':stat,'player_id':pid,
            'observations':[{'id':pid+'-c-'+str(i),'date':f'2026-10-{20+i:02d}',
                             'value':y(i),'workload':31.} for i in range(4)],
            'prior_observations':[{'id':pid+'-p-'+str(i),'date':f'2025-01-{i+1:02d}',
                             'value':y(i),'workload':30.} for i in range(16)]}

class PowerLikelihoodMonteCarloTests(unittest.TestCase):
    def test_early_nba_a_b_posteriors_match_shadow_mc_probability(self):
        for stat,dist,line in [('threes','poisson',2.5),('points','normal',22.5)]:
            subject=record('subject',stat)
            peers=[tuple(bridge.observations(record(str(i),stat),before=date(2026,10,29),stat=stat))
                   for i in range(6)]
            params=dict(root='unused',stat=stat,player_id='subject',
                        cutoff=datetime(2026,10,29,14,tzinfo=timezone.utc),
                        before=date(2026,10,29),dist=dist,line=line,side='under')
            with patch.object(bridge,'peers',return_value=peers):
                a=bridge.model_a(subject,**params)
                b=bridge.model_b(subject,**params)
            a.update(status='forecast',posterior_mean=a['mean'])
            b.update(status='forecast',distribution=dist,workload_posterior=b['workload'],
                     conversion_posterior=b['conversion'])
            for engine,p in [('A',a),('B',b)]:
                s=mc.simulate(p,engine=engine,identity=['NBA',stat,'subject',engine],
                    line=line,side='under',draws=1024,max_draws=2048,target=.015)
                self.assertAlmostEqual(s['q_win']+s['q_push']+s['q_loss'],1.,places=9)
                self.assertFalse(s['publication_eligible'])
                self.assertLess(abs(s['q_win']-p['q_win']),.1)
    def test_new_version_is_indexed_and_negbin_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'a.jsonl'
            path.write_text(json.dumps({'version':mc.NBA_PRIOR_VERSION,'publication_eligible':False,
                'sport':'NBA','player_id':'s','stat':'points','side':'under',
                'reference_line':22.5,'game_date':'2026-10-29','run_id':'z',
                'forecast_at':'2026-10-29T12:00:00Z'})+'\n')
            indexed=runner._indexed(path,mc.SUPPORTED_POSTERIOR_VERSIONS_A)
            self.assertEqual(len(indexed),1)
        with self.assertRaisesRegex(base.ModelUnavailable,'weighted_prior_negbin'):
            mc.sampler_a({'status':'forecast','version':mc.NBA_PRIOR_VERSION,'distribution':'negbin'})
        with self.assertRaisesRegex(base.ModelUnavailable,'weighted_prior_negbin'):
            mc.sampler_b({'status':'forecast','version':mc.NBA_PRIOR_VERSION,'distribution':'negbin'})
if __name__=='__main__':
    unittest.main()
