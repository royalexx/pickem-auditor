"""Low-cost, strictly prospective NHL SOG NB2 SHADOW (not a promotion).

Single precommitted mechanism: replace the *same* pregame pooled Poisson mean
with a fixed-shape negative-binomial likelihood, without changing opportunity
or fitting a distribution to the evaluation slate. November 10 evidence is
hypothesis-generating and must never be called an unseen test.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path

from .phase15_nhl_roster import membership_status,RosterEvidenceError,utc,digest

SCHEMA="v25_nhl_sog_nb2_fixed_shape_prospective_shadow_v1"
STUDY="EXP_NHL_SOG_P15_RATE_DISPERSION_NEXT_PROSPECTIVE"
FIXED_SHAPE=4.0


def _positive(value,name,*,allow_zero=False):
    if isinstance(value,bool):
        raise ValueError(name+"_bool")
    try:x=float(value)
    except (TypeError,ValueError,OverflowError) as exc:
        raise ValueError(name+"_not_finite_number") from exc
    if not math.isfinite(x) or (x<0 if allow_zero else x<=0):
        raise ValueError(name+"_not_positive")
    return x


def nb2_sog_probabilities(mean,line,*,shape=FIXED_SHAPE):
    mu=_positive(mean,"count_mean",allow_zero=True)
    r=_positive(shape,"shape")
    threshold=_positive(line,"line",allow_zero=True)
    if threshold>80:
        raise ValueError("unsupported_sog_offer_line")
    cutoff=math.floor(threshold)
    masses=[]
    for k in range(cutoff+1):
        if mu==0:
            value=1.0 if k==0 else 0.0
        else:
            logval=(math.lgamma(r+k)-math.lgamma(r)-math.lgamma(k+1)
                    +r*math.log(r/(r+mu))+k*math.log(mu/(r+mu)))
            value=math.exp(logval)
        masses.append(value)
    cdf=min(1.0,max(0.0,math.fsum(masses)))
    push=masses[cutoff] if threshold==cutoff else 0.0
    under=max(0.0,cdf-push)
    over=max(0.0,1.0-cdf)
    mass=over+under+push
    if not math.isfinite(mass) or abs(mass-1)>1e-9:
        raise ValueError("nb2_distribution_mass_not_reconciled")
    if 1-push<1e-12:
        return {"mean":mu,"shape":r,"variance":mu+mu*mu/r,
                "q_over":over,"q_under":under,"q_push":push,
                "p_over_nonpush":None,"model_kind":"nb2_gamma_poisson_count_v1"}
    return {"mean":mu,"shape":r,"variance":mu+mu*mu/r,
            "q_over":over,"q_under":under,"q_push":push,
            "p_over_nonpush":over/(1-push),
            "model_kind":"nb2_gamma_poisson_count_v1"}


def build_prospective_shadow(*,phase1,phase1_bytes_sha256,roster_manifest,
                             roster_root,model_revision,now,experiment_spec):
    if phase1.get("schema")!="v25-phase1-nhl-nba-certified-replay-v1":
        raise ValueError("shadow_input_must_be_strict_original_phase1")
    if phase1.get("model_promotion_authorized") is not False or (
            phase1.get("tier1_tier2_publication_allowed") is not False):
        raise ValueError("shadow_untrusted_source_promotion_flags")
    if (not isinstance(phase1_bytes_sha256,str) or
            len(phase1_bytes_sha256)!=64):
        raise ValueError("missing_original_phase1_input_digest")
    if roster_manifest.get("schema")!="phase15_nhl_pregame_roster_capture_v1":
        raise ValueError("shadow_independent_roster_capture_required")
    if roster_manifest.get("source_phase1_sha256")!=phase1_bytes_sha256:
        raise ValueError("roster_receipts_not_for_exact_phase1_report")
    if (experiment_spec.get("experiment_id")!=STUDY or
            experiment_spec.get("schema")!="v25_locked_shadow_prospective_experiment_v1" or
            experiment_spec.get("research_fixed_nb2_shape")!=FIXED_SHAPE or
            experiment_spec.get("tier1_tier2_release_allowed") is not False or
            experiment_spec.get("model_promotion_allowed") is not False):
        raise ValueError("fixed_shape_and_anti_promotion_prereg_required")
    generated_at=now.astimezone(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("naive_generation_clock_forbidden")
    if phase1.get("input_immutable_bundle_sha256") is None:
        raise ValueError("original_bundle_digest_missing")
    accepted=[]
    attempt_ledger=[]
    status_counts=Counter()
    contracts=[r for r in phase1["contracts"] if r["sport"]=="NHL"]
    if len(contracts)!=phase1["by_sport"].get("NHL"):
        raise ValueError("original_NHL_contract_denominator_mismatch")
    seen=set()
    for row in contracts:
        ident=str(row["contract_id"])
        if ident in seen:raise ValueError("duplicate_original_NHL_contract")
        seen.add(ident)
        result={"contract_id":ident,"source_original_event_id":row["event_id"],
                "player_id":str(row["player_id"]),"team":row["team_id"],
                "opponent":row["opponent_id"],"line":row["line"],
                "stat":row["stat"],"sport":"NHL","period":row["period"]}
        reason=None
        try:
            if row["stat"]!="shots on goal" or row["period"]!="full":
                reason="not_NHL_SOG_full_game"
            elif row["outcome"].get("status")!="pending_official_settlement":
                reason="already_settled_or_postgame_input_cannot_be_retroforecast"
            elif utc(row["event_start"])<=generated_at:
                reason="event_already_started_no_backdating"
            elif utc(row["input_freeze_at"])>generated_at:
                reason="freeze_timestamp_after_current_run"
            else:
                data=row["models"]["pooled_peer_shrunk_rate"]
                book=row["models"]["real_no_vig_market"]
                if data.get("status")!="counterfactual_shadow":
                    reason="missing_eligible_original_pregame_rate"
                elif book.get("status")!="available":
                    reason="original_two_sided_market_unavailable"
                else:
                    check=membership_status(row["player_id"],row["team_id"],
                        row["opponent_id"],receipts=roster_manifest.get("roster_receipts"),
                        source_root=roster_root,
                        forecast_at=generated_at.isoformat(),event_start=row["event_start"])
                    if check["status"]!="pre_event_team_membership_confirmed":
                        reason=check["status"]
                    else:
                        dist=data.get("distribution") or {}
                        lam=_positive(dist.get("rate"),"original_poisson_mean",allow_zero=True)
                        likelihood=nb2_sog_probabilities(lam,row["line"])
                        if likelihood["p_over_nonpush"] is None:
                            reason="no_nonpush_probability"
                        else:
                            accepted.append({
                               **result,
                               "original_input_freeze_at":row["input_freeze_at"],
                               "original_event_start":row["event_start"],
                               "source_original_bundle_sha256":phase1["input_immutable_bundle_sha256"],
                               "source_phase1_scored_sha256":phase1_bytes_sha256,
                               "source_contract_id":ident,
                               "snapshot_captured_at":generated_at.isoformat().replace("+00:00","Z"),
                               "new_model_code_revision":model_revision,
                               "experiment_id":STUDY,
                               "model":likelihood,
                               "original_same_mean_poisson_p_over_nonpush":data["p_over_nonpush"],
                               "original_same_contract_no_vig_market_p_over_nonpush":book["p_over_nonpush"],
                               "membership_confirmation_only":True,
                               "lineup_and_participation_forecast_verified":False,
                               "status":"research_shadow",
                               "allowed_as_production_selection":False,
                               "preregistered_fixed_shape":FIXED_SHAPE,
                            })
        except (RosterEvidenceError,ValueError,KeyError,TypeError) as exc:
            reason="source_or_math_unverifiable:"+str(exc)[:110]
        result["status"]="shadow_created" if reason is None else "excluded"
        if reason:result["reason"]=reason
        status_counts[reason or "shadow_created"]+=1
        attempt_ledger.append(result)
    return {
       "schema":SCHEMA,"experiment_id":STUDY,
       "experiment_fixed_shape":FIXED_SHAPE,
       "code_revision":model_revision,
       "created_at_utc":generated_at.isoformat().replace("+00:00","Z"),
       "original_phase1_sha256":phase1_bytes_sha256,
       "original_bundle_sha256":phase1["input_immutable_bundle_sha256"],
       "original_prepared_attempt_sides":phase1["prepared_attempt_count"],
       "original_all_sports_paired_contracts":phase1["retained_paired_contracts"],
       "NHL_original_contracts":len(contracts),
       "NHL_shadow_accepted":len(accepted),
       "NHL_shadow_attempt_status":dict(sorted(status_counts.items())),
       "roster_evidence_member_not_starter":True,
       "nov10_discovery_games_not_scored_as_unseen":True,
       "experiment_frozen_before_sports_event":True,
       "model_promotion_allowed":False,
       "tier1_tier2_publication_allowed":False,
       "NUTS_or_heavy_training_used":False,
       "original_frozen_models_unchanged":True,
       "forecasts":accepted,
       "complete_candidate_attempt_ledger":attempt_ledger,
    }
