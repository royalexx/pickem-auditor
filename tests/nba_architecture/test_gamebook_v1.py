from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from v2.nba_architecture.gamebook_v1 import read_final_box
from v2.nba_architecture.v2_contracts import ContractError

ROOT=Path(__file__).resolve().parents[2]/'docs/nba_architecture/substantive_remediation_20261117/source_search'

class OfficialGamebookTests(unittest.TestCase):
    def fixture(self):
        raw=(ROOT/'nba_pdf.raw').read_bytes();r=json.loads((ROOT/'nba_pdf.receipt.json').read_bytes())
        r['raw_sha256']=r['sha256'];return raw,r

    def test_actual_official_final_box_preserves_seconds_dnp_and_unknown_clocks(self):
        raw,r=self.fixture();x=read_final_box(raw,r)
        self.assertEqual(len(x['rows']),26);self.assertEqual(x['overtime_periods'],0)
        self.assertEqual(x['duration_minutes'],'48')
        wanamaker=next(p for p in x['rows'] if p['name']=='Brad Wanamaker')
        self.assertEqual(wanamaker['exact_seconds'],49);self.assertEqual(wanamaker['stats']['points'],2)
        self.assertEqual(sum(p['state']=='DNP' for p in x['rows']),2)
        self.assertIsNone(x['original_available_at']);self.assertIsNone(x['correction_history_complete'])
        self.assertEqual(x['source_admission'],'INDEPENDENT_REVIEW_REQUIRED')

    def test_tampered_pdf_hash_and_lookalike_host_reject(self):
        raw,r=self.fixture()
        with self.assertRaises(ContractError):read_final_box(raw+b'x',r)
        r['url']=r['url'].replace('statsdmz.nba.com','statsdmz.nba.com.evil.test')
        with self.assertRaises(ContractError):read_final_box(raw,r)

    def test_quarter_or_unparsed_player_cannot_silently_replace_full_game(self):
        raw,r=self.fixture();text=(ROOT/'nba_pdf.txt').read_text().split('\f')[0]
        for bad in (text.replace('FINAL BOX','2nd QUARTER ONLY'),text.replace('DNP - Coach\'s decision','UNRECOGNIZED')):
            with patch('v2.nba_architecture.gamebook_v1.subprocess.check_output',return_value=bad.encode()),self.assertRaises(ContractError):read_final_box(raw,r)

    def test_resealed_text_count_mutation_fails_physical_or_team_totals(self):
        raw,r=self.fixture();text=(ROOT/'nba_pdf.txt').read_text().split('\f')[0]
        # Source-derived table values must agree with the independently printed team totals.
        lines=text.splitlines();line=next(i for i,s in enumerate(lines) if 'Brad Wanamaker' in s)
        original=lines[line];lines[line]=original.rsplit('2',1)[0]+'3'
        with patch('v2.nba_architecture.gamebook_v1.subprocess.check_output',return_value='\n'.join(lines).encode()),self.assertRaises(ContractError):read_final_box(raw,r)

if __name__=='__main__':unittest.main()

class GameSpecificIdentityTests(unittest.TestCase):
    def build(self):
        from v2.nba_architecture.gamebook_identity_v1 import join_game_ids
        raw,r=OfficialGamebookTests().fixture();box=read_final_box(raw,r)
        eraw=(ROOT/'espn2018.raw').read_bytes();receipt=json.loads((ROOT/'espn2018.receipt.json').read_bytes())
        return join_game_ids,box,eraw,receipt

    def test_actual_26_game_only_identities_and_minute_precision_preserved(self):
        fn,box,raw,r=self.build();x=fn(box,raw,r)
        self.assertEqual(len(x['rows']),26);self.assertEqual(x['source_event_time'],'2018-10-17T00:00Z')
        self.assertFalse(x['future_roster_or_trade_evidence']);self.assertFalse(x['original_pregame_availability_proven'])

    def test_resealed_team_jersey_name_stats_dnp_collision_and_missing_reject(self):
        fn,box,raw,r=self.build()
        for attack in ('team','jersey','name','stats','dnp','collision','missing'):
            x=json.loads(raw);team=x['boxscore']['players'][0];people=team['statistics'][0]['athletes']
            if attack=='team':team['team']['abbreviation']='BOS'
            elif attack=='jersey':people[0]['athlete']['jersey']='999'
            elif attack=='name':people[0]['athlete']['displayName']='Other Person'
            elif attack=='stats':people[0]['stats'][1]='999'
            elif attack=='dnp':people[0]['didNotPlay']=True
            elif attack=='collision':people[1]['athlete']['id']=people[0]['athlete']['id']
            elif attack=='missing':people.pop()
            changed=json.dumps(x).encode();receipt=deepcopy(r);receipt['raw_sha256']=hashlib.sha256(changed).hexdigest()
            with self.subTest(attack=attack),self.assertRaises(ContractError):fn(box,changed,receipt)
