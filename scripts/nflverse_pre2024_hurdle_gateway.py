"""Unified nflreadpy historical context for zero-stat research challengers.

Never read 2024+ seasons in training. 2023+ participation is FTN released
AFTER the season, hence NOT admissible in the strict 2024 holdout.
2021–22 NGS-sourced participation is used only as a *dropback presence*
proxy: it is NOT an actual routes-run rate. Injury row date_modified must
precede kickoff and 2024; unverified reports stay missing.

These loaders are optional, strictly pre2024, and fail closed. All data are
indexed by canonical GSIS IDs and nflverse game IDs. FTN 2023 participation
is deliberately quarantined, including when loading via nflreadpy.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date,datetime,timezone
import re,math
CUTOFF=date(2024,1,1)
PARTICIPATION_ALLOWED_YEARS=(2021,2022)
YEAR_RANGE=(2021,2022,2023)
_ID_RE=re.compile(r"^[0-9A-Za-z-]{3,32}$")
_PERSONNEL11=re.compile(r"(?i)\b1\s*RB\s*,\s*1\s*TE\s*,\s*3\s*WR\b")
SOURCE_VERSION="nflreadpy_asof_2023_12_31_zero_hurdle_v1"

def _date(v):
    if v is None:raise ValueError("missing_observation_date")
    return date.fromisoformat(str(v)[:10])

def _check(year,day):
    if int(year) not in YEAR_RANGE or _date(day)>=CUTOFF:
        raise ValueError("2024_plus_observation_forbidden")

def _play_id(value):
    """nflreadpy PBP play_id can be 40.0 while participation is 40."""
    try:
        f=float(value)
        if not math.isfinite(f) or not f.is_integer():return None
        return int(f)
    except (TypeError,ValueError):
        return None

def player_ids(val):
    """Parse delimiter-separated GSIS identities, not substring matches."""
    if val is None:return frozenset()
    if isinstance(val,(list,tuple,set)):parts=val
    else:parts=re.split(r"[;,|\s]+",str(val))
    return frozenset(str(x) for x in parts if _ID_RE.fullmatch(str(x)))

def summarize_participation(rows,schedule):
    """Return player dropback-presence proxy and opponent offense 11-personnel.

    Requires game-level schedule dates. Only 2021-22 NGS participation allowed.
    Numerator: offensive play presence when dropback; denominator: all team
    dropbacks. Presence on the field does not certify a route was run.
    """
    team_dropbacks=defaultdict(int)
    team11=defaultdict(int)
    teamoffplays=defaultdict(int)
    player_db=defaultdict(int)
    players_by_team=defaultdict(set)
    outgame={}
    seen=set()
    for r in rows:
        gid=str(r.get("nflverse_game_id") or "")
        if gid not in schedule:continue
        fixture=schedule[gid]
        _check(fixture["season"],fixture["gameday"])
        if int(fixture["season"]) not in PARTICIPATION_ALLOWED_YEARS:
            raise ValueError("ftn_2023_participation_postseason_leakage")
        key=(gid,_play_id(r.get("play_id")))
        if key in seen:raise ValueError("duplicate_participation_play")
        seen.add(key)
        offense=str(r.get("possession_team") or "")
        if offense not in (fixture["home_team"],fixture["away_team"]):continue
        opponent=fixture["away_team"] if offense==fixture["home_team"] else fixture["home_team"]
        if not r.get("offense_personnel"):continue
        teamoffplays[(gid,offense)]+=1
        if _PERSONNEL11.search(str(r["offense_personnel"])):
            team11[(gid,offense)]+=1
        # Require verified dropback field from PBP joined by play id upstream,
        # rather than treating every participation play as a passing play.
        if r.get("qb_dropback") not in (True,1,"1"):continue
        team_dropbacks[(gid,offense)]+=1
        for pid in player_ids(r.get("offense_players")):
            player_db[(gid,offense,pid)]+=1
            players_by_team[(gid,offense)].add(pid)
        outgame[(gid,offense)]={
            "gameday":str(fixture["gameday"]),"season":int(fixture["season"]),
            "week":int(fixture["week"]), "team":offense,"opponent":opponent}
    byplayer=defaultdict(list);byopponent=defaultdict(list)
    for (gid,team),info in outgame.items():
        n=team_dropbacks[(gid,team)]
        if n<8:continue
        for pid in players_by_team[(gid,team)]:
            count=player_db[(gid,team,pid)]
            byplayer[pid].append({**info,"dropback_presence_rate":count/n,
               "source":"2021_22_NGS_participation_not_routes"})
    for (gid,team),count in teamoffplays.items():
        if count<12:continue
        f=schedule[gid];opp=f["away_team"] if team==f["home_team"] else f["home_team"]
        byopponent[team].append({"gameday":str(f["gameday"]),
           "offense_team":team,"opponent_defense":opp,
           "offense_11_personnel_share":team11[(gid,team)]/count,
           "source":"2021_22_NGS_participation_only"})
    for d in (byplayer,byopponent):
        for k in d:d[k].sort(key=lambda r:r["gameday"])
    return {"player_dropback_presence":dict(byplayer),
            "offense_11_personnel":dict(byopponent),
            "provenance":{"source":"nflreadpy.load_participation(2021,2022)",
               "2023_ftn_participation_used":False,"actual_routes_run_available":False,
               "observations_after_2023":0}}

def parse_injury_history(rows,schedule):
    """Only officially timestamped pregame statuses; active is NOT inferred.
    'Emergency only' is not exposed as a standardized nflverse designation.
    """
    out=defaultdict(list)
    lookup={(int(v["season"]),int(v["week"]),str(team)):(str(v["gameday"]),v)
      for v in schedule.values() for team in (v["home_team"],v["away_team"])}
    for r in rows:
        season=int(r.get("season") or 0);week=int(r.get("week") or 0)
        if season not in YEAR_RANGE:raise ValueError("post2023_injuries_entered_training")
        pid=str(r.get("gsis_id") or "")
        team=str(r.get("team") or "")
        if not pid or (season,week,team) not in lookup:continue
        gameday,_=lookup[(season,week,team)]
        if _date(gameday)>=CUTOFF:continue
        modified=r.get("date_modified")
        if not modified:continue
        stamp=str(modified)
        try:day=_date(stamp)
        except (ValueError,TypeError):continue
        if day>=_date(gameday) or day>=CUTOFF:continue
        status=str(r.get("report_status") or "").strip().lower()
        if status not in ("questionable","doubtful","out","probable",""):
            status="unknown"
        out[(pid,season,week)].append({"gameday":gameday,
          "date_modified":stamp,"status":status,
          "injury":str(r.get("report_primary_injury") or "").lower(),
          "source":"nflreadpy.load_injuries","team":team,
          "active_for_game_verified":False})
    return {k:sorted(v,key=lambda r:r["date_modified"])[-1]
            for k,v in out.items()}

def load_nflreadpy_strict_pre2024_context(*,include_participation=True,
                                         include_injuries=True):
    import nflreadpy
    schedules={}
    for year in YEAR_RANGE:
        for r in nflreadpy.load_schedules(seasons=[year]).to_dicts():
            if r.get("game_type")!="REG":continue
            day=str(r.get("gameday") or "")
            if not day or _date(day)>=CUTOFF:continue
            schedules[str(r["game_id"])]={
               "season":year,"week":int(r["week"]),"gameday":day,
               "home_team":r["home_team"],"away_team":r["away_team"]}
    participation={}
    if include_participation:
        rows=[]
        for year in PARTICIPATION_ALLOWED_YEARS:
            # Gateway reads only older NGS participation. Current 2023 FTN
            # participation is expressly forbidden by the strict cutoff.
            df=nflreadpy.load_participation(seasons=[year])
            rows.extend(df.select("nflverse_game_id","play_id",
               "possession_team","offense_personnel","offense_players").to_dicts())
        # PBP is allowed only for pre-2024 games; add canonical dropback label.
        dropbacks=set()
        for year in PARTICIPATION_ALLOWED_YEARS:
            frame=nflreadpy.load_pbp(seasons=[year])
            for r in frame.select("game_id","play_id","qb_dropback").to_dicts():
                if r.get("qb_dropback") in (True,1,"1"):
                    dropbacks.add((str(r["game_id"]),_play_id(r.get("play_id"))))
        for row in rows:
            row["qb_dropback"]=(str(row["nflverse_game_id"]),_play_id(row.get("play_id"))) in dropbacks
        participation=summarize_participation(rows,schedules)
    injuries={}
    if include_injuries:
        rows=[]
        for year in YEAR_RANGE:
            rows.extend(nflreadpy.load_injuries(seasons=[year]).to_dicts())
        injuries=parse_injury_history(rows,schedules)
    return {"participation":participation,"injuries":injuries,
        "source":"nflreadpy_unified","cutoff_exclusive":CUTOFF.isoformat(),
        "training_years":list(YEAR_RANGE),
        "ftn_participation_2023_plus":False,"features_from_2024_plus":False}
