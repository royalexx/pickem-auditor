"""NHL settlement must use final official game/player identifiers, not name search."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import population_history as hist
import settle as st

DATE="2026-11-05"
GID="2026020211"
def observation(*,pid="8480001",team="BOS",opponent="MTL",stat="shots on goal",value=3):
    return hist.make(sport="NHL",stat=stat,game_id=GID,game_date=DATE,
                     season="2026",player_id=pid,
                     position="G" if stat=="saves" else "F",
                     team=team,opponent=opponent,home=False,
                     value=value,workload=18.5,workload_unit="minutes",
                     source_url="https://api-web.nhle.com/v1/gamecenter/"+GID+"/boxscore",
                     source_sha256="a"*64)

def snapshot(**updates):
    r={"game_date":DATE,"sport":"NHL","stat":"shots on goal",
       "player":"Official Test Player","player_id":"8480001",
       "team":"BOS","opponent":"MTL","event_id":GID,
       "event_id_namespace":"nhl","side":"over",
       "reference_line":2.5,"actual_stat":None,"outcome":None}
    r.update(updates)
    return r

class OfficialNHLSettlementTests(unittest.TestCase):
    def make_pool(self,root,records):
        local=root/"data/live_pool_staging/populations"/(DATE+".jsonl")
        local.parent.mkdir(parents=True)
        local.write_text("".join(json.dumps(record)+"\n" for record in records),
                         encoding="utf-8")
        receipt=root/"reports"/("live_population_collect_"+DATE+".json")
        receipt.parent.mkdir(parents=True)
        receipt.write_text(json.dumps({"game_date":DATE,"status":"complete",
            "completed_games":{"NHL":1},
            "sports":{"NHL":{"games":1,"rows":len(records)}},"errors":{}}))
        return local

    def test_id_and_fixture_verified_with_both_bet_sides(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.make_pool(root,[observation()])
            def forbidden_fetch(*args,**kwargs):
                self.fail("Should never use name-search or network when official local rows exist")
            fetchers=st.default_fetchers(fetch=forbidden_fetch,root=root)
            rows=[snapshot(side="over"),snapshot(side="under")]
            settled,n=st.settle_rows(rows,as_of="2026-11-06",fetchers=fetchers)
            self.assertEqual(n,2)
            self.assertEqual([r["actual_stat"] for r in settled],[3.,3.])
            self.assertEqual([r["outcome"] for r in settled],["win","loss"])
            self.assertEqual(fetchers.lookup_record(snapshot()),3.)

    def test_identity_mismatch_and_dnp_remain_unsettled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.make_pool(root,[observation()])
            fetchers=st.default_fetchers(fetch=lambda *a,**kw: None,root=root)
            invalid=[snapshot(player_id="not-the-player"),
                     snapshot(team="MTL",opponent="BOS"),
                     snapshot(event_id="2026020999",event_id_namespace="nhl"),
                     snapshot(player_id=None),
                     snapshot(stat="saves"),
                     snapshot(team=None)]
            output,count=st.settle_rows(invalid,as_of="2026-11-06",fetchers=fetchers)
            self.assertEqual(count,0)
            self.assertTrue(all(r.get("actual_stat") is None for r in output))

    def test_verified_zero_saves_is_settled_but_missing_goalie_is_not_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.make_pool(root,[observation(pid="8480002",stat="saves",value=0)])
            fetchers=st.default_fetchers(fetch=lambda *a,**kw: None,root=root)
            r=snapshot(player_id="8480002",stat="goalie saves",side="under",
                       reference_line=0.5)
            output,count=st.settle_rows([r],as_of="2026-11-06",fetchers=fetchers)
            self.assertEqual(count,1)
            self.assertEqual(output[0]["actual_stat"],0.)
            self.assertEqual(output[0]["outcome"],"win")
            self.assertIsNone(fetchers.lookup_record(snapshot(player_id="8480003",stat="goalie saves")))

    def test_local_incomplete_source_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.make_pool(root,[observation()])
            rec=root/"reports"/("live_population_collect_"+DATE+".json")
            j=json.loads(rec.read_text());j["errors"]={"NHL":"incomplete"}
            rec.write_text(json.dumps(j))
            fetchers=st.default_fetchers(fetch=lambda *a,**kw: None,root=root)
            with self.assertRaisesRegex(ValueError,"LOCAL_COMPLETED_SOURCE_NOT_VERIFIED"):
                fetchers.lookup_record(snapshot())

    def test_missing_population_uses_official_completed_gamecenter_not_player_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            gid=int(GID)
            players=[{"playerId":8480001+i,"toi":"12:00",
                      "hits":1,"blockedShots":0,"sog":3} for i in range(10)]
            raw={"id":gid,"gameDate":DATE,"gameState":"OFF",
                 "awayTeam":{"abbrev":"BOS"},"homeTeam":{"abbrev":"MTL"},
                 "playerByGameStats":{"awayTeam":{"forwards":players,
                   "defense":[],"goalies":[]},"homeTeam":{"forwards":[],
                   "defense":[],"goalies":[]}}}
            requested=[]
            def fake_fetch(url,**kwargs):
                requested.append(url)
                if url.endswith("/score/"+DATE):
                    return {"games":[{"gameType":2,"gameState":"OFF","id":gid}]}
                if url.endswith("/gamecenter/"+GID+"/boxscore"):
                    return raw
                self.fail("Unexpected or legacy NHL endpoint "+url)
            fetchers=st.default_fetchers(fetch=fake_fetch,root=root)
            result=fetchers.lookup_record(snapshot())
            self.assertEqual(result,3.)
            self.assertEqual(len(requested),2)
            self.assertFalse(any("/search/player" in u or "/game-log/" in u for u in requested))

if __name__=="__main__":
    unittest.main()
