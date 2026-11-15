"""Phase 5.1: research-only S1 posterior-mean Poisson and frozen Gamma comparisons.

The pure mathematical interface does NOT certify data. Only run_day(), using
the unchanged original C03 collector and native source verifier, may write
genuinely pregame shadow forecasts. No old experiment is modified.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
from zoneinfo import ZoneInfo

from . import nhl_sog_exposure_shadow as gamma

EXPERIMENT = "EXP-V25-NHL-SOG-RATE-SHRINKAGE-PROSPECTIVE-001"
SCHEMA = "v25_nhl_sog_rate_shrinkage_source_certified_v1"
SPEC_FILE = "config/experiment_specs/EXP_V25_NHL_SOG_RATE_SHRINKAGE_PROSPECTIVE_001.json"
UTC = timezone.utc
MAX_K = 4096
MODEL_IDS = ("M0", "S1", "M2", "M1", "M3", "M4")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
FORBIDDEN = frozenset({
    "current_game_sog", "current_game_toi", "actual_sog", "actual_toi",
    "final_score", "current_game_played", "postgame_roster", "target_outcome",
    "final_sog", "final_toi", "current_game_roster_appearance",
    "postgame_lineup", "realized_sog", "realized_toi"
})

class S1Blocked(ValueError):
    """Explicit integrity/availability failure; never infer or backdate data."""


def _check(predicate, reason):
    if not predicate:
        raise S1Blocked(reason)


def canon(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def sha(body):
    return hashlib.sha256(body).hexdigest()


def utc(value):
    _check(isinstance(value, str) and "T" in value, "TIMESTAMP_MISSING")
    try:
        v = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError, TypeError) as exc:
        raise S1Blocked("TIMESTAMP_INVALID") from exc
    _check(v.tzinfo is not None and v.utcoffset() is not None, "TIMESTAMP_NAIVE")
    return v.astimezone(UTC)


def valid_played_toi(x):
    _check(type(x) in (float, int) and math.isfinite(x)
           and 0 < x <= 65, "PLAYED_TOI_INVALID_OR_DNP")
    return float(x)


def _num(x, field, *, positive=False):
    _check(type(x) in (float, int) and math.isfinite(x)
           and (x > 0 if positive else x >= 0), "INVALID_" + field.upper())
    return float(x)


def verify_sha_bytes(path, digest):
    _check(isinstance(digest, str) and HEX64.fullmatch(digest) is not None,
           "SOURCE_SHA256_INVALID")
    p = Path(path)
    _check(p.is_file(), "SOURCE_RECEIPT_MISSING")
    raw = p.read_bytes()
    _check(sha(raw) == digest, "SOURCE_RECEIPT_SHA256_MISMATCH")
    return raw


def append_exact(path, value):
    p = Path(path)
    body = canon(value)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        with p.open("xb") as fp:
            fp.write(body)
    except FileExistsError:
        _check(p.read_bytes() == body, "IMMUTABLE_ARTIFACT_OVERWRITE_ATTEMPT")
    return sha(body)


def _append_addressed(root, folder, obj):
    data = canon(obj)
    digest = sha(data)
    path = Path(root) / folder / (digest + ".json")
    append_exact(path, obj)
    return {"path": str(path), "sha256": digest}


def assert_unique_player_games(pairs):
    pairs = list(pairs)
    _check(len(pairs) == len(set(pairs)), "DUPLICATE_PLAYER_GAME")
    return len(pairs)


def poisson_pmf(mu):
    """Recurrence avoids factorials; tail truncation <=1e-13, no renormalizing."""
    mu = _num(mu, "POISSON_MEAN")
    _check(mu <= 200, "SOG_MEAN_OUTSIDE_RESEARCH_SUPPORT")
    if mu == 0:
        return [1.0]
    probs = [math.exp(-mu)]
    running = probs[0]
    for k in range(1, MAX_K + 1):
        probs.append(probs[-1] * mu / k)
        running += probs[-1]
        if k >= 20 and k > mu and 1. - running < 1e-13:
            break
    _check(0 <= 1.-running < 1e-10, "POISSON_MASS_NOT_NORMALIZED")
    return probs


def _gamma_mass(k, a, b, w):
    return gamma._pmf_gamma_poisson(k, a, b, w)


def _other_pmf(model, kind):
    if kind == "M0":
        return poisson_pmf(float(model["plugin_rate"]) * float(model["plugin_exposure"]))
    if kind == "M4":
        mu = float(model["plugin_rate"]) * float(model["plugin_exposure"])
        _check(0 <= mu <= 200, "NB2_MEAN_INVALID")
        if mu == 0:
            return [1.]
        r = 4.
        def mass(k):
            return math.exp(math.lgamma(k+r)-math.lgamma(r)-math.lgamma(k+1)
                            +r*math.log(r/(r+mu))+k*math.log(mu/(r+mu)))
    else:
        mapping = {"M1":"mixture_exposure_plugin_poisson",
                   "M2":"fixed_exposure_gamma_poisson",
                   "M3":"full_gamma_poisson_exposure"}
        _check(kind in mapping, "UNKNOWN_CONTROL")
        def mass(k):
            return gamma._mass(model, k, mapping[kind])
    probs = []
    cumulative = 0.
    for k in range(MAX_K+1):
        x = mass(k)
        _check(math.isfinite(x) and x >= 0, "NEGATIVE_OR_NONFINITE_MASS")
        probs.append(x)
        cumulative += x
        if k >= 20 and 1.-cumulative < 1e-13:
            break
    _check(0 <= 1.-cumulative < 1e-10, "CONTROL_PMF_NOT_NORMALIZED")
    return probs


def summary(pmf):
    total = math.fsum(pmf)
    _check(pmf and all(math.isfinite(x) and x >= 0 for x in pmf)
           and abs(total-1.) < 1e-10, "DISTRIBUTION_NOT_NORMALIZED")
    mean = math.fsum(k*x for k,x in enumerate(pmf))
    variance = math.fsum((k-mean)**2*x for k,x in enumerate(pmf))
    return {"mean":mean, "variance":variance, "zero":pmf[0],
            "tail6":max(0., 1.-math.fsum(pmf[:6]))}


def exact_contract_probs(pmf, line):
    line = _num(line, "LINE")
    _check(0 <= line <= 80, "LINE_OUTSIDE_SUPPORT")
    summary(pmf)
    lower = math.ceil(line)-1
    under = math.fsum(pmf[:lower+1])
    push = pmf[int(line)] if line.is_integer() and int(line)<len(pmf) else 0.
    over = 1. - under - push
    _check(over >= -1e-10 and 0 <= under <= 1+1e-10
           and 0 <= push <= 1+1e-10, "THREE_WAY_INTEGRITY")
    p = {"under":min(1.,under),"push":push,"over":max(0.,over)}
    _check(abs(math.fsum(p.values())-1)<1e-10, "THREE_WAY_NOT_NORMALIZED")
    return p


def score_count(pmf, actual):
    _check(type(actual) is int and 0 <= actual < len(pmf), "SOG_OUTCOME_UNSUPPORTED")
    summary(pmf)
    cumulative = 0.
    crps = 0.
    for k,x in enumerate(pmf):
        cumulative += x
        crps += (cumulative - float(k >= actual))**2
    _check(pmf[actual] > 0, "TARGET_ZERO_MASS")
    return {"crps":crps, "nll":-math.log(pmf[actual]),
            "actual_sog":actual}


def build_paired_distributions(model, *, forecast_at, code_sha,
                               expected_event_id, expected_player_id):
    """Pure mathematical QA. The caller MUST separately certify all source bytes."""
    _check(isinstance(model, dict) and model.get("schema") == gamma.SCHEMA,
           "GAMMA_SCHEMA_MISMATCH")
    _check(not (FORBIDDEN & set(model)), "CURRENT_GAME_POSTGAME_FEATURE_PRESENT")
    _check(isinstance(code_sha, str) and HEX40.fullmatch(code_sha) is not None,
           "UNPINNED_CODE_COMMIT")
    _check(str(expected_event_id) == model.get("target_event_id") and
           str(expected_player_id) == model.get("player_id"),
           "PLAYER_EVENT_IDENTITY_MISMATCH")
    _check(model.get("gamma_parameterization") == "shape_rate"
           and float(model.get("tau_minutes", -1)) == 60.,
           "POSTERIOR_OR_PRIOR_PARAMETERIZATION_DRIFT")
    freeze = utc(model.get("input_freeze_at"))
    event = utc(model.get("event_start_at"))
    forecast = utc(forecast_at)
    cutoff = utc(model.get("fit_data_cutoff_at"))
    _check(cutoff <= freeze <= forecast < event, "MODEL_OR_FEATURE_TIME_LEAK")
    a = _num(model.get("rate_a"), "GAMMA_SHAPE", positive=True)
    b = _num(model.get("rate_b"), "GAMMA_RATE", positive=True)
    w0 = valid_played_toi(model.get("plugin_exposure"))
    _num(model.get("plugin_rate"), "OWN_RATE")
    mu = (a/b) * w0
    _check(mu <= 200, "SOG_MEAN_OUTSIDE_RESEARCH_SUPPORT")
    for receipt in model.get("source_manifest", []):
        _check(utc(receipt.get("received_at")) <= freeze, "SOURCE_AFTER_FREEZE")
        _check(str(receipt.get("event_id")) != str(expected_event_id),
               "TARGET_GAME_IN_PREGAME_HISTORY")
    models = {}
    for name in MODEL_IDS:
        pmf = poisson_pmf(mu) if name == "S1" else _other_pmf(model, name)
        z = summary(pmf)
        if name == "S1":
            _check(abs(z["mean"]-mu)<1e-8 and abs(z["variance"]-mu)<1e-7,
                   "POISSON_ANALYTIC_MOMENT_MISMATCH")
        if name == "M2":
            mean2 = mu
            var2 = mu+w0*w0*a/(b*b)
            _check(abs(z["mean"]-mean2)<1e-7 and abs(z["variance"]-var2)<1e-6,
                   "GAMMA_ANALYTIC_MOMENT_MISMATCH")
        models[name] = {"model_id":name,"pmf":pmf,**z}
    return models


def _within(root, rel):
    _check(isinstance(rel, str) and rel and "\\x00" not in rel
           and "\\\\" not in rel, "SOURCE_PATH_UNSAFE")
    rp = Path(rel)
    _check(not rp.is_absolute() and ".." not in rp.parts, "SOURCE_PATH_UNSAFE")
    path = (Path(root).resolve()/rp).resolve()
    _check(path.is_relative_to(Path(root).resolve()), "SOURCE_PATH_TRAVERSAL")
    return path


def _recompute_posterior_from_signed_sources(model, source_pool):
    """Separate raw-byte arithmetic check after native verifier has audited lineage."""
    manifests = model.get("source_manifest")
    n = model.get("own_played_games")
    q = model.get("peer_games")
    _check(type(n) is int and n >= 5 and n <= 20 and
           type(q) is int and q >= 200 and isinstance(manifests,list)
           and len(manifests) == n+q, "HISTORY_DENOMINATOR_MISMATCH")
    obs = []
    for r in manifests:
        raw = verify_sha_bytes(_within(source_pool,r.get("archive_path")),
                               r.get("content_sha256"))
        try:
            d = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise S1Blocked("SIGNED_OBSERVATION_JSON_INVALID") from exc
        _check(d.get("schema") == gamma.OBS_SCHEMA
               and d.get("played") is True
               and d.get("player_id") == r.get("player_id")
               and d.get("event_id") == r.get("event_id"), "SOURCE_IDENTITY_OR_DNP")
        _check(str(d.get("event_id")) != str(model["target_event_id"]),
               "CURRENT_EVENT_HISTORY_CONTAMINATION")
        ended = utc(d.get("event_ended_at"))
        received = utc(r.get("received_at"))
        freeze = utc(model["input_freeze_at"])
        _check(ended <= received <= freeze, "SOURCE_FINAL_NOT_AVAILABLE_PRE_FREEZE")
        w=valid_played_toi(d.get("toi_minutes"))
        y=d.get("shots_on_goal")
        _check(type(y) is int and y >= 0, "OFFICIAL_SOG_INVALID")
        obs.append((str(d["player_id"]),str(d["event_id"]),y,w,d))
    assert_unique_player_games([(x[0],x[1]) for x in obs])
    own=obs[:n];peers=obs[n:]
    _check(all(x[0]==str(model["player_id"]) and
               x[4]["position_group"]==model["position_group"] for x in own),
           "OWN_SOURCE_PLAYER_OR_ROLE_MISMATCH")
    _check(all(x[0]!=str(model["player_id"]) and
               x[4]["position_group"]==model["position_group"] for x in peers),
           "PEER_SOURCE_PLAYER_OR_ROLE_MISMATCH")
    peer_group = {x[0] for x in peers}
    _check(len(peer_group) >= 20 and
           len(peer_group) == model.get("peer_players"), "PEER_COHORT_DRIFT")
    r_peer=math.fsum(x[2] for x in peers)/math.fsum(x[3] for x in peers)
    a=60.*r_peer+math.fsum(x[2] for x in own)
    b=60.+math.fsum(x[3] for x in own)
    w0=float(statistics.median(x[3] for x in own[-5:]))
    ownrate=math.fsum(x[2] for x in own)/math.fsum(x[3] for x in own)
    for name,expected in [("rate_a",a),("rate_b",b),
                          ("plugin_exposure",w0),("plugin_rate",ownrate),
                          ("peer_rate",r_peer)]:
        _check(math.isclose(float(model[name]),expected,rel_tol=1e-11,abs_tol=1e-10),
               "RAW_SOURCE_POSTERIOR_RECOMPUTE_MISMATCH:"+name)
    _check(max(utc(r["received_at"]) for r in manifests)
           == utc(model["fit_data_cutoff_at"]), "TRAINING_DATA_CUTOFF_DRIFT")
    _check([x["content_sha256"] for x in manifests[:n]] ==
           model.get("own_source_sha256") and
           [x["content_sha256"] for x in manifests[n:]] ==
           model.get("peer_source_sha256"), "SOURCE_SHA_MEMBERSHIP_DRIFT")
    return {"signed_own_games":n,"signed_peer_games":q,"signed_peer_players":len(peer_group),
            "peer_rate":r_peer,"recomputed_a":a,"recomputed_b":b,
            "recomputed_w0":w0,"raw_short_positive_toi_count":
                sum(x[3]<0.25 for x in obs)}


def run_day(root, *, code_sha):
    """One on-demand source-native research capture; no schedules, no outcomes."""
    from .nhl_sog_nb2_source_native import verify_native_source
    _check(isinstance(code_sha,str) and HEX40.fullmatch(code_sha) is not None,
           "MODEL_COMMIT_REQUIRED")
    root=Path(root).resolve()
    spec_path=Path(__file__).resolve().parents[1]/SPEC_FILE
    spec_raw=spec_path.read_bytes() if spec_path.is_file() else b""
    _check(spec_raw, "PREREGISTERED_SPEC_MISSING")
    spec=json.loads(spec_raw)
    _check(spec.get("experiment_id")==EXPERIMENT and
           spec.get("schema")=="v25_nhl_sog_rate_shrinkage_preregistered_v1" and
           spec.get("status")=="PREREGISTERED_SHADOW_ONLY_NO_OUTCOME_INSPECTION" and
           spec["model"]["tau_minutes"]==60 and
           spec["primary"]["margin_CRPS"]==0.001, "PREREGISTRATION_DRIFT")
    now=datetime.now(UTC)
    day=now.astimezone(ZoneInfo("America/Toronto")).date().isoformat()
    result={"schema":"v25_nhl_sog_s1_attempt_audit_v1","experiment_id":EXPERIMENT,
            "date_et":day,"captured_at_utc":now.isoformat(),
            "code_commit":code_sha,"code_source_sha256":sha(Path(__file__).read_bytes()),
            "preregistration_sha256":sha(spec_raw),"research_only":True,
            "production_changed":False,"no_outcome_access":True,
            "attempts":[],"status":"NOT_STARTED","source_batches":0}
    if spec["primary"]["prospective_start_et"] <= day <= spec["primary"]["prospective_end_et"]:
        directory=root/"reports"/"v25_sog_source_cert_sprint"/day
        candidates=sorted(directory.glob(
            "daily_original_gamma_poisson_research_*/daily_research_generation_manifest.json"))
        result["source_batches"]=len(candidates)
        result["status"]="NO_FROZEN_ORIGINAL_SOURCE_BATCH"
        if candidates:
            first=candidates[0]
            mraw=first.read_bytes()
            manifest=json.loads(mraw)
            _check(manifest.get("schema")==
                   "v25_daily_original_sog_gamma_poisson_research_generator_v1"
                   and manifest.get("slate_date_et")==day
                   and manifest.get("research_only") is True
                   and manifest.get("forecast_promotion_allowed") is False,
                   "ORIGINAL_SOURCE_BATCH_CONTRACT_INVALID")
            result["original_c03_manifest_sha256"]=sha(mraw)
            result["source_manifest"]=str(first.relative_to(root))
            result["source_stage_denominators"]=manifest.get("counts",{})
            result["source_stage_failures"]=manifest.get("failures",[])
            attempts=manifest.get("attempts")
            _check(isinstance(attempts,list), "SOURCE_ATTEMPT_LEDGER_MISSING")
            result["source_attempt_count"]=len(attempts)
            seen=set()
            for a in attempts:
                row={"original_receipt_sha256":a.get("receipt_sha256"),
                     "player_id":a.get("player_id"),
                     "official_event_id":a.get("official_nhl_event_id"),
                     "status":"ABSTAIN","reason":None}
                try:
                    _check(a.get("status")=="SHADOW_FORECAST",
                           "ORIGINAL_NOT_FROZEN")
                    # This verifier reads only pregame sources and frozen origin
                    # snapshots. It does not read either experiment's outcomes.
                    e=verify_native_source(root,manifest,first,a,now=now)
                    q=e["quote"]; model=e["model"]
                    key=(str(e["official_event_id"]),str(q.player_id))
                    _check(key not in seen,"DUPLICATE_SOURCE_PLAYER_EVENT")
                    seen.add(key)
                    _check(now < utc(q.event_start_at)-timedelta(minutes=3),
                           "GAME_START_TOO_CLOSE")
                    pool=_within(root,manifest["source_pool"])
                    audit=_recompute_posterior_from_signed_sources(model,pool)
                    distributions=build_paired_distributions(
                        model,forecast_at=now.isoformat(),code_sha=code_sha,
                        expected_event_id=q.event_id,expected_player_id=q.player_id)
                    for v in distributions.values():
                        v["original_line_three_way"]=exact_contract_probs(v["pmf"],q.line)
                    frozen_dir=root/"reports"/"v25_sog_rate_shrinkage_prospective"/day/"frozen"
                    frozen_dir.mkdir(parents=True,exist_ok=True)
                    existing=[]
                    for fp in sorted(frozen_dir.glob("*.json")):
                        verify_sha_bytes(fp,fp.stem)
                        old=json.loads(fp.read_bytes())
                        if (old.get("official_nhl_event_id"),old.get("player_id"))==key:
                            existing.append(fp)
                    _check(len(existing)<=1,"DUPLICATE_FROZEN_PLAYER_EVENT")
                    if existing:
                        old=json.loads(existing[0].read_bytes())
                        _check(old["original_c03_model_sha256"]==e["model_digest"]
                               and old["original_c03_snapshot_sha256"]==
                               e["snapshot_digest"], "ORIGINAL_SOURCE_CHANGED_ON_REPLAY")
                        row["status"]="ALREADY_FROZEN"
                        row["forecast_sha256"]=existing[0].stem
                        result["attempts"].append(row)
                        continue
                    z={"schema":SCHEMA,"experiment_id":EXPERIMENT,
                       "source_certification":"CERTIFIED_COLLECTOR_POSSESSION_NO_UPSTREAM_PUBLISHER_TIMESTAMP",
                       "publisher_publication_time_authenticated":False,
                       "official_nhl_event_id":key[0],"event_id":q.event_id,
                       "player_id":key[1],"team_id":q.team_id,"opponent_id":q.opponent_id,
                       "position_group":model["position_group"],"stat_key":"shots on goal",
                       "period":"full","event_start_at":q.event_start_at,
                       "input_freeze_at":model["input_freeze_at"],
                       "model_training_cutoff_at":model["fit_data_cutoff_at"],
                       "forecast_at":now.isoformat(),"code_commit":code_sha,
                       "code_source_sha256":result["code_source_sha256"],
                       "preregistration_sha256":result["preregistration_sha256"],
                       "original_c03_manifest_sha256":result["original_c03_manifest_sha256"],
                       "original_c03_model_sha256":e["model_digest"],
                       "original_c03_snapshot_sha256":e["snapshot_digest"],
                       "original_c03_attempt_sha256":e["original_wrapper_digest"],
                       "original_c03_input_sha256":e["original_input_digest"],
                       "original_original_provider_http_sha256":e["provider_http_body_digest"],
                       "original_quote_id":q.quote_id,"original_contract_id":q.contract_id,
                       "original_quote_at":q.quote_at,"original_book":q.book,
                       "original_offered_line":q.line,
                       "original_two_sided_offer_verified":True,
                       "model_conditioning":"played_game; DNP separately unscored",
                       "official_roster_membership_verified":True,
                       "lineup_participation_confirmed":False,
                       "posterior_a":model["rate_a"],"posterior_b":model["rate_b"],
                       "prior_tau_minutes":60.,"own_game_count":model["own_played_games"],
                       "peer_game_count":model["peer_games"],
                       "history_source_sha256":[r["content_sha256"] for r in model["source_manifest"]],
                       "source_recompute_audit":audit,
                       "distributions":distributions,
                       "no_outcome_access":True,"production_selection_allowed":False,
                       "tier_publication_allowed":False,"model_promotion_allowed":False}
                    digest=sha(canon(z))
                    fp=frozen_dir/(digest+".json")
                    append_exact(fp,z)
                    row["status"]="FROZEN_S1_M0_M2_RESEARCH"
                    row["forecast_sha256"]=digest
                    row["forecast_path"]=str(fp.relative_to(root))
                except (S1Blocked,ValueError,KeyError,TypeError,OSError) as exc:
                    row["reason"]=type(exc).__name__+":"+str(exc)[:180]
                result["attempts"].append(row)
            result["status"]=("FROZEN_SOURCE_CERTIFIED_SHADOW" if any(
                x["status"]=="FROZEN_S1_M0_M2_RESEARCH" for x in result["attempts"])
                else "NO_NEW_ELIGIBLE_FUTURE_FORECAST")
    result["counts"]={k:sum(a["status"]==k for a in result["attempts"])
                      for k in ("FROZEN_S1_M0_M2_RESEARCH","ALREADY_FROZEN","ABSTAIN")}
    result["audit_receipt"]=_append_addressed(
        root,"reports/v25_sog_rate_shrinkage_prospective/"+day+"/attempt_audit",result)
    return result
