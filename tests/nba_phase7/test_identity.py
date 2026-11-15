import copy
import gzip
import json
from pathlib import Path
import unittest
from research.nba_phase7.fixtures import nba_bytes,espn_roster,receipt,AT
from research.nba_phase7.evidence import build_crosswalk,injury_pdf,resolve_injuries
from v2.nba_ws1.store import Receipt

class IdentityTests(unittest.TestCase):
    def inputs(self,espn=None):
        n=nba_bytes();e=json.dumps(espn or espn_roster()).encode()
        return n,receipt(n,'https://www.nba.com/team/1001/team1'),e,receipt(e,'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/1/roster')
    def test_name_DOB_team_bridge(self):
        r=build_crosswalk(*self.inputs(),freeze_at=AT);self.assertEqual(r['verified_identity_count'],6)
        self.assertIsNone(r['entries'][0]['eligibility'])
    def test_name_alone_is_insufficient(self):
        e=espn_roster();e['athletes'][0]['dateOfBirth']='2000-01-01T00:00Z'
        r=build_crosswalk(*self.inputs(e),freeze_at=AT);self.assertEqual(r['verified_identity_count'],5)
    def test_duplicate_identity_fails_closed(self):
        e=espn_roster();e['athletes'].append(e['athletes'][0])
        with self.assertRaisesRegex(ValueError,'CROSSWALK_ID_COLLISION'):build_crosswalk(*self.inputs(e),freeze_at=AT)
    def test_two_same_name_birthdates_ambiguous(self):
        e=espn_roster();e['athletes'].append({**e['athletes'][0],'id':'999'})
        r=build_crosswalk(*self.inputs(e),freeze_at=AT);self.assertEqual(r['verified_identity_count'],5)
    def test_wrong_team_rejected(self):
        e=espn_roster();e['team']['abbreviation']='WRONG'
        with self.assertRaisesRegex(ValueError,'CROSS_PROVIDER_TEAM_UNRESOLVED'):build_crosswalk(*self.inputs(e),freeze_at=AT)
    def test_future_mapping_rejected(self):
        with self.assertRaisesRegex(ValueError,'SOURCE_AFTER_FREEZE'):build_crosswalk(*self.inputs(),freeze_at='2026-11-16T23:24:00Z')
    def test_raw_source_tampering_rejected(self):
        n,r,e,er=self.inputs()
        with self.assertRaisesRegex(ValueError,'SOURCE_HASH_MISMATCH'):build_crosswalk(n+b' ',r,e,er,freeze_at=AT)
    def test_original_official_pdf_parse_and_preserve_unresolved(self):
        root=Path('research/nba_phase6/official_source_probe');meta=json.loads((root/'official_injury_pdf_receipt.json').read_text())
        raw=(root/meta['path']).read_bytes();r=Receipt(**meta['receipt']);p=injury_pdf(raw,r,freeze_at='2026-11-15T22:00:00Z')
        self.assertGreater(len(p['rows']),20);self.assertFalse(p['complete_active_roster'])
        a=resolve_injuries(p,[],freeze_at='2026-11-15T22:00:00Z');self.assertEqual(a['unresolved_count'],len(p['rows']));self.assertEqual(a['resolved_count'],0)
    def test_future_official_report_rejected(self):
        root=Path('research/nba_phase6/official_source_probe');meta=json.loads((root/'official_injury_pdf_receipt.json').read_text());raw=(root/meta['path']).read_bytes()
        r=Receipt.capture(raw,source=meta['receipt']['source'],observed_at='2026-11-15T20:00:00Z',origin='fixture')
        with self.assertRaisesRegex(ValueError,'FUTURE_INJURY_PUBLICATION'):injury_pdf(raw,r,freeze_at='2026-11-15T22:00:00Z')
    def test_raw_team_identity_overrides_old_narrative(self):
        root=Path('research/nba_phase6/current_source_probe');cap=json.loads((root/'capture_receipt.json').read_text());teams={}
        for source in cap['sources']:
            raw=json.loads(gzip.decompress((root/source['path']).read_bytes()))
            if 'athletes' in raw:teams[str(raw['team']['id'])]=raw['team']['abbreviation']
        self.assertEqual(teams['30'],'CHA');self.assertEqual(teams['12'],'LAC')
