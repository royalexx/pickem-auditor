"""Synthetic engineering checks, never historical calibration evidence."""
import copy
import unittest
from . import native_ws1 as n
from . import shadow as s


def fixture():
    row = dict(provider_event_id="p", event_id="e", event_id_namespace="espn", player_id="a",
        player_id_namespace="espn", nflverse_player_id=None, book="B", stat="receptions",
        period="full_game", line=4, over_odds=-120, under_odds=100, team="A", opponent="B",
        player="Player", sport="NFL", source_certified=True, source_sha256="source",
        source_archive_path="raw", source_received_at="2026-11-15T04:00:00Z",
        input_freeze_at="2026-11-15T05:00:00Z", event_start_at="2026-11-15T18:00:00Z",
        scheduled_kickoff="2026-11-15T18:00:00Z", roster_receipt_sha256="roster")
    row['quote_id']=n.digest({'identity':{k:row.get(k) for k in n.QUOTE_IDENTITY},'quote_source_sha256':'source'})
    row['candidate_id']=n.digest({'quote_id':row['quote_id'],'event':'e','player':'a'})
    row['original_quote']={k:row[k] for k in ('book','player','stat','line','over_odds','under_odds','sport')}
    row['original_quote'].update(event_id='p',event_start=row['event_start_at'],event_teams=['A','B'])
    manifest={'input_freeze_at':row['input_freeze_at'],'events':[dict(espn_event_id='e',schedule_verified=True,scheduled_kickoff=row['event_start_at'],home='A',away='B')]}
    receipts={'source':dict(archive_path='raw',source_received_at=row['source_received_at']),'roster':{}}
    return row,manifest,receipts


class NativeMarketTests(unittest.TestCase):
    def test_c2_without_original_forecast_or_availability(self):
        r,m,v=fixture()
        p,implied,_=n.market(r,m,v,s.timestamp('2026-11-15T06:00:00Z'))
        self.assertAlmostEqual(p,(120/220)/(120/220+.5))
        self.assertAlmostEqual(implied['under'],.5)

    def test_identity_price_chronology_failures(self):
        for key,value in [('over_odds',0),('under_odds',True),('period','first_half'),('player_id','other'),
                          ('source_received_at','2026-11-15T19:00:00Z')]:
            r,m,v=fixture();r[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                n.market(r,m,v,s.timestamp('2026-11-15T06:00:00Z'))
        r,m,v=fixture()
        with self.assertRaisesRegex(ValueError,'started_game'):
            n.market(r,m,v,s.timestamp(r['event_start_at']))

    def test_raw_pair_duplicate_and_wrong_price(self):
        r,m,v=fixture(); key=('p','B','receptions','Player',4)
        match=dict(over_odds=-120,under_odds=100,event_start=r['event_start_at'],provider_over_player_id='a',provider_under_player_id='a')
        for pairs in ({},{key:[match,match]},{key:[dict(match,under_odds=-110)]}):
            with self.assertRaises(ValueError):
                n.market(r,m,v,s.timestamp('2026-11-15T06:00:00Z'),pairs)

    def test_never_pair_different_markets(self):
        payload=[dict(id='p',commence_time='t',bookmakers=[dict(title='B',markets=[
            dict(key='player_receptions',outcomes=[dict(name='Over',description='P',point=4,price=-110)]),
            dict(key='player_receptions',outcomes=[dict(name='Under',description='P',point=4,price=-110)])])])]
        self.assertEqual(n.raw_pairs(payload),{})

if __name__=='__main__': unittest.main()

class IndependentScoringTests(unittest.TestCase):
    def test_market_scored_without_c1(self):
        from .test_shadow import fixture
        from .score import compare
        m,f,r=fixture();r['production']=None
        out=s.build(m,f,[r],[],now='2026-11-14T23:00:00Z')
        forecast=next(x for x in out['forecasts'] if x['candidate']=='C2')
        scored=compare(out,[dict(contract_id='c1',event_id='g1',identity=forecast['identity'],outcome='over')])
        self.assertEqual(scored['standalone_conditional_nonpush']['C2']['n'],1)
        self.assertEqual(scored['pairwise_comparisons']['C2']['C1']['matched_contracts'],0)
