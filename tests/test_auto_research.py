"""Structured source research must preserve game identity and refuse invented status."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime,timezone

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import auto_research as ar

NOW=datetime(2026,10,27,20,0,tzinfo=timezone.utc)

class AutoResearchTests(unittest.TestCase):
    def make(self,tmp,date="2026-10-27"):
        root=Path(tmp)
        for name in ("slate.jsonl","odds.jsonl"):
            (root/name).write_text('{"sport":"NHL"}\n')
        packet=root/"research.json"
        packet.write_text(json.dumps({"date":date,"availability":{},"weather":{},"index":{"by_player":{}}}))
        return root/"slate.jsonl",root/"odds.jsonl",packet,root/"receipt.json"

    def test_conflicting_date_is_not_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            s,q,p,o=self.make(tmp,"2026-10-26")
            content=p.read_bytes()
            with self.assertRaisesRegex(ValueError,"RESEARCH_PACKET_DATE_MISMATCH"):
                ar.refresh(slate=s,quotes=q,packet_path=p,out=o,now=NOW,fetch=lambda *a,**k:{})
            self.assertEqual(p.read_bytes(),content)

    def test_confirmed_only_resolver_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            s,q,p,o=self.make(tmp)
            candidates=[{"id":"NHL|Example|shots on goal|over"}]
            result={"date":"2026-10-27","availability":{},"weather":{},"index":{"by_player":{}}}
            diag={"attempts":[{"status":"source_failed"}],"verified_pregame_games":[],"resolved_statuses":[]}
            with patch.object(ar.fs,"prepare_pipeline",return_value=candidates):
                with patch.object(ar,"resolve",return_value=(result,diag)):
                    receipt=ar.refresh(slate=s,quotes=q,packet_path=p,out=o,now=NOW,fetch=lambda *a,**k:{})
            self.assertFalse(receipt["evidence_complete"])
            self.assertEqual(receipt["resolved_statuses"],0)
            self.assertEqual(json.loads(p.read_text())["availability"],{})
            self.assertTrue(o.exists())

    def test_missing_price_candidates_block_research(self):
        with tempfile.TemporaryDirectory() as tmp:
            s,q,p,o=self.make(tmp)
            with patch.object(ar.fs,"prepare_pipeline",return_value=[]):
                with self.assertRaisesRegex(ValueError,"RESEARCH_NO_PRICED_CANDIDATES"):
                    ar.refresh(slate=s,quotes=q,packet_path=p,out=o,now=NOW,fetch=lambda *a,**k:{})
