"""P6 independent post-G0 adversarial controls; QA/reference only.

Target: accepted NBA SOJC 2.0.0 G0 SHA 59d28dc23be97de2a6a82d22be8338151e31f5b6.
These checks DO NOT implement S/O/J/C models or certify real historical features.
Full-game minute totals alone are not a five-on-court timeline certificate.
"""
import copy
import hashlib
import math
import unittest

from golden_v2 import pregame, distribution, j_scenarios
from v2.nba_architecture.v2_contracts import (
    ContractError, seal, verify, validate_pregame, validate_distribution,
    validate_scenarios, threshold_triplet, seed_for,
)


def tamper_and_reseal(record, alter):
    candidate = copy.deepcopy(record)
    candidate.pop("content_hash")
    alter(candidate)
    return seal(candidate)


def independent_pmf_crps(pmf, y):
    """Integer CRPS through CDF sum, NOT through target C scoring code."""
    assert y >= 0 and isinstance(y, int)
    assert all(k >= 0 and isinstance(k, int) for k in pmf)
    upper = max(y, max(pmf))
    cumulative = 0.0
    score = 0.0
    for k in range(upper + 1):
        cumulative += pmf.get(k, 0.0)
        score += (cumulative - (1.0 if k >= y else 0.0)) ** 2
    return score


def independent_pairwise_crps(pmf, y):
    """Alternative E|X-y|-0.5 E|X-X'| identity."""
    first = math.fsum(p * abs(k - y) for k, p in pmf.items())
    half = 0.5 * math.fsum(
        p*q*abs(k-l) for k, p in pmf.items()
        for l, q in pmf.items()
    )
    return first-half


def finite_poisson(lam, tail_at=90):
    return {k: math.exp(-lam + k * math.log(lam) - math.lgamma(k+1))
            for k in range(tail_at+1)}


def finite_nb(r, p, tail_at=180):
    return {k: math.exp(math.lgamma(k+r) - math.lgamma(r)
            - math.lgamma(k+1) + r*math.log(p) + k*math.log1p(-p))
            for k in range(tail_at+1)}


def energy_score(atoms, y):
    """Finite exact ES; atoms: [(tuple, probability)]."""
    distance = lambda x,z: math.sqrt(math.fsum((a-b)**2 for a,b in zip(x,z)))
    return (math.fsum(p*distance(x,y) for x,p in atoms)
            - 0.5*math.fsum(p*q*distance(x,z)
                            for x,p in atoms for z,q in atoms))


def variogram_05(atoms, y):
    """One unordered pair, no normalization: VS_0.5."""
    prediction = math.fsum(p*abs(x[0]-x[1])**0.5 for x,p in atoms)
    observed = abs(y[0]-y[1])**0.5
    return (prediction-observed)**2


def five_on_floor(intervals, duration):
    """Reference sweep: (start, end, player_id); half-open clock intervals."""
    endpoints = sorted({0.0, float(duration)}
                       | {float(a) for a, _, _ in intervals}
                       | {float(b) for _, b, _ in intervals})
    if any(not (0 <= a < b <= duration) for a,b,_ in intervals):
        return False
    for a,b in zip(endpoints, endpoints[1:]):
        midpoint = (a+b)/2
        active = [player for start, end, player in intervals
                  if start <= midpoint < end]
        if len(active) != 5 or len(active) != len(set(active)):
            return False
    return True


