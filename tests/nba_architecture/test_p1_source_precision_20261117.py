"""Exact rational physical decisions on synthetic official-shaped raw clocks."""
import hashlib
import json
from decimal import localcontext
from fractions import Fraction
import tempfile
import unittest

from tests.nba_architecture.test_p1_remediation import (
    official_fixture,nba_entry,repair_opponent,official_build,NBA_GAME,NBA_TEAMS,
)
from v2.nba_architecture.p1_evidence import seconds,duration,adjudicate_player
from v2.nba_architecture.p1_handoff import export_prior_game
from v2.nba_architecture.p1_vault import OfficialOutcomeVault
from v2.nba_architecture.v2_contracts import canonical

TINY='0.'+'0'*80+'1'
BELOW_THIRTY='29.'+'9'*80
ABOVE_THIRTY='30.'+'0'*80+'1'


def row(minutes):
    return json.loads(repair_opponent(nba_entry(minutes))['record']['payload'])


class ExactPhysicalClockBoundaries(unittest.TestCase):
    def test_seconds_preserve_positive_sub_decimal_context_increment(self):
        raw='PT48M'+TINY+'S'
        self.assertGreater(seconds(raw),Fraction(48*60))

    def test_raw_over_cap_adjudication_and_native_export_reject(self):
        for ot in (0,2,7):
            cap=48+5*ot;b=official_fixture(ot,cap,exact=f'PT{cap}M{TINY}S')
            for consumer in ('adjudicate','native'):
                with self.subTest(ot=ot,consumer=consumer),self.assertRaisesRegex(ValueError,'PLAYER_MINUTES_EXCEED_GAME_DURATION'):
                    if consumer=='adjudicate':adjudicate_player(row(cap),b)
                    else:export_prior_game(row(cap),b,ingested_at='2026-11-16T19:00:00Z',source_profile='synthetic_engineering')

    def test_builder_rejects_raw_over_cap_without_float_rounding(self):
        for ot in (0,2):
            cap=48+5*ot;b=official_fixture(ot,cap,exact=f'PT{cap}M{TINY}S')
            with self.subTest(ot=ot),self.assertRaisesRegex(ValueError,'PLAYER_MINUTES_EXCEED_GAME_DURATION'):
                official_build(nba_entry(cap),b,require_official_evidence=True)

    def test_vault_rejects_raw_over_cap_before_writing(self):
        for ot in (0,2):
            cap=48+5*ot;b=official_fixture(ot,cap,exact=f'PT{cap}M{TINY}S')
            with tempfile.TemporaryDirectory() as td:
                v=OfficialOutcomeVault(td)
                with self.subTest(ot=ot),self.assertRaisesRegex(ValueError,'PLAYER_MINUTES_EXCEED_GAME_DURATION'):
                    v.append(game_id=NBA_GAME,player_id='nba:player:7',team_id=NBA_TEAMS[0],state='PLAYED',minutes=cap,stats=row(cap)['stats'],source_id='nba:official:box',source_bytes=b['raw'],observed_at='2026-11-16T19:00:00Z',official_status='FINAL',official_game_evidence=b)
                self.assertEqual(v.records(),[])

    def test_rounding_just_below_thirty_seconds_remains_admissible(self):
        b=official_fixture(minutes=0,exact=f'PT00M{BELOW_THIRTY}S')
        d,minutes,status=adjudicate_player(row(0),b)
        self.assertEqual(status,'ADJUDICATED_ROUNDED_SUBMINUTE')
        self.assertEqual(d['duration_minutes'],48)
        self.assertEqual(row(0)['minutes'],0)

    def test_rounding_at_and_above_thirty_seconds_rejects(self):
        for s in ('30',ABOVE_THIRTY):
            with self.subTest(seconds=s),self.assertRaisesRegex(ValueError,'ZERO_MINUTE_CREDIT_UNRESOLVED'):
                adjudicate_player(row(0),official_fixture(minutes=0,exact=f'PT00M{s}S'))

    def test_display_difference_must_not_round_to_half_minute(self):
        for display,raw in ((48,f'PT47M{BELOW_THIRTY}S'),(47,f'PT47M{ABOVE_THIRTY}S')):
            with self.subTest(display=display),self.assertRaisesRegex(ValueError,'OFFICIAL_MINUTE_CONFLICT'):
                adjudicate_player(row(display),official_fixture(minutes=display,exact=raw))

    def test_exact_legal_controls_and_decimal_context_independence(self):
        for precision in (6,28,120):
            with localcontext() as ctx:
                ctx.prec=precision
                for ot in (0,2,7):
                    cap=48+5*ot
                    d,minutes,status=adjudicate_player(row(cap),official_fixture(ot,cap))
                    self.assertEqual((d['duration_minutes'],minutes,status),(cap,float(cap),'OFFICIAL_BOX_RECONCILED'))
                # Equality in the ordinary display tolerance is deliberately legal.
                self.assertEqual(adjudicate_player(row(48),official_fixture(minutes=48,exact='PT47M30S'))[1],47.5)

    def test_final_clock_positive_raw_increment_is_not_zero(self):
        b=official_fixture();g=json.loads(b['raw']);g['game']['gameClock']='PT00M'+TINY+'S'
        b['raw']=canonical(g);b['capture']['raw_sha256']=hashlib.sha256(b['raw']).hexdigest()
        with self.assertRaisesRegex(ValueError,'OFFICIAL_FINAL_CLOCK_CONFLICT'):
            duration(b,game_id=NBA_GAME)
