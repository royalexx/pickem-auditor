"""Audit retained original PDF and new provider identity source bytes, never forecasts."""
from dataclasses import asdict
from datetime import datetime,timezone
import gzip
import json
from pathlib import Path
import re
from v2.nba_ws1.store import Receipt,instant,digest
from v2.nba_joint.forecast import freeze
from .evidence import injury_pdf,build_crosswalk,resolve_injuries


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--probe',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    output=Path(a.output);output.mkdir(parents=True,exist_ok=False);probe=Path(a.probe)
    records=json.loads((probe/'receipt.json').read_text());sources=[]
    for item in records:
        if 'path' not in item:continue
        raw=gzip.decompress((probe/item['path']).read_bytes())
        r=Receipt.capture(raw,source=item['url'],observed_at=item['retrieved_at'],origin='original_capture')
        if digest(raw)!=item['sha256']:raise ValueError('PROBE_SOURCE_CHANGED')
        sources.append((raw,r,item))
    nba=next((raw,r) for raw,r,item in sources if '/team/' in item['url'])
    folder=Path('research/nba_phase6/current_source_probe');cap=json.loads((folder/'capture_receipt.json').read_text())
    original=json.loads((folder/cap['snapshot_path']).read_text());receipts={r['receipt_id']:Receipt(**r) for r in original['receipts']}
    espn=[]
    for item in cap['sources']:
        r=receipts[item['receipt_id']]
        if r.source.endswith('/teams/12/roster'):espn.append((gzip.decompress((folder/item['path']).read_bytes()),r))
    at=datetime.now(timezone.utc).isoformat();walk=build_crosswalk(*nba,*espn[0],freeze_at=at)
    old=Path('research/nba_phase6/official_source_probe');pdf=json.loads((old/'official_injury_pdf_receipt.json').read_text())
    report=injury_pdf((old/pdf['path']).read_bytes(),Receipt(**pdf['receipt']),freeze_at=at)
    availability=resolve_injuries(report,[walk],freeze_at=at)
    # Independent layout-text enumeration ensures parsing did not quietly drop
    # reported player/status rows on continuation pages.
    import subprocess
    text=subprocess.check_output(['pdftotext','-layout',str(old/pdf['path']),'-'],timeout=15).decode()
    enumeration=[]
    for line in text.splitlines():
        cols=re.split(r'\s{2,}',line.strip())
        for i,col in enumerate(cols[:-1]):
            if ',' in col and cols[i+1] in ('Out','Available','Probable','Questionable','Doubtful'):enumeration.append((col,cols[i+1]))
    parsed=[(r['official_player_name'],r['status']) for r in report['rows']]
    from collections import Counter
    if Counter(enumeration)!=Counter(parsed):raise ValueError('INDEPENDENT_PDF_ROW_ENUMERATION_MISMATCH:'+str((len(enumeration),len(parsed))))
    freeze(output/'identity_crosswalk.json',walk);freeze(output/'official_injury_report.json',report);freeze(output/'resolved_availability.json',availability)
    freeze(output/'source_audit_receipt.json',dict(status='SOURCE_IDENTITY_IMPROVED_GAME_FORECAST_BLOCKED',audit_at=at,
        crosswalk_entries=len(walk['entries']),crosswalk_unresolved=len(walk['unresolved']),official_pdf_rows=len(report['rows']),independent_text_rows=len(enumeration),
        resolved_official_rows=availability['resolved_count'],unresolved_official_rows=availability['unresolved_count'],
        original_phase6_snapshot_not_recertified=True,legitimate_pregame_forecasts_generated=0,
        reason='New crosswalk first observed after the original Warriors-Clippers freeze and tipoff. Official report matchup labels must also agree with the registered schedule; identity repair alone grants no game binding.',
        current_source_probes=records,new_source_receipts=[asdict(r) for raw,r,item in sources]))
    print(json.dumps({'crosswalk':len(walk['entries']),'unresolved_crosswalk':len(walk['unresolved']),'pdf_rows':len(report['rows']),'resolved_rows':availability['resolved_count'],'unresolved_rows':availability['unresolved_count']}))

if __name__=='__main__':main()
