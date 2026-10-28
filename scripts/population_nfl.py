"""NFL regular-season weekly production + verified game/team snap workload join.

The GSIS player ID in player_stats and PFR snap count ID often differ.
We NEVER claim they are the same ID. Join exact unique game/team/player
display names only; an ambiguous/missing match is excluded and counted.
NFL rows require genuine observed offensive snaps. No guessed targets,
yards or defensive tackle exposure.
"""
from __future__ import annotations
import re
import math
import unicodedata
from datetime import date, datetime, timezone
import population_history as store

COLUMNS={
 "pass attempts":"attempts","completions":"completions",
 "targets":"targets","receptions":"receptions","carries":"carries",
 "passing touchdowns":"passing_tds","rushing touchdowns":"rushing_tds",
 "receiving touchdowns":"receiving_tds",
 "passing yards":"passing_yards","rushing yards":"rushing_yards",
 "receiving yards":"receiving_yards",
 "solo tackles":"def_tackles_solo",
 "tackle assists":"def_tackle_assists",
 "qb hits":"def_qb_hits","passes defended":"def_pass_defended",
 "tackles + assists":None,
}
SOURCE="https://github.com/nflverse/nflverse-data/releases"
OFFENSE={"QB","RB","WR","TE"}
DEFENSE={"LB","MLB","OLB","ILB","DE","DT","NT","CB","DB","S","FS","SS"}
POSITIONS=OFFENSE|DEFENSE
SNAP_MINIMUM=1

def name_key(value):
    if not isinstance(value,str):return None
    ascii_name=unicodedata.normalize("NFKD",value).encode("ascii","ignore").decode().lower()
    ascii_name=re.sub(r"\b(jr|sr|ii|iii|iv|v)\b","",ascii_name)
    chars=re.sub(r"[^a-z ]","",ascii_name)
    tokens=chars.split()
    return " ".join(tokens) if len(tokens)>=2 else None

def initials_key(value):
    full=name_key(value)
    if not full:return None
    parts=full.split()
    return (parts[0][0],parts[-1])

def game_key(season,week,team):
    return (int(season),int(week),str(team))

def safe_field(value):
    if isinstance(value,float) and not math.isfinite(value):
        return None
    return value