class PostG0ActualContractControls(unittest.TestCase):
    def test_prospective_missing_original_feature_clock_fails_closed(self):
        p = pregame("original_prospective")
        bad = tamper_and_reseal(p, lambda x:
            x["features"][0].update(available_at=None))
        with self.assertRaises(ContractError):
            validate_pregame(bad)

    def test_same_feature_label_does_not_excuse_future_availability(self):
        p = pregame("original_prospective")
        bad = tamper_and_reseal(p, lambda x:
            x["features"][0].update(available_at=x["event_start_at"]))
        with self.assertRaises(ContractError):
            validate_pregame(bad)

    def test_unresealed_source_snapshot_tamper_detected(self):
        p = pregame("original_prospective")
        p["sources"][0]["raw_sha256"] = "9"*64
        with self.assertRaises(ContractError):
            verify(p)

    def test_player_wrong_team_distribution_even_after_reseal(self):
        p = pregame()
        d = distribution(p)
        bad = tamper_and_reseal(d, lambda x: x.update(team_id=p["team_ids"][1]))
        with self.assertRaises(ContractError):
            validate_distribution(bad, p)

    def test_invalid_pmf_negative_mass_rejected(self):
        p = pregame()
        d = distribution(p)
        bad = tamper_and_reseal(d, lambda x: x["pmf"][0].update(mass=-.01))
        with self.assertRaises(ContractError):
            validate_distribution(bad, p)

    def test_invalid_pmf_mass_sum_rejected(self):
        p = pregame()
        d = distribution(p)
        bad = tamper_and_reseal(d, lambda x: x["pmf"][1].update(mass=.65))
        with self.assertRaises(ContractError):
            validate_distribution(bad, p)

    def test_scenario_combo_cannot_be_set_independently(self):
        p = pregame("original_prospective")
        s = j_scenarios(p)
        bad = tamper_and_reseal(s, lambda x:
            x["scenarios"][0]["players"][0]["stats"].update(pra=999))
        with self.assertRaises(ContractError):
            validate_scenarios(bad, p)

    def test_scenario_made_threes_can_not_exceed_3pa(self):
        p = pregame("original_prospective")
        s = j_scenarios(p)
        bad = tamper_and_reseal(s, lambda x:
            x["scenarios"][0]["players"][0]["stats"].update(threes=999))
        with self.assertRaises(ContractError):
            validate_scenarios(bad, p)

    def test_seed_changes_when_game_key_changes(self):
        a = seed_for(187, "nba:A", "draw:1", "J3")
        self.assertEqual(a, seed_for(187, "nba:A", "draw:1", "J3"))
        self.assertNotEqual(a, seed_for(187, "nba:B", "draw:1", "J3"))


class IndependentNumericalOracles(unittest.TestCase):
    def test_poisson_nlpd_at_y3_lambda2(self):
        lam, y = 2.0, 3
        manual = lam-y*math.log(lam)+math.lgamma(y+1)
        pmf = finite_poisson(lam)
        self.assertAlmostEqual(-math.log(pmf[y]), manual, places=13)

    def test_poisson_crps_two_independent_identities(self):
        law = finite_poisson(2.0)
        self.assertAlmostEqual(sum(law.values()), 1, places=13)
        for y in (0,1,3,7):
            self.assertAlmostEqual(independent_pmf_crps(law,y),
                                   independent_pairwise_crps(law,y),places=11)

    def test_nb_two_half_zero_rational_oracle(self):
        law = finite_nb(2, .5)
        self.assertAlmostEqual(sum(law.values()),1.,places=13)
        self.assertAlmostEqual(independent_pmf_crps(law,0),26/27,places=12)
        self.assertAlmostEqual(independent_pairwise_crps(law,0),26/27,places=12)
        self.assertAlmostEqual(-math.log(law[0]),math.log(4),places=13)

    def test_nb_three_point_four_two_probability_and_crps(self):
        law = finite_nb(3, .4)
        y=2
        manual = (math.lgamma(y+3)-math.lgamma(3)-math.lgamma(y+1)
                  +3*math.log(.4)+y*math.log(.6))
        self.assertAlmostEqual(math.log(law[y]),manual,places=12)
        self.assertAlmostEqual(independent_pmf_crps(law,y),
                               independent_pairwise_crps(law,y),places=10)

    def test_poisson_point_rmse_not_draw_loss(self):
        mean, variance, actual = 2.,2.,0.
        self.assertEqual(abs(mean-actual),2.)
        self.assertEqual(math.sqrt((mean-actual)**2),2.)
        self.assertAlmostEqual(math.sqrt(variance+(mean-actual)**2),
                               math.sqrt(6.))

    def test_randomized_pit_and_push_mass(self):
        pmf = [{"value":0,"mass":.25},{"value":2,"mass":.75}]
        self.assertEqual(threshold_triplet(pmf,2),
                         {"over":0,"under":.25,"push":.75})
        self.assertAlmostEqual(.25+.37*.75,.5275)
        self.assertAlmostEqual(sum(threshold_triplet(pmf,2).values()),1)

    def test_two_point_joint_exact_energy_variogram(self):
        atoms = [((0,0),.5),((2,2),.5)]
        y=(0,2)
        self.assertAlmostEqual(energy_score(atoms,y),2-math.sqrt(2)/2)
        self.assertAlmostEqual(variogram_05(atoms,y),2.)
        independent = [((0,0),.25),((0,2),.25),
                       ((2,0),.25),((2,2),.25)]
        self.assertNotAlmostEqual(energy_score(atoms,y),
                                  energy_score(independent,y))
        self.assertNotAlmostEqual(variogram_05(atoms,y),
                                  variogram_05(independent,y))

    def test_5000_vs_20000_numeric_mc_se_exact_ratio(self):
        p=.36
        se5=math.sqrt(p*(1-p)/5000)
        se20=math.sqrt(p*(1-p)/20000)
        self.assertEqual(se5/se20,2.)


