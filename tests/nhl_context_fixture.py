"""Synthetic official-shaped boxscores. Never represents real NHL outcomes."""
from datetime import datetime, timedelta, timezone


def games(days=80, seed=71, goalies_per_team=2):
    import numpy as np
    import nhl_context_data as store
    rng = np.random.default_rng(seed)
    bundles = []
    teams = ["AAA", "BBB", "CCC", "DDD"]
    for day in range(days):
        rotation = day % 3
        pairs = [[(0,1),(2,3)],[(0,2),(1,3)],[(0,3),(1,2)]][rotation]
        for pair, (left,right) in enumerate(pairs):
            away, home = (left,right) if day % 2 else (right,left)
            gid = 2023020001+2*day+pair
            start = datetime(2023,10,1,23,tzinfo=timezone.utc)+timedelta(days=day)
            box = {"id": gid,"gameState":"OFF", "gameDate": start.date().isoformat(),
                   "startTimeUTC": start.isoformat(), "periodDescriptor":{"number":3,"periodType":"REG"},
                   "playerByGameStats": {}}
            shots = {t: int(rng.negative_binomial(50,50/(50+27+2*t+2*(t==home)))) for t in (away,home)}
            for side,t,op in (("homeTeam",home,away),("awayTeam",away,home)):
                box[side] = {"id":t+1, "abbrev":teams[t], "sog":shots[t]}
                allocation = rng.multinomial(shots[t],[.32,.28,.24,.16])
                players = []
                for p in range(4):
                    players.append({"playerId":1000+10*t+p,"toi":f"{16+p}:00",
                                    "sog":int(allocation[p]),"hits":int(rng.poisson(1.8)),
                                    "blockedShots":int(rng.poisson(.7+p*.25))})
                starter = 2000+10*t+day%goalies_per_team
                relief = 2000+10*t+(day+1)%goalies_per_team
                short = rng.random() < .12
                played = int(rng.integers(30,50)) if short else 59
                faced = int(rng.binomial(shots[op], played/60))
                stopped = int(rng.binomial(faced,.91))
                goalies = [{"playerId":starter,"toi":f"{played}:00","starter":True,
                            "shotsAgainst":faced,"goalsAgainst":faced-stopped,"saves":stopped}]
                if short:
                    extra = shots[op]-faced
                    saved = int(rng.binomial(extra,.91))
                    goalies.append({"playerId":relief,"toi":f"{60-played}:00","starter":False,
                                    "shotsAgainst":extra,"goalsAgainst":extra-saved,"saves":saved})
                box["playerByGameStats"][side] = {"forwards":players[:3],"defense":players[3:],"goalies":goalies}
            pbp = {"id":gid, "plays":[]}
            for side,other in (("homeTeam","awayTeam"),("awayTeam","homeTeam")):
                for _ in range(box[side]["sog"]+10):
                    pbp["plays"].append({"typeDescKey":"shot-on-goal", "periodDescriptor":{"number":1,"periodType":"REG"},
                                         "details":{"eventOwnerTeamId":box[side]["id"]}})
                pbp["plays"].append({"typeDescKey":"blocked-shot", "periodDescriptor":{"number":1,"periodType":"REG"},
                                     "details":{"shootingPlayerId":box["playerByGameStats"][side]["forwards"][0]["playerId"],
                                                "blockingPlayerId":box["playerByGameStats"][other]["forwards"][0]["playerId"]}})
            bundle = store.normalize(box, observed_at=(start+timedelta(hours=4)).isoformat(), pbp=pbp)
            bundles.append(bundle)
    return bundles


def box():
    """Minimal independent normalizer fixture, no network."""
    result={"id":2023020001,"gameDate":"2023-10-01","startTimeUTC":"2023-10-01T23:00:00Z",
            "gameState":"OFF","periodDescriptor":{"number":3,"periodType":"REG"},
            "homeTeam":{"id":1,"abbrev":"AAA","sog":4},"awayTeam":{"id":2,"abbrev":"BBB","sog":4},
            "playerByGameStats":{}}
    for i, side in enumerate(("homeTeam","awayTeam")):
        result["playerByGameStats"][side]={"forwards":[{"playerId":100+i,"toi":"18:00","sog":4,"hits":2,"blockedShots":1}],
          "defense":[],"goalies":[{"playerId":200+i,"toi":"59:00","saves":3,"shotsAgainst":4,"goalsAgainst":1,"starter":True}]}
    return result
