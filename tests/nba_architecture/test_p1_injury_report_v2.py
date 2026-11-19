from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from v2.nba_architecture.p1_injury_report_v2 import select_report, report_time, verify_report, capture_latest

ROOT=Path(__file__).resolve().parents[2]
U='https://ak-static.cms.nba.com/referee/injury/Injury-Report_'
def url(day,clock):return U+day+'_'+clock+'.pdf'
def index(*urls):return (' '.join('<a href="'+u+'">pdf</a>' for u in urls)).encode()

class InjuryV2Tests(unittest.TestCase):
    def test_original_actual_index_red_is_chronologically_repaired(self):
        p=ROOT/'docs/nba_architecture/p1_overnight_20261119/raw/pregame-20261118T234000059565Z-aae5f441/official-injury-index/body.raw'
        x=select_report(p.read_bytes(),observed_at='2026-11-18T23:40:02Z',freeze_at='2026-11-18T23:45:00Z')
        self.assertEqual(x['selected_url'],url('2026-11-18','06_30PM'))
        self.assertEqual(x['unique_urls'],x['eligible_urls']+x['rejected_urls'])
        self.assertIsNone(x['source_publication_at'])

    def test_am_pm_midnight_noon_and_day_order(self):
        self.assertLess(report_time(url('2026-11-19','12_45AM')),report_time(url('2026-11-19','12_45PM')))
        self.assertEqual(report_time(url('2026-11-19','12_45AM')).hour,5)
        self.assertEqual(report_time(url('2026-11-19','12_45PM')).hour,17)
        x=select_report(index(url('2026-11-18','11_45PM'),url('2026-11-19','12_15AM')),observed_at='2026-11-19T05:20:00Z',freeze_at='2026-11-19T05:30:00Z')
        self.assertEqual(x['selected_url'],url('2026-11-19','12_15AM'))

    def test_missing_stale_future_and_invalid_urls_retained(self):
        candidates=[url('2026-11-19','01_00PM'),url('2026-11-19','03_00PM'),url('2026-11-19','02_00PM'),url('2026-11-19','13_00PM'),url('2026-02-30','01_00PM'),url('2026-11-19','02_99PM'),url('2026-11-19','02_00PM')+'?approve=1',url('2026-11-19','02_00PM').replace('ak-static.cms.nba.com','evil.test')]
        x=select_report(index(*candidates),observed_at='2026-11-19T19:10:00Z',freeze_at='2026-11-19T19:20:00Z')
        self.assertEqual(x['selected_url'],url('2026-11-19','02_00PM'));self.assertEqual(x['unique_urls'],8);self.assertEqual(x['rejected_urls'],7)
        self.assertIsNone(select_report(b'',observed_at='2026-11-19T19:10:00Z',freeze_at='2026-11-19T19:20:00Z')['selected_url'])

    def test_timezones_and_dst_reject_ambiguous_clocks(self):
        for candidate in [url('2026-11-01','01_30AM'),url('2026-03-08','02_30AM')]:
            with self.assertRaises(ValueError):report_time(candidate)
        with self.assertRaises(ValueError):select_report(b'',observed_at='2026-11-19T19:10:00',freeze_at='2026-11-19T19:20:00Z')
        with self.assertRaises(ValueError):select_report(b'',observed_at='2026-11-19T19:30:00Z',freeze_at='2026-11-19T19:20:00Z')

    def test_actual_pdf_printed_header_mismatch_and_invalid_body(self):
        p=ROOT/'docs/nba_architecture/p1_overnight_20261119/raw/pregame-20261118T234000059565Z-aae5f441/injury-pdf-0/body.raw'
        verify_report(p,url('2026-11-18','12_45AM'))
        with self.assertRaisesRegex(ValueError,'MISMATCH'):verify_report(p,url('2026-11-18','06_30PM'))
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'error';f.write_bytes(b'Access Denied')
            with self.assertRaisesRegex(ValueError,'PDF_BODY_REQUIRED'):verify_report(f,url('2026-11-18','06_30PM'))

    def test_latest_unavailable_no_fallback_preserves_denial(self):
        now=datetime.now(timezone.utc);local=now.astimezone(__import__('zoneinfo').ZoneInfo('America/New_York'));candidate=url(local.strftime('%Y-%m-%d'),local.strftime('%I_%M%p'))
        calls=[]
        def denied(source,dest):
            dest.mkdir();calls.append(source)
            if len(calls)==1:
                (dest/'body.raw').write_bytes(index(candidate));return {'status':200,'ingested_at':now.isoformat()}
            (dest/'body.raw').write_bytes(b'denied');return {'status':403,'ingested_at':now.isoformat()}
        with tempfile.TemporaryDirectory() as tmp,patch('v2.nba_architecture.p1_injury_report_v2.capture',side_effect=denied):
            out=Path(tmp)/'out';x=capture_latest(freeze_at=(now+timedelta(minutes=5)).isoformat(),output=out)
            self.assertEqual(x['status'],'REJECTED');self.assertEqual(len(calls),2)
            self.assertIn('LATEST_REPORT_HTTP_UNAVAILABLE_NO_FALLBACK',x['errors']);self.assertEqual((out/'report/body.raw').read_bytes(),b'denied')
            with self.assertRaises(FileExistsError):capture_latest(freeze_at=(now+timedelta(minutes=5)).isoformat(),output=out)

    def test_past_freeze_does_not_fetch(self):
        with tempfile.TemporaryDirectory() as tmp,patch('v2.nba_architecture.p1_injury_report_v2.capture',side_effect=AssertionError('late network')):
            x=capture_latest(freeze_at='2026-11-18T23:45:00Z',output=Path(tmp)/'late')
            self.assertIn('CAPTURE_STARTED_AFTER_FREEZE',x['errors'])

    def test_malformed_href_never_synthesizes_a_valid_prefix(self):
        good=url('2026-11-19','02_00PM')
        bad=[good+'.evil',good+'/garbage',good+' junk',good+'#approved']
        x=select_report(index(*bad),observed_at='2026-11-19T19:10:00Z',freeze_at='2026-11-19T19:20:00Z')
        self.assertIsNone(x['selected_url']);self.assertEqual(x['unique_urls'],4)
        self.assertEqual(x['rejected_urls'],4)
        self.assertEqual({r['url'] for r in x['ledger']},set(bad))

    def test_matching_href_delimiters_preserve_embedded_other_quote(self):
        bad=url('2026-11-19','02_00PM')+"'evil"
        x=select_report(index(bad),observed_at='2026-11-19T19:10:00Z',freeze_at='2026-11-19T19:20:00Z')
        self.assertIsNone(x['selected_url']);self.assertEqual(x['ledger'][0]['url'],bad)