class IndependentEngineeringBlockerWitnesses(unittest.TestCase):
    def test_aggregate_240_minutes_can_hide_six_on_court(self):
        # Six players each assigned 40 minutes gives 240 aggregate.
        # If all overlap for minutes 0..40, six are on court, then zero.
        illegal = [(0,40,f"player:{i}") for i in range(6)]
        self.assertEqual(sum(b-a for a,b,_ in illegal),240)
        self.assertFalse(five_on_floor(illegal,48))

    def test_duplicate_participant_interval_detected(self):
        illegal = [(0,48,"A"),(0,48,"B"),(0,48,"C"),
                   (0,48,"D"),(0,48,"D")]
        self.assertEqual(sum(b-a for a,b,_ in illegal),240)
        self.assertFalse(five_on_floor(illegal,48))

    def test_five_on_court_full_regulation_and_overtime(self):
        for ot in range(4):
            duration=48+ot*5
            valid=[(0,duration,str(i)) for i in range(5)]
            self.assertTrue(five_on_floor(valid,duration))
            self.assertEqual(sum(b-a for a,b,_ in valid),240+25*ot)

    def test_completed_pipelines_are_not_stage_voters(self):
        dependencies={"S_ONLY":("S",),"S_O":("S","O"),
                      "S_O_J":("S","O","J")}
        self.assertEqual(len(dependencies),3)
        self.assertTrue({"S","O","J"}.isdisjoint(dependencies))
        self.assertTrue(all("S" in stages for stages in dependencies.values()))
        # G1 must test the actual C optimizer; this is a QA oracle only.

    def test_10000_paths_from_two_games_are_two_outcomes(self):
        paths=[(f"game:{g}",j) for g in (1,2) for j in range(5000)]
        self.assertEqual(len(paths),10000)
        self.assertEqual(len({game for game,_ in paths}),2)
        # Path replication is numerical integration, not more independent games.

    def test_game_level_error_invariant_to_mc_replication(self):
        # One score per observed game, not a score per simulated scenario.
        observed={"A":1,"B":0}
        predictions={"A":.7,"B":.2}
        losses={g:(predictions[g]-y)**2 for g,y in observed.items()}
        baseline=sum(losses.values())/len(losses)
        for replication in (1,5000,20000):
            replicated={g:[predictions[g]]*replication for g in observed}
            unique_game_scores=[
                (sum(replicated[g])/len(replicated[g])-observed[g])**2
                for g in observed
            ]
            self.assertAlmostEqual(sum(unique_game_scores)/2,baseline,places=10)


if __name__=="__main__":
    unittest.main()
