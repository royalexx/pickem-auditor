import pathlib,sys,unittest
import numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from v25_post2025_audit import binary_baseline,confidence,cluster_interval,tail,global_optimum
from v25_nfl_2024_all_volume_rolling_calibration import fit_from_past

class Post2025AuditTests(unittest.TestCase):
    def test_binary_baseline_cannot_claim_original_count_distribution(self):
        r={'y':1,'mean':9,'bias':1,'crps':2,'coverage80':True,'mae':1}
        x=binary_baseline(r,.7)
        self.assertAlmostEqual(x['brier'],.09)
        for field in ['mean','bias','crps','coverage80','mae']:self.assertIsNone(x[field])

    def test_confidence_compares_average_claim_not_cutoff(self):
        rows=[{'week':1,'game_id':'g','player_id':str(i),'market':'targets','line':1.5,
               'q':.85,'y':int(i<8),'hit':int(i<8)} for i in range(10)]
        r=confidence(rows)
        self.assertAlmostEqual(r['claimed'],.85);self.assertAlmostEqual(r['hit'],.8)
        self.assertAlmostEqual(r['gap_week']['mean'],-.05)

    def test_cluster_interval_collapses_repeated_same_game(self):
        rows=[{'game_id':'a'}]*9+[{'game_id':'b'}]
        r=cluster_interval(rows,[.2]*10)
        self.assertEqual(r['clusters'],2)
        np.testing.assert_allclose(r['descriptive_95'],[.2,.2])

    def test_zero_and_poisson_survival_at_half_line(self):
        self.assertEqual(tail({'mean':0.,'variance':0.},np.array([.5]))[0],0.)
        self.assertAlmostEqual(tail({'mean':2.,'variance':2.},np.array([.5]))[0],1-np.exp(-2))

    def test_nb_parameterization_matches_zero_probability(self):
        # mu=2, variance=4 => k=2, p=.5, P(X=0)=.25.
        self.assertAlmostEqual(tail({'mean':2.,'variance':4.},np.array([.5]))[0],.75)

    def test_global_objective_independent_optimizer_agrees(self):
        h=[{'p':.2 if i%2 else .8,'y':int(i%3==0),'role':'WR','week':1} for i in range(120)]
        fit=fit_from_past(h);r=global_optimum(h,fit)
        self.assertLess(r['objective_improvement'],1e-6)

if __name__=='__main__':unittest.main()
