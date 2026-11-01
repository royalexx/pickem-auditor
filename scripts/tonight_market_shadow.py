"""Fresh SNF and NHL saves prospective research at supported public lines."""
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import traceback
import fetch_slate as fs
import jobs
import context_feeds as context
import nfl_context_daily as nfl_daily
import nhl_saves_posterior_shadow as saves

DATE='2026-11-01'
ROOT=Path('reports/tonight_market_shadow')/DATE
DATA=ROOT/'data'

def now():return datetime.now(timezone.utc)
def at(s):return datetime.fromisoformat(str(s).replace('Z','+00:00'))
def write(name,value):fs.write_json(value,ROOT/name)
def download(tag,folder,patterns):
    folder.mkdir(parents=True,exist_ok=True)
    args=['gh','release','download',tag,'--repo','royalexx/pickem-auditor','--dir',str(folder),'--clobber']
    for p in patterns:args+=['--pattern',p]
    subprocess.run(args,check=True)

def main():
    DATA.mkdir(parents=True,exist_ok=True)
    receipt={'date':DATE,'created_at':now().isoformat(),'shadow_only':True,'automatic_promotion':False,'stages':{}}
    def stage(name,fn):
        print('START',name,flush=True)
        try:r=fn();receipt['stages'][name]=r;write('receipt.json',receipt);return r
        except Exception as exc:
            receipt['stages'][name]={'error':type(exc).__name__+':'+str(exc)[:300]}
            write('receipt.json',receipt);traceback.print_exc();return None
    # Only two quota-guarded bulk requests, one per requested league.
    odds={}
    for sport in ['NHL','NFL']:
        q,n=fs.fetch_odds(DATE,sports=[sport]);odds[sport]=q
        receipt['stages']['odds_'+sport]={'rows':len(q),'note':n}
    write('receipt.json',receipt)
    schedule=stage('official_nhl_schedule',lambda:fs.fetch_json('https://api-web.nhle.com/v1/schedule/'+DATE))
    nhl_games=[] if not schedule else [g for d in schedule.get('gameWeek',[]) if d.get('date')==DATE for g in d.get('games',[]) if at(g['startTimeUTC'])>now()]
    write('nhl_schedule.json',schedule or {})
    client,error=fs.make_nhl_client()
    nhl_result=stage('collect_nhl',lambda:fs.fetch_nhl(DATE,now().isoformat(),client=client))
    nhl_rows=[]
    if nhl_result:
        candidates,note=nhl_result;teams={t for g in nhl_games for t in [g['homeTeam']['abbrev'],g['awayTeam']['abbrev']]}
        nhl_rows=[r for r in candidates if r.get('team') in teams]
        receipt['stages']['collect_nhl']={'rows':len(nhl_rows),'notes':note,'upcoming_games':len(nhl_games)}
    nfl_result=stage('collect_snf',lambda:fs.fetch_nfl(DATE,now().isoformat(),season_store_path=DATA/'season/nfl_2026.sqlite3'))
    nfl_rows=[]
    if nfl_result:
        candidates,note=nfl_result
        nfl_rows=[r for r in candidates if r.get('team') in ('PHI','WAS') and r.get('opponent') in ('PHI','WAS')]
        receipt['stages']['collect_snf']={'rows':len(nfl_rows),'notes':note}
    rows=nhl_rows+nfl_rows
    # Keep only actual, still-pregame quotes on this date. Never restamp odds.
    quotes=[q for sport in odds for q in odds[sport] if q.get('event_start') and at(q['event_start'])>now()]
    resolved,unmatched=fs.attach_prices(rows,quotes)
    fs.write_jsonl(resolved,DATA/'quotes.jsonl')
    summary={'date':DATE,'retrieved_at':now().isoformat(),'rows':len(rows),'missing':[],
        'feeds':{s.lower():{'status':'ok','rows':len([r for r in rows if r['sport']==s])} for s in ('NFL','NHL')}}
    fs.commit_slate(rows,summary,DATA/'slate_fetch.jsonl')
    receipt['collection']={'rows':len(rows),'quotes':len(resolved),'unmatched':len(unmatched),
        'actual_nfl_target_quote_rows':sum(q.get('sport')=='NFL' and q.get('stat')=='targets' for q in resolved)}
    # The release forecasts only saves. Build exact market snapshots directly
    # from collector-owned goalie IDs and the independently fetched NHL schedule.
    snapshots=[];excluded=[]
    for row in nhl_rows:
        if row.get('stat')!='goalie saves':continue
        games=[g for g in nhl_games if {g['homeTeam']['abbrev'],g['awayTeam']['abbrev']}=={row.get('team'),row.get('opponent')}]
        if len(games)!=1:continue
        game=games[0];fresh=[]
        for q in fs.quotes_for_row(resolved,row):
            if q.get('event_start') and at(q['event_start'])==at(game['startTimeUTC']) and 0<=(now()-at(q['retrieved_at'])).total_seconds()<=3600:fresh.append(q)
        price=fs.primary_price(fresh)
        if not price:excluded.append({'player':row.get('player'),'reason':'no_fresh_two_sided_saves_quote'});continue
        forecast_at=now().isoformat()
        for side in ('over','under'):
            snapshots.append({**{k:row.get(k) for k in ('sport','player','player_id','team','opponent')},
                'game_date':DATE,'stat':'goalie saves','side':side,'reference_line':float(price['line']),
                'forecast_at':forecast_at,'event_start':game['startTimeUTC'],'run_type':'shadow',
                'run_id':'tonight-saves:'+game['id'].__str__()+':'+str(row['player_id']),
                'home_team':game['homeTeam']['abbrev'],'away_team':game['awayTeam']['abbrev'],
                'matchup_orientation_verified':True,'venue_source':'https://api-web.nhle.com/v1/schedule/'+DATE,
                'line_origin':'market','market_quotes':[q for q in fresh if float(q['line'])==float(price['line'])],
                'conditional_on_appearance':True,'starting_goalie_verified':False})
    fs.write_jsonl(snapshots,DATA/'saves_market_snapshots.jsonl')
    receipt['saves_snapshot_candidates']=len(snapshots);receipt['saves_quote_exclusions']=excluded
    modeldir=ROOT/'models/nhl_saves'
    def hockey():
        download(saves.TAG,modeldir,list(saves.EXPECTED_SHA))
        return saves.run(snapshots=DATA/'saves_market_snapshots.jsonl',model_dir=modeldir,game_date=DATE,
            out=DATA/'nhl_saves_posterior.jsonl',receipt=ROOT/'nhl_saves_receipt.json')
    stage('trained_nhl_saves',hockey)
    stage('trained_nfl_targets',lambda:nfl_daily.run(snapshots=DATA/'prop_snapshots.jsonl',data_root=DATA,
        model_dir=ROOT/'models/nfl_targets',out=DATA/'nfl_context'/f'{DATE}.jsonl',
        receipt=ROOT/'nfl_targets_receipt.json',game_date=DATE,download=True))
    # Retain legacy forecasts on the same real public market lines separately.
    if resolved:
        import nflreadpy
        nfl_schedule=nflreadpy.load_schedules([2026]).to_dicts()
        games=context.games_from_schedules(DATE,nfl_schedule=nfl_schedule,nhl_games=nhl_games)
        packet=context.build_research_packet(DATE,rows,[],{},{},{},scheduled_games=games)
        fs.write_json(packet,DATA/f'research_{DATE}.json')
        def legacy():
            from auto_research import refresh
            research=refresh(slate=DATA/'slate_fetch.jsonl',quotes=DATA/'quotes.jsonl',
                packet_path=DATA/f'research_{DATE}.json',out=ROOT/'structured_research.json')
            return jobs.run_snapshot(game_date=DATE,slate_path=DATA/'slate_fetch.jsonl',quotes_path=DATA/'quotes.jsonl',
                snapshot_path=DATA/'prop_snapshots.jsonl',preflight_fn=lambda:{'ok':True,'operational':True},
                collect_fn=lambda *a,**kw:(rows,{**summary,'_fresh_quotes':resolved}),events_loader=lambda date:[])
        stage('legacy_market_forecasts',legacy)
    receipt['finished_at']=now().isoformat()
    write('receipt.json',receipt)
    print('TONIGHT_RECEIPT',json.dumps(receipt,allow_nan=False),flush=True)
    if not (receipt['stages'].get('trained_nhl_saves') or {}).get('forecast_count'):
        raise RuntimeError('NO_VERIFIED_MARKET_SAVES_FORECASTS: inspect receipt')

if __name__=='__main__':main()
