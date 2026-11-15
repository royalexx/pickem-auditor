"""Reproducible targeted test receipt, separate from statistical acceptance."""
import io
import json
from pathlib import Path
import unittest


def main():
    root=Path('research/nba_joint_v01/results');root.mkdir(exist_ok=True)
    specs=[('tests/nba_ws1','test_*.py'),('tests','test_nba_opportunity.py'),('tests','test_nba_joint*.py'),('tests','test_v25_nhl_nba_phase1.py'),('tests','test_v25_official_capture.py'),('tests','test_population_multisport.py')]
    summaries=[]
    for directory,pattern in specs:
        stream=io.StringIO();suite=unittest.TestLoader().discover(directory,pattern=pattern)
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        log=root/('tests_'+pattern.replace('*','all').replace('.py','')+'.log')
        with log.open('x') as f:f.write(stream.getvalue())
        summaries.append(dict(suite=directory+'/'+pattern,run=result.testsRun,passed=result.testsRun-len(result.skipped)-len(result.errors)-len(result.failures),failed=len(result.failures),errors=len(result.errors),skipped=[{'test':str(t),'reason':r} for t,r in result.skipped],successful=result.wasSuccessful()))
    total=dict(run=sum(r['run'] for r in summaries),passed=sum(r['passed'] for r in summaries),failed=sum(r['failed'] for r in summaries),errors=sum(r['errors'] for r in summaries),skipped=sum(len(r['skipped']) for r in summaries))
    with (root/'test_receipt.json').open('x') as f:json.dump(dict(suites=summaries,total=total),f,indent=2,sort_keys=True)
    print(json.dumps(total))
    if not all(r['successful'] for r in summaries):raise SystemExit(1)


if __name__=='__main__':main()
