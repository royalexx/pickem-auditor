"""Manual research CLI. Fails closed and preserves rejected input hashes."""
import argparse
import json
from pathlib import Path
from . import synthetic_fixture,simulate,audit,extract_forecast,freeze
from .common import sha,STATS
from .sources import canary
from .forecast import freeze_scenarios


def main():
    p=argparse.ArgumentParser(description='Isolated NBA joint v0.1 shadow simulator')
    modes=p.add_mutually_exclusive_group(required=True);modes.add_argument('--fixture',action='store_true');modes.add_argument('--input');modes.add_argument('--snapshot')
    p.add_argument('--model');p.add_argument('--scenarios',type=int,default=128);p.add_argument('--seed',type=int,default=20261115);p.add_argument('--output',required=True)
    a=p.parse_args();dest=Path(a.output);dest.mkdir(parents=True,exist_ok=False)
    if a.snapshot:
        receipt=canary(a.snapshot);freeze(dest/'blocked.json',receipt);print(json.dumps(receipt,sort_keys=True));return 2
    if a.fixture:game,model=synthetic_fixture()
    else:
        if not a.model:p.error('--input requires --model')
        game=json.loads(Path(a.input).read_text());model=json.loads(Path(a.model).read_text())
    try:
        out=simulate(game,model,n=a.scenarios,seed=a.seed)
        check=audit(out)
        forecasts=[extract_forecast(out,i,k) for i in range(len(game['players'])) for k in STATS]
        scenario_bytes_hash=freeze_scenarios(dest/'scenarios.json.gz',out)
        freeze(dest/'forecasts.json',forecasts)
        freeze(dest/'manifest.json',dict(schema='NBAJointResearchRun/1',status='UNCERTIFIED/SHADOW',input_sha256=out['input_sha256'],model_sha256=out['model_sha256'],output_sha256=out['output_sha256'],scenario_artifact='scenarios.json.gz',scenario_bytes_sha256=scenario_bytes_hash,audit=check,timing=out['timing'],source_ledger=game.get('source_ledger'),certified=0,promotion_authorized=False))
        print(json.dumps({'output':str(dest),'output_sha256':out['output_sha256'],'audit':check}))
    except (ValueError,KeyError) as exc:
        freeze(dest/'blocked.json',dict(status='BLOCKED',reason=str(exc),input_sha256=sha(game),model_sha256=sha(model),accepted=0,attempted_players=len(game.get('players',[])),attempted_scenarios=a.scenarios))
        print(str(exc));return 2
    return 0


if __name__=='__main__':raise SystemExit(main())
