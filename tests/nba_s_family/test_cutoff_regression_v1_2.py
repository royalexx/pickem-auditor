"""F-P2-02 paired controls; synthetic histories only, old probes unchanged."""
import copy
import unittest
from tests.nba_s_family.test_statistical import histories, manifest, pregame, opportunity_fixture
from v2.nba_architecture.v2_contracts import seal
from v2.nba_s_family import fit, predict, SFError
from v2.nba_s_family.integration import joint_conditional


class DeclaredCutoffTests(unittest.TestCase):
    def pair(self, fitted_cutoff, declared='2022-10-10T00:00:00Z', stat='points', family='S1'):
        p=pregame();p['training_cutoff_at']=declared
        p=seal({k:v for k,v in p.items() if k!='content_hash'})
        g,o=opportunity_fixture(p)
        f=fit(histories(stat),asof_cutoff_utc=fitted_cutoff,source_manifest=manifest(),stat=stat,family=family)
        prediction=predict(f,frozen_pregame=p,target_player_id='espn:player:10',role='wing',opportunity=o,game_state=g)
        args=dict(pregame=p,game_state=g,opportunity=o,scenario_id=o['scenarios'][0]['scenario_id'],player_id='espn:player:10',team_id='espn:team:1',role='wing')
        return prediction,lambda:joint_conditional(f,**args)

    def test_model_before_declared_cutoff(self):
        r,conditional=self.pair('2022-10-09T23:59:59.999999Z')
        self.assertIsNone(r.abstain_reason);self.assertTrue(conditional()['pmf'])

    def test_exact_cutoff_equality_all_pts_reb_ast_3pm_count_laws(self):
        for stat in ('points','rebounds','assists','threes'):
            for family in ('S1','S2'):
                with self.subTest(stat=stat,family=family):
                    r,conditional=self.pair('2022-10-10T00:00:00Z',stat=stat,family=family)
                    self.assertIsNone(r.abstain_reason,r.abstain_reason)
                    self.assertEqual(conditional()['stat'],stat)

    def test_one_microsecond_after_declared_cutoff_consistent_rejection(self):
        r,conditional=self.pair('2022-10-10T00:00:00.000001Z')
        self.assertEqual(r.abstain_reason,'MODEL_AFTER_DATA_CUTOFF')
        with self.assertRaisesRegex(SFError,'MODEL_AFTER_DATA_CUTOFF'):conditional()

    def test_before_freeze_after_declared_cutoff_consistent_rejection(self):
        r,conditional=self.pair('2022-10-11T00:00:00Z')
        self.assertEqual(r.abstain_reason,'MODEL_AFTER_DATA_CUTOFF')
        with self.assertRaisesRegex(SFError,'MODEL_AFTER_DATA_CUTOFF'):conditional()

    def test_postfreeze_still_rejects_with_existing_reason(self):
        r,conditional=self.pair('2022-10-20T00:00:00Z')
        self.assertEqual(r.abstain_reason,'MODEL_FIT_AFTER_FREEZE')
        with self.assertRaisesRegex(SFError,'MODEL_FIT_AFTER_FREEZE'):conditional()

if __name__=='__main__':unittest.main()
