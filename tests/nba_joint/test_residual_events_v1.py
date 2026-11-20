import copy
import unittest
from v2.nba_joint.residual_events_v1 import simulate
from v2.nba_joint.residual_audit_v1 import audit_run,audit_path
from v2.nba_joint.residual_opportunity_v1 import capacity_certificate,draw_team,audit_team
import numpy as np


def fixture():
    beta=dict(alpha=20.,beta=30.)
    rates={s:dict(alpha=20.,beta=b) for s,b in dict(points=30.,threes=300.,rebounds=100.,assists=120.,turnovers=300.).items()}
    spec=dict(rates=rates,conversion3=beta,conversion2=beta,conversion_ft=beta,ft_non3_point_share=beta)
    players=[]
    for team in ('A','B'):
        for i in range(7):
            players.append(dict(player_id=f'{team}{i}',team_id=team,name=f'Fixture{team}{i}',
                minutes=dict(mean=12.,variance=15.,ot_probability=.12,ot_continuation=.2,family='beta'),**spec))
    return dict(target='SYNTHETIC_ENGINEERING_ONLY',named_players=players,
        residual_groups={team:spec.copy() for team in ('A','B')},pace=dict(shape=200.,scale=.5),
        events={k:dict(alpha=a,beta=b) for k,a,b in (
            ('assisted_fg',60,40),('credited_rebound',90,10),('offensive_rebound',25,75),('shooting_ft_three_series',5,95))})


class ResidualPublicPathTests(unittest.TestCase):
    def test_actual_event_accounting_and_determinism(self):
        m=fixture();a=simulate(m,seed=41,n=3);b=simulate(m,seed=41,n=3)
        self.assertEqual(a,b);self.assertEqual(audit_run(a)['scenarios'],3)
        for scenario in a['scenarios']:
            path=scenario['proposals'][-1]
            self.assertGreater(len(path['ledger']),400)
            self.assertTrue(all(scenario['fixed']['O'][t]['renormalized_named_exposures'] is False for t in ('A','B')))

    def test_mutations_rejected_from_independent_reconstruction(self):
        run=simulate(fixture(),seed=42,n=1);s=run['scenarios'][0];fixed=s['fixed'];base=s['proposals'][-1]
        mutations=[]
        v=copy.deepcopy(base);v['counts']['A'][0]['points']+=1;mutations.append(v)
        v=copy.deepcopy(base);shot=next(r for r in v['ledger'] if r['kind']=='FIELD_GOAL');shot['score']['A']+=1;mutations.append(v)
        v=copy.deepcopy(base);r=next(r for r in v['ledger'] if r['kind']=='REBOUND');r['miss']=-1;mutations.append(v)
        v=copy.deepcopy(base);r=next(r for r in v['ledger'] if r['kind']=='FIELD_GOAL');r['actor']=999;mutations.append(v)
        v=copy.deepcopy(base);r=next(r for r in v['ledger'] if r['kind']=='FIELD_GOAL' and r['made']);r['assist']=r['actor'];mutations.append(v)
        v=copy.deepcopy(base);r=next(r for r in v['ledger'] if r['kind']=='DEFLECTION_OUT_OF_BOUNDS');v['ledger'].remove(r)
        for i,r in enumerate(v['ledger']):r['index']=i
        mutations.append(v)
        for changed in mutations:
            with self.assertRaises(ValueError):audit_path(fixed,changed)

    def test_execution_failure_not_dropped_or_scored(self):
        run=simulate(fixture(),seed=41,n=3,event_budget=5)
        self.assertEqual(run['status'],'FAILED_WHOLE_RUN');self.assertEqual(len(run['failed']),3)
        self.assertEqual(run['scenario_denominator'],3);self.assertEqual(len(run['scenarios']),3)
        with self.assertRaises(ValueError):audit_run(run)

    def test_o_negative_public_contracts(self):
        p=fixture()['named_players'][:7];self.assertLess(capacity_certificate(p)['conservative_numeric_upper_share'],5)
        for length in (49.,True,float('nan')):
            with self.assertRaises(ValueError):draw_team(p,length,np.random.default_rng(1))
        for change in ('mixed','family','duplicate'):
            bad=copy.deepcopy(p)
            if change=='mixed':bad[0]['team_id']='WRONG'
            elif change=='family':bad[0]['minutes']['family']='truncated_lognormal'
            else:bad[0]['player_id']=bad[1]['player_id']
            with self.assertRaises(ValueError):capacity_certificate(bad)
        d=draw_team(p,48.,np.random.default_rng(1));audit_team(d,48.)
        d['actors'][0]['team_id']='WRONG'
        with self.assertRaises(ValueError):audit_team(d,48.)


if __name__=='__main__':unittest.main()
