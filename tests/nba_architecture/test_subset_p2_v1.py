import copy
import json
import unittest
from pathlib import Path

from tests.nba_architecture.test_research_profile_v1 import CAP, COHORT
from tests.nba_s_family.test_statistical import histories, manifest, CUTOFF
from v2.nba_s_family import fit, FittedS
from v2.nba_architecture.p1_subset_handoff_v1 import canonical, digest, export_requests
from v2.nba_architecture.subset_p2_v1 import run_p2, read_p2, native_s_control


class P2SubsetTests(unittest.TestCase):
    def test_actual_public_handoff_retains_all_player_stat_attempts(self):
        raw=canonical(export_requests(CAP, COHORT))
        result=run_p2(raw,CAP,COHORT)
        self.assertEqual((result['candidate_denominator'],result['attempt_denominator']),(36,144))
        self.assertEqual(sum(r['reason']=='P1_SOURCE_ABSTENTION' for r in result['rows']),40)
        self.assertEqual(sum(r['reason']=='SAVED_S_ARTIFACT_UNAVAILABLE' for r in result['rows']),104)
        self.assertEqual(result['forecasted_rows'],0)
        self.assertEqual(read_p2(canonical(result),source_raw=raw,capture_dir=CAP,cohort=COHORT),result)

    def test_native_positive_and_model_byte_stat_exposure_negative_controls(self):
        # Synthetic control fitting only: no historical replacement or real output.
        fitted=fit(histories(),asof_cutoff_utc=CUTOFF,source_manifest=manifest(),stat='points')
        kwargs=dict(player_id='espn:player:10',role='wing',projected_exposure=30.,statistic='points')
        positive=native_s_control(fitted,**kwargs)
        self.assertIsNone(positive['abstain_reason']);self.assertFalse(positive['admitted'])
        self.assertTrue(positive['parameters']['support'])
        for mutation in ('stat','exposure','code','player'):
            f=fitted;k=kwargs.copy()
            if mutation=='stat':k['statistic']='rebounds'
            if mutation=='exposure':k['projected_exposure']=-1
            if mutation=='player':k['player_id']='espn:player:missing'
            if mutation=='code':
                d=f.data;d['code_sha256']='0'*64;f=FittedS(canonical(d))
            self.assertIsNotNone(native_s_control(f,**k)['abstain_reason'],mutation)

    def test_resealed_output_or_source_mutations_do_not_admit(self):
        source=export_requests(CAP,COHORT);raw=canonical(source)
        result=run_p2(raw,CAP,COHORT)
        for attack in ('approval','drop','forecast','identity'):
            x=copy.deepcopy(result)
            if attack=='approval':x['approved']=True
            if attack=='drop':x['rows'].pop()
            if attack=='forecast':x['rows'][0]['forecast']={'p0':1.}
            if attack=='identity':x['rows'][0]['team_id']='wrong'
            x.pop('payload_sha256');x['payload_sha256']=digest(canonical(x))
            with self.assertRaises(ValueError):read_p2(canonical(x),source_raw=raw,capture_dir=CAP,cohort=COHORT)
        source['requests']['rows'].pop()
        with self.assertRaises(ValueError):run_p2(canonical(source),CAP,COHORT)
