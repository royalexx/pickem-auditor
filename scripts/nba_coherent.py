#!/usr/bin/env python3
"""Frozen-cohort coherent opportunity S4/J research, create-only artifacts."""
from datetime import datetime,timezone
import argparse
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys
import zlib

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.subset_contract_v1 import strict_json
from v2.nba_architecture.subset_p3_v1 import require
from v2.nba_opportunity import utc

P=ROOT/'docs/nba_architecture/coherent_opportunity_20261120';OLD=P.parent/'complete_predictive_20261120'
spec=importlib.util.spec_from_file_location('coherent_frozen_inputs',OLD/'inputs.py')
inputs=importlib.util.module_from_spec(spec);spec.loader.exec_module(inputs)
MODEL_ADMISSION_SHA=None


def now():return datetime.now(timezone.utc).isoformat()


def sums(out):
    (out/'SHA256SUMS').write_text(''.join(digest(f.read_bytes())+'  '+str(f.relative_to(out))+'\n'
        for f in sorted(out.rglob('*')) if f.is_file() and f.name!='SHA256SUMS'))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('fit','predict','replay'))
    parser.add_argument('--output',required=True);args=parser.parse_args();out=Path(args.output)
    require(not out.exists(),'COHERENT_CREATE_ONLY_OUTPUT')
    if args.command=='fit':
        from v2.nba_joint.coherent_components_v1 import fit
        r=fit(approval_path=P/'independent_prefit/PREFIT_APPROVAL.json',protocol_path=P/'PROTOCOL.json',
            old_model_path=OLD/'fitted_j/event_model.json',old_admission_path=OLD/'independent_j_artifact/ARTIFACT_ADMISSION.json',
            source_inputs=inputs.outcome_inputs(),original_raw_dir=inputs.ARCHIVE/'inputs/raw',
            spec_path=inputs.ARCHIVE/'inputs/spec.json',policy_path=inputs.ARCHIVE/'inputs/policy.raw',output=out)
        sums(out);print(canonical(r).decode());return
    if args.command=='replay':
        from v2.nba_joint.coherent_issued_v1 import replay
        r=replay(P/'actual',model_dir=P/'fitted',source_inputs=inputs.outcome_inputs())
        out.mkdir(parents=True);(out/'RESULT.json').write_bytes(canonical(r));sums(out);print(canonical(r).decode());return
    require(MODEL_ADMISSION_SHA is not None,'COHERENT_MODEL_ARTIFACT_REVIEW_CLOSED')
    a_raw=(P/'independent_artifact/ARTIFACT_ADMISSION.json').read_bytes()
    require(digest(a_raw)==MODEL_ADMISSION_SHA,'COHERENT_ARTIFACT_ADMISSION_BYTES');a=strict_json(a_raw)
    model_raw=(P/'fitted/model.json').read_bytes();receipt_raw=(P/'fitted/FIT_RECEIPT.json').read_bytes()
    require(digest(model_raw)==a['model_raw_sha256'] and digest(receipt_raw)==a['fit_receipt_raw_sha256'],'COHERENT_MODEL_RECEIPT_BYTES')
    model=strict_json(model_raw);fitted=strict_json(receipt_raw)
    from v2.nba_architecture.conditional_c_v1 import read_native_outcomes
    read_native_outcomes(**inputs.outcome_inputs())
    from v2.nba_joint.coherent_components_v1 import PROTOCOL_SHA,ADDENDUM_SHA
    require(digest((P/'PROTOCOL.json').read_bytes())==PROTOCOL_SHA and
        digest((P/'PROTOCOL_ADDENDUM.json').read_bytes())==ADDENDUM_SHA,'COHERENT_FROZEN_PROTOCOL')
    cohort=strict_json((OLD/'FULL_FORECAST_COHORT.json').read_bytes());freeze=now()
    require(digest((OLD/'FULL_FORECAST_COHORT.json').read_bytes())==strict_json((P/'PROTOCOL.json').read_bytes())['cohort_raw_sha256'],
        'COHERENT_FROZEN_ORIGINAL_COHORT')
    require(max(utc(a['admitted_at']),utc(fitted['verified_at']))<=utc(freeze)<utc(cohort['start']),'COHERENT_ACTUAL_FUTURE_FREEZE')
    cohort.update(freeze_at=freeze,kind='NEW_COHERENT_S4_J_SAME35_LATER_ACTUAL_FREEZE')
    reference_raw=(OLD/'actual_full_forecast/forecast.json').read_bytes()
    require(digest(reference_raw)=='a60ec92b970e6b417a1b9b48dceca3b2a1140dcf84f7f4ef24a8b57edcfc987f','COHERENT_FROZEN_S1_REFERENCE')
    reference=strict_json(reference_raw);reasons={}
    for r in reference['law_payload']['rows']:
        if r['model'] is None:reasons.setdefault(r['player_id'],set()).add(r['reason'])
    cohort['inherited_abstention_reasons']={k:sorted(v) for k,v in reasons.items()}
    out.mkdir(parents=True);(out/'COHORT.json').write_bytes(canonical(cohort));started=now()
    from v2.nba_joint.coherent_predictive_v1 import generate,validate_bank,rows,SharedForecast
    from v2.nba_joint import coherent_predictive_v1 as kernel
    bank=generate(model,cohort,out/'trace',seed=20261120,n=64,path_budget=4096,event_budget=4096)
    (out/'BANK.json').write_bytes(canonical(bank))
    coherence=[];physics=None
    if bank['status']=='ENGINEERING_SAMPLE':
        physics=validate_bank(bank,out/'trace',model);marginals=rows(bank);view=SharedForecast(bank)
        for row in marginals:
            if row['samples'] is None:continue
            for kind,value in (('pmf',0),('cdf',10),('oup',10.5)):
                kw=dict(player_id=row['player_id'],statistic=row['statistic'],kind=kind,value=value)
                s=view.query(channel='S4',**kw);j=view.query(channel='J',**kw)
                require(s==j,'COHERENT_S_J_QUERY_DIVERGENCE');coherence.append(s)
        (out/'MARGINALS.json').write_bytes(canonical(dict(schema='coherent-shared-S4-J-marginals/1',rows=marginals,
            attempts=280,supported=112,abstained=168,primitive_attempts=140,primitive_supported=56,primitive_abstained=84,
            source_bank_payload_sha256=bank['payload_sha256'],independent_vote=False,actual_scores=0,pending_outcomes=280,release=False)))
        (out/'COHERENCE.json').write_bytes(canonical(dict(queries=coherence,exact_equal_pairs=len(coherence),
            software_identity_not_accuracy=True,physics=physics,zero_sensitivity_gate='PENDING')))
        # Read-only schema adapter to the frozen reference diagnostic. Rejected
        # entries carry their real trace receipts, not fabricated event paths.
        adapted=dict(schema='coherent-bank-reference-diagnostic-adapter/1',source_bank_payload_sha256=bank['payload_sha256'],
            n_requested=64,scenario_denominator=64,status='ENGINEERING_SAMPLE',failed=[],scenarios=[dict(fixed=s['fixed'],
                proposals=s['proposals'][:-1]+[s['accepted']],accepted_attempt=len(s['proposals'])-1) for s in bank['scenarios']])
        adapted['payload_sha256']=digest(canonical(adapted))
        from v2.nba_joint.residual_diagnostics_v1 import compare_with_full_S
        (out/'REFERENCE_COMPARISON.json').write_bytes(canonical(compare_with_full_S(adapted,reference)))
    completed=now();require(utc(started)<=utc(completed)<utc(cohort['start']),'COHERENT_ISSUE_CLOCK')
    modules=['v2/nba_joint/coherent_predictive_v1.py','v2/nba_joint/coherent_components_v1.py',
        'v2/nba_joint/residual_events_v1.py','v2/nba_joint/residual_opportunity_v1.py','v2/nba_joint/residual_audit_v1.py',
        'v2/nba_joint/common.py','v2/nba_architecture/conditional_c_v1.py']
    receipt=dict(schema='coherent-S4-J-actual-execution/1',implementation_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        code_raw_sha256={x:digest((ROOT/x).read_bytes()) for x in modules},model_raw_sha256=digest(model_raw),
        fit_receipt_raw_sha256=digest(receipt_raw),model_admission_raw_sha256=MODEL_ADMISSION_SHA,
        protocol_raw_sha256=PROTOCOL_SHA,addendum_raw_sha256=ADDENDUM_SHA,freeze_at=freeze,started_at=started,completed_at=completed,
        bank_raw_sha256=digest((out/'BANK.json').read_bytes()),bank_payload_sha256=bank['payload_sha256'],status=bank['status'],
        scenarios_requested=64,scenarios_dropped=0,failed=bank['failed'],path_proposals=sum(len(s['proposals']) for s in bank['scenarios']),
        exact_S4_J_query_pairs=len(coherence),population_accuracy_established=False,historical_validation=False,
        artifact_raw_sha256={f.name:digest(f.read_bytes()) for f in sorted(out.iterdir()) if f.is_file()},
        zero_sensitivity_gate='PENDING',python=platform.python_version(),zlib=zlib.ZLIB_RUNTIME_VERSION,
        gzip_format='GZIP_MTIME0_EMPTY_FILENAME_DEFAULT_LEVEL9',release=False)
    (out/'EXECUTION_RECEIPT.json').write_bytes(canonical(receipt));sums(out);print(canonical(receipt).decode())


if __name__=='__main__':main()
