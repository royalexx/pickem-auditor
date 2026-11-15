"""Numerical/adversarial fixtures only; never counted as prospective forecasts."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from v2 import nfl_volume_distributions as v

NOW='2026-11-15T16:30:00Z'
FREEZE='2026-11-15T16:20:00Z'


def player(market='receiving_targets',position='WR'):
    return dict(player_stat_id='stat',player_id='gsis:00-0000001',player='Fixture only',
        game_id='target',normalized_market=market,period='full_game',position=position,
        event_start_at='2026-11-15T18:00:00Z',model_input_ready=True,
        abstention_reasons=[],identity_source_sha256='a'*64,role_source_sha256='b'*64,
        eligibility_status='EXPECTED_STARTER' if position=='QB' else 'ROLE_UNCERTAINTY',
        confirmed_game_day_active=False,missing_stat_rows=0)


def history(market='receiving_targets',values=(0,1,4)):
    return [dict(player_stat_id='stat',player_id='gsis:00-0000001',game_id=f'old{i}',
        game_date=f'2026-10-{i+1:02}',market=market,period='full_game',value=y,
        source_available_at='2026-11-14T00:00:00Z',source_sha256='a'*64,
        components={v.FIELDS[market][0]:y,**{k:0 for k in v.FIELDS[market][1:]}}) for i,y in enumerate(values)]


def contract(d,line):
    return dict(player_stat_id=d['player_stat_id'],normalized_market=d['normalized_market'],
        original_source_manifest_sha256=v.OLD_SHA,
        original_record=dict(event_id=d['game_id'],period=d['period'],source_certified=True,
            book='fixture',source_sha256='a'*64,source_received_at=FREEZE,
            line=line,candidate_id='c',quote_id='q'))


class VolumeTests(unittest.TestCase):
    def test_eleven_markets_and_only_combined_defense(self):
        self.assertEqual(len(v.FIELDS),11)
        for m in ('solo_tackles','assisted_tackles','sacks','touchdowns','interceptions'):
            with self.assertRaisesRegex(ValueError,'UNAPPROVED'):
                v.validate_value(m,{'value':0,'components':{}})

    def test_all_markets_support(self):
        for m in v.FIELDS:
            with self.subTest(market=m):
                h=history(m)
                if m=='tackles_assists':
                    with self.assertRaisesRegex(ValueError,'TACKLE_ACCOUNTING'):
                        v.validate_value(m,h[0])
                    continue
                for r in h: self.assertEqual(v.validate_value(m,r),r['value'])
                d=v.distribution(player(m),h,v.EW,NOW,FREEZE)
                self.assertAlmostEqual(sum(p for _,p in d['pmf']),1)
                self.assertGreaterEqual(d['predictive_variance'],0)

    def test_signed_yards_and_nonnegative_counts(self):
        for m in v.FIELDS:
            if m=='tackles_assists':continue
            h=history(m,(-8,0,11))
            if m.endswith('yards'):
                self.assertEqual(v.validate_value(m,h[0]),-8)
            else:
                with self.assertRaisesRegex(ValueError,'NEGATIVE_COUNT'):v.validate_value(m,h[0])

    def test_missing_never_zero(self):
        for bad in (None,'',float('nan'),float('inf'),True,1.5):
            h=history(); h[0]['components']['targets']=bad
            with self.subTest(bad=bad),self.assertRaises(ValueError):v.validate_value('receiving_targets',h[0])
        self.assertEqual(v.validate_value('receiving_targets',history()[0]),0)

    def test_zero_mass_and_exact_pushes(self):
        d=v.distribution(player(),history(),v.UNIFORM,NOW,FREEZE)
        self.assertAlmostEqual(d['zero_mass'],1/3)
        for line in (-1,0,.5,1,2,4,20):
            c=v.contract_probabilities(d,contract(d,line),NOW)
            self.assertAlmostEqual(c['q_over']+c['q_under']+c['q_push'],1)
            self.assertAlmostEqual(c['q_push'],1/3 if line in (0,1,4) else 0)

    def test_dependence_and_exact_composite_identity(self):
        for m in ('rushing_receiving_yards','passing_rushing_yards'):
            h=history(m,(10,10,10)); keys=v.FIELDS[m]
            for r,x in zip(h,(0,5,10)):r['components']={keys[0]:x,keys[1]:10-x}
            d=v.distribution(player(m),h,v.UNIFORM,NOW,FREEZE)
            self.assertEqual(d['predictive_mean'],10)
            self.assertEqual(d['predictive_variance'],0)
            self.assertEqual(d['dependence'],'same_game_source_pair')
            for r in d['joint_outcomes']:self.assertEqual(sum(r['components'].values()),r['value'])
            h[0]['value']=11
            with self.assertRaisesRegex(ValueError,'COMPONENT_IDENTITY'):v.validate_value(m,h[0])

    def test_frozen_s2_recency_math(self):
        d=v.distribution(player(),history(),v.EW,NOW,FREEZE)
        w=[2**(-2/4),2**(-1/4),1]
        self.assertAlmostEqual(d['predictive_mean'],sum(a*b for a,b in zip((0,1,4),w))/sum(w))

    def test_uniform_benchmark_math(self):
        d=v.distribution(player(),history(),v.UNIFORM,NOW,FREEZE)
        self.assertAlmostEqual(d['predictive_mean'],5/3)
        self.assertAlmostEqual(d['predictive_variance'],26/9)

    def test_reproducibility_and_fingerprints(self):
        d=v.distribution(player(),history(),v.EW,NOW,FREEZE)
        self.assertEqual(d,v.distribution(player(),history(),v.EW,NOW,FREEZE))
        h=history();h[-1]['value']=h[-1]['components']['targets']=5
        e=v.distribution(player(),h,v.EW,NOW,FREEZE)
        self.assertNotEqual(d['model_input_fingerprint'],e['model_input_fingerprint'])
        self.assertNotEqual(d['distribution_sha256'],e['distribution_sha256'])
        self.assertEqual(len(d['model_input_fingerprint']),64)

    def test_threshold_never_refits(self):
        d=v.distribution(player(),history(),v.EW,NOW,FREEZE)
        a=v.contract_probabilities(d,contract(d,1),NOW)
        b=v.contract_probabilities(d,contract(d,2),NOW)
        self.assertEqual(a['distribution_sha256'],b['distribution_sha256'])

    def test_wrong_contract_identity_and_time(self):
        d=v.distribution(player(),history(),v.EW,NOW,FREEZE)
        for mutate in (lambda c:c.update(player_stat_id='other'),
                       lambda c:c['original_record'].update(event_id='other'),
                       lambda c:c['original_record'].update(source_received_at='2026-11-15T19:00:00Z'),
                       lambda c:c['original_record'].update(line=None),
                       lambda c:c['original_record'].update(source_certified=False)):
            c=contract(d,1);mutate(c)
            with self.assertRaises((ValueError,TypeError)):v.contract_probabilities(d,c,NOW)

    def test_qb1_and_historical_starter_only(self):
        p=player('rush_attempts','QB');h=history('rush_attempts')
        starters={(r['game_id'],p['player_id']) for r in h}
        self.assertEqual(len(v.select_history(p,h,FREEZE,NOW,starters)[0]),3)
        p['eligibility_status']='BACKUP'
        with self.assertRaisesRegex(ValueError,'QB_NOT_SOURCE'):v.select_history(p,h,FREEZE,NOW,starters)
        p['eligibility_status']='EXPECTED_STARTER'
        with self.assertRaisesRegex(ValueError,'INSUFFICIENT_SOURCE_ROLE'):v.select_history(p,h,FREEZE,NOW,set())

    def test_no_leakage_or_duplicates(self):
        for mutate in (lambda h:h.append(copy.deepcopy(h[0])),
                       lambda h:h[0].update(game_date='2026-11-15'),
                       lambda h:h[0].update(game_id='target'),
                       lambda h:h[0].update(player_id='wrong'),
                       lambda h:h[0].update(source_available_at='2026-11-15T17:00:00Z')):
            h=history();mutate(h)
            with self.assertRaises(ValueError):v.select_history(player(),h,FREEZE,NOW,set())

    def test_timing_naive_and_kickoff(self):
        with self.assertRaisesRegex(ValueError,'NAIVE'):v.stamp('2026-11-15T16:00:00')
        with self.assertRaisesRegex(ValueError,'KICKOFF'):v.select_history(player(),history(),FREEZE,'2026-11-15T18:00:00Z',set())
        with self.assertRaisesRegex(ValueError,'FUTURE_FREEZE'):v.select_history(player(),history(),FREEZE,'2026-11-15T16:00:00Z',set())

    def test_not_ready_and_unbound_player(self):
        p=player();p['model_input_ready']=False;p['abstention_reasons']=['INACTIVE']
        with self.assertRaisesRegex(ValueError,'INACTIVE'):v.select_history(p,history(),FREEZE,NOW,set())
        p=player();p['identity_source_sha256']=None
        with self.assertRaisesRegex(ValueError,'UNBOUND'):v.select_history(p,history(),FREEZE,NOW,set())

    def test_exact_bytes_and_path_escape(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'a').write_bytes(b'real\n')
            ref=dict(path='a',sha256=hashlib.sha256(b'real\n').hexdigest())
            self.assertEqual(v.bound(root,ref),b'real\n')
            (root/'a').write_bytes(b'real')
            with self.assertRaisesRegex(ValueError,'SHA256'):v.bound(root,ref)
            with self.assertRaisesRegex(ValueError,'PATH_ESCAPE'):v.bound(root,dict(path='../a',sha256='a'))

    def test_no_clobber(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x';v.write_once(p,b'first')
            with self.assertRaises(FileExistsError):v.write_once(p,b'second')
            self.assertEqual(p.read_bytes(),b'first')

    def test_unavailable_model_cannot_be_activated(self):
        for model in v.UNAVAILABLE:
            with self.assertRaisesRegex(ValueError,'MODEL_NOT_ACTIVATED'):
                v.distribution(player(),history(),model,NOW,FREEZE)


class RawSourceTests(unittest.TestCase):
    def packet(self,root,*,targets=3,receptions=2,attempts=12,components=None,at='2026-11-14T00:00:00Z'):
        def put(name,obj,gz=False):
            import gzip
            raw=v.canonical(obj)
            if gz:raw=gzip.compress(raw,mtime=0)
            (root/name).write_bytes(raw)
            return dict(path=name,sha256=v.sha(raw),source_available_at=at)
        g=dict(game_id='old0',gameday='2026-10-01',home_qb_id='00-0000001',away_qb_id='00-0000002')
        stats=dict(player_id='00-0000001',game_id='old0',team='A',targets=targets,receptions=receptions,
                   attempts=attempts,completions=2)
        gr=put('games.gz',dict(rows=[g]),True);sr=put('stats.gz',dict(rows=[stats]),True)
        er=put('eligibility',{})
        archive='reports/nfl_20261115_prospective'
        (root/archive).mkdir(parents=True)
        (root/archive/'eligibility').write_bytes((root/'eligibility').read_bytes())
        original=dict(sources={'roster':dict(sha256=er['sha256'],archive_path='eligibility',source_received_at=at)})
        old=put('old',original)
        pin=dict(source_evidence=[gr,sr],previous_canonical_manifest=old,feature_freeze_at=FREEZE)
        p=player();p['identity_source_sha256']=er['sha256'];p['role_source_sha256']=None
        h=history(values=(targets,))[0];h['source_sha256']=sr['sha256']
        if components is not None:h['components']=components
        return pin,[p],[h]

    def test_raw_target_opportunity_and_zero_verification(self):
        for target in (0,3):
            with tempfile.TemporaryDirectory() as td:
                root=Path(td);packet=self.packet(root,targets=target,receptions=min(target,2))
                starters,audit=v.verify_sources(root,*packet)
                self.assertEqual(audit['target_opportunity_checks'],1)
                self.assertIn(('old0','gsis:00-0000001'),starters)

    def test_receptions_cannot_exceed_official_targets(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);packet=self.packet(root,targets=1,receptions=2)
            with self.assertRaisesRegex(ValueError,'RECEPTIONS_TARGETS'):v.verify_sources(root,*packet)

    def test_targets_cannot_exceed_verified_pass_opportunities(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);packet=self.packet(root,targets=14)
            with self.assertRaisesRegex(ValueError,'TARGETS_PASSING'):v.verify_sources(root,*packet)

    def test_missing_exposure_disclosed_without_invented_rate_model(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);packet=self.packet(root,attempts=None)
            _,audit=v.verify_sources(root,*packet)
            self.assertEqual(audit['target_exposure_unavailable'],1)
            self.assertEqual(audit['target_opportunity_checks'],0)

    def test_raw_component_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);packet=self.packet(root,components={'targets':7})
            with self.assertRaisesRegex(ValueError,'RAW_COMPONENT'):v.verify_sources(root,*packet)

    def test_raw_source_after_freeze_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);packet=self.packet(root,at='2026-11-15T17:00:00Z')
            with self.assertRaisesRegex(ValueError,'RAW_SOURCE_AFTER'):v.verify_sources(root,*packet)

if __name__=='__main__':unittest.main()

