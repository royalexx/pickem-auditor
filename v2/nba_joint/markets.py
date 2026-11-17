"""Exact WS1 original-contract extraction, with complete rejection accounting."""
from .common import STATS,instant,sha
from .forecast import extract_forecast


def original_markets(out,snapshot):
    data=snapshot.require_usable();seen=set();accepted=[];rejected=[]
    if data['game']['game_id']!=out['game']['game_id']:raise ValueError('CONTRACT_GAME_IDENTITY')
    pid={p['player_id']:i for i,p in enumerate(out['players'])};receipts={r['receipt_id']:r for r in data['receipts']}
    contracts=data['market_context']['original_contracts']
    for q in contracts:
        reason=None
        key=q['contract_id']
        if key in seen:reason='DUPLICATE_CONTRACT'
        seen.add(key)
        if q['player_id'] not in pid:reason=reason or 'PLAYER_NOT_FORECAST'
        elif out['players'][pid[q['player_id']]]['team_id']!=q['team_id']:reason=reason or 'CONTRACT_TEAM_IDENTITY'
        if q['stat'] not in STATS:reason=reason or 'UNSUPPORTED_MARKET'
        if q['period']!='full_game':reason=reason or 'STAT_POLICY_MISMATCH'
        terms=q['payout_terms']
        if not isinstance(terms,dict) or terms.get('overtime_included') is not True or 'dnp' not in terms:reason=reason or 'SETTLEMENT_TERMS_UNAVAILABLE'
        r=receipts[q['receipt_id']]
        if instant(q['quoted_at'])>instant(out['game']['forecast_at']):reason=reason or 'LATE_QUOTE'
        if reason:rejected.append({'contract':q,'reason':reason});continue
        f=extract_forecast(out,pid[q['player_id']],q['stat'],line=q['line'])
        f.pop('output_sha256');f.update(original_contract=q,original_source_receipt=r,threshold_kind='authenticated original contract identity; model remains uncertified',product_void_semantics=terms,source_raw_sha256=r['raw_sha256'])
        f['output_sha256']=sha(f);accepted.append(f)
    return {'attempted':len(contracts),'accepted':accepted,'rejected':rejected,'forecast_certification':'UNCERTIFIED/SHADOW'}
