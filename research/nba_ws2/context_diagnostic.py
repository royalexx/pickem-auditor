"""Bounded postgame context inspection. Outcomes only, never pregame inputs.

Reads existing source-backed game IDs and fetches at most 32 deterministic
ESPN summaries. Does not alter canonical collectors or feature store.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import urllib.request
import numpy as np
import pandas as pd
from research.nba_ws2.run_experiment import load_population


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--cache',required=True)
    a=p.parse_args();folder=Path(a.cache);folder.mkdir(parents=True,exist_ok=True)
    rows,_=load_population(a.input)
    games=sorted({(r['game_date'],r['game_id']) for r in rows if r['season']=='2025'})
    selected=[games[i] for i in np.linspace(0,len(games)-1,32).astype(int)]
    def fetch(pair):
        day,gid=pair;path=folder/(gid+'.json');url='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event='+gid
        try:
            if not path.exists():
                req=urllib.request.Request(url,headers={'User-Agent':'NBA-WS2-Research/1.0'})
                with urllib.request.urlopen(req,timeout=20) as response:raw=response.read()
                path.write_bytes(raw)
            raw=path.read_bytes();data=json.loads(raw)
            comp=data['header']['competitions'][0]
            if str(comp['id'])!=gid:raise ValueError('IDENTITY_MISMATCH')
            scores=[int(c['score']) for c in comp['competitors']]
            margin=abs(scores[0]-scores[1]);period=comp['status'].get('period')
            players=[]
            for box in data['boxscore']['players']:
                team=box['team']['abbreviation']
                for cat in box.get('statistics',[]):
                    labels=cat.get('labels',[])
                    for athlete in cat.get('athletes',[]):
                        stats=dict(zip(labels,athlete.get('stats',[])))
                        players.append({'game_id':gid,'player_id':str(athlete['athlete']['id']),'team':team,
                            'starter_outcome':athlete.get('starter'), 'did_not_play_outcome':athlete.get('didNotPlay'),
                            'minutes_text':stats.get('MIN'),'final_margin_outcome':margin,'period_outcome':period})
            return {'game_id':gid,'url':url,'sha256':hashlib.sha256(raw).hexdigest(),
                'retrieved_at':__import__('datetime').datetime.fromtimestamp(path.stat().st_mtime,__import__('datetime').timezone.utc).isoformat(),
                'historical_population_hashes':sorted({r['source_sha256'] for r in rows if r['game_id']==gid}),
                'players':players}
        except Exception as exc:return {'game_id':gid,'error':str(exc)}
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(fetch,selected))
    extracted=[r for result in results for r in result.get('players',[])]
    dest=Path(a.output);dest.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(extracted).to_csv(dest/'postgame_context_sample.csv',index=False)
    (dest/'context_source_manifest.json').write_text(json.dumps(results,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'attempted_games':len(results),'succeeded':sum('players' in r for r in results),
        'failures':[r for r in results if 'error' in r],'rows':len(extracted)}))

if __name__=='__main__':main()
