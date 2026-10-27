"""Bounded live endpoint diagnostics. Prints coverage failures, never player picks."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from datetime import datetime
import urllib.request
import urllib.error
from zoneinfo import ZoneInfo
from local_credentials import odds_api_key


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date',default=datetime.now(ZoneInfo('America/Toronto')).date().isoformat())
    parser.add_argument('--timeout',type=float,default=8)
    args=parser.parse_args()
    compact=args.date.replace('-','')
    urls={
      'nhl_schedule':f'https://api-web.nhle.com/v1/schedule/{args.date}',
      'nhl_stats':'https://api.nhle.com/stats/rest/en/team?limit=1',
      'nba_scoreboard':f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={compact}',
      'nba_player_stats':'https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/statistics/byathlete?region=us&lang=en&contentorigin=espn&isqualified=true&limit=1',
      'nfl_history_host':'https://github.com/nflverse/nflverse-data',
      'nba_pace_host':'https://stats.nba.com/',
      'weather_host':'https://api.weather.gov/',
    }
    def probe(item):
        name,url=item
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'pickem-auditor-diagnostics/1','Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=args.timeout) as response:
                payload=response.read(1_000_000)
                if name in ('nfl_history_host','nba_pace_host','weather_host'):
                    return name,{'ok':True,'status':response.status,'note':'host reachable only; data schema not validated'}
                data=json.loads(payload)
                keys={'nhl_schedule':'gameWeek','nhl_stats':'data','nba_scoreboard':'events','nba_player_stats':'athletes'}
                key=keys[name]
                return name,{'ok':isinstance(data,dict) and key in data,'status':response.status,
                             'schema_key':key,'items':len(data.get(key,[])) if isinstance(data,dict) and isinstance(data.get(key),list) else None}
        except Exception as exc:
            return name,{'ok':False,'error':f'{type(exc).__name__}: {exc}'}
    with ThreadPoolExecutor(max_workers=len(urls)) as pool:
        feeds=dict(pool.map(probe,urls.items()))
    result={'date':args.date,'imports':{k:importlib.util.find_spec(k) is not None for k in ('nflreadpy','nhlpy','nba_api','polars')},
            'odds_key_present':bool(odds_api_key()),'feeds':feeds}
    print(json.dumps(result,indent=2))
    return 0 if all(result['imports'].values()) and result['odds_key_present'] and all(x['ok'] for x in feeds.values()) else 2

if __name__=='__main__':raise SystemExit(main())
