"""Quarantine contradictory nonparticipation; never erase source credits."""
import copy
import hashlib
import json
import tempfile
import unittest
from tests.nba_architecture.test_p1_history import make_entry,build
from tests.nba_architecture.test_p1_remediation import (
    official_fixture,repair_opponent,NBA_GAME,NBA_TEAMS,
)
from v2.nba_architecture.v2_contracts import canonical
from v2.nba_architecture.p1_evidence import adjudicate_player
from v2.nba_architecture.p1_handoff import export_prior_game
from v2.nba_architecture.p1_vault import OfficialOutcomeVault


def bundle(played='0',stats=None,exact='PT00M00S'):
    b=official_fixture();g=json.loads(b['raw']);person=g['game']['homeTeam']['players'][0]
    person['statistics']=dict(stats or {})
    if exact is not None:person['statistics']['minutes']=exact
    if played is None:person.pop('played',None)
    else:person['played']=played
    b['raw']=canonical(g);b['capture']['raw_sha256']=hashlib.sha256(b['raw']).hexdigest()
    return b


def entry(status='dnp',minutes=None,stats=None):
    return repair_opponent(make_entry(game=NBA_GAME,player='nba:player:7',team=NBA_TEAMS[0],status=status,minutes=minutes,stats={} if stats is None else stats))


def data(**kwargs):
    return json.loads(entry(**kwargs)['record']['payload'])


def native(d,b):
    return export_prior_game(d,b,ingested_at='2026-11-16T19:00:00Z',source_profile='synthetic_engineering')


class NonparticipationSourceBoundaries(unittest.TestCase):
    def test_native_rejects_caller_nonplayed_minutes_or_credits(self):
        for status in ('dnp','unknown'):
            for minutes,stats in ((0,{}),(None,{'points':1}),(None,{'points':True})):
                with self.subTest(status=status,minutes=minutes,stats=stats),self.assertRaises(ValueError):
                    native(data(status=status,minutes=minutes,stats=stats),bundle())

    def test_native_rejects_invalid_participation_and_played_numeric_types(self):
        for status in ('DNP','banana',True,None):
            with self.subTest(status=status),self.assertRaises(ValueError):native(data(status=status),bundle())
        for minutes in (True,float('inf'),float('nan'),-1):
            # Direct adversary bypasses normalized JSON construction for NaN/Inf.
            d=data(status='played',minutes=0);d['minutes']=minutes
            with self.subTest(minutes=minutes),self.assertRaises(ValueError):native(d,bundle(played='1'))

    def test_raw_nonplayed_positive_credit_or_exposure_quarantines(self):
        for status,played in (('dnp','0'),('unknown',None)):
            for raw in (bundle(played,{'points':1}),bundle(played,{},'PT00M00.0000000000000000001S')):
                with self.subTest(status=status,raw=raw['raw']),self.assertRaisesRegex(ValueError,'NONPARTICIPATION_CREDIT_UNRESOLVED'):
                    native(data(status=status),raw)

    def test_unknown_must_not_mask_explicit_played_or_invalid_source_status(self):
        for played in ('1','0','banana'):
            with self.subTest(played=played),self.assertRaisesRegex(ValueError,'PARTICIPATION_CONFLICT'):
                native(data(status='unknown'),bundle(played=played))

    def test_valid_dnp_unknown_and_played_zero_stay_distinct(self):
        for status,played,expected in (('dnp','0','NONPARTICIPATION_OR_UNKNOWN'),('unknown',None,'NONPARTICIPATION_OR_UNKNOWN'),('unknown','unknown','NONPARTICIPATION_OR_UNKNOWN')):
            p=native(data(status=status),bundle(played=played,stats={'points':0}))
            self.assertEqual(p['exposure']['participation'],status)
            self.assertIsNone(p['exposure']['displayed_minutes']);self.assertIsNone(p['exposure']['exact_minutes'])
            self.assertEqual(p['exposure']['accounting_status'],expected)
        p=native(data(status='played',minutes=0),bundle(played='1'))
        self.assertEqual(p['exposure']['participation'],'played');self.assertEqual(p['exposure']['exact_minutes'],0)

    def test_true_zero_raw_credits_cannot_hide_behind_omitted_retained_stats(self):
        d=data(status='played',minutes=0,stats={})
        with self.assertRaisesRegex(ValueError,'ZERO_MINUTE_CREDIT_UNRESOLVED'):
            native(d,bundle(played='1',stats={'points':1}))

    def test_historical_builder_raw_nonplayed_credit_quarantines(self):
        with self.assertRaisesRegex(ValueError,'NONPARTICIPATION_CREDIT_UNRESOLVED'):
            build([entry()],team_ids=NBA_TEAMS,official_game_evidence={NBA_GAME:bundle(stats={'points':1})},require_official_evidence=True)
        p=build([entry()],team_ids=NBA_TEAMS,official_game_evidence={NBA_GAME:bundle()},require_official_evidence=True)
        self.assertEqual(p['players'][0]['availability'],'unknown')

    def test_vault_raw_dnp_credit_rejects_and_valid_zero_source_persists(self):
        args=dict(game_id=NBA_GAME,player_id='nba:player:7',team_id=NBA_TEAMS[0],state='DNP',minutes=None,stats={},source_id='nba:official:box',observed_at='2026-11-16T19:00:00Z',official_status='FINAL')
        with tempfile.TemporaryDirectory() as td:
            v=OfficialOutcomeVault(td);b=bundle(stats={'points':1})
            with self.assertRaisesRegex(ValueError,'NONPARTICIPATION_CREDIT_UNRESOLVED'):
                v.append(**args,source_bytes=b['raw'],official_game_evidence=b)
            self.assertEqual(v.records(),[])
            b=bundle();v.append(**args,source_bytes=b['raw'],official_game_evidence=b)
            self.assertEqual(v.latest(NBA_GAME,'nba:player:7')['state'],'DNP')
