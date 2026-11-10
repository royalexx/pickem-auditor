import copy
import json
import math
import sys
from pathlib import Path
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from v25_opportunity_distribution import OpportunityModel,validate_history,normalise_player_source
from nfl_contract_settlement import settle,index_outcomes
from v25_phase2_online_probability_calibration import calibrate_asof

def history():
    out=[]
    for w in range(1,16):
        out.append({"event_id":f"2023_{w:02}_A_B","season":2023,"week":w,
          "team":"A","opponent":"B","pass_attempts":30,"rush_attempts":20,
          "players":{
            "q":{"role":"QB","values":{"pass attempts":30,"completions":20,"passing yards":240}},
            "bench":{"role":"QB","values":{"pass attempts":0,"completions":0,"passing yards":0}},
            "wr":{"role":"WR","values":{"targets":10,"receptions":7,"receiving yards":90}},
            "te":{"role":"TE","values":{"targets":5,"receptions":4,"receiving yards":40}},
            "rb":{"role":"RB","values":{"targets":3,"receptions":2,"receiving yards":12,"carries":18,"rushing yards":72}},
            "lb":{"role":"LB","values":{"solo tackles":5,"tackle assists":3,"tackles + assists":9}}}})
    return out

class OpportunityRepairTests(unittest.TestCase):
    def test_joint_attempt_and_target_conservation(self):
        r=OpportunityModel(history(),1).forecast_team("A","future",n=128)
        a=r["team_pass_attempts"]
        q=sum((v["pass attempts"] for v in r["draws"].values() if "pass attempts" in v),np.zeros(128,dtype=int))
        t=sum((v["targets"] for v in r["draws"].values() if "targets" in v),np.zeros(128,dtype=int))
        np.testing.assert_array_equal(q+r["unknown_qb_attempts"],a)
        np.testing.assert_array_equal(t+r["unknown_receiver_targets"]+r["non_target_attempts"],a)
        for values in r["draws"].values():
            if "receptions" in values:self.assertTrue(np.all(values["receptions"]<=values["targets"]))
            if "completions" in values:self.assertTrue(np.all(values["completions"]<=values["pass attempts"]))
        carries=sum((v.get("carries",np.zeros(128,dtype=int)) for v in r["draws"].values()),np.zeros(128,dtype=int))
        np.testing.assert_array_equal(carries+r["unknown_rb_attempts"]+r["non_rb_rush_attempts"],r["team_rush_attempts"])
        for v in r["draws"].values():
            if "tackles + assists" in v:self.assertTrue(np.all(v["solo tackles"]+v["tackle assists"]<=v["tackles + assists"]))

    def test_stale_zero_attempt_backup_does_not_halve_primary(self):
        h=history();before=OpportunityModel(h,1).forecast_team("A","future",n=512)
        for g in h:g["players"]["older_backup"]={"role":"QB","values":{"pass attempts":0,"completions":0,"passing yards":0}}
        after=OpportunityModel(h,1).forecast_team("A","future",n=512)
        np.testing.assert_array_equal(before["draws"]["q"]["pass attempts"],after["draws"]["q"]["pass attempts"])
        self.assertGreater(np.mean(after["draws"]["q"]["pass attempts"]),24.)

    def test_receiver_denominator_only_observed_appearance_games(self):
        h=history()
        for g in h[:-2]:del g["players"]["wr"]
        r=OpportunityModel(h,1).forecast_team("A","future",n=128)
        self.assertEqual(r["player_diagnostics"]["wr"]["matched_attempt_exposure"],60)
        self.assertEqual(r["player_diagnostics"]["wr"]["appearance_games"],2)
        self.assertGreater(r["player_diagnostics"]["wr"]["conditional_target_per_attempt"],.20)

    def test_active_zero_target_row_is_observation_not_absence(self):
        h=history();h[-1]["players"]["wr"]["values"].update(targets=0,receptions=0,**{"receiving yards":0})
        r=OpportunityModel(h,1).forecast_team("A","future",n=128)
        self.assertEqual(r["player_diagnostics"]["wr"]["appearance_games"],8)
        self.assertEqual(r["player_diagnostics"]["wr"]["role_status"],"conditional_on_unverified_current_appearance")
        self.assertFalse(r["player_diagnostics"]["wr"]["publication_eligible"])

    def test_unknown_recipient_rate_measures_arrivals_not_departed_mass(self):
        h=history()
        for g in h[:3]:g["players"]["departed"]={"role":"WR","values":{"targets":5,"receptions":3,"receiving yards":30}}
        model=OpportunityModel(h,1)
        # No new recipient after the first two appearances: no unknown-target successes.
        self.assertEqual(model.unseen["alpha"],1.)
        self.assertEqual(model.unseen["historical_origins"],13)

    def test_future_and_current_labels_are_rejected(self):
        for week in [1,2,18]:
            h=history();h[-1].update(season=2024,week=week)
            with self.assertRaisesRegex(ValueError,"current_or_future"):
                OpportunityModel(h,1)

    def test_duplicate_and_hidden_fields_are_rejected(self):
        h=history()
        with self.assertRaisesRegex(ValueError,"duplicate"):validate_history(h+[copy.deepcopy(h[-1])],1)
        h[0]["final_score"]=42
        with self.assertRaisesRegex(ValueError,"hidden_feature"):validate_history(h,1)

    def test_conditional_count_exceeds_opportunity_rejected(self):
        h=history();h[0]["players"]["wr"]["values"]["receptions"]=11
        with self.assertRaisesRegex(ValueError,"exceeds_exposure"):OpportunityModel(h,1)

    def test_determinism_and_different_random_seeds(self):
        m=OpportunityModel(history(),1)
        a=m.forecast_team("A","future",n=128,seed=1)
        b=m.forecast_team("A","future",n=128,seed=1)
        c=m.forecast_team("A","future",n=128,seed=2)
        np.testing.assert_array_equal(a["draws"]["wr"]["targets"],b["draws"]["wr"]["targets"])
        self.assertFalse(np.array_equal(a["draws"]["wr"]["targets"],c["draws"]["wr"]["targets"]))

    def test_zero_identity_raw_and_no_history(self):
        for method in ["raw","global_platt","role_platt"]:
            offers=[{"event_id":"e","team":"A","player_id":str(p),"role":"WR","raw_over":p} for p in [0.,.5,1.]]
            r=calibrate_asof([],offers,week=1,mode=method)
            self.assertEqual([x["calibrated_over"] for x in r["probabilities"]],[0.,.5,1.])
            self.assertFalse(r["calibration_active"])

    def test_team_identity_and_missing_outcomes(self):
        truth=index_outcomes([{"game_id":"g","team":"B","player_id":"p","stat":"targets","value":8}])
        c={"game_id":"g","team":"A","player_id":"p","market":"targets","research_line":5.5}
        self.assertEqual(settle(c,truth)["state"],"UNMATCHED")
        c["team"]="B";self.assertEqual(settle(c,truth)["actual_over"],1)
        c["research_line"]=8;self.assertEqual(settle(c,truth)["state"],"PUSH")

    def test_duplicate_settlement_is_rejected(self):
        x={"game_id":"g","team":"B","player_id":"p","stat":"targets","value":0}
        with self.assertRaisesRegex(ValueError,"duplicate"):index_outcomes([x,x])

    def test_forecast_interface_rejects_current_outcome_and_future_schedule_feature(self):
        from v25_opportunity_repair_replay import forecast_snapshot
        x={"schema":"v25-opportunity-asof-v1","week":1,"history":history(),"schedule":[{"event_id":"next","team":"A","opponent":"B","week":1}]}
        x["actual_targets"]=[12]
        with self.assertRaisesRegex(ValueError,"outcome"):forecast_snapshot(x,128,5)
        del x["actual_targets"];x["schedule"][0]["actual_pass_attempts"]=40
        with self.assertRaisesRegex(ValueError,"schedule_outcome"):forecast_snapshot(x,128,5)

    def test_zero_placeholder_is_quarantined_and_nonzero_unidentified_row_rejected(self):
        from v25_opportunity_distribution import FIELD
        x={"season":2023,"week":1,"season_type":"REG","game_id":"g","team":"A","opponent_team":"B","player_id":None,"position":None}
        x.update({c:0 for c in FIELD.values() if c});x["def_tackles_with_assist"]=0
        ledger=[];self.assertEqual(normalise_player_source([x],rejection_ledger=ledger),[])
        self.assertEqual(len(ledger),1)
        x["targets"]=1
        with self.assertRaisesRegex(ValueError,"identity"):normalise_player_source([x],rejection_ledger=ledger)

    def test_research_default_selects_validated_count_control_and_abstains_yards(self):
        from v25_opportunity_repair_replay import forecast_snapshot
        x={"schema":"v25-opportunity-asof-v1","week":1,"history":history(),
           "schedule":[{"event_id":"next","team":"A","opponent":"B","week":1}]}
        r=forecast_snapshot(x,128,5)
        self.assertEqual(r["research_default_model"],"simple_control")
        self.assertEqual(len(r["default_supported_markets"]),8)
        self.assertEqual(len(r["default_abstained_markets"]),3)
        for pid,markets in r["forecasts"][0]["research_default_draws"].items():
            self.assertFalse(any("yards" in m for m in markets))
            for market,values in markets.items():
                self.assertEqual(values,r["forecasts"][0]["simple_control"][pid][market])
        self.assertFalse(r["default_is_joint_scenario_model"])
        self.assertFalse(r["production_promotion_authorized"])

    def test_count_scoring_and_push_semantics(self):
        from v25_opportunity_repair_replay import sample_score
        values=[0,1,2,3]*32;r=sample_score(values,2,1.5)
        self.assertAlmostEqual(r["crps"],.375)
        self.assertEqual(r["y"],1)
        push=sample_score(values,2,2)
        self.assertIsNone(push["y"]);self.assertEqual(push["p_push"],.25)

    def test_route_predictive_volatility_is_sd_not_standard_error(self):
        from v2.nfl_opportunity.contracts import prepare_inputs
        from v2.nfl_opportunity.allocation import fit_allocator
        root=Path(__file__).resolve().parents[1]
        x=json.loads((root/"examples/v25_phase2_nfl_synthetic_case.json").read_text())
        for i,r in enumerate(x["player_history"]):
            if r["player_id"]=="WR2_A" and r["routes"]>0:r["targets"]=1 if i%2 else min(12,r["routes"])
        forecast,team,players,_=prepare_inputs(x)
        fitted=fit_allocator(team,players,forecast)
        prior=next(p for p in fitted.players if p.player_id=="WR2_A")
        rows=[p for p in players if p.player_id=="WR2_A" and p.routes>0 and p.event_id!=forecast.event_id]
        rates=[math.log((p.targets+.5)/(p.routes-p.targets+.5)) for p in rows]
        self.assertAlmostEqual(prior.logit_sd,max(.05,float(np.std(rates,ddof=1))))

if __name__=="__main__":unittest.main()
