"""Append-only research audit archive; never statistic-scoring admission.

Validate immutable input buffers from archived copies, retain every abstention,
and reuse native C's exclusive write-once primitive. No model or source is
admitted by a caller label, digest or structural archive record.
"""
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath
import re
import tempfile

from .warehouse import _write_once,WarehouseError
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.subset_contract_v1 import strict_json
from v2.nba_architecture.subset_p3_v1 import require
from v2.nba_architecture.subset_p4_v1 import read_p4

VERSION='nba-subset-research-audit-archive/1.0.0'
ROOT=Path(__file__).resolve().parents[2]
READERS=(
    'config/nba_research_profile.json',
    'scripts/nba_subset_pipeline.py','scripts/nba_p1_prospective_capture.py',
    'v2/nba_architecture/p1_capture_v1.py',
    'v2/nba_architecture/p1_subset_handoff_v1.py',
    'v2/nba_architecture/research_profile_v1.py',
    'v2/nba_architecture/gamebook_identity_v1.py',
    'v2/nba_architecture/subset_contract_v1.py',
    'v2/nba_architecture/subset_p2_v1.py','v2/nba_architecture/subset_p3_v1.py',
    'v2/nba_architecture/subset_p4_v1.py',
    'v2/nba_architecture/v2_contracts.py','v2/nba_architecture/families_v2.py',
    'v2/nba_opportunity.py','v2/nba_s_family/model.py',
    'v2/nba_c/warehouse.py','v2/nba_c/subset_archive_v1.py')


def _safe_name(name):
    require(isinstance(name,str) and name and '\\' not in name,'SUBSET_ARCHIVE_PATH')
    path=PurePosixPath(name)
    require(not path.is_absolute() and '..' not in path.parts and str(path)==name,'SUBSET_ARCHIVE_PATH')
    return name


def _tree(root,prefix):
    root=Path(root);require(root.is_dir() and not root.is_symlink(),'SUBSET_ARCHIVE_INPUT_DIRECTORY')
    result={}
    for file in sorted(root.rglob('*')):
        require(not file.is_symlink(),'SUBSET_ARCHIVE_SYMLINK')
        if file.is_file():result[_safe_name(prefix+'/'+file.relative_to(root).as_posix())]=file.read_bytes()
    return result


def _domain(name):
    if name.startswith('readers/'):return 'EXACT_READER_OR_CONFIGURATION_FILE_BYTES'
    if name.startswith('outputs/'):return 'EXACT_PUBLIC_HANDOFF_WIRE_BYTES'
    if name=='inputs/model.json':return 'ORIGINAL_SAVED_MODEL_FILE_BYTES'
    if name=='inputs/cohort.json':return 'CANONICAL_JSON_FROZEN_COHORT'
    if name.endswith('/body.raw'):return 'CAPTURED_HTTP_BODY_BYTES_SEE_ORIGINAL_RECEIPT'
    if name.endswith('/receipt.json'):return 'ORIGINAL_CAPTURE_RECEIPT_UTF8_JSON'
    return 'ORIGINAL_CAPTURE_SUPPORT_FILE_BYTES'


def _validate_snapshot(files):
    required={'inputs/cohort.json','inputs/model.json'}|{'outputs/'+s+'.json' for s in ('p1','p2','p3','p4')}|{'readers/'+r for r in READERS}
    require(required<=set(files),'SUBSET_ARCHIVE_REQUIRED_OBJECT_MISSING')
    for name,raw in files.items():
        _safe_name(name);require(type(raw) is bytes,'SUBSET_ARCHIVE_BYTE_DOMAIN')
        require(name in required or name.startswith(('inputs/capture/','inputs/history/')),'SUBSET_ARCHIVE_UNSUPPORTED_OBJECT')
    require({n for n in files if n.startswith('readers/')}=={'readers/'+r for r in READERS},'SUBSET_ARCHIVE_READER_POPULATION')
    for reader in READERS:
        require(files['readers/'+reader]==(ROOT/reader).read_bytes(),'SUBSET_ARCHIVE_EXECUTING_READER_CHANGED:'+reader)
    cohort=strict_json(files['inputs/cohort.json'])
    outputs={s:files['outputs/'+s+'.json'] for s in ('p1','p2','p3','p4')}
    with tempfile.TemporaryDirectory(prefix='nba-subset-archive-replay-') as directory:
        tmp=Path(directory);(tmp/'capture').mkdir();(tmp/'history').mkdir()
        for name,raw in files.items():
            if name.startswith('inputs/'):
                destination=tmp/name.removeprefix('inputs/');destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(raw)
        p3=strict_json(outputs['p3'])
        p4=read_p4(outputs['p4'],p2_raw=outputs['p2'],p3_raw=outputs['p3'],source_raw=outputs['p1'],
            capture_dir=tmp/'capture',cohort=cohort,history_dir=tmp/'history',
            model_path=tmp/'model.json',forecast_at=p3['forecast_at'])
        # These exact wires were source/model replayed by the public P4 reader.
        p2=strict_json(outputs['p2']);p1=strict_json(outputs['p1'])
    return dict(candidate_denominator=p1['requests']['source_candidate_rows'],
        source_ready_candidates=p1['requests']['source_ready_rows'],
        source_abstained_candidates=p1['requests']['abstained_source_rows'],
        prior_observation_denominator=p3['observation_denominator'],
        p2_attempts=p2['attempt_denominator'],p3_attempts=p3['attempt_denominator'],p4_attempts=p4['attempt_denominator'],
        total_attempt_records=p2['attempt_denominator']+p3['attempt_denominator']+p4['attempt_denominator'],
        conditional_minute_forecast_records=p3['forecasted_rows'],
        statistic_forecast_records=p2['forecasted_rows']+p4['statistic_forecasted_rows'],
        explicit_abstention_records=p2['abstained_rows']+p3['abstained_rows']+p4['abstained_rows'],
        native_minute_laws_consumed=p4['native_minute_laws_read'],
        minute_stat_references=p4['minute_stat_references'],
        forecast_at=p3['forecast_at'],input_freeze_at=p3['input_freeze_at'],event_start_at=p3['event_start_at'])


