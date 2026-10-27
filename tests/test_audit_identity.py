"""Offline regressions for snapshot identity and independent calibration observations."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import jobs
import report

class AuditIdentityTests(unittest.TestCase):
    def snapshot(self):
        return jobs.pipeline_to_snapshot(
            {'final_rank': 'Tier 2'},
            meta=dict(game_date='2026-10-26',sport='NBA',player='Example Player',stat='points',matchup='BOS @ NYK'),
            run_id='test',run_at='test',
            candidate=dict(side='over',line=20.5,team='BOS',opponent='NYK',player_id='123',event_id='abc'))

    def test_nba_settlement_fetches_and_parses_real_gamelog_contract(self):
        import settle
        calls=[]
        def fetch(url, **kwargs):
            calls.append(url)
            if '/gamelog' in url:
                return dict(names=['minutes','points'],
                    events={'g1':{'gameDate':'2026-10-26T23:00:00Z'}},
                    seasonTypes=[dict(displayName='Regular Season',categories=[dict(events=[
                        dict(eventId='g1',stats=['32','25'])])])])
            return {'athletes':[{'athlete':{'displayName':'Example Player','id':'123'}}]}
        fetchers=settle.default_fetchers(fetch)
        row=self.snapshot()
        updated,n=settle.settle_rows([row],as_of='2026-10-27',fetchers=fetchers)
        self.assertEqual(n,1)
        self.assertEqual(updated[0]['actual_stat'],25)
        self.assertEqual(updated[0]['outcome'],'win')
        self.assertEqual(len(calls),2)
        self.assertTrue(any('/123/' in url and '/gamelog' in url for url in calls))

    def test_generated_and_legacy_snapshots_find_closing_prices(self):
        quote=dict(sport='NBA',player='Example Player',player_norm='example player',team='BOS',opponent='NYK',
                   stat='points',line=20.5,book='Pinnacle',over_odds=-110,under_odds=-110,
                   retrieved_at='2026-10-26T12:00:00Z')
        snapshot=self.snapshot()
        self.assertEqual(snapshot['player_id'],'123')
        self.assertEqual(snapshot['event_id'],'abc')
        legacy={k:v for k,v in snapshot.items() if k not in ('team','opponent','player_id','event_id')}
        oldest={k:v for k,v in legacy.items() if k!='inputs'}
        for row in (snapshot,legacy,oldest):
            line,prob=jobs.closing_consensus_for_row(row,[quote],'2026-10-26T12:05:00Z')
            self.assertEqual(line,20.5)
            self.assertIsNotNone(prob)

    def test_distinct_market_identity_is_not_collapsed(self):
        base=dict(game_date='2026-10-26',sport='NBA',player='Same Name',player_id='1',event_id='a',
                  stat='points',side='over',reference_line=20.5)
        rows=[base,dict(base,sport='NHL'),dict(base,player_id='2'),dict(base,event_id='b'),
              dict(base,reference_line=21.5),dict(base,side='under')]
        self.assertEqual(len(report.dedupe_props(rows)),6)

    def test_earliest_verified_pregame_prediction_and_legacy_fallback(self):
        base=dict(game_date='2026-10-26',sport='NBA',player='P',stat='points',side='over',reference_line=20.5,
                  event_start='2026-10-26T20:00:00Z')
        early=dict(base,forecast_at='2026-10-26T12:00:00Z',q_grade=.6)
        late=dict(base,forecast_at='2026-10-26T19:00:00Z',q_grade=.7)
        post=dict(base,forecast_at='2026-10-26T20:01:00Z',q_grade=.9)
        legacy=dict(base,settled_at='2026-10-28T00:00:00Z')
        self.assertEqual(report.dedupe_props([post,late,legacy,early]),[early])
        self.assertEqual(report.dedupe_props([early,late,post,legacy]),[early])
        self.assertEqual(report.dedupe_props([post]),[])
        old=dict(base,settled_at='2026-10-27T00:00:00Z')
        self.assertEqual(report.dedupe_props([legacy,old]),[legacy])

if __name__=='__main__':unittest.main()
