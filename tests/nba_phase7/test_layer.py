import copy
import unittest
from research.nba_phase7.participation import participation_layer

class LayerTests(unittest.TestCase):
    def roster(self):return {'input_freeze_at':'2026-11-16T23:30:00Z','game':{'game_id':'espn:game:1','event_start_at':'2026-11-17T00:00:00Z'},'players':[{'player_id':'espn:player:1','team_id':'espn:team:1','eligibility':None}],'coverage':{'complete_game_day_universe':False}}
    def row(self,status='Out'):
        return {'player_id':'espn:player:1','team_id':'espn:team:1','status':status,'date':'11/16/2026','time':'07:00 (ET)','matchup':'A@B','retrieved_at':'2026-11-16T23:20:00Z','published_at_claim':'2026-11-16T23:00:00Z','evidence_kind':'original_source_identity_bridge','identity_evidence':{'valid_from':'2026-11-16T23:20:00Z','valid_until':'2026-11-17T23:20:00Z'}}
    def runlayer(self,rows):return participation_layer(self.roster(),{'resolved':rows},game_abbreviations=['A','B'])
    def test_available_never_means_probability_one(self):
        r=self.runlayer([self.row('Available')]);self.assertIsNone(r['rows'][0]['P0_probability'])
    def test_verified_out_exclusion_keeps_eligibility_unknown(self):
        r=self.runlayer([self.row()]);self.assertEqual(r['rows'][0]['P0_probability'],0);self.assertIsNone(r['rows'][0]['eligibility'])
    def test_late_injury_rejected(self):
        row=self.row();row['retrieved_at']='2026-11-16T23:31:00Z';r=self.runlayer([row]);self.assertIsNone(r['rows'][0]['P0_probability']);self.assertEqual(len(r['rows'][0]['rejected_availability']),1)
    def test_conflicting_status_blocks(self):
        r=self.runlayer([self.row(),self.row('Available')]);self.assertIsNone(r['rows'][0]['P0_probability']);self.assertEqual(r['rows'][0]['availability'],'conflicting')
    def test_wrong_game_not_inactive_input(self):
        row=self.row();row['matchup']='C@B';r=self.runlayer([row]);self.assertIsNone(r['rows'][0]['P0_probability'])
    def test_fixture_cannot_support_real_exclusion(self):
        row=self.row();row['evidence_kind']='fixture';r=self.runlayer([row]);self.assertIsNone(r['rows'][0]['P0_probability'])
