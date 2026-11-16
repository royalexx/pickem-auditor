"""Export real advance roster observations; never claim registered game-day freeze."""
import gzip,json
from pathlib import Path
from v2.nba_ws1.store import Receipt
from v2.nba_joint.forecast import freeze
from research.nba_phase7.pilot import registered_slots

def export(source,identities,output):
    root=Path(source);rosters={};walks={};rows=[]
    for p in root.glob('source_*.json'):
        item=json.loads(p.read_text());r=Receipt(**item['receipt'])
        if r.source.endswith('/roster'):
            raw=gzip.decompress((root/item['path']).read_bytes());r.verify(raw);d=json.loads(raw);rosters['espn:team:'+str(d['team']['id'])]=(d,r,item)
    for p in Path(identities).glob('team_*.json'):
        w=json.loads(p.read_text())
        for e in w['entries']:walks[(e['espn_team_id'],e['espn_player_id'])]=e
    for s in registered_slots():
        for tid in (s['game']['home_team_id'],s['game']['away_team_id']):
            d,r,item=rosters[tid]
            for p in d['athletes']:
                pid='espn:player:'+str(p['id']);e=walks.get((tid,pid))
                rows.append(dict(slot=s['slot'],game_id=s['game']['game_id'],team_id=tid,player_id=pid,source_full_name=p['fullName'],nba_player_id=e['nba_player_id'] if e else None,
                    original_candidate_source=r.source,original_raw_source_receipt=item,source_publication_at=None,actual_retrieval_at=r.observed_at,
                    forecast_freeze_at=None,observation_kind='genuine_advance_original_roster_observation_not_registered_game_day_capture',
                    identity_evidence=e,roster_membership_evidence=item,legal_eligibility=None,eligibility_evidence=[],availability_evidence=[],pregame_role_evidence=[],
                    prior_participation_history={'5':None,'10':None,'20':None},prior_minute_law_support=None,
                    source_coverage_flags=['ADVANCE_MEMBERSHIP_ONLY','GAME_DAY_REFRESH_REQUIRED','LEGAL_ELIGIBILITY_UNKNOWN','PRIOR_HISTORY_NOT_ACQUIRED_IN_ADVANCE_AUDIT'],
                    ambiguity_flags=[] if e else ['NBA_ESPN_IDENTITY_UNRESOLVED'],postgame_appearance=None,observed_minutes_conditional_on_playing=None,explicit_DNP=None,missing_or_unlisted_outcome=None,
                    original_contract_present=False,abstention_reasons=['NOT_REGISTERED_GAME_DAY_FREEZE','LEGAL_ELIGIBILITY_UNKNOWN','PARTICIPATION_MODEL_UNFITTED','ORIGINAL_MARKET_TERMS_MISSING']))
    result=dict(schema='NBAPhase8AAdvanceCandidateObservations/1',rows=rows,candidate_game_rows=len(rows),game_day_candidate_rows=0,postgame_records=0,verified_eligible_denominator=False,training_ready=False)
    freeze(output,result);return result
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--identities',required=True);p.add_argument('--output',required=True);a=p.parse_args();r=export(a.source,a.identities,a.output);print(r['candidate_game_rows'])
