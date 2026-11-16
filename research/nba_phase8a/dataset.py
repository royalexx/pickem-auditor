"""Frozen candidate observations; outcomes belong only to separate settlement records."""
from v2.nba_ws1.store import instant


def candidate_table(ledger,snapshot):
    if any(k in ledger for k in ('actual_participants','settlement','postgame_actuals')):raise ValueError('POSTGAME_FEATURE_CONTAMINATION')
    rows=[];players={p['player_id']:p for p in snapshot['players']}
    for p in ledger['roster_contract']['players']:
        part=next(r for r in ledger['participation']['rows'] if r['player_id']==p['player_id'] and r['team_id']==p['team_id'])
        h=players[p['player_id']]['history']
        if any(instant(x['event_start_at'])>=instant(snapshot['game']['event_start_at']) for x in h):raise ValueError('SAME_GAME_HISTORY_LEAKAGE')
        rows.append(dict(game_id=p['game_id'],team_id=p['team_id'],player_id=p['player_id'],
            original_candidate_source=p['source_evidence'][0],original_raw_source_receipts=p['source_evidence'],
            publication_at=p['source_evidence'][0]['published_at'],retrieval_at=p['source_evidence'][0]['retrieved_at'],forecast_freeze_at=ledger['input_freeze_at'],
            roster_membership_evidence=p['source_evidence'][:1],legal_eligibility=None,
            eligibility_evidence=[],availability_evidence=part['accepted_availability'],rejected_availability=part['rejected_availability'],pregame_role_evidence=p['starting_role_evidence'],
            prior_participation_history={str(n):h[-n:] for n in (5,10,20)},
            prior_history_semantics='available source history only; absent games not inferred DNP; bounded ten team games cannot certify twenty-game coverage',
            prior_minute_law_support=part['M0_usable'],M0_abstention=part.get('M0_abstention'),
            source_coverage_flags=p['missing_data_status'],ambiguity_flags=p['abstention_reasons'],
            postgame_appearance=None,observed_minutes_conditional_on_playing=None,explicit_DNP=None,missing_or_unlisted_outcome=None,
            original_contracts=[c for c in snapshot['market_context']['original_contracts'] if c.get('player_id')==p['player_id']],
            all_abstention_reasons=sorted(set(p['abstention_reasons']+part['abstention_reasons']))))
    return dict(schema='NBAPhase8ACandidateObservations/1',rows=rows,rejected_source_candidates=ledger['roster_contract']['rejected_candidates'],
        nba_unresolved_candidates=[r for w in ledger['identity_crosswalks'] for r in w['unresolved']],
        denominator_kind='source-observed ESPN roster membership, with separate rejected/unresolved NBA records',verified_eligible_denominator=False,
        original_candidates=len(rows),additional_rejected_candidates=len(ledger['roster_contract']['rejected_candidates']),postgame_records=0,
        settlement_join_keys=['game_id','team_id','player_id'],features_immutable=True)
