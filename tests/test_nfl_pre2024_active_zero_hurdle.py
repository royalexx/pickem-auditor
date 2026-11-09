"""Pre-2024 nflreadpy gateway, active-zero hurdle and Monte Carlo invariants."""
from __future__ import annotations
import math,sys,unittest
from collections import defaultdict
from pathlib import Path
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import nflverse_pre2024_hurdle_gateway as gateway
import nfl_pre2024_active_zero_hurdle as hz
import nfl_pre2024_hybrid_bayesian_mc as mc

def state(year=2023):
    x={k:defaultdict(list) for k in
       ("player","role","team_offense","opponent_allowed","league_offense","ngs")}
    x["latest_by_player"]={"P":{"gameday":f"{year}-12-03",
       "team":"A","season":year,"position":"WR"}}
    for date in [f"{year}-11-05",f"{year}-11-12",f"{year}-11-19",
                 f"{year}-11-26",f"{year}-12-03"]:
        r={"gameday":date,"game_date":date,"value":2.,
           "workload":42.,"team":"A","position":"WR","season":year}
        x["player"][("targets","P")].append(r.copy())
        x["role"][("targets","WR")].append(r.copy())
    return x

class NFLverseGatewayTests(unittest.TestCase):
 def test_exact_ids_not_substrings(self):
    got=gateway.player_ids("00-003001;00-0030012;00-003333")
    self.assertEqual(got,frozenset(("00-003001","00-0030012","00-003333")))
 def test_stale_2023_ftn_participation_forbidden(self):
    fixtures={"2023_12_A_B":{"gameday":"2023-11-19","season":2023,
        "week":12,"home_team":"B","away_team":"A"}}
    with self.assertRaisesRegex(ValueError,"ftn_2023_participation"):
        gateway.summarize_participation([
          {"nflverse_game_id":"2023_12_A_B","play_id":7,
           "possession_team":"A","offense_personnel":"1 RB, 1 TE, 3 WR",
           "offense_players":"P","qb_dropback":True}],fixtures)
 def test_2022_ngs_presence_and_11_personnel_correct_team(self):
    fixture={"2022_01_A_B":{"gameday":"2022-09-11","season":2022,
       "week":1,"home_team":"B","away_team":"A"}}
    plays=[]
    for i in range(14):
      plays.append({"nflverse_game_id":"2022_01_A_B","play_id":i+1,
         "possession_team":"A","offense_personnel":
              ("1 RB, 1 TE, 3 WR" if i<12 else "2 RB, 1 TE, 2 WR"),
         "offense_players":("00-1234;00-9999" if i<10 else "00-9999"),
         "qb_dropback":True})
    data=gateway.summarize_participation(plays,fixture)
    self.assertAlmostEqual(data["player_dropback_presence"]["00-1234"][0]
                            ["dropback_presence_rate"],10/14)
    self.assertAlmostEqual(data["offense_11_personnel"]["A"][0]
                            ["offense_11_personnel_share"],12/14)
    self.assertEqual(data["provenance"]["actual_routes_run_available"],False)
 def test_injury_status_asof_not_postgame(self):
    fixture={"2023_13_A_B":{"gameday":"2023-12-03","season":2023,
         "week":13,"home_team":"B","away_team":"A"}}
    rows=[
       {"gsis_id":"P","team":"A","season":2023,"week":13,
        "date_modified":"2023-12-01 16:00:00",
        "report_status":"Questionable","report_primary_injury":"Ankle"},
       {"gsis_id":"P","team":"A","season":2023,"week":13,
        "date_modified":"2023-12-04 12:00:00",
        "report_status":"Out","report_primary_injury":"Ankle"}]
    v=gateway.parse_injury_history(rows,fixture)
    self.assertEqual(v[("P",2023,13)]["status"],"questionable")
    self.assertFalse(v[("P",2023,13)]["active_for_game_verified"])
 def test_2024_injury_season_fails(self):
    with self.assertRaisesRegex(ValueError,"post2023_injuries"):
        gateway.parse_injury_history([
          {"season":2024,"week":1,"team":"A","gsis_id":"P"}],{})

