"""Source-quality evidence ceiling for verified Tier decisions.

A count of citations or named events is never evidence of incremental value.
Machine workload proof is corroboration of Engine B's *own* observations, not
an independent cause. Human/agent causal evidence must be quantified, recent,
counterchecked, and independently sourced before claiming a higher ceiling.
No probabilities or existing numerical thresholds are changed.
"""
from __future__ import annotations
from datetime import datetime, timezone
from urllib.parse import urlparse
from math import isfinite
from research_packet import _validate_fact, _is_primary_domain
from effect_ledger import canonical

VERSION = "mechanism-evidence-v1"
TIERS = ("Watchlist", "Tier 3", "Tier 2", "Tier 1")
OVERLAP_CHANNELS = frozenset(("workload", "role", "pace", "weather"))
VALID_TYPES = frozenset(("workload", "role", "pace", "weather", "scheme"))

def _num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v):
        return None
    return float(v)

def _domain(url):
    host = urlparse(str(url or "")).hostname or ""
    if host.endswith(".nhl.com") or host == "nhl.com": return "nhl.com"
    if host.endswith(".nba.com") or host == "nba.com": return "nba.com"
    if host.endswith(".nfl.com") or host == "nfl.com": return "nfl.com"
    if host.endswith(".espn.com") or host == "espn.com": return "espn.com"
    return host.lower()

def _fact_proven(fact, now, *, need_quote=True):
    if not isinstance(fact, dict):
        return False
    errors = []
    vf = _validate_fact("mechanism", fact, errors, require_fresh=True, now=now)
    return (not errors and vf is not None and vf.confidence == "confirmed"
            and _is_primary_domain(vf.source_url)
            and (not need_quote or bool(str(fact.get("quote") or "").strip())))

def _human_chain(mech, item, now):
    """Full causal record, not a source count. A missing part means no promotion."""
    output = {"event_id": mech.get("event_id"), "type": mech.get("type"),
              "status": "unsupported", "reasons": []}
    reasons = output["reasons"]
    try:
        event = canonical(mech.get("event_id"))
    except (ValueError, TypeError):
        reasons.append("NO_STABLE_CAUSAL_EVENT")
        return output
    if (mech.get("type") not in VALID_TYPES or
            mech.get("supports_side") != item.get("side")):
        reasons.append("WRONG_DIRECTION_OR_UNSUPPORTED_CAUSAL_PATHWAY")
    sources = mech.get("sources") or []
    owners = {_domain(f.get("source_url")) for f in sources
              if _fact_proven(f, now)}
    if len(owners) < 2:
        reasons.append("NEEDS_TWO_INDEPENDENT_PRIMARY_SOURCE_OWNERS")
    facts = mech.get("causal_validation")
    if not isinstance(facts, dict) or facts.get("target_stat") != item.get("stat"):
        reasons.append("STAT_SPECIFIC_CAUSAL_CHAIN_MISSING")
        facts = {}
    b, a = _num(facts.get("before")), _num(facts.get("after"))
    bn, an = facts.get("before_n"), facts.get("after_n")
    if (b is None or a is None or b <= 0 or
            isinstance(bn,bool) or isinstance(an,bool) or
            not isinstance(bn,int) or not isinstance(an,int) or
            bn < 5 or an < 5 or not facts.get("metric") or
            not facts.get("units")):
        reasons.append("MEASURABLE_COMPARABLE_CAUSAL_SAMPLES_MISSING")
    else:
        change = (a-b)/b
        if abs(change) < .10:
            reasons.append("OBSERVED_CHANGE_NOT_MATERIAL")
        if ((item.get("side") == "over" and change <= 0)
                or (item.get("side") == "under" and change >= 0)):
            reasons.append("OBSERVED_EFFECT_OPPOSES_PICK")
        output["effect_ratio"] = round(change, 6)
        output["sample_sizes"] = {"before":bn, "after":an}
    counter = facts.get("counterevidence")
    if not _fact_proven(counter, now):
        reasons.append("COUNTEREVIDENCE_NOT_INDEPENDENTLY_READ")
    # Distinct source *owners* are not evidence of different causal events.
    # Require explicit same-event linkage, and model-incremental auditing.
    if facts.get("event_id") != mech.get("event_id"):
        reasons.append("CAUSAL_EVENT_IDENTITY_MISMATCH")
    if mech.get("type") in OVERLAP_CHANNELS:
        reasons.append("EMBEDDED_OR_UNRESOLVED_MODEL_INPUT_OVERLAP")
    if mech.get("type") == "scheme":
        # A's documented opponent factor incorporates broad opponent scheme;
        # no machine-readable independently charted player-specific effect
        # presently proves separation from that factor.
        reasons.append("SCHEME_EFFECT_INDEPENDENCE_NOT_ESTABLISHED")
    if not reasons:
        output.update(status="independent_confirmed", source_owners=sorted(owners),
                      canonical_event_id=event)
    return output

