"""One preregistered prospective S1 artifact batch; never historical replacement.

The compiled independent approval pin starts closed. It may be populated only
after the exact reader/protocol review, then a separate artifact review is still
required before genuine forecast admission. No tuning, scoring or sampler.
"""
from datetime import datetime,timezone
from pathlib import Path
import subprocess

from . import model as native
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.prospective_s_sources_v1 import build_dataset,SPEC_SHA,RULE_SHA
from v2.nba_architecture.subset_p3_v1 import require
from v2.nba_opportunity import utc

PREFIT_APPROVAL_SHA='a76ce1e31d029edecc30b57d9ee7dd37941cb31fc697c5c01b0566c18b9fe558'
APPROVED_READER_SHA='8b61c753a41b59b9baad25ce179bd56ef3ceaf31645e76998b6408f296a447fd'
APPROVED_DATASET_SHA='e5cb76ef446d6651b718c6279367a7078ffa86f01b621cfbfd9c7b4d74adbd1d'
PARAMETERS=dict(prior_minutes=180.,prior_attempts=40.,dispersion=12.,min_player_games=2)
SEED=20261120
NATIVE_SHA='a63a469d8df74f6e6f82c7480ee289da443452dd62f603859629a5d821d28cd6'


def _now():return datetime.now(timezone.utc).isoformat()


def fit_prospective(raw_dir,spec_path,policy_path,approval_path,output):
    """Rebuild admitted inputs from original captures; no caller history rows."""
    require(PREFIT_APPROVAL_SHA is not None,'INDEPENDENT_PREFIT_APPROVAL_NOT_COMPILED')
    approval=Path(approval_path).read_bytes()
    require(digest(approval)==PREFIT_APPROVAL_SHA,'INDEPENDENT_PREFIT_APPROVAL_BYTES')
    require(digest(Path(native.__file__).read_bytes())==NATIVE_SHA,'UNREVIEWED_NATIVE_S_FIT_CODE')
    data=build_dataset(raw_dir,spec_path,policy_path)
    require(data['reader_raw_sha256']==APPROVED_READER_SHA and data['payload_sha256']==APPROVED_DATASET_SHA,'UNREVIEWED_SOURCE_READER_OR_DATASET')
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    source_manifest=canonical(data['source_manifest']);raw_sources=canonical(data['raw_sources'])
    (out/'source_manifest.json').write_bytes(source_manifest);(out/'raw_sources.json').write_bytes(raw_sources)
    (out/'source_dataset.json').write_bytes(canonical(data))
    started=_now();require(utc(data['data_cutoff_at'])<=utc(started),'FIT_BEFORE_DATA_CUTOFF')
    artifacts={}
    for statistic,rows in data['histories'].items():
        fitted=native.fit(rows,asof_cutoff_utc=data['data_cutoff_at'],source_manifest=data['source_manifest'],
            stat=statistic,family='S1',hyperparameters=PARAMETERS,seed=SEED)
        path=out/(statistic+'.json')
        with path.open('xb') as stream:stream.write(fitted.payload)
        artifacts[statistic]=dict(sha256=fitted.artifact_sha256,bytes=len(fitted.payload),training_rows=len(rows),
            last_game_start_at=fitted.data['last_game_start_at'],last_outcome_available_at=fitted.data['last_outcome_available_at'])
    completed=_now()
    for statistic,item in artifacts.items():require(digest((out/(statistic+'.json')).read_bytes())==item['sha256'],'FITTED_ARTIFACT_WRITE_VERIFY')
    verified=_now()
    require(utc(started)<=utc(completed)<=utc(verified),'FIT_OR_VERIFICATION_CLOCK_REVERSED')
    receipt=dict(schema='nba-new-prospective-S1-fit/1.0.0',kind='NEW_PROSPECTIVE_BASELINE_NOT_HISTORICAL_REPLACEMENT',
        implementation_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        fit_code_sha256=digest(Path(__file__).read_bytes()),native_code_sha256=digest(Path(native.__file__).read_bytes()),
        prefit_approval_raw_sha256=PREFIT_APPROVAL_SHA,source_reader_sha256=data['reader_raw_sha256'],
        prefit_spec_raw_sha256=SPEC_SHA,timing_rule_raw_sha256=RULE_SHA,source_dataset_sha256=data['payload_sha256'],
        source_dataset_raw_sha256=digest(canonical(data)),source_manifest_raw_sha256=digest(source_manifest),raw_sources_raw_sha256=digest(raw_sources),
        data_cutoff_at=data['data_cutoff_at'],fit_started_at=started,fit_completed_at=completed,artifact_bytes_verified_at=verified,
        artifacts=artifacts,source_observation_denominator=data['source_observation_denominator'],
        training_attempt_denominator=data['training_attempt_denominator'],included_training_attempts=data['included_training_attempts'],
        excluded_training_attempts=data['excluded_training_attempts'],fixed_hyperparameters=PARAMETERS,seed=SEED,
        target=data['target'],model_admission='PENDING_SEPARATE_INDEPENDENT_ARTIFACT_REVIEW',
        holdout_scoring=False,tuning=False,weight_optimization=False,nuts=False,production_release=False)
    (out/'fit_receipt.json').write_bytes(canonical(receipt))
    (out/'SHA256SUMS').write_text(''.join(digest(p.read_bytes())+'  '+p.name+'\n' for p in sorted(out.iterdir()) if p.is_file() and p.name!='SHA256SUMS'))
    return receipt
