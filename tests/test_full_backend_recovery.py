"""Regression tests for frozen-history source proof and selective Stan recovery."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import full_backend_eval as model
import recover_full_backend_eval as recovery

class PinnedSourceAndRecovery(unittest.TestCase):
    def test_branch_head_advance_must_not_veto_frozen_commit(self):
        self.assertNotIn('history_warehouse_snapshot_sha_changed',
                         Path(ROOT/'scripts/full_backend_eval.py').read_text())
        self.assertIn('FROZEN_WAREHOUSE_SHA',
                      Path(ROOT/'scripts/full_backend_eval.py').read_text())
        text=Path(ROOT/'.github/workflows/recover-full-backend-coverage.yml').read_text()
        self.assertIn('FROZEN_WAREHOUSE_SHA:',text)
        self.assertIn('full-backend-reconciled',text.replace('_','-'))
    def test_recover_only_failed_stan_jobs(self):
        marks={k:{'status':'ready'} for k in model.MARKETS}
        plan={'market_count':31,'blocked_count':0,'archive_sha':'a'*40,'markets':marks}
        jobs=[{'name':'preflight','status':'completed','conclusion':'success'}]
        for market in marks:
            for backend in recovery.BACKENDS:
                jobs.append({'name':f'{market} / {backend}',
                             'status':'completed',
                             'conclusion':('failure' if market=='nba_ra' and
                                           backend=='cmdstanpy' else 'success')})
        receipt=recovery.retry_plan(plan,jobs)
        self.assertEqual(receipt['retry_matrix'],['nba_ra'])
        self.assertEqual(receipt['retry_count'],1)
        jobs[-1]['status']='in_progress'
        with self.assertRaisesRegex(ValueError,'original_run_not_finished'):
            recovery.retry_plan(plan,jobs)
    def test_changed_original_history_sha_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            record={'schema':model.VERSION,'markets':{
                'nba_points':{'status':'ready',
                              'configuration_sha256':'bad',
                              'train_source_digest':'a'}}}
            result=model.run_market(temp,'nba_points','pymc',record,
                                    draws=500,tune=700,chains=4,replicates=2)
            self.assertEqual(result['status'],'blocked_or_failed')

if __name__=='__main__':
    unittest.main()
