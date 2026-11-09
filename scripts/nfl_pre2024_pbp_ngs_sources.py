"""Strict pre-2024 NFL historical source adapter (PBP, NGS, gated FTN).

Every training observation must refer to a game played before 2024-01-01.
The public FTN 2022-23 archive currently exposes date_pulled=2024-09-06;
a row is forbidden unless its charting provenance predates the cutoff.
Never pass 2024 player statistics, FTN, NGS or PBP into this adapter.

Source aggregate: team-game offense and opposing-defense opportunities,
not player box-score results duplicated as team events.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date,datetime,timezone
import math

CUTOFF=date(2024,1,1)
TRAINING_SEASONS=(2021,2022,2023)
SUPPORTED_SOURCES=("pbp","ngs_passing","ngs_receiving","ngs_rushing","ftn_pre2024_verified_only")

def _gameday(s):
    result=date.fromisoformat(str(s)[:10])
    if result>=CUTOFF:raise ValueError("2024_plus_date_forbidden_in_training")
    return result

def _metric(v,default=0.):
    try:
        if v is None:return default
        val=float(v)
        return val if math.isfinite(val) else default
    except (TypeError,ValueError):
        return default

def _yes(v):
    return v is True or v==1 or v=="1"

def _ftn_date_safe(text):
    if not isinstance(text,str) or not text.strip():
        return False
    try:return _gameday(text)<CUTOFF
    except (TypeError,ValueError):return False

def ftn_safe_history(ftn_rows,schedule_day):
    """Accept only contemporaneously charted matches, not retroactive loads."""
    result=[]
    for r in ftn_rows:
        if int(r["season"]) not in TRAINING_SEASONS:
            raise ValueError("non_pre2024_ftn_season")
        gid=str(r["nflverse_game_id"])
        day=schedule_day.get(gid)
        if day is None:continue
        _gameday(day)
        if not _ftn_date_safe(r.get("date_pulled")):
            continue
        result.append(r)
    return result

def aggregate_games(pbp_rows,schedule_day,player_position=None,ftn_rows=()):
    """Return completed team-game rows for pre2024 games only.

    PBP downstream pass depth and RB target rates are short-pass/checkdown
    *proxies*, not verified first-read/checkdown labels.
    """
    player_position=player_position or {}
    ftn={}
    for r in ftn_safe_history(ftn_rows,schedule_day):
        k=(str(r["nflverse_game_id"]),int(r["nflverse_play_id"]))
        if k in ftn:raise ValueError("duplicate_ftn_play")
        ftn[k]=r
    groups=defaultdict(lambda:defaultdict(float))
    coverage={"pbp_plays":0,"ftn_eligible_plays":len(ftn),"ftn_joined_pbp_plays":0,
              "ftn_disallowed_or_missing":len(ftn_rows)-len(ftn),"pre2024_games":set()}
    for r in pbp_rows:
        season=int(r.get("season",0))
        if season not in TRAINING_SEASONS:
            raise ValueError("training_pbp_season_not_pre2024")
        gid=str(r.get("game_id") or "")
        if gid not in schedule_day:continue
        day=_gameday(schedule_day[gid])
        posteam=r.get("posteam");defteam=r.get("defteam")
        if not posteam or not defteam or posteam==defteam:continue
        if r.get("season_type")!="REG":continue
        pas=_yes(r.get("pass_attempt"));rush=_yes(r.get("rush_attempt"))
        drop=_yes(r.get("qb_dropback"))
        if not (pas or rush or drop):continue
        key=(gid,day.isoformat(),season,int(r.get("week") or 0),str(posteam),str(defteam))
        v=groups[key]
        v["pass_attempts"]+=float(pas)
        v["rush_attempts"]+=float(rush)
        v["dropbacks"]+=float(drop)
        v["sacks"]+=float(_yes(r.get("sack")))
        v["qb_hits"]+=float(_yes(r.get("qb_hit")))
        if pas:
            air=r.get("air_yards")
            short=air is not None and _metric(air,1e6)<=5.
            v["short_pass_attempts"]+=float(short)
            v["pass_completions"]+=float(_yes(r.get("complete_pass")))
            v["short_pass_completions"]+=float(short and _yes(r.get("complete_pass")))
            rb=player_position.get(str(r.get("receiver_player_id")),None)=="RB"
            v["rb_targets"]+=float(rb)
            v["short_rb_targets"]+=float(rb and short)
            v["passing_yards"]+=_metric(r.get("passing_yards"))
        if rush:
            v["rushing_yards"]+=_metric(r.get("rushing_yards"))
        score=r.get("score_differential")
        if (score is not None and abs(_metric(score,1000.))<=7.
                and int(_metric(r.get("qtr"),5.))<=3):
            v["neutral_passes"]+=float(pas)
            v["neutral_rushes"]+=float(rush)
        ft=ftn.get((gid,int(r.get("play_id") or -1)))
        if ft:
            coverage["ftn_joined_pbp_plays"]+=1
            read=str(ft.get("read_thrown") or "").strip().upper()
            if read=="CHK":v["charted_checkdowns"]+=1
            if read=="DES":v["charted_designed_reads"]+=1
            if read=="SD":v["charted_scramble_drill"]+=1
            v["charted_blitzers"]+=_metric(ft.get("n_blitzers"))
            v["charted_dropbacks"]+=float(drop)
            v["charted_screen_passes"]+=float(_yes(ft.get("is_screen_pass")))
        coverage["pbp_plays"]+=1
        coverage["pre2024_games"].add(gid)
    rows=[]
    for (gid,day,season,week,team,opp),v in sorted(groups.items()):
        if v["pass_attempts"]+v["rush_attempts"]<5:continue
        rows.append(dict(game_id=gid,gameday=day,season=season,week=week,
            team=team,opponent=opp,**dict(v)))
    coverage["pre2024_games"]=len(coverage["pre2024_games"])
    return rows,coverage

NGS_FIELDS={
 "passing":("avg_time_to_throw","avg_intended_air_yards",
    "completion_percentage_above_expectation","expected_completion_percentage",
    "aggressiveness","attempts"),
 "receiving":("avg_separation","avg_cushion","avg_intended_air_yards",
    "avg_expected_yac","avg_yac_above_expectation","targets"),
 "rushing":("expected_rush_yards","rush_yards_over_expected_per_att",
    "percent_attempts_gte_eight_defenders","rush_attempts"),
}

def ngs_pre2024_rows(data,stat_type,schedule_by_season_week):
    if stat_type not in NGS_FIELDS:raise ValueError("unregistered_ngs_market")
    keep=[]
    for row in data:
        season=int(row.get("season") or 0)
        week=int(row.get("week") or 0)
        if season not in TRAINING_SEASONS:raise ValueError("2024_plus_ngs_season_forbidden")
        if row.get("season_type") not in ("REG",None):continue
        # A 2023-season week played in January 2024 is NOT training data.
        team=str(row.get("team_abbr") or "")
        day=schedule_by_season_week.get((season,week,team))
        if day is None:continue
        _gameday(day)
        pid=str(row.get("player_gsis_id") or "")
        if not pid:continue
        vals={k:_metric(row.get(k),None) for k in NGS_FIELDS[stat_type]}
        keep.append(dict(player_id=pid,season=season,week=week,team=team,
                         gameday=str(day),**vals))
    return keep

def assert_pre2024_training_inputs(*,player_rows,pbp_games,ngs_rows,ftn_rows=()):
    for kind,rows in (("players",player_rows),("pbp",pbp_games),("ngs",ngs_rows)):
        for row in rows:
            day=row.get("game_date",row.get("gameday"))
            if day is None:raise ValueError(kind+"_missing_game_date")
            _gameday(day)
            season=int(row.get("season",0))
            if season not in TRAINING_SEASONS:
                raise ValueError(kind+"_2024_plus_training_observation")
    for r in ftn_rows:
        if not _ftn_date_safe(r.get("date_pulled")):
            raise ValueError("ftn_provenance_after_pre2024_cutoff")
    return True
