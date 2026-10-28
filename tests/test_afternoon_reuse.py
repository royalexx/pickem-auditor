"""Fresh pregame slate can be reused safely without a second paid odds request."""
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import jobs

class PrefetchTests(unittest.TestCase):
    def fixture(self,d,age=4,quote_age=4):
        root=Path(d);now=datetime(2026,10,27,20,tzinfo=timezone.utc)
        stamp=lambda minutes:(now-timedelta(minutes=minutes)).isoformat()
        slate=root/"slate_fetch.jsonl";quotes=root/"odds_quotes.jsonl"
        row={"sport":"NHL","game_date":"2026-10-27","player":"Example","stat":"shots on goal"}
        quote={"sport":"NHL","game_date":"2026-10-27","player":"Example","stat":"shots on goal","retrieved_at":stamp(quote_age)}
        slate.write_text(json.dumps(row)+"\n");quotes.write_text(json.dumps(quote)+"\n")
        (root/"slate_fetch.meta.json").write_text(json.dumps({"date":"2026-10-27","retrieved_at":stamp(age),"rows":1,"feeds":{"odds":{"status":"ok","rows":1}}}))
        return now,slate,quotes

    def test_reuses_verified(self):
        with tempfile.TemporaryDirectory() as d:
            now,s,q=self.fixture(d)
            rows,meta=jobs.reuse_recent_collect("2026-10-27",s,q,now=now)
            self.assertEqual((len(rows),meta["date"]),(1,"2026-10-27"))

    def test_stale_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            now,s,q=self.fixture(d,age=31)
            with self.assertRaisesRegex(jobs.JobError,"PREFETCH_STALE"):
                jobs.reuse_recent_collect("2026-10-27",s,q,now=now)

    def test_stale_odds_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            now,s,q=self.fixture(d,quote_age=31)
            with self.assertRaisesRegex(jobs.JobError,"PREFETCH_QUOTE_STALE"):
                jobs.reuse_recent_collect("2026-10-27",s,q,now=now)

    def test_mixed_fresh_and_stale_quotes_do_not_invalidate_fresh_markets(self):
        with tempfile.TemporaryDirectory() as d:
            now,slate,quotes=self.fixture(d,quote_age=4)
            old=json.loads(quotes.read_text().splitlines()[0])
            old["player"]="Old Market"
            old["retrieved_at"]=(now-timedelta(minutes=75)).isoformat()
            original=quotes.read_text()+json.dumps(old)+"\n"
            quotes.write_text(original)
            meta_file=Path(d)/"slate_fetch.meta.json"
            receipt=json.loads(meta_file.read_text())
            receipt["feeds"]["odds"]["rows"]=2
            meta_file.write_text(json.dumps(receipt))
            rows,meta=jobs.reuse_recent_collect("2026-10-27",slate,quotes,now=now)
            self.assertEqual(meta["_excluded_stale_quotes"],1)
            self.assertEqual(len(meta["_fresh_quotes"]),1)
            self.assertEqual(meta["_fresh_quotes"][0]["player"],"Example")
            self.assertEqual(quotes.read_text(),original)
            self.assertEqual(json.loads(meta_file.read_text()),receipt)

    def test_quote_date_mismatch_rejected_even_when_other_quote_fresh(self):
        with tempfile.TemporaryDirectory() as d:
            now,slate,quotes=self.fixture(d)
            bad=json.loads(quotes.read_text())
            bad["game_date"]="2026-10-26"
            quotes.write_text(quotes.read_text()+json.dumps(bad)+"\n")
            meta_file=Path(d)/"slate_fetch.meta.json"
            receipt=json.loads(meta_file.read_text())
            receipt["feeds"]["odds"]["rows"]=2
            meta_file.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(jobs.JobError,"PREFETCH_QUOTE_DATE_MISMATCH"):
                jobs.reuse_recent_collect("2026-10-27",slate,quotes,now=now)

    def test_event_start_in_quote_is_usable_without_new_paid_event_fetch(self):
        from datetime import datetime
        quotes=[{"sport":"NHL","team":"BOS","opponent":"TOR",
                 "event_id":"event","event_start":"2026-10-27T23:00:00Z"}]
        indexed=jobs.commence_index_from_quotes(quotes,[])
        self.assertEqual(indexed[("NHL","bos","tor")],"2026-10-27T23:00:00Z")
        self.assertTrue(jobs.game_started(indexed[("NHL","bos","tor")],
                                            datetime(2026,10,27,23,1,tzinfo=timezone.utc)))

    def test_cross_date_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            now,s,q=self.fixture(d)
            with self.assertRaisesRegex(jobs.JobError,"PREFETCH_DATE_MISMATCH"):
                jobs.reuse_recent_collect("2026-10-26",s,q,now=now)

    def test_no_odds_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            now,s,q=self.fixture(d);q.unlink()
            with self.assertRaisesRegex(jobs.JobError,"PREFETCH_MISSING"):
                jobs.reuse_recent_collect("2026-10-27",s,q,now=now)
