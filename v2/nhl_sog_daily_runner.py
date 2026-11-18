"""Daily family source admission: existing quote/roster gates, no GP inference dependency."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json
from .nhl_sog_exposure_shadow import ExperimentBlocked,fit_model,_utc
from .nhl_sog_official_history_producer import independent_verify_observation_lineage,_signed
from .contracts import MarketQuote
from .nhl_sog_daily_ledger import Ledger

def validate_contract(model,quote,*,source_root,roster_root,roster_receipts,
                                source_bound_player_name,
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
    if (not model.get("target_event_id") or not model.get("current_team_id") or
            quote.event_id!=model["target_event_id"] or
            quote.team_id!=model["current_team_id"]):
        raise ExperimentBlocked("TARGET_EVENT_TEAM_UNVERIFIED")
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
    # A file hash does not bind an offered player/line/book/price to the
    # specific structured original quote. Independently crosscheck every
    # original provider row before adapting a full count law to one line.
    from .nhl_sog_quote_binding import verify_structured_original_sog_offer
    quote_lineage=verify_structured_original_sog_offer(
        quote,source_root=source_root,
        source_bound_player_name=source_bound_player_name)
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
    return {"status":"SOURCE_AND_ROSTER_VERIFIED_NO_MODEL_INFERENCE"}


def freeze_family(bundle,contract,*,source_root,ledger_path):
    root=Path(source_root).resolve()
    observed=datetime.now(timezone.utc).isoformat()
    if any(contract.get(k)!=v for k,v in bundle['quote'].items()):
        raise ValueError('SHARED_CONTRACT_QUOTE_DRIFT')
    q=MarketQuote(**bundle['quote'])
    from scripts.c03_live_transport import verify_signed_capture
    def _proof(unused,pool,digest,*,freeze,event):
        if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('SIGNED_PROOF_SHA_INVALID')
        rel='c03_collector_receipts/'+digest+'.json'
        raw=(pool/rel).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('SIGNED_PROOF_HASH_DRIFT')
        fields=json.loads(raw)['receipt_fields']
        r=dict(fields,transport_attestation='collector_signed_tls_bytes_v1',
            collector_proof_archive_path=rel,collector_proof_sha256=digest)
        return r,verify_signed_capture(r,archive_root=pool,freeze=freeze,event_start=event)
    from .nhl_sog_pregame_schedule import official_games
    from zoneinfo import ZoneInfo
    receipt,doc=_proof(root,root,contract['signed_schedule_proof_sha256'],
        freeze=observed,event=q.event_start_at)
    day=datetime.fromisoformat(q.event_start_at.replace('Z','+00:00')).astimezone(ZoneInfo('America/Toronto')).date().isoformat()
    games=official_games(receipt['source_url'],doc,day)
    matched=[g for g in games if str(g.get('id'))==str(contract['official_game_id'])]
    if len(matched)!=1:raise ValueError('OFFICIAL_EVENT_NOT_UNIQUE')
    game=matched[0]
    if (game.get('gameState') not in ('FUT','PRE') or
        _utc(game['startTimeUTC'],'game_start')!=_utc(q.event_start_at,'quote_start') or
        {game[t]['abbrev'] for t in ('homeTeam','awayTeam')}!={q.team_id,q.opponent_id}):
        raise ValueError('OFFICIAL_GAME_CONTRACT_DRIFT')
    for team in (q.team_id,q.opponent_id):
        rr=bundle['official_roster_receipts'][team]
        signed,_=_proof(root,root,rr['source_c03_collector_proof_sha256'],
            freeze=observed,event=q.event_start_at)
        if (signed['body_sha256']!=rr['sha256'] or
            signed['source_url']!='https://api-web.nhle.com/v1/roster/'+team+'/current'):
            raise ValueError('SIGNED_ROSTER_RECEIPT_DRIFT')
    own=bundle['own_official_history'];peers=bundle['peer_official_history']
    own_verified=[independent_verify_observation_lineage(x,archive_root=root,
        freeze=observed,event_start=q.event_start_at) for x in own]
    peer_verified=[independent_verify_observation_lineage(x,archive_root=root,
        freeze=observed,event_start=q.event_start_at) for x in peers]
    profile=_signed(own[0]['raw_profile_receipt'],root,observed,q.event_start_at)
    first=profile['firstName'];last=profile['lastName']
    if isinstance(first,dict):first=first['default']
    if isinstance(last,dict):last=last['default']
    name=first.strip()+' '+last.strip()
    model=fit_model(own_verified,peer_verified,archive_root=root,player_id=q.player_id,
        position_group=bundle['official_position_group'],target_event_id=q.event_id,
        current_team_id=q.team_id,input_freeze_at=observed,event_start_at=q.event_start_at)
    validate_contract(model,q,source_root=root,roster_root=root,
        roster_receipts=bundle['official_roster_receipts'],source_bound_player_name=name,
        code_commit=bundle['code_commit'],run_id=bundle['run_id'],forecast_id=bundle['forecast_id'],
        forecast_at=datetime.now(timezone.utc).isoformat(),decision_cutoff_at=observed)
    return Ledger(ledger_path).freeze(contract,model,run_id=bundle['run_id'],code_sha=bundle['code_commit'])
