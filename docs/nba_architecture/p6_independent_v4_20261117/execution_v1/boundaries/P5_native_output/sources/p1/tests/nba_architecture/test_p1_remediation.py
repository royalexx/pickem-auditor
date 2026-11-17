"""Permanent F-P1-01 regression; synthetic unless explicitly marked real."""
import tempfile
import unittest
from tests.nba_architecture.test_p1_history import make_entry, build
from tests.nba_architecture import test_p1_history as fixtures


class AccountingBoundary(unittest.TestCase):
    def test_zero_positive_requires_adjudication(self):
        with self.assertRaisesRegex(ValueError, 'ZERO_MINUTE_CREDIT_UNRESOLVED'):
            build([make_entry(minutes=0)])

    def test_900_requires_duration(self):
        with self.assertRaisesRegex(ValueError, 'GAME_DURATION_EVIDENCE_REQUIRED'):
            build([make_entry(minutes=900)])

    def test_vault_zero_positive_requires_adjudication(self):
        from v2.nba_architecture.p1_vault import OfficialOutcomeVault
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, 'ZERO_MINUTE_CREDIT_UNRESOLVED'):
                fixtures.P1VaultTest()._put(OfficialOutcomeVault(td),
                                 state='PLAYED_ZERO_MINUTES', minutes=0)

# Official-shaped JSON below is deliberately SYNTHETIC. It tests the adapter,
# never the authenticity of an NBA capture or an actual historic performance.
import copy
import hashlib
import json
from v2.nba_architecture.v2_contracts import canonical, digest
from v2.nba_architecture.p1_evidence import VERSION, duration, adjudicate_player

NBA_GAME = 'nba:game:0022200001'
NBA_TEAMS = ('nba:team:1', 'nba:team:2')


def official_fixture(ot=0, minutes=26, points=11, exact=None):
    raw = canonical(dict(game=dict(gameId='0022200001', gameStatus=3,
        period=4 + ot, gameClock='PT00M00.00S', gameTimeUTC='2022-10-21T23:00:00Z',
        homeTeam=dict(teamId=1, players=[dict(personId=7, played='1', statistics=dict(
            minutes=exact or f'PT{minutes}M00.00S', points=points,
            reboundsTotal=5, assists=3, threePointersMade=2))]),
        awayTeam=dict(teamId=2, players=[]))))
    capture = dict(schema=VERSION,
        url='https://cdn.nba.com/static/json/liveData/boxscore/boxscore_0022200001.json',
        raw_sha256=hashlib.sha256(raw).hexdigest(), retrieved_at='2026-11-16T18:00:00Z',
        revision=1, supersedes_receipt_sha256=None)
    return dict(capture=capture, raw=raw, prior=[])


def nba_entry(minutes=26, stats=None):
    return make_entry(game=NBA_GAME, player='nba:player:7', team=NBA_TEAMS[0], minutes=minutes, stats=stats)


def repair_opponent(e):
    d=json.loads(e['record']['payload']);d['opponent_id']=NBA_TEAMS[1]
    e['record']['payload']=canonical(d).decode()
    e['record']['record_id']=digest({k:v for k,v in e['record'].items() if k!='record_id'})
    return e


def official_build(e, bundle, **kwargs):
    return build([repair_opponent(e)], team_ids=NBA_TEAMS,
                 official_game_evidence={NBA_GAME:bundle}, **kwargs)


