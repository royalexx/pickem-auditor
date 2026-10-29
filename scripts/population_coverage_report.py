#!/usr/bin/env python3
"""Read-only coverage proof for the joint, fully Bayesian history warehouse.

This does NOT mean a model is trained or calibrated: the report reconciles
cursor-proven date continuity with immutable on-disk per-stat season shards.
A multi-season training fit still requires population_window_check.py.
"""
import argparse
from datetime import date
import json
from pathlib import Path
from population_backfill import read_state, RECENT_START, DEFAULT_START
from population_history import SPORTS

ROOT=Path(__file__).resolve().parents[1]


def summarize(root, *, as_of=None):
    root=Path(root)
    cutoff=date.fromisoformat(as_of) if as_of else date.today()
    pop=root/'data/bayesian_warehouse/populations'
    result={'schema':'joint_bayesian_history_coverage_v1',
            'audit_as_of':cutoff.isoformat(),
            'status':'collection_inventory_only_not_fit_ready',
            'source':'committed_population_cursors_and_shard_partitions',
            'sports':{},'no_claim_of_training_validation':True}
    for sport in SPORTS:
        archive=read_state(root,sport)
        recent=read_state(root,sport,stream='recent') if sport in RECENT_START else None
        stats={}
        for statfolder in sorted((pop/sport.lower()).glob('*')):
            if not statfolder.is_dir():continue
            years=sorted(int(p.stem.split('.')[0]) for p in statfolder.glob('*.jsonl.gz')
                         if p.name[:4].isdigit() and len(p.name)>=13)
            stats[statfolder.name]={
                'partition_seasons':years,'partition_count':len(years),
                'missing_in_partition_span':[y for y in range(years[0],years[-1]+1)
                                              if y not in years] if years else [],
                'records_verified_for_this_report':False}
        output={'archive':{'next_uncollected':archive['cursor'],
                            'days_or_seasons_collected':archive['dates_complete'],
                            'source_games':archive['source_games'],
                            'market_rows_inserted':archive['market_rows_inserted']},
                'markets':stats,
                'note':'Presence of season partitions alone does not establish completed dates, training-window sufficiency or convergence.'}
        if recent:
            target_start=int(RECENT_START[sport][:4])
            latest_season=cutoff.year if cutoff.month>=10 else cutoff.year-1
            expected=list(range(target_start,latest_season+1))
            output['recent']={
                'start':RECENT_START[sport],
                'next_uncollected':recent['cursor'],
                'days_collected':recent['dates_complete'],
                'source_games':recent['source_games'],
                'market_rows_inserted':recent['market_rows_inserted'],
                'caught_up_to_as_of':date.fromisoformat(recent['cursor'])>=cutoff,
                'target_season_partitions':expected,
                'markets_with_contiguous_target_partitions':
                    [stat for stat,detail in stats.items()
                     if all(y in detail['partition_seasons'] for y in expected)],
            }
            # A missing recent date cannot be hidden by historical 2018 shards.
            output['sufficient_recent_source_continuity_for_as_of']=(
                date.fromisoformat(recent['cursor'])>=cutoff)
        else:
            # NFL cursor means first not-yet-collected completed season.
            next_year=int(archive['cursor'])
            completed_through=next_year-1
            output['completed_season_source_through']=completed_through
            output['latest_completed_nfl_season_as_of']=(
                cutoff.year-1 if cutoff.month>=3 else cutoff.year-2)
            output['up_to_date_completed_seasons']=(
                completed_through>=output['latest_completed_nfl_season_as_of'])
        result['sports'][sport]=output
    return result


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--as-of',default=None)
    p.add_argument('--out',type=Path,default=Path('reports/population_coverage.json'))
    args=p.parse_args(argv)
    report=summarize(args.root,as_of=args.as_of)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
