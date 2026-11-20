"""Create-only, offline-replayable archive of one genuine prospective batch."""
from pathlib import Path
import shutil
import subprocess
import sys

from .p1_subset_handoff_v1 import canonical, digest
from .subset_contract_v1 import strict_json
from .subset_p3_v1 import require
from .prospective_s_runtime_v1 import run_forecasts

ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILES = (
    'v2/__init__.py', 'v2/nba_opportunity.py',
    'v2/nba_s_family/__init__.py', 'v2/nba_s_family/model.py',
    'v2/nba_s_family/prospective_fit_v1.py',
    'v2/nba_architecture/__init__.py', 'v2/nba_architecture/v2_contracts.py',
    'v2/nba_architecture/contracts.py',
    'v2/nba_architecture/schema-2.0.0.json',
    'v2/nba_architecture/gamebook_identity_v1.py',
    'v2/nba_architecture/p1_capture_v1.py',
    'v2/nba_architecture/research_profile_v1.py',
    'v2/nba_architecture/p1_subset_handoff_v1.py',
    'v2/nba_architecture/subset_contract_v1.py',
    'v2/nba_architecture/subset_p2_v1.py',
    'v2/nba_architecture/subset_p3_v1.py',
    'v2/nba_architecture/subset_p2_dispatch_v1.py',
    'v2/nba_architecture/prospective_s_sources_v1.py',
    'v2/nba_architecture/prospective_s_admission_v1.py',
    'v2/nba_architecture/prospective_s_runtime_v1.py',
    'v2/nba_architecture/prospective_s_archive_v1.py',
    'scripts/nba_p1_prospective_capture.py', 'scripts/nba_genuine_s.py',
    'config/nba_research_profile.json',
)


def create_archive(output, result, **inputs):
    root = Path(output); root.mkdir(parents=True, exist_ok=False)
    frozen = root/'inputs'; frozen.mkdir()
    shutil.copytree(inputs['raw_dir'], frozen/'raw')
    shutil.copytree(inputs['model_dir'], frozen/'models')
    paths = dict(spec_path='spec.json', policy_path='policy.raw', prefit_path='prefit_decision.md',
        admission_path='artifact_decision.md', model_path='minutes_model.json')
    for key,name in paths.items():shutil.copyfile(inputs[key], frozen/name)
    (frozen/'cohort.json').write_bytes(canonical(inputs['cohort']))
    (root/'forecast.json').write_bytes(canonical(result))
    for name in SOURCE_FILES:
        dest = root/'reader'/name; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, dest)
    require(run_forecasts(**inputs)==result, 'GENUINE_ARCHIVE_INPUT_RESULT_MISMATCH')
    files = {p.relative_to(root).as_posix():dict(sha256=digest(p.read_bytes()),bytes=p.stat().st_size,
        byte_domain='EXACT_ARCHIVED_FILE_BYTES') for p in sorted(root.rglob('*')) if p.is_file()}
    manifest = dict(schema='nba-genuine-S-offline-archive/1.0.0',forecast_at=result['forecast_at'],
        implementation_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True,cwd=ROOT).strip(),
        files=files,candidate_denominator=result['candidate_denominator'],attempt_denominator=result['attempt_denominator'],
        forecasted_rows=result['forecasted_rows'],abstained_rows=result['abstained_rows'],
        payload_sha256=result['payload_sha256'],production_release=False)
    manifest_raw = canonical(manifest); (root/'manifest.json').write_bytes(manifest_raw)
    return dict(manifest_raw_sha256=digest(manifest_raw),file_denominator=len(files),
        candidate_denominator=result['candidate_denominator'],attempt_denominator=result['attempt_denominator'],
        forecasted_rows=result['forecasted_rows'],abstained_rows=result['abstained_rows'])


