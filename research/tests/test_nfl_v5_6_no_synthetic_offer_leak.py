"""V5.6 'contracts are evaluation-only' adversarial test.

Two inputs with identical history/games/QB1 but radically different synthetic
market offers, lines, selected players, old V3 probabilities and an injected
counterfeit 'actual'. The game simulation MUST be byte-for-byte identical.
This detects indirect future-player/offer-selection leakage.
"""
import copy,gzip,json,pathlib,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
BASE=ROOT/"reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111"
sys.path[:0]=[str(ROOT/"research"),str(BASE/"EXP_ALL13_20261111T200951Z/frozen_code")]
import nfl_v5_6_prior_coverage_decade_replay_20261112 as runner
class NoOfferLeak(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  source=BASE/"V5_6_EMPIRICAL_ROSTER_COVERAGE_PILOT_20261112T160633Z/2016_week_02_v5_preweek.json.gz"
  cls.packet=json.load(gzip.open(source,"rb"))
  cls.gameid=cls.packet["contracts"][0]["game_id"]
  cls.original=[z for z in cls.packet["contracts"] if z["game_id"]==cls.gameid]
  assert len(cls.original)>3
 def _forecast(self,packet):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t)/"packet.json.gz"
   with gzip.open(p,"wb") as f:f.write(runner.canon(packet))
   return runner.child(p)
 def test_synthetic_offer_presence_has_no_model_influence(self):
  first=copy.deepcopy(self.packet);first["contracts"]=copy.deepcopy(self.original)
  second=copy.deepcopy(first)
  for z in second["contracts"]:
   z["line"]=float(z["line"])+120
   z["v3_online"]=.001
   z["v3_draws"]=None
   z["future_realized_actual"]=9999999
  second["contracts"]=second["contracts"][::2]
  self.assertGreater(len(second["contracts"]),0)
  a=self._forecast(first)["games"][self.gameid]
  b=self._forecast(second)["games"][self.gameid]
  self.assertEqual(a["joint_state"],b["joint_state"])
  self.assertEqual(a["source_profile_indices"],b["source_profile_indices"])
  self.assertEqual(a["whole_game_profile_weights_prior"],b["whole_game_profile_weights_prior"])
 def test_cannot_fit_from_current_week_history(self):
  p=copy.deepcopy(self.packet)
  row=copy.deepcopy(p["history"][-1]);row["season"]=2016;row["week"]=2
  p["history"].append(row)
  with self.assertRaises(ValueError):self._forecast(p)
 def test_cannot_fit_from_current_week_playbyplay(self):
  p=copy.deepcopy(self.packet)
  row=copy.deepcopy(p["pbp_prior"][-1]);row["season"]=2016;row["week"]=2
  p["pbp_prior"].append(row)
  with self.assertRaises(ValueError):self._forecast(p)
 def test_shares_are_from_prior_roster_stats_only(self):
  a=copy.deepcopy(self.packet);a["contracts"]=copy.deepcopy(self.original)
  first=self._forecast(a)["games"][self.gameid]
  a["contracts"]=a["contracts"][:1]
  after=self._forecast(a)["games"][self.gameid]
  self.assertEqual(first["joint_state"],after["joint_state"])
if __name__=="__main__":unittest.main()
