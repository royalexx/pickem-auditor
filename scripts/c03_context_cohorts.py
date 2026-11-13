"""C03 v2 context cohort/lineage integrity; experimental opt-in only.

An archived candidate is NOT evidence that upstream availability was published
before the game. Receipts bind raw response BODY bytes, exact claim pointers,
collector possession clocks and event/player identity. This independent module
does not modify legacy engines or authorize publication.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA_RECEIPT="availability_source_receipt_v2"
SCHEMA_CLAIM="availability_claim_v2"
SCHEMA_COHORT="pickem_context_cohort_v2"
SCHEMA_NEUTRAL="neutral_input_transform_v1"
SCHEMA_BINDING="pickem_pre_eval_input_binding_v2"

KNOWN_STATUS={"active","out","questionable","doubtful"}
RESEARCH_OWNED={
    "hard_veto","data_veto","role_change","availability_issue",
    "weather_issue","role_window_issue","identity_issue",
    "spread","total","team_is_underdog","is_starter","role",
    "outdoor","sustained_wind_mph","gust_mph","precip_prob",
    "precip_intensity","back_to_back","third_in_four",
    "goalie_confirmed","expected_starting_qb","snow",
    # Every numeric pregame role/workload context field must be neutralized.
    "minutes_tonight","ice_time_tonight",
    "snap_pct_tonight","route_pct_tonight",
}
ALLOWED_KINDS={"subject_status","teammate_status","roster_membership",
               "named_nfl_starting_qb","named_nhl_starting_goalie",
               "verified_player_position"}
COHORT_A="A"
COHORT_B="B"
COHORT_C="C"
COHORT_D="D"


class CohortError(ValueError):
    pass


def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),
                      allow_nan=False,ensure_ascii=False).encode("utf-8")


def neutral_digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _utc(value,name):
    if not isinstance(value,str) or "T" not in value:
        raise CohortError("TIMESTAMP_MISSING:"+name)
    try:dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    except (TypeError,ValueError,OverflowError) as e:
        raise CohortError("TIMESTAMP_INVALID:"+name) from e
    if dt.tzinfo is None:
        raise CohortError("TIMESTAMP_NAIVE:"+name)
    return dt.astimezone(timezone.utc)


def _safe_archive(root,rel):
    if not isinstance(rel,str) or not rel or rel.startswith("/") or (
            "\\" in rel or ".." in Path(rel).parts):
        raise CohortError("SOURCE_PATH_UNSAFE")
    base=Path(root).resolve()
    path=(base/rel).resolve()
    if not path.is_relative_to(base):
        raise CohortError("SOURCE_PATH_UNSAFE")
    return path


def _url(raw):
    uri=urlsplit(raw)
    if uri.scheme!="https" or not uri.hostname or uri.username or uri.password:
        raise CohortError("SOURCE_URL_UNTRUSTED")
    return uri._replace(query="",fragment="").geturl()


def archive_response(raw,*,archive_root,source_url,observed_at,received_at,
                     source_id,source_namespace,http_status):
    """Capture original HTTP response *body* bytes, not reserialized parsed data.

    Production transport must call at network receipt time, using a trusted
    clock. Supplied timestamps alone cannot authenticate historical possession.
    The returned metadata therefore NEVER proves the provider publication time.
    """
    if not isinstance(raw,bytes) or not raw or len(raw)>32_000_000:
        raise CohortError("RAW_RESPONSE_BYTES_REQUIRED")
    observed=_utc(observed_at,"observed_at")
    received=_utc(received_at,"received_at")
    if observed>received:
        raise CohortError("SOURCE_CLOCK_ORDER_INVALID")
    if type(http_status) is not int or http_status!=200:
        raise CohortError("SOURCE_HTTP_NOT_OK")
    if not isinstance(source_id,str) or not source_id or not isinstance(source_namespace,str) or not source_namespace:
        raise CohortError("SOURCE_ID_MISSING")
    digest=hashlib.sha256(raw).hexdigest()
    rel="raw_http_body/"+digest+".bin"
    path=_safe_archive(archive_root,rel)
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open("xb") as f:f.write(raw)
    except FileExistsError:pass
    if path.read_bytes()!=raw:
        raise CohortError("RAW_ARCHIVE_MUTATED")
    return {
        "schema":SCHEMA_RECEIPT,"source_id":source_id,
        "source_namespace":source_namespace,
        "source_kind":"raw_http_response_body",
        "body_bytes":len(raw),"body_sha256":digest,
        "archive_path":rel,"source_url":_url(source_url),
        "observed_at":observed_at,"received_at":received_at,
        "http_status":http_status,
        "clock_semantics":"collector_possession_only_no_upstream_publication_claim",
        "source_publication_truth_verified":False,
        "transport_attestation":"unverified_until_independent_live_capture",
    }


def verify_receipt(receipt,*,archive_root,freeze,event_start):
    if not isinstance(receipt,dict) or receipt.get("schema")!=SCHEMA_RECEIPT:
        raise CohortError("SOURCE_RECEIPT_SCHEMA_MISSING")
    if receipt.get("source_kind")!="raw_http_response_body" or (
            receipt.get("clock_semantics")!="collector_possession_only_no_upstream_publication_claim"):
        raise CohortError("SOURCE_KIND_UNTRUSTED")
    if receipt.get("source_publication_truth_verified") is not False:
        raise CohortError("FALSE_PUBLICATION_CLAIM")
    if receipt.get("http_status")!=200:
        raise CohortError("SOURCE_HTTP_NOT_OK")
    _url(receipt.get("source_url"))
    host=urlsplit(receipt["source_url"]).hostname
    allowed={
        "espn":{"site.api.espn.com"},
        "nhl_official":{"api-web.nhle.com","api.nhle.com"},
        "nfl_official":{"static.www.nfl.com","www.nfl.com"},
    }
    if (receipt.get("source_namespace") not in allowed or
            host not in allowed[receipt["source_namespace"]]):
        raise CohortError("SOURCE_NAMESPACE_HOST_MISMATCH")
    observed=_utc(receipt.get("observed_at"),"observed_at")
    received=_utc(receipt.get("received_at"),"received_at")
    freeze=_utc(freeze,"input_freeze_at")
    start=_utc(event_start,"event_start_at")
    if not observed<=received<=freeze<start:
        raise CohortError("SOURCE_AFTER_CUTOFF")
    path=_safe_archive(archive_root,receipt.get("archive_path"))
    if not path.is_file():
        raise CohortError("SOURCE_ARCHIVE_MISSING")
    raw=path.read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    if (digest!=receipt.get("body_sha256") or
            len(raw)!=receipt.get("body_bytes")):
        raise CohortError("SOURCE_DIGEST_MISMATCH")
    if not isinstance(receipt.get("source_id"),str) or not receipt["source_id"]:
        raise CohortError("SOURCE_ID_MISSING")
    try:doc=json.loads(raw)
    except (ValueError,UnicodeDecodeError) as e:
        raise CohortError("SOURCE_BODY_NOT_JSON") from e
    if not isinstance(doc,(dict,list)):
        raise CohortError("SOURCE_BODY_NOT_OBJECT")
    return doc


def _pointer(doc,pointer):
    if not isinstance(pointer,str) or not pointer.startswith("/"):
        raise CohortError("CLAIM_POINTER_MISSING")
    v=doc
    for part in pointer[1:].split("/"):
        key=part.replace("~1","/").replace("~0","~")
        if isinstance(v,dict) and key in v:
            v=v[key]
        elif isinstance(v,list) and key.isdigit() and int(key)<len(v):
            v=v[int(key)]
        else:
            raise CohortError("CLAIM_PATH_NOT_FOUND")
    return v


def verify_claim(claim,receipts,*,archive_root,freeze,event_start,
                 expected_event,expected_team):
    if not isinstance(claim,dict) or claim.get("schema")!=SCHEMA_CLAIM:
        raise CohortError("CLAIM_SCHEMA_INVALID")
    if claim.get("kind") not in ALLOWED_KINDS:
        raise CohortError("CLAIM_KIND_INVALID")
    receipt=receipts.get(claim.get("source_id"))
    if receipt is None:
        raise CohortError("SOURCE_RECEIPT_MISSING")
    doc=verify_receipt(receipt,archive_root=archive_root,
                       freeze=freeze,event_start=event_start)
    for field in ("event_id","team_id","player_id"):
        expected=claim.get(field)
        if not isinstance(expected,str) or not expected:
            raise CohortError("CLAIM_IDENTITY_MISSING:"+field)
        if str(_pointer(doc,claim.get(field+"_path")))!=expected:
            raise CohortError("SOURCE_IDENTITY_MISMATCH")
    if claim["event_id"]!=expected_event or claim["team_id"]!=expected_team:
        raise CohortError("SOURCE_IDENTITY_MISMATCH")
    observed=_pointer(doc,claim.get("value_path"))
    value=claim.get("value")
    if type(value) is not type(observed) or value!=observed:
        raise CohortError("SOURCE_CLAIM_VALUE_MISMATCH")
    if not isinstance(value,str):
        raise CohortError("STATUS_VALUE_NOT_LITERAL")
    status=value.lower().strip()
    if claim["kind"] in ("subject_status","teammate_status"):
        if status not in KNOWN_STATUS:
            raise CohortError("UNRECOGNIZED_STATUS")
    elif claim["kind"]=="verified_player_position":
        if status not in ("qb","rb","wr","te","fb","unknown"):
            raise CohortError("UNRECOGNIZED_NFL_POSITION_CLAIM")
    elif status not in ("starter","member"):
        raise CohortError("UNRECOGNIZED_LINEUP_CLAIM")
    return {**claim,"status":status}


def neutralize(candidate):
    """Restore collector-owned pre-research values, never allow context uplifts.

    The pre-merge fields are captured by research_packet.merge_into_pipeline.
    Derived research numeric fields not in this premerge original are removed.
    """
    if not isinstance(candidate,dict):
        raise CohortError("CANDIDATE_INVALID")
    original=deepcopy(candidate)
    base=original.get("research_merge_base")
    context=original.get("event_context")
    if context and not isinstance(base,dict):
        raise CohortError("PREMERGE_NUMERIC_ORIGIN_MISSING")
    if base is not None and (not isinstance(base,dict) or set(base)-RESEARCH_OWNED):
        raise CohortError("RESEARCH_MERGE_BASE_INVALID")
    soft=original.get("soft_flags",0)
    research_soft=original.get("research_soft_flags",0)
    if (type(soft) is not int or type(research_soft) is not int or
            research_soft<0 or soft<research_soft):
        raise CohortError("RESEARCH_SOFT_FLAG_ORIGIN_INVALID")
    for key in RESEARCH_OWNED:
        original.pop(key,None)
    if base:
        original.update(deepcopy(base))
    original.pop("research_merge_base",None)
    original.pop("research_soft_flags",None)
    original.pop("event_context",None)
    original.pop("research_merge_status",None)
    original.pop("mechanism_quality",None)
    original["soft_flags"]=soft-research_soft
    original["mechanisms"]=0
    original["research_checklist"]=False
    scouting=original.get("scouting")
    if scouting is not None:
        if not isinstance(scouting,dict) or not isinstance(scouting.get("historical_usage"),str):
            raise CohortError("HISTORICAL_SCOUTING_ORIGIN_MISSING")
        original["scouting"]={"historical_usage":scouting["historical_usage"]}
    return original


def _decision(code,reason,original,neutral=None,claims=None,receipts=None,
              freeze=None,event_start=None):
    if code=="D":
        return {"cohort":code,"reason":reason,"status":"ABSTAIN_UNCERTIFIED",
                "neutral_candidate":None,"binding":None,"publication_allowed":False}
    bind={"schema":SCHEMA_COHORT,
          "binding_schema":SCHEMA_BINDING,
          "neutral_transform_schema":SCHEMA_NEUTRAL,
          "cohort":code,"reason":reason,
          "original_candidate_sha256":neutral_digest(original),
          "neutral_candidate_sha256":neutral_digest(neutral),
          "event_id":str(original.get("event_id") or ""),
          "player_id":str(original.get("player_id") or ""),
          "team_id":str(original.get("team") or ""),
          "input_freeze_at":freeze,"event_start_at":event_start,
          "claims":deepcopy(claims or []),
          "source_receipts":deepcopy(receipts or []),
          "scope":"baseline_numeric_conditional_on_played",
          "availability_source_truth":"collector_possession_only",
          "not_a_context_adjusted_forecast":True,
          "context_exposure_probability_estimated":False,
          "publication_allowed":False}
    return {"cohort":code,"reason":reason,
            "status":("source_input_certifiable_not_Tier_eligible" if code=="A"
                      else "context_receipt_checked_shadow_needs_transport_signoff"),
            "neutral_candidate":neutral,"binding":bind,"publication_allowed":False}


def classify(candidate,*,source_receipts,claims,archive_root,
             input_freeze_at,event_start_at):
    """Classify all attempted pregame subjects; D is explicit, not dropped."""
    try:
        freeze=_utc(input_freeze_at,"input_freeze_at")
        start=_utc(event_start_at,"event_start_at")
        if not freeze<start:
            raise CohortError("FORECAST_NOT_PREGAME")
        if not isinstance(candidate,dict) or not str(candidate.get("event_id") or "") or (
                not str(candidate.get("player_id") or "")):
            raise CohortError("CANDIDATE_IDENTITY_MISSING")
        neutral=neutralize(candidate)
        if not isinstance(source_receipts,list) or not isinstance(claims,list):
            raise CohortError("SOURCE_RECEIPT_MISSING")
        if not isinstance(candidate.get("event_context",{}),dict):
            raise CohortError("EVENT_CONTEXT_INVALID")
        receipt_map={}
        for r in source_receipts:
            sid=r.get("source_id") if isinstance(r,dict) else None
            if not sid or sid in receipt_map:
                raise CohortError("DUPLICATE_OR_MISSING_SOURCE_ID")
            receipt_map[sid]=r
        verified=[]
        for claim in claims:
            verified.append(verify_claim(claim,receipt_map,archive_root=archive_root,
                freeze=input_freeze_at,event_start=event_start_at,
                expected_event=str(candidate["event_id"]),expected_team=str(candidate["team"])))
        pid=str(candidate["player_id"])
        statuses=[v["status"] for v in verified
                  if v["kind"]=="subject_status" and v["player_id"]==pid]
        if len(set(statuses))>1:
            raise CohortError("AVAILABILITY_CONFLICT")
        declared_subject=candidate.get("event_context",{}).get("subject_status")
        if declared_subject is not None:
            declared=(declared_subject.get("value") if isinstance(declared_subject,dict)
                      else declared_subject)
            if not isinstance(declared,str) or (
                    statuses and declared.lower().strip()!=statuses[0]):
                raise CohortError("SUBJECT_SOURCE_STATUS_MISMATCH")
        if statuses and statuses[0]=="out":
            raise CohortError("PLAYER_OUT")
        if statuses and statuses[0] in ("questionable","doubtful"):
            raise CohortError("STATUS_UNCERTAIN")
        teammate_out={v["player_id"] for v in verified
                      if v["kind"]=="teammate_status" and v["status"]=="out" and v["player_id"]!=pid}
        requested={str(ev.get("player_id")) for ev in
                   candidate.get("event_context",{}).get("events",[])
                   if isinstance(ev,dict)}
        if not requested<=teammate_out:
            raise CohortError("SOURCE_RECEIPT_MISSING")
        if candidate.get("event_context",{}).get("subject_status") and not statuses:
            raise CohortError("SOURCE_RECEIPT_MISSING")
        if candidate.get("event_context") and not (statuses or teammate_out):
            raise CohortError("SOURCE_RECEIPT_MISSING")
        skater=claim_set(verified,pid,"roster_membership","member")
        if candidate.get("sport")=="NHL" and not skater:
            raise CohortError("NHL_ROSTER_IDENTITY_UNVERIFIED")
        if candidate.get("sport")=="NHL" and candidate.get("stat") in ("goalie saves","saves"):
            if not claim_set(verified,pid,"named_nhl_starting_goalie","starter"):
                raise CohortError("NHL_STARTING_GOALIE_UNVERIFIED")
        if candidate.get("sport")=="NFL":
            stat=str(candidate.get("stat") or "")
            pass_markets={"pass attempts","passing yards","completions"}
            qb_rushing_markets={"rushing yards","rush attempts","rushing attempts"}
            positions={v["status"] for v in verified if (
                v["kind"]=="verified_player_position" and v["player_id"]==pid)}
            if len(positions)>1:
                raise CohortError("NFL_POSITION_CONFLICT")
            position=next(iter(positions),None)
            if stat in qb_rushing_markets and position is None:
                raise CohortError("NFL_RUSHER_POSITION_UNVERIFIED")
            if stat in pass_markets and position not in (None,"qb"):
                raise CohortError("NFL_PASSER_POSITION_CONFLICT")
            if (stat in pass_markets or
                    stat in qb_rushing_markets and position=="qb"):
                if not claim_set(verified,pid,"named_nfl_starting_qb","starter"):
                    raise CohortError("STARTING_QB_UNVERIFIED")
        label=COHORT_B if (statuses or teammate_out or verified) else COHORT_A
        return _decision(label,"CERTIFIED_INPUT_CONTEXT_NEUTRAL" if label=="B" else
                         "NO_CONTEXT_DEPENDENCY",candidate,neutral,claims,source_receipts,
                         input_freeze_at,event_start_at)
    except (CohortError,KeyError,TypeError,ValueError) as exc:
        return _decision(COHORT_D,str(exc),candidate)


def claim_set(claims,player_id,kind,status):
    return any(c["kind"]==kind and c["player_id"]==player_id and c["status"]==status
               for c in claims)


def verify_context_binding(binding,*,archive_root,original_candidate,neutral_candidate,
                           input_freeze_at,event_start_at):
    if not isinstance(binding,dict) or binding.get("schema")!=SCHEMA_COHORT:
        return False,"C03_BINDING_MISSING"
    if (binding.get("input_freeze_at")!=input_freeze_at or
            binding.get("event_start_at")!=event_start_at or
            binding.get("original_candidate_sha256")!=neutral_digest(original_candidate) or
            binding.get("neutral_candidate_sha256")!=neutral_digest(neutral_candidate)):
        return False,"C03_CANDIDATE_DIGEST_MISMATCH"
    verified=classify(original_candidate,source_receipts=binding.get("source_receipts"),
               claims=binding.get("claims"),archive_root=archive_root,
               input_freeze_at=input_freeze_at,event_start_at=event_start_at)
    if verified["cohort"]!=binding.get("cohort") or verified["cohort"]=="D":
        return False,"C03_COHORT_OR_SOURCE_INVALID:"+str(verified["reason"])
    if neutral_digest(verified["neutral_candidate"])!=neutral_digest(neutral_candidate):
        return False,"C03_NEUTRAL_TRANSFORM_MISMATCH"
    return True,"C03_CONTEXT_SOURCE_AND_NEUTRAL_BINDING_OK"


def register_research_adjustment(baseline,artifact,*,archive_root):
    """C separate non-promotable only if an immutable trained artifact exists."""
    if baseline.get("cohort") not in ("A","B") or not isinstance(artifact,dict):
        raise CohortError("ADJUSTMENT_BASELINE_INVALID")
    rel=artifact.get("artifact_path")
    digest=artifact.get("artifact_sha256")
    if not isinstance(digest,str) or len(digest)!=64:
        raise CohortError("ADJUSTMENT_ARTIFACT_MISSING")
    path=_safe_archive(archive_root,rel)
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
        raise CohortError("ADJUSTMENT_ARTIFACT_INTEGRITY_FAILURE")
    if not artifact.get("model_training_cutoff_at") or not artifact.get("code_commit"):
        raise CohortError("ADJUSTMENT_FIT_PROVENANCE_MISSING")
    cutoff=_utc(artifact["model_training_cutoff_at"],"adjustment_training_cutoff")
    freeze=_utc(baseline["binding"]["input_freeze_at"],"baseline_freeze")
    if cutoff>freeze or (not isinstance(artifact["code_commit"],str)
                        or len(artifact["code_commit"])!=40
                        or any(c not in "0123456789abcdef" for c in artifact["code_commit"])):
        raise CohortError("ADJUSTMENT_TRAINED_AFTER_FREEZE_OR_CODE_UNVERIFIED")
    manifest=artifact.get("training_manifest")
    if not isinstance(manifest,dict) or not isinstance(manifest.get("sha256"),str):
        raise CohortError("ADJUSTMENT_TRAINING_MANIFEST_MISSING")
    manifest_file=_safe_archive(archive_root,manifest.get("archive_path"))
    if (not manifest_file.is_file() or
            hashlib.sha256(manifest_file.read_bytes()).hexdigest()!=manifest["sha256"]):
        raise CohortError("ADJUSTMENT_TRAINING_MANIFEST_INVALID")
    return {"schema":SCHEMA_COHORT,"cohort":"C",
            "status":"VERIFIED_INPUT_CONTEXT_RESEARCH_SHADOW_ONLY",
            "artifact_sha256":digest,"source_baseline":baseline["binding"],
            "certified_for_publication":False,"tier_publication_allowed":False}


def archive_original_candidate(candidate,archive_root,*,possessed_at=None):
    """Freeze BOTH original and neutral inputs; never overwrite old captures."""
    if possessed_at is not None:
        _utc(possessed_at,"original_candidate_possessed_at")
    body=canonical(candidate)
    digest=hashlib.sha256(body).hexdigest()
    rel="c03_original_candidate/"+digest+".json"
    path=_safe_archive(archive_root,rel)
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open("xb") as f:f.write(body)
    except FileExistsError:pass
    if path.read_bytes()!=body:
        raise CohortError("C03_ORIGINAL_SOURCE_MUTATED")
    return {"archive_path":rel,"content_sha256":digest,"bytes":len(body),
            "collector_possessed_at":possessed_at}


def capture_live_http_body(url,*,archive_root,source_namespace,source_id,timeout=12):
    """Opt-in live transport capture. No retroactive/injected collection clock.

    This helper is not called by the legacy collector and never changes its
    source bytes. Only allowlisted public HTTPS event feeds are accepted.
    """
    from urllib.request import Request,urlopen
    parts=urlsplit(url)
    if parts.scheme!="https" or parts.hostname not in (
         "site.api.espn.com","api-web.nhle.com","api.nhle.com"):
        raise CohortError("LIVE_SOURCE_DOMAIN_NOT_ALLOWED")
    observed=datetime.now(timezone.utc)
    req=Request(url,headers={"Accept":"application/json"})
    try:
        with urlopen(req,timeout=timeout) as response:
            status=response.status
            content_type=response.headers.get("Content-Type","")
            body=response.read(32_000_001)
    except (OSError,ValueError,TimeoutError) as exc:
        raise CohortError("LIVE_SOURCE_FETCH_FAILED:"+type(exc).__name__) from exc
    received=datetime.now(timezone.utc)
    if "json" not in content_type.lower():
        raise CohortError("LIVE_SOURCE_NOT_JSON")
    stamp=lambda x:x.isoformat().replace("+00:00","Z")
    receipt=archive_response(body,archive_root=archive_root,source_url=url,
                             observed_at=stamp(observed),received_at=stamp(received),
                             source_id=source_id,source_namespace=source_namespace,
                             http_status=status)
    receipt["transport_attestation"]="collector_live_transport_verified"
    receipt["transport_capture_id"]=neutral_digest({
         "source_id":source_id,"url":receipt["source_url"],
         "observed_at":receipt["observed_at"],"received_at":receipt["received_at"],
         "body_sha256":receipt["body_sha256"]})
    return receipt


def strict_c03_snapshot_status(row,*,archive_root):
    """V2 fail-closed wrapper around the unchanged, independently checked v1.

    A context-neutral baseline must first pass v1 strict certification on its
    exact evaluated neutral candidate, then prove the original/claim binding.
    """
    from phase0r_contract import strict_snapshot_status
    ok,reason=strict_snapshot_status(row,archive_root=archive_root)
    if not ok:return False,"BASE_V1_"+str(reason)
    ctx=row.get("c03_context_binding")
    if not isinstance(ctx,dict) or ctx.get("schema")!=SCHEMA_COHORT:
        return False,"C03_BINDING_MISSING"
    if ctx.get("cohort") not in ("A","B"):
        return False,"C03_NONBASELINE_COHORT"
    original=row.get("c03_original_candidate")
    neutral=row.get("inputs")
    original_receipt=ctx.get("original_candidate_receipt")
    if not isinstance(original,dict) or not isinstance(original_receipt,dict):
        return False,"C03_ORIGINAL_CANDIDATE_NOT_ARCHIVED"
    try:
        path=_safe_archive(archive_root,original_receipt.get("archive_path"))
        body=path.read_bytes()
        if (body!=canonical(original) or len(body)!=original_receipt.get("bytes") or
                hashlib.sha256(body).hexdigest()!=original_receipt.get("content_sha256")):
            return False,"C03_ORIGINAL_BYTES_MISMATCH"
    except (OSError,ValueError,TypeError,CohortError):
        return False,"C03_ORIGINAL_ARCHIVE_INVALID"
    try:
        archived_at=_utc(original_receipt.get("collector_possessed_at"),
                         "original_candidate_possessed_at")
        freeze=_utc(row.get("input_freeze_at"),"input_freeze_at")
        if archived_at>freeze:
            return False,"C03_ORIGINAL_CAPTURE_AFTER_FREEZE"
    except CohortError:
        return False,"C03_ORIGINAL_CAPTURE_TIME_UNVERIFIED"
    ok,reason=verify_context_binding(ctx,archive_root=archive_root,
                    original_candidate=original,neutral_candidate=neutral,
                    input_freeze_at=row.get("input_freeze_at"),
                    event_start_at=row.get("event_start"))
    if not ok:return False,reason
    if original.get("sport")=="NHL":
        # A generic 'member' string in a research packet is NOT official NHL
        # roster evidence. Revalidate both team rosters against independent
        # NHL-hosted bytes, with goalie/skater identity kept distinct.
        try:
            from v2.phase15_nhl_roster import verify_receipt
            rosters=ctx.get("official_nhl_roster_receipts")
            own_team=str(original.get("team") or "")
            other_team=str(original.get("opponent") or "")
            if not isinstance(rosters,dict) or own_team==other_team:
                return False,"C03_NHL_OFFICIAL_ROSTER_MISSING"
            ours=verify_receipt(rosters[own_team],source_root=archive_root,
                 forecast_at=row.get("input_freeze_at"),
                 event_start=row.get("event_start"))
            theirs=verify_receipt(rosters[other_team],source_root=archive_root,
                 forecast_at=row.get("input_freeze_at"),
                 event_start=row.get("event_start"))
            pid=str(original["player_id"])
            expected="goalie" if original.get("stat") in ("goalie saves","saves") else "skater"
            if pid in theirs or ours.get(pid)!=expected:
                return False,"C03_NHL_OFFICIAL_TEAM_OR_ROLE_MISMATCH"
        except (KeyError,TypeError,ValueError,OSError) as exc:
            return False,"C03_NHL_OFFICIAL_ROSTER_UNVERIFIED:"+type(exc).__name__
    if ctx["cohort"]=="B":
        receipts=ctx.get("source_receipts") or []
        if not receipts or any(r.get("transport_attestation")!="collector_live_transport_verified"
                               or not r.get("transport_capture_id") for r in receipts):
            return False,"C03_LIVE_TRANSPORT_NOT_ATTESTED"
        for r in receipts:
            expected=neutral_digest({
                 "source_id":r.get("source_id"),"url":r.get("source_url"),
                 "observed_at":r.get("observed_at"),"received_at":r.get("received_at"),
                 "body_sha256":r.get("body_sha256")})
            if expected!=r.get("transport_capture_id"):
                return False,"C03_TRANSPORT_ATTESTATION_MISMATCH"
        # Provider publication truth is never inferred from possession.
        if any(r.get("source_publication_truth_verified") is not False for r in receipts):
            return False,"C03_UPSTREAM_PUBLICATION_CLAIM_INVALID"
    return True,"C03_STRICT_SOURCE_NEUTRAL_BASELINE"


def settlement_disposition(*,participated,official_state,actual_stat,line,
                           void_terms_verified,provider_void_on_dnp):
    """Separate played zero and early-exit outcomes from DNP/void policy.

    No default book rules: without a verified market-specific void definition
    neither a missing player nor a postponed event is scorable.
    """
    if official_state not in ("settled","dnp","postponed","void","unverified"):
        raise CohortError("SETTLEMENT_STATE_UNKNOWN")
    if official_state in ("dnp","postponed","void"):
        if not void_terms_verified or provider_void_on_dnp is None:
            return {"status":"UNVERIFIED_VOID_RULE","scoreable":False}
        if official_state=="void" or (official_state=="dnp" and provider_void_on_dnp):
            return {"status":"VOID","scoreable":False}
        return {"status":"NEEDS_OFFICIAL_BOOK_RESOLUTION","scoreable":False}
    if official_state!="settled" or participated is not True:
        return {"status":"UNVERIFIED_SETTLEMENT","scoreable":False}
    if type(actual_stat) not in (int,float) or type(line) not in (int,float):
        raise CohortError("INVALID_SETTLEMENT_VALUE")
    import math
    if not math.isfinite(actual_stat) or not math.isfinite(line):
        raise CohortError("NONFINITE_SETTLEMENT")
    return {"status":("push" if actual_stat==line else
                      "over" if actual_stat>line else "under"),
            "scoreable":True,"actual_stat":actual_stat,
            "participation":"played_includes_zero_or_early_exit"}
