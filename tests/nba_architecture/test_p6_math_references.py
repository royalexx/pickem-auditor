"""Independent mathematical reference oracles for C-family P5/P6.

The tests prove reference calculations, not that an as-yet-unaccepted C adapter
implements them. No historical games, real props or optimized weights are used.
"""
import itertools
import math
import random
import unittest


def discrete_crps_cdf(pmf, observation):
    upper=max(max(pmf),observation)
    cdf=0.0
    score=0.0
    for k in range(upper+1):
        cdf+=pmf.get(k,0.0)
        score+=(cdf - (1.0 if observation<=k else 0.0))**2
    return score


def discrete_crps_energy(pmf, observation):
    mean_abs=sum(p*abs(k-observation) for k,p in pmf.items())
    pair=sum(p*q*abs(k-j) for k,p in pmf.items() for j,q in pmf.items())
    return mean_abs-0.5*pair


def poisson(lam, max_k=75):
    pmf={0:math.exp(-lam)}
    for k in range(1,max_k+1):
        pmf[k]=pmf[k-1]*lam/k
    return pmf


def nb_integer_r(r,p,max_k=150):
    assert isinstance(r,int) and r>=1 and 0<p<1
    pmf={0:p**r}
    for k in range(1,max_k+1):
        pmf[k]=pmf[k-1]*(k+r-1)/k*(1-p)
    return pmf


def moments(pmf, y):
    mean=sum(k*v for k,v in pmf.items())
    mae=sum(v*abs(k-y) for k,v in pmf.items())
    mse=sum(v*(k-y)**2 for k,v in pmf.items())
    return mean,mae,math.sqrt(mse),mean-y


def energy_score(joint,y):
    def distance(a,b):
        return math.sqrt(sum((i-j)**2 for i,j in zip(a,b)))
    first=sum(w*distance(x,y) for x,w in joint)
    second=sum(p*q*distance(x,z) for x,p in joint for z,q in joint)
    return first-.5*second


def variogram_05(joint,y):
    expectation=sum(w*math.sqrt(abs(x[0]-x[1])) for x,w in joint)
    return (math.sqrt(abs(y[0]-y[1]))-expectation)**2


class NumericalReferences(unittest.TestCase):
    def test_poisson_exact_nlpd_mae_rmse_bias(self):
        p=poisson(1.0)
        self.assertLess(abs(sum(p.values())-1),1e-13)
        self.assertAlmostEqual(-math.log(p[0]),1.0,places=13)
        m,mae,rmse,bias=moments(p,0)
        self.assertAlmostEqual(m,1.0,places=12)
        self.assertAlmostEqual(mae,1.0,places=12)
        self.assertAlmostEqual(rmse,math.sqrt(2),places=12)
        self.assertAlmostEqual(bias,1.0,places=12)

    def test_poisson_crps_against_independent_bessel_series(self):
        pmf=poisson(1.0)
        i0=sum(1/(math.factorial(k)**2) for k in range(18))
        i1=sum(1/(math.factorial(k)*math.factorial(k+1)) for k in range(18))
        reference=1-math.exp(-2)*(i0+i1)
        self.assertAlmostEqual(discrete_crps_cdf(pmf,0),reference,places=11)
        self.assertAlmostEqual(discrete_crps_energy(pmf,0),reference,places=11)

    def test_negative_binomial_parameters_and_moments(self):
        r,p=2,0.5
        pmf=nb_integer_r(r,p)
        self.assertAlmostEqual(-math.log(pmf[0]),math.log(4),places=12)
        m,mae,rmse,bias=moments(pmf,0)
        self.assertAlmostEqual(m,r*(1-p)/p,places=11)
        self.assertAlmostEqual(mae,2,places=11)
        self.assertAlmostEqual(rmse,math.sqrt(8),places=11)
        self.assertAlmostEqual(bias,2,places=11)

    def test_negative_binomial_crps_cdf_and_pairwise_independent(self):
        pmf=nb_integer_r(2,.5)
        self.assertAlmostEqual(discrete_crps_cdf(pmf,3),
                               discrete_crps_energy(pmf,3),places=11)

    def test_randomized_pit_for_discrete_mass(self):
        law={0:.25,2:.75}
        u=.37
        y=2
        less=sum(v for k,v in law.items() if k<y)
        pit=less+u*law[y]
        self.assertAlmostEqual(pit,.5275,places=13)
        self.assertGreaterEqual(pit,less)
        self.assertLessEqual(pit,less+law[y])

    def test_known_quantiles_zeros_and_tail(self):
        law={0:.25,2:.75}
        def q(alpha):
            a=0
            for k in sorted(law):
                a+=law[k]
                if alpha<=a: return k
            raise AssertionError("unnormalized")
        self.assertEqual(q(.10),0)
        self.assertEqual(q(.90),2)
        self.assertEqual(law[0],.25)
        self.assertEqual(sum(p for k,p in law.items() if k>1),.75)
        self.assertEqual(sum(p for k,p in law.items() if k>2),0)

    def test_energy_known_two_state_correlated_game(self):
        law=[((0,0),.5),((2,2),.5)]
        observation=(0,2)
        self.assertAlmostEqual(energy_score(law,observation),
                               2-math.sqrt(2)/2,places=13)

    def test_variogram_known_two_state(self):
        law=[((0,0),.5),((2,2),.5)]
        self.assertAlmostEqual(variogram_05(law,(0,2)),2.0,places=13)

    def test_same_marginals_can_have_different_joint_energy(self):
        correlated=[((0,0),.5),((2,2),.5)]
        independent=[((0,0),.25),((0,2),.25),((2,0),.25),((2,2),.25)]
        self.assertNotAlmostEqual(energy_score(correlated,(0,2)),
                                  energy_score(independent,(0,2)),places=9)

    def test_cluster_count_not_monte_carlo_draw_count(self):
        records=[{"game_id":"g1","date":"2026-11-16","draw":j} for j in range(5000)]
        records += [{"game_id":"g2","date":"2026-11-17","draw":j} for j in range(5000)]
        self.assertEqual(len(records),10000)
        self.assertEqual(len({r["game_id"] for r in records}),2)
        self.assertEqual(len({r["date"] for r in records}),2)
        # This is an oracle on experimental units, not validation of C implementation.

    def test_5000_vs_20000_binomial_precision_reference(self):
        p=.37
        se5=math.sqrt(p*(1-p)/5000)
        se20=math.sqrt(p*(1-p)/20000)
        self.assertAlmostEqual(se5/se20,2.0,places=13)


if __name__=="__main__":
    unittest.main()
