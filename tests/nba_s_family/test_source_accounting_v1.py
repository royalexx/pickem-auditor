"""Independent finite enumeration references, using only synthetic counts."""
import itertools
import unittest
from v2.nba_s_family.model import SFError
from v2.nba_s_family.source_accounting import validate_count_feasibility


def feasible(stats):
    try:return validate_count_feasibility(stats)
    except SFError as exc:
        if exc.reason=='P1_NATIVE_INTEGER_ACCOUNTING_INFEASIBLE':return False
        raise


def shooting_reference():
    cases=0
    fields=('points','fgm','threes','ftm')
    for fga in range(2):
        for fg3a in range(fga+1):
            for fta in range(2):
                complete=[]
                for three in range(fg3a+1):
                    for two in range(fga-fg3a+1):
                        for ft in range(fta+1):
                            complete.append(dict(points=2*two+3*three+ft,fgm=two+three,threes=three,ftm=ft))
                # Every optional field subset, with candidate count values.
                for values in itertools.product([None,*range(5)],*[ [None,0,1] for _ in range(3)]):
                    fixed={k:v for k,v in zip(fields,values) if v is not None}
                    expected=any(all(row[k]==v for k,v in fixed.items()) for row in complete)
                    actual=feasible(dict(fga=fga,fg3a=fg3a,fta=fta,**fixed))
                    if actual!=expected:raise AssertionError((fixed,fga,fg3a,fta,expected,actual))
                    cases+=1
    return dict(cases=cases,disagreements=0,basis='exhaustive bounded 2PM/3PM/FTM integer enumeration; all optional field subsets')


def combo_reference():
    cases=0
    complete=[dict(pr=p+r,pa=p+a,ra=r+a) for p,r,a in itertools.product(range(5),repeat=3)]
    for values in itertools.product([None,*range(5)],repeat=3):
        fixed={k:v for k,v in zip(('pr','pa','ra'),values) if v is not None}
        expected=any(all(row[k]==v for k,v in fixed.items()) for row in complete)
        actual=feasible(fixed)
        if actual!=expected:raise AssertionError((fixed,expected,actual))
        cases+=1
    return dict(cases=cases,disagreements=0,basis='exhaustive integer P/R/A enumeration; all PR/PA/RA field subsets')


class IndependentIntegerReferences(unittest.TestCase):
    def test_shooting_all_field_subsets_against_integer_event_enumeration(self):
        self.assertEqual(shooting_reference()['cases'],972)

    def test_combo_all_field_subsets_against_integer_primitive_enumeration(self):
        self.assertEqual(combo_reference()['cases'],216)
        self.assertFalse(feasible(dict(pr=3,pa=3,ra=3)))
        self.assertTrue(feasible(dict(pr=4,pa=4,ra=4)))

    def test_no_boolean_or_unsupported_numerical_certification(self):
        with self.assertRaisesRegex(SFError,'INTEGER_SUPPORT'):validate_count_feasibility({'points':True})
        with self.assertRaisesRegex(SFError,'NUMERICAL_RANGE_UNRESOLVED'):validate_count_feasibility({'points':2**49})
        self.assertTrue(validate_count_feasibility({'points':0}))

if __name__=='__main__':unittest.main()
