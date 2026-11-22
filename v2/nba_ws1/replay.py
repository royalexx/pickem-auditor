"""Verify retained source bytes and rebuild a bounded capture without network access."""
from dataclasses import asdict
import argparse
import gzip
import json
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from .store import Receipt,NBAPregameFeatureSnapshot,build_snapshot,save_snapshot,canonical,digest
from .adapters import schedule_records,espn_roster_records,espn_boxscore_records,espn_team_records,espn_injury_records


def replay(folder):
    folder=Path(folder);capture=json.loads((folder/'capture_receipt.json').read_text())
    original=json.loads((folder/capture['snapshot_path']).read_text())
    content_hash=original.pop('content_hash')
    if digest(canonical(original).encode())!=content_hash:raise ValueError('CAPTURE_METADATA_HASH_MISMATCH')
    # Only source identities and frozen clocks are read here; all feature values
    # are recomputed from retained raw bytes, never trusted from the old output.
    receipts={r['receipt_id']:Receipt(**r) for r in original['receipts']};records=[];gid=original['game']['game_id']
    for item in capture['sources']:
        path=(folder/item['path']).resolve()
        if not path.is_relative_to(folder.resolve()):raise ValueError('SOURCE_PATH_ESCAPE')
        raw=gzip.decompress(path.read_bytes());r=receipts[item['receipt_id']];r.verify(raw);data=json.loads(raw)
        parsed=urlsplit(r.source);route=parsed.path;query=parse_qs(parsed.query)
        if route.endswith('/scoreboard'):
            records.extend(g for g in schedule_records(data,r) if g.data['game_id']==gid)
        elif route.endswith('/summary'):
            if query['event'][0]==gid.split(':')[-1]:records.extend(espn_injury_records(data,r,game_id=gid))
            else:records.extend(espn_boxscore_records(data,r));records.extend(espn_team_records(data,r))
        elif route.endswith('/roster'):
            team='espn:team:'+route.split('/')[-2]
            records.extend(espn_roster_records(data,r,game_id=gid,team_id=team))
        elif route.endswith('/schedule'):continue
        else:raise ValueError('UNSUPPORTED_CAPTURE_SOURCE')
    return build_snapshot(game_id=gid,forecast_at=original['forecast_at'],input_freeze_at=original['input_freeze_at'],
        model_training_cutoff_at=original['model_training_cutoff_at'],records=records,receipts=list(receipts.values()),
        quote_max_age_seconds=original['market_context']['quote_max_age_seconds'])


def main():
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--expect-hash');p.add_argument('--save',action='store_true');a=p.parse_args()
    s=replay(a.folder)
    if a.expect_hash and s.content_hash!=a.expect_hash:raise ValueError('REPLAY_HASH_MISMATCH')
    if a.save:save_snapshot(s,a.folder/'snapshots')
    print(canonical(dict(content_hash=s.content_hash,status=s.to_dict()['status'],source_bytes_verified=True)))

if __name__=='__main__':main()
