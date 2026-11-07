"""Keep the NBA power-likelihood family distinct in mixed-source audits."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import date

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'tests'))
import phase4_validation as v
from test_phase4_validation import scenario, parent, mc


def bridge(row,engine):
    return {**parent(row,engine),'sport':'NBA','version':v.NBA_PRIOR_VERSION,
            'source_only_prior_power':.4,'distribution':'normal'}


class BridgeValidationTests(unittest.TestCase):
    def test_reader_accepts_mixed_known_versions_but_preserves_each(self):
        day=date(2026,11,5)
        legacy=scenario(day,player='old')
        nba={**scenario(day,player='bridge'),'sport':'NBA'}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/(day.isoformat()+'.jsonl')
            path.write_text(json.dumps(parent(legacy,'A'))+'\n'+json.dumps(bridge(nba,'A'))+'\n')
            rows=v.read_sidecars(folder,version='history-bayes-v1',engine='A')
        self.assertEqual({r['version'] for r in rows.values()},
                         {'history-bayes-v1',v.NBA_PRIOR_VERSION})

    def test_bridge_wrong_sport_engine_power_or_distribution_is_rejected(self):
        row={**scenario(date(2026,11,5)),'sport':'NBA'}
        for mutation in [{'sport':'NHL'},{'engine':'bayesian_b'},
                         {'source_only_prior_power':1.0},{'distribution':'unknown'}]:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/'2026-11-05.jsonl'
                path.write_text(json.dumps({**bridge(row,'A'),**mutation})+'\n')
                with self.assertRaisesRegex(ValueError,'invalid_phase4_source_sidecar'):
                    v.read_sidecars(folder,version='history-bayes-v1',engine='A')

    def test_bridge_predictions_and_mc_never_enter_legacy_model_labels(self):
        row={**scenario(date(2026,11,5)),'sport':'NBA'}
        a,b=bridge(row,'A'),bridge(row,'B')
        sim=mc(row)
        for child in sim['engines'].values():child['bayesian_parent_version']=v.NBA_PRIOR_VERSION
        models=v._snapshot_models(row,a,b,sim)
        for name in ('bayes_a','bayes_b','bayes_mix70','mc_a','mc_b','mc_mix70'):
            self.assertIsNone(models[name])
        self.assertAlmostEqual(models['nba_prior_a'][0],.70)
        self.assertAlmostEqual(models['nba_prior_b'][0],.67)
        self.assertAlmostEqual(models['nba_prior_mix70'][0],.7*.70+.3*.67)
        self.assertAlmostEqual(models['mc_prior_a'][0],.71)
        self.assertAlmostEqual(models['mc_prior_mix70'][0],.7*.71+.3*.68)
        sim['engines']['A']['analytic_q_win']=.99
        self.assertIsNone(v._snapshot_models(row,a,b,sim)['mc_prior_a'])

    def test_full_chronological_audit_scores_bridge_under_explicit_labels(self):
        rows=[{**scenario(date(2026,11,d),player=str(d)),'sport':'NBA'} for d in (5,6)]
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);original=root/'original.jsonl'
            original.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            for label,engine in [('a','A'),('b','B')]:
                (root/label).mkdir()
                for row in rows:
                    (root/label/(row['game_date']+'.jsonl')).write_text(json.dumps(bridge(row,engine))+'\n')
            report=v.validate(original,a_dir=root/'a',b_dir=root/'b',mc_dir=root/'none')
        self.assertEqual(report['holdout_models']['nba_prior_a']['n'],1)
        self.assertEqual(report['holdout_models']['bayes_a']['n'],0)
        self.assertEqual(report['model_versions']['nba_prior_a'],v.NBA_PRIOR_VERSION)
        self.assertEqual(report['coverage']['nba_prior_a_covered'],2)
        self.assertFalse(report['calibrated_for_production'])


if __name__=='__main__':unittest.main()
