"""Point-in-time, distribution-free NBA P1 -> P3 feature transport (PA-NBA-P1/1).

Input is a verified WS1 NBA pregame snapshot and its original source bytes.
The consumer never imports the collector, and the outcome vault is inaccessible.
This module does not infer legal eligibility, participation odds or NBA IDs.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo
from v2.p0_integrity.contracts import record, validate_record, sha256, utc, AdmissionError

VERSION='PA-NBA-P1/1'
STATS=('points','rebounds','assists','threes','pra','pr','pa','ra')
PRIMARY=('points','rebounds','assists','threes')
BANNED={'actual_minutes','realized_minutes','realized_usage','final_score','outcome',
        'target_game_boxscore','target_game_result','target_game_play_by_play','future_outcomes',
        'target_game_minutes','actual_possessions','actual_usage','actual_rotation'}

class FeatureAdmissionError(ValueError):
    pass

def fail(code):
    raise FeatureAdmissionError(code)

def _clean(obj):
    if isinstance(obj,dict):
        for k,v in obj.items():
            if k in BANNED:fail('TARGET_OUTCOME_FIELD_FORBIDDEN:'+k)
            _clean(v)
    elif isinstance(obj,list):
        for v in obj:_clean(v)

def _iso(s):
    try:return utc(s)
    except (ValueError,TypeError) as exc:raise FeatureAdmissionError('INVALID_OR_NON_UTC_TIME') from exc

def _digest(b):return hashlib.sha256(b).hexdigest()

def _source_map(snapshot, raw_by_receipt):
    ids=set(); result={}
    for r in snapshot.get('receipts',[]):
        rid=r['receipt_id']
        if rid in ids:fail('DUPLICATE_SOURCE_RECEIPT')
        ids.add(rid)
        if rid not in raw_by_receipt:fail('SOURCE_BYTES_MISSING:'+rid)
        raw=raw_by_receipt[rid]
        if not isinstance(raw,bytes) or _digest(raw)!=r['raw_sha256']:
            fail('SOURCE_SHA_MISMATCH:'+rid)
        if _iso(r['source_available_at'])>_iso(snapshot['input_freeze_at']) or \
           _iso(r['observed_at'])>_iso(snapshot['input_freeze_at']):
            fail('SOURCE_AFTER_FREEZE:'+rid)
        # A retrospective-retrieval receipt created now may be a valid present-day
        # pregame observation, never evidence of an original pregame in past seasons.
        result[rid]=r
    if not result:fail('NO_ORIGINAL_SOURCE_BYTES')
    return result

def _raw_crosswalk(evidence, at, source_receipts):
    """An NBA ID is published only with time-valid authenticated cross-provider evidence."""
    if evidence is None:return None
    if not isinstance(evidence,list):fail('CROSSWALK_SCHEMA')
    accepted=[]
    for item in evidence:
        if _iso(item['observed_at'])>_iso(at):continue
        if _iso(item['valid_from'])<=_iso(at) and (item.get('valid_to') is None or _iso(at)<_iso(item['valid_to'])):
            if item.get('source_receipt_id') not in source_receipts or not str(item.get('nba_player_id','')).startswith('nba:player:'):
                fail('CROSSWALK_EVIDENCE_MISSING')
            accepted.append(item['nba_player_id'])
    if len(set(accepted))!=1 or len(accepted)!=1:fail('CROSSWALK_AMBIGUOUS')
    return accepted[0]

def _roster_metadata(pid,roster_record,records,receipts,raw_by_receipt):
    """Read name/position only from the already-archived ORIGINAL ESPN roster.

    Never match on names or lift identities from old boxscores. Conflicting
    current roster aliases are missing/ambiguous, never guessed.
    """
    entry=next((x for x in records if x.get('record_id')==roster_record and x.get('kind')=='roster'),None)
    if entry is None:return {'name':None,'position':None,'listed_roster_status':None,'listed_roster_uncertainty':None,'evidence_receipt_id':None,'status':'ROSTER_RECORD_MISSING'}
    rid=entry['receipt_id'];receipt=receipts.get(rid)
    try:payload=json.loads(entry['payload'])
    except (KeyError,TypeError,ValueError):return {'name':None,'position':None,'listed_roster_status':None,'listed_roster_uncertainty':None,'evidence_receipt_id':rid,'status':'ROSTER_PAYLOAD_MISSING'}
    base={'name':None,'position':None,'listed_roster_status':payload.get('status'),
          'listed_roster_uncertainty':payload.get('uncertainty'),
          'evidence_receipt_id':rid,'status':'SOURCE_LISTED_NOT_CONFIRMED'}
    if not receipt or not receipt['source'].split('?')[0].endswith('/roster'):
        return base
    try:roster=json.loads(raw_by_receipt[rid])
    except (KeyError,ValueError,TypeError):return base
    seen=[]
    def walk(x):
        if isinstance(x,dict):
            if str(x.get('id',''))==pid.rsplit(':',1)[-1] and (x.get('displayName') or x.get('fullName')):
                p=x.get('position')
                pos=(p.get('abbreviation') or p.get('name')) if isinstance(p,dict) else None
                seen.append((x.get('displayName') or x.get('fullName'),pos))
            for child in x.values():walk(child)
        elif isinstance(x,list):
            for child in x:walk(child)
    walk(roster)
    unique=set(seen)
    if len(unique)!=1:return {**base,'status':'ROSTER_NAME_POSITION_AMBIGUOUS' if unique else 'ROSTER_DETAILS_UNAVAILABLE'}
    name,position=next(iter(unique))
    return {**base,'name':name,'position':position}

def _status(evidence):
    """ESPN roster listing is a candidate, not verified legal eligibility."""
    if not evidence:return 'UNVERIFIED_AVAILABILITY'
    tokens=[str(x.get('status','')).lower() for x in evidence]
    if any(x in ('out','ruled out','inactive') for x in tokens):return 'RULED_OUT_SOURCE_REPORTED'
    if any(x in ('questionable','doubtful','probable','gtd','day-to-day') for x in tokens):return 'QUESTIONABLE_SOURCE_REPORTED'
    return 'UNVERIFIED_AVAILABILITY'

def build_feature_rows(snapshot, raw_by_receipt, *, reconstruction_class='original', crosswalks=None, receipt_id_map=None):
    """Yield exact P0 PregameFeatureSnapshot records and an explicit P1 handoff.

    Snapshot must be reconstructed/validated by WS1.from_json at the producer
    boundary; this method independently checks source bytes, temporal identity,
    negative controls, and P0 schema. No actual target-game stats are accepted.
    """
    if reconstruction_class not in ('original','reconstructed'):fail('INVALID_RECONSTRUCTION_CLASS')
    if snapshot.get('schema_version')!='nba-pregame-feature-snapshot/1.0.0':fail('WS1_SCHEMA_MISMATCH')
    _clean(snapshot)
    target=snapshot['game']; game_id=target['game_id']; at=_iso(snapshot['input_freeze_at']); start=_iso(target['event_start_at'])
    if not at<start:fail('INPUT_NOT_PREGAME')
    if _iso(snapshot['forecast_at'])<at or _iso(snapshot['source_available_at'])>at:
        fail('SOURCE_FREEZE_ORDER_INVALID')
    receipts=_source_map(snapshot,raw_by_receipt)
    if not game_id.startswith('espn:game:'):fail('INVALID_TARGET_GAME_NAMESPACE')
    teams={target['home_team_id'],target['away_team_id']}
    if len(teams)!=2:fail('GAME_TEAMS_AMBIGUOUS')
    # Historical dates alone cannot prove availability: the receipt clock above
    # independently proves that *these exact response bytes* were held at freeze.
    local_day=start.astimezone(ZoneInfo('America/Toronto')).date()
    team_map={x['team_id']:x for x in snapshot.get('teams',[])}
    if set(team_map)!=teams:fail('TEAM_CONTEXT_MISMATCH')
    by_pid={}; rows=[]; excluded=[]
    for p in snapshot.get('players',[]):
        pid=p['player_id']; team=p['team_id']; opp=p['opponent_id']
        if not pid.startswith('espn:player:') or pid in by_pid:
            excluded.append({'player_id':pid,'reason':'PLAYER_ID_DUPLICATED_OR_INVALID'});continue
        by_pid[pid]=True
        if team not in teams or opp!=next(iter(teams-{team})):
            excluded.append({'player_id':pid,'reason':'PLAYER_TEAM_OPPONENT_CONFLICT'});continue
        history=p.get('history',[])
        bad_history=False
        for h in history:
            # Reject instead of silently stripping future or target-game rows.
            if h['game_id']==game_id or __import__('datetime').date.fromisoformat(h['game_date'])>=local_day:
                bad_history=True;break
            if h['receipt_id'] not in receipts or h['player_id']!=pid or h.get('participation') not in ('played','dnp','unknown'):
                bad_history=True;break
            if h['participation']!='played' and (h.get('minutes') is not None or h.get('stats')):
                bad_history=True;break
        if bad_history:excluded.append({'player_id':pid,'reason':'HISTORY_TARGET_LEAKAGE_OR_IDENTITY'});continue
        source_ids=set()
        roster_record=p.get('roster_record_id')
        for r in snapshot.get('input_records',[]):
            if r.get('record_id')==roster_record:
                if r.get('kind')!='roster':fail('ROSTER_RECORD_TYPE_MISMATCH')
                source_ids.add(r['receipt_id'])
        # Everything actually reflected in historical state is bound to exact receipts.
        source_ids.update(h['receipt_id'] for h in history)
        source_ids.update(a['receipt_id'] for a in p.get('availability',[]))
        if not source_ids:source_ids.add(next(iter(receipts)))
        if not source_ids.issubset(receipts):
            excluded.append({'player_id':pid,'reason':'PLAYER_SOURCE_MISSING'});continue
        aw=p.get('availability',[])
        stat_detail=p['features']; t=team_map[team]; o=team_map[opp]
        missing=sorted(set(p.get('missing_feature_codes',[])+t.get('missing_feature_codes',[])+o.get('missing_feature_codes',[])))
        cross=None
        if crosswalks and pid in crosswalks:
            try:cross=_raw_crosswalk(crosswalks[pid],at,receipts)
            except FeatureAdmissionError:
                excluded.append({'player_id':pid,'reason':'CROSSWALK_AMBIGUOUS_OR_UNVERIFIED'});continue
        status=_status(aw)
        roster_meta=_roster_metadata(pid,roster_record,snapshot.get('input_records',[]),receipts,raw_by_receipt)
        for field,reason in [('name','PLAYER_NAME_UNAVAILABLE'),('position','PLAYER_POSITION_UNAVAILABLE'),('listed_roster_status','ROSTER_STATUS_UNAVAILABLE')]:
            if roster_meta[field] is None:missing.append(reason)
        missing=sorted(set(missing))
        public_ids=sorted((receipt_id_map or {}).get(r,r) for r in source_ids)
        features={'interface_version':VERSION,'candidate_kind':'SOURCE_LISTED_SUBSET',
                  'legal_eligibility':'UNVERIFIED','availability_status':status,
                  'participation_probability':None,'source_listed':True,
                  'espn_player_id':pid,'official_nba_player_id':cross,
                  'espn_event_id':game_id,'official_nba_event_id':None,
                  'home':p['home'],'roster_record_id':roster_record,
                  'current_name':roster_meta['name'],'position':roster_meta['position'],
                  'listed_roster_status':roster_meta['listed_roster_status'],
                  'listed_roster_uncertainty':roster_meta['listed_roster_uncertainty'],
                  'identity_source_status':roster_meta['status'],
                  'identity_evidence_receipt_id':(receipt_id_map or {}).get(roster_meta['evidence_receipt_id'],roster_meta['evidence_receipt_id']),
                  'prior_player_history':history,'prior_player_features':stat_detail,
                  'current_team_context':t,'opponent_context':o,
                  'missingness':missing,'injury_evidence':aw,
                  'feature_source_receipt_ids':public_ids,
                  'reconstruction_note':('AUTHENTIC_SAME_DAY_POSSESSION' if reconstruction_class=='original' else 'RETROSPECTIVE_NOT_ORIGINAL')}
        _clean(features)
        for stat in STATS:
            # No synthetic probabilities, no invented market terms.
            ident=(VERSION,game_id,pid,team,stat,at.isoformat())
            uid=_digest(json.dumps(ident,separators=(',',':')).encode())
            obj=record('PregameFeatureSnapshot',feature_snapshot_id='nba-p1:'+uid,
                sport='NBA',event_id=game_id,team_id=team,opponent_id=opp,
                player_id=pid,stat_key=stat,period='full',input_freeze_at=at.isoformat().replace('+00:00','Z'),
                source_receipt_ids=public_ids,feature_sha256=sha256(features),
                reconstruction_class=reconstruction_class,features=features)
            rows.append(obj)
    summary={'schema':VERSION,'event_id':game_id,'event_start_at':start.isoformat().replace('+00:00','Z'),
             'input_freeze_at':at.isoformat().replace('+00:00','Z'),'research_profile':'source_listed_subset',
             'reconstruction_class':reconstruction_class,'player_candidates_total':len(snapshot.get('players',[])),
             'player_candidates_accepted':len(rows)//len(STATS),'player_candidates_rejected':len(excluded),
             'feature_rows':len(rows),'market_category':'DISTRIBUTION_ONLY_NO_VERIFIED_QUOTE',
             'source_receipt_count':len(receipts),'unknown_availability':sum(x['features']['availability_status']=='UNVERIFIED_AVAILABILITY' for x in rows[::len(STATS)]),
             'rejected':excluded,'abstention_reasons':sorted(set(snapshot.get('abstention_codes',[]))),
             'historical_reconstruction_never_original':reconstruction_class=='reconstructed',
             'source_listed_count':len(rows)//len(STATS),
             'confirmed_available_count':0,
             'questionable_count':sum(x['features']['availability_status']=='QUESTIONABLE_SOURCE_REPORTED' for x in rows[::len(STATS)]),
             'ruled_out_count':sum(x['features']['availability_status']=='RULED_OUT_SOURCE_REPORTED' for x in rows[::len(STATS)]),
             'name_supported_count':sum(x['features']['current_name'] is not None for x in rows[::len(STATS)]),
             'position_supported_count':sum(x['features']['position'] is not None for x in rows[::len(STATS)]),
             'official_player_ids_verified_count':sum(x['features']['official_nba_player_id'] is not None for x in rows[::len(STATS)])}
    return rows,summary

def verify_handoff(rows, manifest, raw_by_receipt):
    """Independent P3 boundary: reject changed features, late sources or false A status."""
    if manifest.get('schema')!=VERSION:fail('HANDOFF_SCHEMA')
    freeze=_iso(manifest['input_freeze_at']);start=_iso(manifest['event_start_at'])
    if not freeze<start:fail('HANDOFF_AFTER_TIPOFF')
    if len(rows)!=manifest['feature_rows']:fail('FEATURE_DENOMINATOR_MISMATCH')
    for x in rows:
        validate_record('PregameFeatureSnapshot',x)
        if x['input_freeze_at']!=manifest['input_freeze_at'] or x['event_id']!=manifest['event_id']:
            fail('HANDOFF_IDENTITY_OR_CLOCK_MISMATCH')
        if x['reconstruction_class']!=manifest['reconstruction_class']:fail('RECONSTRUCTION_CLASS_MISMATCH')
        if not set(x['source_receipt_ids']).issubset(raw_by_receipt):fail('HANDOFF_SOURCE_BYTES_MISSING')
        _clean(x['features'])
    return True

def verify_dev_p0_record(root,kind,sha):
    """Verify a P0-schema receipt inside P1-only staging (no global P0 writes)."""
    from v2.p0_integrity.contracts import SCHEMAS,validate_record,canonical_bytes
    if kind not in ('SourceReceipt','PregameFeatureSnapshot'):fail('P1_RECORD_KIND_FORBIDDEN')
    if not isinstance(sha,str) or len(sha)!=64 or any(x not in '0123456789abcdef' for x in sha):
        fail('INVALID_P1_RECORD_SHA')
    base=(Path(root)/'research/nba_p1_original/dev_v1/p0_records'/kind)
    path=base/(sha+'.json')
    if path.is_symlink() or not path.is_file():fail('P1_P0_RECORD_MISSING')
    raw=path.read_bytes()
    if _digest(raw)!=sha:fail('P1_P0_RECORD_CORRUPTED')
    obj=json.loads(raw)
    validate_record(kind,obj)
    logical_id=obj[SCHEMAS[kind][0]]
    key=_digest((kind+'\x00'+logical_id).encode())
    claim=base/'_ids'/(key+'.json')
    expected=canonical_bytes({'kind':kind,'id':logical_id,'record_sha256':sha})
    if claim.is_symlink() or not claim.is_file() or claim.read_bytes()!=expected:
        fail('P1_P0_LOGICAL_ID_CLAIM_BROKEN')
    return obj

def load_handoff(root, manifest_relpath):
    """Read-only P3 API; immutable file hashes verified; no network/collector import."""
    from v2.p0_integrity.storage import attest_project_storage
    # The accepted P0 attestation recognizes the Deepnote logical /work root,
    # not its detached-run-specific resolved physical mount.
    if Path(root)!=Path('/work'):fail('P0_HANDOFF_ROOT_NOT_ATTESTED')
    attest_project_storage('/work')
    root=Path(root).resolve(strict=True)
    manifest_file=(root/manifest_relpath).resolve(strict=True)
    if not manifest_file.is_relative_to(root):fail('HANDOFF_PATH_ESCAPE')
    manifest=json.loads(manifest_file.read_bytes())
    if manifest.get('schema')!=VERSION:fail('HANDOFF_SCHEMA')
    rows=[];raws={}
    for item in manifest['features']:
        p=(root/item['path']).resolve(strict=True)
        if not p.is_relative_to(root) or _digest(p.read_bytes())!=item['sha256']:fail('FEATURE_BYTES_CHANGED')
        rows.append(json.loads(p.read_bytes()))
    for item in manifest['sources']:
        receipt=verify_dev_p0_record('/work','SourceReceipt',item['p0_sha256'])
        if receipt['receipt_id']!=item['receipt_id']:
            fail('P0_RECEIPT_IDENTITY_CHANGED')
        if _iso(receipt['source_available_at'])>_iso(manifest['input_freeze_at']) or \
           _iso(receipt['collected_at'])>_iso(manifest['input_freeze_at']):
            fail('P0_SOURCE_AVAILABLE_AFTER_FREEZE')
        if receipt['archive_path']!=item['path'] or receipt['source_sha256']!=item['sha256']:
            fail('P0_RECEIPT_SOURCE_BYTES_MISMATCH')
        p=(root/item['path']).resolve(strict=True)
        if not p.is_relative_to(root) or _digest(p.read_bytes())!=item['sha256']:fail('SOURCE_BYTES_CHANGED')
        raws[item['receipt_id']]=p.read_bytes()
    verify_handoff(rows,manifest,raws)
    return {'games':[{'event_id':manifest['event_id'],'event_start_at':manifest['event_start_at']}],
            'players':sorted({r['player_id'] for r in rows}),
            'features':rows,'market_quotes':manifest.get('accepted_market_quotes',[]),
            'summary':manifest,'original_source_bytes':raws}
