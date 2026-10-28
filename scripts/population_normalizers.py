"""Source-verified NHL goalie/skater + NBA boxscore normalization.

No bookmaker or historical price calls. Every row must be a completed
regular-season game with a stable player ID, a non-missing stat and observed
minutes. Missing players/stat columns are never replaced with zeros.
"""
from __future__ import annotations
import math
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import population_history as store

NHL_BASE="https://api-web.nhle.com/v1"
NBA_BASE="https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
NBA_LABELS={
 "points":("PTS","points"),
 "rebounds":("REB","totalRebounds"),
 "assists":("AST","assists"),
 "threes":("3PM","FG3M","3PTM","threePointFieldGoalsMade","3PT","3P","3FG"),
 "steals":("STL","steals"),
 "blocks":("BLK","blocks"),
 "turnovers":("TO","turnovers"),
}
NBA_COMBOS={"pra":("points","rebounds","assists"),"pr":("points","rebounds"),
            "pa":("points","assists"),"ra":("rebounds","assists")}


def minutes(value):
    if isinstance(value,str):
        value=value.strip()
        if ":" in value:
            parts=value.split(":")
            if len(parts)!=2 or not all(x.isdigit() for x in parts):
                raise ValueError("invalid_minutes_clock")
            m,s=map(int,parts)
            if s>=60:return None
            value=m+s/60
        else:
            try:value=float(value)
            except ValueError:return None
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<value<=65:
        return None
    return round(float(value),6)


def count(value):
    if isinstance(value,bool) or value is None:return None
    if isinstance(value,int):return value if 0<=value<=200 else None
    if isinstance(value,str) and re.fullmatch(r"\d+",value.strip()):
        v=int(value.strip());return v if v<=200 else None
    return None


def made_from_attempt_pair(value):
    """ESPN three-point field goal pair encodes makes-attempts, e.g. '3-8'."""
    if not isinstance(value,str):return None
    match=re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*",value)
    if not match:return None
    made,attempted=map(int,match.groups())
    return made if 0<=made<=attempted<=60 else None


def nhl_game(raw,day,expected_id=None):
    gid=raw.get("id") if isinstance(raw,dict) else None
    if isinstance(gid,bool) or not isinstance(gid,int) or str(gid)[4:6]!="02":
        raise ValueError("invalid_nhl_regular_season_game")
    if expected_id is not None and str(expected_id)!=str(gid):
        raise ValueError("nhl_boxscore_game_id_mismatch")
    if raw.get("gameDate") is not None and str(raw["gameDate"])!=str(day):
        raise ValueError("nhl_boxscore_game_date_mismatch")
    if raw.get("gameState") not in ("FINAL","OFF"):
        raise ValueError("uncompleted_nhl_game")
    teams={side:(raw.get(side) or {}).get("abbrev") for side in ("awayTeam","homeTeam")}
    if not all(isinstance(v,str) for v in teams.values()) or teams["awayTeam"]==teams["homeTeam"]:
        raise ValueError("invalid_nhl_teams")
    box=raw.get("playerByGameStats")
    if not isinstance(box,dict):raise ValueError("missing_nhl_boxscore")
    digest=store.source_hash(raw)
    result=[]
    for side,opposite in (("awayTeam","homeTeam"),("homeTeam","awayTeam")):
        team_box=box.get(side)
        if not isinstance(team_box,dict):raise ValueError("incomplete_nhl_team_boxscore")
        for group,position in (("forwards","F"),("defense","D"),("goalies","G")):
            players=team_box.get(group)
            if not isinstance(players,list):raise ValueError("missing_nhl_player_group")
            for player in players:
                ident=player.get("playerId")
                if isinstance(ident,bool) or not isinstance(ident,int):continue
                exposure=minutes(player.get("toi"))
                if exposure is None:continue
                stats={"hits":player.get("hits"),
                       "blocked shots":player.get("blockedShots"),
                       "shots on goal":player.get("sog")} if position!="G" else {"saves":player.get("saves")}
                for stat,raw_value in stats.items():
                    value=count(raw_value)
                    # NHL goalie saves sometimes arrive as 'SAVES/SHOTS',
                    # but cannot be inferred when the response is ambiguous.
                    if stat=="saves" and isinstance(raw_value,str) and "/" in raw_value:
                        first,sep,second=raw_value.partition("/")
                        if first.strip().isdigit() and second.strip().isdigit() and int(first)<=int(second):
                            value=count(first.strip())
                    if value is None:continue
                    result.append(store.make(sport="NHL",stat=stat,game_id=gid,game_date=day,
                        season=str(gid)[:4],player_id=ident,position=position,
                        team=teams[side],opponent=teams[opposite],home=side=="homeTeam",
                        value=value,workload=exposure,workload_unit="minutes",
                        source_url=f"{NHL_BASE}/gamecenter/{gid}/boxscore",source_sha256=digest))
    if len(result)<20:raise ValueError("incomplete_nhl_multi_stat_boxscore")
    return result


