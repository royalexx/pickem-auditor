#!/usr/bin/env python3
"""Bounded genuine S1 shadow forecast and deterministic offline replay.

No schedule, historical forecast replacement, scoring or trusted publication.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from v2.nba_architecture.p1_subset_handoff_v1 import canonical, digest
from v2.nba_architecture.prospective_s_sources_v1 import SPEC_SHA
from v2.nba_architecture.subset_contract_v1 import strict_json
from v2.nba_architecture.subset_p3_v1 import require
from v2.nba_architecture.prospective_s_runtime_v1 import run_forecasts, read_forecasts


def frozen_inputs(root):
    p=Path(root)/'inputs'
    return dict(raw_dir=p/'raw',spec_path=p/'spec.json',policy_path=p/'policy.raw',
        model_dir=p/'models',prefit_path=p/'prefit_decision.md',admission_path=p/'artifact_decision.md',
        model_path=p/'minutes_model.json',cohort=strict_json((p/'cohort.json').read_bytes()))


def main():
    parser=argparse.ArgumentParser(description=__doc__); commands=parser.add_subparsers(dest='command',required=True)
    replay=commands.add_parser('replay-archive');replay.add_argument('archive')
    forecast=commands.add_parser('forecast')
    for name in ('raw-dir','spec-path','policy-path','model-dir','prefit-path','admission-path','model-path','cohort-path','output'):
        forecast.add_argument('--'+name,required=True)
    args=parser.parse_args()
    if args.command=='replay-archive':
        root=Path(args.archive); expected=strict_json((root/'forecast.json').read_bytes())
        result=read_forecasts((root/'forecast.json').read_bytes(),forecast_at=expected['forecast_at'],**frozen_inputs(root))
        print(canonical(dict(mode='OFFLINE_REPLAY_ONLY',new_forecast_issued=False,payload_sha256=result['payload_sha256'],
            candidate_denominator=result['candidate_denominator'],attempt_denominator=result['attempt_denominator'],
            forecasted_rows=result['forecasted_rows'],abstained_rows=result['abstained_rows'])).decode())
    else:
        from v2.nba_architecture.prospective_s_archive_v1 import create_archive
        kwargs={key:getattr(args,key) for key in ('raw_dir','spec_path','policy_path','model_dir','prefit_path','admission_path','model_path')}
        kwargs['cohort']=strict_json(Path(args.cohort_path).read_bytes())
        # Issue time is actual invocation time; caller cannot backdate it.
        kwargs['forecast_at']=datetime.now(timezone.utc).isoformat()
        require(not Path(args.output).exists(),'GENUINE_FORECAST_OUTPUT_ALREADY_EXISTS')
        try:
            result=run_forecasts(**kwargs)
        except (ValueError,OSError,KeyError,TypeError,StopIteration) as error:
            # A rejected batch never becomes an empty success. If the original
            # frozen spec is available, retain every expected player/stat attempt
            # in the error receipt even when a capture/model has been tampered.
            rejected=[];population_known=False
            try:
                raw=Path(args.spec_path).read_bytes()
                require(digest(raw)==SPEC_SHA,'REJECT_RECEIPT_UNVERIFIED_POPULATION')
                spec=strict_json(raw);population_known=True
                rejected=[dict(player_id=p['player_id'],team_id=p['team_id'],statistic=s,
                    status='REJECTED_BATCH',reason=str(error),forecast=None)
                    for p in spec['frozen_candidates'] for s in ('points','rebounds','assists','threes')]
            except (ValueError,OSError,KeyError,TypeError):pass
            print(canonical(dict(mode='GENUINE_S_REJECTED_BATCH',forecast_at=kwargs['forecast_at'],
                source_population_known=population_known,candidate_denominator=len(rejected)//4 if population_known else None,
                attempt_denominator=len(rejected) if population_known else None,forecasted_rows=0,
                rejected_rows=len(rejected) if population_known else None,rows=rejected,error=str(error))).decode())
            raise
        archive=create_archive(args.output,result,**kwargs)
        print(canonical(dict(mode='ACTUAL_CLOCK_GENUINE_S_SHADOW_FORECAST',forecast_at=kwargs['forecast_at'],
            **archive,payload_sha256=result['payload_sha256'])).decode())


if __name__=='__main__':main()
