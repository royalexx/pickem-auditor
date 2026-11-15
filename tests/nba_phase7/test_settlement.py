import json
from pathlib import Path
import unittest
from v2.nba_ws1.store import Receipt
from v2.nba_ws1.capture import BASE
from research.nba_phase7.settlement import settle_original,market_settlement

class SettlementTests(unittest.TestCase):
    def observation(self,participation='played'):
        return {'game_id':'espn:game:1','player_id':'espn:player:1','team_id':'espn:team:1','participation':participation,'stats':{'points':10}}
    def contract(self):
        return {'game_id':'espn:game:1','player_id':'espn:player:1','team_id':'espn:team:1','stat':'points','period':'full_game_including_overtime','line':10,'payout_terms':{'dnp':'void'}}
    def test_explicit_DNP_is_void_not_under_or_push(self):self.assertEqual(market_settlement(self.contract(),self.observation('dnp')),'void')
    def test_missing_DNP_terms_block(self):
        c=self.contract();c['payout_terms']={}
        with self.assertRaisesRegex(ValueError,'DNP_SETTLEMENT_TERMS_UNAVAILABLE'):market_settlement(c,self.observation('dnp'))
    def test_original_contract_mismatch_block(self):
        c=self.contract();c['player_id']='espn:player:2'
        with self.assertRaisesRegex(ValueError,'ORIGINAL_CONTRACT_IDENTITY_MISMATCH'):market_settlement(c,self.observation())
    def test_push_requires_played_outcome(self):self.assertEqual(market_settlement(self.contract(),self.observation()),'push')
    def test_unknown_status_not_scored(self):
        with self.assertRaisesRegex(ValueError,'PARTICIPATION_UNRESOLVED'):market_settlement(self.contract(),self.observation('unknown'))
    def test_official_final_independent_parser(self):
        from research.nba_joint_v01.data import box
        from v2.nba_ws1.adapters import espn_boxscore_records
        path=Path('work/joint_input/raw/401704643.json')
        if path.exists():raw=path.read_bytes()
        else:
            import gzip
            raw=gzip.decompress(Path('research/nba_joint_v01/inputs/official/401704643.json.gz').read_bytes())
        d=json.loads(raw);comp=d['header']['competitions'][0];ids={c['homeAway']:'espn:team:'+str(c['team']['id']) for c in comp['competitors']}
        game={'game_id':'espn:game:401704643','home_team_id':ids['home'],'away_team_id':ids['away'],'event_start_at':comp['date']}
        r=Receipt.capture(raw,source=BASE+'/summary?event=401704643',observed_at='2026-11-15T22:40:00Z',origin='fixture')
        records=espn_boxscore_records(d,r);p=records[0].data
        ledger={'game':game,'input_freeze_at':'2024-10-25T00:00:00Z','participation':{'rows':[{'player_id':p['player_id'],'team_id':p['team_id'],'eligibility':None,'P0_probability':None}]}}
        out=settle_original(ledger,raw,r);self.assertEqual(len(out['candidate_rows']),1);self.assertEqual(out['denominator']['participation_scored'],0)
        self.assertEqual(out['source_receipt']['origin'],'fixture')
        ledger['input_freeze_at']='2026-11-15T22:00:00Z'
        with self.assertRaisesRegex(ValueError,'RETROSPECTIVE_CAPTURE_NOT_ORIGINAL'):settle_original(ledger,raw,r)
