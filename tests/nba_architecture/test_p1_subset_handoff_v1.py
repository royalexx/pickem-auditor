from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from v2.nba_architecture.p1_subset_handoff_v1 import export_requests,read_requests,conditional_requests,canonical,digest
from tests.nba_architecture.test_research_profile_v1 import CAP,COHORT

class HandoffTests(unittest.TestCase):
    def test_real_source_to_serialized_consumer(self):
        value=export_requests(CAP,COHORT);raw=canonical(value)
        self.assertEqual(read_requests(raw,CAP,COHORT),value)
        consumed=conditional_requests(raw,CAP,COHORT)
        self.assertEqual((consumed['candidate_denominator'],len(consumed['requests']),consumed['source_abstentions']),(36,26,10))
        self.assertEqual(consumed['forecasted_rows'],0)
        self.assertFalse(consumed['actual_model_consumer_executed'])

    def test_resealed_claims_identities_and_numerics_cannot_change_source(self):
        value=export_requests(CAP,COHORT)
        for attack in ('q','eligibility','forecast','identity','conditioning','drop','approve','model'):
            x=deepcopy(value)
            if attack=='q':x['requests']['rows'][0]['genuine_participation_probability']=1
            if attack=='eligibility':x['requests']['rows'][0]['legal_eligibility']=True
            if attack=='forecast':x['forecasted_rows']=1
            if attack=='identity':x['requests']['rows'][0]['player_id']='espn:player:999'
            if attack=='conditioning':x['requests']['rows'][0]['conditioning']='unconditional'
            if attack=='drop':x['requests']['rows'].pop()
            if attack=='approve':x['approved']=True
            if attack=='model':x['model_attached']=True
            del x['payload_sha256'];x['payload_sha256']=digest(canonical(x))
            with self.subTest(attack=attack),self.assertRaises(ValueError):read_requests(canonical(x),CAP,COHORT)

    def test_changed_receipt_and_body_detected_even_if_other_rows_stay_valid(self):
        raw=canonical(export_requests(CAP,COHORT))
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'capture';shutil.copytree(CAP,p);f=p/'roster-5/body.raw';f.write_bytes(f.read_bytes()+b' ')
            with self.assertRaises(ValueError):read_requests(raw,p,COHORT)
        with self.assertRaises(ValueError):read_requests(b'{"a":1,"a":2}',CAP,COHORT)
