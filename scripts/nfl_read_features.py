"""Historical offense/defense read covariates using the configured FTN workflow.

Reuse the existing bucket dictionary and opponent-QB-adjusted profiles. Do not
call a live confirmed-passer scenario with fabricated historical confirmations.
Instead expose a pregame, recent-passer mixture as descriptive model covariates.
"""
from __future__ import annotations
import gzip
import json
from collections import Counter,defaultdict
from datetime import datetime,timedelta,timezone
from pathlib import Path

import nhl_context_data as common
import nhl_context_train as io
from nfl_season_store import BUCKETS,READ_MAP,FTN_FIELDS,bucket,token,build_profiles

KNOWN=BUCKETS[:-1]
VALUE_NAMES=(["qb_mix_"+k for k in BUCKETS]+["receiver_share_"+k for k in BUCKETS]+
             ["defense_qb_adjusted_"+k for k in KNOWN]+
             ["offense_target_share_per_throw","matched_target_share_per_throw",
              "offense_read_coverage","defense_read_coverage"])
FEATURE_NAMES=VALUE_NAMES+[n+"_observed" for n in VALUE_NAMES]


def fetch_charting(season):
    import nflreadpy
    frame=nflreadpy.load_ftn_charting(seasons=[season])
    required={"nflverse_game_id","nflverse_play_id","season","read_thrown"}
    absent=required-set(frame.columns)
    if absent:raise ValueError("missing_ftn_columns:"+",".join(sorted(absent)))
    from nfl_context_data import clean
    return clean(frame.select([n for n in FTN_FIELDS if n in frame.columns]).to_dicts())


def attach(folder,bundles, *, fetcher=fetch_charting):
    """Archive FTN separately and join exact game/play IDs to archived PBP."""
    import nfl_context_data as data
    folder=Path(folder);result=[]
    for b in bundles:
        year=b["season"];path=folder/f"ftn_{year}.json.gz";receipt=folder/f"ftn_{year}.receipt.json"
        if path.exists():
            if io.file_hash(path)!=io.load_json(receipt)["sha256"]:raise ValueError("ftn_source_hash_changed")
            with gzip.open(path,"rt",encoding="utf-8") as h:chart=json.load(h)
        else:
            print(f"FETCH_FTN_CHARTING {year}",flush=True)
            chart=fetcher(year)
            tmp=path.with_suffix(".tmp");tmp.write_bytes(gzip.compress((common.encode(chart)+"\n").encode(),mtime=0));tmp.replace(path)
            io.write_json(receipt,{"sha256":io.file_hash(path),"source":"https://github.com/nflverse/nflverse-data/releases/tag/ftn_charting",
                                  "retrieved_at":datetime.now(timezone.utc).isoformat(),
                                  "attribution":"FTN Data via nflverse, CC BY-SA 4.0","read_mapping":READ_MAP})
        with gzip.open(folder/f"season_{year}.json.gz","rt",encoding="utf-8") as h:raw=json.load(h)
        result.append(join(b,raw["pbp"],chart))
    return result


def join(bundle,pbp,chart):
    import nfl_context_data as data
    games={r["game_id"]:r for r in bundle["teams"]}
    teams={(r["game_id"],r["team"]):r["opponent"] for r in bundle["teams"]}
    keyed={};unmatched=0;codes=Counter()
    for c in chart:
        if str(c.get("season"))!=str(bundle["season"]):continue
        gid=str(c.get("nflverse_game_id"));pid=token(c.get("nflverse_play_id"))
        if gid not in games:continue
        if pid is None:raise ValueError("invalid_ftn_play_identity")
        key=(gid,pid)
        if key in keyed and keyed[key]!=c:raise ValueError("conflicting_duplicate_ftn_play")
        keyed[key]=c
    plays=[];seen={};joined=set()
    for p in pbp:
        gid=str(p.get("game_id"))
        if gid not in games or data.no_play(p) or data.one(p.get("two_point_attempt")):continue
        if (gid,p.get("posteam")) not in teams:continue
        if p.get("defteam")!=teams[(gid,p["posteam"])]:raise ValueError("read_pbp_opponent_mismatch")
        if p.get("season_type")!="REG" or not (data.one(p.get("pass_attempt")) or data.one(p.get("qb_dropback")) or data.one(p.get("rush_attempt"))):continue
        pid=token(p.get("play_id"))
        if pid is None:raise ValueError("invalid_read_pbp_identity")
        key=(gid,pid)
        if key in seen:
            if seen[key]!=p:raise ValueError("conflicting_read_pbp_play")
            continue
        seen[key]=p;c=keyed.get(key)
        if c is not None:joined.add(key)
        if data.one(p.get("pass_attempt")) and not data.one(p.get("sack")):
            codes[bucket(c.get("read_thrown") if c else None)]+=1
        plays.append({**p,"game_id":gid,"play_id":pid,"start_time":games[gid]["start_time"],
                      "available_at":games[gid]["available_at"],"chart":c})
    unmatched=len(set(keyed)-joined)
    if not plays:raise ValueError("empty_read_pbp_join")
    return {**bundle,"read_plays":plays,"read_source":{
        "chart_sha256":common.digest(chart),"read_mapping":READ_MAP,
        "charted_play_joins":len(joined),"unmatched_chart_plays":unmatched,
        "throw_buckets":dict(codes),"attribution":"FTN Data via nflverse, CC BY-SA 4.0"}}


