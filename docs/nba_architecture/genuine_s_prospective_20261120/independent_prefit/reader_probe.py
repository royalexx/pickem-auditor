"""Independent reader review. All native fit calls are forbidden by a spy."""
from collections import Counter
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from v2.nba_architecture import prospective_s_sources_v1 as reader
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_c.subset_archive_v1 import READERS
from v2.nba_s_family import model as native

HERE=Path(__file__).resolve().parent
PACKET=HERE.parent;RAW=PACKET/'raw';SPEC=PACKET/'PREFIT_POPULATION.json';POLICY=PACKET/'policy/nba_rule5.raw'
RESULT={}

def html(game):return b'<script id="__NEXT_DATA__">'+canonical({'props':{'pageProps':{'game':game}}})+b'</script>'

class IndependentPreFitReader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fit_spy=patch.object(native,'fit',side_effect=AssertionError('FIT_FORBIDDEN_DURING_PREFIT_REVIEW'))
        cls.fit=cls.fit_spy.start()
        cls.dataset=reader.build_dataset(RAW,SPEC,POLICY)
        cls.spec=json.loads(SPEC.read_bytes());cls.raw=canonical(cls.dataset)
        (HERE/'independent_dataset.json').write_bytes(cls.raw)
        RESULT.update(tested_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            reader_raw_sha256=digest(Path(reader.__file__).read_bytes()),dataset_raw_sha256=digest(cls.raw),
            dataset_payload_sha256=cls.dataset['payload_sha256'],prefit_spec_raw_sha256=digest(SPEC.read_bytes()),
            native_S_reader_raw_sha256=digest(Path(native.__file__).read_bytes()),timing_policy_raw_sha256=digest(POLICY.read_bytes()),
            native_fit_calls=cls.fit.call_count)

    @classmethod
    def tearDownClass(cls):
        RESULT['native_fit_calls']=cls.fit.call_count
        cls.fit_spy.stop()

    def test_01_exact_frozen_reader_dataset_matches_independent_raw_audit(self):
        d=self.dataset;raw_audit=json.loads((HERE/'population.stdout').read_bytes())
        self.assertEqual((d['source_capture_count'],d['game_count'],d['source_observation_denominator'],d['player_row_denominator'],
            d['inactive_identity_denominator'],d['training_attempt_denominator'],d['included_training_attempts'],d['excluded_training_attempts']),
            (60,20,698,532,166,2792,1824,968))
        other=json.loads((PACKET/'reader_repaired_evidence/dataset.json').read_bytes())
        self.assertEqual(d,other)
        indexed={(r['nba_game_id'],str(r['nba_person_id'])):r for r in d['records']}
        self.assertEqual(len(indexed),698)
        for original in raw_audit['observations']:
            row=indexed[(original['nba_game_id'],str(original['nba_person_id']))]
            self.assertEqual(row['fit_included'],original['status']=='ELIGIBLE_BEFORE_READER_REVIEW')
            if row['source_list']=='players':self.assertEqual(row['exact_seconds'],original['exact_reported_seconds'])
            if row['fit_included']:
                self.assertEqual(row['role'],'ESPN_POSITION_BIN_AT_CAPTURE:'+original['observed_peer_position_bin'])
                self.assertEqual(row['player_id'],'espn:player:'+original['espn_player_id'])
        self.assertFalse(d['fit_performed']);self.fit.assert_not_called()
        RESULT['counts']={k:d[k] for k in ('source_capture_count','game_count','source_observation_denominator',
            'player_row_denominator','inactive_identity_denominator','training_attempt_denominator',
            'included_training_attempts','excluded_training_attempts')}
        RESULT['record_states']=dict(Counter(r['state'] for r in d['records']))

    def test_02_native_fit_rows_are_exact_typed_transforms_with_full_lineage(self):
        d=self.dataset;included={(r['game_id'],r['player_id']):r for r in d['records'] if r['fit_included']}
        self.assertEqual(len(included),456)
        for stat,history in d['histories'].items():
            self.assertEqual(len(history),456)
            self.assertEqual(len({(r['game_id'],r['player_id']) for r in history}),456)
            for row in history:
                source=included[(row['game_id'],row['player_id'])]
                self.assertGreaterEqual(source['exact_seconds'],30)
                self.assertEqual(row['minutes'],float(Fraction(source['exact_seconds'],60)))
                self.assertEqual(source['exact_minutes_rational'],str(Fraction(source['exact_seconds'],60)))
                self.assertEqual(row['count'],source['official_counts'][reader.STAT_KEYS[stat]])
                self.assertEqual(row['three_attempts'],source['official_counts']['threePointersAttempted'])
                self.assertEqual(row['role'],source['role']);self.assertEqual(row['team_id'],source['team_id'])
                key=row['source_receipt_sha256'];entry=d['source_manifest'][key]
                self.assertEqual(entry['games'][row['game_id']]['players'][row['player_id']],row['team_id'])
                self.assertEqual(digest(d['raw_sources'][key].encode()),row['source_raw_sha256'])
                summary='summary-'+row['game_id'].removeprefix('espn:game:')
                self.assertEqual(source['role_identity_source_raw_sha256'],digest((RAW/summary/'body.raw').read_bytes()))
                self.assertEqual(source['role_identity_source_receipt_sha256'],digest((RAW/summary/'receipt.json').read_bytes()))
                role_receipt=json.loads((RAW/summary/'receipt.json').read_bytes())
                self.assertEqual(source['role_source_observed_at'],role_receipt['retrieval_completed_at'])
                self.assertLessEqual(reader.utc(row['outcome_available_at']),reader.utc(entry['available_at']))
                self.assertLessEqual(reader.utc(entry['available_at']),reader.utc(d['data_cutoff_at']))
                self.assertNotEqual(row['game_id'],'espn:game:'+d['target']['game_id'])
        self.assertEqual(len(d['attempts']),4*len(d['records']))
        for index in range(len(d['records'])):
            attempts=[a for a in d['attempts'] if a['source_observation_index']==index]
            self.assertEqual({a['statistic'] for a in attempts},set(reader.STAT_KEYS))
            self.assertTrue(all(a['included']==d['records'][index]['fit_included'] for a in attempts))
        self.fit.assert_not_called()

    def test_03_closed_frozen_source_policy_and_receipt_mutations_reject(self):
        actual=Path.read_bytes
        cases=[]
        for label in ('nba-box-0022600258','summary-401910007','nba-index-2026-11-18','roster-29','schedule-29','scoreboard'):
            cases.extend([(RAW/label/'body.raw',b' '),(RAW/label/'receipt.json',b' ')])
        cases.extend([(SPEC,b' '),(POLICY,b' ')])
        for target,suffix in cases:
            def changed(path,*args,**kwargs):
                raw=actual(path,*args,**kwargs)
                return raw+suffix if path==target else raw
            with self.subTest(path=str(target.relative_to(ROOT))),patch.object(Path,'read_bytes',changed),self.assertRaises(ValueError):
                reader.build_dataset(RAW,SPEC,POLICY)
        # Even a rewritten receipt with its own body hash cannot change the frozen manifest.
        target=RAW/'nba-box-0022600258/body.raw';receipt=target.parent/'receipt.json'
        altered=actual(target)+b' ';value=json.loads(actual(receipt));value['raw_sha256']=digest(altered);value['bytes']=len(altered)
        def resealed(path,*args,**kwargs):
            if path==target:return altered
            if path==receipt:return canonical(value)
            return actual(path,*args,**kwargs)
        with patch.object(Path,'read_bytes',resealed),self.assertRaises(ValueError):reader.build_dataset(RAW,SPEC,POLICY)
        self.fit.assert_not_called()

    def test_04_public_parser_rejects_game_time_period_identity_and_json_attacks(self):
        join=self.spec['game_joins'][0]
        o=(RAW/('nba-box-'+join['nba_id'])/'body.raw').read_bytes()
        e=(RAW/('summary-'+join['espn_id'])/'body.raw').read_bytes();i=(RAW/join['index']/'body.raw').read_bytes()
        base=reader.next_data(o)['game']
        for attack in ('wrong_game','nonfinal','live_clock','period3','period_gap','score','team_id','duplicate_player','noninteger_count'):
            value=copy.deepcopy(base)
            if attack=='wrong_game':value['gameId']='wrong'
            elif attack=='nonfinal':value['gameStatus']=2
            elif attack=='live_clock':value['gameClock']='PT00M01.00S'
            elif attack=='period3':value['period']=3
            elif attack=='period_gap':value['awayTeam']['periods'].pop()
            elif attack=='score':value['awayTeam']['periods'][0]['score']+=1
            elif attack=='team_id':value['awayTeamId']+=1
            elif attack=='duplicate_player':value['awayTeam']['players'].append(copy.deepcopy(value['awayTeam']['players'][0]))
            elif attack=='noninteger_count':value['awayTeam']['players'][0]['statistics']['points']=float(value['awayTeam']['players'][0]['statistics']['points'])
            with self.subTest(attack=attack),self.assertRaises(ValueError):reader.parse_completed_game(html(value),e,i,join)
        for attack in (html(base)+html(base),b'<script id="__NEXT_DATA__">{"a":1,"a":2}</script>',b'<script id="__NEXT_DATA__">{"a":NaN}</script>'):
            with self.assertRaises(ValueError):reader.next_data(attack)
        self.fit.assert_not_called()

    def test_05_public_parser_preserves_exposure_role_and_conflict_abstentions(self):
        join=self.spec['game_joins'][0]
        o=(RAW/('nba-box-'+join['nba_id'])/'body.raw').read_bytes();e=(RAW/('summary-'+join['espn_id'])/'body.raw').read_bytes()
        i=(RAW/join['index']/'body.raw').read_bytes();base=reader.next_data(o)['game'];target=str(base['awayTeam']['players'][0]['personId'])
        for display,expected in [('0:00','ZERO_DISPLAY'),('0:29','PLAYED_SUB30'),('0:30','PLAYED_ORDINARY'),('0:60','UNKNOWN'),('99:00','UNKNOWN'),('','UNKNOWN')]:
            value=copy.deepcopy(base);value['awayTeam']['players'][0]['statistics']['minutes']=display
            out=reader.parse_completed_game(html(value),e,i,join);row=next(r for r in out['rows'] if r['nba_person_id']==target)
            self.assertEqual(row['state'],expected)
            if expected!='PLAYED_ORDINARY':self.assertFalse(row['fit_included'])
        source=json.loads(e);team=next(t for t in source['boxscore']['players'] if t['team']['name']==base['awayTeam']['teamName'])
        key=reader.name_key(base['awayTeam']['players'][0]['firstName']+' '+base['awayTeam']['players'][0]['familyName'])
        person=next(r for r in team['statistics'][0]['athletes'] if reader.name_key(r['athlete']['displayName'])==key)
        person['athlete']['position']['abbreviation']='G-F'
        out=reader.parse_completed_game(o,canonical(source),i,join);row=next(r for r in out['rows'] if r['nba_person_id']==target)
        self.assertFalse(row['fit_included']);self.assertEqual(row['reason'],'AMBIGUOUS_OR_MISSING_CAPTURE_POSITION')
        conflicts=[r for r in self.dataset['records'] if r['reason']=='CROSS_SOURCE_FULL_COUNT_VECTOR_CONFLICT']
        self.assertEqual([(r['name'],r['nba_game_id']) for r in conflicts],[('Malachi Smith','0022600206')])
        self.assertEqual(len([r for r in self.dataset['records'] if r['state']=='DNP']),68)
        self.fit.assert_not_called()

    def test_06_preserved_twenty_readers_old_model_and_timing_rule(self):
        paths=list(READERS)+['v2/nba_architecture/subset_p2_dispatch_v1.py','v2/nba_c/subset_dispatch_archive_v1.py','scripts/nba_subset_p2_dispatch.py']
        self.assertEqual(len(paths),20)
        for path in paths:
            with self.subTest(path=path):
                prior=subprocess.check_output(['git','show','a4493ac7:'+path],cwd=ROOT)
                self.assertEqual(prior,(ROOT/path).read_bytes())
        self.assertEqual(digest((ROOT/'research/nba_ws2/results/model.json').read_bytes()),'ea7eae3afc760eafda0fbf0dbdccd2cb77b31b0aca54fc3606b4b31ba90693de')
        self.assertEqual(POLICY.read_bytes(),(ROOT/'docs/nba_architecture/p1_remediation_20261117/sources/nba_rule5.raw').read_bytes())
        self.assertIn(b'All periods of regulation play in the NBA will be twelve minutes.',POLICY.read_bytes())
        self.assertIn(b'All overtime periods of play will be five minutes.',POLICY.read_bytes())
        RESULT['old_twenty_readers_unchanged']=paths


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(IndependentPreFitReader))
    RESULT.update(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),
        disposition='PREFIT_REVIEW_EVIDENCE_ONLY_ARTIFACT_ADMISSION_NOT_GRANTED')
    (HERE/'READER_RESULTS.json').write_text(json.dumps(RESULT,indent=2,sort_keys=True)+'\n')
    sys.exit(not result.wasSuccessful())
