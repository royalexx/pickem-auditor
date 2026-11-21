"""Isolated call-site tests for existing Phase 8C, without copying collectors.

These tests compile ONLY the exact storage guard AST from the real pinned daily
module, providing fake shared gateway modules to test delegation and fail-closed
behavior before the separate P0 common package is integrated.
"""
from __future__ import annotations
import ast
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock,patch

DAILY=Path(__file__).resolve().parents[2]/"research"/"nba_phase8c"/"daily.py"

def original_guard():
    tree=ast.parse(DAILY.read_text())
    node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and
              x.name=="ensure_authoritative_storage")
    ns={"Path":Path}
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(DAILY),"exec"),ns)
    return ns["ensure_authoritative_storage"],ast.unparse(node)

def mocked_gateway(fn):
    storage=types.ModuleType("v2.p0_integrity.storage")
    storage.attest_project_storage=fn
    contracts=types.ModuleType("v2.p0_integrity.contracts")
    contracts.AdmissionError=type("AdmissionError",(ValueError,),{})
    package=types.ModuleType("v2.p0_integrity")
    package.__path__=[]
    return patch.dict(sys.modules,{
        "v2.p0_integrity":package,
        "v2.p0_integrity.storage":storage,
        "v2.p0_integrity.contracts":contracts})

class ExistingRunnerStorageBridgeTests(unittest.TestCase):
    def test_canonical_project_alias_accepted_after_verified_gateway(self):
        guard,text=original_guard()
        self.assertNotIn("NBA_PILOT_DURABLE_STORAGE_ATTESTED",text)
        mocked=MagicMock(return_value={"verified_path":"/datasets/_deepnote_work",
                                      "status":"STORAGE_ATTESTED_FOR_PROJECT_PATH"})
        with mocked_gateway(mocked):
            value=guard("/work")
        self.assertEqual(value,Path("/datasets/_deepnote_work"))
        mocked.assert_called_once_with("/work")

    def test_unverified_mount_is_rejected_even_with_old_flag_set(self):
        guard,_=original_guard()
        denied=MagicMock(side_effect=ValueError("NO_CROSS_RUN_PROOF"))
        with patch.dict(os.environ,{"NBA_PILOT_DURABLE_STORAGE_ATTESTED":"1"}):
            with mocked_gateway(denied):
                with self.assertRaisesRegex(ValueError,"DURABLE_STORAGE_NOT_ATTESTED"):
                    guard("/work")
        denied.assert_called_once_with("/work")

    def test_tmp_is_never_accepted_on_argument_alone(self):
        guard,_=original_guard()
        denied=MagicMock(side_effect=ValueError("UNAPPROVED_LOGICAL_ROOT"))
        with mocked_gateway(denied):
            with self.assertRaisesRegex(ValueError,"DURABLE_STORAGE_NOT_ATTESTED"):
                guard("/tmp")
        denied.assert_called_once_with("/tmp")

    def test_absent_shared_package_blocks_instead_of_relaxing(self):
        guard,_=original_guard()
        with patch.dict(sys.modules,{"v2.p0_integrity":None,
                                     "v2.p0_integrity.storage":None,
                                     "v2.p0_integrity.contracts":None}):
            with self.assertRaisesRegex(ValueError,"COMMON_STORAGE_ATTESTATION_MODULE_MISSING"):
                guard("/work")

if __name__=="__main__":
    unittest.main()
