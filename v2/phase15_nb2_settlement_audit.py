"""Read-only, official-final-only evaluation of *previously frozen* NHL NB2 shadows.

Strictly research: no refitting/recensoring, no selection/re-ranking after
outcomes, no artificial pushes, no production/Tier promotion.
"""
from __future__ import annotations
from collections import Counter,defaultdict
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import hashlib,json,math

from .official_nba_nhl_capture import nhl_stat_rows,SettlementCaptureError
from .phase15_nb2_shadow import SCHEMA as SHADOW_SCHEMA, nb2_sog_probabilities
from .phase15_nhl_roster import utc

SCHEMA="phase15_nhl_sog_nb2_future_original_contract_official_evaluation_v1"


def _sha(raw):return hashlib.sha256(raw).hexdigest()


def _prob(x,label):
    if isinstance(x,bool):raise SettlementCaptureError("invalid_"+label)
    try:f=float(x)
    except (TypeError,ValueError,OverflowError) as exc:
        raise SettlementCaptureError("invalid_"+label) from exc
    if not math.isfinite(f) or not 0<=f<=1:
        raise SettlementCaptureError("not_probability_"+label)
    return f


def _metric(p,y):
    return {"brier":(p-y)**2,
            "log_loss":-(y*math.log(max(1e-12,p))+
                         (1-y)*math.log(max(1e-12,1-p)))}


