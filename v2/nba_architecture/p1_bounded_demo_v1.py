"""Restricted historical demonstration; excludes no source-admission failures."""
from copy import deepcopy
from .p1_listed_source_v1 import listed_population_receipt

VERSION = 'nba-p1-bounded-exposure-demo/1.0.0'


def classify_rows(rows, duration_seconds):
    """Policy-only helper, no authority to admit caller-provided rows."""
    result = []
    for original in rows:
        row = deepcopy(original)
        state, seconds = row.get('state'), row.get('exact_seconds')
        if state == 'DNP' and seconds is None and row.get('stats') == {}:
            disposition, reason = 'DNP', 'EXPLICIT_SOURCE_DNP'
        elif state == 'PLAYED' and type(seconds) is int and 30 <= seconds <= duration_seconds:
            disposition, reason = 'INCLUDED', 'ORDINARY_POSITIVE_EXPOSURE'
        else:
            disposition = 'EXCLUDED'
            if state == 'PLAYED_ZERO_MINUTES' or seconds == 0:
                reason = 'ZERO_EXPOSURE_REQUIRES_SEPARATE_ADJUDICATION'
            elif type(seconds) is int and 0 < seconds < 30:
                reason = 'SUB30SECOND_EXCEPTION_OUTSIDE_DEMO'
            else:
                reason = 'UNKNOWN_OR_UNSUPPORTED_EXPOSURE'
        result.append(dict(source_row=row, disposition=disposition, reason=reason))
    return result


def demonstrate(pdf, pdf_receipt, espn, receipt, **kwargs):
    """Actual public source path; unadmitted bundles are never filtered to pass."""
    admission = listed_population_receipt(pdf, pdf_receipt, espn, receipt, **kwargs)
    if admission['status'] != 'ACCEPTED_BOUNDED_CONTENT':
        return dict(schema=VERSION, status='REJECTED_WHOLE_SOURCE', admission=admission,
                    included_rows=0, excluded_rows=None, explicit_dnp_rows=None,
                    target_eligible_roster_count=None, G1='NO-GO')
    source = admission['result']
    duration_seconds = int(source['duration_minutes']) * 60
    rows = classify_rows(source['rows'], duration_seconds)
    counts = {state: sum(r['disposition'] == state for r in rows)
              for state in ('INCLUDED', 'DNP', 'EXCLUDED')}
    return dict(schema=VERSION, status='BOUNDED_HISTORICAL_DEMONSTRATION',
                attempted_rows=admission['attempted_rows'], included_rows=counts['INCLUDED'],
                explicit_dnp_rows=counts['DNP'], excluded_rows=counts['EXCLUDED'], rows=rows,
                source_admission=source, target_eligible_roster_count=None,
                B_P1_01='BLOCKED', B_P1_02='BLOCKED', G1='NO-GO')
