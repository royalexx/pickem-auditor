"""Actual installed public admission, no mocked trust root."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from v2.nba_architecture.p1_listed_source_v1 import read_listed_population, ROOT
from v2.nba_architecture.v2_contracts import ContractError

S = ROOT/'docs/nba_architecture/substantive_remediation_20261117/source_search'


def inputs():
    pdf = (S/'nba_pdf.raw').read_bytes()
    pr = json.loads((S/'nba_pdf.receipt.json').read_bytes()); pr['raw_sha256'] = pr['sha256']
    return [pdf, pr, (S/'espn2018.raw').read_bytes(), json.loads((S/'espn2018.receipt.json').read_bytes())]


class PublicListedTests(unittest.TestCase):
    def test_real_handoff_all_states_and_unknowns(self):
        x = read_listed_population(*inputs())
        self.assertEqual(len(x['rows']), 26)
        self.assertEqual(sum(r['state'] == 'DNP' for r in x['rows']), 2)
        self.assertEqual(x['duration_minutes'], '48')
        self.assertEqual(x['overtime_periods'], 0)
        for key in ('target_eligible_roster_count', 'source_published_at', 'original_pregame_available_at', 'correction_history_complete', 'ingested_at'):
            self.assertIsNone(x[key])
        self.assertTrue(all(r['genuine_participation_probability'] is None for r in x['rows']))

    def test_changed_raw_and_resealed_population_attacks(self):
        for attack in ('missing','duplicate','team','game','bytes'):
            args=inputs(); obj=json.loads(args[2]); team=obj['boxscore']['players'][0]; people=team['statistics'][0]['athletes']
            if attack=='missing': people.pop()
            if attack=='duplicate': people.append(deepcopy(people[0]))
            if attack=='team': team['team']['id']='2'
            if attack=='game': obj['header']['id']='401070219'
            args[2]=json.dumps(obj).encode() if attack!='bytes' else args[2]+b' '
            args[3]['raw_sha256']=hashlib.sha256(args[2]).hexdigest()
            with self.subTest(attack=attack),self.assertRaises(ContractError): read_listed_population(*args)

    def test_false_receipt_claims_and_capabilities(self):
        for key,value in [('retrieved_at','2018-10-16T00:00:00Z'),('source_published_at','2018-10-16T00:00:00Z'),('correction_history_complete',True),('predecessor_sha256','f'*64),('approved',True),('reviewer','independent'),('eligible_roster_complete',True)]:
            args=inputs();args[3][key]=value
            with self.subTest(key=key),self.assertRaises(ContractError): read_listed_population(*args)
        for capability in ['PREGAME_ROSTER','COMPLETE_CORRECTIONS','FITTED_MODEL']:
            with self.assertRaises(ContractError): read_listed_population(*inputs(),required_capability=capability)

    def test_late_capture_and_altered_pdf(self):
        with self.assertRaisesRegex(ContractError,'LATE_CAPTURE'):
            read_listed_population(*inputs(),input_freeze_at='2018-10-19T23:45:00Z')
        args=inputs();args[0]+=b'x'
        with self.assertRaises(ContractError):read_listed_population(*args)
