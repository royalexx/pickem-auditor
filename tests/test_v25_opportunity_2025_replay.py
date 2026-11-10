import copy,json,pathlib,sys,unittest,tempfile,hashlib
import numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from v25_opportunity_2025_replay import forecast,snapshot_for,game_paired
from v25_opportunity_distribution import OpportunityModel,validate_history,normalise_player_source
from test_v25_opportunity_distribution_repair import history

def snap(week=1):
    h=history()
    for g in h:g['season']=2024
    return {'schema':'v25-opportunity-2025-asof-v1','season':2025,'week':week,'history':h,
       'schedule':[{'event_id':'2025_01_A_B','team':'A','opponent':'B','week':week}]}

class Replay2025Tests(unittest.TestCase):
    def test_week1_identical_controls(self):
        r=forecast(snap(),128,5)
        self.assertTrue(r['contracts'])
        for c in r['contracts']:
            self.assertEqual(c['draws']['expanding'],c['draws']['frozen_2024'])
            self.assertEqual(c['research_line']%1,.5)
            self.assertNotIn('yards',c['market'])

    def test_expanding_updates_but_frozen_retains_preseason_counts(self):
        a=snap(2);b=copy.deepcopy(a)
        for x in [a,b]:
            new=copy.deepcopy(x['history'][-1]);new.update(event_id='new2025',season=2025,week=1)
            x['history'].append(new)
        b['history'][-1]['players']['wr']['values'].update(targets=20,receptions=15)
        ra=forecast(a,128,5);rb=forecast(b,128,5)
        pick=lambda r:next(c for c in r['contracts'] if c['player_id']=='wr' and c['market']=='targets')
        aa,bb=pick(ra),pick(rb)
        self.assertEqual(aa['draws']['frozen_2024'],bb['draws']['frozen_2024'])
        self.assertNotEqual(aa['draws']['expanding'],bb['draws']['expanding'])

    def test_current_future_history_and_default_2024_boundary(self):
        for w in [2,3,18]:
            x=snap(2);g=copy.deepcopy(x['history'][-1]);g.update(event_id='future',season=2025,week=w);x['history'].append(g)
            with self.assertRaisesRegex(ValueError,'current_or_future'):forecast(x,128,5)
        x=snap(2)
        for g in x['history']:g['season']=2023
        x['history'][-1].update(season=2025,week=1)
        with self.assertRaisesRegex(ValueError,'calendar_out_of_range'):OpportunityModel(x['history'],2)

    def test_only_past_weeks_and_safe_schedule_survive_oracle_mutation(self):
        # A source may carry future scores and outcomes, but the boundary
        # constructs identity-only schedules; those fields never reach child.
        games=[{'season':2025,'week':1,'game_id':'g','home_team':'A','away_team':'B','actual':99}]
        a=snapshot_for(history(),games,1);games[0]['actual']=-100
        self.assertEqual(a,snapshot_for(history(),games,1))
        a['schedule'][0]['actual']=12
        with self.assertRaisesRegex(ValueError,'schedule_outcome'):forecast(a,128,5)

    def test_hidden_outcome_and_duplicate_schedule_rejected(self):
        x=snap();x['actual']={}
        with self.assertRaisesRegex(ValueError,'snapshot_hidden_outcome'):forecast(x,128,5)
        x=snap();x['schedule']*=2
        with self.assertRaisesRegex(ValueError,'duplicate_schedule'):forecast(x,128,5)

    def test_deterministic_and_unsupported_year_rejected(self):
        self.assertEqual(forecast(snap(),128,5),forecast(snap(),128,5))
        with self.assertRaisesRegex(ValueError,'unsupported_forecast_season'):
            validate_history(history(),1,forecast_season=2026)

    def test_no_frozen_rookie_history_is_explicit_abstention(self):
        x=snap(2);g=copy.deepcopy(x['history'][-1]);g.update(season=2025,week=1,event_id='first')
        g['players']['rookie']={'role':'WR','values':{'targets':3,'receptions':2,'receiving yards':15}}
        x['history'].append(g)
        r=forecast(x,128,5)
        c=next(c for c in r['contracts'] if c['player_id']=='rookie')
        self.assertIn('frozen_2024',c['abstentions']);self.assertNotIn('frozen_2024',c['draws'])
        self.assertIn('expanding',c['draws'])

    def test_cluster_difference_is_paired_not_different_universes(self):
        row={'week':1,'game_id':'g','team':'A','player_id':'p','market':'targets','line':1.5,'brier':.1}
        out=game_paired([row,{**row,'player_id':'extra','brier':.8}],[{**row,'brier':.2}],'brier')
        self.assertEqual(out['n'],1);self.assertAlmostEqual(out['new_minus_reference'],-.1)

    def test_independent_audit_rejects_changed_receipt(self):
        from v25_opportunity_2025_audit import audit,sha
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);oracle=root/'oracle.json';oracle.write_text('{"rows":[]}')
            r={'source_hashes':{'oracle_source':sha(oracle)},'receipt_sha256':'0'*64}
            (root/'FINAL_REPORT.json').write_text(json.dumps(r))
            with self.assertRaisesRegex(AssertionError,'report_digest'):audit(root,oracle)

    def test_independent_audit_rejects_changed_frozen_code(self):
        from v25_opportunity_2025_audit import audit,sha,content_sha
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);oracle=root/'oracle.json';oracle.write_text('{"rows":[]}');(root/'code').mkdir()
            (root/'code/model.py').write_text('tampered')
            r={'source_hashes':{'oracle_source':sha(oracle)},'2025_untouched_holdout':False,
               'production_authorized':False,'code_hashes':{'model.py':'0'*64}}
            r['receipt_sha256']=content_sha(r);(root/'FINAL_REPORT.json').write_text(json.dumps(r))
            with self.assertRaisesRegex(AssertionError,'frozen_code_changed'):audit(root,oracle)

if __name__=='__main__':unittest.main()
