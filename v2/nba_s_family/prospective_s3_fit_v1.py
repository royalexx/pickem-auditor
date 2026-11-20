"""Closed-gate new prospective S3 artifact; never a historical replacement."""
from pathlib import Path
from datetime import datetime,timezone
import subprocess
from . import model as native
from v2.nba_architecture.prospective_s_sources_v1 import build_dataset
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.subset_p3_v1 import require
from v2.nba_opportunity import utc

APPROVAL_SHA='1e8e21143d8aba0afc53483f85e82af22c941c85f64091e9bd32a83bde734cd5'
READER_SHA='8b61c753a41b59b9baad25ce179bd56ef3ceaf31645e76998b6408f296a447fd'
DATASET_SHA='e5cb76ef446d6651b718c6279367a7078ffa86f01b621cfbfd9c7b4d74adbd1d'
NATIVE_SHA='a63a469d8df74f6e6f82c7480ee289da443452dd62f603859629a5d821d28cd6'
CUTOFF='2026-11-20T01:07:00.131517+00:00'
PARAMETERS=dict(prior_minutes=180.,prior_attempts=40.,dispersion=12.,min_player_games=2)
SEED=20261120


def now():return datetime.now(timezone.utc).isoformat()


def fit_new_s3(raw_dir,spec_path,policy_path,approval_path,output):
    require(APPROVAL_SHA is not None,'S3_INDEPENDENT_PREFIT_CLOSED')
    require(digest(Path(approval_path).read_bytes())==APPROVAL_SHA,'S3_PREFIT_APPROVAL_BYTES')
    require(digest(Path(native.__file__).read_bytes())==NATIVE_SHA,'S3_NATIVE_FIT_CODE')
    data=build_dataset(raw_dir,spec_path,policy_path)
    require(data['reader_raw_sha256']==READER_SHA and data['payload_sha256']==DATASET_SHA
        and data['data_cutoff_at']==CUTOFF,'S3_FROZEN_READER_DATA_CUTOFF')
    require(len(data['histories']['threes'])==456 and data['role_semantics']=='ESPN_POSITION_BIN_OBSERVED_AT_CAPTURE',
        'S3_PREFIT_ROWS_ROLES')
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    started=now();require(utc(CUTOFF)<=utc(started),'S3_FIT_BEFORE_SOURCE_CUTOFF')
    fitted=native.fit(data['histories']['threes'],asof_cutoff_utc=CUTOFF,source_manifest=data['source_manifest'],
        stat='threes',family='S3',hyperparameters=PARAMETERS,seed=SEED)
    completed=now();raw=fitted.payload
    with (out/'three_conversion.json').open('xb') as f:f.write(raw)
    require(digest((out/'three_conversion.json').read_bytes())==fitted.artifact_sha256,'S3_ARTIFACT_WRITE_VERIFICATION')
    verified=now();require(utc(started)<=utc(completed)<=utc(verified),'S3_FIT_CLOCK_REVERSED')
    receipt=dict(schema='nba-new-prospective-S3-fit/1',kind='NEW_PROSPECTIVE_NOT_HISTORICAL_REPLACEMENT',
        implementation_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        writer_raw_sha256=digest(Path(__file__).read_bytes()),native_raw_sha256=NATIVE_SHA,
        source_reader_raw_sha256=READER_SHA,source_dataset_sha256=DATASET_SHA,
        source_manifest_raw_sha256=digest(canonical(data['source_manifest'])),
        source_body_map_raw_sha256=digest(canonical(data['raw_sources'])),
        prefit_approval_raw_sha256=APPROVAL_SHA,artifact_raw_sha256=fitted.artifact_sha256,
        training_cutoff_at=CUTOFF,fit_started_at=started,fit_completed_at=completed,artifact_verified_at=verified,
        stat='threes',family='S3',training_rows=456,source_observations=698,training_attempts_all_stats=2792,
        source_role_semantics=data['role_semantics'],hyperparameters=PARAMETERS,seed=SEED,
        model_admission='PENDING_SEPARATE_REAL_ARTIFACT_REVIEW',J_admitted=False,
        historical_scoring=False,new_weights_fitted=False,NUTS=False,production_release=False)
    with (out/'FIT_RECEIPT.json').open('xb') as f:f.write(canonical(receipt))
    (out/'SHA256SUMS').write_text(''.join(digest(f.read_bytes())+'  '+f.name+'\n' for f in sorted(out.iterdir()) if f.name!='SHA256SUMS'))
    return receipt
