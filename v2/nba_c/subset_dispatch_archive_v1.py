"""Append dispatch evidence to the original immutable research archive.

The base P1-P5 archive and all its reader bytes remain unchanged. A separate
content-addressed namespace binds the new code, optional model candidates and
dispatch wire, and replays from archived copies without original input paths.
"""
from datetime import datetime,timezone
from pathlib import Path
import tempfile

from .subset_archive_v1 import SubsetAuditArchive,_safe_name,_tree
from .warehouse import _write_once
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.subset_contract_v1 import strict_json
from v2.nba_architecture.subset_p2_dispatch_v1 import run_dispatch,provided_inventory
from v2.nba_architecture.subset_p3_v1 import require

VERSION='nba-p2-dispatch-audit-archive/1.0.0'
ROOT=Path(__file__).resolve().parents[2]
READERS=('v2/nba_architecture/subset_p2_dispatch_v1.py',
    'v2/nba_c/subset_dispatch_archive_v1.py','scripts/nba_subset_p2_dispatch.py')


class DispatchAuditArchive:
    def __init__(self,root):
        self.base=SubsetAuditArchive(root);self.root=Path(root)/'p2_fixed_exposure_dispatch'

    def _object(self,sha):
        self.base._object(sha)  # Reuse the strict content-address format check.
        return self.root/'objects'/(sha+'.bin')

    def _record(self,sha):
        self.base._record(sha)
        return self.root/'records'/(sha+'.json')

    def _manifest(self,base_id,dispatch_raw,model_status,models,codes):
        require(set(codes)==set(READERS),'DISPATCH_ARCHIVE_READER_POPULATION')
        for name,raw in codes.items():require(raw==(ROOT/name).read_bytes(),'DISPATCH_ARCHIVE_READER_CHANGED:'+name)
        base=self.base.read(base_id)
        files={}
        for name,reference in base['objects'].items():
            raw=self.base._object(reference['sha256']).read_bytes()
            require(digest(raw)==reference['sha256'],'DISPATCH_ARCHIVE_BASE_OBJECT_CHANGED')
            files[name]=raw
        require(model_status in ('NOT_PROVIDED','MISSING','PROVIDED'),'DISPATCH_ARCHIVE_MODEL_DIRECTORY_STATUS')
        require(model_status=='PROVIDED' or not models,'DISPATCH_ARCHIVE_MODEL_POPULATION')
        with tempfile.TemporaryDirectory(prefix='p2-dispatch-replay-') as temporary:
            tmp=Path(temporary);(tmp/'capture').mkdir();(tmp/'history').mkdir()
            for name,raw in files.items():
                if name.startswith('inputs/'):
                    path=tmp/_safe_name(name.removeprefix('inputs/'));path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            model_dir=None
            if model_status=='MISSING':model_dir=tmp/'absent-models'
            elif model_status=='PROVIDED':
                model_dir=tmp/'models';model_dir.mkdir()
                for name,raw in models.items():
                    path=model_dir/_safe_name(name);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            cohort=strict_json(files['inputs/cohort.json']);p3_raw=files['outputs/p3.json'];p3=strict_json(p3_raw)
            expected=run_dispatch(files['outputs/p1.json'],p3_raw,capture_dir=tmp/'capture',cohort=cohort,
                history_dir=tmp/'history',model_path=tmp/'model.json',forecast_at=p3['forecast_at'],model_dir=model_dir)
            require(canonical(strict_json(dispatch_raw))==canonical(expected),'DISPATCH_ARCHIVE_SOURCE_OR_OUTPUT_MISMATCH')
        return dict(schema=VERSION,kind='REPLAY_VERIFIED_FIXED_EXPOSURE_DISPATCH_AUDIT',
            base_record_id=base_id,dispatch=dict(sha256=digest(dispatch_raw),bytes=len(dispatch_raw),byte_domain='EXACT_DISPATCH_WIRE_BYTES'),
            model_directory_status=model_status,model_files={name:dict(sha256=digest(raw),bytes=len(raw),byte_domain='EXACT_PROVIDED_MODEL_EVIDENCE_BYTES') for name,raw in sorted(models.items())},
            reader_files={name:dict(sha256=digest(raw),bytes=len(raw),byte_domain='EXACT_EXECUTING_READER_BYTES') for name,raw in sorted(codes.items())},
            candidate_denominator=expected['candidate_denominator'],dispatch_attempts=expected['attempt_denominator'],
            exposure_bound_rows=expected['exposure_bound_rows'],statistic_forecast_records=expected['forecasted_rows'],
            dispatch_abstentions=expected['abstained_rows'],model_candidate_denominator=expected['model_candidate_denominator'],
            provided_file_denominator=expected['provided_file_denominator'],
            original_attempt_records=base['counts']['total_attempt_records'],
            combined_attempt_records=base['counts']['total_attempt_records']+expected['attempt_denominator'],
            conditioning=expected['conditioning'],exposure_variant=expected['exposure_variant'],
            minute_uncertainty_integrated=False,model_admission_granted=False,scoring_admitted=False,
            production_release=False)

    def put(self,base_record_id,dispatch_raw,*,model_dir=None):
        require(type(dispatch_raw) is bytes,'DISPATCH_ARCHIVE_WIRE_BYTES')
        status,_=provided_inventory(model_dir)
        models={name.removeprefix('models/'):raw for name,raw in _tree(model_dir,'models').items()} if status=='PROVIDED' else {}
        codes={name:(ROOT/name).read_bytes() for name in READERS}
        manifest=self._manifest(base_record_id,dispatch_raw,status,models,codes)
        for raw in [dispatch_raw,*models.values(),*codes.values()]:_write_once(self._object(digest(raw)),raw)
        raw=canonical(manifest)+b'\n';record_id=digest(raw);created=_write_once(self._record(record_id),raw)
        return dict(schema=VERSION,record_id=record_id,base_record_id=base_record_id,created=created,
            operation_completed_at=datetime.now(timezone.utc).isoformat(),
            dispatch_attempts=manifest['dispatch_attempts'],exposure_bound_rows=manifest['exposure_bound_rows'],
            statistic_forecast_records=manifest['statistic_forecast_records'],dispatch_abstentions=manifest['dispatch_abstentions'])

    def read(self,record_id):
        raw=self._record(record_id).read_bytes();require(digest(raw)==record_id,'DISPATCH_ARCHIVE_RECORD_BYTES')
        value=strict_json(raw);require(raw==canonical(value)+b'\n','DISPATCH_ARCHIVE_RECORD_CANONICAL')
        def fetch(reference):
            body=self._object(reference['sha256']).read_bytes()
            require(digest(body)==reference['sha256'] and len(body)==reference['bytes'],'DISPATCH_ARCHIVE_OBJECT_BYTES')
            return body
        models={_safe_name(name):fetch(ref) for name,ref in value['model_files'].items()}
        codes={_safe_name(name):fetch(ref) for name,ref in value['reader_files'].items()}
        expected=self._manifest(value['base_record_id'],fetch(value['dispatch']),value['model_directory_status'],models,codes)
        require(canonical(value)==canonical(expected),'DISPATCH_ARCHIVE_RESEALED_CLAIM')
        return value
