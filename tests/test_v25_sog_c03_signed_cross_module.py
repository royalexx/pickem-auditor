"""Cross-module C03 HMAC -> NHL SOG official history integrity regression.

Synthetic signed test fixtures only. This DOES NOT certify a live upstream
HTTP collection or its actual publisher timestamp. Tests the joint verifier.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.c03_context_cohorts import archive_response, canonical
from scripts import c03_live_transport as transport
from v2.nhl_sog_exposure_shadow import ExperimentBlocked
from v2.nhl_sog_official_history_producer import (
    import_signed_official_history, independent_verify_observation_lineage,
)

ROOT=Path(__file__).resolve().parents[1]
PLAYER="8470000"
GAME="2026020310"
TEST_KEY="83"*32


def signed_fixture(root:Path, *, source_url:str, document:dict, clock:str, source_id:str)->dict:
    raw=json.dumps(document,sort_keys=True,separators=(",",":")).encode()
    receipt=archive_response(
        raw,archive_root=root,source_url=source_url,
        observed_at=clock,received_at=clock,source_id=source_id,
        source_namespace="nhl_official",http_status=200,
    )
    receipt["transport_attestation"]="collector_signed_tls_bytes_v1"
    proof={"schema":transport.SCHEMA,
           "receipt_fields":transport._signed_body(receipt),
           "hmac_sha256":transport._mac(receipt,transport._key())}
    proof_bytes=canonical(proof)
    digest=hashlib.sha256(proof_bytes).hexdigest()
    path=root/"c03_collector_receipts"/(digest+".json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(proof_bytes)
    receipt["collector_proof_archive_path"]="c03_collector_receipts/"+digest+".json"
    receipt["collector_proof_sha256"]=digest
    return receipt


class C03NHLSourceIntegrationTests(unittest.TestCase):
    def test_standalone_package_can_reach_integrated_signed_verifier(self):
        env=dict(os.environ,PYTHONPATH=str(ROOT))
        code=(
            "from v2.nhl_sog_official_history_producer import _signed\n"
            "from v2.nhl_sog_exposure_shadow import ExperimentBlocked\n"
            "try:\n"
            "    _signed({},'.','2026-11-11T18:00:00Z','2026-11-12T00:00:00Z')\n"
            "except ExperimentBlocked as exc:\n"
            "    assert 'C03_SIGNED_COLLECTOR_NOT_IN_INTEGRATION_BASE' not in str(exc),str(exc)\n"
            "    assert 'AUTHENTIC_RAW_NHL_SOURCE_NOT_VERIFIED:' in str(exc),str(exc)\n"
            "else:\n"
            "    raise AssertionError('unsigned evidence accepted')\n"
            "print('C03_SOG_STANDALONE_VERIFIER_REACHED')\n"
        )
        proc=subprocess.run([sys.executable,"-c",code],cwd=ROOT,env=env,
                            capture_output=True,text=True,timeout=30)
        self.assertEqual(proc.returncode,0,proc.stdout+"\n"+proc.stderr)
        self.assertIn("C03_SOG_STANDALONE_VERIFIER_REACHED",proc.stdout)

    def test_signed_official_history_import_and_independent_recheck(self):
        # A synthetic, unit-tested signer: same HMAC trust boundary, not a live capture.
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{
                "PICKEM_C03_COLLECTOR_HMAC_KEY_HEX":TEST_KEY}):
            root=Path(tmp)
            moment=datetime.now(timezone.utc)
            stamp=moment.isoformat().replace("+00:00","Z")
            cutoff=(moment+timedelta(minutes=5)).isoformat().replace("+00:00","Z")
            next_game=(moment+timedelta(hours=1)).isoformat().replace("+00:00","Z")
            url="https://api-web.nhle.com/v1/"
            profile=signed_fixture(root,source_url=url+"player/"+PLAYER+"/landing",
                    document={"playerId":int(PLAYER),"position":"C",
                     "firstName":{"default":"Test"},"lastName":{"default":"Skater"}},
                    clock=stamp,source_id="test_profile")
            log=signed_fixture(root,source_url=url+"player/"+PLAYER+"/game-log/20262027/2",
                    document={"gameLog":[{"gameId":int(GAME),"shots":3,"toi":"20:30"}]},
                    clock=stamp,source_id="test_log")
            final=signed_fixture(root,source_url=url+"gamecenter/"+GAME+"/landing",
                    document={"id":int(GAME),"gameState":"OFF"},
                    clock=stamp,source_id="test_final")
            imported=import_signed_official_history(
                player_id=PLAYER,position_group="F",gamelog_receipt=log,
                player_profile_receipt=profile,completed_game_receipts={GAME:final},
                archive_root=root,input_freeze_at=cutoff,event_start_at=next_game)
            self.assertEqual(len(imported),1)
            obs=independent_verify_observation_lineage(
                imported[0],archive_root=root,freeze=cutoff,event_start=next_game)
            self.assertEqual(obs["source_kind"],"collector_observed_bytes")
            self.assertTrue(imported[0]["raw_log_receipt"]["source_publication_truth_verified"] is False)
            self.assertFalse(any("production" in x.lower() for x in imported[0]["observation_receipt"]))
            # An exact derived-row cache can accelerate verification while all
            # signed upstream bodies and HMAC proofs are still read at root.
            cache=root/"cache"
            local=cache/obs["archive_path"]
            local.parent.mkdir(parents=True)
            derived_bytes=(root/obs["archive_path"]).read_bytes()
            local.write_bytes(derived_bytes)
            self.assertEqual(independent_verify_observation_lineage(
                imported[0],archive_root=root,freeze=cutoff,event_start=next_game,
                observation_root=cache),obs)
            local.write_bytes(derived_bytes+b" ")
            with self.assertRaisesRegex(ExperimentBlocked,"SOURCE_DIGEST_MISMATCH"):
                independent_verify_observation_lineage(
                    imported[0],archive_root=root,freeze=cutoff,event_start=next_game,
                    observation_root=cache)
            local.write_bytes(derived_bytes)
            # Proof tamper must fail even if the structured observation already exists.
            original_path=root/log["collector_proof_archive_path"]
            original=original_path.read_bytes()
            original_path.write_bytes(original+b" ")
            with self.assertRaisesRegex(ExperimentBlocked,"AUTHENTIC_RAW_NHL_SOURCE_NOT_VERIFIED"):
                independent_verify_observation_lineage(
                    imported[0],archive_root=root,freeze=cutoff,event_start=next_game,
                    observation_root=cache)
            original_path.write_bytes(original)
            # Body tamper must also fail, even when the derived observation was not altered.
            rawpath=root/log["archive_path"]
            rawpath.write_bytes(b'{"gameLog":[]}')
            with self.assertRaisesRegex(ExperimentBlocked,"AUTHENTIC_RAW_NHL_SOURCE_NOT_VERIFIED"):
                independent_verify_observation_lineage(
                    imported[0],archive_root=root,freeze=cutoff,event_start=next_game)

if __name__=="__main__":
    unittest.main()