class ZeroHurdleTests(unittest.TestCase):
 def test_no_2024_training_outcome(self):
    with self.assertRaisesRegex(ValueError,"2024_plus_hurdle_label"):
        hz.make_training_rows(state(),{},[{"season":2024,"game_date":"2024-09-08",
         "game_id":"2024_01_A_B","stat":"targets","player_id":"P"}])
 def test_player_signal_3_game_drop_calculated(self):
    h=[{"gameday":"2022-09-04","dropback_presence_rate":.70},
       {"gameday":"2022-09-11","dropback_presence_rate":.70},
       {"gameday":"2022-09-18","dropback_presence_rate":.30}]
    avg,delta,n=hz._recent(h,"dropback_presence_rate",hz._day("2022-09-25"))
    self.assertEqual(n,3)
    self.assertAlmostEqual(delta,-.4)
    self.assertAlmostEqual(avg,(.70+.70+.30)/3)
 def test_stale_2022_presence_not_recent_for_2024(self):
    x=state()
    context={"participation":{"provenance":{
       "2023_ftn_participation_used":False,"actual_routes_run_available":False},
       "player_dropback_presence":{"P":[
       {"gameday":"2022-12-01","dropback_presence_rate":.30}]}}}
    f=hz.features(x,context,market="targets",pid="P",position="WR",
       team="A",opponent="B",asof="2024-01-01")
    self.assertEqual(float(f[hz.FEATURE_NAMES.index("dropback_proxy_available")]),0.)
    self.assertTrue(math.isnan(float(f[hz.FEATURE_NAMES.index("dropback_presence_last3")])))
 def test_personnel11_signal_without_unverified_future(self):
    x=state(year=2022)
    context={"participation":{"provenance":{
       "2023_ftn_participation_used":False,"actual_routes_run_available":False},
       "offense_11_personnel":{"B":[
      {"gameday":"2022-11-19","offense_11_personnel_share":.85},
      {"gameday":"2022-11-26","offense_11_personnel_share":.85},
      {"gameday":"2022-12-03","offense_11_personnel_share":.85}]}}}
    f=hz.features(x,context,market="targets",pid="P",position="WR",
       team="A",opponent="B",asof="2022-12-12")
    self.assertAlmostEqual(float(f[hz.FEATURE_NAMES.index("personnel11_opponent_last3")]),.85)
    self.assertEqual(float(f[hz.FEATURE_NAMES.index("personnel11_available")]),1.)
 def test_unverified_participation_cannot_be_injected(self):
    with self.assertRaisesRegex(ValueError,"unsafe_participation_provenance"):
      hz.features(state(),{"participation":{"offense_11_personnel":{"B":[]}}},
          market="targets",pid="P",position="WR",team="A",opponent="B",
          asof="2024-01-01")
 def test_wrong_team_prior_not_used(self):
    x=state()
    for row in x["player"][("targets","P")]:row["team"]="OLD"
    self.assertIsNone(hz.features(x,{},market="targets",pid="P",
        position="WR",team="A",opponent="B",asof="2024-01-01"))
 def test_injury_questionable_feature_not_claimed_emergency(self):
    x=state()
    context={"injuries":{("P",2023,14):{"gameday":"2023-12-10",
        "date_modified":"2023-12-09","status":"questionable"}}}
    f=hz.features(x,context,market="targets",pid="P",position="WR",
       team="A",opponent="B",asof="2023-12-10",season=2023,week=14)
    self.assertEqual(float(f[hz.FEATURE_NAMES.index("injury_questionable_asof")]),1.)
 def test_out_report_not_a_zero_bet(self):
    x=state()
    context={"injuries":{("P",2023,14):{"gameday":"2023-12-10",
        "date_modified":"2023-12-09","status":"out"}}}
    self.assertIsNone(hz.features(x,context,market="targets",pid="P",
       position="WR",team="A",opponent="B",asof="2023-12-10",
       season=2023,week=14))
 def test_future_injury_report_fails(self):
    x=state()
    context={"injuries":{("P",2023,14):{"gameday":"2023-12-10",
        "date_modified":"2023-12-11","status":"questionable"}}}
    with self.assertRaisesRegex(ValueError,"postdated"):
       hz.features(x,context,market="targets",pid="P",position="WR",
           team="A",opponent="B",asof="2023-12-10",season=2023,week=14)
 def test_no_hurdle_without_fitted_model(self):
    p,ev=hz.zero_probability(None,state(),{},market="targets",
        pid="P",position="WR",team="A",opponent="B",asof="2024-01-01")
    self.assertIsNone(p)
    self.assertEqual(ev["status"],"untrained_hurdle_abstain")
 def test_event_zero_probability_not_game_outcome(self):
    class Stub:
      def predict_proba(self,x):return np.asarray([[.2,.8]])
    p,ev=hz.zero_probability((Stub(),None),state(),{},market="targets",
        pid="P",position="WR",team="A",opponent="B",asof="2024-01-01")
    self.assertAlmostEqual(p,.8)
    self.assertTrue(ev["active_player_not_2024_verified"])
 def test_2024_hurdle_features_refused(self):
    with self.assertRaisesRegex(ValueError,"2024_plus"):
      hz.features(state(),{},market="targets",pid="P",position="WR",
          team="A",opponent="B",asof="2024-09-01")

