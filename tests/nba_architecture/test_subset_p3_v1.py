import copy
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest,export_requests
from v2.nba_architecture.subset_p3_v1 import run_p3,read_p3,MODEL_SHA,NATIVE_SHA

ROOT=Path(__file__).resolve().parents[2]
PACKET=ROOT/'docs/nba_architecture/p1_p5_handoffs_20261119'
CAP=ROOT/'docs/nba_architecture/p1_subset_acceptance_20261119/initial_tonight_capture'
COHORT=json.loads((PACKET/'PROSPECTIVE_COHORT.json').read_bytes())
HISTORY=PACKET/'prospective_inputs'
MODEL=ROOT/'research/nba_ws2/results/model.json'
# Replay the actual original native probe clock; never claim a new live forecast.
AT=json.loads((PACKET/'p3_initial_native_probe.json').read_bytes())['forecast_at']


class P3SubsetTests(unittest.TestCase):
    def run_model(self,history=HISTORY,model=MODEL,cohort=COHORT,at=AT,capture=CAP):
        source=canonical(export_requests(capture,cohort))
        return run_p3(source,capture,cohort,history_dir=history,model_path=model,forecast_at=at)

    def reseal(self,folder,body=None,receipt=None):
        b=folder/'body.raw';r=folder/'receipt.json'
        if body is not None:b.write_bytes(canonical(body))
        value=json.loads(r.read_bytes())
        value.update(raw_sha256=digest(b.read_bytes()),bytes=len(b.read_bytes()))
        if receipt:value.update(receipt)
        r.write_bytes(canonical(value))

    def latest(self,history,tid='29'):
        events=json.loads((history/('selected-'+tid+'.json')).read_bytes())
        return history/('summary-'+max(events,key=lambda e:e['date'])['id'])

    def test_actual_public_native_forecasts_and_complete_denominators(self):
        x=self.run_model();self.assertEqual((x['candidate_denominator'],x['attempt_denominator'],x['forecasted_rows'],x['abstained_rows'],x['observation_denominator']),(36,108,36,72,540))
        self.assertEqual(x['model_raw_sha256'],MODEL_SHA);self.assertEqual(x['native_reader_raw_sha256'],NATIVE_SHA)
        self.assertEqual(len({(r['player_id'],r['model']) for r in x['rows']}),108)
        for row in x['rows']:
            self.assertIsNone(row['participation_probability']);self.assertIsNone(row['legal_eligibility'])
            if row['forecast']:
                f=row['forecast'];self.assertIsNone(f['participation_probability']);self.assertIsNone(f['active_roster_eligible'])
                self.assertGreater(f['expected_minutes_given_played'],0)
                self.assertIn('UNCONDITIONAL_OPPORTUNITY_UNAVAILABLE',f['abstention_reasons'])
                self.assertEqual(len(f['role']['features']),13);self.assertEqual(f['scenario_ids'],[])
        source=canonical(export_requests(CAP,COHORT))
        self.assertEqual(read_p3(canonical(x),source_raw=source,capture_dir=CAP,cohort=COHORT,history_dir=HISTORY,model_path=MODEL,forecast_at=AT),x)

    def test_missing_player_and_zero_display_are_unknown_not_dnp(self):
        for attack in ('missing','zero'):
            with self.subTest(attack=attack),tempfile.TemporaryDirectory() as tmp:
                h=Path(tmp)/'history';shutil.copytree(HISTORY,h);folder=self.latest(h)
                b=json.loads((folder/'body.raw').read_bytes());team=next(t for t in b['boxscore']['players'] if t['team']['id']=='29');s=team['statistics'][0]
                target=next(a for a in s['athletes'] if a['athlete']['id']=='5041935')
                if attack=='missing':s['athletes'].remove(target)
                else:target['didNotPlay']=False;target['stats'][s['names'].index('MIN')]='0'
                self.reseal(folder,body=b);x=self.run_model(h)
                rows=[r for r in x['rows'] if r['player_id']=='espn:player:5041935']
                self.assertTrue(all(r['reason']=='UNKNOWN_RETURN_GAP_POPULATION' for r in rows))
                self.assertEqual(x['attempt_denominator'],108)
                observations=[r for r in x['observations'] if r['player_id']=='espn:player:5041935']
                self.assertEqual(observations[-1]['state'],'UNKNOWN' if attack=='missing' else 'PLAYED_ZERO_DISPLAY')

    def test_rehashed_identity_game_duplicate_and_body_attacks(self):
        for attack in ('game','team','duplicate','bytes'):
            with self.subTest(attack=attack),tempfile.TemporaryDirectory() as tmp:
                h=Path(tmp)/'history';shutil.copytree(HISTORY,h);folder=self.latest(h);b=json.loads((folder/'body.raw').read_bytes())
                if attack=='game':b['header']['id']='wrong'
                if attack=='team':b['boxscore']['players'][0]['team']['id']='wrong'
                if attack=='duplicate':
                    a=b['boxscore']['players'][0]['statistics'][0]['athletes'];a.append(copy.deepcopy(a[0]))
                if attack=='bytes':(folder/'body.raw').write_bytes((folder/'body.raw').read_bytes()+b' ')
                else:self.reseal(folder,body=b)
                x=self.run_model(h);self.assertIn('29',x['team_errors']);self.assertEqual(x['attempt_denominator'],108)
                self.assertTrue(any(r['forecast'] for r in x['rows'] if r['team_id']=='espn:team:9'))

    def test_missing_intervening_appearance_is_not_silently_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            h=Path(tmp)/'history';shutil.copytree(HISTORY,h)
            events=sorted(json.loads((h/'selected-29.json').read_bytes()),key=lambda e:e['date'])
            folder=h/('summary-'+events[-2]['id']);b=json.loads((folder/'body.raw').read_bytes())
            athletes=next(t for t in b['boxscore']['players'] if t['team']['id']=='29')['statistics'][0]['athletes']
            target=next(a for a in athletes if a['athlete']['id']=='5041935');athletes.remove(target)
            self.reseal(folder,body=b);x=self.run_model(h)
            self.assertTrue(all(r['reason']=='UNKNOWN_CONDITIONAL_HISTORY_WINDOW' for r in x['rows'] if r['player_id']=='espn:player:5041935'))
            self.assertEqual(x['attempt_denominator'],108)

    def test_late_publication_orphan_and_completeness_claims_reject(self):
        for change in [dict(ingested_at='2026-11-19T23:00:00Z'),dict(source_published_at='2026-11-18T00:00:00Z'),dict(predecessor_sha256='0'*64),dict(correction_history_complete=True)]:
            with self.subTest(change=change),tempfile.TemporaryDirectory() as tmp:
                h=Path(tmp)/'history';shutil.copytree(HISTORY,h);self.reseal(self.latest(h),receipt=change)
                x=self.run_model(h);self.assertIn('29',x['team_errors']);self.assertEqual(x['attempt_denominator'],108)

    def test_unreviewed_models_and_future_training_changes_do_not_admit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'model.json';value=json.loads(MODEL.read_bytes());value['training_cutoff_at']='2027-01-01T00:00:00Z';path.write_bytes(canonical(value))
            x=self.run_model(model=path);self.assertEqual(x['forecasted_rows'],0);self.assertEqual(x['abstained_rows'],108)
            self.assertTrue(any('UNREVIEWED_OR_ALTERED_MINUTES_ARTIFACT' in str(r['reason']) for r in x['rows']))

    def test_resealed_forecast_q_identity_drop_and_duplicate_mutations(self):
        x=self.run_model();source=canonical(export_requests(CAP,COHORT))
        for attack in ('q','identity','drop','model','minutes','completeness'):
            v=copy.deepcopy(x)
            if attack=='q':v['rows'][0]['participation_probability']=1.
            if attack=='identity':v['rows'][0]['team_id']='wrong'
            if attack=='drop':v['rows'].pop()
            if attack=='model':v['model_raw_sha256']='0'*64
            if attack=='minutes':v['rows'][0]['forecast']['expected_minutes_given_played']=48.
            if attack=='completeness':v['correction_history_complete']=True
            v.pop('payload_sha256');v['payload_sha256']=digest(canonical(v))
            with self.subTest(attack=attack),self.assertRaises(ValueError):read_p3(canonical(v),source_raw=source,capture_dir=CAP,cohort=COHORT,history_dir=HISTORY,model_path=MODEL,forecast_at=AT)
        for wire in [b'{"forecasted_rows":999,'+canonical(x)[1:],b'{"x":NaN}']:
            with self.assertRaises(ValueError):read_p3(wire,source_raw=source,capture_dir=CAP,cohort=COHORT,history_dir=HISTORY,model_path=MODEL,forecast_at=AT)

    def test_invalid_forecast_clock_or_frozen_population_rejected(self):
        for at in ['2026-11-19T22:00:00Z','2026-11-20T01:00:00Z']:
            with self.assertRaises(ValueError):self.run_model(at=at)
        c=copy.deepcopy(COHORT);c['frozen_candidates'].pop()
        with self.assertRaises(ValueError):self.run_model(cohort=c)

    def test_malformed_receipt_and_position_fail_locally(self):
        for kind in ('null_receipt','null_clock','null_position'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
                h=Path(tmp)/'history';shutil.copytree(HISTORY,h)
                cap=Path(tmp)/'capture';shutil.copytree(CAP,cap)
                if kind=='null_receipt':(self.latest(h)/'receipt.json').write_text('null')
                if kind=='null_clock':self.reseal(self.latest(h),receipt=dict(ingested_at=None))
                if kind=='null_position':
                    folder=cap/'roster-29';b=json.loads((folder/'body.raw').read_bytes());next(a for a in b['athletes'] if a['id']=='5041935')['position']=None;self.reseal(folder,body=b)
                x=self.run_model(history=h,capture=cap);self.assertEqual(x['attempt_denominator'],108)
                self.assertTrue(any(r['forecast'] for r in x['rows'] if r['team_id']=='espn:team:9'))
                if kind=='null_position':self.assertTrue(all(r['reason']=='P3_POSITION_UNAVAILABLE' for r in x['rows'] if r['player_id']=='espn:player:5041935'))

    def test_credited_dnp_and_missing_schedule_game_reject_without_denominator_loss(self):
        for attack in ('credited_dnp','missing_game'):
            with self.subTest(attack=attack),tempfile.TemporaryDirectory() as tmp:
                h=Path(tmp)/'history';shutil.copytree(HISTORY,h)
                if attack=='credited_dnp':
                    folder=self.latest(h);b=json.loads((folder/'body.raw').read_bytes());s=next(t for t in b['boxscore']['players'] if t['team']['id']=='29')['statistics'][0]
                    target=s['athletes'][0];target['didNotPlay']=True;target['stats'][s['names'].index('MIN')]='0';target['stats'][s['names'].index('PTS')]='3'
                else:
                    folder=h/'schedule-29';b=json.loads((folder/'body.raw').read_bytes());b['events'].pop(0)
                self.reseal(folder,body=b);x=self.run_model(h)
                self.assertIn('29',x['team_errors']);self.assertEqual(x['observation_denominator'],540);self.assertEqual(x['attempt_denominator'],108)
                unknown=[r for r in x['observations'] if r['team_id']=='espn:team:29']
                self.assertTrue(all(r['state']=='UNKNOWN' and r['source_rejection'] for r in unknown))
