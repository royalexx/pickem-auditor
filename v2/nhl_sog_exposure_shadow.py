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
    return {**d,"source_sha256":digest,"source_received_at":receipt["received_at"],
            "source_archive_path":rel,"source_url":url}


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
      "source_manifest":[
          {"archive_path":o["source_archive_path"],
           "content_sha256":o["source_sha256"],
           "received_at":o["source_received_at"],"source_uri":o["source_url"],
           "player_id":o["player_id"],"event_id":o["event_id"]}
          for o in own+peers],
      "fit_data_cutoff_at":max(o["source_received_at"] for o in own+peers),
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


def forecast_for_approved_quote(model,quote,*,source_root,roster_root,roster_receipts,
                                code_commit,run_id,forecast_id,forecast_at,
                                decision_cutoff_at):
    """Strict shadow-only FixedLine adapter with separate full-distribution hash.

    A source-hashed GENERATIVE model supports many alternate quotes. Each
    immutable ForecastSnapshot uses FixedLineDistribution only at its exact
    offer, never pretending a fixed-line object is the full SOG likelihood.
    """
    from .contracts import (MarketQuote,ForecastSnapshot,SourceReceipt,
                            FixedLineDistribution)
    from .phase15_nhl_roster import membership_status
    if not isinstance(quote,MarketQuote) or not quote.accepted or (
            quote.quote_kind!="real" or quote.sport!="NHL" or
            quote.stat_key!="shots on goal" or quote.period!="full"):
        raise ExperimentBlocked("UNMATCHED_OR_SYNTHETIC_QUOTE")
    if (quote.player_id!=model.get("player_id") or
            _utc(model["input_freeze_at"],"input_freeze_at")>
            _utc(forecast_at,"forecast_at") or
            _utc(model["event_start_at"],"event_start")!=
            _utc(quote.event_start_at,"quote_event_start")):
        raise ExperimentBlocked("MODEL_QUOTE_IDENTITY_OR_TIME_MISMATCH")
    path=quote.quote_archive_path
    if not isinstance(path,str) or not path or path.startswith("/") or (
            "\\" in path or ".." in Path(path).parts):
        raise ExperimentBlocked("ORIGINAL_QUOTE_ARCHIVE_MISSING")
    root=Path(source_root).resolve()
    file=(root/path).resolve()
    if not file.is_relative_to(root) or not file.is_file() or (
            hashlib.sha256(file.read_bytes()).hexdigest()!=quote.quote_receipt_sha256):
        raise ExperimentBlocked("ORIGINAL_QUOTE_HASH_MISMATCH")
    membership=membership_status(quote.player_id,quote.team_id,quote.opponent_id,
        receipts=roster_receipts,source_root=roster_root,
        forecast_at=forecast_at,event_start=quote.event_start_at)
    if membership.get("status")!="pre_event_team_membership_confirmed":
        raise ExperimentBlocked("NHL_ROSTER_MEMBERSHIP_UNVERIFIED")
    # The official roster differentiates F and D; verify the group, not just
    # general 'skater' membership. Opponent roster also guards traded players.
    team_roster=roster_receipts.get(quote.team_id)
    team_bytes=(Path(roster_root)/team_roster["raw_archive_path"]).read_bytes()
    roster=json.loads(team_bytes)
    role="F" if any(str(x.get("id"))==quote.player_id for x in roster["forwards"]) else (
         "D" if any(str(x.get("id"))==quote.player_id for x in roster["defensemen"]) else None)
    if role!=model["position_group"]:
        raise ExperimentBlocked("CURRENT_OFFICIAL_POSITION_MISMATCH")
    sources=[]
    seen=set()
    for record in model["source_manifest"]:
        ident=record["content_sha256"]
        if ident in seen:continue
        seen.add(ident)
        sources.append(SourceReceipt(
            source_id="sog_observation_"+ident[:24],
            first_available_at=record["received_at"],
            retrieved_at=record["received_at"],
            content_sha256=ident,
            source_uri=None,archive_path=record["archive_path"],
            source_kind="archive_possession"))
    p=forecast_lines(model,[quote.line])[format(float(quote.line),"g")]
    dist=FixedLineDistribution(float(quote.line),p["over"],p["under"],p["push"])
    snap=ForecastSnapshot(
        forecast_id=forecast_id,run_id=run_id,
        model_id=model["model_id"],model_version=SCHEMA,
        quote_id=quote.quote_id,contract_id=quote.contract_id,
        event_id=quote.event_id,sport=quote.sport,league=quote.league,
        season=quote.season,team_id=quote.team_id,opponent_id=quote.opponent_id,
        player_id=quote.player_id,stat_key=quote.stat_key,period=quote.period,
        line=quote.line,quote_receipt_sha256=quote.quote_receipt_sha256,
        forecast_at=forecast_at,input_freeze_at=model["input_freeze_at"],
        decision_cutoff_at=decision_cutoff_at,
        model_training_cutoff_at=model["fit_data_cutoff_at"],
        model_artifact_sha256=stable_hash(model),code_commit=code_commit,
        sources=tuple(sources),distribution=dist)
    snap.validate_against(quote)
    return {"status":"RESEARCH_SHADOW_ONLY",
            "snapshot":snap.to_record(),
            "fixed_line_is_not_full_distribution":True,
            "full_distribution_sha256":stable_hash(model),
            "full_distribution_artifact":model,
            "model_promotion_allowed":False,"tier_publication_allowed":False}


