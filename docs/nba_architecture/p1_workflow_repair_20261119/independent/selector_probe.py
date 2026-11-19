"""Independent public v2 selector/capture tests; hostile inputs are synthetic."""
import json,pathlib,tempfile,unittest
from datetime import datetime,timezone
from unittest.mock import patch
import v2.nba_architecture.p1_injury_report_v2 as m
ROOT=pathlib.Path(__file__).resolve().parents[4]
OLD=ROOT/'docs/nba_architecture/p1_overnight_20261119/raw/pregame-20261118T234000059565Z-aae5f441'
U='https://ak-static.cms.nba.com/referee/injury/Injury-Report_'
def url(clock):return U+'2026-11-19_'+clock+'.pdf'
def select(raw):return m.select_report(raw,observed_at='2026-11-19T19:10:00Z',freeze_at='2026-11-19T19:15:00Z')
class Fixed(datetime):
 @classmethod
 def now(cls,tz=None):return cls(2026,11,18,17,50,tzinfo=timezone.utc)
class Independent(unittest.TestCase):
 def test_actual_old_index_replay_clock_only(self):
  receipt=json.loads((OLD/'official-injury-index/receipt.json').read_bytes());x=m.select_report((OLD/'official-injury-index/body.raw').read_bytes(),observed_at=receipt['ingested_at'],freeze_at='2026-11-18T23:45:00Z')
  self.assertEqual(x['selected_url'],U+'2026-11-18_06_30PM.pdf');self.assertEqual(x['unique_urls'],82);self.assertEqual(x['eligible_urls']+x['rejected_urls'],82);self.assertIsNone(x['source_publication_at']);self.assertEqual(x['admission'],'UNADMITTED')
 def test_complete_href_suffix_quote_entity_attacks(self):
  base=url('02_00PM')
  for suffix in ['.evil','/tail','?approved=true','#fragment',"'tail",'&quot;tail','&#34;tail','&#39;tail',' extra']:
   raw=('<a href="'+base+suffix+'">x</a>').encode();x=select(raw)
   with self.subTest(suffix=suffix):self.assertIsNone(x['selected_url']);self.assertEqual(x['unique_urls'],1);self.assertEqual(x['rejected_urls'],1)
 def test_future_stale_unsupported_and_occurrences(self):
  values=[url('02_00PM'),url('02_00PM'),url('03_00PM'),url('12_45PM'),url('02_00PM').replace('ak-static.cms.nba.com','evil.test'),U+'2026-02-30_02_00PM.pdf']
  x=select(''.join('<a href="'+v+'">x</a>' for v in values).encode());self.assertEqual((x['url_occurrences'],x['unique_urls'],x['eligible_urls'],x['rejected_urls']),(6,5,1,4));self.assertEqual(x['selected_url'],url('02_00PM'))
 def test_calendar_zone_and_freeze(self):
  self.assertEqual(m.report_time(url('12_45AM')).isoformat(),'2026-11-19T05:45:00+00:00');self.assertEqual(m.report_time(url('12_45PM')).isoformat(),'2026-11-19T17:45:00+00:00')
  for u in [U+'2026-11-01_01_30AM.pdf',U+'2026-03-08_02_30AM.pdf']:
   with self.assertRaises(ValueError):m.report_time(u)
  for observed,freeze in [('2026-11-19T19:10:00','2026-11-19T19:15:00Z'),('2026-11-19T19:20:00Z','2026-11-19T19:15:00Z')]:
   with self.assertRaises(ValueError):m.select_report(b'',observed_at=observed,freeze_at=freeze)
 def test_real_printed_pdf_rejects_wrong_clock(self):
  pdf=OLD/'injury-pdf-0/body.raw';m.verify_report(pdf,U+'2026-11-18_12_45AM.pdf')
  with self.assertRaisesRegex(ValueError,'MISMATCH'):m.verify_report(pdf,U+'2026-11-18_06_30PM.pdf')
 def test_public_denial_and_late_no_fallback(self):
  candidate=U+'2026-11-18_12_45PM.pdf';pdf=(OLD/'injury-pdf-1/body.raw').read_bytes()
  for denial in [True,False]:
   calls=[]
   def capture(source,dest):
    dest.mkdir();calls.append(source)
    raw=('<a href="'+candidate+'">x</a>').encode() if len(calls)==1 else b'denied' if denial else pdf
    (dest/'body.raw').write_bytes(raw)
    return dict(status=403 if len(calls)==2 and denial else 200,ingested_at='2026-11-18T18:01:00Z' if len(calls)==2 and not denial else '2026-11-18T17:50:00Z')
   with tempfile.TemporaryDirectory() as tmp,patch.object(m,'datetime',Fixed),patch.object(m,'capture',capture):
    out=pathlib.Path(tmp)/'out';x=m.capture_latest(freeze_at='2026-11-18T18:00:00Z',output=out);self.assertEqual(x['status'],'REJECTED');self.assertEqual(len(calls),2);self.assertIn('LATEST_REPORT_HTTP_UNAVAILABLE_NO_FALLBACK' if denial else 'REPORT_CAPTURE_AFTER_FREEZE',x['errors']);self.assertTrue((out/'report/body.raw').exists())
    with self.assertRaises(FileExistsError):m.capture_latest(freeze_at='2026-11-18T18:00:00Z',output=out)
 def test_no_fetch_after_freeze(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(m,'capture',side_effect=AssertionError('network afterfreeze')):
   x=m.capture_latest(freeze_at='2026-11-18T23:45:00Z',output=pathlib.Path(tmp)/'late');self.assertEqual(x['errors'],['CAPTURE_STARTED_AFTER_FREEZE'])
if __name__=='__main__':unittest.main(verbosity=2)
