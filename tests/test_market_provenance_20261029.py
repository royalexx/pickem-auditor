import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from jobs import matchup_label,venue_index_from_quotes
from market_coverage_audit import audit

class MarketProvenanceTests(unittest.TestCase):
    def test_canonical_venue_orientation(self):
        q={'sport':'NHL','team':'COL','opponent':'NJD','event_teams':['COL','NJD']}
        idx=venue_index_from_quotes([q])
        self.assertEqual(idx[('NHL','col','njd')],('COL','NJD'))
        self.assertEqual(matchup_label('COL','NJD',home_team='COL',away_team='NJD'),'NJD @ COL')
        self.assertEqual(matchup_label('COL','NJD'),'COL vs NJD')
        self.assertEqual(venue_index_from_quotes([q,{**q,'event_teams':['NJD','COL']}]),{})

    def test_missing_blocks_is_raw_source_coverage_not_parser_failure(self):
        inventory={'NHL':{'pregame_event_count':4,'raw_bookmaker_market_counts':{'player_shots_on_goal':300}}}
        report=audit([],[],raw_inventory=inventory)
        rows={r['stat']:r for r in report['market_rows'] if r['sport']=='NHL'}
        self.assertEqual(rows['blocked shots']['status'],'raw_market_missing_from_provider_payload')
        self.assertEqual(rows['hits']['status'],'provider_unsupported_no_live_hits_in_propline')
        self.assertIn('blocked shots',{r['stat'] for r in report['nhl_missing_market_diagnosis']})
        self.assertFalse(any(r['sport']=='NFL' for r in report['absent_supported']))

if __name__=='__main__':
    unittest.main()
