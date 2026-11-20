"""Independent public-path review; no fitting, scoring, or implementation writes."""
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from v2.nba_architecture import subset_p2_dispatch_v1 as dispatch
from v2.nba_architecture.p1_subset_handoff_v1 import canonical, digest
from v2.nba_s_family import model as native
from v2.nba_c.subset_dispatch_archive_v1 import DispatchAuditArchive
from v2.nba_c.subset_archive_v1 import READERS as OLD_READERS
from v2.nba_c.warehouse import _write_once

HERE = Path(os.environ.get('NBA_P2_REVIEW_OUTPUT', str(Path(__file__).resolve().parent)))
HERE.mkdir(parents=True, exist_ok=True)
OLD = ROOT / 'docs/nba_architecture/p1_p5_handoffs_20261119'
CAP = ROOT / 'docs/nba_architecture/p1_subset_acceptance_20261119/initial_tonight_capture'
HISTORY = OLD / 'prospective_inputs'
MODEL = ROOT / 'research/nba_ws2/results/model.json'
FIXTURE = ROOT / 'research/nba_p4_latest/fixtures_v2'
BASE = '82c6092f2b970552e4a1a8a8a6c495052fb3e8b2'
EVIDENCE = {}
REPLAY_AT = os.environ.get('NBA_P2_REVIEW_FORECAST_AT')


def reseal(value):
    value = copy.deepcopy(value)
    value.pop('payload_sha256', None)
    value['payload_sha256'] = digest(canonical(value))
    return canonical(value)


def synthetic():
    source = json.loads((FIXTURE / 'inputs.json').read_bytes())
    p = source['pregame']
    artifact = (FIXTURE / 'points.json').read_bytes()
    if digest(artifact) != '662cc75155f2fd26e42c7b177df396a61acf7b8f0505a3479a314cf6feebf96f':
        raise AssertionError('Frozen existing native S fixture bytes changed')
    manifest = canonical(source['source_manifest'])
    bodies = (FIXTURE / 'raw_sources.json').read_bytes()
    contract = dispatch.ModelContract(
        digest(artifact), digest(manifest), digest(bodies), digest(Path(native.__file__).read_bytes()),
        digest(canonical(p)), json.loads(artifact)['training_cutoff_at'], 'points', 'S1',
        (('F', 'high', 'rotation'),), tuple((x['player_id'], x['team_id']) for x in p['players']),
        'SYNTHETIC_ENGINEERING_ONLY')
    binding = dict(game_id=p['game_id'], player_id='espn:player:10', team_id='espn:team:1',
        opponent_id='espn:team:2', statistic='points', cohort_sha256=contract.cohort_sha256,
        conditioning=dispatch.CONDITIONING, participation_probability=None, legal_eligibility=None,
        p3_variant='M0', p3_forecast_id='independent:synthetic:M0', projected_exposure=30.,
        exposure_units='minutes', role_features=dict(position='F', historical_workload_state='high'),
        forecast_at=p['forecast_at'], input_freeze_at=p['input_freeze_at'], event_start_at=p['event_start_at'])
    return binding, contract, artifact, manifest, bodies


class IndependentDispatcherReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cohort = json.loads((OLD / 'PROSPECTIVE_COHORT.json').read_bytes())
        cls.run_dir = HERE / ('recorded_replay_cli' if REPLAY_AT else 'actual_current_cli')
        argv = [sys.executable, 'scripts/nba_subset_p2_dispatch.py', '--capture', str(CAP.relative_to(ROOT)),
            '--cohort', str((OLD/'PROSPECTIVE_COHORT.json').relative_to(ROOT)), '--history',
            str(HISTORY.relative_to(ROOT)), '--output', str(cls.run_dir)]
        if REPLAY_AT:
            argv.extend(['--forecast-at', REPLAY_AT])
        started = datetime.now(timezone.utc).isoformat()
        process = subprocess.run(argv, cwd=ROOT, capture_output=True)
        (HERE/'actual_cli.stdout').write_bytes(process.stdout)
        (HERE/'actual_cli.stderr').write_bytes(process.stderr)
        EVIDENCE['actual_cli'] = dict(argv=argv, started_at=started,
            completed_at=datetime.now(timezone.utc).isoformat(), exit_code=process.returncode)
        if process.returncode:
            raise RuntimeError(process.stderr.decode())
        cls.receipt = json.loads((cls.run_dir/'receipt.json').read_bytes())
        cls.wire = (cls.run_dir/'dispatch.json').read_bytes()
        cls.output = json.loads(cls.wire)
        cls.inputs = dict(source_raw=(cls.run_dir/'p1.json').read_bytes(), p3_raw=(cls.run_dir/'p3.json').read_bytes(),
            capture_dir=CAP, cohort=cls.cohort, history_dir=HISTORY, model_path=MODEL,
            forecast_at=cls.receipt['forecast_at'])
        cls.record = cls.receipt['dispatch_receipt']['record_id']
        cls.archive = DispatchAuditArchive(cls.run_dir/'archive')
        EVIDENCE['tested_commit'] = subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip()
        EVIDENCE['implementation_sha256'] = {name:digest((ROOT/name).read_bytes()) for name in
            ('v2/nba_architecture/subset_p2_dispatch_v1.py', 'v2/nba_c/subset_dispatch_archive_v1.py',
             'scripts/nba_subset_p2_dispatch.py')}

    def test_01_actual_current_clock_and_complete_source_denominators(self):
        self.assertEqual(self.receipt['operation'], 'RECORDED_CLOCK_REPLAY' if REPLAY_AT else 'CURRENT_RESEARCH_EXECUTION')
        self.assertEqual('--forecast-at' in self.receipt['command'], bool(REPLAY_AT))
        at = datetime.fromisoformat(self.receipt['forecast_at'])
        self.assertLess(at, datetime.fromisoformat(self.cohort['start'].replace('Z','+00:00')))
        x = self.output
        self.assertEqual((x['candidate_denominator'],x['attempt_denominator'],x['exposure_bound_rows'],
            x['forecasted_rows'],x['abstained_rows']),(36,144,48,0,144))
        counts = Counter(r['reason'] for r in x['rows'])
        self.assertEqual(counts['P1_SOURCE_ABSTENTION'],44)
        self.assertEqual(sum(v for k,v in counts.items() if k.startswith('P3_MINUTES_UNAVAILABLE:')),52)
        self.assertEqual(counts['SAVED_S_ARTIFACT_UNAVAILABLE'],48)
        self.assertEqual(len({(r['game_id'],r['player_id'],r['team_id'],r['statistic']) for r in x['rows']}),144)
        self.assertEqual(x['model_candidate_denominator'],4)
        self.assertEqual(x['admitted_model_count'],0)
        self.assertFalse(dispatch.ADMITTED_MODELS)
        for row in x['rows']:
            self.assertIsNone(row['trained_role']); self.assertIsNone(row['participation_probability'])
            self.assertIsNone(row['legal_eligibility']); self.assertIsNone(row['forecast'])
            self.assertFalse(row['actual_native_model_executed'])
        p3=json.loads(self.inputs['p3_raw'])
        minutes={(r['player_id'],r['team_id']):r['forecast'] for r in p3['rows'] if r['model']=='M0'}
        for row in x['rows']:
            if row['binding']:
                b=row['binding'];m=minutes[(row['player_id'],row['team_id'])]
                self.assertEqual(b['projected_exposure'],m['expected_minutes_given_played'])
                self.assertEqual(b['p3_forecast_id'],m['forecast_id'])
                self.assertEqual(b['p3_variant'],'M0')
        EVIDENCE['actual_counts'] = dict(candidate_rows=36,dispatch_attempts=144,source_abstentions=44,
            minute_history_abstentions=52,missing_real_model_abstentions=48,exposure_bindings=48,real_S_forecasts=0)

    def test_02_all_old_reader_bytes_are_unchanged(self):
        for name in OLD_READERS:
            with self.subTest(path=name):
                prior=subprocess.check_output(['git','show',BASE+':'+name],cwd=ROOT)
                self.assertEqual(prior,(ROOT/name).read_bytes())
        EVIDENCE['old_readers_unchanged']=list(OLD_READERS)

    def test_03_frozen_native_positive_and_exact_probability_semantics(self):
        args=synthetic()
        with patch.object(native,'predict_conditional',wraps=native.predict_conditional) as call:
            result=dispatch.structural_dispatch_control(*args)
        self.assertEqual(call.call_count,1)
        self.assertFalse(result['admitted']);self.assertEqual(result['mode'],'SYNTHETIC_ENGINEERING_ONLY')
        f=result['result'];self.assertFalse(f['minute_uncertainty_integrated'])
        self.assertIsNone(f['participation_probability']);self.assertIsNone(f['legal_eligibility'])
        self.assertEqual(f['trained_role'],'rotation')
        support=f['parameters']['support'];masses=[r['mass'] for r in support]
        self.assertAlmostEqual(sum(masses),1.,places=12)
        for line in (0.,10.,10.5,30.):
            expected=dict(over=sum(r['mass'] for r in support if r['value']>line),
                under=sum(r['mass'] for r in support if r['value']<line),
                push=sum(r['mass'] for r in support if r['value']==line))
            actual=native.exact_triplet(masses,line)
            for key,value in expected.items():self.assertAlmostEqual(actual[key],value,places=12)
        EVIDENCE['synthetic_control']=result

    def test_04_contract_source_clock_role_and_training_attacks(self):
        b,c,a,m,r=synthetic()
        mutations=[('q',dict(participation_probability=1.)),('legal',dict(legal_eligibility=True)),
            ('clock',dict(forecast_at=b['event_start_at'])),('negative_exposure',dict(projected_exposure=-1)),
            ('nan_exposure',dict(projected_exposure=float('nan'))),('variant',dict(p3_variant='M1')),
            ('units',dict(exposure_units='attempts')),('team',dict(team_id='espn:team:wrong')),
            ('role',dict(role_features=dict(position='F',historical_workload_state='untrained'))),
            ('real_target',dict(game_id='401910019'))]
        for name,changes in mutations:
            with self.subTest(attack=name),self.assertRaises((ValueError,KeyError)):
                dispatch.structural_dispatch_control(dict(b,**changes),c,a,m,r)
        for name,cc,aa,mm,rr in [('artifact_bytes',c,a+b' ',m,r),('manifest_bytes',c,a,m+b' ',r),
            ('raw_source_bytes',c,a,m,r+b' '),('reader',replace(c,native_code_sha256='0'*64),a,m,r),
            ('family_S3',replace(c,family='S3'),a,m,r),('family_S0',replace(c,family='S0'),a,m,r),
            ('unresolved_role',replace(c,role_map=()),a,m,r),
            ('duplicate_role',replace(c,role_map=c.role_map+c.role_map),a,m,r)]:
            with self.subTest(attack=name),self.assertRaises(ValueError):
                dispatch.structural_dispatch_control(b,cc,aa,mm,rr)
        for attack in ('target_training','duplicate_training','wrong_dated_team','future_cutoff','missing_manifest_key',
                'changed_body','postcutoff_source','wrong_training_source_hash'):
            art=json.loads(a);manifest=json.loads(m);bodies=json.loads(r);cc=c
            key=art['training_rows'][0]['source_receipt_sha256']
            if attack=='target_training':art['training_rows'][0]['game_id']=b['game_id']
            elif attack=='duplicate_training':art['training_rows'].append(copy.deepcopy(art['training_rows'][0]))
            elif attack=='wrong_dated_team':art['training_rows'][0]['team_id']='espn:team:wrong'
            elif attack=='future_cutoff':art['training_cutoff_at']='2027-01-01T00:00:00Z';cc=replace(cc,training_cutoff_at=art['training_cutoff_at'])
            elif attack=='missing_manifest_key':manifest.pop(key)
            elif attack=='changed_body':bodies[key]+=' '
            elif attack=='postcutoff_source':manifest[key]['available_at']='2027-01-01T00:00:00Z'
            elif attack=='wrong_training_source_hash':art['training_rows'][0]['source_raw_sha256']='0'*64
            aa,mm,rr=map(canonical,(art,manifest,bodies))
            cc=replace(cc,artifact_sha256=digest(aa),manifest_raw_sha256=digest(mm),raw_sources_sha256=digest(rr))
            with self.subTest(attack=attack),self.assertRaises(ValueError):
                dispatch.structural_dispatch_control(b,cc,aa,mm,rr)

    def test_05_untrusted_model_and_approval_candidates_never_admit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'models';root.mkdir();(root/'points.json').write_bytes((FIXTURE/'points.json').read_bytes())
            (root/'approval.json').write_text('{"approved":true,"reviewer":"independent","real":true}')
            (root/'extra').mkdir();(root/'extra/unmatched.bin').write_bytes(b'not a model')
            x=dispatch.run_dispatch(**self.inputs,model_dir=root)
            self.assertEqual(x['provided_file_denominator'],3);self.assertEqual(x['forecasted_rows'],0)
            self.assertEqual(x['attempt_denominator'],144)
            self.assertEqual(sum(row['reason']=='S_ARTIFACT_NOT_ADMITTED' for row in x['rows']),12)
            self.assertEqual(x['provided_files']['extra/unmatched.bin']['disposition'],'REJECTED_UNMATCHED_PROVIDED_FILE')
            archive=DispatchAuditArchive(Path(tmp)/'archive')
            # Use the genuine base archive through a copy, then model candidates are independently archived.
            shutil.copytree(self.run_dir/'archive/subset_research_audit',Path(tmp)/'archive/subset_research_audit')
            receipt=archive.put(self.receipt['base_receipt']['record_id'],canonical(x),model_dir=root)
            value=archive.read(receipt['record_id'])
            self.assertEqual(set(value['model_files']),{'points.json','approval.json','extra/unmatched.bin'})
            self.assertFalse(value['model_admission_granted'])

    def test_06_resealed_public_wire_and_upstream_mutations_fail(self):
        for attack in ('drop','duplicate','q','legal','role','forecast','model_count','candidate_drop','file_count','M2'):
            x=copy.deepcopy(self.output)
            if attack=='drop':x['rows'].pop()
            elif attack=='duplicate':x['rows'].append(copy.deepcopy(x['rows'][0]))
            elif attack=='q':x['rows'][0]['participation_probability']=1.
            elif attack=='legal':x['rows'][0]['legal_eligibility']=True
            elif attack=='role':x['rows'][0]['trained_role']='rotation'
            elif attack=='forecast':x['rows'][0]['forecast']={'mean':20.}
            elif attack=='model_count':x['admitted_model_count']=1
            elif attack=='candidate_drop':x['model_candidates'].pop()
            elif attack=='file_count':x['provided_file_denominator']=1
            elif attack=='M2':x['exposure_variant']='M2'
            with self.subTest(attack=attack),self.assertRaises(ValueError):
                dispatch.read_dispatch(reseal(x),**self.inputs)
        for raw in (b'{"forecasted_rows":999,'+self.wire[1:],b'{"q":NaN}'):
            with self.assertRaises(ValueError):dispatch.read_dispatch(raw,**self.inputs)
        for stage in ('source_raw','p3_raw'):
            x=json.loads(self.inputs[stage]);rows=x['requests']['rows'] if stage=='source_raw' else x['rows']
            rows[0]['team_id']='wrong'
            with self.subTest(stage=stage),self.assertRaises(ValueError):
                dispatch.run_dispatch(**dict(self.inputs,**{stage:reseal(x)}))
        for at in (self.cohort['start'],'2026-11-21T00:00:00Z'):
            with self.assertRaises(ValueError):dispatch.run_dispatch(**dict(self.inputs,forecast_at=at))

    def test_07_archive_replay_idempotence_and_native_write_once(self):
        with patch('v2.nba_c.subset_dispatch_archive_v1._write_once',wraps=_write_once) as calls:
            receipt=self.archive.put(self.receipt['base_receipt']['record_id'],self.wire)
        self.assertFalse(receipt['created']);self.assertEqual(receipt['record_id'],self.record)
        self.assertGreaterEqual(calls.call_count,5)
        old_read=Path.read_bytes
        def guarded(path,*args,**kwargs):
            if any(path==root or root in path.parents for root in (CAP,HISTORY,MODEL)):
                raise AssertionError('Archive reached original input path: '+str(path))
            return old_read(path,*args,**kwargs)
        with patch.object(Path,'read_bytes',guarded):value=self.archive.read(self.record)
        self.assertEqual((value['original_attempt_records'],value['combined_attempt_records']),(684,828))
        self.assertFalse(value['scoring_admitted']);self.assertFalse(value['model_admission_granted'])
        EVIDENCE['dispatch_archive_manifest']=value
        EVIDENCE['native_write_once_calls']=calls.call_count

    def test_08_archive_raw_and_resealed_tampering_rejects(self):
        for attack in ('missing_object','changed_object','native_collision','resealed_q','resealed_drop',
                'reader_change','reader_drop','false_counts','false_admission','model_drop','traversal'):
            with self.subTest(attack=attack),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'archive';shutil.copytree(self.run_dir/'archive',root)
                archive=DispatchAuditArchive(root);manifest=json.loads(archive._record(self.record).read_bytes())
                ref=manifest['dispatch'];obj=archive._object(ref['sha256'])
                if attack=='missing_object':obj.unlink()
                elif attack=='changed_object':
                    obj.chmod(0o644);obj.write_bytes(obj.read_bytes()+b' ')
                elif attack=='native_collision':
                    obj.chmod(0o644);obj.write_bytes(b'collision')
                    with self.assertRaises(ValueError):archive.put(self.receipt['base_receipt']['record_id'],self.wire)
                    continue
                elif attack in ('resealed_q','resealed_drop'):
                    value=json.loads(obj.read_bytes())
                    if attack=='resealed_q':value['rows'][0]['participation_probability']=1.
                    else:value['rows'].pop()
                    raw=reseal(value);sha=digest(raw);archive._object(sha).write_bytes(raw)
                    manifest['dispatch'].update(sha256=sha,bytes=len(raw))
                elif attack=='reader_change':
                    name=next(iter(manifest['reader_files']));raw=b'changed code';sha=digest(raw)
                    archive._object(sha).write_bytes(raw);manifest['reader_files'][name].update(sha256=sha,bytes=len(raw))
                elif attack=='reader_drop':manifest['reader_files'].pop(next(iter(manifest['reader_files'])))
                elif attack=='false_counts':manifest['combined_attempt_records']-=1
                elif attack=='false_admission':manifest['model_admission_granted']=True
                elif attack=='model_drop':manifest['model_files']['points.json']=dict(manifest['dispatch'])
                elif attack=='traversal':manifest['reader_files']['../escape']=manifest['reader_files'].pop(next(iter(manifest['reader_files'])))
                if attack in ('missing_object','changed_object'):
                    record=self.record
                else:
                    raw=canonical(manifest)+b'\n';record=digest(raw);archive._record(record).write_bytes(raw)
                with self.assertRaises((ValueError,OSError)):archive.read(record)

    def test_09_exact_manifest_and_checksum_domains(self):
        checked=0
        for line in (self.run_dir/'SHA256SUMS').read_text().splitlines():
            expected,name=line.split('  ',1)
            self.assertEqual(hashlib.sha256((self.run_dir/name).read_bytes()).hexdigest(),expected)
            checked+=1
        manifest=self.archive._record(self.record).read_bytes()
        self.assertEqual(manifest,canonical(json.loads(manifest))+b'\n')
        self.assertEqual(digest(manifest),self.record)
        EVIDENCE['cli_files_independently_rehashed']=checked


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(IndependentDispatcherReview))
    EVIDENCE['tests_run']=result.testsRun
    EVIDENCE['failures']=len(result.failures)
    EVIDENCE['errors']=len(result.errors)
    EVIDENCE['reviewer']='independent_p2_dispatch_review; no implementation repairs authored'
    (HERE/'RESULTS.json').write_text(json.dumps(EVIDENCE,indent=2,sort_keys=True)+'\n')
    sys.exit(not result.wasSuccessful())