def score_frozen_shadow(*,original_phase1,phase1_bytes_sha256,shadow,
                        independent_settlements,official_source_root,
                        evidence_frozen_proof=None):
    if (original_phase1.get("schema")!="v25-phase1-nhl-nba-certified-replay-v1"
            or original_phase1.get("model_promotion_authorized") is not False):
        raise SettlementCaptureError("incorrect_original_strict_phase1")
    if shadow.get("schema")!=SHADOW_SCHEMA:
        raise SettlementCaptureError("not_exact_original_shadow_schema")
    if (shadow.get("original_phase1_sha256")!=phase1_bytes_sha256 or
            shadow.get("original_bundle_sha256")!=original_phase1.get(
                "input_immutable_bundle_sha256")):
        raise SettlementCaptureError("frozen_original_phase1_sha_mismatch")
    if (shadow.get("tier1_tier2_publication_allowed") is not False or
            shadow.get("model_promotion_allowed") is not False):
        raise SettlementCaptureError("unauthorized_shadow_release_state")
    if shadow.get("experiment_fixed_shape")!=4.0:
        raise SettlementCaptureError("wrong_registered_shape")
    ledger=shadow.get("complete_candidate_attempt_ledger")
    source=[c for c in original_phase1["contracts"] if c["sport"]=="NHL"]
    if (not isinstance(ledger,list) or
            len(ledger)!=len(source) or
            len(source)!=shadow.get("NHL_original_contracts") or
            len(shadow.get("forecasts",[]))!=shadow.get("NHL_shadow_accepted")):
        raise SettlementCaptureError("missing_original_candidate_or_forecast_denominator")
    original={}
    for c in source:
        key=c["contract_id"]
        if key in original:raise SettlementCaptureError("duplicate_source_contract_id")
        original[key]=c
    seen=set()
    admitted=set()
    for item in ledger:
        key=item["contract_id"]
        if key not in original or key in seen:
            raise SettlementCaptureError("unknown_or_duplicate_attempt_contract")
        seen.add(key)
        if item["status"]=="shadow_created":admitted.add(key)
        elif item["status"]!="excluded":
            raise SettlementCaptureError("invalid_original_attempt_status")
    if seen!=set(original):
        raise SettlementCaptureError("original_NHL_attempt_ledger_incomplete")
    forecasts={}
    for f in shadow["forecasts"]:
        key=f["contract_id"]
        if key not in admitted or key in forecasts:
            raise SettlementCaptureError("duplicate_or_unrecognized_shadow_forecast")
        c=original[key]
        if any((str(f[k])!=str(c[ck])) for k,ck in (
                ("source_original_event_id","event_id"),
                ("player_id","player_id"),("team","team_id"),
                ("opponent","opponent_id"),("stat","stat"),
                ("period","period"),("line","line"))):
            raise SettlementCaptureError("shadow_contract_identity_or_line_changed")
        snap=utc(f["snapshot_captured_at"])
        if snap>=utc(c["event_start"]) or utc(c["input_freeze_at"])>snap:
            raise SettlementCaptureError("shadow_not_genuinely_pregame")
        if f.get("status")!="research_shadow" or f.get("allowed_as_production_selection") is not False:
            raise SettlementCaptureError("shadow_has_production_inference_privilege")
        model=f["model"]
        rate=float(c["models"]["pooled_peer_shrunk_rate"]["distribution"]["rate"])
        expected=nb2_sog_probabilities(rate,c["line"],shape=4)
        for name in ("q_over","q_under","q_push","p_over_nonpush","mean","shape","variance"):
            if model.get(name) is None or not math.isclose(
                float(model[name]),float(expected[name]),abs_tol=1e-10,rel_tol=1e-10):
                raise SettlementCaptureError("shadow_distribution_modified_after_freeze:"+name)
        if not math.isclose(f["original_same_mean_poisson_p_over_nonpush"],
                            c["models"]["pooled_peer_shrunk_rate"]["p_over_nonpush"],
                            rel_tol=1e-10,abs_tol=1e-10):
            raise SettlementCaptureError("original_control_probability_modified")
        if not math.isclose(f["original_same_contract_no_vig_market_p_over_nonpush"],
                            c["models"]["real_no_vig_market"]["p_over_nonpush"],
                            rel_tol=1e-10,abs_tol=1e-10):
            raise SettlementCaptureError("original_market_probability_modified")
        forecasts[key]=f
    if set(forecasts)!=admitted:
        raise SettlementCaptureError("shadow_attempt_created_forecast_set_disagrees")
    sourcekey={(c["sport"],str(c["event_id"]),str(c["player_id"]),c["stat"]):c
               for c in source}
    if len(sourcekey)!=len(source):
        raise SettlementCaptureError("multiple_lines_one_player_stat_needs_unique_scoring")
    matched={}
    officialroot=Path(official_source_root).resolve()
    for s in independent_settlements:
        key=(s.get("sport"),str(s.get("event_id")),str(s.get("player_id")),s.get("stat"))
        if key not in sourcekey or key in matched or s.get("status")!="settled":
            raise SettlementCaptureError("official_unmatched_duplicate_or_not_settled")
        c=sourcekey[key]
        if utc(s.get("retrieved_at"))<=utc(c["event_start"]):
            raise SettlementCaptureError("official_outcome_known_before_event")
        rel=s.get("source_archive_path")
        if (not isinstance(rel,str) or not rel or rel.startswith("/") or
                "\\" in rel or ".." in Path(rel).parts):
            raise SettlementCaptureError("unsafe_official_source_file")
        file=(officialroot/rel).resolve()
        if not file.is_relative_to(officialroot) or not file.is_file():
            raise SettlementCaptureError("missing_exact_official_source_bytes")
        raw=file.read_bytes()
        if _sha(raw)!=s.get("source_sha256"):
            raise SettlementCaptureError("official_source_sha_tampered")
        doc=json.loads(raw)
        if (doc.get("gameState") not in ("FINAL","OFF") or
                str(doc.get("id"))!=str(s.get("official_game_id"))):
            raise SettlementCaptureError("source_wrong_game_or_not_final")
        if (s.get("source_url")!=
            "https://api-web.nhle.com/v1/gamecenter/"+str(s["official_game_id"])+"/boxscore"):
            raise SettlementCaptureError("incorrect_NHL_official_source_url")
        rows=nhl_stat_rows(doc,expected_teams={c["team_id"],c["opponent_id"]})
        p=rows.get(str(c["player_id"]))
        if not p or p["team"]!=c["team_id"] or p["shots on goal"]!=s["actual"]:
            raise SettlementCaptureError("settlement_not_reproducible_from_official_boxscore")
        matched[key]=s
    entries=[]
    counts=Counter()
    stats=defaultdict(list)
    for key,f in sorted(forecasts.items()):
        c=original[key]
        source_id=(c["sport"],str(c["event_id"]),str(c["player_id"]),c["stat"])
        s=matched.get(source_id)
        if s is None:
            counts["unsettled_source_or_dnp"]+=1
            entries.append({"contract_id":key,"status":"pending_official_source_or_dnp",
                            "no_imputed_result":True})
            continue
        actual=float(s["actual"])
        if actual==float(c["line"]):
            counts["push_excluded_from_binary"]+=1
            entries.append({"contract_id":key,"status":"push","actual":actual,
                            "official_sha256":s["source_sha256"]})
            continue
        y=int(actual>float(c["line"]))
        probs={
           "fixed_NB2":_prob(f["model"]["p_over_nonpush"],"fixedNB2"),
           "original_pooled_Poisson":_prob(
                f["original_same_mean_poisson_p_over_nonpush"],"originalPoisson"),
           "original_real_no_vig_market":_prob(
                f["original_same_contract_no_vig_market_p_over_nonpush"],"realMarket"),
        }
        row={"contract_id":key,"status":"source_verified_settled_nonpush",
             "sport":c["sport"],"original_event_id":c["event_id"],
             "player_id":c["player_id"],"game_date":utc(c["event_start"]).astimezone(ZoneInfo("America/Toronto")).date().isoformat(),
             "line":c["line"],"observed_over":y,"actual":actual,
             "official_source_sha256":s["source_sha256"],
             "models":{k:{"p_over_nonpush":p,**_metric(p,y)}
                       for k,p in probs.items()}}
        for model,p in probs.items():stats[model].append((row["original_event_id"],row["game_date"],p,y))
        entries.append(row)
        counts["over" if y else "under"]+=1
    summaries={}
    for model,obs in stats.items():
        n=len(obs)
        summaries[model]={"n":n,"brier":sum((p-y)**2 for ev,dt,p,y in obs)/n,
                          "log_loss":sum(_metric(p,y)["log_loss"] for ev,dt,p,y in obs)/n,
                          "mean_p_over":sum(p for ev,dt,p,y in obs)/n,
                          "observed_over_rate":sum(y for ev,dt,p,y in obs)/n,
                          "n_game_clusters":len({ev for ev,dt,p,y in obs}),
                          "n_calendar_dates":len({dt for ev,dt,p,y in obs})}
    for model in ("fixed_NB2","original_pooled_Poisson"):
        if model in summaries:
            summaries[model]["brier_minus_market"]=summaries[model]["brier"]-summaries[
                "original_real_no_vig_market"]["brier"]
    verified_proof=(isinstance(evidence_frozen_proof,dict) and
                     evidence_frozen_proof.get("status")=="independently_frozen_before_event" and
                     bool(evidence_frozen_proof.get("github_commit_sha")) and
                     bool(evidence_frozen_proof.get("evidence_zip_sha256")))
    return {
       "schema":SCHEMA,"research_only":True,
       "original_source_contracts":len(source),
       "original_shadow_created":len(forecasts),
       "original_excluded":len(source)-len(forecasts),
       "official_settlement_rows_received":len(matched),
       "outcomes":dict(counts),
       "shadow_source_git_archive_attestation_provided":verified_proof,
       "attestation_requires_independent_verification_not_just_self_report":True,
       "distribution_assessed_after_original_freeze":True,
       "matched_scores":summaries,
       "contract_ledger":entries,
       "statistical_release":"BLOCKED_REQUIRE_MULTIPLE_INDEPENDENT_FUTURE_DATES",
       "model_promotion_allowed":False,
       "tier1_tier2_publication_allowed":False,
       "training_updated":False,
    }