def verify_archive(output, *, expected_manifest_sha256, python=sys.executable):
    """Verify exact caller-pinned manifest, then invoke archived code in isolation.

    A hash supplied by the caller checks transport only. Admission still requires
    the reviewed registry in the archived reader and full source/fit replay.
    """
    root = Path(output).resolve(); raw = (root/'manifest.json').read_bytes()
    require(ROOT.resolve() != (root/'reader').resolve(),
        'GENUINE_ARCHIVE_EXTERNAL_TRUSTED_READER_REQUIRED')
    require(digest(raw)==expected_manifest_sha256, 'GENUINE_ARCHIVE_MANIFEST_BYTES')
    manifest = strict_json(raw); actual = set()
    require(set(manifest)=={'schema','forecast_at','implementation_commit','files','candidate_denominator',
        'attempt_denominator','forecasted_rows','abstained_rows','payload_sha256','production_release'} and
        manifest['schema']=='nba-genuine-S-offline-archive/1.0.0' and manifest['production_release'] is False,
        'GENUINE_ARCHIVE_MANIFEST_SCOPE')
    require(all(type(manifest[key]) is int and manifest[key]>=0 for key in
        ('candidate_denominator','attempt_denominator','forecasted_rows','abstained_rows')),
        'GENUINE_ARCHIVE_MANIFEST_DENOMINATORS')
    for path in root.rglob('*'):
        require(not path.is_symlink(), 'GENUINE_ARCHIVE_SYMLINK')
        if path.is_file() and path.name!='manifest.json':actual.add(path.relative_to(root).as_posix())
    require(actual==set(manifest['files']), 'GENUINE_ARCHIVE_FILE_POPULATION')
    # A resealed hash manifest grants transport integrity only. The archived
    # executable and admission registry must equal this separately reviewed
    # checkout; an archive cannot appoint its own verification code.
    reader_paths = {'reader/'+name for name in SOURCE_FILES}
    require({name for name in actual if name.startswith('reader/')} == reader_paths,
        'GENUINE_ARCHIVE_READER_POPULATION')
    for name in SOURCE_FILES:
        require((root/'reader'/name).read_bytes() == (ROOT/name).read_bytes(),
            'GENUINE_ARCHIVE_UNREVIEWED_READER_BYTES:'+name)
    for name,item in manifest['files'].items():
        path = root/name
        require(path.resolve().is_relative_to(root) and path.is_file(), 'GENUINE_ARCHIVE_PATH')
        require(digest(path.read_bytes())==item['sha256'] and path.stat().st_size==item['bytes'],
            'GENUINE_ARCHIVE_FILE_BYTES:'+name)
    # The archived CLI computes every result again using only frozen inputs.
    command = [str(python),'-I','-B',str(root/'reader/scripts/nba_genuine_s.py'),
        '_recompute-archive',str(root)]
    child = subprocess.run(command,cwd=root,capture_output=True,text=True)
    require(child.returncode==0, 'GENUINE_ARCHIVE_OFFLINE_REPLAY:'+child.stderr)
    result = strict_json(child.stdout)
    require(result['mode']=='DETERMINISTIC_RECOMPUTATION_ONLY_UNVERIFIED_CODE' and
        result['payload_sha256']==manifest['payload_sha256'], 'GENUINE_ARCHIVE_OUTPUT_JOIN')
    require(result['new_forecast_issued'] is False and all(result[key] == manifest[key]
        for key in ('forecast_at','candidate_denominator','attempt_denominator','forecasted_rows','abstained_rows')),
        'GENUINE_ARCHIVE_REPLAY_DENOMINATOR_JOIN')
    return dict(schema='nba-genuine-S-archive-verification/1.0.0',status='VERIFIED_OFFLINE_REPLAY',
        manifest_raw_sha256=expected_manifest_sha256,command=command,stdout=child.stdout,stderr=child.stderr,
        candidate_denominator=manifest['candidate_denominator'],attempt_denominator=manifest['attempt_denominator'],
        forecasted_rows=manifest['forecasted_rows'],abstained_rows=manifest['abstained_rows'],
        payload_sha256=result['payload_sha256'],new_forecast_issued=False)
