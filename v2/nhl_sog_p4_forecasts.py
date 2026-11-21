"""P4 NHL SOG complete-count research artifact adapter.

No collection, no independent quote fitting, no outcome access. The locked
EXPOSURE-EB Gamma model is always fitted by its original source-verified
implementation. The original native NB2 experiment remains owned by
v2.nhl_sog_nb2_source_native; this module never manufactures admission.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import json
import math
import os
from pathlib import Path

from .nhl_sog_exposure_shadow import (
    ExperimentBlocked, fit_model, _mass, stable_hash, forecast_lines, _utc,
    SCHEMA as GAMMA_SCHEMA, EXPERIMENT as GAMMA_EXPERIMENT,
)
from .nhl_sog_nb2_source_native import (
    EXPERIMENT as NATIVE_EXPERIMENT, SHAPE as NATIVE_SHAPE,
)

SCHEMA = "v25_nhl_sog_p4_full_count_v1"
BUNDLE_SCHEMA = "v25_nhl_sog_p4_p2_source_bundle_v1"
ADAPTIVE_SCHEMA = "v25_nhl_sog_p4_adaptive_gamma_rate_v1"
MAX_COUNT = 4096
TAIL_TOL = 1e-12
MODELS = {
    "poisson_plugin": "plugin_poisson",
    "gamma_fixed_toi": "fixed_exposure_gamma_poisson",
    "poisson_exposure_mixture": "mixture_exposure_plugin_poisson",
    "gamma_exposure_mixture": "full_gamma_poisson_exposure",
}
LOCKED_IDS = {GAMMA_EXPERIMENT, NATIVE_EXPERIMENT}


class P4Blocked(ValueError):
    """A named fail-closed modeling, provenance or persistence condition."""


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def _check(ok, code):
    if not ok:
        raise P4Blocked(code)


def _safe_child(root, rel):
    _check(isinstance(rel, str) and bool(rel) and not rel.startswith("/")
           and "\\\\" not in rel and ".." not in Path(rel).parts,
           "UNSAFE_SOURCE_PATH")
    p = (Path(root).resolve() / rel).resolve()
    _check(p.is_relative_to(Path(root).resolve()), "SOURCE_PATH_ESCAPES_ROOT")
    return p


def verify_manifest(root, path, expected_sha):
    _check(isinstance(expected_sha, str) and len(expected_sha) == 64,
           "ORIGINAL_SOURCE_MANIFEST_SHA_MISSING")
    p = _safe_child(root, path)
    _check(p.is_file(), "ORIGINAL_SOURCE_MANIFEST_MISSING")
    raw = p.read_bytes()
    _check(sha256(raw) == expected_sha, "ORIGINAL_SOURCE_MANIFEST_SHA_MISMATCH")
    try:
        manifest = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise P4Blocked("ORIGINAL_SOURCE_MANIFEST_INVALID") from exc
    return manifest


def _mass_for(model, k, kind):
    if kind == "nb2_fixed_shape4":
        mu = model["plugin_rate"] * model["plugin_exposure"]
        _check(math.isfinite(mu) and mu >= 0, "INVALID_FROZEN_PLUGIN_MEAN")
        if mu == 0:
            return float(k == 0)
        r = NATIVE_SHAPE
        return math.exp(math.lgamma(k+r)-math.lgamma(r)-math.lgamma(k+1)
                        +r*math.log(r/(r+mu))+k*math.log(mu/(r+mu)))
    return _mass(model, k, kind)


def full_law(model, kind, *, tol=TAIL_TOL):
    """Numerically bounded PMF, with the untruncated analytic law retained.

    Tail is NOT renormalized into the enumerated probabilities. P5 must use
    the analytic evaluator for farther tails, and keep the recorded bound.
    """
    _check(model.get("schema") == GAMMA_SCHEMA, "GAMMA_MODEL_SCHEMA_MISMATCH")
    _check(kind in set(MODELS.values()) | {"nb2_fixed_shape4"},
           "UNKNOWN_COUNT_LIKELIHOOD")
    _check(isinstance(tol, (int,float)) and not isinstance(tol,bool)
           and math.isfinite(tol) and 0 < tol <= 1e-8, "INVALID_TAIL_TOLERANCE")
    pmf = []
    for k in range(MAX_COUNT):
        p = _mass_for(model, k, kind)
        _check(math.isfinite(p) and -1e-15 <= p <= 1 + 1e-12,
               "INVALID_COUNT_PROBABILITY")
        pmf.append(max(0.0, p))
        total = math.fsum(pmf)
        _check(total <= 1 + 1e-10, "COUNT_MASS_GREATER_THAN_ONE")
        tail = max(0.0, 1.0 - total)
        if tail <= tol:
            break
    else:
        raise P4Blocked("COUNT_TAIL_NOT_NUMERICALLY_BOUNDED")
    mu = math.fsum(i*p for i,p in enumerate(pmf))
    v = math.fsum(((i-mu)**2)*p for i,p in enumerate(pmf))
    # Exact analytical moments, not moments of a truncated approximation.
    a, b = model["rate_a"], model["rate_b"]
    pi = model["exposure_pmf"]
    r, w0 = model["plugin_rate"], model["plugin_exposure"]
    ew = math.fsum(w*p for w,p in pi)
    ew2 = math.fsum(w*w*p for w,p in pi)
    varw = max(0.0, ew2-ew*ew)
    if kind == "plugin_poisson":
        mean, variance = r*w0, r*w0
    elif kind == "fixed_exposure_gamma_poisson":
        mean = a*w0/b
        variance = mean + a*(w0/b)**2
    elif kind == "mixture_exposure_plugin_poisson":
        mean = r*ew
        variance = mean + r*r*varw
    elif kind == "full_gamma_poisson_exposure":
        mean = a*ew/b
        variance = mean + (a/b)**2*varw + a*ew2/(b*b)
    else:
        mean = r*w0
        variance = mean + mean*mean/NATIVE_SHAPE
    _check(all(math.isfinite(x) and x >= 0 for x in (mean, variance)),
           "INVALID_DISTRIBUTION_MOMENTS")
    quantiles = {}
    for q in (0.05, 0.5, 0.9, 0.95, 0.99):
        cum = 0.0
        for k,p in enumerate(pmf):
            cum += p
            if cum >= q:
                quantiles[str(q)] = k
                break
        _check(str(q) in quantiles, "QUANTILE_OUTSIDE_TAIL_BOUND")
    out = {
        "schema": "v25_sog_bounded_integer_law_v1",
        "model_kind": kind, "support": "nonnegative_integer",
        "participation_condition": "conditional_on_played",
        "pmf_from_zero": pmf, "last_enumerated_k": len(pmf)-1,
        "unallocated_upper_tail_mass": tail, "tail_mass_upper_bound": tol,
        "tail_evaluator": "v2.nhl_sog_p4_forecasts._mass_for/v1",
        "no_truncation_renormalization": True,
        "mean": mean, "variance": variance,
        "zero_probability": pmf[0], "quantiles": quantiles,
        "parameter_source_model_sha256": stable_hash(model),
        "parameters": {
            "rate_a": a, "rate_b": b, "plugin_rate": r,
            "plugin_exposure": w0, "exposure_pmf": pi,
            "native_shape": NATIVE_SHAPE if kind=="nb2_fixed_shape4" else None,
        },
        "numerical_diagnostics": {
            "enumerated_mass": total,
            "moment_approximation_error": abs(mu-mean),
            "variance_approximation_error": abs(v-variance),
            "tail_bound_verified": True,
        },
    }
    return out


def three_way(law, line):
    _check(isinstance(line,(int,float)) and not isinstance(line,bool)
           and math.isfinite(line) and 0 <= line <= 80, "INVALID_SOG_LINE")
    ps = law["pmf_from_zero"]
    # Integer-valued SOG: q_under is strict Y < line.
    lower = math.ceil(line)-1
    _check(lower < len(ps), "QUOTE_LINE_ABOVE_BOUNDED_SUPPORT")
    under = math.fsum(ps[:max(0,lower+1)])
    push = ps[int(line)] if float(line).is_integer() else 0.0
    over = 1.0-under-push
    _check(-1e-10 <= over <= 1+1e-10, "THREE_WAY_PROBABILITY_INVALID")
    over=max(0.0,min(1.0,over))
    _check(abs(math.fsum((over,under,push))-1.0)<1e-10,
           "THREE_WAY_COMPLEMENTARITY_INVALID")
    return {"over":over, "under":under, "push":push}


def _history_receipts(bundle, *, root, now):
    own = bundle.get("own_official_history")
    peers = bundle.get("peer_official_history")
    _check(isinstance(own,list) and isinstance(peers,list) and bool(own)
           and bool(peers), "OFFICIAL_PLAYED_HISTORY_ABSENT")
    mode = bundle.get("source_classification")
    if mode == "synthetic":
        _check(bundle.get("synthetic_fixture") is True,
               "SYNTHETIC_FIXTURE_NOT_DECLARED")
        return own, peers
    _check(mode == "original_signed", "SOURCE_CLASSIFICATION_UNSUPPORTED")
    from .nhl_sog_official_history_producer import independent_verify_observation_lineage
    freeze = bundle["input_freeze_at"]
    start = bundle["event_start_at"]
    o = [independent_verify_observation_lineage(x,archive_root=root,
          freeze=freeze,event_start=start) for x in own]
    p = [independent_verify_observation_lineage(x,archive_root=root,
          freeze=freeze,event_start=start) for x in peers]
    return o,p


def fit_source_bundle(bundle, *, source_root, now=None):
    """Stable P2 adapter; no independent network access.

    For original_signed, CURRENT system time always controls the admission;
    a caller's historical timestamp cannot manufacture prospective status.
    The optional injected now exists for synthetic tests only.
    """
    _check(isinstance(bundle,dict) and bundle.get("schema")==BUNDLE_SCHEMA,
           "P2_SOURCE_BUNDLE_SCHEMA_MISSING")
    mode=bundle.get("source_classification")
    _check(mode in ("original_signed","synthetic"), "SOURCE_CLASSIFICATION_UNSUPPORTED")
    if mode == "original_signed":
        _check(now is None, "ORIGINAL_NOW_INJECTION_PROHIBITED")
        now=datetime.now(timezone.utc)
    elif now is None:
        now=datetime.now(timezone.utc)
    _check(now.tzinfo is not None, "NAIVE_NOW")
    freeze=_utc(bundle.get("input_freeze_at"),"input_freeze_at")
    start=_utc(bundle.get("event_start_at"),"event_start_at")
    cutoff=_utc(bundle.get("historical_availability_cutoff_at"),
                "historical_availability_cutoff_at")
    _check(cutoff <= freeze <= now < start, "SOURCE_OR_FORECAST_CHRONOLOGY_INVALID")
    for k in ("event_id","player_id","team_id","opponent_id","position_group"):
        _check(isinstance(bundle.get(k),str) and bool(bundle[k]), "MISSING_IDENTITY:"+k)
    _check(bundle["team_id"]!=bundle["opponent_id"],"INVALID_OPPONENT_IDENTITY")
    _check(bundle["position_group"] in ("F","D"),"POSITION_GROUP_NOT_VERIFIED")
    flags=bundle.get("flags") or {}
    _check(flags.get("role_change") is not True, "ROLE_TRANSITION_UNSUPPORTED")
    _check(flags.get("subject_out") is not True, "PLAYER_OUT")
    _check(flags.get("role_uncertain") is not True, "ROLE_UNCERTAIN")
    _check(flags.get("participation_unverified") is not True,
           "PARTICIPATION_OR_MEMBERSHIP_UNVERIFIED")
    _check(flags.get("context_affected") is not True,
           "CONTEXT_AFFECTED_COHORT_NOT_PRIMARY")
    if mode == "original_signed":
        verify_manifest(source_root,bundle.get("source_manifest_path"),
                        bundle.get("source_manifest_sha256"))
        from .phase15_nhl_roster import membership_status
        membership = membership_status(
            bundle["player_id"],bundle["team_id"],bundle["opponent_id"],
            receipts=bundle.get("official_roster_receipts") or {},
            source_root=source_root,forecast_at=now.isoformat(),
            event_start=bundle["event_start_at"])
        _check(membership.get("status")=="pre_event_team_membership_confirmed",
               "CURRENT_OFFICIAL_MEMBERSHIP_UNVERIFIED")
    own,peers=_history_receipts(bundle,root=source_root,now=now)
    model=fit_model(own,peers,archive_root=source_root,
       player_id=bundle["player_id"],position_group=bundle["position_group"],
       input_freeze_at=bundle["input_freeze_at"],
       event_start_at=bundle["event_start_at"],
       target_event_id=bundle["event_id"],current_team_id=bundle["team_id"])
    _check(_utc(model["fit_data_cutoff_at"],"fit_data_cutoff_at") <= cutoff,
           "HISTORY_RECEIVED_AFTER_TRAINING_CUTOFF")
    model["p4_source_classification"]=mode
    model["p4_input_source_manifest_sha256"]=(
        bundle.get("source_manifest_sha256") if mode=="original_signed" else None)
    model["p4_conditioning"]="conditional_on_played"
    model["p4_prospective_certification_candidate"]=(mode=="original_signed")
    # The registered fit/policy and its own model identifiers are unchanged.
    return model


def append_immutable(root, namespace, forecast_id, row):
    """Exclusive create + SHA verification; no update, overwrite or backdating."""
    _check(isinstance(forecast_id,str) and forecast_id
           and all(c.isalnum() or c in "-_" for c in forecast_id),
           "UNSAFE_FORECAST_ID")
    raw=canonical(row)
    digest=sha256(raw)
    root=Path(root).resolve()
    target=_safe_child(root,f"{namespace}/{forecast_id}.json")
    target.parent.mkdir(parents=True,exist_ok=True)
    try:
        fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:
        _check(target.read_bytes()==raw,"DUPLICATE_FORECAST_ID_OR_MUTATION")
        return {"path":str(target.relative_to(root)),"sha256":digest,
                "already_frozen":True}
    with os.fdopen(fd,"wb") as h:
        h.write(raw)
        h.flush()
        os.fsync(h.fileno())
    _check(sha256(target.read_bytes())==digest,"FORECAST_WRITE_SHA_MISMATCH")
    return {"path":str(target.relative_to(root)), "sha256":digest,
            "already_frozen":False}


def read_immutable(root, receipt):
    p=_safe_child(root,receipt["path"])
    _check(p.is_file(),"IMMUTABLE_ARTIFACT_MISSING")
    raw=p.read_bytes()
    _check(sha256(raw)==receipt["sha256"],"IMMUTABLE_ARTIFACT_MUTATED")
    return json.loads(raw)


def freeze_forecast(model, *, kind, event_id, player_id, team_id, opponent_id,
                    event_start_at, forecast_at, training_cutoff_at, code_commit,
                    source_manifest_sha256, artifact_root, forecast_id, quote=None,
                    cohort="distribution_only", experiment_id=None):
    """Serialize complete count law and optional exact original offered line.

    This method never grants quote certification or native NB2 eligibility.
    Those are issued ONLY by the existing strict original source validators.
    """
    _check(isinstance(code_commit,str) and len(code_commit)==40
           and all(c in "0123456789abcdef" for c in code_commit),
           "CODE_COMMIT_UNPINNED")
    _check(model.get("target_event_id")==event_id and
           model.get("player_id")==player_id and
           model.get("current_team_id")==team_id,
           "MODEL_FORECAST_IDENTITY_MISMATCH")
    _check(team_id!=opponent_id,"INVALID_OPPONENT_IDENTITY")
    start=_utc(event_start_at,"event_start_at")
    forecast=_utc(forecast_at,"forecast_at")
    freeze=_utc(model["input_freeze_at"],"input_freeze_at")
    trained=_utc(training_cutoff_at,"training_cutoff_at")
    _check(trained<=freeze<=forecast<start,"FORECAST_CHRONOLOGY_INVALID")
    _check(_utc(model["fit_data_cutoff_at"],"fit_data_cutoff_at")<=trained,
           "MODEL_USED_AFTER_TRAINING_CUTOFF")
    _check(cohort in ("distribution_only","original_quote_matched","synthetic"),
           "UNKNOWN_RESEARCH_COHORT")
    _check(kind in set(MODELS.values())|{"nb2_fixed_shape4"},
           "UNKNOWN_MODEL_KIND")
    if kind=="nb2_fixed_shape4":
        _check(cohort=="synthetic", "NATIVE_NB2_REQUIRES_REGISTERED_FROZEN_SOURCE")
        _check(experiment_id is None,"SYNTHETIC_CANNOT_JOIN_REGISTERED_NB2")
    if cohort=="original_quote_matched":
        _check(model.get("verified_original_source_lineage") is True,
               "ORIGINAL_SIGNED_HISTORY_NOT_VERIFIED")
        _check(quote is not None and quote.get("source_verified") is True,
               "ORIGINAL_QUOTE_VERIFIER_REQUIRED")
        _check(quote.get("event_id")==event_id and quote.get("player_id")==player_id,
               "QUOTE_PLAYER_EVENT_MISMATCH")
        _check(_utc(quote["quote_at"],"quote_at")<=freeze,
               "QUOTE_CAPTURE_AFTER_INPUT_FREEZE")
    else:
        _check(quote is None,"NO_MARKET_QUOTE_IN_DISTRIBUTION_COHORT")
    law=full_law(model,kind)
    offered=None
    if quote is not None:
        offered={"quote_id":quote["quote_id"],"contract_id":quote["contract_id"],
                 "book":quote["book"],"line":quote["line"],
                 "quote_at":quote["quote_at"],
                 "quote_receipt_sha256":quote["quote_receipt_sha256"],
                 "probabilities":three_way(law,quote["line"])}
        _check(kind != "plugin_poisson" or all(
            abs(offered["probabilities"][x]-
                forecast_lines(model,[quote["line"]],kind="plugin_poisson")[
                    format(float(quote["line"]),"g")][x])<1e-10
            for x in ("over","under","push")),"POISSON_CONTROL_CHANGED")
    row={
        "schema":SCHEMA,"forecast_id":forecast_id,"experiment_id":experiment_id,
        "event_id":event_id,"player_id":player_id,"team_id":team_id,
        "opponent_id":opponent_id,"event_start_at":event_start_at,
        "model_family":kind,"model_version":GAMMA_SCHEMA,
        "code_commit":code_commit, "model_artifact_sha256":stable_hash(model),
        "source_manifest_sha256":source_manifest_sha256,
        "input_freeze_at":model["input_freeze_at"],"forecast_at":forecast_at,
        "model_training_cutoff_at":training_cutoff_at,
        "source_classification":model.get("p4_source_classification","existing_verified_model"),
        "cohort":cohort,"participation_condition":"conditional_on_played",
        "dnp_probability":None,"void_semantics":"external_contract_settlement_only",
        "distribution":law,"original_quote":offered,
        "tier_allowed":False,"production_selection_allowed":False,
        "research_only":True,"outcome_used":False,
    }
    return append_immutable(artifact_root,"p4_nhl_sog/forecasts",forecast_id,row)


def propose_adaptive_update(previous, observations, *, cutoff_at):
    """Separate Track B sufficient-statistics challenger; no locked-model editing.

    Assumes gamma shape/rate posterior for a played-game per-minute Poisson
    rate. Explicit finalized source availability is required for each update.
    """
    _check(previous.get("schema")==ADAPTIVE_SCHEMA and
           previous.get("research_track")=="ADAPTIVE_CHALLENGER"
           and previous.get("experiment_id") not in LOCKED_IDS,
           "LOCKED_EXPERIMENT_CANNOT_BE_UPDATED")
    cutoff=_utc(cutoff_at,"cutoff_at")
    prior_cutoff=_utc(previous["model_training_cutoff_at"],
                      "model_training_cutoff_at")
    _check(cutoff>prior_cutoff,"NONINCREASING_TRAINING_CUTOFF")
    _check(isinstance(observations,list) and bool(observations),
           "NO_NEW_FINALIZED_OBSERVATIONS")
    a,b=previous["alpha"],previous["beta"]
    _check(all(isinstance(x,(int,float)) and not isinstance(x,bool)
               and math.isfinite(x) and x>0 for x in (a,b)),
           "ADAPTIVE_STATE_INVALID")
    known=set(previous.get("seen_player_game_ids",[]))
    new=[]
    for o in observations:
        _check(o.get("played") is True,"DNP_NOT_A_RATE_OBSERVATION")
        _check(o.get("finalized") is True,"UNFINALIZED_OBSERVATION")
        available=_utc(o["first_available_at"],"first_available_at")
        _check(prior_cutoff<available<=cutoff,
               "ADAPTIVE_OUTCOME_NOT_CHRONOLOGICALLY_AVAILABLE")
        _check(isinstance(o.get("source_sha256"),str)
               and len(o["source_sha256"])==64,
               "ADAPTIVE_SOURCE_SHA_MISSING")
        gid=o["player_id"]+"|"+o["event_id"]
        _check(gid not in known,"DUPLICATE_ADAPTIVE_PLAYER_GAME")
        known.add(gid)
        y=o.get("shots_on_goal");w=o.get("toi_minutes")
        _check(isinstance(y,int) and not isinstance(y,bool) and y>=0
               and isinstance(w,(int,float)) and not isinstance(w,bool)
               and math.isfinite(w) and 0<w<=65, "INVALID_FINAL_SOG_TOI")
        a+=y; b+=w; new.append(o)
    result=dict(previous)
    result.update(alpha=a,beta=b,model_training_cutoff_at=cutoff_at,
        seen_player_game_ids=sorted(known),
        parent_model_sha256=sha256(canonical(previous)),
        new_training_data_sha256=sha256(canonical(new)),
        version=int(previous["version"])+1,
        outcome_access_scope="finalized_prior_games_only",
        production_selection_allowed=False)
    return result


def freeze_adaptive_update(root, model_id, previous, observations, *, cutoff_at):
    """Validate fully BEFORE exclusive creation; parent survives failed updates."""
    nxt=propose_adaptive_update(previous,observations,cutoff_at=cutoff_at)
    return append_immutable(root,"p4_nhl_sog/adaptive_models",
           model_id+"_v"+str(nxt["version"]),nxt)


def coverage_attempt(root, *, attempt_id, event_id, player_id, reason,
                     source_classification, forecast_at):
    _check(reason != "", "EMPTY_ABSTENTION_REASON")
    row={"schema":"v25_nhl_sog_p4_attempt_v1","attempt_id":attempt_id,
         "event_id":event_id,"player_id":player_id,
         "reason":reason,"status":"ABSTAIN",
         "source_classification":source_classification,
         "attempted_at":forecast_at,"research_only":True}
    return append_immutable(root,"p4_nhl_sog/attempts",attempt_id,row)