def count_log_loss(model,observed_sog,kind="full_gamma_poisson_exposure"):
    y=_num(observed_sog,"observed_sog")
    if y<0 or not y.is_integer():raise ExperimentBlocked("INVALID_SETTLEMENT_COUNT")
    mass=_mass(model,int(y),kind)
    return -math.log(max(mass,1e-300))


def count_crps(model,observed_sog,kind="full_gamma_poisson_exposure",
               tolerance=1e-12,max_terms=2500):
    """Discrete CRPS via sum_k [F(k)-1{y<=k}]^2; fail on material tail."""
    y=_num(observed_sog,"observed_sog")
    if y<0 or not y.is_integer():raise ExperimentBlocked("INVALID_SETTLEMENT_COUNT")
    acc=0.
    cumulative=0.
    for k in range(max_terms):
        mass=_mass(model,k,kind)
        cumulative+=mass
        acc+=(cumulative-float(y<=k))**2
        if cumulative>=1-tolerance and k>=y:
            return acc
    raise ExperimentBlocked("TAIL_TRUNCATION_NOT_CERTIFIED")


def fixed_horizon_feasibility_grid(*,replicates=3000,seed=20261112):
    """40-date simulated operating characteristics, not estimated real power.

    One-sided Student-t_39 critical value 2.02269092 at alpha .025.
    Scenarios explicitly vary date-to-date SD and AR(1) correlation. False
    rejection under positive serial dependence is an integrity warning, not a
    reason to cherry-pick a model on final outcomes.
    """
    if not 100<=replicates<=50000:
        raise ExperimentBlocked("FEASIBILITY_REPLICATES_OUT_OF_RANGE")
    rng=random.Random(seed)
    out=[]
    for sd in (.01,.02,.04,.08):
        for rho in (0.,.3,.6):
            counts={"null_rejections":0,"effect_rejections":0}
            for effect,key in ((0.,"null_rejections"),(-.002,"effect_rejections")):
                rejected=0
                for _ in range(replicates):
                    z=0.
                    differences=[]
                    for _date in range(40):
                        z=rho*z+math.sqrt(1-rho*rho)*rng.gauss(0.,sd)
                        differences.append(effect+z)
                    std=statistics.stdev(differences)
                    t=statistics.mean(differences)/(std/math.sqrt(40))
                    rejected+=int(t< -2.02269092)
                counts[key]=rejected
            out.append({"date_sd_assumed":sd,"ar1_rho_assumed":rho,
                "null_type1_rate":counts["null_rejections"]/replicates,
                "effect_minus_0_002_power":counts["effect_rejections"]/replicates})
    return {"experiment_id":EXPERIMENT,"schema":"sog_fixed_40_date_feasibility_v1",
            "seed":seed,"replicates":replicates,"eligible_dates":40,
            "effect_is_hypothetical_not_estimated":-0.002,
            "critical_t39":2.02269092,"one_sided_alpha":.025,
            "results":out,
            "inference_status":"SIMULATION_ONLY_NOT_PROSPECTIVE_CERTIFICATION"}
