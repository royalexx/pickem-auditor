"""Synthetic, source-shaped NFL observations. Not real predictive evidence."""
from datetime import date,timedelta
import random


def season(year,weeks=16):
    rng=random.Random(year);raw={"schedule":[],"stats":[],"snaps":[],"pbp":[]}
    for week in range(1,weeks+1):
        day=(date(year,9,1)+timedelta(days=7*(week-1))).isoformat()
        for away,home in (("AAA","BBB"),("CCC","DDD")):
            gid=f"{year}_{week:02d}_{away}_{home}"
            raw["schedule"].append(dict(season=year,week=week,game_id=gid,game_type="REG",gameday=day,
                                        gametime="13:00",home_team=home,away_team=away,home_score=24,away_score=17))
            event=0
            for team,opp in ((home,away),(away,home)):
                qb="QB-"+team
                # Build through a dict update to avoid duplicate keyword fields.
                def emit(**kw):
                    nonlocal event
                    event+=1
                    p=dict(game_id=gid,play_id=event,season_type="REG",posteam=team,defteam=opp,
                           no_play=0,two_point_attempt=0,pass_attempt=0,rush_attempt=0,sack=0,
                           qb_dropback=0,receiver_player_id=None,complete_pass=0,rusher_player_id=None,
                           passer_player_id=None)
                    p.update(kw);raw["pbp"].append(p)
                attempts=0
                for slot in range(4):
                    pid=f"WR-{team}-{slot}";targets=rng.randrange(1,8);rec=rng.randrange(targets+1);carries=rng.randrange(3)
                    name=f"Receiver {team}{chr(65+slot)}";snaps=rng.randrange(25,76)
                    raw["stats"].append(dict(season=year,week=week,season_type="REG",player_id=pid,position="WR",
                        player_display_name=name,team=team,opponent_team=opp,targets=targets,receptions=rec,carries=carries))
                    raw["snaps"].append(dict(season=year,week=week,game_type="REG",game_id=gid,team=team,
                        opponent=opp,player=name,pfr_player_id="pfr"+pid,offense_snaps=snaps,defense_snaps=0))
                    for j in range(targets):
                        emit(pass_attempt=1,qb_dropback=1,receiver_player_id=pid,complete_pass=int(j<rec),passer_player_id=qb)
                    attempts+=targets
                    for _ in range(carries):emit(rush_attempt=1,rusher_player_id=pid)
                qname=f"Quarterback {team}"
                raw["stats"].append(dict(season=year,week=week,season_type="REG",player_id=qb,position="QB",
                    player_display_name=qname,team=team,opponent_team=opp,attempts=attempts,carries=2))
                raw["snaps"].append(dict(season=year,week=week,game_type="REG",game_id=gid,team=team,
                    opponent=opp,player=qname,pfr_player_id="pfr"+qb,offense_snaps=rng.randrange(45,75),defense_snaps=0))
                for _ in range(2):emit(rush_attempt=1,rusher_player_id=qb)
                emit(sack=1,qb_dropback=1,passer_player_id=qb)
                name=f"Linebacker {team}";pid="LB-"+team
                raw["stats"].append(dict(season=year,week=week,season_type="REG",player_id=pid,position="LB",
                    player_display_name=name,team=team,opponent_team=opp,def_tackles_solo=3,
                    def_tackles_with_assist=1,def_tackle_assists=2))
                raw["snaps"].append(dict(season=year,week=week,game_type="REG",game_id=gid,team=team,
                    opponent=opp,player=name,pfr_player_id="pfr"+pid,offense_snaps=0,defense_snaps=rng.randrange(40,75)))
    return raw