def normalize_season(stats,snaps,schedule,season,*,cutoff):
    """Return (long_rows, coverage). All three inputs must be trusted bulk data."""
    boundary=date.fromisoformat(cutoff)
    if not all(isinstance(x,list) for x in (stats,snaps,schedule)):
        raise ValueError("missing_nfl_bulk_source")
    games={}
    for game in schedule:
        if game.get("game_type")!="REG" or int(game.get("season",0))!=season:continue
        gid=str(game.get("game_id") or "")
        d=str(game.get("gameday") or "")
        if not gid or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",d):continue
        day=date.fromisoformat(d)
        if day>=boundary:continue
        away,home=game.get("away_team"),game.get("home_team")
        if not home or not away or home==away:continue
        for team,opponent,is_home in ((home,away,True),(away,home,False)):
            key=game_key(season,game["week"],team)
            if key in games:raise ValueError("ambiguous_nfl_schedule_team_week")
            games[key]=(gid,d,opponent,is_home)
    snap_index={}
    for row in snaps:
        if row.get("game_type")!="REG" or int(row.get("season",0))!=season:continue
        key=game_key(season,row.get("week",0),row.get("team",""))
        if key not in games:continue
        expected_gid=games[key][0]
        if str(row.get("game_id"))!=expected_gid:continue
        name=name_key(row.get("player"))
        if name is None:continue
        ident=(key,name)
        snap_index.setdefault(ident,[]).append(row)
    # Fallback matching by first initial plus surname is permitted ONLY
    # when uniquely identifying one weekly player and one PFR snap player
    # in this same game and team. Distinct source IDs never get conflated.
    snap_initials={}
    for (key,name),matches in snap_index.items():
        short=initials_key(name)
        if short:
            snap_initials.setdefault((key,short),[]).extend(matches)
    weekly_short_counts={}
    for row in stats:
        if row.get("season_type")=="REG" and row.get("position") in POSITIONS:
            key=game_key(season,row.get("week",0),row.get("team") or row.get("recent_team") or "")
            short=initials_key(row.get("player_display_name") or row.get("player_name"))
            if key in games and short:
                weekly_short_counts[(key,short)]=weekly_short_counts.get((key,short),0)+1
    output=[]
    coverage={"source":"nflreadpy.load_player_stats/load_snap_counts/load_schedules",
              "season":season,"n_schedule_team_weeks":len(games),
              "n_stats_rows":len(stats),"eligible_player_rows":0,
              "unmatched_snap_rows":0,"ambiguous_snap_rows":0,
              "invalid_player_rows":0,"written_market_rows":0}
    seen=set()
    for row in stats:
        if int(row.get("season",0))!=season or row.get("season_type")!="REG":continue
        position=row.get("position")
        if position not in POSITIONS:continue
        key=game_key(season,row.get("week",0),row.get("team") or row.get("recent_team") or "")
        if key not in games:continue
        player_id=row.get("player_id")
        if not player_id or str(player_id) in ("nan","None"):continue
        team=key[2]
        gid,day,opponent,home=games[key]
        if row.get("opponent_team") not in (None,opponent):
            coverage["invalid_player_rows"]+=1;continue
        person=name_key(row.get("player_display_name") or row.get("player_name"))
        matches=snap_index.get((key,person),[])
        if not matches:
            short=initials_key(row.get("player_display_name") or row.get("player_name"))
            if short and weekly_short_counts.get((key,short))==1:
                matches=snap_initials.get((key,short),[])
        if not matches:
            coverage["unmatched_snap_rows"]+=1;continue
        if len(matches)!=1:
            coverage["ambiguous_snap_rows"]+=1;continue
        matched=matches[0]
        exposure=matched.get("offense_snaps" if position in OFFENSE else "defense_snaps")
        if isinstance(exposure,bool) or not isinstance(exposure,(int,float)) or not SNAP_MINIMUM<=exposure<=160:
            coverage["invalid_player_rows"]+=1;continue
        dedup=(gid,str(player_id))
        if dedup in seen:
            raise ValueError("ambiguous_duplicate_nfl_player_game")
        seen.add(dedup)
        coverage["eligible_player_rows"]+=1
        source_rows={
            "weekly":{k:safe_field(row.get(k)) for k in ("season","week","player_id","position",
                "player_display_name","recent_team","team","opponent_team",
                "def_tackles_with_assist",*tuple(c for c in COLUMNS.values() if c is not None))},
            "snap":{k:safe_field(matched.get(k)) for k in ("game_id","week","season","team",
                "opponent","player","pfr_player_id","offense_snaps","defense_snaps")},
            "schedule":{k:v for k,v in zip(("game_id","gameday","opponent","home"),(gid,day,opponent,home))}}
        digest=store.source_hash(source_rows)
        for stat,column in COLUMNS.items():
            if not store.market_eligible({"sport":"NFL","stat":stat,"position":position}):
                continue
            if position in DEFENSE and stat not in ("tackles + assists","solo tackles",
                    "tackle assists","qb hits","passes defended"):
                continue
            if position in OFFENSE and stat in ("tackles + assists","solo tackles",
                    "tackle assists","qb hits","passes defended"):
                continue
            if stat=="tackles + assists":
                components=(row.get("def_tackles_solo"),row.get("def_tackles_with_assist"),
                            row.get("def_tackle_assists"))
                if any(v is None or isinstance(v,bool) or
                       not isinstance(v,(float,int)) or not float(v).is_integer() for v in components):
                    continue
                v=sum(components)
            else:
                v=row.get(column)
            if isinstance(v,bool) or not isinstance(v,(int,float)) or v is None:
                continue
            if store.family("NFL",stat)=="count":
                if not float(v).is_integer() or not 0<=v<=200:continue
                v=int(v)
            else:
                if not -150<=v<=1000:continue
                v=float(v)
            output.append(store.make(sport="NFL",stat=stat,game_id=gid,
                game_date=day,season=str(season),player_id=player_id,
                position=position,team=team,opponent=opponent,home=home,
                value=v,workload=float(exposure),workload_unit="snaps",
                source_url=SOURCE+"/tag/player_stats",
                source_sha256=digest))
    coverage["written_market_rows"]=len(output)
    return output,coverage

def fetch_season(season):
    import nflreadpy
    return (nflreadpy.load_player_stats(seasons=[season],summary_level="week").to_dicts(),
            nflreadpy.load_snap_counts(seasons=[season]).to_dicts(),
            nflreadpy.load_schedules(seasons=[season]).to_dicts())