def assess(packet, item, *, now=None, review_type=None, machine_provenance=None,
           human_reviewed=False):
    """Return a deterministic *tier ceiling*, not a probability or uplift.

    No event count, arbitrary headline or unvalidated URL promotes a Tier.
    The strict machine route can substantiate Tier 3 when paired with complete
    model/market gates; it cannot independently corroborate its own Engine B.
    A future certified model-incremental causal channel can qualify higher.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None: raise ValueError("mechanism audit clock must be aware")
    events = (packet.get("mechanisms") or {}).get(item.get("candidate_id")) or []
    result = {"version":VERSION, "tier_ceiling":"Watchlist",
              "quality":"insufficient", "machine_overlap_detected":False,
              "events_assessed":len(events), "evaluations":[],
              "no_probability_adjustment":True,
              "legacy_count_not_authoritative":True}
    if review_type == "structured_machine_verification":
        proof = machine_provenance or {}
        event = proof.get("validated_mechanism")
        same = [m for m in events if isinstance(m,dict)
                and m.get("event_id") == event and m.get("type") == "workload"
                and m.get("supports_side") == item.get("side")]
        if (proof.get("independent_live_refetch") is True and
                proof.get("source_read_by_human") is False and
                isinstance(proof.get("source_payload_sha256"),str) and
                len(proof["source_payload_sha256"]) == 64 and
                proof.get("shared_collector_games",0) >= 3 and
                proof.get("supporting_game_count",0) >= 1 and
                proof.get("opposing_game_count",0) >= 1 and len(same) == 1 and
                any(_fact_proven(s,now,need_quote=False) for s in same[0].get("sources") or [])):
            result.update(tier_ceiling="Tier 3",quality="source_correlated_model_overlap",
                          machine_overlap_detected=True)
            result["evaluations"]=[{"event_id":event,
                "status":"verified_but_embedded_in_engine_b",
                "reasons":["WORKLOAD_ALREADY_USED_IN_HISTORICAL_ENGINE_B"],
                "source":proof.get("source"),
                "history_sha256":proof["source_payload_sha256"]}]
        else:
            result["evaluations"]=[{"status":"insufficient_machine_provenance",
                                   "reasons":["REPLAYED_LIVE_SOURCE_PROOF_REQUIRED"]}]
        return result
    if review_type != "human_attestation" or not human_reviewed:
        return result
    result["evaluations"]=[_human_chain(m,item,now) for m in events
                           if isinstance(m,dict)]
    independent = [x for x in result["evaluations"]
                   if x.get("status") == "independent_confirmed"]
    # Not treating the number of statements, web pages, or records as
    # qualitative strength. No fully model-incremental causal certificate
    # currently exists, so this audit conservatively caps human research at
    # Watchlist until audited causal separation is implemented.
    result["quality"] = ("model_incrementality_not_certified" if independent
                         else "insufficient")
    return result
