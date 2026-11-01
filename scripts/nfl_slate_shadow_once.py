"""NFL-only prospective slate and unchanged production A/B shadow replay."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import traceback
import nflreadpy as nfl
import fetch_slate as fs
import jobs
import context_feeds as context
import nfl_context_daily as daily

DATE='2026-11-01'
ROOT=Path('reports/nfl_slate_shadow')/DATE
DATA=ROOT/'data'

def save(name, obj):
    fs.write_json(obj, ROOT/name)

def main():
    DATA.mkdir(parents=True,exist_ok=True)
    report={'date':DATE,'shadow_only':True,'automatic_promotion':False,'stages':{}}
    now=lambda:datetime.now(timezone.utc)
    stamp=now().isoformat()
    urls=[]
    print('COLLECT_FRESH_NFL',stamp,flush=True)
    rows,note=fs.fetch_nfl(DATE,stamp,source_urls=urls,season_store_path=DATA/'season/nfl_2026.sqlite3')
    if not rows:raise RuntimeError('NO_NFL_SOURCE_ROWS:'+str(note))
    quotes,odds_note=fs.fetch_odds(DATE,sports=['NFL'])
    resolved,unmatched=fs.attach_prices(rows,quotes)
    fs.write_jsonl(resolved,DATA/'quotes.jsonl')
    summary={'date':DATE,'retrieved_at':stamp,'rows':len(rows),'missing':[],
             'feeds':{'nfl':{'status':'ok','rows':len(rows),'notes':[note] if note else [],'source_urls':urls},
                      'odds':{'status':'ok' if resolved else 'unavailable','rows':len(resolved),'notes':[odds_note] if odds_note else []}}}
    fs.commit_slate(rows,summary,DATA/'slate_fetch.jsonl')
    report['collection']={'rows':len(rows),'by_stat':dict(Counter(r['stat'] for r in rows)),
                          'quote_rows':len(resolved),'unmatched_quotes':len(unmatched),'odds_note':odds_note,'source_note':note,'retrieved_at':stamp}
    save('receipt.json',report)
    print('FRESH_COLLECTION',json.dumps(report['collection']),flush=True)
    try:
        report['stages']['new_targets']=daily.run(snapshots=DATA/'prop_snapshots.jsonl',data_root=DATA,
            model_dir=ROOT/'model',out=DATA/'nfl_context'/f'{DATE}.jsonl',receipt=ROOT/'targets_receipt.json',game_date=DATE,download=True)
    except Exception as exc:
        report['stages']['new_targets']={'error':type(exc).__name__+':'+str(exc)[:300]}
        traceback.print_exc()
    save('receipt.json',report)
    if resolved:
        try:
            print('BUILD_SOURCE_RESEARCH',flush=True)
            packet,availability,notes=context.collect_context(DATE,rows,now().isoformat(),fetch=fs.fetch_json,
                odds_events=[],nfl_schedule=nfl.load_schedules([2026]).to_dicts(),nhl_schedule_games=[],nba_matchups={},nfl_loader=nfl)
            fs.write_json(packet,DATA/f'research_{DATE}.json')
            fs.write_jsonl(availability,DATA/'availability.jsonl')
            report['research_notes']=notes
            print('RUN_UNCHANGED_PRODUCTION_SHADOW',flush=True)
            report['stages']['old_production']=jobs.run_snapshot(game_date=DATE,slate_path=DATA/'slate_fetch.jsonl',
                quotes_path=DATA/'quotes.jsonl',snapshot_path=DATA/'prop_snapshots.jsonl',
                preflight_fn=lambda:{'operational':True,'ok':True,'feeds_ready':{'nfl':True,'odds':True}},
                collect_fn=lambda *a,**kw:(rows,{**summary,'_fresh_quotes':resolved}),events_loader=lambda date:[])
        except Exception as exc:
            report['stages']['old_production']={'error':type(exc).__name__+':'+str(exc)[:300]}
            traceback.print_exc()
    else:report['stages']['old_production']={'status':'blocked_no_fresh_market_quotes'}
    old=daily.read_rows(DATA/'prop_snapshots.jsonl')
    new=[r for r in daily.read_rows(DATA/'nfl_context'/f'{DATE}.jsonl') if r.get('status')=='forecast']
    # A numerical probability difference requires identical player, game, stat, side and line.
    def key(r):return tuple(r.get(k) for k in ('game_date','player_id','team','opponent','stat','side','reference_line'))
    index={key(r):r for r in old}
    pairs=[{'identity':key(r),'new_q_win':r['q_win'],'old_q_win':index[key(r)].get('q_win')} for r in new if key(r) in index]
    save('matched_comparison.json',{'pairs':pairs,'paired_count':len(pairs),
        'reason':None if pairs else 'New model predicts targets; legacy production supports different stats. No cross-stat probability or accuracy comparison is valid.',
        'settlement_status':'pending','old_rows':len(old),'new_rows':len(new)})
    report['comparison']={'legacy_rows':len(old),'new_target_rows':len(new),'same_market_pairs':len(pairs),'settlement_status':'pending'}
    save('receipt.json',report)
    print('NFL_SHADOW_RECEIPT',json.dumps(report,allow_nan=False),flush=True)
    if not new:raise RuntimeError('NO_NEW_TARGET_FORECASTS')

if __name__=='__main__':main()
