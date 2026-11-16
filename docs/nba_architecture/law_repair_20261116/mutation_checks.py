"""Remove each repaired boundary in temporary source copies; tests must catch it."""
import json,pathlib,shutil,subprocess,tempfile,hashlib
root=pathlib.Path.cwd();source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();raw={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'v2/nba_architecture').glob('*.py')};out=root/'docs/nba_architecture/law_repair_20261116';results=[]
for name in ('O_COUPLING','FORECAST_EXPOSURE'):
 with tempfile.TemporaryDirectory(prefix='g0-law-mutant-') as td:
  work=pathlib.Path(td)
  for area in ('v2/nba_architecture','tests/nba_architecture'):
   shutil.copytree(root/area,work/area,ignore=shutil.ignore_patterns('__pycache__'))
  f=work/'v2/nba_architecture/families_v2.py';s=f.read_text()
  if name=='O_COUPLING':
   old='    validate_exposure_coupling(o, p, g)\n    return True'
   assert old in s;s=s.replace(old,'    return True',1)
  else:
   start=s.index('    from .exposure_v2 import positive_exposure_bound')
   end=s.index("    if d['pipeline_mode'] == 'S_O_J':",start)
   s=s[:start]+s[end:]
  f.write_text(s)
  cmd=['python','-m','unittest','discover','-s','tests/nba_architecture','-p','test_g0_law_repair*','-v']
  r=subprocess.run(cmd,cwd=work,capture_output=True,text=True)
  (out/('mutant-'+name+'.log')).write_text(r.stdout+r.stderr)
  results.append(dict(source_commit=source_sha,source_raw_sha256=raw,disabled_boundary=name,command=cmd,exit=r.returncode,killed=r.returncode!=0,
                      import_error='ImportError' in r.stderr,summary=r.stderr.splitlines()[-4:]))
  print(results[-1],flush=True)
(out/'mutation_results.json').write_text(json.dumps(results,indent=2)+'\n')
assert all(r['killed'] and not r['import_error'] for r in results)