class OfficialEvidenceBoundary(unittest.TestCase):
    def test_regulation_and_arbitrary_overtime(self):
        for ot in (0,1,2,3,4,7):
            with self.subTest(ot=ot):
                m=48+5*ot
                b=official_fixture(ot,m)
                self.assertEqual(duration(b,game_id=NBA_GAME)['duration_minutes'],m)
                p=official_build(nba_entry(m),b,require_official_evidence=True)
                self.assertEqual(next(f['value'] for f in p['features'] if f['name'].endswith(':overtime_periods')),ot)

    def test_over_duration_rejected(self):
        for ot in (0,1,2,3,5):
            with self.subTest(ot=ot),self.assertRaisesRegex(ValueError,'PLAYER_MINUTES_EXCEED_GAME_DURATION'):
                official_build(nba_entry(49+5*ot),official_fixture(ot,49+5*ot))

    def test_zero_display_subminute_preserves_credit_and_display(self):
        p=official_build(nba_entry(0),official_fixture(minutes=0,exact='PT00M12.00S'))
        values={f['name'].split(':')[-1]:f['value'] for f in p['features']}
        self.assertEqual(values['minutes'],0)
        self.assertEqual(values['points'],11)
        self.assertEqual(values['official_exact_minutes'],.2)
        self.assertEqual(values['source_status'],'ADJUDICATED_ROUNDED_SUBMINUTE')

    def test_true_zero_deadball_unresolved(self):
        with self.assertRaisesRegex(ValueError,'ZERO_MINUTE_CREDIT_UNRESOLVED'):
            official_build(nba_entry(0),official_fixture(minutes=0))

    def test_wrong_teams_and_player(self):
        for field,value in [('team_id','nba:team:99'),('player_id','nba:player:99')]:
            e=repair_opponent(nba_entry());d=json.loads(e['record']['payload']);d[field]=value
            b=official_fixture()
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'OFFICIAL_.*CONFLICT'):
                adjudicate_player(d,b)

    def test_hash_and_identity(self):
        for what in ('hash','url','game'):
            b=official_fixture()
            if what=='hash': b['raw']+=b' '
            if what=='url': b['capture']['url']=b['capture']['url'].replace('cdn.nba.com','nba.com.evil.test')
            if what=='game': b['capture']['url']=b['capture']['url'].replace('0022200001','0022200002')
            with self.subTest(what=what),self.assertRaises(ValueError): duration(b,game_id=NBA_GAME)

    def test_complete_revision_chain(self):
        old=official_fixture();new=official_fixture(2,56)
        new['capture'].update(revision=2,supersedes_receipt_sha256=digest(old['capture']),retrieved_at='2026-11-16T19:00:00Z')
        with self.assertRaisesRegex(ValueError,'OFFICIAL_REVISION_CHAIN'): duration(new,game_id=NBA_GAME)
        new['prior']=[old]
        self.assertEqual(duration(new,game_id=NBA_GAME)['overtime_periods'],2)
        new['prior'][0]['raw']+=b' '
        with self.assertRaisesRegex(ValueError,'OFFICIAL_SOURCE_SHA_MISMATCH'): duration(new,game_id=NBA_GAME)

    def test_nonfinal_and_date_conflict(self):
        b=official_fixture();g=json.loads(b['raw']);g['game']['gameStatus']=2
        b['raw']=canonical(g);b['capture']['raw_sha256']=hashlib.sha256(b['raw']).hexdigest()
        with self.assertRaisesRegex(ValueError,'OFFICIAL_COMPLETED_DURATION_REQUIRED'):duration(b,game_id=NBA_GAME)
        with self.assertRaisesRegex(ValueError,'OFFICIAL_GAME_DATE_CONFLICT'):duration(official_fixture(),game_id=NBA_GAME,game_date='2022-10-22')

    def test_missing_official_evidence_strict_consumer(self):
        with self.assertRaisesRegex(ValueError,'OFFICIAL_SOURCE_EVIDENCE_REQUIRED'):
            build([make_entry()],require_official_evidence=True)

    def test_target_evidence_rejected(self):
        from tests.nba_architecture.test_p1_history import GAME
        with self.assertRaisesRegex(ValueError,'TARGET_GAME_OUTCOME_ACCESS'):
            build([make_entry()],official_game_evidence={GAME:official_fixture()})

    def test_stat_conflict(self):
        with self.assertRaisesRegex(ValueError,'OFFICIAL_STAT_CONFLICT'):
            official_build(nba_entry(),official_fixture(points=12))

    def test_vault_valid_multiot_and_subminute_replay(self):
        from v2.nba_architecture.p1_vault import OfficialOutcomeVault
        for minutes,ot,exact in [(56,2,None),(0,0,'PT00M12.00S')]:
            b=official_fixture(ot,minutes,exact=exact)
            with tempfile.TemporaryDirectory() as td:
                v=OfficialOutcomeVault(td)
                p=v.append(game_id=NBA_GAME,player_id='nba:player:7',team_id=NBA_TEAMS[0],
                    state='PLAYED' if minutes else 'PLAYED_ZERO_MINUTES',minutes=minutes,
                    stats={'points':11,'rebounds':5,'assists':3,'threes':2},
                    source_id='nba:official:box',source_bytes=b['raw'],
                    observed_at='2026-11-16T19:00:00Z',official_status='FINAL',official_game_evidence=b)
                self.assertEqual(v.latest(NBA_GAME,'nba:player:7')['content_hash'],p['content_hash'])

    def test_vault_deleted_parent_blocks_all_reads(self):
        from v2.nba_architecture.p1_vault import OfficialOutcomeVault
        from tests.nba_architecture import test_p1_history as fixtures
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            v=OfficialOutcomeVault(td);p=fixtures.P1VaultTest()._put(v)
            fixtures.P1VaultTest()._put(v,revision=2,supersedes_sha256=p['content_hash'],observed_at='2023-02-11T05:00:00Z')
            (Path(td)/(p['content_hash']+'.json')).unlink()
            with self.assertRaisesRegex(ValueError,'VAULT_REVISION_GAP'):v.records()

