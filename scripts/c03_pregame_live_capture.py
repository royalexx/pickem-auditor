"""C03 research-only transport-to-claim capture for prepared pregame rows.

No implicit mapping from Propline event IDs or NHL official player IDs into
ESPN namespaces. Without a verified upstream crosswalk the attempt abstains.
Legacy collector is entirely unchanged while C03 shadow flag is disabled.
"""
from __future__ import annotations

from datetime import datetime,timedelta,timezone
import hashlib

from c03_context_cohorts import CohortError
from c03_live_transport import capture_signed_live,claim_from_espn_summary

PATHS={"NBA":"basketball/nba","NFL":"football/nfl","NHL":"hockey/nhl"}


def annotate_prepared_candidates(rows,*,archive_root):
    """Opt-in real HTTPS capture, never a synthesized availability status.

    Mutates only the locally prepared run's experimental _c03* fields.
    Every missing/late/conflicting source gets a specific rejection reason.
    """
    cached={}
    records=[]
    for row in rows:
        if not isinstance(row,dict):
            records.append(row)
            continue
        next_row=dict(row)
        meta=row.get("_meta") or {}
        try:
            sport=meta.get("sport") or row.get("sport")
            path=PATHS.get(sport)
            if path is None:raise CohortError("C03_UNSUPPORTED_SPORT")
            event_id=str(meta.get("event_id") or row.get("event_id") or "")
            athlete=str(meta.get("player_id") or row.get("player_id") or "")
            event_namespace=meta.get("event_id_namespace") or row.get("event_id_namespace")
            athlete_namespace=meta.get("player_id_namespace") or row.get("player_id_namespace")
            if event_namespace!="espn":
                raise CohortError("C03_ESPN_EVENT_CROSSWALK_UNVERIFIED")
            if athlete_namespace!="espn":
                raise CohortError("C03_ESPN_PLAYER_CROSSWALK_UNVERIFIED")
            if not event_id.isdigit() or not athlete.isdigit():
                raise CohortError("C03_ESPN_CANONICAL_IDS_MISSING")
            team=str(row.get("team") or meta.get("team") or "")
            if not team or not team.isupper() or not team.isascii():
                raise CohortError("C03_TEAM_SOURCE_IDENTITY_UNVERIFIED")
            start=meta.get("event_start")
            if not start:raise CohortError("C03_EVENT_START_UNVERIFIED")
            from c03_context_cohorts import _utc
            start_dt=_utc(start,"event_start")
            now=datetime.now(timezone.utc)
            if not now+timedelta(seconds=3)<start_dt:
                raise CohortError("C03_SOURCE_CAPTURE_TOO_CLOSE_TO_START")
            cutoff=min(now+timedelta(seconds=50),start_dt-timedelta(seconds=1))
            url=("https://site.api.espn.com/apis/site/v2/sports/"+path+
                 "/summary?event="+event_id)
            source_key=(sport,event_id)
            if source_key not in cached:
                sid="c03_raw_"+hashlib.sha256(
                    (sport+"|"+event_id+"|"+now.isoformat()).encode()).hexdigest()[:28]
                cached[source_key]=capture_signed_live(url,
                    archive_root=archive_root,source_namespace="espn",
                    source_id=sid,input_cutoff_at=cutoff.isoformat(),
                    event_start_at=start)
            receipt=cached[source_key]
            claimed=claim_from_espn_summary(receipt,archive_root=archive_root,
                   event_id=event_id,team_id=team,player_id=athlete,
                   kind="subject_status",freeze=cutoff.isoformat(),event_start=start)
            claims=[claimed]
            context=row.get("event_context") or {}
            if not isinstance(context,dict):
                raise CohortError("C03_EVENT_CONTEXT_NOT_AN_OBJECT")
            for item in context.get("events") or []:
                if not isinstance(item,dict) or not str(item.get("player_id") or "").isdigit():
                    raise CohortError("C03_TEAMMATE_PLAYER_ID_NOT_CANONICAL")
                peer_claim=claim_from_espn_summary(
                    receipt,archive_root=archive_root,event_id=event_id,
                    team_id=team,player_id=str(item["player_id"]),
                    kind="teammate_status",freeze=cutoff.isoformat(),event_start=start)
                if peer_claim["value"]!="out":
                    raise CohortError("C03_TEAMMATE_OUT_NOT_CONFIRMED")
                claims.append(peer_claim)
            next_row["_c03_claims"]=claims
            next_row["_c03_source_receipts"]=[receipt]
        except (CohortError,OSError,ValueError,KeyError,TypeError) as exc:
            next_row["_c03_capture_issue"]=str(exc)[:220]
            next_row["_c03_claims"]=[]
            next_row["_c03_source_receipts"]=[]
        records.append(next_row)
    return records
