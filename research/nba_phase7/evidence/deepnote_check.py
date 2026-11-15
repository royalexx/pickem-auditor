# Authorized bounded fixture verification. No project-storage writes or live source collection.
import hashlib,io,json,os,pathlib,shutil,subprocess,sys,tempfile,urllib.request,zipfile
PIN='af8c0893429034924be40f02aea62582e284bfec'
root=pathlib.Path(tempfile.mkdtemp(prefix='nba_phase7_fixture_'))
url='https://codeload.github.com/royalexx/pickem-auditor/zip/'+PIN
with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'NBA-Phase7-Pinned-Fixture'}),timeout=90) as response:
    archive=zipfile.ZipFile(io.BytesIO(response.read()))
for item in archive.infolist():
    parts=pathlib.PurePosixPath(item.filename).parts
    if len(parts)<2 or '..' in parts:continue
    target=root.joinpath(*parts[1:])
    if item.is_dir():target.mkdir(parents=True,exist_ok=True)
    else:
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(item))
env={**os.environ,'OPENBLAS_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'}
pdf_available=shutil.which('pdftotext') is not None
script='''import os,unittest,json,shutil
suite=unittest.defaultTestLoader.discover('tests/nba_phase7')
def leaves(s):
 for t in s:
  if isinstance(t,unittest.TestSuite):yield from leaves(t)
  else:yield t
all_tests=list(leaves(suite));omitted=[];kept=[]
for t in all_tests:
 if not shutil.which('pdftotext') and any(x in t.id() for x in ('original_official_pdf_parse','future_official_report')):omitted.append(t.id())
 else:kept.append(t)
r=unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(kept))
print('PHASE7_TEST_RECEIPT',json.dumps({'run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'pdf_checks_unavailable':omitted,'pdftotext_available':bool(shutil.which('pdftotext'))},sort_keys=True))
assert r.wasSuccessful()
'''
p=subprocess.run([sys.executable,'-B','-c',script],cwd=root,env=env,text=True,capture_output=True,timeout=120)
print(p.stdout[-4000:]);print(p.stderr[-1500:]);assert p.returncode==0,'PINNED_PHASE7_TEST_FAILURE'
p=subprocess.run([sys.executable,'-B','-m','research.nba_phase7.smoke','--output',str(root/'work/phase7_smoke')],cwd=root,env=env,text=True,capture_output=True,timeout=120)
assert p.returncode==0,(p.stdout+p.stderr)[-2000:]
r=json.loads((root/'work/phase7_smoke/receipt.json').read_text())
print('PHASE7_DEEPNOTE_FIXTURE',json.dumps({'pin':PIN,'storage':'read-only project; temporary fixture files only','new_source_requests':0,'source_qualified_forecasts':0,'smoke':{k:r[k] for k in ('status','scenarios','violations','model_sha256','output_sha256','cpu_seconds','wall_seconds','peak_process_rss_mib')},'pdf_available':pdf_available,'independent_statistical_approval':False},sort_keys=True))
