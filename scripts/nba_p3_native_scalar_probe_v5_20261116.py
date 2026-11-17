"""Versioned bool/int red-to-green witness; all source inputs synthetic."""
import hashlib
import json
from pathlib import Path
import subprocess

from test_p3_p1_native_v4 import native_fixture
from test_p3_native_scalar_v5 import eligibility_fixture
from v2.nba_architecture.v2_contracts import ContractError
from v2.nba_o_p1_native import consume_p1_context


def main():
    rows = []
    for case in ('valid_integer_counts','boolean_counts','float_counts','numeric_eligibility_summary'):
        p, export = eligibility_fixture(False) if case == 'numeric_eligibility_summary' else native_fixture()
        if case == 'boolean_counts':
            export['candidate_denominator'].update(observed_candidates=True, admitted=False)
        elif case == 'float_counts':
            export['candidate_denominator'].update(observed_candidates=1.0, admitted=0.0)
        elif case == 'numeric_eligibility_summary':
            export['players'][0]['legal_eligibility'] = 0
        try:
            output = consume_p1_context(export, frozen_pregame=p)
            result = 'ACCEPTED_TRANSPORT_BLOCKED_SOURCE'
        except ContractError as exc:
            output = dict(error=exc.code)
            result = 'REJECTED_INVALID_TRANSPORT'
        rows.append(dict(case=case, pregame=p, input=export, output=output, result=result))
    print(json.dumps(dict(schema='nba-p3-native-scalar-probe/1.0.0',
        scope='SYNTHETIC_ENGINEERING_NO_AUTHENTIC_SOURCE_ADMISSION',
        owner_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        code_raw_sha256=hashlib.sha256(Path('v2/nba_o_p1_native.py').read_bytes()).hexdigest(),
        results=rows),sort_keys=True,indent=2))


if __name__ == '__main__':
    main()