from v2.nba_architecture.p1_context import VERSION as CONTEXT_VERSION, resolve_dated_identity, pregame_candidates


def context_fixture(assertions):
    raw=canonical(dict(schema=CONTEXT_VERSION,assertions=assertions))
    return dict(source_url='https://www.nba.com/reviewed-source-export',raw=raw,
        raw_sha256=hashlib.sha256(raw).hexdigest(),observed_at='2023-02-08T10:00:00Z',
        available_at='2023-02-08T10:00:00Z',origin='original_capture')


class DatedContextBoundary(unittest.TestCase):
    def test_trade_timing_and_overlap(self):
        old=dict(kind='membership',provider_id='nba:player:7',canonical_id='nba:team:1',
                 valid_from='2022-10-01T00:00:00Z',valid_to='2023-02-09T12:00:00Z')
        new=dict(old,canonical_id='nba:team:2',valid_from=old['valid_to'],valid_to=None)
        b=context_fixture([old,new])
        for at,team in [('2023-02-09T11:59:59Z','nba:team:1'),('2023-02-09T12:00:00Z','nba:team:2')]:
            self.assertEqual(resolve_dated_identity('nba:player:7','membership',at,[b],input_freeze_at='2023-02-09T13:00:00Z')['canonical_id'],team)
        with self.assertRaisesRegex(ValueError,'DATED_IDENTITY_MISSING_OR_AMBIGUOUS'):
            resolve_dated_identity('nba:player:7','membership','2023-02-09T12:00:00Z',[b,b],input_freeze_at='2023-02-09T13:00:00Z')

    def test_missing_context_is_blocked(self):
        p=pregame_candidates(game_id='nba:game:target',team_ids=NBA_TEAMS,
            event_start_at='2023-02-10T01:00:00Z',input_freeze_at='2023-02-09T23:00:00Z',bundles=[])
        self.assertEqual(p['players'],[])
        self.assertEqual(p['status'],'BLOCKED_NO_AUTHENTICATED_PREGAME_CONTEXT')

    def test_postgame_roster_cannot_enter_context(self):
        b=context_fixture([]);b['observed_at']=b['available_at']='2023-02-10T05:00:00Z'
        with self.assertRaisesRegex(ValueError,'CONTEXT_POST_FREEZE_OR_BACKDATED'):
            pregame_candidates(game_id='nba:game:target',team_ids=NBA_TEAMS,
                event_start_at='2023-02-10T01:00:00Z',input_freeze_at='2023-02-09T23:00:00Z',bundles=[b])

    def test_target_outcome_fields_cannot_be_roster(self):
        b=context_fixture([dict(kind='player_game',minutes=30,points=11)])
        with self.assertRaisesRegex(ValueError,'PREGAME_CONTEXT_OUTCOME_OR_FIELDS'):
            pregame_candidates(game_id='nba:game:target',team_ids=NBA_TEAMS,
                event_start_at='2023-02-10T01:00:00Z',input_freeze_at='2023-02-09T23:00:00Z',bundles=[b])

    def test_context_hash_and_reconstruction_guard(self):
        for field,value in [('raw',b'corrupt'),('origin','retrospective_retrieval')]:
            b=context_fixture([]);b[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                pregame_candidates(game_id='nba:game:target',team_ids=NBA_TEAMS,
                    event_start_at='2023-02-10T01:00:00Z',input_freeze_at='2023-02-09T23:00:00Z',bundles=[b])

class AdditionalAdversarialBoundary(unittest.TestCase):
    def test_unknown_and_dnp_do_not_fill_stats(self):
        for status in ('unknown','dnp'):
            with self.subTest(status=status),self.assertRaisesRegex(ValueError,'DNP_UNKNOWN_NOT_ZERO'):
                build([make_entry(status=status,minutes=0,stats={'points':11})])

    def test_attempted_threes_exceed_total_attempts(self):
        with self.assertRaisesRegex(ValueError,'SHOOTING_ACCOUNTING'):
            build([make_entry(stats={'fga':1,'fg3a':2})])

    def test_duration_evidence_after_ingestion(self):
        b=official_fixture();b['capture']['retrieved_at']='2026-11-17T01:00:00Z'
        with self.assertRaisesRegex(ValueError,'OFFICIAL_EVIDENCE_AFTER_INGESTION'):
            official_build(nba_entry(),b)

    def test_vault_finite_and_durations(self):
        from v2.nba_architecture.p1_vault import OfficialOutcomeVault
        for value in (float('inf'),float('nan'),900):
            with tempfile.TemporaryDirectory() as td,self.subTest(minutes=value),self.assertRaises(ValueError):
                fixtures.P1VaultTest()._put(OfficialOutcomeVault(td),minutes=value)

    def test_positive_context_and_wrong_team_and_future_trade(self):
        args=dict(game_id='nba:game:target',team_ids=NBA_TEAMS,
            event_start_at='2023-02-10T01:00:00Z',input_freeze_at='2023-02-09T23:00:00Z')
        row=dict(kind='pregame_roster',game_id=args['game_id'],player_id='nba:player:7',team_id=NBA_TEAMS[0],
                 effective_at='2023-02-09T10:00:00Z',legal_eligibility=None,availability='unknown')
        self.assertIsNone(pregame_candidates(**args,bundles=[context_fixture([row])])['players'][0]['legal_eligibility'])
        for key,value in [('team_id','nba:team:99'),('effective_at','2023-02-10T00:00:00Z')]:
            bad=dict(row);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):pregame_candidates(**args,bundles=[context_fixture([bad])])

    def test_vault_source_corruption(self):
        from pathlib import Path
        from v2.nba_architecture.p1_vault import OfficialOutcomeVault
        with tempfile.TemporaryDirectory() as td:
            v=OfficialOutcomeVault(td);p=fixtures.P1VaultTest()._put(v)
            (Path(td)/'sources'/(p['source_raw_sha256']+'.raw')).write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError,'VAULT_ORIGINAL_SOURCE_MISSING_OR_TAMPERED'):v.records()

    def test_vault_is_not_a_pregame_dependency(self):
        import ast
        from pathlib import Path
        for name in ('p1_history.py','p1_evidence.py','p1_context.py'):
            tree=ast.parse((Path('v2/nba_architecture')/name).read_text())
            imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
            self.assertTrue(all(not x or 'vault' not in x for x in imports))

