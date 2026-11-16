"""Independent report F1/F2 and finite-marginal compatibility controls."""
import copy
import unittest
from golden_v2 import distribution, original_offer
from test_v2_contracts import evaluation
from test_g0_pipeline_completion_20261116 import coherent_case
from v2.nba_architecture.v2_contracts import seal, ContractError, marginal_from_joint, offer_view, STATS
from v2.nba_architecture.families_v2 import validate_opportunity, validate_forecast, validate_settlement


def reseal(obj):
    obj = copy.deepcopy(obj)
    obj.pop('content_hash')
    return seal(obj)


def law(player, atoms, probability=1.):
    player.update(participation_probability=probability,
                  participation_evidence='unknown' if probability is None else 'independently_estimated')
    player['minutes_law']['parameters']['support'] = [
        {'minutes': minutes, 'mass': mass} for minutes, mass in atoms]


def refresh(c):
    c['opportunity'] = reseal(c['opportunity'])
    c['scenarios']['opportunity_sha256'] = c['opportunity']['content_hash']
    c['scenarios'] = reseal(c['scenarios'])
    c['points'] = marginal_from_joint(c['scenarios'], c['pregame'],
        c['pregame']['players'][0]['player_id'], 'points', '2026-11-16T23:03:00Z', 42)
    return c


def exposure_distribution(c, index=5, positive_mass=.75, stat='points', conditioning='unconditional'):
    d = distribution(c['pregame'], mode='S_O')
    d.update(player_id=c['pregame']['players'][index]['player_id'], stat=stat,
             conditioning=conditioning, pmf=[{'value': 0, 'mass': 1-positive_mass},
                                           {'value': 2, 'mass': positive_mass}])
    d['lineage']['G'] = c['game_state']['model']
    d['opportunity_output_sha256'] = c['opportunity']['content_hash']
    return reseal(d)


class IndependentReportRegressions(unittest.TestCase):
    def test_f1_unattainable_minute_atom_rejected_at_all_boundaries(self):
        c = coherent_case()
        law(c['opportunity']['players'][0], [(0., .5), (48., .5)])
        refresh(c)
        for name, call in [
            ('O', lambda: validate_opportunity(c['opportunity'], c['pregame'], c['game_state'])),
            ('forecast', lambda: validate_forecast(c['points'], c['pregame'], g=c['game_state'], o=c['opportunity'], scenarios=c['scenarios'])),
            ('C', lambda: validate_settlement(evaluation(c['points']), c['points'], c['pregame'], g=c['game_state'], o=c['opportunity'], scenarios=c['scenarios']))]:
            with self.subTest(boundary=name):
                with self.assertRaises(ContractError): call()

    def test_f2_all_eight_markets_zero_exposure_rejected_at_forecast_and_c(self):
        c = coherent_case()
        for stat in sorted(STATS):
            d = exposure_distribution(c, stat=stat)
            q = original_offer(c['pregame']); q.update(player_id=d['player_id'], stat=stat); q=reseal(q)
            v = offer_view(d,q,c['pregame'],'2026-11-16T23:04:00Z')
            e = evaluation(d,v,actual=0,participation='PLAYED_ZERO_MINUTES')
            with self.subTest(stat=stat,boundary='forecast'):
                with self.assertRaises(ContractError):validate_forecast(d,c['pregame'],g=c['game_state'],o=c['opportunity'])
            with self.subTest(stat=stat,boundary='C'):
                with self.assertRaises(ContractError):validate_settlement(e,d,c['pregame'],g=c['game_state'],o=c['opportunity'],view=v,quote=q)

    def test_f2_zero_count_positive_counterparts_all_markets(self):
        c=coherent_case()
        for stat in sorted(STATS):
            d=exposure_distribution(c,positive_mass=0,stat=stat)
            q=original_offer(c['pregame']);q.update(player_id=d['player_id'],stat=stat);q=reseal(q)
            v=offer_view(d,q,c['pregame'],'2026-11-16T23:04:00Z')
            self.assertEqual(v['probabilities'],{'over':0,'under':1.,'push':0})
            self.assertTrue(validate_settlement(evaluation(d,v,actual=0,participation='PLAYED_ZERO_MINUTES'),d,c['pregame'],g=c['game_state'],o=c['opportunity'],view=v,quote=q))


