"""Controlled public-CLI failure; forces event budget5, not a forecast issue."""
from pathlib import Path
import contextlib,importlib.util,io,json,sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from v2.nba_joint import coherent_predictive_v1 as k
P=ROOT/'docs/nba_architecture/coherent_opportunity_20261120';HERE=Path(__file__).resolve().parent;out=HERE/'failed_cli_control';s=importlib.util.spec_from_file_location('controlled_cli',ROOT/'scripts/nba_coherent.py');cli=importlib.util.module_from_spec(s);s.loader.exec_module(cli);original=k.generate
calls=[]
def force_failure(*args,**kwargs):
 assert kwargs['n']==64 and kwargs['event_budget']==4096;calls.append({'requested_n':64,'requested_event_budget':4096,'forced_event_budget':5});kwargs['event_budget']=5;return original(*args,**kwargs)
stream=io.StringIO();exit_code=None
with patch.object(k,'generate',force_failure),patch.object(sys,'argv',['scripts/nba_coherent.py','predict','--output',str(out)]),contextlib.redirect_stdout(stream):
 try:cli.main()
 except SystemExit as exc:exit_code=exc.code
(out/'CONTROLLED_STDOUT.txt').write_text(stream.getvalue());assert exit_code==2;reject=json.loads((out/'REJECTED_ATTEMPTS.json').read_bytes());bank=json.loads((out/'BANK.json').read_bytes());assert len(reject['rows'])==reject['attempts']==280;assert reject['primitive_attempts']==140;assert reject['forecasts']==reject['actual_scores']==0;assert sum(r['status']=='REJECTED_FAILED_BATCH' for r in reject['rows'])==112;assert sum(r['status']=='ABSTAINED_SOURCE_OR_MINUTE_MODEL' for r in reject['rows'])==168;assert bank['status']=='FAILED_WHOLE_RUN' and len(bank['failed'])==len(bank['scenarios'])==64;assert not(out/'MARGINALS.json').exists();assert not(out/'COHERENCE.json').exists();result={'CONTROLLED_FAULT_INJECTION_NOT_A_PROSPECTIVE_FORECAST':True,'raw_cli_exit_code':exit_code,'requested_and_forced_budgets':calls,'failed_scenarios_retained':64,'market_attempts':280,'primitive_attempts':140,'rejected_supported':112,'source_abstentions':168,'forecasts':0,'actual_scores':0,'new_fit_calls':0,'successful_subset_exposed':False};(HERE/'FAILED_CLI_RESULTS.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result,indent=2))
