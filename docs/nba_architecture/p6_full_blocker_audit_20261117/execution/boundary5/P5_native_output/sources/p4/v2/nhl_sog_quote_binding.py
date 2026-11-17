"""NHL SOG exact original structured provider quote binding (no raw-HTTP claim)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
import unicodedata

from .nhl_sog_exposure_shadow import ExperimentBlocked,_utc
from .contracts import MarketQuote

PROPLINE_URL_PATH="/v1/sports/icehockey_nhl/odds"
NOTE="structured_pre_resolution_quote_records_not_raw_http_bytes"


def _name(text):
    if not isinstance(text,str) or not text.strip():
        raise ExperimentBlocked("QUOTE_PLAYER_NAME_MISSING")
    s=unicodedata.normalize("NFKD",text).casefold()
    return " ".join("".join(ch if ch.isalnum() else " " for ch in s
                           if not unicodedata.combining(ch)).split())


def _american_decimal(value):
    if type(value) not in (float,int) or value==0:
        raise ExperimentBlocked("ORIGINAL_QUOTE_AMERICAN_ODDS_INVALID")
    if value>=100:return 1+value/100
    if value<=-100:return 1+100/(-value)
    raise ExperimentBlocked("ORIGINAL_QUOTE_ODDS_OUT_OF_RANGE")


def verify_structured_original_sog_offer(quote,*,source_root,
                                         source_bound_player_name):
    """Require exact row (event, stat, player, book, line, prices, time).

    Structured original PropLine API archive is not authenticated raw upstream
    HTTP bytes; never claim independent book publication clock.
    """
    if not isinstance(quote,MarketQuote) or quote.quote_kind!="real":
        raise ExperimentBlocked("QUOTE_NOT_REAL_MARKET")
    if (quote.sport,quote.stat_key,quote.period)!=("NHL","shots on goal","full"):
        raise ExperimentBlocked("QUOTE_NON_SOG_CONTRACT")
    if quote.product_type!="sportsbook_two_sided" or (
            quote.over_decimal_odds is None or quote.under_decimal_odds is None):
        raise ExperimentBlocked("TWO_SIDED_ORIGINAL_OFFER_REQUIRED")
    rel=quote.quote_archive_path
    if not isinstance(rel,str) or not rel or rel.startswith("/") or (
            "\\" in rel or ".." in Path(rel).parts):
        raise ExperimentBlocked("ORIGINAL_PROVIDER_QUOTE_ARCHIVE_MISSING")
    root=Path(source_root).resolve()
    file=(root/rel).resolve()
    if not file.is_relative_to(root) or not file.is_file():
        raise ExperimentBlocked("ORIGINAL_PROVIDER_QUOTE_ARCHIVE_UNAVAILABLE")
    raw=file.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=quote.quote_receipt_sha256:
        raise ExperimentBlocked("ORIGINAL_PROVIDER_QUOTE_ARCHIVE_DIGEST_MISMATCH")
    target_name=_name(source_bound_player_name)
    matches=[]
    for line in raw.splitlines():
        if not line.strip():continue
        try:r=json.loads(line)
        except (ValueError,UnicodeDecodeError) as exc:
            raise ExperimentBlocked("ORIGINAL_PROVIDER_QUOTE_RECORD_INVALID") from exc
        if not isinstance(r,dict):raise ExperimentBlocked("QUOTE_RECORD_NOT_OBJECT")
        if (r.get("sport")!="NHL" or
                str(r.get("event_id"))!=quote.event_id or
                r.get("stat")!="shots on goal" or
                str(r.get("book") or "").casefold()!=quote.book.casefold() or
                _name(str(r.get("player") or ""))!=target_name):
            continue
        try:price_over=float(r["over_odds"]);price_under=float(r["under_odds"])
        except (TypeError,ValueError,KeyError) as exc:
            raise ExperimentBlocked("ORIGINAL_PROVIDER_OFFER_PRICE_INVALID") from exc
        if (type(r.get("line")) not in (float,int) or
                float(r["line"])!=float(quote.line) or
                abs(_american_decimal(price_over)-quote.over_decimal_odds)>1e-8 or
                abs(_american_decimal(price_under)-quote.under_decimal_odds)>1e-8):
            continue
        uri=urlsplit(r.get("source_url") or "")
        if (uri.scheme!="https" or uri.hostname!="api.prop-line.com" or
                uri.path!=PROPLINE_URL_PATH or
                r.get("event_id_namespace")!="propline"):
            raise ExperimentBlocked("ORIGINAL_OFFER_PROVIDER_ORIGIN_INVALID")
        if _utc(r.get("retrieved_at"),"quote_row_at")!=_utc(quote.quote_at,"quote_at"):
            raise ExperimentBlocked("ORIGINAL_OFFER_TIMESTAMP_DRIFT")
        if _utc(r.get("event_start"),"quote_event_start")!=(
                _utc(quote.event_start_at,"event_start")):
            raise ExperimentBlocked("ORIGINAL_OFFER_EVENT_START_DRIFT")
        matches.append(r)
    if len(matches)!=1:
        raise ExperimentBlocked("ORIGINAL_OFFER_FULL_IDENTITY_NOT_UNIQUE")
    return {"source_semantics":NOTE,"exact_provider_row_sha256":hashlib.sha256(
        json.dumps(matches[0],sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest(),
        "quote_archive_sha256":quote.quote_receipt_sha256,
        "player_name_normalized":target_name,
        "quote_id":quote.quote_id,"contract_id":quote.contract_id}
