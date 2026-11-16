import ast,json,pathlib,shutil,subprocess,tempfile,time
root=pathlib.Path.cwd();out=root/'docs/nba_architecture/completion_20261116';results=[]
for code in ['ZERO_PROBABILITY_PARTICIPATION','CERTAIN_PARTICIPATION_DNP','CONDITIONAL_TARGET_DNP','O_DRAW_OUTSIDE_MINUTES_SUPPORT']:
 with tempfile.TemporaryDirectory(prefix='g0-mutant-') as td:
  work=pathlib.Path(td);shutil.copytree(root/'v2/nba_architecture',work/'v2/nba_architecture',ignore=shutil.ignore_patterns('__pycache__'));shutil.copytree(root/'tests/nba_architecture',work/'tests/nba_architecture',ignore=shutil.ignore_patterns('__pycache__'))
  for path in (work/'v2/nba_architecture').glob('*.py'):
   tree=ast.parse(path.read_text());changed=[False]
   class Mutator(ast.NodeTransformer):
    def visit_Call(self,node):
     if isinstance(node.func,ast.Name) and node.func.id=='req' and len(node.args)==2 and isinstance(node.args[1],ast.Constant) and node.args[1].value==code:
      node.args[0]=ast.Constant(True);changed[0]=True
     return self.generic_visit(node)
   tree=Mutator().visit(tree)
   if changed[0]:path.write_text(ast.unparse(ast.fix_missing_locations(tree))+'\n')
  cmd=['python','-m','unittest','discover','-s','tests/nba_architecture','-p','test_g0*.py','-v'];r=subprocess.run(cmd,cwd=work,capture_output=True,text=True)
  (out/('mutant-'+code+'.log')).write_text(r.stdout+r.stderr)
  results.append(dict(disabled_guard=code,exit=r.returncode,killed=r.returncode!=0,unexpected_import_error='ImportError' in r.stderr));print(results[-1],flush=True)
(out/'guard_mutation_results.json').write_text(json.dumps(results,indent=2)+'\n')
assert all(r['killed'] and not r['unexpected_import_error'] for r in results)
