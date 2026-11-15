import copy
import gzip
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import numpy as np
from v2.nba_ws1 import NBAPregameFeatureSnapshot
from v2.nba_ws1.adapters import espn_injury_records, espn_roster_records
from v2.nba_ws1.store import Receipt
from v2.nba_joint import simulate,synthetic_fixture,extract_forecast,audit
from v2.nba_joint.common import sha
from research.nba_phase6.run import project, require_complete_oracle
from research.nba_phase6.roster import build_roster_contract

class AdversarialTests(unittest.TestCase):
    def test_partial_oracle_cannot_credit_missing_player_opportunity(self):
        game={'players':[{'player_id':str(i),'team_id':'A'} for i in range(5)]}
        actual={str(i):{'player_id':str(i),'team':'A'} for i in range(6)}
        with self.assertRaisesRegex(ValueError,'ORACLE_MISSING_PARTICIPANT_LAW'):require_complete_oracle(game,actual)
    def test_wrong_team_does_not_complete_oracle(self):
        game={'players':[{'player_id':'1','team_id':'A'}]}
        with self.assertRaisesRegex(ValueError,'ORACLE_MISSING_PARTICIPANT_LAW'):require_complete_oracle(game,{'1':{'player_id':'1','team':'B'}})
    def test_original_bytes_tamper(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/'capture';shutil.copytree('research/nba_joint_v01/prospective_canary',folder)
            record=json.loads((folder/'capture_receipt.json').read_text())['sources'][0]
            (folder/record['path']).write_bytes(gzip.compress(b'{}',mtime=0))
            m=json.loads(Path('research/nba_joint_v01/results/model.json').read_text())
            with self.assertRaisesRegex(ValueError,'SOURCE_HASH_MISMATCH'):build_roster_contract(folder,m)
    def test_future_injury_announcement(self):
        raw={'injuries':[{'team':{'id':'1'},'injuries':[{'date':'2026-11-17T00:00:00Z','athlete':{'id':'1'},'status':'Out'}]}]}
        r=Receipt.capture(json.dumps(raw).encode(),source='https://site.api.espn.com/summary',observed_at='2026-11-15T20:00:00Z',origin='fixture')
        with self.assertRaisesRegex(ValueError,'FUTURE_INJURY_REPORT'):espn_injury_records(raw,r,game_id='espn:game:1')
    def test_wrong_team_identity(self):
        r=Receipt.capture(b'{}',source='https://site.api.espn.com/roster',observed_at='2026-11-15T20:00:00Z',origin='fixture')
        with self.assertRaisesRegex(ValueError,'ROSTER_TEAM_MISMATCH'):
            espn_roster_records({'team':{'id':'1'},'athletes':[]},r,game_id='espn:game:1',team_id='espn:team:2')
    def test_postfreeze_roster_change(self):
        folder=Path('research/nba_joint_v01/prospective_canary');receipt=json.loads((folder/'capture_receipt.json').read_text())
        snapshot=NBAPregameFeatureSnapshot.from_json((folder/receipt['snapshot_path']).read_text())
        data=snapshot.to_dict();data['players'][0]['team_id']='espn:team:999'
        h=data.pop('content_hash');data['content_hash']=sha(data)
        with self.assertRaisesRegex(ValueError,'SNAPSHOT_DERIVATION_MISMATCH'):NBAPregameFeatureSnapshot.from_json(json.dumps(data))
    def test_underfilled_oracle_abstains(self):
        mask=np.array([True]*4+[False]*4)
        with self.assertRaisesRegex(ValueError,'ORACLE_FEWER_THAN_FIVE_SUPPORTED_PARTICIPANTS'):
            project(np.ones((2,8)),np.array([48.,53.]),[list(range(8))],mask=mask)
    def test_unresolved_pool_conserves_without_fake_players(self):
        raw=np.full((2,8),30.);duration=np.array([48.,53.])
        for reserve in (24,48):
            m=project(raw,duration,[list(range(8))],reserve_per48=reserve)
            self.assertEqual(m.shape,raw.shape)
            np.testing.assert_allclose(m.sum(axis=1)+reserve*duration/48,5*duration,atol=1e-7)
            self.assertFalse(np.allclose(m.sum(axis=1),5*duration))
    def test_inactive_player_cannot_receive_injected_minutes(self):
        g,m=synthetic_fixture();a=simulate(g,m,n=4);g['players'][0]['eligible']=False
        plan=dict(kind='raw_m0_diagnostic',minutes=a['independent_minutes'],raw_minutes=a['independent_minutes'],parent_input_sha256=sha(g))
        with self.assertRaisesRegex(ValueError,'RESEARCH_INACTIVE_EXPOSURE'):simulate(g,m,n=4,research_minutes=plan)
    def test_oracle_exports_blocked_and_rotation_audited(self):
        g,m=synthetic_fixture();a=simulate(g,m,n=4)
        plan=dict(kind='postgame_appearance_oracle',minutes=a['minutes'],raw_minutes=a['independent_minutes'],parent_input_sha256=sha(g))
        o=simulate(g,m,n=4,research_minutes=plan);self.assertEqual(audit(o)['violations'],0)
        with self.assertRaisesRegex(ValueError,'DIAGNOSTIC_NOT_FORECAST'):extract_forecast(o,0,'pra',line=20.5)
    def test_overtime_mismatch_fails_closed(self):
        g,m=synthetic_fixture();a=simulate(g,m,n=4)
        plan=dict(kind='postgame_appearance_oracle',minutes=a['minutes']*1.01,raw_minutes=a['independent_minutes'],parent_input_sha256=sha(g))
        with self.assertRaisesRegex(ValueError,'INVALID_TEAM_MINUTES'):simulate(g,m,n=4,research_minutes=plan)
    def test_event_parameters_never_tuned_by_project(self):
        g,m=synthetic_fixture();h=sha(m);a=simulate(g,m,n=4)
        project(a['independent_minutes'],a['state']['duration'],a['team_indices'])
        self.assertEqual(sha(m),h)
