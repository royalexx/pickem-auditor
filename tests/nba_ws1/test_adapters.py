import copy
import json
import unittest
from v2.nba_ws1.store import Receipt,Record,build_snapshot,NBAPregameFeatureSnapshot,canonical,digest
from v2.nba_ws1.adapters import (espn_boxscore_records,schedule_records,resolve_crosswalk,observed_minutes,legacy_population_records)

T='2026-11-15T18:00:00Z'

def box():
    return {'header':{'competitions':[{'id':'1','date':'2026-11-13T00:00:00Z','status':{'type':{'completed':True,'name':'STATUS_FINAL'}},'competitors':[{'team':{'id':'1'}},{'team':{'id':'2'}}]}]},
        'boxscore':{'players':[{'team':{'id':'1'},'statistics':[{'labels':['MIN','PTS','FG','3PT','FT','REB','AST'], 'athletes':[
            {'athlete':{'id':'11'},'starter':True,'stats':['67:30','12','4-10','2-5','2-2','5','3']},
            {'athlete':{'id':'12'},'didNotPlay':True,'stats':[]},
            {'athlete':{'id':'13'},'starter':False,'stats':['0:00','0','0-0','0-0','0-0','0','0']}]}]},
            {'team':{'id':'2'},'statistics':[{'labels':['MIN','PTS'],'athletes':[{'athlete':{'id':'21'},'stats':['15','3']}]}]}]}}

class AdapterTests(unittest.TestCase):
    def receipt(self,p=None):return Receipt.capture(canonical(p or box()).encode(),source='espn-test',observed_at=T,origin='fixture')
    def test_box_extracts_attempts_starts_zero_and_dnp(self):
        p=box();r=self.receipt(p);rows=espn_boxscore_records(p,r);data={x.data['player_id']:x.data for x in rows}
        self.assertEqual(data['espn:player:11']['minutes'],67.5)
        self.assertEqual(data['espn:player:11']['stats']['fga'],10)
        self.assertEqual(data['espn:player:11']['stats']['pra'],20)
        self.assertEqual(data['espn:player:12']['participation'],'dnp')
        self.assertIsNone(data['espn:player:12']['minutes'])
        self.assertEqual(data['espn:player:13']['participation'],'played')
        self.assertEqual(data['espn:player:13']['minutes'],0)
    def test_live_box_rejected(self):
        p=box();p['header']['competitions'][0]['status']['type']={'completed':False,'name':'STATUS_IN_PROGRESS'}
        with self.assertRaisesRegex(ValueError,'NOT_FINAL'):espn_boxscore_records(p,self.receipt(p))
    def test_player_cross_team_collision(self):
        p=box();p['boxscore']['players'][1]['statistics'][0]['athletes'][0]['athlete']['id']='11'
        with self.assertRaisesRegex(ValueError,'COLLISION'):espn_boxscore_records(p,self.receipt(p))
    def test_overtime_is_observed_history_only(self):
        self.assertEqual(observed_minutes('70:30'),70.5)
        for value in (True,'-1','nan','12:65',None):self.assertIsNone(observed_minutes(value))
    def test_crosswalk_collision_expiry_and_future(self):
        r=self.receipt();entry=dict(provider_id='other:1',kind='player',canonical_id='espn:player:11',receipt_id=r.receipt_id,valid_from=T,valid_to=None)
        self.assertEqual(resolve_crosswalk('other:1','player',T,[entry],[r]),'espn:player:11')
        for entries,at in [([entry,entry],T),([entry],'2026-11-14T00:00:00Z'),([{**entry,'valid_to':T}],T)]:
            with self.assertRaisesRegex(ValueError,'CROSSWALK'):resolve_crosswalk('other:1','player',at,entries,[r])
    def test_postponed_and_cancelled_schedule_never_outcomes(self):
        p={'events':[{'id':'1','date':'2026-11-16T00:00Z','status':{'type':{'name':'STATUS_POSTPONED'}},'competitions':[{'competitors':[{'team':{'id':'1'},'homeAway':'home'},{'team':{'id':'2'},'homeAway':'away'}]}]}]}
        record=schedule_records(p,self.receipt(p))[0]
        s=build_snapshot(game_id=record.data['game_id'],forecast_at=T,input_freeze_at=T,model_training_cutoff_at=T,records=[record],receipts=[self.receipt(p)]).to_dict()
        self.assertIn('EVENT_NOT_SCHEDULED',s['abstention_codes'])
    def test_legacy_scope_fail_closed(self):
        from v2.nba_ws1.adapters import norm
        import population_history as pop
        row=pop.make(sport='NBA',stat='points',game_id='1',game_date='2026-11-10',season='2027',player_id='1',position='G',team='LAL',opponent='PHX',home=True,value=10,workload=20,workload_unit='minutes',source_url='https://site.api.espn.com/',source_sha256='a'*64)
        r=Receipt.capture(canonical([row]).encode(),source='legacy-shard',observed_at=T,origin='retrospective_retrieval')
        rows,ledger=legacy_population_records([row],r);self.assertFalse(rows);self.assertEqual(ledger['rejected_rows'],1)
        rows,ledger=legacy_population_records([row],r,eligible_game_ids={'1'});self.assertEqual(len(rows),1)
        self.assertEqual(rows[0].data['team_id'],'espn_abbrev:team:LAL')
        row={**row,'team':'WORLD'}
        rows,ledger=legacy_population_records([row],r,eligible_game_ids={'1'});self.assertFalse(rows)
        self.assertEqual(ledger['rejections'][0]['code'],'NON_FRANCHISE_EXHIBITION')

if __name__=='__main__':unittest.main()
