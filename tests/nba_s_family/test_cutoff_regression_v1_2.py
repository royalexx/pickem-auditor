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

class ArtifactChronologyTests(unittest.TestCase):
    def test_resealed_late_training_release_rejected_by_both_interfaces(self):
        from tests.nba_s_family.test_statistical import CUTOFF
        from v2.nba_s_family.model import FittedS,canonical
        p=pregame();g,o=opportunity_fixture(p)
        f=fit(histories(),asof_cutoff_utc=CUTOFF,source_manifest=manifest(),stat='points')
        for field,value in [('outcome_available_at','2022-10-12T00:00:00Z'),('game_start_at',CUTOFF)]:
            with self.subTest(field=field):
                a=f.data;a['training_rows'][0][field]=value;bad=FittedS(canonical(a))
                r=predict(bad,frozen_pregame=p,target_player_id='espn:player:10',role='wing',opportunity=o,game_state=g)
                self.assertEqual(r.abstain_reason,'TRAINING_ROW_AFTER_MODEL_CUTOFF')
                with self.assertRaisesRegex(SFError,'TRAINING_ROW_AFTER_MODEL_CUTOFF'):
                    joint_conditional(bad,pregame=p,game_state=g,opportunity=o,scenario_id=o['scenarios'][0]['scenario_id'],player_id='espn:player:10',team_id='espn:team:1',role='wing')

    def test_model_release_cutoff_equality_remains_valid(self):
        rows=histories();m=manifest();cutoff='2022-10-07T00:00:00Z'
        rows[-1]['outcome_available_at']=cutoff
        f=fit(rows,asof_cutoff_utc=cutoff,source_manifest=m,stat='points')
        p=pregame();g,o=opportunity_fixture(p)
        r=predict(f,frozen_pregame=p,target_player_id='espn:player:10',role='wing',opportunity=o,game_state=g)
        self.assertIsNone(r.abstain_reason)
