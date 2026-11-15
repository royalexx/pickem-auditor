import json
import sys
from pathlib import Path
import unittest
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import nfl_sunday_market_extension as m

def test_all_eleven_mappings():
    for key in m.FIELDS: assert m.market(key)==key
    assert len(m.FIELDS)==11

def test_frozen_eight_compatibility():
    for old,new in m.MIGRATION.items(): assert m.market(old)==new

def test_specialty_and_defensive_exclusions():
    for key in sorted(m.DENIED|{'touchdowns','longest reception','passing efficiency','field goals'}):
        with unittest.TestCase().assertRaises(ValueError):m.market(key)

def test_signed_composites_and_missing_zero():
    r={'passing_yards':200,'rushing_yards':-4,'receiving_yards':0}
    assert m.value(r,'passing_rushing_yards')==196
    assert m.value(r,'rushing_receiving_yards')==-4
    assert m.value({'rushing_yards':0},'rushing_receiving_yards') is None
    assert m.value({'rushing_yards':0,'receiving_yards':None},'rushing_receiving_yards') is None
    assert m.value({'rushing_yards':0,'receiving_yards':0},'rushing_receiving_yards')==0
    assert m.value({'def_tackles_solo':3,'def_tackles_with_assist':2,'def_tackle_assists':2},'tackles_assists')==7

def test_same_game_pairing_and_conflicts():
    a={'gsis_id':'00-0036963','game_id':'A','rushing_yards':4}
    b={'gsis_id':'00-0036963','game_id':'B','receiving_yards':5}
    assert all(m.value(r,'rushing_receiving_yards') is None for r in m.unique_history([a,b]))
    assert len(m.unique_history([a,a]))==1
    with unittest.TestCase().assertRaises(ValueError):m.unique_history([a,{**a,'rushing_yards':5}])

def test_source_chronology():
    r={'game_date':'2026-11-08','source_available_at':'2026-11-15T14:00:00Z'}
    assert m.history_valid(r,'2026-11-15T16:00:00Z')
    assert not m.history_valid({**r,'game_date':'2026-11-15'},'2026-11-15T16:00:00Z')
    assert not m.history_valid(r,'2026-11-15T13:00:00Z')
    with unittest.TestCase().assertRaises(ValueError):m.history_valid({**r,'source_available_at':'2026-11-15T13:00:00'},'2026-11-15T16:00:00Z')

def test_namespace_and_roles():
    with unittest.TestCase().assertRaises(ValueError):m.identity('4374302')
    assert m.identity('00-0036963')=='gsis:00-0036963'
    for key in m.FIELDS:
        assert not m.eligible('QB',key,False,True)
    assert m.eligible('QB','passing_rushing_yards',True,False)
    assert not m.eligible('WR','rush_attempts',False,False)
    assert m.eligible('WR','rush_attempts',False,True)
    assert not m.eligible('LB','pass_attempts',False,True)

def test_hash_and_immutable_write():
    tmp=TemporaryDirectory()
    tmp_path=Path(tmp.name)
    p=tmp_path/'source';b=b'original bytes\n'
    m.unchanged(p,b)
    assert m.verified(p,m.sha(b))==b
    with unittest.TestCase().assertRaises(ValueError):m.verified(p,'0'*64)
    with unittest.TestCase().assertRaises(ValueError):m.unchanged(p,b'changed')
    assert p.read_bytes()==b
    tmp.cleanup()

def test_single_writer_lease():
    original=m.ROOT
    with TemporaryDirectory() as directory:
        m.ROOT=Path(directory)
        try:
            out=m.ROOT/'market_extension_v2_5_1';out.mkdir()
            (out/'.ws1_extension.lock').write_text('already running')
            with unittest.TestCase().assertRaisesRegex(RuntimeError,'ALREADY_RUNNING'):m.build()
        finally:m.ROOT=original


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(v) for k,v in globals().items() if k.startswith("test_") and callable(v))

if __name__=="__main__":unittest.main()