class MonteCarloCouplingTests(unittest.TestCase):
 def test_hurdle_keeps_all_team_targets(self):
    rng=np.random.default_rng(49)
    alpha=np.asarray([4.,3.,10.])
    sums=rng.integers(25,40,size=1800)
    arr=mc._alloc(rng,sums,alpha)
    before=(arr[:,0]==0).mean()
    after=mc._alloc_zero_hurdle(rng,arr,[.94,None])
    self.assertTrue(np.array_equal(sums,after.sum(axis=1)))
    self.assertTrue(np.all(after>=0))
    self.assertGreater((after[:,0]==0).mean(),before+.4)
 def test_hurdle_can_reduce_zero_with_residual_events(self):
    rng=np.random.default_rng(91)
    src=np.array([[0,2,10]]*500)
    out=mc._alloc_zero_hurdle(rng,src,[.1,None])
    self.assertTrue(np.all(out.sum(axis=1)==12))
    self.assertLess((out[:,0]==0).mean(),.2)
 def test_defense_zero_hurdle_increases_zero_rate(self):
    rng=np.random.default_rng(23)
    x=rng.poisson(4.,size=2500)
    y=mc._defense_zero_hurdle(rng,x,.85)
    self.assertGreater(np.mean(y==0),.80)
    self.assertTrue(np.all(y>=0))
 def test_original_sim_without_hurdle_still_runs(self):
    from test_nfl_pre2024_team_xgb_hybrid_mc import make_state,fixture,vols,disps
    out,rec=mc.simulate_game(make_state(),fixture(),vols(),disps(),draws=180)
    self.assertTrue(out)
    self.assertFalse(rec["conditional_active_zero_hurdle"])
 def test_model_2024_plus_state_rejected(self):
    from test_nfl_pre2024_team_xgb_hybrid_mc import make_state,fixture,vols,disps
    x=make_state()
    x["player"][("targets","WRA")].append({"season":2024,
       "gameday":"2024-09-08","value":1.,"team":"A"})
    with self.assertRaisesRegex(ValueError,"2024_plus"):
       mc.simulate_game(x,fixture(),vols(),disps(),draws=150)

if __name__=="__main__":unittest.main()
