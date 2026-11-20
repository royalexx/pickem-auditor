"""Real frozen source/artifact paths, replay and deliberate admission attacks."""
import copy
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from scripts.nba_genuine_s import frozen_inputs
from v2.nba_architecture.p1_subset_handoff_v1 import canonical, digest
from v2.nba_architecture.prospective_s_runtime_v1 import run_forecasts, read_forecasts, verify_bundle
from v2.nba_architecture.prospective_s_archive_v1 import verify_archive
from v2.nba_s_family.model import exact_triplet

PACK=Path(__file__).resolve().parents[2]/'docs/nba_architecture/genuine_s_prospective_20261120'
ARCHIVE=PACK/'corrected_archive'


class GenuineProspectiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=(ARCHIVE/'forecast.json').read_bytes()
        cls.result=json.loads(cls.raw)
        cls.inputs=dict(frozen_inputs(ARCHIVE),forecast_at=cls.result['forecast_at'])

    def test_real_public_source_to_fitted_S_path_keeps_every_candidate_attempt_and_unknown(self):
        result=read_forecasts(self.raw,**self.inputs)
        self.assertEqual((result['candidate_denominator'],result['attempt_denominator']),(35,140))
        self.assertGreater(result['forecasted_rows'],0)
        self.assertEqual(result['forecasted_rows']+result['abstained_rows'],140)
        self.assertEqual({r['statistic'] for r in result['rows'] if r['forecast']},
            {'points','rebounds','assists','threes'})
        self.assertEqual((result['source_ready_candidates'],result['source_abstained_candidates']),(27,8))
        self.assertEqual((result['source_observation_denominator'],result['training_attempt_denominator'],
            result['included_training_attempts'],result['excluded_training_attempts']),(698,2792,1824,968))
        self.assertTrue(all(r['participation_probability'] is None and r['legal_eligibility'] is None for r in result['rows']))
        self.assertFalse(result['minute_uncertainty_integrated'])
        self.assertFalse(result['accuracy_validated']);self.assertFalse(result['production_release'])
        self.assertTrue(any(r['unobserved_intervening_scheduled_games'] for r in result['minutes']))
        for team,gid in [('espn:team:29','401910019'),('espn:team:16','401910021')]:
            self.assertTrue(all(gid in {g['game_id'] for g in r['unobserved_intervening_scheduled_games']}
                for r in result['minutes'] if r['team_id']==team))
        for r in result['rows']:
            if r['forecast']:
                self.assertTrue(r['forecast']['actual_native_model_executed'])
                self.assertTrue(r['forecast']['trained_role'].startswith('ESPN_POSITION_BIN_AT_CAPTURE:'))

    def test_actual_numeric_laws_have_integer_support_bounded_tail_and_exact_triplets(self):
        for row in self.result['rows']:
            if not row['forecast']:continue
            p=row['forecast']['parameters'];support=p['support'];mass=[a['mass'] for a in support]
            self.assertEqual([a['value'] for a in support],list(range(len(support))))
            self.assertTrue(all(math.isfinite(x) and x>=0 for x in mass))
            self.assertAlmostEqual(math.fsum(mass),1.,places=12)
            self.assertLessEqual(p['tail_mass_upper_bound'],1e-10)
            for line in (0.,.5,5.,5.5,20.):
                triplet=exact_triplet(mass,line)
                self.assertAlmostEqual(sum(triplet.values()),1.,places=12)
                if line%1:self.assertEqual(triplet['push'],0.)

    def test_changed_population_target_late_freeze_and_forged_decision_do_not_admit(self):
        for attack in ('missing-player','duplicate-player','wrong-team','wrong-game','late-freeze'):
            inputs=copy.deepcopy(self.inputs);cohort=inputs['cohort']
            if attack=='missing-player':cohort['frozen_candidates'].pop()
            if attack=='duplicate-player':cohort['frozen_candidates'].append(copy.deepcopy(cohort['frozen_candidates'][0]))
            if attack=='wrong-team':cohort['frozen_candidates'][0]['team_id']='espn:team:9'
            if attack=='wrong-game':cohort['game_id']='401910019'
            if attack=='late-freeze':cohort['freeze_at']='2026-11-22T02:00Z'
            with self.subTest(attack=attack),self.assertRaises(ValueError):run_forecasts(**inputs)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'approved.json';path.write_bytes(canonical(dict(approved=True,reviewer='independent',
                complete_roster=True,source_authentic=True)))
            inputs=dict(self.inputs,prefit_path=path)
            with self.assertRaises(ValueError):run_forecasts(**inputs)

    def test_model_source_and_resealed_output_mutations_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);shutil.copytree(ARCHIVE/'inputs/models',path/'models')
            inputs=dict(self.inputs,model_dir=path/'models')
            artifact=path/'models/points.json';artifact.write_bytes(artifact.read_bytes()+b' ')
            with self.assertRaises(ValueError):run_forecasts(**inputs)
        for attack in ('delete-rejected','fake-q','alter-probability','false-completeness'):
            value=copy.deepcopy(self.result)
            if attack=='delete-rejected':value['rows']=[r for r in value['rows'] if r['forecast']]
            if attack=='fake-q':value['rows'][0]['participation_probability']=1.
            if attack=='alter-probability':
                next(r for r in value['rows'] if r['forecast'])['forecast']['parameters']['support'][0]['mass']+=.01
            if attack=='false-completeness':value['correction_history_complete']=True
            value.pop('payload_sha256');value['payload_sha256']=digest(canonical(value))
            with self.subTest(attack=attack),self.assertRaises(ValueError):read_forecasts(canonical(value),**self.inputs)

    def test_archive_public_path_runs_with_isolated_reader_and_original_paths_unavailable(self):
        sha=digest((ARCHIVE/'manifest.json').read_bytes())
        result=verify_archive(ARCHIVE,expected_manifest_sha256=sha)
        self.assertEqual(result['status'],'VERIFIED_OFFLINE_REPLAY')
        self.assertEqual(result['forecasted_rows'],self.result['forecasted_rows'])
        self.assertFalse(result['new_forecast_issued'])
        with self.assertRaises(ValueError):verify_archive(ARCHIVE,expected_manifest_sha256='0'*64)

    def test_resealed_reader_registry_and_manifest_coverage_cannot_appoint_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'archive';shutil.copytree(ARCHIVE,root)
            original=(root/'manifest.json').read_bytes()
            for name in ('reader/scripts/nba_genuine_s.py','reader/v2/nba_architecture/prospective_s_admission_v1.py'):
                path=root/name;before=path.read_bytes();path.write_bytes(before+b'\n# forged code\n')
                manifest=json.loads(original);manifest['files'][name].update(sha256=digest(path.read_bytes()),bytes=path.stat().st_size)
                raw=canonical(manifest);(root/'manifest.json').write_bytes(raw)
                with self.subTest(name=name),self.assertRaisesRegex(ValueError,'UNREVIEWED_READER_BYTES'):
                    verify_archive(root,expected_manifest_sha256=digest(raw))
                path.write_bytes(before)
            manifest=json.loads(original);manifest['forecasted_rows']=140;manifest['abstained_rows']=0
            raw=canonical(manifest);(root/'manifest.json').write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'REPLAY_DENOMINATOR_JOIN'):
                verify_archive(root,expected_manifest_sha256=digest(raw))

    def test_nested_manifest_and_false_byte_domain_do_not_escape_archive_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'archive';shutil.copytree(ARCHIVE,root)
            original=(root/'manifest.json').read_bytes()
            extra=root/'inputs/extra/manifest.json';extra.parent.mkdir();extra.write_bytes(b'{}')
            with self.assertRaisesRegex(ValueError,'FILE_POPULATION'):
                verify_archive(root,expected_manifest_sha256=digest(original))
            extra.unlink();extra.parent.rmdir()
            manifest=json.loads(original);next(iter(manifest['files'].values()))['byte_domain']='FALSE_UNREVIEWED_DOMAIN'
            raw=canonical(manifest);(root/'manifest.json').write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'FILE_REFERENCE_SCHEMA'):
                verify_archive(root,expected_manifest_sha256=digest(raw))

    def test_public_cli_rejected_source_batch_retains_140_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);shutil.copytree(ARCHIVE/'inputs/raw',p/'raw')
            body=p/'raw/roster-16/body.raw';value=json.loads(body.read_bytes());value['athletes'].pop();body.write_bytes(canonical(value))
            args=[sys.executable,'scripts/nba_genuine_s.py','forecast']
            inputs=dict(self.inputs,raw_dir=p/'raw')
            for name in ('raw_dir','spec_path','policy_path','model_dir','prefit_path','admission_path','model_path'):
                args.extend(['--'+name.replace('_','-'),str(inputs[name])])
            args.extend(['--cohort-path',str(ARCHIVE/'inputs/cohort.json'),'--output',str(p/'output')])
            child=subprocess.run(args,capture_output=True,text=True,cwd=PACK.parents[2])
            self.assertNotEqual(child.returncode,0)
            rejected=json.loads(child.stdout)
            self.assertEqual((rejected['candidate_denominator'],rejected['attempt_denominator'],rejected['rejected_rows']),(35,140,140))
            self.assertEqual(rejected['forecasted_rows'],0)
            self.assertFalse((p/'output').exists())

    def test_live_cli_rejects_same_archive_destination_without_overwriting(self):
        args=[sys.executable,'scripts/nba_genuine_s.py','forecast']
        for name in ('raw_dir','spec_path','policy_path','model_dir','prefit_path','admission_path','model_path'):
            args.extend(['--'+name.replace('_','-'),str(self.inputs[name])])
        args.extend(['--cohort-path',str(ARCHIVE/'inputs/cohort.json'),'--output',str(ARCHIVE)])
        child=subprocess.run(args,capture_output=True,text=True,cwd=PACK.parents[2])
        self.assertNotEqual(child.returncode,0)
        self.assertIn('GENUINE_FORECAST_OUTPUT_ALREADY_EXISTS',child.stderr)
