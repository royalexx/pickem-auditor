"""Read-only existing-byte admission evidence; never fits or grants admission."""
import argparse
import base64
import hashlib
import json
import subprocess
from pathlib import Path
from datetime import datetime

VERSION = 'nba-p234-artifact-inspection/1.0.0'
MODEL = 'research/nba_ws2/results/model.json'
EXPECTED = 'ea7eae3afc760eafda0fbf0dbdccd2cb77b31b0aca54fc3606b4b31ba90693de'
CUTOFF = '2018-10-18T00:00:00Z'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def inspect_ws2(raw, *, declared_cutoff=CUTOFF):
    """Inspect only the exact preserved model; caller cannot install a root."""
    if sha(raw) != EXPECTED:
        raise ValueError('ALTERED_OR_UNREVIEWED_FITTED_BYTES')
    model = json.loads(raw)
    parse = lambda x: datetime.fromisoformat(x.replace('Z', '+00:00'))
    cutoff = parse(declared_cutoff)
    if cutoff.tzinfo is None:
        raise ValueError('CUTOFF_TIMEZONE_REQUIRED')
    reasons = ['TRAINING_OBSERVATION_BYTES_AND_AVAILABILITY_UNVERIFIED',
               'TRAINING_MANIFEST_PREIMAGE_UNVERIFIED',
               'SUPPORTED_IDENTITIES_UNVERIFIED',
               'NO_INDEPENDENT_FITTED_ARTIFACT_ADMISSION']
    if parse(model['training_cutoff_at']) > cutoff:
        reasons.insert(0, 'MODEL_AFTER_DECLARED_CUTOFF')
    return dict(schema=VERSION, status='EXISTING_BUT_INADMISSIBLE',
                artifact_sha256=sha(raw), artifact_byte_domain='REPOSITORY_FILE_UTF8',
                declared_cutoff_at=declared_cutoff,
                model_cutoff_at=model['training_cutoff_at'],
                producer_commit=model['code_commit'],
                training_manifest_reference=model['training_manifest_sha256'],
                statistic='minutes', conditioning='given_played',
                model_variants=['M0', 'M1', 'M2'], family=model['family'],
                genuine_participation_probability=None,
                training_rows_admitted=0, blockers=reasons)


def inspect_repository(root):
    root = Path(root)
    ws2 = inspect_ws2((root / MODEL).read_bytes())
    text_path = 'docs/nba_architecture/substantive_remediation_20261117/source_search/ws2-model.tool-text.json'
    text_raw = (root / text_path).read_bytes()
    nuts_path = 'config/provisional_nuts_artifacts.json'
    nuts_raw = (root / nuts_path).read_bytes()
    nuts = json.loads(nuts_raw)
    # A manifest is not the fitted bytes. Do not dereference/decompress posteriors.
    nba = [m for m in nuts['models'] if m['sport'] == 'NBA']
    synthetic_path = 'docs/nba_architecture/g1_accounting_repair_20261117/before/hidden_credit_rounding_adversary.json'
    probe = json.loads((root/synthetic_path).read_bytes())
    fitted = probe['fitted_artifact']
    payload = base64.b64decode(fitted['raw_base64'], validate=True)
    if sha(payload) != fitted['raw_sha256']:
        raise ValueError('PRESERVED_SYNTHETIC_ARTIFACT_HASH_MISMATCH')
    saved = json.loads(payload)
    return dict(schema=VERSION,
                tested_commit=subprocess.check_output(['git','rev-parse','HEAD'], cwd=root, text=True).strip(),
                horizon=dict(game_id='espn:game:401070219', cutoff_at=CUTOFF),
                artifacts=[dict(path=MODEL, **ws2),
                  dict(path=synthetic_path, artifact_sha256=sha(payload),
                       byte_domain='BASE64_DECODED_FITTED_PAYLOAD',
                       family=saved['family'], stat=saved['stat'],
                       training_cutoff_at=saved['training_cutoff_at'],
                       training_rows=len(saved['training_rows']),
                       status='SYNTHETIC_ENGINEERING_ONLY_NOT_GENUINE_FIT'),
                  dict(path=text_path, raw_sha256=sha(text_raw),
                       byte_domain='TOOL_RETURNED_UTF8_PROJECT_FILE_TEXT',
                       same_json_value=json.loads(text_raw)==json.loads((root/MODEL).read_bytes()),
                       status='UNADMITTED_TEXT_COPY_NOT_SECOND_FIT'),
                  dict(path=nuts_path, raw_sha256=sha(nuts_raw),
                       byte_domain='REPOSITORY_FILE_UTF8_MANIFEST_ONLY',
                       nba_references=nba, fitted_bytes_verified=False,
                       status=('REFERENCED_NBA_POSTERIORS_NOT_ADMITTED' if nba else 'NO_NBA_REFERENCES_IN_THIS_MANIFEST'))],
                denominators=dict(inventory_members=4, admitted_members=0,
                                  target_eligible_players=None, real_handoffs=0),
                criteria={k:dict(status='BLOCKED', independent_decision='PENDING', dependency=v)
                    for k,v in {
                      'B-P2-01':'No independently admitted S fitted bytes/training availability/roles for frozen horizon.',
                      'B-P3-01':'WS2 conditional minutes exists but is late and unadmitted; genuine participation fit and original complete roster/role priors unavailable.',
                      'B-P4-01':'No admitted source/S/O joins or accepted WP3 physical law; native bounded-coupling consumer closure unimplemented.'}.items()})


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', default='.')
    args = p.parse_args()
    print(json.dumps(inspect_repository(args.root), indent=2, sort_keys=True, allow_nan=False))
