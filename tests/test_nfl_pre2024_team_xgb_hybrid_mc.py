"""Strict pre-2024 hybrid XGBoost team + Bayesian allocation Monte Carlo tests."""
import sys,unittest,math,tempfile
from pathlib import Path
from collections import defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import nfl_pre2024_team_volume_xgb as tx
import nfl_pre2024_hybrid_bayesian_mc as hy
import nfl_pre2024_team_defense_challenger as ref
import nfl_pre2024_team_xgb_hybrid_replay as replay

def make_state():
    s={x:defaultdict(list) for x in
        ("player","role","team_offense","opponent_allowed",
         "league_offense","ngs")}
    s["latest_by_player"]={}
    for team in ("A","B"):
        roster=[("QB"+team,"QB"),("WR"+team,"WR"),("RB"+team,"RB"),
                ("LB"+team,"LB")]
        for pid,pos in roster:
            s["latest_by_player"][pid]={"gameday":"2023-12-17",
              "team":team,"season":2023,"position":pos}
        for i in range(5):
            day=f"2023-12-{3+i*4:02d}"
            def add(pid,pos,market,value):
                row={"gameday":day,"game_date":day,"value":float(value),
                     "position":pos,"team":team,"season":2023,
                     "workload":48.}
                s["player"][(market,pid)].append(row)
                s["role"][(market,pos)].append(row)
            for stat,v in (("pass attempts",34.),("completions",23.),("passing yards",265.)):
                add("QB"+team,"QB",stat,v)
            for stat,v in (("targets",8.),("receptions",6.),("receiving yards",72.)):
                add("WR"+team,"WR",stat,v)
            for stat,v in (("targets",4.),("receptions",3.),("receiving yards",22.),
                           ("carries",16.),("rushing yards",72.)):
                add("RB"+team,"RB",stat,v)
            for stat,v in (("carries",3.),("rushing yards",12.)):
                add("QB"+team,"QB",stat,v)
            for stat,v in (("tackles + assists",8.),("solo tackles",4.),
                           ("tackle assists",2.)):
                add("LB"+team,"LB",stat,v)
            for metric,val in (("pass_attempts",34.),("rush_attempts",25.),
                              ("dropbacks",37.)):
                r={"gameday":day,"value":val}
                s["team_offense"][(metric,team)].append(r)
                s["opponent_allowed"][(metric,team)].append(r)
                s["league_offense"][metric].append(r)
    return s

def fixture():
    return {"game_id":"2024_01_A_B","home_team":"B",
        "away_team":"A","week":1,"gameday":"2024-09-08"}

def vols(pass_a=33.,pass_b=35.):
    return {"A":{"pass_attempts":pass_a,"rush_attempts":25.},
            "B":{"pass_attempts":pass_b,"rush_attempts":28.}}
def disps():
    return {t:{"pass_attempts":35.,"rush_attempts":30.} for t in ("A","B")}

class TeamVolumeTest(unittest.TestCase):
 def test_pre2024_features_are_finite_and_ordered(self):
    rows=[]
    for w in range(1,7):
        rows.append({"gameday":f"2023-10-{w+10:02d}",
           "season":2023,"game_id":f"2023_{w:02d}_A_B",
           "team":"A","opponent":"B","week":w,
           "pass_attempts":32.,"rush_attempts":26.})
    idx=tx.build_index(rows,{})
    feat=tx.features(idx,"A","B",asof="2024-01-01",home=False,week=1)
    self.assertEqual(len(feat),len(tx.FEATURES))
    self.assertTrue(np.isfinite(feat).all())
 def test_future_team_source_blocks_pre2024_index(self):
    with self.assertRaisesRegex(ValueError,"2024_team"):
        tx.build_index([{"gameday":"2024-09-08","season":2024,"team":"A",
                         "opponent":"B"}],{})
 def test_future_ngs_source_blocks_pre2024_index(self):
    with self.assertRaisesRegex(ValueError,"2024_ngs"):
        tx.build_index([],{"receiving":[{"gameday":"2024-09-08",
                  "season":2024,"team":"A"}]})
 def test_2024_feature_datetime_blocked(self):
    idx=tx.build_index([],{})
    with self.assertRaisesRegex(ValueError,"2024_observation"):
        tx.features(idx,"A","B",asof="2024-09-08",home=False,week=1)

