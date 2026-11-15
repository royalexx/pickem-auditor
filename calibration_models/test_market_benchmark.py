"""Independent numeric expectations; fixtures are synthetic engineering only."""
import copy
from fractions import Fraction
import tempfile
from pathlib import Path
import unittest
from . import market_benchmark as b


def fixture(m='receptions',line=4.5,book='B'):
    r=dict(book=book,player='P',player_id='1',event_id='G',provider_event_id='raw',
        quote_id='q'+book, candidate_id='c',stat=next(k for k,v in b.LABELS.items() if v==m),
        period='full_game',line=line,over_odds=-120,under_odds=100,source_certified=True,
        source_sha256='h',source_received_at='2026-11-15T04:00:00Z',event_start_at='2026-11-15T18:00:00Z',
        settlement_semantics='FULL_GAME_OFFICIAL_STAT_OVERTIME_INCLUDED_V1')
    r['original_quote']={k:r[k] for k in ('book','player','stat','line','over_odds','under_odds')}
    r['original_quote'].update(event_id='raw',event_start=r['event_start_at'])
    w=dict(original_record=r,normalized_market=m,player_stat_id='ps')
    meta=dict(source_sha256='h',provider_event_id='raw',exact_bookmaker_title=book,period_as_reported='full_game',combined_tackle_accounting_certified=True,
        original_market_record=dict(outcomes=[dict(name=s,description='P',point=line,price=p,player_id='espn:1') for s,p in [('Over',-120),('Under',100)]]))
    ps=dict(game_id='G',espn_player_id='1',period='full_game',normalized_market=m)
    return w,meta,ps


def quote(w=None,meta=None,ps=None,cutoff='2026-11-15T05:00:00Z',dup=False):
    if w is None: w,meta,ps=fixture()
    return b.quote(w,meta,ps,cutoff,dup)

class BenchmarkTests(unittest.TestCase):
    def test_all_eleven(self):
        self.assertEqual(len(set(b.MARKETS)),11)
        for m in b.MARKETS:
            self.assertIsNotNone(quote(*fixture(m))['conditional_no_push'])
    def test_specialties_and_standalone_tackles_excluded(self):
        for m in ('solo_tackles','assisted_tackles','sacks','passes_defended','touchdowns','interceptions','field_goals'):
            w,meta,ps=fixture();w['normalized_market']=m
            self.assertIsNone(quote(w,meta,ps)['conditional_no_push'])
    def test_exact_prices_and_vig(self):
        self.assertEqual(b.implied(-120),float(Fraction(6,11)))
        self.assertEqual(b.implied(150),float(Fraction(2,5)))
        self.assertEqual(b.devig(-120,100)['over'],float(Fraction(12,23)))
        self.assertAlmostEqual(sum(b.devig(-115,-105).values()),1)
        for x in (0,99,True,float('inf'),None):
            with self.assertRaises(ValueError): b.implied(x)
    def test_nonpush_not_unconditional(self):
        w,m,p=fixture(line=4);q=quote(w,m,p)
        self.assertIsNone(q['push_probability']);self.assertIsNone(q['unconditional'])
        self.assertEqual(q['probability_semantics'],'conditional_on_nonpush')
    def test_different_lines_not_averaged(self):
        a=quote(*fixture(line=4.5));c=quote(*fixture(line=5.5,book='C'))
        lines=b.consensus([a,c]);self.assertEqual(len(lines),2)
        self.assertTrue(all(x['book_count']==1 for x in lines))
    def test_same_line_consensus(self):
        a=quote(*fixture());c=quote(*fixture(book='C'))
        lines=b.consensus([a,c]);self.assertEqual(lines[0]['book_count'],2)
        self.assertEqual(lines[0]['conditional_no_push']['over'],float(Fraction(12,23)))
    def test_identical_quote_duplicate(self):
        w,m,p=fixture();q=quote(w,m,p,dup=True)
        self.assertIsNone(q['conditional_no_push'])
        self.assertIsNone(b.consensus([q,q])[0]['conditional_no_push'])
    def test_wrong_player_game_and_period(self):
        for key,value in [('game_id','other'),('espn_player_id','2'),('period','first_half'),('normalized_market','rushing_yards')]:
            w,m,p=fixture();p[key]=value
            self.assertIsNone(quote(w,m,p)['conditional_no_push'])
    def test_missing_side(self):
        for side in ('over','under'):
            w,m,p=fixture();w['original_record'][side+'_odds']=None;w['original_record']['original_quote'][side+'_odds']=None
            q=quote(w,m,p);self.assertIsNone(q['conditional_no_push']);self.assertEqual(q['availability_state'],b.STATES[2])
    def test_hash_integrity_and_immutable_write(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path=root/'x';path.write_bytes(b'original')
            self.assertEqual(b.checked(root,dict(path='x',sha256=b.sha(b'original'))),b'original')
            with self.assertRaises(ValueError): b.checked(root,dict(path='x',sha256=b.CANONICAL_SHA))
            with self.assertRaises(ValueError): b.exclusive(path,b'changed')
    def test_chronology(self):
        for cutoff in ('2026-11-15T03:00:00Z','2026-11-15T18:00:00Z','2026-11-16T05:00:00Z'):
            w,m,p=fixture();self.assertIsNone(quote(w,m,p,cutoff)['conditional_no_push'])
        w,m,p=fixture();w['original_record']['source_received_at']='2026-11-15T19:00:00Z'
        self.assertEqual(quote(w,m,p)['availability_state'],b.STATES[6])
    def test_settlement_period_and_cross_market(self):
        for change in ('settlement','period','tackles','raw_price','raw_player'):
            w,m,p=fixture('tackles_assists' if change=='tackles' else 'receptions')
            if change=='settlement': w['original_record']['settlement_semantics']='PRODUCT_SPECIFIC_RULES_UNVERIFIED'
            if change=='period': m['period_as_reported']=None
            if change=='tackles': m['combined_tackle_accounting_certified']=False
            if change=='raw_price': m['original_market_record']['outcomes'][0]['price']=-110
            if change=='raw_player': m['original_market_record']['outcomes'][0]['player_id']='other'
            self.assertIsNone(quote(w,m,p)['conditional_no_push'])
    def test_false_composite_reconstruction(self):
        for market in ('rushing_receiving_yards','passing_rushing_yards','receiving_targets'):
            w,m,p=fixture();w['normalized_market']=market;p['normalized_market']=market
            self.assertIsNone(quote(w,m,p)['conditional_no_push'])
    def test_unavailable_and_uncertified_never_inferred(self):
        w,m,p=fixture();w['original_record']['source_certified']=False
        q=quote(w,m,p);self.assertIsNone(q['conditional_no_push'])
        self.assertIsNone(b.consensus([q])[0]['conditional_no_push'])
        self.assertEqual(b.consensus([]),[])
    def test_missing_kickoff_retained(self):
        w,m,p=fixture();w['original_record']['event_start_at']=None
        q=quote(w,m,p);self.assertIn('INVALID_CHRONOLOGY',q['reasons'])
        self.assertIsNone(q['conditional_no_push'])

    def test_no_mutation(self):
        w,m,p=fixture();before=copy.deepcopy((w,m,p));quote(w,m,p)
        self.assertEqual((w,m,p),before)

if __name__=='__main__': unittest.main()
