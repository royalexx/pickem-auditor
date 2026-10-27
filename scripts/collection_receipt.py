#!/usr/bin/env python3
"""Check a persistent history ZIP for dated collection evidence, not task triggers."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import zipfile

def receipt(zip_path,expected_date,*,not_before=None):
    with zipfile.ZipFile(zip_path) as archive:
        manifest=json.loads(archive.read('data/archive_manifest.json'))
        handoff=json.loads(archive.read('data/handoff-summary.json'))
    collected=handoff.get('collected_at')
    when=datetime.fromisoformat(str(collected or '').replace('Z','+00:00')) if collected else None
    date_ok=(manifest.get('slate_date')==expected_date)
    cutoff=datetime.fromisoformat(not_before.replace('Z','+00:00')) if not_before else None
    stamp_ok=bool(when and when.tzinfo and (cutoff is None or when>=cutoff))
    counts_ok=bool(handoff.get('snapshots',0)>0 and isinstance(manifest.get('final_coverage'),dict))
    ok=date_ok and stamp_ok and counts_ok and handoff.get('pipeline_errors')==0
    return {'archive':Path(zip_path).name,'expected_date':expected_date,
            'manifest_slate_date':manifest.get('slate_date'),'collected_at':collected,
            'snapshot_count':handoff.get('snapshots',0),'pipeline_errors':handoff.get('pipeline_errors'),
            'dated_archive_evidence':ok,
            'note':'Archive evidence only; confirm Library version advanced and source collection logs before declaring a scheduled task successful.'}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive',required=True);ap.add_argument('--date',required=True)
    ap.add_argument('--not-before',help='Earliest acceptable UTC collection timestamp')
    a=ap.parse_args()
    out=receipt(a.archive,a.date,not_before=a.not_before)
    print(json.dumps(out,indent=2))
    return 0 if out['dated_archive_evidence'] else 2

if __name__=='__main__':sys.exit(main())
