#!/usr/bin/env python3
"""Pinned output-only repair for future runs using the frozen PyMC model.

Never changes model graph, priors, seeds, sampler arguments, training data,
cutoff, or strict acceptance thresholds. Fails closed for source drift.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

SCHEMA = "precision_posterior_safety_overlay_v1"
FROZEN_CODE_SHA = "bca3c5f1198009d5254a8dbe81aa73fc75c34e9d"
FROZEN_BLOB_SHA = "3923d0557795a0596f98daa995d6b0500cb7e610"

OLD_FLATTEN = '''        if getattr(group,"data_vars",None):
            values.extend(np.asarray(group.to_array(),dtype=float).ravel().tolist())'''
NEW_FLATTEN = '''        if getattr(group,"data_vars",None):
            # Never broadcast independently shaped diagnostics via Dataset.to_array().
            for variable in group.data_vars.values():
                values.extend(np.asarray(variable,dtype=float).ravel().tolist())'''

OLD_SAVE = '''    checks=diagnostics(posterior,all_effects=a.strict_all_effects)
    a.out.mkdir(parents=True,exist_ok=True)
    posterior.to_netcdf(a.out/"posterior.nc")'''
NEW_SAVE = '''    # Save the entire NUTS posterior BEFORE diagnostics. Each GitHub run has
    # its own output directory: never overwrite an earlier run or partial.
    a.out.mkdir(parents=True,exist_ok=True)
    import hashlib as _hashlib
    import json as _json
    import os as _os
    from datetime import datetime as _datetime, timezone as _timezone
    destination=a.out/"posterior.nc"
    pending=a.out/"posterior.pending.nc"
    if destination.exists() or pending.exists():
        raise ValueError("posterior_checkpoint_already_exists_choose_new_run_directory")
    posterior.to_netcdf(pending)
    if not pending.is_file() or pending.stat().st_size<1024:
        raise ValueError("empty_or_missing_posterior_checkpoint")
    _os.replace(pending,destination)
    _hash=_hashlib.sha256()
    with destination.open("rb") as _saved:
        for _piece in iter(lambda:_saved.read(1024*1024), b""):
            _hash.update(_piece)
    _checkpoint={
        "schema":"precision_posterior_checkpoint_v1",
        "status":"saved_before_diagnostics",
        "file":"posterior.nc",
        "bytes":destination.stat().st_size,
        "sha256":_hash.hexdigest(),
        "chains":a.chains,
        "draws_per_chain":a.draws,
        "tune_per_chain":a.tune,
        "diagnostics_complete":False,
        "created_utc":_datetime.now(_timezone.utc).isoformat(),
    }
    _receipt=a.out/"posterior_checkpoint.json"
    _temp_receipt=a.out/"posterior_checkpoint.pending.json"
    _temp_receipt.write_text(_json.dumps(_checkpoint,sort_keys=True,indent=2),encoding="utf-8")
    _os.replace(_temp_receipt,_receipt)
    print("NUTS_POSTERIOR_CHECKPOINT "+_json.dumps({
        "bytes":_checkpoint["bytes"],"sha256":_checkpoint["sha256"],
        "chains":a.chains,"draws_per_chain":a.draws,
        "saved_before_diagnostics":True},sort_keys=True),flush=True)
    checks=diagnostics(posterior,all_effects=a.strict_all_effects)
    _checkpoint["diagnostics_complete"]=True
    _checkpoint["diagnostic_status"]=checks.get("status")
    _temp_receipt.write_text(_json.dumps(_checkpoint,sort_keys=True,indent=2),encoding="utf-8")
    _os.replace(_temp_receipt,_receipt)'''


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()


def apply_patch(source: str) -> str:
    for snippet in (OLD_FLATTEN,OLD_SAVE):
        if source.count(snippet)!=1:
            raise ValueError("unexpected_frozen_code_patch_anchor")
    result=source.replace(OLD_FLATTEN,NEW_FLATTEN).replace(OLD_SAVE,NEW_SAVE)
    if "nuts={\"target_accept\":.99}" not in result:
        raise ValueError("frozen_sampler_settings_missing")
    if "MAX_RHAT" not in result or "MIN_ESS" not in result or "strict_all_effects" not in result:
        raise ValueError("frozen_diagnostics_contract_missing")
    if result.index("posterior.to_netcdf(pending)") >= result.index(
            "checks=diagnostics(posterior,all_effects=a.strict_all_effects)"):
        raise ValueError("posterior_saved_after_diagnostics")
    if "np.asarray(group.to_array()" in result:
        raise ValueError("broadcasting_diagnostic_still_present")
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--receipt",type=Path,required=True)
    parser.add_argument("--expected-code-sha",required=True)
    args=parser.parse_args(argv)
    if args.expected_code_sha!=FROZEN_CODE_SHA:
        raise ValueError("unrecognized_frozen_training_commit")
    original=args.source.read_bytes()
    if blob_sha(original)!=FROZEN_BLOB_SHA:
        raise ValueError("unrecognized_frozen_model_script_blob")
    patched=apply_patch(original.decode("utf-8"))
    data=patched.encode("utf-8")
    # Atomic replacement of only this pinned output/diagnostics source file.
    temp=args.source.with_suffix(".safety.pending")
    if temp.exists():raise ValueError("prior_safety_patch_pending_file")
    try:
        temp.write_bytes(data)
        os.replace(temp,args.source)
    finally:
        temp.unlink(missing_ok=True)
    assert blob_sha(args.source.read_bytes())==blob_sha(data)
    result={"schema":SCHEMA,"model_commit":FROZEN_CODE_SHA,
            "original_blob_sha":FROZEN_BLOB_SHA,"patched_blob_sha":blob_sha(data),
            "updated_sections":["diagnostic_variable_flattening","posterior_checkpoint_before_diagnostics"],
            "changes_sampling_priors_data_seed_or_acceptance_thresholds":False,
            "restarts_completed_samples":False,
            "restart_requires_fresh_nuts":True}
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(result,sort_keys=True,indent=2),encoding="utf-8")
    print("POSTERIOR_SAFETY_PATCH "+json.dumps(result,sort_keys=True),flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
