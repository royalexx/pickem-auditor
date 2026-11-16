"""Index observed discovery failures without rewriting their original logs."""
import ast,json,pathlib,re
out=pathlib.Path('docs/nba_architecture/completion_20261116');found=set()
for f in out.glob('*red.log'):
 found.update(re.findall(r'^(?:FAIL|ERROR): (test_\w+)',f.read_text(),re.M))
methods={}
for p in pathlib.Path('tests/nba_architecture').glob('test_*.py'):
 source=p.read_text()
 for n in ast.walk(ast.parse(source)):
  if isinstance(n,ast.FunctionDef):methods[n.name]=(str(p),ast.get_source_segment(source,n))
issues=[]
for name in sorted(found):
 p,code=methods[name]
 issues.append(dict(id='G0-COMPLETION-'+name,severity='HIGH',affected_contract=name,exact_invalid_input_or_valid_counterpart=code,original_behavior='FAIL/ERROR reproduced before repair; see discovery logs. These continuation logs are working-tree evidence, not independently frozen executions.',correct_behavior='Reject invalid resealed input, or accept legitimate numerical counterpart',root_cause='Absent '+name.removeprefix('test_').replace('_',' ')+' invariant',repair_location=['v2/nba_architecture/v2_contracts.py','v2/nba_architecture/families_v2.py','v2/nba_architecture/schema-2.0.0.json'],reproducer=p+'::'+name,positive_counterparts='invariants.json positive_tests and coherent_joint.json',final_result='Closed by final exact-SHA suite; not independent approval'))
prior=json.load(open('docs/nba_architecture/hardening_20261116/failure_ledger.json'))['issues']
(out/'failure_ledger.json').write_text(json.dumps(dict(version='1.1.0',prior_campaign_issues=prior,continuation_observed_failures=issues,new_complete_boundaries=['validate_forecast requires original G/O/J objects','validate_settlement requires original quote/view and complete correction history'],historical_twelve_repairs={'seven':'docs/nba_architecture/G0_REMEDIATION_20261116.json','five':'docs/nba_architecture/independent_final_20261116/DECISION.md','executable_inventory':'test_inventory.json'},unresolved_critical_or_high_g0=[]),indent=2)+'\n')
print(len(issues),'observed continuation discoveries indexed')
