"""Non-promoting compatibility adapters for pre-existing V2 and NBA/NHL outputs.

Adapters preserve original identity, source and offer semantics. No adapter
creates a genuine historical pregame timestamp, model SHA or participation
probability from retrospective results.
"""
from __future__ import annotations
from dataclasses import asdict, is_dataclass
from .contracts import AdmissionError, record, sha256

def _fields(old):
    if is_dataclass(old):
        return asdict(old)
    if isinstance(old,dict):
        return dict(old)
    raise AdmissionError("UNSUPPORTED_LEGACY_RECORD")

def legacy_source_receipt(old, *, verified_publisher_availability=False):
    """Mapping from v2.contracts.SourceReceipt; possession is conservative."""
    x=_fields(old)
    for key in ("source_id","first_available_at","retrieved_at","content_sha256",
                "archive_path","source_kind"):
        if key not in x:
            raise AdmissionError("LEGACY_SOURCE_FIELD_MISSING:"+key)
    publisher=(verified_publisher_availability and
               x["source_kind"]=="provider_publication")
    return record("SourceReceipt",
        receipt_id="legacy-source:"+x["source_id"],
        source_id=x["source_id"],
        source_kind=x["source_kind"],
        source_available_at=(x["first_available_at"] if publisher else x["retrieved_at"]),
        collected_at=x["retrieved_at"],
        source_sha256=x["content_sha256"],
        archive_path=x["archive_path"],
        provenance_class=("original_publication" if publisher else "collector_possession"))

def legacy_market_quote(old, *, source_receipt_id, selected_side="paired"):
    """Never manufactures side-specific prices, source bytes, or market P."""
    x=_fields(old)
    if x.get("quote_kind")!="real" or not x.get("quote_archive_path"):
        raise AdmissionError("NO_ORIGINAL_REAL_QUOTE")
    if selected_side not in ("over","under","paired"):
        raise AdmissionError("QUOTED_SIDE_NOT_SUPPORTED")
    return record("MarketQuote",
        quote_id=x["quote_id"],contract_id=x["contract_id"],
        event_id=x["event_id"],sport=x["sport"],team_id=x["team_id"],
        opponent_id=x["opponent_id"],player_id=x["player_id"],
        stat_key=x["stat_key"],period=x["period"],quote_timestamp=x["quote_at"],
        event_start_at=x["event_start_at"],book=x["book"],
        product_type=x["product_type"],quote_kind="real",line=x["line"],
        side=selected_side,source_receipt_id=source_receipt_id,
        source_sha256=x["quote_receipt_sha256"],
        terms={"settlement_policy":x["settlement_policy"],
               "over_decimal_odds":x.get("over_decimal_odds"),
               "under_decimal_odds":x.get("under_decimal_odds"),
               "raw_quote_path":x["quote_archive_path"]},
        accepted=x["accepted"],reject_reason=x["reject_reason"])

def legacy_forecast_reference(old):
    """Read-only manifest: legacy fixed-line forecast is NOT A/B-certified."""
    x=_fields(old)
    if hasattr(old,"to_record"):
        x=old.to_record()
    if not x.get("forecast_id") or not x.get("event_id"):
        raise AdmissionError("LEGACY_FORECAST_IDENTITY_MISSING")
    return {"reference_type":"LEGACY_FORECAST_READ_ONLY",
            "legacy_schema":x.get("schema_version","unknown"),
            "legacy_forecast_id":x["forecast_id"],
            "legacy_event_id":x["event_id"],
            "original_record_sha256":sha256(x),
            "p0_admission":"BLOCKED_PENDING_ORIGINAL_FEATURE_AND_MODEL_BYTES",
            "may_promote_to_original":False}

def nba_pregame_feature_adapter(original_record, *, reconstruction_class):
    """One schema transport for accepted source_listed_subset snapshots.

    Does not validate the incoming P1 producer by name or accept absent
    source timestamps; independent admit_forecast checks all source bytes.
    """
    x=_fields(original_record)
    if reconstruction_class not in ("original","reconstructed"):
        raise AdmissionError("MISSING_EXPLICIT_NBA_RECONSTRUCTION_CLASS")
    needed=("feature_snapshot_id","event_id","team_id","opponent_id",
            "player_id","stat_key","period","input_freeze_at",
            "source_receipt_ids","features")
    if any(k not in x for k in needed):
        raise AdmissionError("NBA_SOURCE_LISTED_SUBSET_INCOMPLETE")
    if x.get("sport") not in ("NBA",None):
        raise AdmissionError("WRONG_NBA_SPORT")
    return record("PregameFeatureSnapshot",
        feature_snapshot_id=x["feature_snapshot_id"],sport="NBA",
        event_id=x["event_id"],team_id=x["team_id"],
        opponent_id=x["opponent_id"],player_id=x["player_id"],
        stat_key=x["stat_key"],period=x["period"],
        input_freeze_at=x["input_freeze_at"],
        source_receipt_ids=x["source_receipt_ids"],
        feature_sha256=sha256(x["features"]),features=x["features"],
        reconstruction_class=reconstruction_class)
