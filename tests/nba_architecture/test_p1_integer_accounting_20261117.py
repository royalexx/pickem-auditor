"""Independent exhaustive primitive enumeration, entirely synthetic."""
import itertools
import unittest
from v2.nba_architecture.p1_history import _stats
from v2.nba_architecture.p1_integer_accounting import partial_counts_feasible


def truth_from_primitives(shooting,rebounds=None):
    x,t,f,miss2,miss3,missft=shooting
    s=dict(points=2*x+3*t+f,fgm=x+t,threes=t,fga=x+t+miss2+miss3,
           fg3a=t+miss3,ftm=f,fta=f+missft)
    if rebounds is not None:
        o,d,a=rebounds;r=o+d;p=s['points']
        s.update(oreb=o,dreb=d,rebounds=r,assists=a,pr=p+r,pa=p+a,ra=r+a,pra=p+r+a)
    return s


def compare_all_partial_assignments(test,fields,complete_rows,max_known=2):
    """Every subset and every known0..2 assignment, including impossible ones.

    Primitive ranges0..2 suffice here: any larger unobserved primitive can be
    reduced absent a binding observed total; observed totals themselves<=2.
    Missing attempts may exceed2 through sums, retained by enumeration.
    """
    feasible=set()
    for row in complete_rows:
        for mask in range(1<<len(fields)):
            values=tuple(row[field] if mask>>i&1 else None for i,field in enumerate(fields))
            if all(v is None or v<=max_known for v in values):feasible.add(values)
    count=0
    for values in itertools.product((None,*range(max_known+1)),repeat=len(fields)):
        s={field:v for field,v in zip(fields,values) if v is not None}
        actual=partial_counts_feasible(s);expected=values in feasible
        test.assertEqual(actual,expected,repr(s));count+=1
    return count


class IntegerAccounting(unittest.TestCase):
    def test_original_impossible_point_parity_and_combination_half_integer(self):
        for s in ({'points':1,'fga':1,'fg3a':0,'ftm':0},
                  {'points':1,'fga':1,'ftm':0},
                  {'pr':3,'pa':3,'ra':3}):
            with self.subTest(stats=s),self.assertRaisesRegex(ValueError,'INTEGER_STAT_ACCOUNTING'):_stats(s)

    def test_valid_sparse_integer_completions_and_huge_counts(self):
        for s in ({'points':2,'fga':1,'fg3a':0,'ftm':0},
                  {'pr':3,'pa':3,'ra':2},{'pr':3,'pa':3},
                  {'points':3,'fga':1,'ftm':0},
                  {'points':10**100,'ftm':10**100,'fgm':0},
                  {'pr':10**100,'pa':10**100,'ra':10**100}):
            with self.subTest(stats=s):self.assertTrue(partial_counts_feasible(s));_stats(s)

    def test_exhaustive_shooting_subsets_against_primitive_enumeration(self):
        rows=[truth_from_primitives(p) for p in itertools.product(range(3),repeat=6)]
        self.assertEqual(compare_all_partial_assignments(self,
            ('points','fgm','fga','threes','fg3a','ftm','fta'),rows),4**7)

    def test_exhaustive_rebound_assist_combo_subsets(self):
        rows=[]
        for p,o,d,a in itertools.product(range(3),repeat=4):
            r=o+d;rows.append(dict(points=p,rebounds=r,assists=a,oreb=o,dreb=d,
                                  pr=p+r,pa=p+a,ra=r+a,pra=p+r+a))
        self.assertEqual(compare_all_partial_assignments(self,
            ('points','rebounds','assists','oreb','dreb','pr','pa','ra','pra'),rows),4**9)

    def test_cross_shooting_and_combination_subsets(self):
        rows=[]
        for x,t,f,r,a in itertools.product(range(3),repeat=5):
            p=2*x+3*t+f;rows.append(dict(points=p,fgm=x+t,threes=t,ftm=f,pr=p+r,pa=p+a,ra=r+a))
        self.assertEqual(compare_all_partial_assignments(self,
            ('points','fgm','threes','ftm','pr','pa','ra'),rows),4**7)

class WiderPrimitiveReferences(unittest.TestCase):
    def test_all_field_subsets_of_small_complete_shooting_primitives(self):
        fields=('points','fgm','fga','threes','fg3a','ftm','fta')
        checked=0
        for primitive in itertools.product(range(3),repeat=6):
            full=truth_from_primitives(primitive)
            for mask in range(1<<len(fields)):
                s={field:full[field] for i,field in enumerate(fields) if mask>>i&1}
                self.assertTrue(partial_counts_feasible(s),repr((primitive,s)))
                checked+=1
        self.assertEqual(checked,729*128)

    def test_every_integer_point_under_small_rectangular_attempt_caps(self):
        checked=0
        for cap2,cap3,capft in itertools.product(range(4),range(4),range(3)):
            primitive=list(itertools.product(range(cap2+1),range(cap3+1),range(capft+1)))
            for made,three,free in itertools.product((None,*range(cap2+cap3+1)),(None,*range(cap3+1)),(None,*range(capft+1))):
                s={'fga':cap2+cap3,'fg3a':cap3,'fta':capft}
                for key,value in (('fgm',made),('threes',three),('ftm',free)):
                    if value is not None:s[key]=value
                feasible={2*x+3*t+f for x,t,f in primitive
                    if (made is None or x+t==made) and (three is None or t==three)
                    and (free is None or f==free)}
                for p in range(2*cap2+3*cap3+capft+3):
                    actual=partial_counts_feasible(dict(s,points=p))
                    self.assertEqual(actual,p in feasible,repr((s,p,feasible)));checked+=1
        self.assertGreater(checked,10000)
        print('rectangular exact integer reference assignments:',checked)

    def test_every_integer_point_under_small_triangular_attempt_caps(self):
        checked=0
        for attempts,capft in itertools.product(range(6),range(4)):
            primitive=[(x,t,f) for x,t,f in itertools.product(range(attempts+1),range(attempts+1),range(capft+1)) if x+t<=attempts]
            for made,three,free in itertools.product((None,*range(attempts+1)),(None,*range(attempts+1)),(None,*range(capft+1))):
                s={'fga':attempts,'fta':capft}
                for key,value in (('fgm',made),('threes',three),('ftm',free)):
                    if value is not None:s[key]=value
                feasible={2*x+3*t+f for x,t,f in primitive
                    if (made is None or x+t==made) and (three is None or t==three)
                    and (free is None or f==free)}
                for p in range(3*attempts+capft+3):
                    self.assertEqual(partial_counts_feasible(dict(s,points=p)),p in feasible,repr((s,p,feasible)));checked+=1
        self.assertGreater(checked,10000)
        print('triangular exact integer reference assignments:',checked)
