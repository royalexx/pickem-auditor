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
