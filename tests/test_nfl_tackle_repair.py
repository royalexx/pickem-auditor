import sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts')]
import unittest
from nfl_sunday_market_extension import value
from nfl_sunday_feature_store import count_stat
from nfl_stat_definitions import combined_tackles_assists
FIELDS=('def_tackles_solo','def_tackles_with_assist','def_tackle_assists')
CASES= [([4,3,2],9),([0,0,0],0),([None,3,2],None),([4,None,2],None),([4,3,None],None),([-1,3,2],None),([4.5,3,2],None),([float('inf'),3,2],None),(['bad',3,2],None),([True,3,2],None)]
def check(parts,expected):
    r=dict(zip(FIELDS,parts))
    assert combined_tackles_assists(r)==expected
    assert value(r,'tackles_assists')==expected
    assert count_stat(r,'tackles + assists')==expected

class RepairTests(unittest.TestCase):
    def test_components(self):
        for parts,expected in CASES:
            with self.subTest(parts=parts): check(parts,expected)

class SnapAndProbabilityTests(unittest.TestCase):
    def test_snap_identity_units_and_duplicates(self):
        from nfl_tackle_repair import snap_crosswalk
        players=[{'pfr_id':'a','gsis_id':'00-0000001'}]
        game={'game_id':'G','home_team':'A','away_team':'B','gameday':'2026-11-01','season':'2026','week':'9','result':'0'}
        snap={'pfr_player_id':'a','game_id':'G','team':'A','defense_snaps':'12','st_snaps':'20','defense_pct':'0.2'}
        receipt={'observed_received_at':'2026-11-14T00:00:00Z','sha256':'a'*64}
        rows,rejects=snap_crosswalk(players,[snap,snap],[game],receipt,'2026-11-15T00:00:00Z')
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['defensive_snaps'],12)
        self.assertEqual(rows[0]['special_teams_snaps_raw'],'20')
        self.assertEqual(rejects[0]['reason'],'IDENTICAL_DUPLICATE_NOT_COUNTED')
        rows,_=snap_crosswalk(players,[{**snap,'team':'C'}],[game],receipt,'2026-11-15T00:00:00Z');self.assertFalse(rows)
        rows,_=snap_crosswalk(players,[snap],[{**game,'gameday':'2026-11-15'}],receipt,'2026-11-15T00:00:00Z');self.assertFalse(rows)
        rows,_=snap_crosswalk(players,[snap],[game],{**receipt,'observed_received_at':'2026-11-16T00:00:00Z'},'2026-11-15T00:00:00Z');self.assertFalse(rows)
    def test_push_and_missing_snaps_baseline(self):
        from v2.nfl_marginal_shadow import fit_laws, MODEL_IDS
        laws,_,_=fit_laws([4,3,9],[[2,4,6]]*6,stat='tackles + assists')
        law=laws[MODEL_IDS[3]]
        for line in (5,5.5):
            p=law.probabilities(line)
            self.assertAlmostEqual(p.over+p.under+p.push,1)
            self.assertGreater(p.push,0) if line==5 else self.assertEqual(p.push,0)
    def test_o4_requires_exposure_and_accepts_overlap(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research/nfl_opportunity_20261115'))
        import models as m
        with self.assertRaisesRegex(ValueError,'insufficient_defensive_history'):m.defensive_parameters([],{},[],'LB')
        h={'game_id':'G','team':'A','position':'LB','state':'played','snaps':10,'solo':7,'with_assist':4,'tackle_assists':2}
        ts={('G','A'):{'opponent':'B'},('G','B'):{'plays':10}}
        par=m.defensive_parameters([h]*3,ts,[h],'LB')
        self.assertGreater(par['rate_alpha']/par['rate_beta'],1)
    def test_joint_uses_shared_opponent_draw(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reports/nfl_20261115_prospective/joint_models'))
        import joint_simulator as j
        import numpy as np
        par={'snap_alpha':10,'snap_beta':2,'rate_alpha':10,'rate_beta':40}
        event={'teams':[{'team_id':t,'plays_mean':60,'pass_rate':.55,'sack_rate':.05,'players':[{'player_id':t+'1','role':'DEFENDER','participation':1,'snap_share':.8,'verified_defensive_parameters':par}]} for t in ('A','B')]}
        for model in ('J1','J2','J3'):
            out,st=j.game_once(event,np.random.default_rng(20261115),model,'neutral')
            self.assertEqual(st['A']['defense']['A1']['opponent_plays'],st['B']['plays'])
            self.assertGreaterEqual(out['A1','tackles_assists'],0)

class AuditAdversarialTests(unittest.TestCase):
    def test_malformed_probability_and_nan(self):
        from nfl_tackle_repair_audit import probabilities
        for p in ([.6,.6,0],[float('nan'),.4,.6],[-.1,.5,.6]):
            with self.assertRaises(AssertionError):probabilities(p)
    def test_current_game_history_rejected_by_o4(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research/nfl_opportunity_20261115'))
        import models as m
        with self.assertRaisesRegex(ValueError,'future_defensive_history'):
            m.OpportunityModel.from_defensive_history({},[{'end_at':'2026-11-15T23:59:59Z'}],'2026-11-15T17:00:00Z')
    def test_immutable_source_receipt(self):
        from tempfile import TemporaryDirectory
        from nfl_sunday_feature_store import unchanged
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'frozen';unchanged(p,b'original')
            with self.assertRaises(ValueError):unchanged(p,b'replacement')
            self.assertEqual(p.read_bytes(),b'original')
