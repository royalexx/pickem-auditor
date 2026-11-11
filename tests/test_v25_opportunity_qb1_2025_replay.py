"""QB1 rushing source, as-of and market-boundary adversarial regression tests."""
import copy,datetime,pathlib,sys,unittest
from zoneinfo import ZoneInfo
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
from v25_opportunity_qb1_2025_replay import (
    asof_depth_qb1,asof_packet,child_forecast,kickoff,need
)

def history():
    rows=[]
    for week in range(1,5):
        for team,opponent in (("A","B"),("B","A")):
            rows.append({"event_id":f"2024_{week:02d}_A_B","team":team,
                "opponent":opponent,"season":2024,"week":week,
                "pass_attempts":34,"rush_attempts":22,
                "players":{
                  "qbA" if team=="A" else "qbB":{
                      "role":"QB","values":{"pass attempts":32,
                          "completions":23,"passing yards":231,
                          "carries":5+week,"rushing yards":21+week*3}},
                  "rbA" if team=="A" else "rbB":{
                      "role":"RB","values":{"carries":14,"rushing yards":65,
                          "targets":3,"receptions":2,"receiving yards":17}}}})
    return rows

def selected(player="qbA",source="2025-09-05T12:00:00Z"):
    return {"event_id":"2025_01_A_B","team":"A","opponent":"B",
        "week":1,"player_id":player,"reason":None,
        "source_dated_at":source,"forecast_freeze_at":"2025-09-08T15:00:00Z",
        "kickoff_at":"2025-09-08T17:00:00Z",
        "role_source":"retrospectively_retrieved_dated_QB1_depth_chart",
        "original_pregame_capture_verified":False,
        "is_authoritative_starter_confirmation":False}

class QB1RetrospectiveTests(unittest.TestCase):
    def test_only_qb_rushing_market_never_rb_yards(self):
        packet=asof_packet(history(),1,[selected()])
        x=child_forecast(packet,samples=128,seed=11)
        self.assertEqual(len(x["contracts"]),2)
        self.assertEqual({c["market"] for c in x["contracts"]},
                         {"qb rushing attempts","qb rushing yards"})
        self.assertTrue(all(c["player_id"]=="qbA" and c["role"]=="QB" for c in x["contracts"]))
        self.assertTrue(all(c["depth_chart_is_not_confirmed_starter"] for c in x["contracts"]))
        self.assertTrue(all(c["source_capture_certified"] is False for c in x["contracts"]))
        self.assertFalse(x["production_authorized"])

    def test_reproducible_and_first_week_controls_identical(self):
        p=asof_packet(history(),1,[selected()])
        x=child_forecast(p,samples=128,seed=11)
        y=child_forecast(p,samples=128,seed=11)
        self.assertEqual(x,y)
        for c in x["contracts"]:
            self.assertEqual(c["draws"]["expanding"],c["draws"]["frozen_2024"])

    def test_unverified_depth_causes_abstention_not_backup(self):
        p=asof_packet(history(),1,[{**selected(),"player_id":None,
             "reason":"missing_recent_asof_qb1_depth","source_dated_at":None}])
        x=child_forecast(p,samples=128,seed=11)
        self.assertEqual(x["contracts"],[])
        self.assertEqual(x["rejected"][0]["reason"],"missing_recent_asof_qb1_depth")

    def test_future_source_tampering_fail_closed(self):
        p=asof_packet(history(),1,[selected(source="2025-09-09T18:00:00Z")])
        with self.assertRaisesRegex(ValueError,"source_future_or_stale"):
            child_forecast(p,samples=128,seed=11)

    def test_current_game_label_leak_fails_closed(self):
        p=asof_packet(history(),1,[selected()])
        new=copy.deepcopy(p["history"][-1])
        new.update(event_id="current",season=2025,week=1)
        p["history"].append(new)
        with self.assertRaisesRegex(ValueError,"current_or_future_game_label"):
            child_forecast(p,samples=128,seed=11)

    def test_current_game_postgame_schedule_fields_never_enter_worker(self):
        p=asof_packet(history(),1,[selected()])
        p["actual_starter"]="qbA"
        with self.assertRaisesRegex(ValueError,"hidden_child_field"):
            child_forecast(p,samples=128,seed=11)

    def test_old_player_secondary_QB_is_never_forecast(self):
        p=asof_packet(history(),1,[selected(player="qbA")])
        p["history"][0]["players"]["backup"]={"role":"QB",
              "values":{"pass attempts":1,"carries":1,"rushing yards":0}}
        x=child_forecast(p,samples=128,seed=11)
        self.assertTrue(x["contracts"])
        self.assertFalse(any(c["player_id"]=="backup" for c in x["contracts"]))

    def test_schedule_kickoff_timezone_aware(self):
        row={"gameday":"2025-09-08","gametime":"13:00"}
        self.assertEqual(kickoff(row).isoformat(),"2025-09-08T17:00:00+00:00")

    def test_selected_qb_source_conflict_invalid(self):
        rows=[selected(),{**selected(),"player_id":"qbB"}]
        with self.assertRaisesRegex(ValueError,"bad_qb1_week"):
            asof_packet(history(),1,rows)

    def test_qb1_asof_selection_does_not_use_realized_starter(self):
        games=[]
        # 272 complete schedule objects, including Week 1's chosen example.
        for week in range(1,19):
            for i in range(15 if week in (1,18) else 15):
                games.append({"game_id":f"2025_{week:02d}_{i:02d}",
                  "season":2025,"game_type":"REG","week":week,
                  "gameday":f"2025-09-{min(week+7,28):02d}",
                  "gametime":"13:00","home_team":f"H{i}",
                  "away_team":f"A{i}","home_qb_id":"AFTER_GAME_INCORRECT",
                  "away_qb_id":"AFTER_GAME_INCORRECT"})
        # 270 games; add 2 to get exact 272.
        for i in range(2):
            games.append({**games[-1],"game_id":f"extra_{i}","home_team":f"H{15+i}",
                          "away_team":f"A{15+i}"})
        date="2025-09-08T14:00:00Z"
        depth=[]
        for i in range(17):
            depth.extend([{"dt":date,"team":f"H{i}","gsis_id":f"homeQB{i}",
                           "pos_abb":"QB","pos_rank":1},
                          {"dt":date,"team":f"A{i}","gsis_id":f"awayQB{i}",
                           "pos_abb":"QB","pos_rank":1}])
        selection=asof_depth_qb1(depth,games,max_age_days=365)
        self.assertEqual(len(selection),544)
        self.assertFalse(any(x["player_id"]=="AFTER_GAME_INCORRECT" for x in selection))
        self.assertTrue(all(x["original_pregame_capture_verified"] is False for x in selection))
        self.assertEqual(selection[0]["player_id"],"homeQB0")

if __name__=="__main__":unittest.main()
