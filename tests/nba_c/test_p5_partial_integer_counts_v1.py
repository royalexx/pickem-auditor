"""Independent primitive references for native integer-count transport."""
import itertools
import unittest

from v2.nba_c.physical_counts import partial_counts_feasible
from v2.nba_c.native_adapters import _box_stats
from v2.nba_c.warehouse import WarehouseError


def compare_partial(test,fields,rows):
    feasible=set()
    for row in rows:
        for present in itertools.product((False,True),repeat=len(fields)):
            values=tuple(row[key] if keep else None for key,keep in zip(fields,present))
            if all(value is None or value<=2 for value in values):feasible.add(values)
    cases=0
    for values in itertools.product((None,0,1,2),repeat=len(fields)):
        stats={key:value for key,value in zip(fields,values) if value is not None}
        test.assertEqual(partial_counts_feasible(stats),values in feasible,repr(stats))
        cases+=1
    return cases


class NativeIntegerCountReferencesV1(unittest.TestCase):
    def test_parity_combination_and_component_lower_bound_attacks(self):
        for stats in ({'points':1,'fga':1,'fg3a':0,'ftm':0},
                      {'pr':3,'pa':3,'ra':3},{'oreb':4,'pr':3}):
            with self.subTest(stats=stats),self.assertRaisesRegex(WarehouseError,'INTEGER_STAT_ACCOUNTING'):
                _box_stats(stats)
        for stats in ({'points':2,'fga':1,'fg3a':0,'ftm':0},
                      {'pr':3,'pa':3,'ra':2},{'oreb':2,'pr':3},
                      {'points':10**100,'ftm':10**100,'fgm':0},
                      {'pr':10**100,'pa':10**100,'ra':10**100}):
            with self.subTest(stats=stats):_box_stats(stats)

    def test_exhaustive_shooting_partial_assignments(self):
        rows=[]
        for two_pa,three_pa,fta in itertools.product(range(3),repeat=3):
            for two_pm,three_pm,ftm in itertools.product(range(two_pa+1),range(three_pa+1),range(fta+1)):
                rows.append(dict(points=2*two_pm+3*three_pm+ftm,fgm=two_pm+three_pm,
                    fga=two_pa+three_pa,threes=three_pm,fg3a=three_pa,ftm=ftm,fta=fta))
        self.assertEqual(compare_partial(self,('points','fgm','fga','threes','fg3a','ftm','fta'),rows),16384)

    def test_exhaustive_rebound_and_combination_partial_assignments(self):
        rows=[]
        for points,oreb,dreb,assists in itertools.product(range(3),repeat=4):
            rebounds=oreb+dreb
            rows.append(dict(points=points,oreb=oreb,dreb=dreb,assists=assists,rebounds=rebounds,
                pr=points+rebounds,pa=points+assists,ra=rebounds+assists,pra=points+rebounds+assists))
        self.assertEqual(compare_partial(self,('points','oreb','dreb','assists','rebounds','pr','pa','ra','pra'),rows),262144)

    def test_exhaustive_cross_shooting_and_combo_assignments(self):
        rows=[]
        for two_pm,three_pm,ftm,rebounds,assists in itertools.product(range(3),repeat=5):
            points=2*two_pm+3*three_pm+ftm
            rows.append(dict(points=points,fgm=two_pm+three_pm,threes=three_pm,ftm=ftm,
                pr=points+rebounds,pa=points+assists,ra=rebounds+assists))
        self.assertEqual(compare_partial(self,('points','fgm','threes','ftm','pr','pa','ra'),rows),16384)


if __name__=='__main__':unittest.main()