class ReadHistory:
    def __init__(self,bundles, *, lag_days=7):
        self.lag=lag_days;self.plays=defaultdict(list);self.cache={}
        for b in bundles:
            if "read_plays" not in b:raise ValueError("read_training_requires_ftn_joined_sources")
            self.plays[str(b["season"])].extend(b["read_plays"])

    def snapshot(self,season,at):
        from nfl_context_data import one
        key=(season,at)
        if key in self.cache:return self.cache[key]
        boundary=common.instant(at);valid=[];chart={};by_team=defaultdict(lambda:defaultdict(Counter))
        starts={}
        for p in self.plays[season]:
            if common.instant(p["start_time"])>=boundary or common.instant(p["available_at"])>=boundary:continue
            valid.append(p);starts[p["game_id"]]=p["start_time"]
            if p.get("chart") and common.instant(p["available_at"])+timedelta(days=self.lag)<boundary:
                chart[(p["game_id"],p["play_id"])]=p["chart"]
            # Passer mixture uses recent observed throws, never tonight's QB.
            if one(p.get("pass_attempt")) and not one(p.get("sack")) and p.get("passer_player_id"):
                by_team[p["posteam"]][p["game_id"]][str(p["passer_player_id"])]+=1
        profiles=build_profiles(valid,chart,{"as_of":at,"season":int(season),"read_mapping":READ_MAP})
        weights={}
        for team,games in by_team.items():
            total=Counter()
            for gid in sorted(games,key=lambda g:starts[g])[-3:]:total.update(games[gid])
            denominator=sum(total.values());weights[team]={q:n/denominator for q,n in total.items()}
        # Retain one kickoff snapshot, rather than a season of overlapping RAM.
        self.cache.clear();self.cache[key]=(profiles,weights)
        return self.cache[key]

    def features(self,row):
        profiles,weights=self.snapshot(row["season"],row["start_time"])
        d=profiles["defenses"].get(row["opponent"],{})
        values={n:None for n in VALUE_NAMES};components=[];thin=[]
        known_n=receiver_n=target_n=0
        for qb,weight in weights.get(row["team"],{}).items():
            q=profiles["passers"].get(row["team"]+"|"+qb)
            if not q:continue
            counts={k:q["targeted"].get(k,0)-q["by_defense"].get(row["opponent"],{}).get(k,0) for k in BUCKETS}
            throws=q["throws"]-q["throws_by_defense"].get(row["opponent"],0)
            total=sum(counts.values());known=total-counts["unknown"]
            receiver=q["receivers"].get(row["player_id"])
            if total<=0 or throws<=0:continue
            mix={k:counts[k]/total for k in BUCKETS}
            shares=({k:(receiver["buckets"].get(k,0)-receiver["by_defense"].get(row["opponent"],{}).get(k,0))/counts[k]
                     if counts[k] else None for k in BUCKETS} if receiver else {k:None for k in BUCKETS})
            independent_receiver=sum((receiver["buckets"].get(k,0)-receiver["by_defense"].get(row["opponent"],{}).get(k,0))
                                     for k in BUCKETS) if receiver else 0
            known_n+=known;receiver_n+=independent_receiver;target_n+=total
            matched=dict(mix);ratios={};possible=d.get("opponent_adjusted_comparable_targets",0)>0
            for k in KNOWN:
                expected=d.get("opponent_qb_expected_counts",{}).get(k,0)
                actual=d.get("matched_actual_counts",{}).get(k,0)
                ratios[k]=actual/expected if expected>0 else None
                if mix[k]>0 and ratios[k] is None:possible=False
            if possible:
                norm=sum(mix[k]*(ratios[k] or 0.) for k in KNOWN)
                if norm<=0 and known:possible=False
                else:
                    for k in KNOWN:matched[k]=(1-mix["unknown"])*mix[k]*(ratios[k] or 0.)/norm if norm else 0.
            own_share=sum(mix[k]*(shares[k] or 0.) for k in BUCKETS) if receiver else None
            matched_share=sum(matched[k]*(shares[k] or 0.) for k in BUCKETS) if receiver and possible else None
            components.append({"weight":weight,"mix":mix,"shares":shares,"known":known,
                               "counts":counts,"games":len(q["by_game"]),
                               "offense":total/throws*own_share if own_share is not None else None,
                               "matched":total/throws*matched_share if matched_share is not None else None,
                               "ratios":ratios,"coverage":known/total})
        def weighted(getter):
            pairs=[(c["weight"],getter(c)) for c in components]
            # Never reweight a missing passer to make the remaining one certain.
            if not pairs or abs(sum(w for w,v in pairs)-1)>1e-8 or any(v is None for w,v in pairs):return None
            return sum(w*v for w,v in pairs)
        for k in BUCKETS:
            values["qb_mix_"+k]=weighted(lambda c:c["mix"][k] if c["known"] or k=="unknown" else None)
            values["receiver_share_"+k]=weighted(lambda c:c["shares"][k])
        for k in KNOWN:
            values["defense_qb_adjusted_"+k]=components[0]["ratios"][k] if components else None
        values["offense_target_share_per_throw"]=weighted(lambda c:c["offense"])
        values["matched_target_share_per_throw"]=weighted(lambda c:c["matched"])
        values["offense_read_coverage"]=weighted(lambda c:c["coverage"])
        values["defense_read_coverage"]=d.get("charting_coverage")
        # Reuse the configured reliability conventions, as flags rather than
        # invented certainty or automatic player/defense multipliers.
        if target_n<100 or receiver_n<20 or any(c["games"]<3 for c in components):thin.append("thin_independent_passer_receiver_history")
        if target_n and known_n/target_n<.8:thin.append("insufficient_read_classification")
        if d.get("opponent_adjusted_comparable_targets",0)<100:thin.append("thin_defense_comparison")
        if any(c["mix"][k]*(c["shares"][k] or 0)>0 and min(c["counts"][k],
                   d.get("opponent_qb_expected_counts",{}).get(k,0),
                   d.get("matched_actual_counts",{}).get(k,0))<10 for c in components for k in KNOWN):
            thin.append("sparse_read_bucket_comparison")
        raw=[values[n] for n in VALUE_NAMES]
        meta={"passer_method":"prior_three_games_throw_weighted_mixture_not_confirmed_starter",
              "passer_weights":weights.get(row["team"],{}),"charting_lag_days":self.lag,
              "historical_charting_publication_time_verified":False,"known_offense_targets":known_n,
              "defense_comparable_targets":d.get("opponent_adjusted_comparable_targets",0),
              "offense_read_available":known_n>0,"defense_read_available":d.get("charted_throws",0)>0,
              "reliability_flags":thin,"defense_adjustment_applied_as":"learned_covariates_only_no_external_multiplier"}
        return raw+[float(v is not None) for v in raw],meta


def augment(bundles,rows, *, lag_days=7):
    history=ReadHistory(bundles,lag_days=lag_days);out=[]
    for i,r in enumerate(rows,1):
        x,meta=history.features(r)
        out.append({**r,"x":r["x"]+x,"feature_names":r["feature_names"]+FEATURE_NAMES,"read_context":meta})
        if i%1000==0:print(f"READ_FEATURE_ROWS {i}/{len(rows)}",flush=True)
    return out