class JointBayesianMCTests(unittest.TestCase):
 def test_all_sampled_stats_finite_and_reproducible(self):
    s=make_state()
    a,am=hy.simulate_game(s,fixture(),vols(),disps(),draws=300,seed=9)
    b,bm=hy.simulate_game(s,fixture(),vols(),disps(),draws=300,seed=9)
    self.assertEqual(a.keys(),b.keys())
    for k in a:
        np.testing.assert_array_equal(a[k]["samples"],b[k]["samples"])
    self.assertEqual(am["2024_training_data_used"],False)
 def test_player_targets_receptions_and_carries_consistent(self):
    rng=np.random.default_rng(21)
    s=make_state();roster=hy.previous_roster(s,("A","B"))
    out={}
    pass_total,rush_total=hy._simulate_offense(rng,out,s,"A",roster["A"],
        38.,24.,25.,25.,500)
    total_targets=np.zeros(500);total_carries=np.zeros(500)
    for (team,pid,market),rec in out.items():
        if market=="targets":total_targets+=rec["samples"]
        if market=="carries":total_carries+=rec["samples"]
        if market=="receptions":
            self.assertTrue(np.all(rec["samples"]<=out[(team,pid,"targets")]["samples"]))
        if market=="completions":
            self.assertTrue(np.all(rec["samples"]<=out[(team,pid,"pass attempts")]["samples"]))
    self.assertTrue(np.all(total_targets<=pass_total))
    self.assertTrue(np.all(total_carries<=rush_total))
 def test_higher_team_pass_volume_can_raise_targets(self):
    s=make_state()
    low,_=hy.simulate_game(s,fixture(),vols(28.),disps(),draws=1500,seed=12)
    high,_=hy.simulate_game(s,fixture(),vols(46.),disps(),draws=1500,seed=12)
    self.assertGreater(high[("A","WRA","targets")]["samples"].mean(),
                       low[("A","WRA","targets")]["samples"].mean()+2.)
 def test_tackles_total_includes_unobserved_assisted_credit(self):
    s=make_state()
    out,_=hy.simulate_game(s,fixture(),vols(),disps(),draws=500,seed=19)
    solo=out[("A","LBA","solo tackles")]["samples"]
    assist=out[("A","LBA","tackle assists")]["samples"]
    total=out[("A","LBA","tackles + assists")]["samples"]
    self.assertTrue(np.all(total>=solo+assist))
    self.assertGreater(total.mean(),0.)
 def test_recent_five_stats_override_older_history(self):
    s=make_state()
    before=hy._eligible(s,"A",hy.previous_roster(s,["A"])["A"],"targets")
    for r in s["player"][("targets","WRA")]:r["value"]=13.
    after=hy._eligible(s,"A",hy.previous_roster(s,["A"])["A"],"targets")
    old=dict((p[0],p[2]) for p in before)
    new=dict((p[0],p[2]) for p in after)
    self.assertGreater(new["WRA"],old["WRA"]+3.)
 def test_future_2024_player_stat_aborts(self):
    s=make_state()
    s["player"][("targets","WRA")].append({
        "gameday":"2024-09-08","value":27.,"season":2024,"team":"A"})
    with self.assertRaisesRegex(ValueError,"2024_plus"):
        hy.simulate_game(s,fixture(),vols(),disps(),draws=100)
 def test_training_not_faking_real_bookmaker_availability(self):
    preds,receipt=hy.summarize_game(make_state(),fixture(),vols(),
                                    disps(),draws=200)
    self.assertTrue(preds)
    self.assertTrue(all(p["bookmaker_quote_verified"] is False for p in preds))
    self.assertTrue(all(p["roster_2024_verified"] is False for p in preds))
    self.assertFalse(any("touchdown" in p["market"] for p in preds))
 def test_scoring_never_runs_without_18_week_manifest(self):
    with tempfile.TemporaryDirectory() as td:
        with self.assertRaisesRegex(RuntimeError,"must_freeze_before_evaluate"):
            replay.evaluate(td)
 def test_all_allowed_markets_registered(self):
    self.assertEqual(len(ref.VOLUME_MARKETS),11)
    self.assertEqual(len(tx.TARGETS),2)

if __name__=="__main__":unittest.main()
