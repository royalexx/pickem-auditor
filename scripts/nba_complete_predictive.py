#!/usr/bin/env python3
"""Exact frozen-cohort full-law replay, bounded C read, new J engineering run.

No schedule, training restart, historical replacement, scoring of old games,
merge, deployment or Tier promotion. Existing issuances are immutable.
"""
import argparse
from datetime import datetime,timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.subset_p3_v1 import require
from v2.nba_architecture.subset_contract_v1 import strict_json
from v2.nba_opportunity import utc

P=ROOT/'docs/nba_architecture/complete_predictive_20261120'
spec=importlib.util.spec_from_file_location('complete_predictive_inputs',P/'inputs.py')
inputs=importlib.util.module_from_spec(spec);spec.loader.exec_module(inputs)
MODEL_ADMISSION_SHA=None


def now():return datetime.now(timezone.utc).isoformat()


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    for name in ('replay','read-outcomes','compile-j','run-j'):
        p=sub.add_parser(name);p.add_argument('--output',required=True)
    a=parser.parse_args();out=Path(a.output)
    require(not out.exists(),'COMPLETE_PREDICTIVE_CREATE_ONLY_OUTPUT')
    if a.command=='compile-j':
        from v2.nba_joint.real_event_parameters_v1 import fit_event_parameters
        result=fit_event_parameters(approval_path=P/'independent_j_prefit/PREFIT_APPROVAL.json',
            full_forecast_raw=(P/'actual_full_forecast/forecast.json').read_bytes(),parent_raw=(inputs.ARCHIVE/'forecast.json').read_bytes(),
            full_replay_inputs=inputs.full_inputs(),original_raw_dir=inputs.ARCHIVE/'inputs/raw',
            spec_path=inputs.ARCHIVE/'inputs/spec.json',policy_path=inputs.ARCHIVE/'inputs/policy.raw',
            pbp_raw_dir=P/'raw',pbp_population_path=P/'PBP_POPULATION.json',s3_path=P/'fitted_s3/three_conversion.json',
            s3_receipt_path=P/'fitted_s3/FIT_RECEIPT.json',s3_admission_path=P/'independent_s3_artifact/ARTIFACT_ADMISSION.json',
            full_admission_path=P/'independent_full_law/ADMISSION.json',j_card_path=P/'J_MODEL_CARD.json',output=out)
        print(canonical(result).decode());return
    if a.command=='run-j':
        require(MODEL_ADMISSION_SHA is not None,'REAL_J_PARAMETER_ARTIFACT_REVIEW_CLOSED')
        admission_raw=(P/'independent_j_artifact/ARTIFACT_ADMISSION.json').read_bytes()
        require(digest(admission_raw)==MODEL_ADMISSION_SHA,'REAL_J_PARAMETER_ADMISSION_BYTES')
        admission=strict_json(admission_raw);mr=(P/'fitted_j/event_model.json').read_bytes();receipt_raw=(P/'fitted_j/FIT_RECEIPT.json').read_bytes()
        require(digest(mr)==admission['model_raw_sha256'] and digest(receipt_raw)==admission['fit_receipt_raw_sha256'],
            'REAL_J_PARAMETER_ARTIFACT_BYTES')
        model=strict_json(mr);receipt=strict_json(receipt_raw);full=strict_json((P/'actual_full_forecast/forecast.json').read_bytes())
        freeze=now();require(max(utc(admission['admitted_at']),utc(receipt['completed_at']))<=utc(freeze)<utc(full['event_start_at']),
            'REAL_J_ACTUAL_FUTURE_FREEZE')
        cohort=dict(full['cohort'],freeze_at=freeze,kind='NEW_J_ENGINEERING_COHORT_SAME35_CANDIDATES')
        out.mkdir(parents=True);(out/'COHORT.json').write_bytes(canonical(cohort));started=now()
        from v2.nba_joint.residual_events_v1 import simulate
        from v2.nba_joint.residual_audit_v1 import audit_run
        from v2.nba_joint.residual_diagnostics_v1 import compare_with_full_S
        run=simulate(model,seed=20261120,n=32,path_budget=4096,event_budget=4096)
        # Persist the whole run before validation; failed/rejected paths survive.
        (out/'RUN.json').write_bytes(canonical(run))
        audit=diagnostics=None
        if run['status']=='ENGINEERING_SAMPLE':
            audit=audit_run(run);(out/'PHYSICS.json').write_bytes(canonical(audit))
            diagnostics=compare_with_full_S(run,full);(out/'DISCREPANCY.json').write_bytes(canonical(diagnostics))
        result=dict(schema='new-J-actual-execution/1',implementation_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            input_model_raw_sha256=digest(mr),input_model_receipt_raw_sha256=digest(receipt_raw),model_admission_sha256=MODEL_ADMISSION_SHA,
            input_full_forecast_raw_sha256=digest((P/'actual_full_forecast/forecast.json').read_bytes()),
            freeze_at=freeze,started_at=started,completed_at=now(),event_start_at=full['event_start_at'],
            run_raw_sha256=digest((out/'RUN.json').read_bytes()),status=run['status'],seed=20261120,scenario_denominator=32,
            supported_primitive_rows=56,abstained_primitive_rows=84,attempt_denominator=140,
            marginal_fidelity_accepted=False,historical_predictive_validation=False,release=False)
        require(utc(result['completed_at'])<utc(full['event_start_at']),'REAL_J_COMPLETED_AFTER_EVENT_NO_PROSPECTIVE_ISSUE')
    else:
        from v2.nba_architecture.conditional_c_v1 import replay_and_pending,read_native_outcomes
        started=now();out.mkdir(parents=True)
        if a.command=='read-outcomes':result=read_native_outcomes(**inputs.outcome_inputs())
        else:result=replay_and_pending((P/'actual_full_forecast/forecast.json').read_bytes(),
            (inputs.ARCHIVE/'forecast.json').read_bytes(),full_inputs=inputs.full_inputs(),outcome_inputs=inputs.outcome_inputs())
        (out/'RESULT.json').write_bytes(canonical(result))
        (out/'COMMAND_RECEIPT.json').write_bytes(canonical(dict(command=sys.argv,started_at=started,completed_at=now(),
            implementation_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            result_raw_sha256=digest((out/'RESULT.json').read_bytes()),new_forecast_issued=False,release=False)))
    if a.command=='run-j':(out/'EXECUTION_RECEIPT.json').write_bytes(canonical(result))
    (out/'SHA256SUMS').write_text(''.join(digest(f.read_bytes())+'  '+f.name+'\n' for f in sorted(out.iterdir()) if f.is_file() and f.name!='SHA256SUMS'))
    summary={k:v for k,v in result.items() if k not in ('rows','games','results')}
    print(canonical(summary).decode())


if __name__=='__main__':main()
