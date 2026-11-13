"""EXP-V25-NHL-SOG-EXPOSURE-EB-001: exact CPU-only shadow distribution.

This module cannot certify offers or roster participation. Inputs must be
collector-held, hash-bound historical observation objects; downstream C03 and
official roster contracts control eligible prospective publication. No market,
game-script or teammate-absence adjustment is used.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import statistics

EXPERIMENT="EXP-V25-NHL-SOG-EXPOSURE-EB-001"
SCHEMA="v25_nhl_sog_exposure_gamma_poisson_v1"
OBS_SCHEMA="v25_nhl_sog_observation_v1"
TAU_MINUTES=60.0
ETA_GAMES=3.0
MAX_ICE_MINUTES=65.0
MIN_PLAYER_GAMES=5
MIN_PEERS=20
MIN_PEER_GAMES=200
MAX_RATE_GAMES=20
MAX_EXPOSURE_GAMES=10
MAX_PEER_RATE_GAMES=20


class ExperimentBlocked(ValueError):
    """Invalid or unavailable source/model input; never silently impute."""


def _canonical(v):
    return json.dumps(v,ensure_ascii=False,sort_keys=True,
                      separators=(",",":"),allow_nan=False).encode("utf-8")


def stable_hash(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _utc(value, label):
    if not isinstance(value,str) or "T" not in value:
        raise ExperimentBlocked("MISSING_TIMESTAMP:"+label)
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    except (ValueError,TypeError,OverflowError) as e:
        raise ExperimentBlocked("INVALID_TIMESTAMP:"+label) from e
    if dt.tzinfo is None:
        raise ExperimentBlocked("NAIVE_TIMESTAMP:"+label)
    return dt.astimezone(timezone.utc)


def _num(v,label):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):
        raise ExperimentBlocked("INVALID_NUMBER:"+label)
    return float(v)


def bin_toi_minutes(minutes):
    """0.5-minute, half-up grid; short played intervals never become DNP."""
    minutes=_num(minutes,"TOI")
    if not 0<minutes<=MAX_ICE_MINUTES:
        raise ExperimentBlocked("INVALID_PLAYED_TOI")
    units=int((Decimal(str(minutes))*2).quantize(Decimal("1"),rounding=ROUND_HALF_UP))
    return min(MAX_ICE_MINUTES,max(1,units)/2)


def verify_observation(receipt, archive_root, freeze_at):
    """Verify bytes, actual archived row semantics and pregame possession.

    'collector_observed_bytes' means archived structured source bytes; it is
    NOT an authenticated upstream HTTP publication timestamp.
    """
    if not isinstance(receipt,dict) or receipt.get("source_kind")!="collector_observed_bytes":
        raise ExperimentBlocked("SOURCE_RECEIPT_KIND_INVALID")
    root=Path(archive_root).resolve()
    rel=receipt.get("archive_path")
    if (not isinstance(rel,str) or not rel or rel.startswith("/") or
            "\\" in rel or ".." in Path(rel).parts):
        raise ExperimentBlocked("SOURCE_PATH_UNSAFE")
    path=(root/rel).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ExperimentBlocked("SOURCE_ARCHIVE_MISSING")
    raw=path.read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    if digest != receipt.get("content_sha256"):
        raise ExperimentBlocked("SOURCE_DIGEST_MISMATCH")
    url=receipt.get("source_url")
    if not isinstance(url,str) or not url.startswith("https://"):
        raise ExperimentBlocked("SOURCE_URL_UNVERIFIED")
    freeze=_utc(freeze_at,"freeze")
    received=_utc(receipt.get("received_at"),"source_received")
    if received>freeze:
        raise ExperimentBlocked("SOURCE_RECEIVED_AFTER_FREEZE")
    try:
        d=json.loads(raw)
    except (ValueError,UnicodeDecodeError) as e:
        raise ExperimentBlocked("SOURCE_NOT_JSON") from e
    if not isinstance(d,dict) or d.get("schema")!=OBS_SCHEMA:
        raise ExperimentBlocked("SOURCE_OBSERVATION_SCHEMA_INVALID")
    ended=_utc(d.get("event_ended_at"),"observed_event_end")
    if not ended<=received<=freeze:
        raise ExperimentBlocked("HISTORICAL_OUTCOME_NOT_YET_AVAILABLE")
    for field in ("event_id","player_id"):
        if not isinstance(d.get(field),str) or not d[field]:
            raise ExperimentBlocked("SOURCE_IDENTITY_MISSING:"+field)
    if d.get("position_group") not in ("F","D"):
        raise ExperimentBlocked("POSITION_NOT_VERIFIED")
    if d.get("played") is not True:
        raise ExperimentBlocked("DNP_NOT_A_PLAYED_GAME")
    w=_num(d.get("toi_minutes"),"TOI")
    y=_num(d.get("shots_on_goal"),"SOG")
    if not 0<w<=MAX_ICE_MINUTES or y<0 or not y.is_integer():
        raise ExperimentBlocked("INVALID_SOG_OR_TOI")
    return {**d,"source_sha256":digest,"source_received_at":receipt["received_at"]}


def _clean_history(receipts, *, root, freeze, intended=None, position=None):
    checked=[]
    ids=set()
    for r in receipts:
        d=verify_observation(r,root,freeze)
        if intended is not None and d["player_id"]!=intended:
            raise ExperimentBlocked("PLAYER_IDENTITY_MISMATCH")
        if position is not None and d["position_group"]!=position:
            raise ExperimentBlocked("POSITION_GROUP_MISMATCH")
        key=(d["player_id"],d["event_id"])
        if key in ids:
            raise ExperimentBlocked("DUPLICATE_PLAYER_GAME")
        ids.add(key)
        checked.append(d)
    checked.sort(key=lambda d:(d["event_ended_at"],d["event_id"],d["player_id"]))
    return checked


def _pmf_gamma_poisson(k,a,b,w):
    if k<0:return 0.
    if a<=0 or b<=0 or w<=0:
        raise ExperimentBlocked("GAMMA_PARAMETER_INVALID")
    logp=(math.lgamma(a+k)-math.lgamma(a)-math.lgamma(k+1)
          +a*math.log(b/(b+w))+k*math.log(w/(b+w)))
    return math.exp(logp)


def _pmf_poisson(k,mu):
    if k<0:return 0.
    if mu<0 or not math.isfinite(mu):
        raise ExperimentBlocked("POISSON_MEAN_INVALID")
    if mu==0:return float(k==0)
    return math.exp(-mu+k*math.log(mu)-math.lgamma(k+1))


def _moments(pi, lam, posterior_a=None, posterior_b=None):
    ew=math.fsum(w*p for w,p in pi)
    ew2=math.fsum(w*w*p for w,p in pi)
    vw=max(0.0,ew2-ew*ew)
    mu=ew*lam
    var=mu+vw*lam*lam
    if posterior_a is not None:
        var+=ew2*posterior_a/(posterior_b*posterior_b)
    return mu,var


def fit_model(own_receipts, peer_receipts, *, archive_root,player_id,
              position_group,input_freeze_at,event_start_at,role_change=False,
              subject_out=False,context_affected=False):
    """Return immutable-ready full distribution parameters and source hashes.

    Cohort A only. The calling layer MUST independently verify current official
    roster membership and full contract certification before prospective scoring.
    """
    freeze=_utc(input_freeze_at,"input_freeze_at")
    event=_utc(event_start_at,"event_start_at")
    if not freeze<event:
        raise ExperimentBlocked("FORECAST_NOT_PREGAME")
    if role_change:
        raise ExperimentBlocked("ROLE_TRANSITION_UNSUPPORTED")
    if subject_out:
        raise ExperimentBlocked("PLAYER_OUT")
    if context_affected:
        raise ExperimentBlocked("CONTEXT_AFFECTED_COHORT_NOT_PRIMARY")
    if position_group not in ("F","D") or not str(player_id):
        raise ExperimentBlocked("PLAYER_POSITION_UNKNOWN")
    own=_clean_history(own_receipts,root=archive_root,freeze=input_freeze_at,
                       intended=str(player_id),position=position_group)
    if len(own)<MIN_PLAYER_GAMES:
        raise ExperimentBlocked("THIN_OWN_HISTORY")
    own=own[-MAX_RATE_GAMES:]
    peers=_clean_history(peer_receipts,root=archive_root,freeze=input_freeze_at,
                         position=position_group)
    if any(p["player_id"]==str(player_id) for p in peers):
        raise ExperimentBlocked("PEER_TARGET_DOUBLE_COUNT")
    by_player=defaultdict(list)
    for p in peers:by_player[p["player_id"]].append(p)
    if len(by_player)<MIN_PEERS:
        raise ExperimentBlocked("THIN_PEER_PLAYERS")
    peers=[o for player in sorted(by_player) for o in by_player[player][-MAX_PEER_RATE_GAMES:]]
    if len(peers)<MIN_PEER_GAMES:
        raise ExperimentBlocked("THIN_PEER_GAMES")
    rate_peer=math.fsum(o["shots_on_goal"] for o in peers)/math.fsum(o["toi_minutes"] for o in peers)
    if not math.isfinite(rate_peer) or rate_peer<=0:
        raise ExperimentBlocked("NONPOSITIVE_PEER_RATE")
    a=TAU_MINUTES*rate_peer+math.fsum(o["shots_on_goal"] for o in own)
    b=TAU_MINUTES+math.fsum(o["toi_minutes"] for o in own)
    if a<=0 or b<=0:
        raise ExperimentBlocked("INVALID_POSTERIOR")
    h=Counter(bin_toi_minutes(o["toi_minutes"]) for o in peers)
    htotal=len(peers)
    recent=own[-MAX_EXPOSURE_GAMES:]
    n=Counter(bin_toi_minutes(o["toi_minutes"]) for o in recent)
    support=sorted(set(h)|set(n))
    pi=tuple((w,(n[w]+ETA_GAMES*h[w]/htotal)/(len(recent)+ETA_GAMES)) for w in support)
    mass=math.fsum(p for _,p in pi)
    if abs(mass-1)>1e-12 or any(p<0 or w<=0 for w,p in pi):
        raise ExperimentBlocked("EXPOSURE_PMF_INVALID")
    mean,var=_moments(pi,a/b,a,b)
    w0=float(statistics.median(o["toi_minutes"] for o in own[-5:]))
    own_rate=math.fsum(o["shots_on_goal"] for o in own)/math.fsum(o["toi_minutes"] for o in own)
    model={
      "schema":SCHEMA,"experiment_id":EXPERIMENT,
      "status":"RESEARCH_SHADOW_DISTRIBUTION_ONLY",
      "certified_pregame_offer":False,"promotion_allowed":False,
      "tier_publication_allowed":False,
      "conditioning":"played_game; no DNP mass in this distribution",
      "position_group":position_group,"player_id":str(player_id),
      "input_freeze_at":input_freeze_at,"event_start_at":event_start_at,
      "rate_a":a,"rate_b":b,"gamma_parameterization":"shape_rate",
      "peer_rate":rate_peer,"tau_minutes":TAU_MINUTES,"eta_games":ETA_GAMES,
      "exposure_unit":"minutes","exposure_bin_minutes":0.5,
      "exposure_pmf":[[w,p] for w,p in pi],
      "plugin_rate":own_rate,"plugin_exposure":w0,
      "own_played_games":len(own),"peer_players":len(by_player),
      "peer_games":len(peers),
      "own_source_sha256":[o["source_sha256"] for o in own],
      "peer_source_sha256":[o["source_sha256"] for o in peers],
      "mean":mean,"variance":var,
      "zero_probability":math.fsum(p*_pmf_gamma_poisson(0,a,b,w) for w,p in pi),
      "model_id":"SOG_EXPOSURE_GAMMA_POISSON_V1"
    }
    if not 0<=model["zero_probability"]<=1 or not math.isfinite(var):
        raise ExperimentBlocked("DISTRIBUTION_MOMENTS_INVALID")
    return model


def _mass(model,k,kind="full_gamma_poisson_exposure"):
    a,b=model["rate_a"],model["rate_b"]
    pi=model["exposure_pmf"]
    r=model["plugin_rate"]; w0=model["plugin_exposure"]
    if kind=="plugin_poisson":
        return _pmf_poisson(k,r*w0)
    if kind=="fixed_exposure_gamma_poisson":
        return _pmf_gamma_poisson(k,a,b,w0)
    if kind=="mixture_exposure_plugin_poisson":
        return math.fsum(p*_pmf_poisson(k,r*w) for w,p in pi)
    if kind=="full_gamma_poisson_exposure":
        return math.fsum(p*_pmf_gamma_poisson(k,a,b,w) for w,p in pi)
    raise ExperimentBlocked("UNKNOWN_ABLATION")


def same_data_ablations(model):
    if model.get("schema")!=SCHEMA:
        raise ExperimentBlocked("MODEL_SCHEMA_MISMATCH")
    pi=model["exposure_pmf"]
    r=model["plugin_rate"];w0=model["plugin_exposure"]
    mu_mix,var_mix=_moments(pi,r)
    lam=model["rate_a"]/model["rate_b"]
    mu_fix=w0*lam
    var_fix=mu_fix+w0*w0*model["rate_a"]/model["rate_b"]**2
    return {
      "plugin_poisson":{"kind":"poisson","mean":r*w0,"variance":r*w0},
      "fixed_exposure_gamma_poisson":{"kind":"gamma_poisson","mean":mu_fix,"variance":var_fix},
      "mixture_exposure_plugin_poisson":{"kind":"exposure_poisson_mixture","mean":mu_mix,"variance":var_mix},
      "full_gamma_poisson_exposure":{"kind":"exposure_gamma_poisson_mixture","mean":model["mean"],"variance":model["variance"]}
    }


def forecast_lines(model, lines, *, kind="full_gamma_poisson_exposure"):
    if model.get("schema")!=SCHEMA:
        raise ExperimentBlocked("MODEL_SCHEMA_MISMATCH")
    ans={}
    for line in lines:
        L=_num(line,"line")
        if not 0<=L<=80:
            raise ExperimentBlocked("UNSUPPORTED_SOG_LINE")
        lower=math.ceil(L)-1
        under=math.fsum(_mass(model,k,kind) for k in range(lower+1))
        push=_mass(model,int(L),kind) if float(L).is_integer() else 0.
        if under>1+1e-10 or push>1 or under+push>1+1e-10:
            raise ExperimentBlocked("DISTRIBUTION_MASS_INVALID")
        under=max(0.,min(1.,under))
        push=max(0.,min(1.-under,push))
        over=max(0.,1.-under-push)
        if abs(math.fsum((under,push,over))-1)>1e-10:
            raise ExperimentBlocked("CONTRACT_PROBABILITY_INTEGRITY_FAILURE")
        ans[format(L,"g")]={"over":over,"under":under,"push":push,
                          "over_nonpush":over/(over+under) if over+under>0 else None,
                          "kind":kind}
    return ans


def categorical_brier(probs,state):
    if state not in ("over","under","push"):
        raise ExperimentBlocked("UNSCORABLE_SETTLEMENT")
    if not isinstance(probs,dict):
        raise ExperimentBlocked("PROBABILITY_RECORD_MISSING")
    p=[_num(probs.get(k),k) for k in ("over","under","push")]
    if any(x<0 or x>1 for x in p) or abs(math.fsum(p)-1)>1e-10:
        raise ExperimentBlocked("THREE_WAY_PROBABILITY_INVALID")
    return math.fsum((x-float(name==state))**2 for x,name in zip(p,("over","under","push")))


def evaluate_paired_dates(rows):
    """Date-equal weighted, paired three-way Brier; no void/push deletion."""
    by_date=defaultdict(list)
    seen=set()
    for row in rows:
        if row.get("state") not in ("over","under","push"):
            raise ExperimentBlocked("UNSETTLED_OR_VOID_IN_PRIMARY")
        ident=row.get("contract_id")
        if not ident or ident in seen or not row.get("date") or not row.get("game_id"):
            raise ExperimentBlocked("DUPLICATE_OR_MISSING_CONTRACT")
        seen.add(ident)
        diff=categorical_brier(row["challenger"],row["state"])-categorical_brier(row["control"],row["state"])
        by_date[row["date"]].append(diff)
    means=[statistics.mean(by_date[d]) for d in sorted(by_date)]
    return {"schema":"v25_sog_paired_date_brier_v1",
            "primary_weighting":"equal_eligible_slate_dates",
            "matched_contracts":len(seen),"date_count":len(means),
            "mean_date_delta":statistics.mean(means) if means else None,
            "by_date":{d:{"n":len(by_date[d]),"mean_delta":statistics.mean(by_date[d])}
                       for d in sorted(by_date)}}


def power_null_simulation(*,dates=40,replicates=2000,seed=20261112,
                          intradate_games=6,within_game_contracts=8):
    """Illustrative null Type-I check, NOT a real-data power certificate.

    A precommitted sign-flip final test assumes symmetric date-level null
    score differences. Simulations expose that assumption; empirical checks
    of symmetry/serial dependence are still mandatory.
    """
    if not 5<=dates<=100 or not 20<=replicates<=100000:
        raise ExperimentBlocked("INVALID_POWER_SIMULATION_SIZE")
    rng=random.Random(seed)
    rejects=0
    sign_rng=random.Random(seed+1)
    for _ in range(replicates):
        ds=[]
        for _d in range(dates):
            common=rng.gauss(0,0.04)
            game_effect=[rng.gauss(0,0.035) for _ in range(intradate_games)]
            eps=[common+g+rng.gauss(0,0.07) for g in game_effect
                 for _i in range(within_game_contracts)]
            ds.append(statistics.mean(eps))
        obs=statistics.mean(ds)
        flips=2048
        count=0
        for b in range(flips):
            val=statistics.mean(v*(1 if sign_rng.getrandbits(1) else -1) for v in ds)
            if val<=obs:count+=1
        p=(count+1)/(flips+1)
        if p<=0.025:rejects+=1
    return {"simulation":"symmetric_date_null_with_game_and_date_effects",
            "dates":dates,"replicates":replicates,"seed":seed,
            "one_sided_alpha":0.025,
            "empirical_type1_rate":rejects/replicates,
            "not_a_formal_power_guarantee":True}
