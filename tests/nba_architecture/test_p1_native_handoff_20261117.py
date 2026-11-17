"""Native P1 engineering transport; every fixture here is synthetic."""
import base64
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from tests.nba_architecture.test_p1_remediation import (
    official_fixture, nba_entry, repair_opponent, context_fixture, NBA_GAME,
    NBA_TEAMS,
)
from v2.nba_architecture.v2_contracts import canonical, digest
from v2.nba_architecture import p1_handoff as h


class NativeHandoff(unittest.TestCase):
    def prior(self, bundle=None, minutes=26):
        return h.export_prior_game(json.loads(repair_opponent(nba_entry(minutes))['record']['payload']),
            bundle or official_fixture(minutes=minutes), ingested_at='2026-11-16T19:00:00Z',
            source_profile='synthetic_engineering')

    def test_prior_exact_raw_not_parsed_hash_and_null_authentication(self):
        b=official_fixture(); p=self.prior(b)
        self.assertEqual(p['schema'],h.VERSION)
        self.assertEqual(base64.b64decode(p['evidence_bundle']['raw_base64']),b['raw'])
        self.assertEqual(p['exposure']['raw_sha256'],hashlib.sha256(b['raw']).hexdigest())
        self.assertEqual(p['admission_status'],'BLOCKED')
        self.assertIsNone(p['clocks']['first_defensible_available_at'])
        self.assertIsNone(p['clocks']['outcome_available_at'])
        self.assertIsNone(p['role']); self.assertIsNone(p['role_evidence'])
        self.assertEqual(p['profile'],'synthetic_engineering')
        self.assertEqual(p['candidate_denominator'],{'attempted':1,'admitted':0,'quarantined':1})

    def test_prior_subminute_keeps_display_separate(self):
        p=self.prior(official_fixture(minutes=0,exact='PT00M12.00S'),0)
        self.assertEqual(p['exposure']['displayed_minutes'],0)
        self.assertEqual(p['exposure']['exact_minutes'],.2)
        self.assertEqual(p['exposure']['stats']['points'],11)

    def test_transport_rejects_corrupt_raw_and_ancestor(self):
        old=official_fixture(); new=official_fixture(2,56)
        new['capture'].update(revision=2,supersedes_receipt_sha256=digest(old['capture']),retrieved_at='2026-11-16T18:30:00Z')
        new['prior']=[old]
        p=self.prior(new,56); self.assertEqual(len(h.decode_evidence_bundle(p['evidence_bundle'])['prior']),1)
        for ancestor in (False,True):
            bad=copy.deepcopy(p['evidence_bundle']); node=bad['prior'][0] if ancestor else bad
            node['raw_base64']=base64.b64encode(b'corrupt').decode()
            with self.subTest(ancestor=ancestor),self.assertRaisesRegex(ValueError,'OFFICIAL_SOURCE_SHA_MISMATCH'):
                h.decode_evidence_bundle(bad)

    def test_transport_rejects_orphan_backdated_wrong_identity(self):
        for mutation in ('orphan','clock','game'):
            b=official_fixture()
            if mutation=='orphan': b['capture']['revision']=2
            if mutation=='clock': b['capture']['retrieved_at']='2022-10-21T22:00:00Z'
            if mutation=='game': b['capture']['url']=b['capture']['url'].replace('0022200001','0022200002')
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.prior(b)

    def test_prior_ingestion_cannot_predate_retrieval(self):
        data=json.loads(repair_opponent(nba_entry())['record']['payload'])
        with self.assertRaisesRegex(ValueError,'HANDOFF_INGESTION_BEFORE_RETRIEVAL'):
            h.export_prior_game(data,official_fixture(),ingested_at='2026-11-16T17:00:00Z')

    def test_context_partial_candidates_never_complete_or_fitted(self):
        row=dict(kind='pregame_roster',game_id='nba:game:target',player_id='nba:player:7',team_id=NBA_TEAMS[0],effective_at='2023-02-09T10:00:00Z',legal_eligibility=None,availability='unknown')
        p=h.export_pregame_context(game_id='nba:game:target',team_ids=NBA_TEAMS,event_start_at='2023-02-10T01:00:00Z',input_freeze_at='2023-02-09T23:00:00Z',bundles=[context_fixture([row])],ingested_at='2023-02-09T23:00:00Z')
        self.assertEqual(p['admission_status'],'BLOCKED')
        self.assertEqual(p['roster_completeness']['status'],'UNPROVEN')
        self.assertIsNone(p['home_team_id'])
        player=p['players'][0]
        for field in ('participation_probability','role','membership'):
            self.assertIsNone(player[field])
        self.assertIsNone(player['legal_eligibility']);self.assertEqual(player['observed_availability'],'unknown')

    def test_missing_context_preserves_empty_denominator(self):
        p=h.export_pregame_context(game_id='nba:game:target',team_ids=NBA_TEAMS,event_start_at='2023-02-10T01:00:00Z',input_freeze_at='2023-02-09T23:00:00Z',bundles=[],ingested_at='2023-02-09T23:00:00Z')
        self.assertEqual(p['players'],[])
        self.assertEqual(p['candidate_denominator']['observed_candidates'],0)
        self.assertIsNone(p['candidate_denominator']['complete_population'])

    def test_missing_outcome_explicit_unresolved(self):
        from v2.nba_architecture.p1_vault import OfficialOutcomeVault
        with tempfile.TemporaryDirectory() as td:
            p=h.export_outcome(OfficialOutcomeVault(td),NBA_GAME,'nba:player:7')
        self.assertEqual(p['participation'],'UNRESOLVED');self.assertEqual(p['revisions'],[])
        self.assertEqual(p['stats'],{});self.assertIsNone(p['official_count'])
        for key in ('event_start_at','event_end_at','outcome_released_at'):
            self.assertIsNone(p[key])

    def test_outcome_all_versions_and_exact_raw_immutable(self):
        from v2.nba_architecture.p1_vault import OfficialOutcomeVault
        with tempfile.TemporaryDirectory() as td:
            v=OfficialOutcomeVault(td); b=official_fixture()
            args=dict(game_id=NBA_GAME,player_id='nba:player:7',team_id=NBA_TEAMS[0],state='PLAYED',minutes=26,stats={'points':11,'rebounds':5,'assists':3,'threes':2},source_id='nba:official:box',source_bytes=b['raw'],official_status='FINAL',official_game_evidence=b)
            first=v.append(**args,observed_at='2026-11-16T19:00:00Z')
            v.append(**args,observed_at='2026-11-16T20:00:00Z',revision=2,supersedes_sha256=first['content_hash'])
            before={str(x):x.read_bytes() for x in Path(td).rglob('*') if x.is_file()}
            p=h.export_outcome(v,NBA_GAME,'nba:player:7')
            after={str(x):x.read_bytes() for x in Path(td).rglob('*') if x.is_file()}
            self.assertEqual(before,after);self.assertEqual(len(p['revisions']),2)
            self.assertEqual(p['revisions'][1]['record']['supersedes_sha256'],first['content_hash'])
            self.assertEqual(base64.b64decode(p['revisions'][0]['source_raw_base64']),b['raw'])
            self.assertIsNone(p['outcome_released_at']);self.assertEqual(p['admission_status'],'BLOCKED')

    def test_pregame_does_not_import_or_open_vault(self):
        import ast
        tree=ast.parse(Path('v2/nba_architecture/p1_handoff.py').read_text())
        # Outcome reader is injected, never imported or opened by this module.
        imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
        self.assertTrue(all(not n or 'vault' not in n for n in imports))