class SchemaAndCLI(unittest.TestCase):
    def test_new_capture_and_context_schemas(self):
        from pathlib import Path
        import jsonschema
        root=Path('v2/nba_architecture')
        jsonschema.Draft202012Validator(json.loads((root/'p1-official-capture-1.0.0.schema.json').read_bytes())).validate(official_fixture()['capture'])
        a=dict(kind='membership',provider_id='nba:player:7',canonical_id='nba:team:1',valid_from='2022-01-01T00:00:00Z',valid_to=None)
        jsonschema.Draft202012Validator(json.loads((root/'p1-context-1.0.0.schema.json').read_bytes())).validate(json.loads(context_fixture([a])['raw']))

    def test_real_source_fixture_replays_and_strict_exposure_blocks(self):
        # REAL ESPN bytes + pinned WS1 export. Historical cutoffs are simulated;
        # no official duration, original availability or pregame truth claimed.
        from pathlib import Path
        from scripts.nba_p1_build_pregame import execute
        root=Path('docs/nba_architecture/p1_remediation_20261117')
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'real.json'
            r=execute(root/'real_ws1_manifest.json',out,source_root=root)
            self.assertEqual(r['snapshot_sha256'],'39ef73ff53832aca7e569e641f6201c8b15c5888e863a6cc7a3db744f2f0b369')
            self.assertEqual(r['unresolved_exposure_records'],13)
            self.assertEqual(r['source_original_bytes_verified'],13)
            with self.assertRaisesRegex(ValueError,'OFFICIAL_SOURCE_EVIDENCE_REQUIRED'):
                execute(root/'real_ws1_manifest.json',Path(td)/'blocked.json',source_root=root,require_official_evidence=True)
            self.assertFalse((Path(td)/'blocked.json').exists())

    def test_cli_blocks_whole_manifest_with_denominator(self):
        from pathlib import Path
        from contextlib import redirect_stdout
        import io
        from scripts.nba_p1_build_pregame import main
        root=Path('docs/nba_architecture/p1_remediation_20261117')
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'blocked.json';s=io.StringIO()
            with redirect_stdout(s):
                code=main(['--input',str(root/'real_ws1_manifest.json'),'--output',str(out),
                    '--source-root',str(root),'--require-official-evidence'])
            receipt=json.loads(s.getvalue())
            self.assertEqual(code,2);self.assertEqual(receipt['attempted_entries'],26)
            self.assertFalse(out.exists());self.assertFalse(receipt['output_written'])

