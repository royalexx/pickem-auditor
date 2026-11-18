"""Execute exact hosted worker with isolated synthetic storage/clock/subprocess.
Actual hosted probe runs are separate evidence; this tests binary export protocol.
"""
import base64,hashlib,io,json,pathlib,subprocess,tarfile,tempfile,unittest
from datetime import datetime,timezone
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[4];P=ROOT/'docs/nba_architecture/p1_prospective_20261118';CODE=(P/'HOSTED_WORKER.py').read_bytes();RealPath=pathlib.Path
class Fixed(datetime):
 @classmethod
 def now(cls,tz=None):return cls(2026,11,19,11,0,tzinfo=timezone.utc)
class Early(datetime):
 @classmethod
 def now(cls,tz=None):return cls(2026,11,18,12,0,tzinfo=timezone.utc)
class Response:
 def __init__(self,raw):self.raw=raw
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def read(self):return self.raw
class Hosted(unittest.TestCase):
 def execute(self,store,mode='morning',clock=Fixed,mutate=False):
  def path(*args,**kw):return store if args==('/work/reports/nba_p1_one_night_20261118',) else RealPath(*args,**kw)
  def fetch(request,**kw):
   relative=request.full_url.split('aaeb0601c006d55d3812dc64cf29695a72eda58b/',1)[1];raw=(ROOT/relative).read_bytes();return Response(raw+b'x' if mutate else raw)
  def run(cmd,**kw):
   self.assertIn('--stage',cmd);dest=RealPath(cmd[cmd.index('--output')+1])/'synthetic-attempt';dest.mkdir(parents=True)
   (dest/'body.raw').write_bytes(bytes(range(256))*1000);(dest/'attempt.json').write_text('{"admission":"UNADMITTED"}')
   return subprocess.CompletedProcess(cmd,0,'synthetic capture stdout\n','')
  with patch('pathlib.Path',path),patch('datetime.datetime',clock),patch('urllib.request.urlopen',fetch),patch('subprocess.run',run):exec(compile(CODE,'exact-HOSTED_WORKER.py','exec'),{'capture_mode':mode})
 def test_archive_binary_roundtrip_and_claim(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=RealPath(tmp)/'store';self.execute(store)
   latest=json.loads((store/'latest_morning.json').read_text());export=RealPath(latest['export_path']);meta=json.loads((export/'manifest.json').read_text());encoded=''.join((export/n).read_text() for n in meta['parts']);raw=base64.b64decode(encoded,validate=True)
   self.assertEqual(hashlib.sha256(raw).hexdigest(),meta['archive_sha256']);self.assertEqual(len(raw),meta['bytes']);self.assertTrue(all(len((export/n).read_text())<=32000 for n in meta['parts']))
   with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:self.assertEqual(archive.extractfile('synthetic-attempt/body.raw').read(),bytes(range(256))*1000)
   before=(store/'morning_claim.json').read_bytes()
   with self.assertRaises(FileExistsError):self.execute(store)
   self.assertEqual((store/'morning_claim.json').read_bytes(),before)
 def test_outside_window_and_pin_mutation(self):
  for mode,clock,mutation,reason in [('pregame',Early,False,'OUTSIDE_BOUNDED'),('morning',Early,False,'OUTSIDE_ONE_NIGHT'),('probe',Fixed,True,'PINNED_CODE_OR_COHORT_CHANGED')]:
   with tempfile.TemporaryDirectory() as tmp,self.subTest(mode=mode,mutate=mutation),self.assertRaisesRegex(RuntimeError,reason):self.execute(RealPath(tmp)/'store',mode,clock,mutation)
if __name__=='__main__':unittest.main(verbosity=2)