class LawCouplingControls(unittest.TestCase):
    def exchange_case(self, masses=(.5,.5)):
        c=coherent_case()
        law(c['opportunity']['players'][0],[(0.,masses[0]),(48.,1-masses[0])])
        law(c['opportunity']['players'][5],[(0.,masses[1]),(48.,1-masses[1])])
        # Both observed samples may legitimately take target=48, bench=played-zero.
        # No exact empirical frequencies are imposed on the declared laws.
        for sc in c['opportunity']['scenarios']:sc['players'][5]['participation']='PLAYED_ZERO_MINUTES'
        for sc in c['scenarios']['scenarios']:
            sc['players'][5]['participation']='PLAYED_ZERO_MINUTES'
            c['scenarios']['opportunity_witness'][sc['scenario_id']][5]['participation']='PLAYED_ZERO_MINUTES'
        return refresh(c)

    def test_feasible_exchange_without_empirical_frequency_equality(self):
        c=self.exchange_case()
        self.assertTrue(validate_opportunity(c['opportunity'],c['pregame'],c['game_state']))
        d=exposure_distribution(c,index=0,positive_mass=.4)
        self.assertTrue(validate_forecast(d,c['pregame'],g=c['game_state'],o=c['opportunity']))

    def test_marginal_masses_incompatible_even_when_each_atom_attainable(self):
        c=self.exchange_case((.75,.75))
        with self.assertRaises(ContractError):validate_opportunity(c['opportunity'],c['pregame'],c['game_state'])

    def test_nonzero_count_mass_cannot_exceed_positive_exposure_mass(self):
        c=self.exchange_case()
        d=exposure_distribution(c,index=0,positive_mass=.75)
        with self.assertRaises(ContractError):validate_forecast(d,c['pregame'],g=c['game_state'],o=c['opportunity'])

class FiniteSamplingAndConditioning(unittest.TestCase):
    exchange_case = LawCouplingControls.exchange_case
    def test_empirical_joint_frequency_need_not_equal_law_mass(self):
        c=self.exchange_case()
        # Both finite draws take the same branch of the valid 50/50 joint law.
        self.assertTrue(validate_forecast(c['points'],c['pregame'],g=c['game_state'],o=c['opportunity'],scenarios=c['scenarios']))

    def test_participation_conditioning_uses_conditional_exposure_bound(self):
        c=self.exchange_case()
        d=exposure_distribution(c,index=0,positive_mass=.5,conditioning='conditional_on_participation')
        self.assertTrue(validate_forecast(d,c['pregame'],g=c['game_state'],o=c['opportunity']))
        bad=exposure_distribution(c,index=0,positive_mass=.51,conditioning='conditional_on_participation')
        with self.assertRaises(ContractError):validate_forecast(bad,c['pregame'],g=c['game_state'],o=c['opportunity'])

class IndependentSmallCouplingOracle(unittest.TestCase):
    def test_exact_two_player_exchange_grid(self):
        from v2.nba_architecture.exposure_v2 import _check_team
        from fractions import Fraction
        for a in (Fraction(0),Fraction(1,4),Fraction(1,2),Fraction(3,4),Fraction(1)):
            for b in (Fraction(0),Fraction(1,4),Fraction(1,2),Fraction(3,4),Fraction(1)):
                def atoms(zero):
                    return tuple((m,float(w)) for m,w in ((0.,zero),(48.,1-zero)) if w>0)
                players=((1.,atoms(a)),(1.,atoms(b)))+((1.,((48.,1.),)),)*4
                with self.subTest(a=str(a),b=str(b)):
                    # Four fixed players leave exactly 48 minutes for two others.
                    # Of two 0/48 laws, exactly one must be positive in every state.
                    if a+b==1:self.assertTrue(_check_team(players,((0,1.),),()))
                    else:
                        with self.assertRaises(ContractError):_check_team(players,((0,1.),),())

    def test_overtime_probability_and_marginals_are_jointly_bound(self):
        from v2.nba_architecture.exposure_v2 import _check_team
        players=((1.,((48.,.5),(53.,.5))),)*5+((1.,((0.,1.),)),)
        self.assertTrue(_check_team(players,((0,.5),(1,.5)),()))
        with self.assertRaises(ContractError):_check_team(players,((0,.25),(1,.75)),())

    def test_fractional_minutes_and_permutation(self):
        from v2.nba_architecture.exposure_v2 import _check_team
        players=((1.,((23.5,1.),)),(1.,((24.5,1.),)))+((1.,((48.,1.),)),)*4
        self.assertTrue(_check_team(players,((0,1.),),()))
        self.assertTrue(_check_team(tuple(reversed(players)),((0,1.),),()))

    def test_positive_atom_cannot_be_hidden_below_solver_tolerance(self):
        from v2.nba_architecture.exposure_v2 import _check_team
        players=((1.,((0.,1e-20),(48.,1.-1e-20))),)+((1.,((48.,1.),)),)*4+((1.,((0.,1.),)),)
        with self.assertRaises(ContractError):_check_team(players,((0,1.),),())

    def test_observed_label_must_have_positive_compatible_probability(self):
        from v2.nba_architecture.exposure_v2 import _check_team
        # Conservation plus the second player's law forces the first q to 1.
        # This sampled allocation conserves minutes and uses individually legal
        # atoms, but its DNP label has zero probability under every coupling.
        players=((None,((0.,.5),(48.,.5))),(1.,((0.,.5),(48.,.5))))+((1.,((48.,1.),)),)*4
        invalid=(0,(('DNP',0.),('PLAYED',48.))+(('PLAYED',48.),)*4)
        with self.assertRaises(ContractError):_check_team(players,((0,1.),),(invalid,))

    def test_verification_budget_fails_closed(self):
        from unittest.mock import patch
        import v2.nba_architecture.exposure_v2 as module
        players=((1.,((48.,1.),)),)*5
        module._check_team.cache_clear()
        with patch.object(module,'MAX_SEARCH_NODES',0):
            with self.assertRaises(ContractError) as cm:module._check_team(players,((0,1.),),())
            self.assertEqual(cm.exception.code,'O_COUPLING_VERIFICATION_BUDGET')
        module._check_team.cache_clear()
        self.assertTrue(module._check_team(players,((0,1.),),()))

