"""Explain every audited candidate without promoting diagnostic probabilities."""
from collections import Counter


def dispositions(candidate_ids, audit_rows, *, excluded=None):
    ids = list(candidate_ids)
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate requested candidate IDs')
    counts = Counter(row.get('id') for row in audit_rows)
    if any(counts[i] != 1 for i in ids):
        raise ValueError('each candidate requires exactly one audit result')
    rows = {row['id']: row for row in audit_rows}
    output = []
    for ident in ids:
        row = rows[ident]
        grade = row.get('grade') or {}
        vetoes = row.get('derived_vetoes') or {}
        reason = row.get('reason')
        blockers = list(row.get('research_issues') or [])
        blockers += vetoes.get('data_veto_reasons') or []
        blockers += vetoes.get('hard_veto_reasons') or []
        rank = row.get('final_rank', 'Unranked')
        exclusion = (excluded or {}).get(ident)
        if exclusion:
            status = 'excluded'
            blockers.insert(0, exclusion)
        elif rank in ('Tier 1', 'Tier 2', 'Tier 3'):
            status = 'ranked'
        elif rank == 'Reject':
            status = 'rejected'
        elif rank == 'Watchlist':
            status = 'watchlist'
        else:
            status = 'blocked'
            if reason:
                blockers.insert(0, reason)
            if not row.get('ok', True):
                blockers.append('AUDIT_ERROR')
            if grade.get('data_veto') and not blockers:
                blockers.append('INPUT_DATA_VETO')
            if grade.get('market_valid') is False:
                blockers.append('INVALID_MARKET')
            if not blockers:
                blockers.append('UNEXPLAINED_UNRANKED_RESULT')
        requirements = []
        if grade and grade.get('mechanisms', 0) < 1:
            requirements.append('SOURCED_CAUSAL_MECHANISM_REQUIRED')
        if not grade.get('research_checklist'):
            requirements.append('ADVERSARIAL_REVIEW_NOT_ATTESTED')
        output.append({
            'id': ident, 'disposition': status,
            'final_rank': 'Unranked' if exclusion else rank,
            'blockers': list(dict.fromkeys(blockers)),
            'remaining_review': requirements,
            'numerical_band_diagnostic_only': grade.get('probability_rank'),
            'numeric_notes': grade.get('notes', []),
            'engine_a': row.get('engine_a'), 'engine_b': row.get('engine_b'),
            'context_detail': (row.get('shared_context') or {}).get('detail'),
            'publication_eligible': status == 'ranked',
        })
    return {'candidate_count': len(output),
            'counts': dict(Counter(r['disposition'] for r in output)),
            'research_complete': False,
            'scope': 'Machine dispositions; no attestation of completed source research.',
            'candidates': output}
