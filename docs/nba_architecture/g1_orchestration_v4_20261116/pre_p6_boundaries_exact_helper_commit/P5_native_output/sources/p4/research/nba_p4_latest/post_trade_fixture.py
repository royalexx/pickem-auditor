"""New temporary synthetic profile for a dated historical team/role change.

Original committed fixtures are copied and never modified. The new prior is
fitted by the actual P2 owner API; no authentic-source status is asserted.
"""
from copy import deepcopy
import json
from pathlib import Path
import shutil

from research.nba_p4_latest.fixture import build
from v2.nba_architecture.v2_contracts import digest
from v2.nba_joint.latest_upstream import FIXTURES, load_upstream, raw_sha


def create(root, destination):
    destination=Path(destination)
    shutil.copytree(FIXTURES,destination)
    inputs=list(build(root));p2,_=load_upstream(root)
    artifacts=dict(inputs[4]);manifest=deepcopy(inputs[5])
    raw_sources=json.loads((FIXTURES/'raw_sources.json').read_bytes())
    old=artifacts['points'].data;rows=deepcopy(old['training_rows']);row=rows[0]
    old_receipt=row['source_receipt_sha256']
    source=manifest.pop(old_receipt)
    document=json.loads(raw_sources.pop(old_receipt))
    document.update(team_id='espn:team:former',role='previous_role')
    raw=p2.canonical(document)
    new_receipt=raw_sha(b'new-synthetic-post-trade-receipt:'+raw)
    source['raw_sha256']=raw_sha(raw)
    game=source['games'][row['game_id']]
    game['players'][row['player_id']]='espn:team:former'
    game['duration_receipt_sha256']=new_receipt
    manifest[new_receipt]=source;raw_sources[new_receipt]=raw.decode('ascii')
    row.update(team_id='espn:team:former',role='previous_role',
        source_receipt_sha256=new_receipt,source_raw_sha256=raw_sha(raw))
    artifacts['points']=p2.fit(rows,asof_cutoff_utc=old['training_cutoff_at'],
        source_manifest=manifest,stat='points',family=old['family'],
        hyperparameters=old['hyperparameters'],seed=old['seed'])
    raw_collection=p2.canonical(raw_sources)
    trust=json.loads((FIXTURES/'trust.json').read_bytes())
    trust['artifacts']['points']=artifacts['points'].artifact_sha256
    trust['source_manifest_sha256']=digest(manifest)
    trust['raw_sources_sha256']=raw_sha(raw_collection)
    (destination/'trust.json').write_bytes(p2.canonical(trust))
    (destination/'raw_sources.json').write_bytes(raw_collection)
    (destination/'points.json').write_bytes(artifacts['points'].payload)
    inputs[4],inputs[5]=artifacts,manifest
    return tuple(inputs)
