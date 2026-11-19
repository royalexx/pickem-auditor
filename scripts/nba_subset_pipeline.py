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


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture',required=True);p.add_argument('--cohort',required=True)
    p.add_argument('--output',required=True)
    args=p.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    cohort=json.loads(Path(args.cohort).read_bytes())
    source=canonical(export_requests(args.capture,cohort))
    (out/'p1.json').write_bytes(source)
    p2=run_p2(source,args.capture,cohort);p2raw=canonical(p2)
    (out/'p2.json').write_bytes(p2raw)
    read_p2(p2raw,source_raw=source,capture_dir=args.capture,cohort=cohort)
    receipt=dict(command=sys.argv,executed_at=datetime.now(timezone.utc).isoformat(),
        implementation_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        source_capture=args.capture,cohort=args.cohort,
        candidate_denominator=p2['candidate_denominator'],stat_attempt_denominator=p2['attempt_denominator'],
        p2_forecasted_rows=p2['forecasted_rows'],p2_abstained_rows=p2['abstained_rows'],
        byte_domains={'p1.json':'canonical JSON of replayed original raw source bodies and receipts',
                     'p2.json':'canonical JSON of actual P2 output including every attempted row'})
    (out/'receipt.json').write_bytes(canonical(receipt));print(json.dumps(receipt,indent=2))
    (out/'SHA256SUMS').write_text(''.join(digest(f.read_bytes())+'  '+f.name+'\n' for f in sorted(out.iterdir()) if f.is_file()))


if __name__=='__main__':main()