class ImpliedExposureBound(unittest.TestCase):
    def test_positive_counterfactual_support_can_be_forced_out_by_team_pool(self):
        c=coherent_case()
        for i in range(5):law(c['opportunity']['players'][i],[(48.,1.)])
        # Five certain 48-minute players leave no room for the bench. Its
        # conditional law can describe a counterfactual appearance, but q must be 0.
        law(c['opportunity']['players'][5],[(0.,.5),(48.,.5)],probability=None)
        # Remove played-zero observations: q=0 legitimately implies DNP only.
        for sc in c['opportunity']['scenarios']:sc['players'][5]['participation']='DNP'
        c['opportunity']=reseal(c['opportunity'])
        d=exposure_distribution(c,positive_mass=.25)
        with self.assertRaises(ContractError):validate_forecast(d,c['pregame'],g=c['game_state'],o=c['opportunity'])

class UnknownParticipationPositive(unittest.TestCase):
    def test_conditional_minutes_do_not_invent_certain_participation(self):
        c=coherent_case()
        law(c['opportunity']['players'][5],[(0.,.5),(48.,.5)],probability=None)
        for sc in c['opportunity']['scenarios']:sc['players'][5]['participation']='DNP'
        c['opportunity']=reseal(c['opportunity'])
        # The five starters' participation is also unknown: the bench can exchange
        # minutes with them in the declared law, even if these samples do not.
        d=exposure_distribution(c,positive_mass=.25)
        self.assertTrue(validate_forecast(d,c['pregame'],g=c['game_state'],o=c['opportunity']))

    def test_tiny_positive_overtime_state_cannot_be_dropped(self):
        from v2.nba_architecture.exposure_v2 import _check_team
        players=((1.,((48.,1.),)),)*5
        with self.assertRaises(ContractError):_check_team(players,((0,1.),(1,1e-20)),())

class CountConstraintMustPreserveObservedSupport(unittest.TestCase):
    def test_count_certainty_cannot_force_observed_dnp_to_probability_zero(self):
        c=coherent_case()
        # The bench could exchange with unknown-participation starters.
        law(c['opportunity']['players'][5],[(0.,.5),(48.,.5)],probability=None)
        c['opportunity']=reseal(c['opportunity'])
        # Maximum positive exposure is .5, but achieving .5 requires q=1,
        # which rules out the positive-weight DNP witness. A strict lower value
        # remains feasible with positive DNP probability.
        bad=exposure_distribution(c,positive_mass=.5)
        with self.assertRaises(ContractError):validate_forecast(bad,c['pregame'],g=c['game_state'],o=c['opportunity'])
        good=exposure_distribution(c,positive_mass=.25)
        self.assertTrue(validate_forecast(good,c['pregame'],g=c['game_state'],o=c['opportunity']))

class TinyConditionalAtomUnknownProbability(unittest.TestCase):
    def test_unattainable_tiny_atom_forces_unknown_participation_to_zero(self):
        from v2.nba_architecture.exposure_v2 import _check_team
        players=((None,((0.,1e-20),(48.,1.))),)+((1.,((48.,1.),)),)*4+((1.,((0.,1.),)),)
        with self.assertRaises(ContractError):_check_team(players,((0,1.),),())

