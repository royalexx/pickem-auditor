"""Independent genuine forecast public-path and archive acceptance probes."""
from collections import Counter
from datetime import datetime,timezone
import copy
import csv
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from scripts.nba_genuine_s import frozen_inputs
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture import prospective_s_runtime_v1 as runtime
from v2.nba_architecture.prospective_s_archive_v1 import verify_archive,SOURCE_FILES
from v2.nba_c.subset_archive_v1 import READERS
from v2.nba_s_family import model as native

HERE=Path(__file__).resolve().parent;P=HERE.parent;A=P/'corrected_archive';RESULT={};COMMANDS=[]
def command(argv,stem,cwd=ROOT):
    start=datetime.now(timezone.utc).isoformat();child=subprocess.run([str(v) for v in argv],cwd=cwd,capture_output=True)
    (HERE/(stem+'.stdout')).write_bytes(child.stdout);(HERE/(stem+'.stderr')).write_bytes(child.stderr)
    COMMANDS.append(dict(argv=[str(v) for v in argv],cwd=str(cwd),started_at=start,
        completed_at=datetime.now(timezone.utc).isoformat(),exit_code=child.returncode,stdout=stem+'.stdout',stderr=stem+'.stderr'))
    return child
def reseal(value):
    value=copy.deepcopy(value);value.pop('payload_sha256',None);value['payload_sha256']=digest(canonical(value));return canonical(value)

class FinalReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=(A/'forecast.json').read_bytes();cls.forecast=json.loads(cls.raw);cls.manifest=json.loads((A/'manifest.json').read_bytes())
        cls.sha=digest((A/'manifest.json').read_bytes());cls.inputs=dict(frozen_inputs(A),forecast_at=cls.forecast['forecast_at'])
        RESULT.update(tested_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            actual_forecast_implementation_commit=json.loads((P/'forecast_execution/COMMAND.json').read_bytes())['implementation_commit'],
            manifest_raw_sha256=cls.sha,forecast_raw_sha256=digest(cls.raw),forecast_payload_sha256=cls.forecast['payload_sha256'],
            code_raw_sha256={name:digest((ROOT/name).read_bytes()) for name in SOURCE_FILES},new_genuine_forecasts_issued_by_reviewer=0)

    def test_01_actual_public_cli_receipts_full140_coverage_and_clock_chain(self):
        f=self.forecast
        self.assertEqual((f['candidate_denominator'],f['attempt_denominator'],f['forecasted_rows'],f['abstained_rows']),(35,140,56,84))
        self.assertEqual(f['abstention_reasons'],{'P1_SOURCE_ABSTENTION':32,'INSUFFICIENT_PRIOR_APPEARANCES':20,'UNKNOWN_CONDITIONAL_HISTORY_WINDOW':32})
        self.assertEqual((f['source_ready_candidates'],f['source_abstained_candidates'],f['minute_forecasted_candidates']),(27,8,14))
        keys={(r['player_id'],r['team_id'],r['statistic']) for r in f['rows']};self.assertEqual(len(keys),140)
        expected={(r['player_id'],r['team_id'],s) for r in f['cohort']['frozen_candidates'] for s in runtime.STATS};self.assertEqual(keys,expected)
        times=[f['data_cutoff_at'],f['fit_started_at'],f['fit_completed_at'],f['artifact_bytes_verified_at'],
            f['artifact_independently_admitted_at'],f['cohort']['freeze_at'],f['forecast_at'],f['cohort']['start']]
        self.assertEqual(list(map(runtime.minutes.utc,times)),sorted(map(runtime.minutes.utc,times)))
        self.assertLess(runtime.minutes.utc(times[-2]),runtime.minutes.utc(times[-1]))
        for row in f['rows']:
            self.assertIsNone(row['participation_probability']);self.assertIsNone(row['legal_eligibility'])
        self.assertFalse(f['minute_uncertainty_integrated']);self.assertFalse(f['team_allocation_performed'])
        self.assertFalse(f['accuracy_validated']);self.assertFalse(f['full_G1_accepted']);self.assertFalse(f['production_release'])
        self.assertEqual((A/'forecast.json').read_bytes(),(P/'actual_forecast/forecast.json').read_bytes())
        original=json.loads((P/'forecast_execution/COMMAND.json').read_bytes());repair=json.loads((P/'archive_repair_execution/COMMAND.json').read_bytes())
        self.assertEqual(original['exit_code'],0);self.assertNotIn('--forecast-at',original['command'])
        self.assertFalse(repair['new_forecast_issued']);self.assertEqual(repair['exit_code'],0)
        self.assertEqual(len(self.manifest['files']),165)
        for name,ref in self.manifest['files'].items():self.assertEqual(digest((A/name).read_bytes()),ref['sha256'])
        RESULT['coverage']=dict(candidates=35,attempts=140,genuine_laws=56,abstentions=84,source_abstentions=32,
            insufficient_history=20,unknown_history=32,supported_players=14,archive_files_rehashed=165)
        RESULT['clock_chain']=times

    def test_02_public_reader_observes_native_execution_and_exact_M0_binding(self):
        original=runtime.minutes.MinutesModel.forecast
        with (patch.object(native,'predict_conditional',wraps=native.predict_conditional) as s_calls,
             patch.object(runtime.minutes.MinutesModel,'forecast',autospec=True,side_effect=original) as m_calls):
            result=runtime.read_forecasts(self.raw,**self.inputs)
        self.assertEqual(s_calls.call_count,56);self.assertEqual(m_calls.call_count,14);self.assertEqual(result,self.forecast)
        minutes={(r['player_id'],r['team_id']):r for r in result['minutes']}
        for row in result['rows']:
            if row['forecast']:
                m=minutes[(row['player_id'],row['team_id'])]['forecast'];b=row['binding']
                self.assertEqual(b['projected_exposure'],m['expected_minutes_given_played']);self.assertEqual(b['p3_forecast_id'],m['forecast_id'])
                self.assertEqual(b['p3_variant'],'M0');self.assertTrue(row['forecast']['actual_native_model_executed'])
        for m in minutes.values():
            wanted='401910021' if m['team_id']=='espn:team:16' else '401910019'
            self.assertIn(wanted,{r['game_id'] for r in m['unobserved_intervening_scheduled_games']})
        RESULT['observed_native_calls']=dict(S_predict_conditional=s_calls.call_count,M0_forecast=m_calls.call_count)

    def test_03_all56_numeric_laws_against_independent_gamma_poisson_and_triplets(self):
        checks=[];csv_rows=[]
        for row in self.forecast['rows']:
            record=dict(player=row['name'],player_id=row['player_id'],statistic=row['statistic'],status=row['status'],reason=row['reason'],
                M0_minutes=None,posterior_mean=None,retained_support_mean=None,tail_mass_upper_bound=None)
            if row['forecast']:
                f=row['forecast'];p=f['parameters'];support=p['support'];mass=[r['mass'] for r in support];exposure=row['binding']['projected_exposure']
                self.assertEqual([r['value'] for r in support],list(range(len(support))))
                self.assertTrue(all(math.isfinite(v) and v>=0 for v in mass));self.assertAlmostEqual(math.fsum(mass),1.,places=12)
                self.assertLess(p['tail_mass_upper_bound'],1e-10)
                artifact=json.loads((A/'inputs/models'/(row['statistic']+'.json')).read_bytes());history=artifact['training_rows'];role=f['trained_role']
                own=[r for r in history if r['player_id']==row['player_id']];peers=[r for r in history if r['player_id']!=row['player_id'] and r['role']==role]
                rate=math.fsum(r['count'] for r in peers)/math.fsum(r['minutes'] for r in peers)
                alpha=180*max(rate,1e-10)+math.fsum(r['count'] for r in own);beta=180+math.fsum(r['minutes'] for r in own)
                self.assertAlmostEqual(p['alpha'],alpha,places=12);self.assertAlmostEqual(p['beta'],beta,places=12)
                independent=[math.exp(math.lgamma(k+alpha)-math.lgamma(alpha)-math.lgamma(k+1)+alpha*math.log(beta/(beta+exposure))+k*math.log(exposure/(beta+exposure))) for k in range(len(mass))]
                norm=math.fsum(independent);error=max(abs(a-b/norm) for a,b in zip(mass,independent));self.assertLess(error,1e-10)
                mean=math.fsum(i*v for i,v in enumerate(mass));fullmean=alpha/beta*exposure;self.assertLess(abs(mean-fullmean),1e-8)
                for line in (0.,.5,5.,5.5,20.):
                    expected=dict(over=math.fsum(r['mass'] for r in support if r['value']>line),under=math.fsum(r['mass'] for r in support if r['value']<line),push=math.fsum(r['mass'] for r in support if r['value']==line))
                    actual=native.exact_triplet(mass,line)
                    for key,value in expected.items():self.assertAlmostEqual(actual[key],value,places=12)
                checks.append(dict(player_id=row['player_id'],statistic=row['statistic'],max_pmf_abs_error=error,mean_abs_error=abs(mean-fullmean)))
                record.update(M0_minutes=exposure,posterior_mean=fullmean,retained_support_mean=mean,tail_mass_upper_bound=p['tail_mass_upper_bound'])
            csv_rows.append(record)
        with (HERE/'INDEPENDENT_FORECAST_CHECKS.csv').open('w') as out:
            writer=csv.DictWriter(out,fieldnames=list(csv_rows[0]),lineterminator=chr(10));writer.writeheader();writer.writerows(csv_rows)
        RESULT['numeric_checks']=checks

    def test_04_public_cli_verified_replay_and_cold_original_repository_denial(self):
        child=command([sys.executable,ROOT/'scripts/nba_genuine_s.py','replay-archive',A,'--expected-manifest-sha256',self.sha],'public_replay')
        self.assertEqual(child.returncode,0,child.stderr.decode());result=json.loads(child.stdout)
        self.assertEqual(result['status'],'VERIFIED_OFFLINE_REPLAY');self.assertEqual(result['forecasted_rows'],56);self.assertFalse(result['new_forecast_issued'])
        with tempfile.TemporaryDirectory() as tmp:
            cold=command([sys.executable,'-I','-B',HERE/'cold_recompute.py',A,ROOT],'cold_recompute',Path(tmp))
        self.assertEqual(cold.returncode,0,cold.stderr.decode());r=json.loads(cold.stdout)
        self.assertEqual(r['payload_sha256'],self.forecast['payload_sha256']);self.assertEqual(r['forecasted_rows'],56);self.assertFalse(r['new_forecast_issued'])
        RESULT['public_verified_replay']=result;RESULT['cold_recompute']=r

    def test_05_resealed_output_clock_and_population_mutations_reject(self):
        for attack in ('drop','duplicate','q','legal','mass','role','variant','completeness'):
            value=copy.deepcopy(self.forecast)
            if attack=='drop':value['rows'].pop()
            elif attack=='duplicate':value['rows'].append(copy.deepcopy(value['rows'][0]))
            elif attack=='q':value['rows'][0]['participation_probability']=1.
            elif attack=='legal':value['rows'][0]['legal_eligibility']=True
            elif attack=='mass':next(r for r in value['rows'] if r['forecast'])['forecast']['parameters']['support'][0]['mass']+=.01
            elif attack=='role':next(r for r in value['rows'] if r['forecast'])['forecast']['trained_role']='invented'
            elif attack=='variant':next(r for r in value['rows'] if r['forecast'])['binding']['p3_variant']='M2'
            elif attack=='completeness':value['correction_history_complete']=True
            with self.subTest(attack=attack),self.assertRaises(ValueError):runtime.read_forecasts(reseal(value),**self.inputs)
        for at in ('2026-11-20T01:00Z','2026-11-20T05:00Z','2026-11-22T01:00Z'):
            with self.subTest(forecast_at=at),self.assertRaises(ValueError):runtime.run_forecasts(**dict(self.inputs,forecast_at=at))
        for attack in ('drop','duplicate','target','team','freeze'):
            inputs=copy.deepcopy(self.inputs);cohort=inputs['cohort']
            if attack=='drop':cohort['frozen_candidates'].pop()
            elif attack=='duplicate':cohort['frozen_candidates'].append(copy.deepcopy(cohort['frozen_candidates'][0]))
            elif attack=='target':cohort['game_id']='401910019'
            elif attack=='team':cohort['frozen_candidates'][0]['team_id']='espn:team:9'
            elif attack=='freeze':cohort['freeze_at']='2026-11-20T01:00Z'
            with self.subTest(cohort_attack=attack),self.assertRaises(ValueError):runtime.run_forecasts(**inputs)

    def test_06_all_archive_code_schema_domain_count_clock_and_object_attacks_reject(self):
        attacks=('cli','registry','reader_drop','count','forecast_clock','production','schema','extra_key','domain','ref_key','ref_bool_size','nested_manifest','missing_file','model_resealed','forecast_resealed','source_resealed')
        outcomes=[]
        for attack in attacks:
            with self.subTest(attack=attack),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'archive';shutil.copytree(A,root);m=json.loads((root/'manifest.json').read_bytes())
                def file_update(name,raw):
                    (root/name).write_bytes(raw);m['files'][name]['sha256']=digest(raw);m['files'][name]['bytes']=len(raw)
                if attack in ('cli','registry'):
                    name='reader/'+('scripts/nba_genuine_s.py' if attack=='cli' else 'v2/nba_architecture/prospective_s_admission_v1.py');file_update(name,(root/name).read_bytes()+b'\n# rehashed alteration\n')
                elif attack=='reader_drop':name='reader/v2/nba_architecture/prospective_s_admission_v1.py';(root/name).unlink();m['files'].pop(name)
                elif attack=='count':m['forecasted_rows']+=1
                elif attack=='forecast_clock':m['forecast_at']='2026-11-20T01:00Z'
                elif attack=='production':m['production_release']=True
                elif attack=='schema':m['schema']='unknown'
                elif attack=='extra_key':m['approved']=True
                elif attack=='domain':next(iter(m['files'].values()))['byte_domain']='FALSE_UNREVIEWED_DOMAIN'
                elif attack=='ref_key':next(iter(m['files'].values()))['approved']=True
                elif attack=='ref_bool_size':next(iter(m['files'].values()))['bytes']=False
                elif attack=='nested_manifest':(root/'inputs/extra').mkdir();(root/'inputs/extra/manifest.json').write_text('{}')
                elif attack=='missing_file':(root/'inputs/models/points.json').unlink()
                elif attack=='model_resealed':name='inputs/models/points.json';file_update(name,(root/name).read_bytes()+b' ')
                elif attack=='forecast_resealed':
                    value=json.loads((root/'forecast.json').read_bytes());value['rows'].pop();raw=reseal(value);file_update('forecast.json',raw);m['payload_sha256']=json.loads(raw)['payload_sha256']
                elif attack=='source_resealed':
                    name='inputs/raw/summary-401910007/body.raw';raw=(root/name).read_bytes()+b' ';file_update(name,raw)
                    name='inputs/raw/summary-401910007/receipt.json';r=json.loads((root/name).read_bytes());r['raw_sha256']=digest(raw);r['bytes']=len(raw);file_update(name,canonical(r))
                raw=canonical(m);(root/'manifest.json').write_bytes(raw)
                with self.assertRaises((ValueError,OSError)) as captured:verify_archive(root,expected_manifest_sha256=digest(raw))
                outcomes.append(dict(attack=attack,rejected=True,error=str(captured.exception)))
        RESULT['archive_mutations']=outcomes

    def test_07_actual_cli_rejected_batch_retains140_and_existing_output_is_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);raw=root/'raw';shutil.copytree(A/'inputs/raw',raw)
            file=raw/'summary-401910007/body.raw';file.write_bytes(file.read_bytes()+b' ')
            args=[sys.executable,ROOT/'scripts/nba_genuine_s.py','forecast']
            for key,value in self.inputs.items():
                if key in ('cohort','forecast_at'):continue
                args.extend(['--'+key.replace('_','-'),str(raw if key=='raw_dir' else value)])
            args.extend(['--cohort-path',str(A/'inputs/cohort.json'),'--output',str(root/'rejected-output')])
            child=command(args,'rejected_batch');self.assertNotEqual(child.returncode,0)
            result=json.loads(child.stdout);self.assertEqual((result['candidate_denominator'],result['attempt_denominator'],result['rejected_rows']),(35,140,140))
            self.assertEqual(result['forecasted_rows'],0);self.assertFalse((root/'rejected-output').exists())
            self.assertTrue(all(r['status']=='REJECTED_BATCH' and r['forecast'] is None for r in result['rows']))
            RESULT['rejected_batch']=dict(candidate_denominator=35,attempt_denominator=140,rejected_rows=140,forecasted_rows=0,error=result['error'])
        before=digest((A/'manifest.json').read_bytes());args=[sys.executable,ROOT/'scripts/nba_genuine_s.py','forecast']
        for key,value in self.inputs.items():
            if key not in ('cohort','forecast_at'):args.extend(['--'+key.replace('_','-'),str(value)])
        args.extend(['--cohort-path',str(A/'inputs/cohort.json'),'--output',str(A)])
        child=command(args,'existing_output');self.assertNotEqual(child.returncode,0);self.assertIn(b'GENUINE_FORECAST_OUTPUT_ALREADY_EXISTS',child.stderr)
        self.assertEqual(digest((A/'manifest.json').read_bytes()),before)

    def test_08_old_twenty_readers_and_original_forecast_source_bytes_remain_unchanged(self):
        paths=list(READERS)+['v2/nba_architecture/subset_p2_dispatch_v1.py','v2/nba_c/subset_dispatch_archive_v1.py','scripts/nba_subset_p2_dispatch.py']
        for name in paths:
            with self.subTest(path=name):self.assertEqual(subprocess.check_output(['git','show','a4493ac7:'+name],cwd=ROOT),(ROOT/name).read_bytes())
        for name in ('forecast.json','inputs/cohort.json','inputs/models/fit_receipt.json','inputs/models/points.json','inputs/models/rebounds.json','inputs/models/assists.json','inputs/models/threes.json'):
            self.assertEqual((A/name).read_bytes(),(P/'actual_forecast'/name).read_bytes())
        RESULT['old_twenty_readers_unchanged']=paths


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FinalReview))
    RESULT.update(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),completed_at=datetime.now(timezone.utc).isoformat())
    (HERE/'RESULTS.json').write_text(json.dumps(RESULT,indent=2,sort_keys=True)+'\n')
    (HERE/'COMMANDS.json').write_text(json.dumps(dict(commands=COMMANDS),indent=2)+'\n')
    sys.exit(not result.wasSuccessful())
