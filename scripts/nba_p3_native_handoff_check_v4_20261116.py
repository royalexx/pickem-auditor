"""Call actual latest P1 exporter, then P3 native consumer, on synthetic bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from v2.nba_architecture.v2_contracts import canonical


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--p1-root', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    import v2.nba_architecture
    v2.nba_architecture.__path__.append(str(args.p1_root/'v2/nba_architecture'))
    from v2.nba_architecture.p1_handoff import export_pregame_context
    from v2.nba_o_p1_native import consume_p1_context
    p = json.loads(Path('tests/nba_architecture/golden_v2/joint_same_draw.json').read_text())['pregame']
    player = p['players'][0]
    raw = canonical(dict(schema='nba-p1-dated-context/1.0.0', assertions=[dict(
        kind='pregame_roster',game_id=p['game_id'],player_id=player['player_id'],
        team_id=player['team_id'],effective_at=p['input_freeze_at'],
        legal_eligibility=None,availability='unknown')]))
    bundle = dict(source_url='https://site.api.espn.com/synthetic-reviewed-export',raw=raw,
        raw_sha256=hashlib.sha256(raw).hexdigest(),observed_at=p['input_freeze_at'],
        available_at=p['input_freeze_at'],origin='original_capture')
    export = export_pregame_context(game_id=p['game_id'],team_ids=p['team_ids'],
        event_start_at=p['event_start_at'],input_freeze_at=p['input_freeze_at'],
        bundles=[bundle],ingested_at=p['input_freeze_at'])
    result = consume_p1_context(export, frozen_pregame=p)
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'synthetic_raw_export.json').write_bytes(raw)
    (args.output/'p1_export.json').write_bytes(canonical(export))
    (args.output/'p3_abstention.json').write_bytes(canonical(result))
    receipt = dict(scope='SEPARATE_SYNTHETIC_ENGINEERING_NO_SOURCE_AUTHENTICITY',
        owner_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        p1_sha=subprocess.check_output(['git','-C',str(args.p1_root),'rev-parse','HEAD'],text=True).strip(),
        owner_worktree_status=subprocess.check_output(['git','status','--porcelain'],text=True),
        p1_worktree_status=subprocess.check_output(['git','-C',str(args.p1_root),'status','--porcelain'],text=True),
        p1_code_raw_sha256={name:hashlib.sha256((args.p1_root/name).read_bytes()).hexdigest()
            for name in ['v2/nba_architecture/p1_handoff.py','v2/nba_architecture/p1_context.py']},
        result=result['status'],first_missing_requirement=result['reason'],
        sampled=False,authenticity_admitted=False,independently_accepted=False)
    (args.output/'receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    (args.output/'SHA256SUMS').write_text(''.join(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.name+'\n'
        for path in sorted(args.output.iterdir())))
    print(json.dumps(receipt,sort_keys=True,indent=2))


if __name__ == '__main__':
    main()
