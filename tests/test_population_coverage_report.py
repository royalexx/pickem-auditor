import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from population_coverage_report import summarize

class PopulationCoverageReportTests(unittest.TestCase):
    def test_missing_recent_dates_cannot_claim_training_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for sport,stat,years in [('NHL','hits',[2018,2023]),
                                      ('NBA','points',[2019,2024]),
                                      ('NFL','tackles_assists',[2018,2019,2020,2021,2022])]:
                folder=root/'data/bayesian_warehouse/populations'/sport.lower()/stat
                folder.mkdir(parents=True)
                for year in years:(folder/f'{year}.jsonl.gz').write_bytes(b'')
            report=summarize(root,as_of='2026-10-29')
            self.assertFalse(report['sports']['NHL']['recent']['caught_up_to_as_of'])
            self.assertFalse(report['sports']['NBA']['sufficient_recent_source_continuity_for_as_of'])
            self.assertEqual(report['sports']['NFL']['completed_season_source_through'],2017)
            self.assertTrue(report['no_claim_of_training_validation'])
            self.assertEqual(report['sports']['NHL']['markets']['hits']['missing_in_partition_span'],[2019,2020,2021,2022])
    def test_workflow_prioritizes_recent_before_legacy(self):
        workflow=(Path(__file__).resolve().parents[1]/'.github/workflows/multisport-population-history.yml').read_text()
        self.assertLess(workflow.index('- name: Prioritize verified NHL 2023-present'),
                        workflow.index('- name: NHL skater hits/blocks'))
        self.assertLess(workflow.index('- name: Prioritize verified NBA 2023-present'),
                        workflow.index('- name: NBA points, rebounds'))
        self.assertIn('scripts/population_coverage_report.py',workflow)
        self.assertIn('reports/population_coverage.json',workflow)
if __name__=='__main__':
    unittest.main()
