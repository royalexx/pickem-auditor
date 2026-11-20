#!/usr/bin/env python3
"""Create-only fixed-M0 P2 dispatch and linked audit, without fitting or scoring."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest,export_requests
from v2.nba_architecture.subset_p2_v1 import run_p2
from v2.nba_architecture.subset_p3_v1 import run_p3
from v2.nba_architecture.subset_p4_v1 import run_p4
from v2.nba_architecture.subset_p2_dispatch_v1 import run_dispatch,read_dispatch
from v2.nba_c.subset_archive_v1 import SubsetAuditArchive
from v2.nba_c.subset_dispatch_archive_v1 import DispatchAuditArchive


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','cohort','history','output'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--model',default='research/nba_ws2/results/model.json')
    parser.add_argument('--s-model-dir',help='Optional candidate files; no runtime model registration')
    parser.add_argument('--forecast-at',help='Explicit recorded-clock replay; omitting uses actual current pregame clock')
    args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    cohort=json.loads(Path(args.cohort).read_bytes());at=args.forecast_at or datetime.now(timezone.utc).isoformat()
    p1=canonical(export_requests(args.capture,cohort));p2=canonical(run_p2(p1,args.capture,cohort))
    upstream=dict(source_raw=p1,capture_dir=args.capture,cohort=cohort,history_dir=args.history,model_path=args.model,forecast_at=at)
    p3=canonical(run_p3(**upstream));p4=canonical(run_p4(p2,p3,**upstream))
    outputs=dict(p1=p1,p2=p2,p3=p3,p4=p4)
    for name,raw in outputs.items():(out/(name+'.json')).write_bytes(raw)
    base=SubsetAuditArchive(out/'archive');base_receipt=base.put(outputs,capture_dir=args.capture,cohort=cohort,history_dir=args.history,model_path=args.model)
    dispatch_inputs=dict(upstream,p3_raw=p3,model_dir=args.s_model_dir)
    dispatch=run_dispatch(**dispatch_inputs);wire=canonical(dispatch);read_dispatch(wire,**dispatch_inputs)
    (out/'dispatch.json').write_bytes(wire)
    audit=DispatchAuditArchive(out/'archive');receipt=audit.put(base_receipt['record_id'],wire,model_dir=args.s_model_dir)
    manifest=audit.read(receipt['record_id']);(out/'dispatch-manifest.json').write_bytes(canonical(manifest)+b'\n')
    result=dict(command=sys.argv,implementation_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        forecast_at=at,executed_at=datetime.now(timezone.utc).isoformat(),
        operation='RECORDED_CLOCK_REPLAY' if args.forecast_at else 'CURRENT_RESEARCH_EXECUTION',
        base_receipt=base_receipt,dispatch_receipt=receipt,
        candidate_denominator=dispatch['candidate_denominator'],attempt_denominator=dispatch['attempt_denominator'],
        exposure_bound_rows=dispatch['exposure_bound_rows'],forecasted_rows=dispatch['forecasted_rows'],
        abstained_rows=dispatch['abstained_rows'],conditioning=dispatch['conditioning'],exposure_variant=dispatch['exposure_variant'],
        model_candidate_denominator=dispatch['model_candidate_denominator'],provided_file_denominator=dispatch['provided_file_denominator'],
        byte_domains=dict(outputs='CANONICAL_COMPACT_JSON',manifests='CANONICAL_COMPACT_JSON_PLUS_LF',
            objects='EXACT_RAW_SOURCE_MODEL_READER_OR_WIRE_BYTES'))
    (out/'receipt.json').write_bytes(canonical(result))
    (out/'SHA256SUMS').write_text(''.join(digest(p.read_bytes())+'  '+str(p.relative_to(out))+'\n' for p in sorted(out.rglob('*')) if p.is_file() and p!=out/'SHA256SUMS'))
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