class MonteCarloExposureControls(unittest.TestCase):
    exchange_case = LawCouplingControls.exchange_case

    def test_empirical_s_o_interior_frequency_is_not_a_hard_endpoint(self):
        import math
        c=self.exchange_case();d=exposure_distribution(c,index=0,positive_mass=.75)
        d['numerical'].update(method='empirical_mc',scenario_count=4,effective_sample_size=4.,
            max_probability_se=math.sqrt(.75*.25/4),zero_event_95_upper_bound=1-.05**.25,
            uncertainty_basis='heuristic_weighted_ess')
        d=reseal(d)
        self.assertTrue(validate_forecast(d,c['pregame'],g=c['game_state'],o=c['opportunity']))

    def test_zero_exposure_rejects_even_tiny_positive_mass(self):
        c=coherent_case();d=exposure_distribution(c,positive_mass=1e-20)
        with self.assertRaises(ContractError):validate_forecast(d,c['pregame'],g=c['game_state'],o=c['opportunity'])

class ConditioningProbabilityControls(unittest.TestCase):
    def test_conditional_and_unconditional_count_bounds_differ(self):
        c=coherent_case()
        for i in range(5):law(c['opportunity']['players'][i],[(48.,1.)])
        law(c['opportunity']['players'][0],[(48.,1.)],probability=.5)
        law(c['opportunity']['players'][5],[(48.,1.)],probability=.5)
        for sc in c['opportunity']['scenarios']:sc['players'][5]['participation']='DNP'
        c['opportunity']=reseal(c['opportunity'])
        for conditioning in ('unconditional','conditional_on_declared_roster'):
            d=exposure_distribution(c,index=0,positive_mass=.75,conditioning=conditioning)
            with self.subTest(conditioning=conditioning):
                with self.assertRaises(ContractError):validate_forecast(d,c['pregame'],g=c['game_state'],o=c['opportunity'])
        d=exposure_distribution(c,index=0,positive_mass=.75,conditioning='conditional_on_participation')
        self.assertTrue(validate_forecast(d,c['pregame'],g=c['game_state'],o=c['opportunity']))

    def test_null_participation_condition_is_rejected(self):
        c=coherent_case();law(c['opportunity']['players'][5],[(0.,1.)],probability=0.)
        for sc in c['opportunity']['scenarios']:sc['players'][5]['participation']='DNP'
        c['opportunity']=reseal(c['opportunity'])
        d=exposure_distribution(c,positive_mass=0.,conditioning='conditional_on_participation')
        with self.assertRaises(ContractError):validate_forecast(d,c['pregame'],g=c['game_state'],o=c['opportunity'])

class SourceExclusionAcrossPipelines(unittest.TestCase):
    def test_s_only_cannot_assign_counts_to_authoritative_out(self):
        c=coherent_case();p=c['pregame'];player=p['players'][0]
        player.update(availability='out',availability_evidence=dict(
            source_receipt_sha256=p['sources'][0]['receipt_sha256'],
            player_id=player['player_id'],game_id=p['game_id'],field='availability',value='out'))
        p=reseal(p);d=distribution(p)
        with self.assertRaises(ContractError):validate_forecast(d,p)
        d['pmf']=[{'value':0,'mass':1.}];d=reseal(d)
        self.assertTrue(validate_forecast(d,p))
        d['conditioning']='conditional_on_participation';d=reseal(d)
        with self.assertRaises(ContractError):validate_forecast(d,p)

class NumericalCertificateControls(unittest.TestCase):
    def test_solver_failure_or_false_primal_certificate_cannot_pass(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        import numpy as np
        import v2.nba_architecture.exposure_v2 as module
        players=((1.,((48.,1.),)),)*5
        for result,code in [
            (SimpleNamespace(status=4,success=False,x=None),'O_COUPLING_SOLVER_UNCERTIFIED'),
            (SimpleNamespace(status=0,success=True,x=np.zeros(1)),'O_COUPLING_RESIDUAL_UNCERTIFIED'),
            (SimpleNamespace(status=0,success=True,x=np.asarray([float('nan')])),'O_COUPLING_RESIDUAL_UNCERTIFIED')]:
            module._check_team.cache_clear()
            with self.subTest(code=code),patch.object(module,'linprog',return_value=result):
                with self.assertRaises(ContractError) as cm:module._check_team(players,((0,1.),),())
                self.assertEqual(cm.exception.code,code)
        module._check_team.cache_clear()
