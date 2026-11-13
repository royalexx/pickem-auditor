"""Research-only NHL SOG prospective runner with append-only attempt ledger.

Every CLI invocation records an attempt or source abstention. Does not read
production rankings, write old prediction archives or change any schedule.
CLI uses real UTC clock; no input-controlled or retrospectively provided time.
"""
from __future__ import annotations

from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

from .nhl_sog_exposure_shadow import (ExperimentBlocked,fit_model,forecast_for_approved_quote,
    forecast_lines,stable_hash,_canonical,_utc)
from .nhl_sog_official_history_producer import independent_verify_observation_lineage
from .contracts import MarketQuote,ContractError
from .phase15_nhl_roster import RosterEvidenceError


def _append_addressed(root,namespace,obj):
    body=_canonical(obj)
    digest=hashlib.sha256(body).hexdigest()
    path=Path(root).resolve()/namespace/(digest+".json")
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open("xb") as f:f.write(body)
    except FileExistsError:pass
    if path.read_bytes()!=body:
        raise ExperimentBlocked("CONTENT_ADDRESSED_ARTIFACT_CHANGED")
    return {"sha256":digest,"path":str(path)}


def prospective_shadow_attempt(bundle,*,source_root,output_root):
    """One actual-time attempt; unsupported source evidence => archived abstain."""
    now=datetime.now(timezone.utc)
    observed=now.isoformat().replace("+00:00","Z")
    record={
      "schema":"v25_sog_prospective_attempt_v1",
      "experiment_id":"EXP-V25-NHL-SOG-EXPOSURE-EB-001",
      "attempted_at":observed,"tier_publication_allowed":False,
      "production_selection_allowed":False,
      "outcome_used":False,"source_semantics":"collector_possession_not_upstream_publication",
      "event_id":None,"contract_id":None,
      "status":"ABSTAIN","reason":None
    }
    try:
        if not isinstance(bundle,dict) or bundle.get("schema")!="v25_sog_prospective_input_v1":
            raise ExperimentBlocked("PROSPECTIVE_INPUT_MANIFEST_MISSING")
        raw_quote=bundle.get("quote")
        if not isinstance(raw_quote,dict):
            raise ExperimentBlocked("RAW_REAL_OFFER_RECEIPT_MISSING")
        record["event_id"]=raw_quote.get("event_id")
        record["contract_id"]=raw_quote.get("contract_id")
        quote=MarketQuote(**raw_quote)
        if (not quote.accepted or quote.quote_kind!="real" or
                quote.stat_key!="shots on goal" or quote.sport!="NHL"):
            raise ExperimentBlocked("AUTHENTIC_REAL_NHL_SOG_OFFER_REQUIRED")
        if not _utc(observed,"observed_at")<_utc(quote.event_start_at,"event_start_at"):
            raise ExperimentBlocked("LIVE_EVENT_ALREADY_STARTED")
        root=Path(source_root).resolve()
        quote_file=quote.quote_archive_path
        if not quote_file:
            raise ExperimentBlocked("ORIGINAL_REAL_QUOTE_ARCHIVE_NOT_DECLARED")
        if (quote_file.startswith("/") or ".." in Path(quote_file).parts or
                "\\" in quote_file or not (root/quote_file).is_file()):
            raise ExperimentBlocked("ORIGINAL_REAL_QUOTE_ARCHIVE_UNAVAILABLE")
        if hashlib.sha256((root/quote_file).read_bytes()).hexdigest()!=quote.quote_receipt_sha256:
            raise ExperimentBlocked("ORIGINAL_REAL_QUOTE_ARCHIVE_HASH_MISMATCH")
        rosters=bundle.get("official_roster_receipts")
        if not isinstance(rosters,dict) or not (
                quote.team_id in rosters and quote.opponent_id in rosters):
            raise ExperimentBlocked("CURRENT_OFFICIAL_TWO_TEAM_ROSTER_MISSING")
        own=bundle.get("own_official_history")
        peers=bundle.get("peer_official_history")
        if not isinstance(own,list) or not own:
            raise ExperimentBlocked("AUTHENTIC_OWN_NHL_SOG_TOI_HISTORY_MISSING")
        if not isinstance(peers,list) or not peers:
            raise ExperimentBlocked("AUTHENTIC_PEER_NHL_SOG_TOI_HISTORY_MISSING")
        # Independent, newly executed raw signed-origin verification is
        # mandatory; the derived observation SHA alone proves nothing.
        own_verified=[independent_verify_observation_lineage(x,
                archive_root=root,freeze=observed,event_start=quote.event_start_at)
                for x in own]
        peer_verified=[independent_verify_observation_lineage(x,
                archive_root=root,freeze=observed,event_start=quote.event_start_at)
                for x in peers]
        position=bundle.get("official_position_group")
        model=fit_model(own_verified,peer_verified,archive_root=root,
                  player_id=quote.player_id,position_group=position,
                  target_event_id=quote.event_id,current_team_id=quote.team_id,
                  input_freeze_at=observed,event_start_at=quote.event_start_at)
        model["original_signed_history_derived_sha256"]=stable_hash({
            "own":[x["raw_log_receipt"]["collector_proof_sha256"] for x in own],
            "peer":[x["raw_log_receipt"]["collector_proof_sha256"] for x in peers],
            "own_final":[x["raw_final_receipt"]["collector_proof_sha256"] for x in own],
            "peer_final":[x["raw_final_receipt"]["collector_proof_sha256"] for x in peers]})
        model["verified_original_source_lineage"]=True
        code_commit=bundle.get("code_commit")
        if (not isinstance(code_commit,str) or len(code_commit)!=40 or
                any(c not in "0123456789abcdef" for c in code_commit)):
            raise ExperimentBlocked("ACTUAL_CODE_COMMIT_SHA_NOT_PROVIDED")
        model_ref=_append_addressed(output_root,"models",model)
        later=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
        snapshot=forecast_for_approved_quote(model,quote,source_root=root,
                roster_root=root,roster_receipts=rosters,
                code_commit=code_commit,run_id=bundle.get("run_id") or "",
                forecast_id=bundle.get("forecast_id") or "",
                forecast_at=later,decision_cutoff_at=observed)
        snapshot_ref=_append_addressed(output_root,"snapshots",snapshot)
        probs=forecast_lines(model,[quote.line])[format(float(quote.line),"g")]
        record.update(status="SHADOW_FORECAST",reason=None,
                      model_artifact=model_ref,snapshot_artifact=snapshot_ref,
                      source_manifest_digest=stable_hash(model["source_manifest"]),
                      quote_id=quote.quote_id,three_way_probabilities=probs,
                      baseline_three_way=forecast_lines(model,[quote.line],kind="plugin_poisson")[
                          format(float(quote.line),"g")],
                      never_authorized_to_publish=True)
    except (ExperimentBlocked,ContractError,RosterEvidenceError,ValueError,TypeError,
            OSError,KeyError,ImportError) as exc:
        record["status"]="ABSTAIN"
        record["reason"]=type(exc).__name__+":"+str(exc)[:250]
    result=_append_addressed(output_root,"attempts",record)
    return {"attempt_receipt":result,"attempt":record}


if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--source-root",required=True)
    p.add_argument("--output-root",required=True)
    a=p.parse_args()
    try:manifest=json.loads(Path(a.input).read_bytes())
    except (OSError,ValueError):manifest={}
    print(json.dumps(prospective_shadow_attempt(manifest,source_root=a.source_root,
         output_root=a.output_root),sort_keys=True,indent=2))
