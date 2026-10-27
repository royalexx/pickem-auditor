import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('workflow', Path(__file__).resolve().parents[1] / 'scripts/collect_workflow.py')
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)

class WorkflowTests(unittest.TestCase):
    def test_failure_stops_downstream_and_retains_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(w, 'run_stage', return_value={'name':'collect','returncode':2}) as stage:
                self.assertEqual(w.main(['--date','2026-10-26','--data-dir',d]),2)
            self.assertEqual(stage.call_count,1)
            m=json.loads(next(Path(d).rglob('manifest.json')).read_text())
            self.assertEqual(m['status'],'blocked')
            self.assertFalse(m['research_complete'])

    def test_success_is_not_research_completion_and_runs_are_isolated(self):
        def stage(name,args,directory,env,input_path=None):
            self.assertEqual(env['PICKEM_DATA_DIR'], str(directory))
            payload={'coverage':{'has_priced_history_rows':True}} if name=='collect' else {'counts':{'shortlisted':1}}
            if name!='prep': (directory/(name+'.json')).write_text(json.dumps(payload))
            return {'name':name,'returncode':0}
        with tempfile.TemporaryDirectory() as d, patch.object(w,'run_stage',side_effect=stage):
            for _ in range(2):
                self.assertEqual(w.main(['--date','2026-10-26','--data-dir',d]),0)
            manifests=list(Path(d).rglob('manifest.json'))
            self.assertEqual(len(manifests),2)
            for p in manifests:
                m=json.loads(p.read_text())
                self.assertEqual(m['status'],'research_required')
                self.assertFalse(m['research_complete'])

if __name__=='__main__': unittest.main()
