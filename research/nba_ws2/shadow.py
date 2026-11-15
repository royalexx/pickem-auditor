"""Manual immutable future-slate minutes freeze. No scheduling or production hook.

Input JSON is a list of WS2 PregameOpportunityInput dictionaries supplied by WS1
or a caller. It must contain genuine receipts; this command does not collect or
infer injury status. Every rejected candidate is preserved in the output ledger.
"""
import argparse
from dataclasses import fields
from datetime import datetime, timezone
import json
from pathlib import Path
from v2.nba_opportunity import MinutesModel, PregameOpportunityInput, freeze_shadow, utc


def main():
    p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--input',required=True)
    p.add_argument('--output',required=True);p.add_argument('--name',choices=['M0','M1','M2'],default='M0')
    p.add_argument('--seed',type=int,default=20261115)
    a=p.parse_args();model=MinutesModel.load(a.model);rows=json.loads(Path(a.input).read_text())
    now=datetime.now(timezone.utc).isoformat();result=[]
    for i,row in enumerate(rows):
        try:
            row={**row,'forecast_at':now}
            if utc(row['event_start_at'])<=utc(now):raise ValueError('EVENT_ALREADY_STARTED')
            item=PregameOpportunityInput(**row)
            forecast=model.forecast(a.name,item,a.seed)
            # Reconstructed historical sources cannot become certified via this CLI.
            forecast['prospective_freeze_at']=now
            result.append(forecast)
        except (ValueError,TypeError,KeyError) as exc:
            result.append({'status':'REJECTED/SHADOW','attempt_index':i,
                'game_id':row.get('game_id'),'player_id':row.get('player_id'),
                'forecast_at':now,'reason':str(exc)})
    digest=freeze_shadow(a.output,result)
    print(json.dumps({'attempted':len(rows),'generated':sum('forecast_id' in r for r in result),
        'rejected':sum('forecast_id' not in r for r in result),'sha256':digest,'path':a.output}))

if __name__=='__main__':main()
