"""No-network multisport population source, cursor and no-leakage contracts."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import population_history as pop
import population_normalizers as normal
import population_nfl as nfl
import population_backfill as ingest
import joint_population_bayes as model
import joint_population_holdout as audit


def row(*,sport="NBA",stat="points",gid="401",day="2022-10-21",
        player="1",position="PG",value=20,workload=30.,season="2023",opponent="MIA"):
    return pop.make(sport=sport,stat=stat,game_id=gid,game_date=day,
        season=season,player_id=player,position=position,
        team="BOS",opponent=opponent,home=True,value=value,workload=workload,
        workload_unit="minutes" if sport!="NFL" else "snaps",
        source_url="https://example.org/completed-boxscore",
        source_sha256="a"*64)


def nhl_box():
    def skater(pid):
        return {"playerId":pid,"toi":"15:20","sog":2,"hits":1,"blockedShots":3}
    def goalie(pid):
        return {"playerId":pid,"toi":"60:00","saves":26}
    return {"id":2018020001,"gameState":"FINAL",
        "homeTeam":{"abbrev":"BOS"},"awayTeam":{"abbrev":"NYR"},
        "playerByGameStats":{
            side:{"forwards":[skater(base+i) for i in range(12)],
                  "defense":[skater(base+20+i) for i in range(6)],
                  "goalies":[goalie(base+40)]}
            for side,base in (("homeTeam",100),("awayTeam",200))}}


def nba_box():
    def athlete(pid):
        return {"athlete":{"id":str(pid),"position":{"abbreviation":"PG"}},
                "stats":["30:00","25","7","6","3","1","2","4"]}
    labels=["MIN","PTS","REB","AST","3PM","STL","BLK","TO"]
    return {"header":{"season":{"year":2023},"competitions":[{
        "id":"401","competitors":[
            {"homeAway":"home","team":{"abbreviation":"BOS"}},
            {"homeAway":"away","team":{"abbreviation":"MIA"}}]}]},
        "boxscore":{"players":[
            {"team":{"abbreviation":code},"statistics":[{
                "labels":labels,"athletes":[athlete(base+i) for i in range(8)]}]}
            for code,base in (("BOS",100),("MIA",200))]}}


class MultiSportSources(unittest.TestCase):
    def test_supported_families_and_storage_immutability(self):
        self.assertEqual(pop.family("NHL","saves"),"count")
        self.assertEqual(pop.family("NFL","receiving yards"),"continuous")
        self.assertEqual(pop.family("NBA","pra"),"count")
        with self.assertRaisesRegex(ValueError,"unsupported"):
            pop.family("NFL","made up")
        with tempfile.TemporaryDirectory() as d:
            rows=[row(),row(player="2")]
            self.assertEqual(pop.persist(d,rows)["inserted"],2)
            self.assertEqual(pop.persist(d,rows)["already_present"],2)
            self.assertEqual(len(pop.read(d,sport="NBA",stat="points",before="2022-10-22")),2)
            # A future season shard cannot erase an earlier-as-of training
            # window simply because max_seasons=1 is requested.
            pop.persist(d,[row(gid="2025",day="2025-10-21",season="2026",
                player="99",value=30)])
            early=pop.read(d,sport="NBA",stat="points",
                           before="2022-10-22",max_seasons=1)
            self.assertEqual(len(early),2)
            self.assertEqual(pop.read(d,sport="NBA",stat="points",before="2022-10-21"),[])
            with self.assertRaisesRegex(ValueError,"IMMUTABLE_POPULATION"):
                pop.persist(d,[dict(rows[0],value=21)])
            self.assertEqual(len(pop.read(d,sport="NBA",stat="points",
                                     before="2022-10-22")),2)

    def test_nhl_four_volume_stats_and_goalie_position(self):
        rows=normal.nhl_game(nhl_box(),"2018-10-01")
        counts={s:sum(x["stat"]==s for x in rows) for s in pop.COUNT["NHL"]}
        self.assertEqual(counts,{"shots on goal":36,"hits":36,
                                 "blocked shots":36,"saves":2})
        self.assertTrue(all(r["workload"]>0 for r in rows))
        self.assertTrue(all(r["position"]=="G" for r in rows if r["stat"]=="saves"))
        bad=nhl_box()
        bad["playerByGameStats"]["homeTeam"]["forwards"][0].pop("hits")
        parsed=normal.nhl_game(bad,"2018-10-01")
        self.assertEqual(sum(r["stat"]=="hits" for r in parsed),35)
        bad=nhl_box();bad["gameState"]="LIVE"
        with self.assertRaisesRegex(ValueError,"uncompleted"):
            normal.nhl_game(bad,"2018-10-01")

    def test_nba_minutes_and_combinations(self):
        rows=normal.nba_game(nba_box(),"2022-10-21","401")
        self.assertEqual(len({r["player_id"] for r in rows}),16)
        representative=[r for r in rows if r["player_id"]=="100"]
        metrics={r["stat"]:r["value"] for r in representative}
        self.assertEqual(metrics["pra"],38)
        self.assertEqual(metrics["pr"],32)
        self.assertEqual(metrics["pa"],31)
        self.assertEqual(metrics["ra"],13)
        self.assertEqual(metrics["turnovers"],4)
        self.assertEqual(representative[0]["workload"],30)
        with self.assertRaisesRegex(ValueError,"espn_game_id_mismatch"):
            normal.nba_game(nba_box(),"2022-10-21","402")

    def test_nfl_real_snaps_no_fabricated_workload(self):
        schedule=[{"game_id":"2022_01_BUF_LAR","season":2022,"week":1,"game_type":"REG",
                   "gameday":"2022-09-08","away_team":"BUF","home_team":"LAR"}]
        weekly=[{"season":2022,"week":1,"season_type":"REG","recent_team":"BUF",
                 "opponent_team":"LAR","position":"WR","player_id":"abc123",
                 "player_display_name":"John Smith","targets":9,"receptions":5,
                 "receiving_yards":-3.,"receiving_tds":1}]
        snaps=[{"game_id":"2022_01_BUF_LAR","season":2022,"week":1,"game_type":"REG",
                "team":"BUF","opponent":"LAR","player":"John Smith",
                "offense_snaps":58}]
        rows,coverage=nfl.normalize_season(weekly,snaps,schedule,2022,cutoff="2022-09-09")
        self.assertEqual(coverage["eligible_player_rows"],1)
        self.assertEqual({r["stat"] for r in rows},
                         {"targets","receptions","receiving yards","receiving touchdowns"})
        self.assertEqual(next(r["value"] for r in rows if r["stat"]=="receiving yards"),-3.)
        self.assertEqual({r["workload"] for r in rows},{58.})
        ambiguous=snaps*2
        no_rows,excluded=nfl.normalize_season(weekly,ambiguous,schedule,2022,cutoff="2022-09-09")
        self.assertFalse(no_rows)
        self.assertEqual(excluded["ambiguous_snap_rows"],1)

    def test_nfl_verified_defensive_snaps_and_combined_tackles(self):
        schedule=[{"game_id":"2018_01_BUF_BAL","season":2018,"week":1,"game_type":"REG",
            "gameday":"2018-09-09","away_team":"BUF","home_team":"BAL"}]
        weekly=[{"season":2018,"week":1,"season_type":"REG","team":"BUF",
            "position":"LB","player_id":"defender-1",
            "player_display_name":"A. Defender","opponent_team":"BAL",
            "def_tackles_solo":4.,"def_tackles_with_assist":2.,
            "def_tackle_assists":1.,"def_qb_hits":1.,"def_pass_defended":1.}]
        snaps=[{"game_id":"2018_01_BUF_BAL","season":2018,"week":1,"game_type":"REG",
            "team":"BUF","player":"Alex Defender",
            "defense_snaps":67.,"offense_snaps":0.}]
        rows,counts=nfl.normalize_season(weekly,snaps,schedule,2018,cutoff="2018-09-10")
        self.assertEqual(counts["eligible_player_rows"],1)
        expected={r["stat"]:r["value"] for r in rows}
        self.assertEqual(expected["tackles + assists"],7)
        self.assertEqual(expected["solo tackles"],4)
        self.assertEqual(expected["tackle assists"],1)
        self.assertEqual(expected["qb hits"],1)
        self.assertEqual({r["workload"] for r in rows},{67.})

    def test_multisport_nhl_cursor_restart_after_partial_source_failure(self):
        with tempfile.TemporaryDirectory() as d:
            def fetch(url):
                if "/score/" in url:
                    return {"games":[{"id":2018020001,"gameType":2,"gameState":"FINAL"}]}
                return nhl_box()
            result=ingest.run(d,"NHL",max_days=1,stop_before="2018-10-03",fetcher=fetch)
            self.assertEqual(result["advanced"],1)
            self.assertEqual(result["source_games"],1)
            self.assertEqual(result["status"],"partial")
            self.assertEqual(ingest.read_state(d,"NHL")["cursor"],"2018-10-02")
            replay=ingest.run(d,"NHL",max_days=1,stop_before="2018-10-03",
                               fetcher=lambda url: (_ for _ in ()).throw(RuntimeError("429")))
            self.assertEqual(replay["status"],"blocked")
            self.assertEqual(ingest.read_state(d,"NHL")["cursor"],"2018-10-02")

    def test_generic_model_prep_and_publication_veto(self):
        rows=[row(gid=str(1000+i//16),player=str(i%16),position="C" if i%2 else "PG",
                 value=i%12+1,workload=14+(i%8),opponent="MIA" if i%2 else "NYR") for i in range(48)]
        design=model.prepare(rows,min_rows=20)
        self.assertEqual(design["family"],"count")
        self.assertEqual(len(design["players"]),16)
        selected=model.training_only_subset(rows,max_per_position=3)
        expected={"0","10","12","1","11","13"}  # stable string-ID tie breaks
        self.assertTrue({r["player_id"] for r in selected}==expected)
        self.assertEqual(model.training_only_subset(rows),rows)
        with self.assertRaisesRegex(ValueError,"invalid_training_only_cohort_limit"):
            model.training_only_subset(rows,max_per_position=-2)
        self.assertEqual(design["source_digest"],model.prepare(rows,min_rows=20)["source_digest"])
        with self.assertRaisesRegex(ValueError,"unapproved_joint_posterior"):
            model.forecast(None,design,player_id="0",opponent="MIA",season="2023",
                           home=True,line=20.5)
        with self.assertRaisesRegex(ValueError,"invalid_multisport_nuts_budget"):
            model.fit(design,draws=1,tune=1,chains=1)
        scores=audit._scores([(.7,1),(.2,0)])
        self.assertEqual(scores["n"],2)
        self.assertLess(scores["brier"],.1)


if __name__=="__main__":
    unittest.main()
