"""Adversarial historical event-time SOG benchmark QA (no live source needed)."""
import datetime as dt, hashlib, json, math, pathlib, tempfile, unittest
from scripts import v25_phase5_nhl_sog_historical_replay as R
from v2 import nhl_sog_exposure_shadow as F

class Phase5ReplayTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.root=pathlib.Path(self.tmp.name)
  self.events=[];self.observations=[]
  self.pids=[str(8400000+i) for i in range(50)]
  for j in range(15):
   d=dt.date(2025,10,1)+dt.timedelta(days=j)
   gid=str(2025020000+j)
   self.events.append({"game_id":gid,"game_date":d.isoformat(),"season":"20252026",
    "start_utc":d.isoformat()+"T23:00:00Z","teams":["AAA","BBB"]})
   for i,pid in enumerate(self.pids):
    self.observations.append(self.row(pid,gid,d,i))
  self.day="2025-11-01"
  self.target_id="2025020099"
  self.events.append({"game_id":self.target_id,"game_date":self.day,
      "season":"20252026","start_utc":self.day+"T23:00:00Z","teams":["AAA","BBB"]})
  for i,pid in enumerate(self.pids):self.observations.append(self.row(pid,self.target_id,dt.date.fromisoformat(self.day),i))
  self.cfg={"historical_only":True,"market_replay":False,"evaluation_start":self.day,"evaluation_end":self.day}
 def tearDown(self):self.tmp.cleanup()
 def row(self,pid,gid,day,i):
  return {"player_id":pid,"game_id":gid,"game_date":str(day),"season":"20252026",
          "team":"AAA" if i%2==0 else "BBB","position_group":"F" if i<25 else "D",
          "toi_minutes":13.+(i%12)/2,"sog":(i%5)}
 def write(self,path,rows):
  path.write_bytes(b"".join(R.canonical(x)+b"\n" for x in rows))
  return path
 def files(self,obs=None,events=None):
  a=self.write(self.root/"obs.jsonl",obs if obs is not None else self.observations)
  b=self.write(self.root/"events.jsonl",events if events is not None else self.events)
  return a,b
 def execute(self,obs=None,events=None,runpath=None):
  a,b=self.files(obs,events)
  return R.run(str(a),str(b),str(runpath or self.root/"out"),self.cfg,"unit-test-frozen")
 def test_distribution_normalization_and_moments(self):
  a,b=self.files()
  _,history,_=R.parse_sources(self.observations,self.events)
  cutoff=R.utc("2025-11-01T22:00:00Z")
  view=R.histories_as_of(history,cutoff,self.day)
  mod,info=R.build_params(self.pids[0],view)
  ps=R.pmfs(mod)
  self.assertEqual(set(ps),set(R.MODEL_IDS))
  for name,pmf in ps.items():
   self.assertAlmostEqual(math.fsum(pmf),1.,places=9)
   self.assertGreaterEqual(min(pmf),0.)
   self.assertAlmostEqual(sum(k*x for k,x in enumerate(pmf)),info["model_means"][name],places=7)
  mu=info["model_means"]["M0"]
  self.assertAlmostEqual(info["model_means"]["M4"],mu,places=11)
  v=lambda p:sum((k-sum(j*q for j,q in enumerate(p)))**2*w for k,w in enumerate(p))
  self.assertAlmostEqual(v(ps["M0"]),mu,places=6)
  self.assertAlmostEqual(v(ps["M4"]),mu+mu**2/4,places=5)
  self.assertGreaterEqual(v(ps["M3"]),info["model_means"]["M3"])
 def test_m0_through_m3_original_math(self):
  _,h,_=R.parse_sources(self.observations,self.events)
  model,_=R.build_params(self.pids[0],R.histories_as_of(h,R.utc("2025-11-01T22:00:00Z"),self.day))
  ps=R.pmfs(model)
  for m,k in R.KINDS.items():
   for i in (0,1,3,8):
    self.assertAlmostEqual(ps[m][i],F._mass(model,i,k),places=13)
 def test_target_outcome_toi_and_future_games_cannot_change_sealed_forecasts(self):
  o1=self.execute(runpath=self.root/"first")
  frozen1=(self.root/"first"/o1["run_id"]/"sealed_forecasts.jsonl").read_bytes()
  changed=[dict(x) for x in self.observations]
  for row in changed:
   if row["game_id"]==self.target_id:row["sog"]=21;row["toi_minutes"]=62.
  o2=self.execute(changed,runpath=self.root/"changed")
  frozen2=(self.root/"changed"/o2["run_id"]/"sealed_forecasts.jsonl").read_bytes()
  self.assertEqual(frozen1,frozen2)
  self.assertNotEqual(o1["overall"]["models"]["M0"]["nll"],o2["overall"]["models"]["M0"]["nll"])
 def test_forecast_universe_independent_of_played_target(self):
  full=self.execute(runpath=self.root/"played")
  no_target=[x for x in self.observations if x["game_id"]!=self.target_id]
  absent=self.execute(no_target,runpath=self.root/"absent")
  self.assertEqual(full["forecasted"],absent["forecasted"])
  self.assertEqual(absent["matched_played"],0)
  self.assertEqual(sum(absent["unscored_forecasts"].values()),absent["forecasted"])
 def test_no_target_label_in_sealed_artifact(self):
  res=self.execute()
  data=(self.root/"out"/res["run_id"]/"sealed_forecasts.jsonl").read_text()
  self.assertNotIn('"actual_sog"',data)
  self.assertNotIn('"actual_toi"',data)
  self.assertIn('"cutoff_utc"',data)
  self.assertTrue(res["original_source_capture_does_not_precede_historical_games"])
  self.assertEqual(res["D2_original_line"],"NOT_EXECUTABLE_NO_AUTHENTIC_HISTORICAL_QUOTES")
 def test_duplicate_player_game_fails_closed(self):
  with self.assertRaisesRegex(R.ReplayBlocked,"DUPLICATE"):
   self.execute(self.observations+[dict(self.observations[-1])])
 def test_duplicate_event_fails_closed(self):
  with self.assertRaisesRegex(R.ReplayBlocked,"DUPLICATE"):
   self.execute(events=self.events+[dict(self.events[-1])])
 def test_current_game_team_is_never_roster_feature(self):
  changed=[dict(x) for x in self.observations]
  for row in changed:
   if row["game_id"]==self.target_id:row["team"]="BBB" if row["team"]=="AAA" else "AAA"
  with self.assertRaisesRegex(R.ReplayBlocked,"HISTORICAL_TEAM_NOT_IN_EVENT"):
   fake=[dict(x) for x in changed]
   fake[-1]["team"]="ZZZ"
   self.execute(fake)
 def test_source_releases_after_cutoff_are_excluded(self):
  _,h,_=R.parse_sources(self.observations,self.events)
  before=R.histories_as_of(h,R.utc("2025-10-02T00:00:00Z"),"2025-10-02")
  self.assertTrue(all(not rr for rr in before.values()) if before else True)
  after=R.histories_as_of(h,R.utc("2025-11-01T22:00:00Z"),"2025-11-01")
  self.assertEqual(len(after[self.pids[0]]),15)
  self.assertTrue(all(r["_release"]<R.utc("2025-11-01T22:00:00Z") for r in after[self.pids[0]]))
 def test_no_source_timestamp_can_be_claimed_certified(self):
  out=self.execute()
  self.assertEqual(out["status"],"EXPLORATORY_EVENT_TIME_ONLY")
  self.assertTrue(out["original_source_capture_does_not_precede_historical_games"])
  self.assertEqual(out["model_selection_inference"],"exploratory only; no candidate promotion")
 def test_no_matched_cohort_cherry_pick_or_cohort_loss(self):
  res=self.execute()
  self.assertEqual(res["forecasted"],res["matched_played"])
  self.assertEqual(res["overall"]["n"],res["matched_played"])
  self.assertTrue(all(res["overall"]["models"][k]["crps"]>=0 for k in R.MODEL_IDS))
 def test_fixed_n_brier_push_probability(self):
  _,h,_=R.parse_sources(self.observations,self.events)
  model,_=R.build_params(self.pids[0],R.histories_as_of(h,R.utc("2025-11-01T22:00:00Z"),self.day))
  z=F.forecast_lines(model,[2.,2.5],kind="full_gamma_poisson_exposure")
  self.assertAlmostEqual(sum(z["2"][p] for p in ("under","over","push")),1.,places=12)
  self.assertGreater(z["2"]["push"],0)
  self.assertEqual(z["2.5"]["push"],0)
 def test_future_team_alias_never_replaces_historical_team(self):
  x=[dict(r) for r in self.observations]
  for row in x:
   if row["game_id"]==self.target_id:row["team"]="BBB" if row["team"]=="AAA" else "AAA"
  first=self.execute(runpath=self.root/"one")
  second=self.execute(obs=x,runpath=self.root/"two")
  self.assertEqual(first["forecasted"],second["forecasted"])
  self.assertEqual((self.root/"one"/first["run_id"]/"sealed_forecasts.jsonl").read_bytes(),
                   (self.root/"two"/second["run_id"]/"sealed_forecasts.jsonl").read_bytes())
 def test_immutable_runs_do_not_overwrite(self):
  self.execute()
  with self.assertRaisesRegex(R.ReplayBlocked,"IMMUTABLE_RUN_ALREADY_EXISTS"):self.execute()
 def test_future_game_results_and_labels_never_enter_prior_features(self):
  start=self.execute(runpath=self.root/"control")
  first=(self.root/"control"/start["run_id"]/"sealed_forecasts.jsonl").read_bytes()
  d=dt.date(2025,11,15);gid="2025020100"
  extra={"game_id":gid,"game_date":str(d),"season":"20252026",
         "start_utc":str(d)+"T23:00:00Z","teams":["AAA","BBB"]}
  next_obs=[self.row(pid,gid,d,i) for i,pid in enumerate(self.pids)]
  for r in next_obs:r["sog"]=40
  second=self.execute(self.observations+next_obs,events=self.events+[extra],runpath=self.root/"mutated_future")
  b=(self.root/"mutated_future"/second["run_id"]/"sealed_forecasts.jsonl").read_bytes()
  self.assertEqual(first,b)
 def test_same_game_and_same_date_causal_filter(self):
  _,history,_=R.parse_sources(self.observations,self.events)
  h=R.histories_as_of(history,R.utc("2025-11-01T22:00:00Z"),"2025-11-01")
  self.assertTrue(h)
  for entries in h.values():
   self.assertTrue(all(x["game_date"]<"2025-11-01" for x in entries))
   self.assertTrue(all(x["_start"]<R.utc("2025-11-01T22:00:00Z") for x in entries))
 def test_postgame_score_inserted_into_schedule_has_no_model_effect(self):
  base=self.execute(runpath=self.root/"without_postgame")
  original=(self.root/"without_postgame"/base["run_id"]/"sealed_forecasts.jsonl").read_bytes()
  schedule=[dict(e) for e in self.events]
  for e in schedule:
   if e["game_id"]==self.target_id:
    e["actual_final_score"]={"AAA":80,"BBB":0}
    e["postgame_lineup"]=["FUTURE_ONLY"]
  tested=self.execute(events=schedule,runpath=self.root/"with_postgame")
  changed=(self.root/"with_postgame"/tested["run_id"]/"sealed_forecasts.jsonl").read_bytes()
  self.assertEqual(original,changed)
 def test_very_short_played_exposure_fails_closed_without_fallback(self):
  modified=[dict(r) for r in self.observations]
  for r in modified:
   if r["game_id"]=="2025020014" and r["player_id"]==self.pids[0]:
    r["toi_minutes"]=.05
  result=self.execute(modified,runpath=self.root/"micro_toi")
  self.assertGreater(result["forecast_abstentions"].get("EXPOSURE_BIN_INVALID",0),0)
  self.assertLess(result["matched_played"],50)
 def test_model_outcomes_do_not_create_historical_roster_eligibility(self):
  full=self.execute(runpath=self.root/"present")
  absent=[r for r in self.observations if r["game_id"]!=self.target_id]
  result=self.execute(absent,runpath=self.root/"no_current_game")
  self.assertEqual(full["candidate_player_games"],result["candidate_player_games"])
  self.assertEqual(full["forecasted"],result["forecasted"])
  self.assertEqual(result["matched_played"],0)
if __name__=="__main__":unittest.main()