def nba_game(payload,day,expected_id):
    if not isinstance(payload,dict) or not isinstance(payload.get("boxscore"),dict):
        raise ValueError("missing_espn_nba_boxscore")
    teams=payload["boxscore"].get("players")
    if not isinstance(teams,list) or len(teams)!=2:
        raise ValueError("invalid_espn_nba_team_boxscores")
    header=payload.get("header") or {}
    comps=header.get("competitions") or []
    if not isinstance(comps,list) or not comps or str(comps[0].get("id"))!=str(expected_id):
        raise ValueError("espn_game_id_mismatch")
    contestants=comps[0].get("competitors") or []
    home_code=next(((c.get("team") or {}).get("abbreviation") for c in contestants if c.get("homeAway")=="home"),None)
    away_code=next(((c.get("team") or {}).get("abbreviation") for c in contestants if c.get("homeAway")=="away"),None)
    if not home_code or not away_code or home_code==away_code:
        raise ValueError("nba_home_away_unverified")
    season=header.get("season") or {}
    season_year=season.get("year")
    if not isinstance(season_year,int):raise ValueError("nba_season_not_verified")
    digest=store.source_hash(payload)
    output=[]
    seen=set()
    for team in teams:
        code=(team.get("team") or {}).get("abbreviation")
        if code not in (home_code,away_code):
            raise ValueError("nba_boxscore_unrecognized_team")
        opponent=away_code if code==home_code else home_code
        for category in team.get("statistics") or []:
            labels=category.get("labels") or category.get("names") or []
            if not isinstance(labels,list):continue
            for athlete in category.get("athletes") or []:
                ident=(athlete.get("athlete") or {}).get("id")
                if ident is None:continue
                stats=athlete.get("stats") or []
                if not isinstance(stats,list) or len(stats)!=len(labels):
                    continue
                values={str(k):v for k,v in zip(labels,stats)}
                exposure=minutes(values.get("MIN",values.get("minutes")))
                if exposure is None:continue
                key=str(ident)
                if (code,key) in seen:continue
                seen.add((code,key))
                player_stats={}
                for market,aliases in NBA_LABELS.items():
                    for label in aliases:
                        parsed=count(values.get(label))
                        if parsed is None and market=="threes" and label in ("3PT","3P","3FG"):
                            parsed=made_from_attempt_pair(values.get(label))
                        if parsed is not None:
                            player_stats[market]=parsed
                            break
                for market,parts in NBA_COMBOS.items():
                    if all(k in player_stats for k in parts):
                        player_stats[market]=sum(player_stats[k] for k in parts)
                position=(athlete.get("athlete") or {}).get("position") or {}
                pos=position.get("abbreviation") if isinstance(position,dict) else str(position)
                for market,value in player_stats.items():
                    output.append(store.make(sport="NBA",stat=market,
                        game_id=expected_id,game_date=day,season=str(season_year),
                        player_id=ident,position=pos or "UNK",
                        team=code,opponent=opponent,home=code==home_code,
                        value=value,workload=exposure,workload_unit="minutes",
                        source_url=f"{NBA_BASE}/summary?event={expected_id}",
                        source_sha256=digest))
    if len({r["player_id"] for r in output})<10:
        raise ValueError("incomplete_espn_nba_player_stats")
    return output


def scoreboard_games(sport,board,day):
    if not isinstance(board,dict) or not isinstance(board.get("events"),list):
        raise ValueError("missing_espn_events")
    results=[]
    for event in board["events"]:
        season=event.get("season") or {}
        if season.get("type")!=2:continue
        status=(event.get("status") or {}).get("type") or {}
        if status.get("completed") is not True:
            raise ValueError("nba_past_game_not_final")
        game_id=event.get("id")
        if not game_id or not str(game_id).isdigit():
            raise ValueError("missing_espn_event_id")
        results.append(str(game_id))
    if len(results)!=len(set(results)):raise ValueError("duplicate_scoreboard_events")
    return results