class HandoffBoundary(unittest.TestCase):
    def test_p2_handoff_keeps_exact_and_displayed_minutes(self):
        from v2.nba_architecture.p1_evidence import prior_game_exposure
        data=json.loads(repair_opponent(nba_entry(0))['record']['payload'])
        h=prior_game_exposure(data,official_fixture(minutes=0,exact='PT00M12.00S'))
        self.assertEqual(h['displayed_minutes'],0)
        self.assertEqual(h['exact_minutes'],.2)
        self.assertIn('AUTHENTICITY_REVIEW_REQUIRED',h['source_status'])
        self.assertIsNone(h['original_pregame_available_at'])

    def test_missing_official_result_explicit_unresolved(self):
        from v2.nba_architecture.p1_vault import OfficialOutcomeVault
        with tempfile.TemporaryDirectory() as td:
            h=OfficialOutcomeVault(td).outcome_status(NBA_GAME,'nba:player:7')
            self.assertEqual(h['state'],'UNRESOLVED')
            self.assertEqual(h['reason'],'MISSING_OFFICIAL_RESULT')
            self.assertIsNone(h['minutes']);self.assertEqual(h['stats'],{})

class OfficialCLI(unittest.TestCase):
    def test_strict_multiot_manifest_and_path_escape(self):
        from pathlib import Path
        from scripts.nba_p1_build_pregame import execute
        b=official_fixture(2,56)
        base=dict(schedule=dict(game_id='nba:game:target',team_ids=list(NBA_TEAMS),
            event_start_at='2023-02-10T01:00:00Z',input_freeze_at='2023-02-09T23:45:00Z',
            forecast_at='2023-02-09T23:50:00Z',training_cutoff_at='2023-02-08T00:00:00Z',decision_local_date='2023-02-09'),
            entries=[repair_opponent(nba_entry(56))],ingested_at='2026-11-16T18:01:00Z',original_bytes={},
            official_game_evidence={NBA_GAME:dict(capture=b['capture'],source_path='box.raw',prior=[])})
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'sources';root.mkdir();(root/'box.raw').write_bytes(b['raw']);p=root/'manifest.json'
            p.write_text(json.dumps(base));a=execute(p,root/'out.json',source_root=root,require_official_evidence=True)
            z=execute(p,root/'out.json',source_root=root,require_official_evidence=True)
            self.assertEqual(a,z);self.assertEqual(a['unresolved_exposure_records'],0)
            base['official_game_evidence'][NBA_GAME]['source_path']='../outside.raw'
            (root.parent/'outside.raw').write_bytes(b['raw'])
            try:
                p.write_text(json.dumps(base))
                with self.assertRaisesRegex(ValueError,'SOURCE_PATH_ESCAPE'):
                    execute(p,root/'bad.json',source_root=root,require_official_evidence=True)
            finally:
                (root.parent/'outside.raw').unlink()
