"""Synthetic adapter regression tests: roster evidence is not quote availability."""
import unittest
from unittest.mock import patch
from .test_models import fixture,NOW
from . import models as m
from . import ws1_full_market_adapter_v2_1 as adapter

class AdapterTests(unittest.TestCase):
    def build(self,source='rosterhash',position='WR'):
        p=fixture()
        s={'game_id':'target','player_id':'gsis:Aw','espn_player_id':'123','player_stat_id':'stat1',
           'normalized_market':'receiving_targets','abstention_reasons':[],'model_input_ready':True,
           'identity_source_sha256':source,'position':position,'team':'A','event_start_at':p['events'][0]['event_start']}
        ext={'feature_freeze_at':p['manifest']['input_freeze_at'],'previous_feature_pin':{'sha256':adapter.v1.PIN},
             'tables':{'player_stats':{'path':'stats.jsonl','sha256':'test','rows':1}},
             'expanded_manifest':{'path':'manifest.json','sha256':'test'},'source_evidence':[],
             'new_public_source_receipts':{k:{'raw_path':k+'.csv','sha256':k,'observed_received_at':p['manifest']['input_freeze_at']} for k in ('players','stats2026')}}
        files={adapter.EXT_PATH:m.canonical(ext),'stats.jsonl':m.canonical(s),'manifest.json':b'{}',
               'players.csv':b'espn_id,gsis_id\n123,Aw\n','stats2026.csv':b'game_id,team,player_id\n'}
        meta={'checks':[{'sha256':'rosterhash'}],'originals':[],'rejections':{}}
        with patch.object(adapter.v1,'build',return_value=(p,meta)),patch.object(adapter.v1,'authenticate',return_value=({},None,{'pregame_roster_availability':[]},[])),patch.object(adapter.v1,'checked',side_effect=lambda root,path,digest:files[path]):
            return adapter.build('/synthetic',NOW)
    def test_quote_absence_does_not_block_source_bound_roster(self):
        p,meta=self.build()
        self.assertEqual(len(p['roster']),1)
        self.assertEqual(p['roster'][0]['source_id'],'rosterhash')
        self.assertEqual(p['roster'][0]['player_id'],'Aw')
    def test_unauthenticated_roster_hash_rejected(self):
        p,meta=self.build(source='fabricated')
        self.assertEqual(p['roster'],[])
        self.assertIn('MISSING_ORIGINAL_ROSTER_EVIDENCE',meta['stat_source_rejections']['stat1'])
    def test_qb_starter_evidence_still_required(self):
        p,meta=self.build(position='QB')
        self.assertEqual(p['roster'],[])
        self.assertIn('QB_STARTER_NOT_VERIFIED',meta['stat_source_rejections']['stat1'])
