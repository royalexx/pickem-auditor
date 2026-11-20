"""Independent exact artifact replication and model diagnostics; no scores."""
from collections import Counter
from datetime import datetime,timezone
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest,export_requests
from v2.nba_architecture.prospective_s_sources_v1 import build_dataset,POSITIONS
from v2.nba_architecture import prospective_s_runtime_v1 as runtime
from v2.nba_s_family import model as native

HERE=Path(__file__).resolve().parent;P=HERE.parent;F=P/'fitted';R=P/'raw'
RESULT={}

class ArtifactReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.approval=json.loads((P/'independent_prefit/PREFIT_APPROVAL.json').read_bytes())
        cls.receipt=json.loads((F/'fit_receipt.json').read_bytes())
        cls.data=build_dataset(R,P/'PREFIT_POPULATION.json',P/'policy/nba_rule5.raw')
        RESULT.update(tested_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            verification_started_at=datetime.now(timezone.utc).isoformat(),fit_receipt_raw_sha256=digest((F/'fit_receipt.json').read_bytes()),
            prefit_approval_raw_sha256=digest((P/'independent_prefit/PREFIT_APPROVAL.json').read_bytes()),
            source_dataset_raw_sha256=digest(canonical(cls.data)),source_dataset_payload_sha256=cls.data['payload_sha256'],artifacts={})

    def test_01_approved_activation_receipt_actual_clocks_and_all_saved_hashes(self):
        prior=subprocess.check_output(['git','show','ef360a88:v2/nba_s_family/prospective_fit_v1.py'],cwd=ROOT)
        active=(ROOT/'v2/nba_s_family/prospective_fit_v1.py').read_bytes()
        expected=prior.replace(b'PREFIT_APPROVAL_SHA=None',b"PREFIT_APPROVAL_SHA='"+RESULT['prefit_approval_raw_sha256'].encode()+b"'")
        expected=expected.replace(b'APPROVED_READER_SHA=None',b"APPROVED_READER_SHA='"+self.approval['source_reader_raw_sha256'].encode()+b"'")
        expected=expected.replace(b'APPROVED_DATASET_SHA=None',b"APPROVED_DATASET_SHA='"+self.approval['dataset_payload_sha256'].encode()+b"'")
        self.assertEqual(active,expected);self.assertEqual(digest(active),self.receipt['fit_code_sha256'])
        self.assertEqual(subprocess.check_output(['git','show','2e2bab62:v2/nba_s_family/prospective_fit_v1.py'],cwd=ROOT),active)
        self.assertEqual(self.receipt['implementation_commit'],'2e2bab6220636ad93d1dd18a03daa0d323f31770')
        self.assertEqual(self.receipt['prefit_approval_raw_sha256'],RESULT['prefit_approval_raw_sha256'])
        execution=json.loads((P/'fit_execution/COMMAND.json').read_bytes())
        self.assertEqual(execution['exit_code'],0)
        times=[self.approval['decided_at'],execution['started_at'],self.receipt['fit_started_at'],
            self.receipt['fit_completed_at'],self.receipt['artifact_bytes_verified_at'],execution['completed_at']]
        self.assertEqual(list(map(runtime.minutes.utc,times)),sorted(map(runtime.minutes.utc,times)))
        self.assertLessEqual(runtime.minutes.utc(self.data['data_cutoff_at']),runtime.minutes.utc(times[2]))
        self.assertEqual(json.loads((P/'fit_execution/stdout').read_bytes()),self.receipt)
        self.assertEqual((P/'fit_execution/stderr').read_bytes(),b'')
        self.assertEqual(self.receipt['fixed_hyperparameters'],self.approval['fixed_hyperparameters'])
        self.assertEqual(self.receipt['seed'],20261120)
        for flag in ('holdout_scoring','tuning','weight_optimization','nuts','production_release'):self.assertFalse(self.receipt[flag])
        checks=0
        for line in (F/'SHA256SUMS').read_text().splitlines():
            expected,name=line.split('  ',1);self.assertEqual(digest((F/name).read_bytes()),expected);checks+=1
        RESULT['fit_files_independently_rehashed']=checks;RESULT['actual_fit_clocks']=dict(zip(
            ('prefit_decided','execution_started','fit_started','fit_completed','artifact_verified','execution_completed'),times))

    def test_02_rebuild_each_native_artifact_byte_for_byte_from_original_sources(self):
        self.assertEqual((F/'source_dataset.json').read_bytes(),canonical(self.data))
        self.assertEqual((F/'source_manifest.json').read_bytes(),canonical(self.data['source_manifest']))
        self.assertEqual((F/'raw_sources.json').read_bytes(),canonical(self.data['raw_sources']))
        with patch.object(native,'fit',wraps=native.fit) as calls:
            for stat in ('points','rebounds','assists','threes'):
                replay=native.fit(self.data['histories'][stat],asof_cutoff_utc=self.data['data_cutoff_at'],
                    source_manifest=self.data['source_manifest'],stat=stat,family='S1',
                    hyperparameters=self.approval['fixed_hyperparameters'],seed=self.approval['seed'])
                raw=(F/(stat+'.json')).read_bytes();self.assertEqual(replay.payload,raw)
                value=json.loads(raw);self.assertEqual(digest(raw),self.receipt['artifacts'][stat]['sha256'])
                self.assertEqual(value['family'],'S1');self.assertEqual(value['stat'],stat)
                self.assertEqual(value['training_cutoff_at'],self.data['data_cutoff_at'])
                self.assertEqual(len(value['training_rows']),456)
                self.assertEqual(value['code_sha256'],self.approval['native_S_code_raw_sha256'])
                self.assertEqual(value['hyperparameters'],self.approval['fixed_hyperparameters'])
                self.assertTrue(all(row['game_id']!='espn:game:'+self.data['target']['game_id'] for row in value['training_rows']))
                RESULT['artifacts'][stat]=dict(sha256=digest(raw),bytes=len(raw),training_rows=456,
                    observed_role_counts=dict(Counter(r['role'] for r in value['training_rows'])),byte_identical_native_reconstruction=True)
        self.assertEqual(calls.call_count,4);RESULT['native_fit_verification_replays']=calls.call_count
        RESULT['replay_qualification']='Four in-memory deterministic construction replays of the admitted candidate, not a second model selection or published fit batch.'

    def test_03_independent_gamma_poisson_math_and_support_diagnostics(self):
        candidate=self.data['frozen_candidates'][0];pid=candidate['player_id'];tid=candidate['team_id'].removeprefix('espn:team:')
        roster=json.loads((R/('roster-'+tid)/'body.raw').read_bytes());person=next(p for p in roster['athletes'] if 'espn:player:'+str(p['id'])==pid)
        role='ESPN_POSITION_BIN_AT_CAPTURE:'+POSITIONS[person['position']['abbreviation']]
        diagnostics={}
        for stat in ('points','rebounds','assists','threes'):
            fitted=native.FittedS((F/(stat+'.json')).read_bytes());rows=fitted.data['training_rows']
            own=[r for r in rows if r['player_id']==pid];peers=[r for r in rows if r['player_id']!=pid and r['role']==role]
            peer_rate=math.fsum(r['count'] for r in peers)/math.fsum(r['minutes'] for r in peers)
            alpha=180*max(peer_rate,1e-10)+math.fsum(r['count'] for r in own);beta=180+math.fsum(r['minutes'] for r in own)
            prediction=native.predict_conditional(fitted,player_id=pid,role=role,projected_exposure=20.,statistic=stat)
            self.assertIsNone(prediction.abstain_reason);p=prediction.parameters
            self.assertAlmostEqual(p['alpha'],alpha,places=12);self.assertAlmostEqual(p['beta'],beta,places=12)
            support=p['support'];actual=[r['mass'] for r in support]
            self.assertEqual([r['value'] for r in support],list(range(len(support))))
            self.assertTrue(all(math.isfinite(v) and v>=0 for v in actual));self.assertAlmostEqual(math.fsum(actual),1.,places=12)
            independent=[math.exp(math.lgamma(k+alpha)-math.lgamma(alpha)-math.lgamma(k+1)+
                alpha*math.log(beta/(beta+20.))+k*math.log(20./(beta+20.))) for k in range(len(support))]
            total=math.fsum(independent);independent=[p/total for p in independent]
            error=max(abs(a-b) for a,b in zip(actual,independent));self.assertLess(error,1e-10)
            for line in (0.,.5,10.,10.5):
                triplet=native.exact_triplet(actual,line)
                expected=dict(over=math.fsum(r['mass'] for r in support if r['value']>line),
                    under=math.fsum(r['mass'] for r in support if r['value']<line),push=math.fsum(r['mass'] for r in support if r['value']==line))
                for key,value in expected.items():self.assertAlmostEqual(triplet[key],value,places=12)
            diagnostics[stat]=dict(player_id=pid,observed_peer_position_bin=role,fixed_diagnostic_exposure=20.,
                alpha=alpha,beta=beta,independent_pmf_max_abs_error=error,tail_mass_upper_bound=p['tail_mass_upper_bound'])
        RESULT['native_diagnostics']=dict(qualification='Fixed20minute artifact diagnostics only; no source-M0 forecast or target forecast issued.',statistics=diagnostics)

    def test_04_uncompleted_intervening_counterexample_and_repaired_minutes_control(self):
        spec=json.loads((P/'PREFIT_POPULATION.json').read_bytes());at=datetime.now(timezone.utc).isoformat()
        cohort=dict(self.data['target'],freeze_at=at,frozen_candidates=self.data['frozen_candidates'])
        handoff=export_requests(R,cohort)
        model=SimpleNamespace(training_cutoff_at='2026-11-01T00:00:00Z',forecast=lambda *args,**kwargs:{'SYNTHETIC_M0_PROTOCOL_STUB':True})
        with patch.object(runtime,'_load_model',return_value=model):
            rows,_=runtime._minutes_rows(self.data,handoff,R,P/'PREFIT_POPULATION.json',cohort,P/'unused-model',at)
        found={}
        for row in rows:
            tid=row['team_id'].removeprefix('espn:team:');expected='401910021' if tid=='16' else '401910019'
            self.assertIn(expected,{g['game_id'] for g in row['unobserved_intervening_scheduled_games']})
            found[tid]=row['unobserved_intervening_scheduled_games']
        prior={}
        for tid in spec['target']['teams']:
            schedule=json.loads((R/('schedule-'+tid)/'body.raw').read_bytes())
            prior[tid]=[e['id'] for e in schedule['events'] if runtime.minutes.utc(spec['data_cutoff_at'])<=runtime.minutes.utc(e['date'])<runtime.minutes.utc(spec['target']['start'])]
            self.assertEqual(prior[tid],[])
        RESULT['intervening_game_control']=dict(qualification='Native M0 model mocked; no forecast issued.',old_cutoff_filter_result=prior,repaired_result=found)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ArtifactReview))
    RESULT.update(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),
        verification_completed_at=datetime.now(timezone.utc).isoformat(),genuine_forecasts_issued_during_review=0)
    (HERE/'ARTIFACT_RESULTS.json').write_text(json.dumps(RESULT,indent=2,sort_keys=True)+'\n')
    sys.exit(not result.wasSuccessful())
