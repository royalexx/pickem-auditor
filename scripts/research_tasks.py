#!/usr/bin/env python3
"""Build deduplicated verification tasks and reconcile complete audit outputs."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import context_feeds as cf


def reconcile(inputs, outputs):
    expected = Counter(r.get('id') for r in inputs)
    actual = Counter(r.get('id') for r in outputs)
    if None in expected or any(n != 1 for n in expected.values()):
        raise ValueError('candidate IDs must be present and unique')
    if expected != actual:
        raise ValueError(f'audit ID mismatch: missing={list((expected-actual).elements())}, unexpected={list((actual-expected).elements())}')
    return {'inputs': sum(expected.values()), 'outputs': sum(actual.values()), 'ids_match': True}


def build(packet, scan, prep, now=None):
    candidates = scan.get('research_candidates', scan.get('shortlist', []))
    ids = sorted({r['id'] for r in candidates})
    selected = [r for r in prep if r.get('id') in ids]
    gaps = cf.gap_paths_for_shortlist(packet, ids, candidate_rows=selected, now=now)
    by_path = {}
    for gap in gaps:
        path = gap['path']
        task = by_path.setdefault(path, {**gap, 'status': 'pending', 'attempts': [],
            'completion_rule': 'verified current evidence or documented access/data blocker',
            'source_order': ['official game-day/league source', 'team report', 'credentialed beat report', 'independent corroboration'],
            'instruction': 'Check publication time, game identity and report scope. Record supporting and opposing evidence. Never infer active from absence on an injury list.'})
    for r in candidates:
        for gap in r.get('verification_gaps', []):
            key = f"candidate.{r['id']}.{gap}"
            by_path.setdefault(key, {'path': key, 'reason': gap, 'status': 'pending', 'attempts': [],
                'instruction': 'Refresh the relevant source and rerun the full audit; discovery is not publication approval.'})
    return {'created_at': (now or datetime.now(timezone.utc)).isoformat(),
            'research_complete': False, 'candidate_ids': ids, 'tasks': list(by_path.values()),
            'source_conflicts': packet.get('_source_conflicts', []), 'publication_eligible': False,
            'research_state': 'verification_pending' if by_path else 'ready_for_adversarial_review',
            'completion_note': 'No tasks does not attest adversarial research or approve publication.'}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--packet',required=True);ap.add_argument('--scan',required=True);ap.add_argument('--prep',required=True)
    ap.add_argument('--resolve', action='store_true', help='Resolve supported structured-source gaps, save the packet and automatically regrade.')
    ap.add_argument('--recover-packet', action='append', help='Previously captured same-date research JSON packet; replay only valid sourced facts before regrading. Repeatable.')
    ap.add_argument('--refresh-context', action='store_true', help='Retry existing live context collectors before rebuilding tasks.')
    ap.add_argument('--slate', help='Collected slate JSONL required for --refresh-context')
    ap.add_argument('--audit',action='store_true',help='Evaluate packet and require one output per input ID (offline).')
    a=ap.parse_args();packet=json.loads(Path(a.packet).read_text());scan=json.loads(Path(a.scan).read_text())
    prep=[json.loads(l) for l in Path(a.prep).read_text().splitlines() if l.strip()]
    attempts = []
    if a.recover_packet:
        from research_recovery import recover
        for prior_path in a.recover_packet:
            prior=json.loads(Path(prior_path).read_text(encoding='utf-8'))
            packet,receipt=recover(packet,prior,now=datetime.now(timezone.utc))
            attempts.append({'collector':'research_recovery','source_file':str(prior_path), 'result':receipt})
        destination=Path(a.packet)
        temporary=destination.with_suffix('.recover.tmp')
        temporary.write_text(json.dumps(packet,indent=2)+'\n',encoding='utf-8')
        temporary.replace(destination)
    if a.refresh_context:
        if not a.slate: ap.error('--refresh-context requires --slate')
        import fetch_slate as fs
        rows=fs.read_jsonl(Path(a.slate))
        collected=fs.emit_slate_context(packet['date'], rows, fs.utc_now(), data_dir=Path(a.packet).parent)
        packet=json.loads(Path(a.packet).read_text())
        attempts.append({'collector':'existing_context_feeds','result':collected})
    resolution = None
    if a.resolve:
        from research_resolver import resolve
        import fetch_slate as fs
        ids=[r['id'] for r in scan.get('research_candidates', scan.get('shortlist', []))]
        packet,resolution=resolve(packet,ids,fs.fetch_json)
        destination=Path(a.packet)
        temporary=destination.with_suffix('.research.tmp')
        temporary.write_text(json.dumps(packet,indent=2)+'\n')
        temporary.replace(destination)
    original_candidates=scan.get('research_candidates', scan.get('shortlist', []))
    if resolution:
        import research_packet as rp
        import pickem_math as pm
        from usage_baseline import using_directory
        merged,invalid=rp.prepare_candidates(packet,prep,datetime.now(timezone.utc),require_market_clock=True)
        if merged:
            with using_directory(Path(a.packet).parent):
                scan=pm.scan_candidates(merged)
            # A newly visible availability veto must not erase a research case.
            existing={r['id'] for r in scan.get('research_candidates', [])}
            blockers={r['id']:r for r in scan.get('unresearchable', [])}
            for previous in original_candidates:
                if previous['id'] not in existing:
                    blocker=blockers.get(previous['id'], {})
                    if blocker.get('sample_block') or blocker.get('reason')=='PLAYER_OUT':continue
                    reason=blocker.get('reason') or 'AVAILABILITY_OR_CONTEXT_UNRESOLVED'
                    if reason=='Unranked':reason='AVAILABILITY_OR_CONTEXT_UNRESOLVED'
                    scan.setdefault('research_candidates', []).append({**previous,
                        'publication_eligible':False,'verification_gaps':[reason],
                        'retained_for_research':True})
        if invalid:
            resolution['candidate_validation_errors']=invalid
    result=build(packet,scan,prep)
    result['structured_resolution']=resolution
    if resolution: result['scan_after_resolution']=scan
    if resolution:
        started=set(resolution['started_games'])
        index=packet.get('index',{}).get('by_player',{})
        result['excluded_started_candidate_ids']=[i for i in result['candidate_ids'] if index.get(i.split('|')[1],{}).get('game') in started]
        result['excluded_unverified_fixture_ids']=[i for i in result['candidate_ids'] if index.get(i.split('|')[1],{}).get('game') not in set(resolution['verified_pregame_games']) and i not in result['excluded_started_candidate_ids']]
        for task in result['tasks']:
            task['next_action']='agent_source_research' if not task['path'].startswith('prep.') else 'source_history_or_sample_review'

    result['collection_attempts']=attempts
    if a.audit or a.resolve:
        command=[sys.executable,str(Path(__file__).with_name('research_packet.py')),'audit','--packet',a.packet,'--prep',a.prep]
        audit=subprocess.run(command,capture_output=True,text=True,check=False)
        rows=[json.loads(l) for l in audit.stdout.splitlines() if l.strip()]
        if not rows and audit.returncode:
            result['audit_status']='blocked'
            result['audit_errors']=audit.stderr.splitlines()
            print(json.dumps(result,indent=2))
            return 1
        result['reconciliation']=reconcile(prep,rows)
        result['audit_status']='evaluated' if audit.returncode==0 else 'candidate_errors'
        if resolution:
            excluded=set(result.get('excluded_started_candidate_ids', []))
            for row in rows:
                if row.get('id') in excluded:
                    row['final_rank']='Unranked'
                    row['reason']='GAME_STARTED'
                elif row.get('id') in set(result.get('excluded_unverified_fixture_ids', [])):
                    row['final_rank']='Unranked'
                    row['reason']='FIXTURE_UNVERIFIED'
        result['audit_results']=rows
        from research_dispositions import dispositions
        excluded = {i: 'GAME_STARTED' for i in result.get('excluded_started_candidate_ids', [])}
        excluded.update({i: 'FIXTURE_UNVERIFIED' for i in result.get('excluded_unverified_fixture_ids', [])})
        result['dispositions'] = dispositions(result['candidate_ids'], rows, excluded=excluded)
    print(json.dumps(result,indent=2))
    return 0 if not (a.audit or a.resolve) or audit.returncode==0 else 1

if __name__=='__main__':raise SystemExit(main())
