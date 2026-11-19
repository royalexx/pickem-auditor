#!/usr/bin/env python3
"""Create-only public subset handoff runner. No fitting, scoring or promotion."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from v2.nba_architecture.p1_subset_handoff_v1 import canonical, digest, export_requests
from v2.nba_architecture.subset_p2_v1 import run_p2, read_p2
from v2.nba_architecture.subset_p3_v1 import run_p3, read_p3
from v2.nba_architecture.subset_p4_v1 import run_p4, read_p4
from v2.nba_c.subset_archive_v1 import SubsetAuditArchive


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture',required=True);p.add_argument('--cohort',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--history',help='Original current-team HTTP history capture directory')
    p.add_argument('--model',default='research/nba_ws2/results/model.json')
    p.add_argument('--forecast-at',help='Replay an explicitly recorded clock; never a new live forecast claim')
    p.add_argument('--through',choices=('p2','p3','p4','p5'),default='p5')
    args=p.parse_args()
    if args.through!='p2' and not args.history:p.error('--history is required beyond P2; use --through p2 for the source-only abstention boundary')
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    cohort=json.loads(Path(args.cohort).read_bytes())
    source=canonical(export_requests(args.capture,cohort))
    (out/'p1.json').write_bytes(source)
    p2=run_p2(source,args.capture,cohort);p2raw=canonical(p2)
    (out/'p2.json').write_bytes(p2raw)
    read_p2(p2raw,source_raw=source,capture_dir=args.capture,cohort=cohort)
    p3=None;p4=None;p5=None
    if args.history and args.through!='p2':
        forecast_at=args.forecast_at or datetime.now(timezone.utc).isoformat()
        p3=run_p3(source,args.capture,cohort,history_dir=args.history,model_path=args.model,forecast_at=forecast_at)
        p3raw=canonical(p3);(out/'p3.json').write_bytes(p3raw)
        read_p3(p3raw,source_raw=source,capture_dir=args.capture,cohort=cohort,history_dir=args.history,model_path=args.model,forecast_at=forecast_at)
        if args.through in ('p4','p5'):
            upstream=dict(p2_raw=p2raw,p3_raw=p3raw,source_raw=source,capture_dir=args.capture,
                cohort=cohort,history_dir=args.history,model_path=args.model,forecast_at=forecast_at)
            p4=run_p4(**upstream);p4raw=canonical(p4);(out/'p4.json').write_bytes(p4raw)
            read_p4(p4raw,**upstream)
            if args.through=='p5':
                archive=SubsetAuditArchive(out/'archive')
                p5=archive.put(dict(p1=source,p2=p2raw,p3=p3raw,p4=p4raw),capture_dir=args.capture,
                    cohort=cohort,history_dir=args.history,model_path=args.model)
                verified=archive.read(p5['record_id'])
                (out/'p5-manifest.json').write_bytes(canonical(verified)+b'\n')
                (out/'p5-receipt.json').write_bytes(canonical(p5))
    receipt=dict(command=sys.argv,executed_at=datetime.now(timezone.utc).isoformat(),
        implementation_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        source_capture=args.capture,cohort=args.cohort,
        candidate_denominator=p2['candidate_denominator'],stat_attempt_denominator=p2['attempt_denominator'],
        p2_forecasted_rows=p2['forecasted_rows'],p2_abstained_rows=p2['abstained_rows'],
        p3_forecasted_rows=p3['forecasted_rows'] if p3 else None,
        p3_abstained_rows=p3['abstained_rows'] if p3 else None,
        p4_attempt_rows=p4['attempt_denominator'] if p4 else None,
        p4_native_minute_laws_read=p4['native_minute_laws_read'] if p4 else None,
        p4_minute_stat_references=p4['minute_stat_references'] if p4 else None,
        p4_statistic_forecasted_rows=p4['statistic_forecasted_rows'] if p4 else None,
        through_executed=args.through,p5_record_id=p5['record_id'] if p5 else None,
        p5_counts=p5['counts'] if p5 else None,
        forecast_at=p3['forecast_at'] if p3 else None,
        operation='RECORDED_CLOCK_REPLAY' if args.forecast_at else 'CURRENT_RESEARCH_EXECUTION',
        byte_domains={'p1.json':'canonical JSON of replayed original raw source bodies and receipts',
                     'p2.json':'canonical JSON of actual P2 output including every attempted row',
                     'p3.json':'canonical JSON native played-conditional minute laws and abstentions; original raw model SHA is separate from native canonical model hash',
                     'p4.json':'canonical JSON of native minute-law transports and all statistic abstentions; no joint output',
                     'p5-manifest.json':'canonical JSON plus LF; record id is SHA256 of these exact bytes; referenced objects retain their own byte domains'})
    (out/'receipt.json').write_bytes(canonical(receipt));print(json.dumps(receipt,indent=2))
    (out/'SHA256SUMS').write_text(''.join(digest(f.read_bytes())+'  '+str(f.relative_to(out))+'\n' for f in sorted(out.rglob('*')) if f.is_file() and f!=out/'SHA256SUMS'))


if __name__=='__main__':main()