def _manifest(files):
    counts=_validate_snapshot(files)
    return dict(schema=VERSION,kind='REPLAY_VERIFIED_SUBSET_RESEARCH_AUDIT',
        profile='source_listed_subset',objects={name:dict(sha256=digest(raw),bytes=len(raw),byte_domain=_domain(name)) for name,raw in sorted(files.items())},
        counts=counts,source_admission='RESEARCH_BYTES_CONSISTENCY_ONLY',
        model_admission='PINNED_EXPLORATORY_WS2_REUSE_ONLY',
        participation_probability=None,legal_roster_completeness=None,correction_history_complete=None,
        original_historical_pregame_availability=None,scoring_admitted=False,
        joint_family_accepted=False,production_release=False)


class SubsetAuditArchive:
    """Separate namespace from native forecast/outcome scoring warehouses."""
    def __init__(self,root):self.root=Path(root)/'subset_research_audit'

    def _object(self,sha):
        require(isinstance(sha,str) and re.fullmatch('[0-9a-f]{64}',sha),'SUBSET_ARCHIVE_OBJECT_ID')
        return self.root/'objects'/sha[:2]/(sha+'.bin')

    def _record(self,sha):
        require(isinstance(sha,str) and re.fullmatch('[0-9a-f]{64}',sha),'SUBSET_ARCHIVE_RECORD_ID')
        return self.root/'records'/(sha+'.json')

    def put(self,outputs,*,capture_dir,cohort,history_dir,model_path):
        require(isinstance(outputs,dict) and set(outputs)=={'p1','p2','p3','p4'} and all(type(v) is bytes for v in outputs.values()),'SUBSET_ARCHIVE_STAGE_POPULATION')
        files={'inputs/cohort.json':canonical(cohort),'inputs/model.json':Path(model_path).read_bytes()}
        files.update(_tree(capture_dir,'inputs/capture'));files.update(_tree(history_dir,'inputs/history'))
        files.update({'outputs/'+stage+'.json':raw for stage,raw in outputs.items()})
        files.update({'readers/'+name:(ROOT/name).read_bytes() for name in READERS})
        # Validate the exact immutable buffers to be stored, avoiding path races.
        manifest=_manifest(files);raw=canonical(manifest)+b'\n';record_id=digest(raw)
        for value in files.values():_write_once(self._object(digest(value)),value)
        created=_write_once(self._record(record_id),raw)
        # This is the actual archive-operation clock, separate from source clocks.
        return dict(schema=VERSION,record_id=record_id,created=created,
            operation_completed_at=datetime.now(timezone.utc).isoformat(),counts=manifest['counts'],
            manifest_byte_domain='CANONICAL_JSON_WITH_TERMINAL_LF',
            source_or_model_admission_granted=False,scoring_admitted=False)

    def read(self,record_id):
        raw=self._record(record_id).read_bytes()
        require(digest(raw)==record_id,'SUBSET_ARCHIVE_MANIFEST_BYTES_CHANGED')
        value=strict_json(raw)
        require(isinstance(value,dict) and isinstance(value.get('objects'),dict),'SUBSET_ARCHIVE_MANIFEST_SCHEMA')
        require(raw==canonical(value)+b'\n','SUBSET_ARCHIVE_NONCANONICAL_MANIFEST')
        files={}
        for name,reference in value['objects'].items():
            _safe_name(name)
            require(isinstance(reference,dict) and set(reference)=={'sha256','bytes','byte_domain'},'SUBSET_ARCHIVE_OBJECT_REFERENCE_SCHEMA')
            try:body=self._object(reference['sha256']).read_bytes()
            except FileNotFoundError as exc:raise WarehouseError('SUBSET_ARCHIVE_OBJECT_MISSING:'+name) from exc
            require(digest(body)==reference['sha256'] and len(body)==reference['bytes'],'SUBSET_ARCHIVE_OBJECT_BYTES_CHANGED:'+name)
            files[name]=body
        expected=_manifest(files)
        require(canonical(value)==canonical(expected),'SUBSET_ARCHIVE_RESEALED_CLAIM_OR_REPLAY_MISMATCH')
        return value
