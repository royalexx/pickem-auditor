"""Gate D: source-frozen sportsbook-price comparison, descriptive ONLY.

An original quote's bookmaker American price is not proof of executable odds
or a pick'em operator's paid multipliers. Postgame 1-unit returns on a tiny
counterfactual cohort are NOT economic edge, validated strategy or Tier merit.
"""
from __future__ import annotations
import math
import statistics
from collections import Counter
from .official_nba_nhl_capture import SettlementCaptureError


def _p(x):
    if isinstance(x,bool):raise SettlementCaptureError("market_probability_boolean")
    try:f=float(x)
    except (TypeError,ValueError,OverflowError) as exc:raise SettlementCaptureError("market_prob_invalid") from exc
    if not math.isfinite(f) or not 0<=f<=1:
        raise SettlementCaptureError("market_prob_out_of_range")
    return f


def decimal_price(american):
    if isinstance(american,bool):raise SettlementCaptureError("boolean_american_price")
    try:a=float(american)
    except (TypeError,ValueError,OverflowError) as exc:raise SettlementCaptureError("bad_american_price") from exc
    if not math.isfinite(a) or a==0 or (-100<a<100):
        raise SettlementCaptureError("invalid_american_market_price")
    return 1+100/abs(a) if a<0 else 1+a/100


def _avg(a):return sum(a)/len(a) if a else None


def chosen_book_edge(c,model):
    if c["models"][model]["status"]!="counterfactual_shadow":
        return {"status":"unavailable_model"}
    m=c["models"]["real_no_vig_market"]
    if m["status"]!="available" or m.get("source")!="original_pregame_two_sided_bookmaker_via_PropLine":
        raise SettlementCaptureError("unverified_original_two_sided_book")
    if int(c["line"])==float(c["line"]):
        # Bookmaker void/push terms not independently registered. The model's
        # P(push) is not a settled-offer rule and cannot certify a 1-unit ROI.
        return {"status":"unsupported_integer_line_push_payoff"}
    p=_p(c["models"][model].get("p_over_nonpush"))
    od=decimal_price(m["over_american"]);ud=decimal_price(m["under_american"])
    over_roi=p*(od-1)-(1-p)
    under_roi=(1-p)*(ud-1)-p
    if over_roi>0 and under_roi>0:
        raise SettlementCaptureError("book_two_sided_positive_edge_inconsistent")
    if over_roi<=0 and under_roi<=0:
        side=None;edge=0
    elif over_roi>under_roi:
        side="over";edge=over_roi
    else:
        side="under";edge=under_roi
    return {"status":"priced_counterfactual_research","side":side,
            "model_implied_roi_if_true":edge,
            "p_over_model":p,"book":m["book"],
            "book_decimal_over":od,"book_decimal_under":ud,
            "book_vig":1/od+1/ud-1}


def evaluate_market_research(phase1):
    if phase1.get("schema")!="v25-phase1-nhl-nba-certified-replay-v1" or (
            phase1.get("tier1_tier2_publication_allowed") is not False):
        raise SettlementCaptureError("market_research_untrusted_phase1")
    count=len(phase1.get("contracts",[]))
    if not count or phase1["prepared_attempt_count"]<2*count:
        raise SettlementCaptureError("market_research_denominator_invalid")
    rows=phase1["contracts"]
    result={}
    for model in ("naive_recent_exposure_rate","pooled_peer_shrunk_rate"):
        counter=Counter()
        picks=[];errs=[]
        bets=[]
        for c in rows:
            x=chosen_book_edge(c,model)
            counter[x["status"]]+=1
            if x["status"]!="priced_counterfactual_research":continue
            if not -1e-12<=x["book_vig"]<=.5:
                raise SettlementCaptureError("unreasonable_book_vig")
            counter["offered_with_two_sided_model_price"]+=1
            if x["side"] is None:
                counter["prospective_shadow_no_positive_edge"]+=1
                continue
            counter["counterfactual_selected_"+x["side"]]+=1
            if c["outcome"]["status"] not in ("over","under"):
                counter["shadow_selected_but_not_settled"]+=1
                continue
            y=(c["outcome"]["status"]==x["side"])
            price=x["book_decimal_over"] if x["side"]=="over" else x["book_decimal_under"]
            unit_return=(price-1) if y else -1.
            bets.append(unit_return)
            picks.append({"side":x["side"],"hit":int(y),"event":c["event_id"],
                          "return":unit_return,"sport":c["sport"],"stat":c["stat"]})
        settled=[c for c in rows if c["outcome"]["status"] in ("over","under")]
        for c in settled:
            m=_p(c["models"]["real_no_vig_market"]["p_over_nonpush"])
            p=_p(c["models"][model].get("p_over_nonpush"))
            y=int(c["outcome"]["status"]=="over")
            errs.append((p-y)**2-(m-y)**2)
        result[model]={
            "selection_counts":dict(counter),
            "settled_eligible_contracts":len(settled),
            "paired_brier_difference_vs_market":_avg(errs),
            "positive_difference_worse_than_market":True,
            "counterfactual_selected_settled":len(picks),
            "postgame_one_unit_aggregate_return_research_only":sum(bets),
            "postgame_one_unit_mean_return_research_only":_avg(bets),
            "counterfactual_hit_rate":_avg([p["hit"] for p in picks]),
            "game_clusters_selected_settled":len({p["event"] for p in picks}),
            "returns_not_executable_and_never_model_promotion":True,
        }
    return {
      "schema":"phase15_gateD_original_bookmaker_price_research_v1",
      "original_contracts":count,
      "original_forecast_side_denominator":phase1["prepared_attempt_count"],
      "settled_contracts":sum(c["outcome"]["status"] in ("over","under") for c in rows),
      "real_pregame_original_two_sided_book_quotes":count,
      "market_reference_type":"source_archived_bookmaker_not_pickem",
      "pickem_operator_payout_multiplier_proven":False,
      "site_eligibility_bet_executability_verified":False,
      "matched_models":result,
      "economic_edge_gate":"BLOCKED_NO_OPERATOR_PAYOFF_AND_INDEPENDENT_SAMPLE_POWER",
      "production_model_promotion_allowed":False,
      "tier1_tier2_publication_allowed":False,
    }
