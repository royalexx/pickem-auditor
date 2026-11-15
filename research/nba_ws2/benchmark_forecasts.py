"""End-to-end manual shadow CLI fixture and 100-player CPU inference benchmark."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import sys
import time
from v2.nba_opportunity import FEATURES, MinutesModel, PregameOpportunityInput


def main():
    dest=Path('research/nba_ws2/results');model=MinutesModel.load(dest/'model.json')
    now=datetime.now(timezone.utc)
    t=lambda seconds:(now+timedelta(seconds=seconds)).isoformat()
    f=dict(zip(FEATURES,[28,27,29,7,2,2,0,0,0,1,10,0,0]))
    row=dict(game_id='SYNTHETIC-FUTURE-GAME',player_id='SYNTHETIC-PLAYER',team_id='A',opponent_id='B',
        event_start_at=t(86400),forecast_at=t(0),input_freeze_at=t(-10),source_available_at=t(-30),
        source_ingested_at=t(-20),training_cutoff_at=model.training_cutoff_at,
        source_sha256=hashlib.sha256(b'SYNTHETIC-FIXTURE-NOT-A-SOURCE-RECEIPT').hexdigest(),
        features=f,position='G',participation_status='unverified',participation_probability=None,
        active_roster_eligible=None,reliability_reasons=['SYNTHETIC_CONTRACT_TEST_NOT_A_REAL_FORECAST'])
    timings={}
    for name in ('M0','M1','M2'):
        start=time.perf_counter();cpu=time.process_time()
        forecasts=[model.forecast(name,PregameOpportunityInput(**{**row,'player_id':str(i)}),20261115) for i in range(100)]
        timings[name]={'players':100,'wall_seconds':time.perf_counter()-start,'cpu_seconds':time.process_time()-cpu}
    scratch=Path('work/ws2_cli_fixture');scratch.mkdir(parents=True,exist_ok=True)
    inputfile=scratch/'inputs.json';output=scratch/('freeze_'+now.strftime('%Y%m%dT%H%M%S%f')+'.jsonl')
    rejected={**row,'player_id':'PAST-EVENT-FIXTURE','event_start_at':t(-5)}
    inputfile.write_text(json.dumps([row,rejected]))
    result=subprocess.run([sys.executable,'-m','research.nba_ws2.shadow','--model',str(dest/'model.json'),
        '--input',str(inputfile),'--output',str(output)],text=True,capture_output=True,check=True)
    rows=[json.loads(x) for x in output.read_text().splitlines()]
    assert len(rows)==2 and 'forecast_id' in rows[0] and rows[1]['reason']=='EVENT_ALREADY_STARTED'
    report={'fixture_only':True,'actual_prospective_forecasts':0,'timings_100_player_slate':timings,
        'cli_receipt':json.loads(result.stdout),'cli_rows':len(rows),'rejected_past_event':True,
        'forecast_without_participation_abstains_unconditional':bool(rows[0]['abstention_reasons']),
        'max_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024}
    (dest/'inference_benchmark.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
