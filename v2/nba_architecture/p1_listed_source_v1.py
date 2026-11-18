"""Opt-in completed-game listed population; never a target eligible roster."""
import hashlib
import json
from pathlib import Path
from .admission_v1 import admit_gamebook
from .gamebook_identity_v1 import join_game_ids
from .v2_contracts import req, instant

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / 'docs/nba_architecture/p1_source_admission_20261118'
CAPABILITY = 'COMPLETED_GAME_LISTED_IDENTITY_ONLY'
REGISTRY_SHA256 = 'b69777038b2bf8c5301ea0a2e892667553d0abcab04cf7aff9ee0c2a4e799122'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_listed_population(pdf, pdf_receipt, espn, receipt, *,
                           required_capability=CAPABILITY, input_freeze_at=None):
    """On failure reject the whole bundle; no accepted subset is returned."""
    root_path = PACKET / 'installed_identity_root.json'
    req(root_path.is_file(), 'P1_LISTED_ROOT_UNINSTALLED')
    root_raw = root_path.read_bytes()
    req(digest(root_raw) == REGISTRY_SHA256, 'P1_LISTED_ROOT_CHANGED')
    root = json.loads(root_raw)
    req(required_capability == CAPABILITY, 'P1_LISTED_CAPABILITY_UNSUPPORTED')
    req(digest(espn) == root['espn_raw_sha256'], 'P1_LISTED_SOURCE_UNREVIEWED')
    receipt_raw = json.dumps(receipt, sort_keys=True, separators=(',', ':')).encode()
    req(digest(receipt_raw) == root['receipt_canonical_sha256'], 'P1_LISTED_RECEIPT_CHANGED')
    for relative, expected in root['bindings'].items():
        req(digest((ROOT / relative).read_bytes()) == expected, 'P1_LISTED_BINDING_CHANGED')
    if input_freeze_at is not None:
        req(instant(receipt['retrieved_at']) <= instant(input_freeze_at), 'P1_LISTED_LATE_CAPTURE')
        # This capability never establishes original pregame availability.
        req(False, 'P1_LISTED_NOT_PREGAME')
    box = admit_gamebook(pdf, pdf_receipt, required_capability='OFFICIAL_PRINTED_BOX_SCORE')['source']
    source = json.loads(espn)
    req(str(source['header']['id']) == '401070213', 'P1_LISTED_GAME')
    req({t['team']['abbreviation']: str(t['team']['id']) for t in source['boxscore']['players']}
        == {'PHI': '20', 'BOS': '2'}, 'P1_LISTED_TEAMS')
    joined = join_game_ids(box, espn, receipt)
    rows = [dict(identity, **{k: value for k, value in row.items() if k not in identity},
                 target_eligible=None, genuine_participation_probability=None)
            for identity, row in zip(joined['rows'], box['rows'])]
    req(len(rows) == 26, 'P1_LISTED_POPULATION')
    return dict(schema='nba-p1-listed-source/1.0.0', capability=CAPABILITY,
                rows=rows, attempted_rows=26, accepted_rows=26, rejected_rows=0,
                target_eligible_roster_count=None, identity_scope='THIS_COMPLETED_GAME_ONLY',
                source_raw_sha256=digest(espn), pdf_raw_sha256=digest(pdf),
                retrieval_started_at=receipt['retrieved_at'],
                retrieval_completed_at=receipt['completed_at'], ingested_at=None,
                source_published_at=None, original_pregame_available_at=None,
                correction_history_complete=None, predecessor_sha256=None,
                duration_minutes=box['duration_minutes'], overtime_periods=box['overtime_periods'],
                fitted_model_admitted=False, original_pregame_certified=False)
