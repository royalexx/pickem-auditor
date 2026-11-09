"""As-of source-safe NFL active-zero signals. Train/evaluate strictly pre-2024.

2023+ FTN read convention:
  '0': primary; '1': secondary; '2': third-or-later; 'CHK': checkdown,
  'DES': designed; 'SD': scramble drill.
FTN's available 2023 records have date_pulled=2024-09-06 and are NOT
admissible in a pre-2024 training/validation campaign.

nflverse participation (2023 onward) was delivered AFTER the season.
Use <=2022 NGS participation only, provided archival provenance qualifies.
Play participation demonstrates snap-on-field, NOT individual route run.
Injury designation is only a *reported risk signal*, never a conclusion
about an individual's actual 2024 active/limited game status.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime, timezone
import math,re

CUTOFF=date(2024,1,1)
FTN_CODES_2023_PLUS={
    "0":"primary",
    "1":"secondary",
    "2":"third_or_later",
    "CHK":"checkdown",
    "DES":"designed",
    "SD":"scramble_drill",
}
ALLOWED_PRE2024_PARTICIPATION_SEASONS=frozenset(range(2016,2023))
INJURY_DESIGNATIONS={"OUT":0,"DOUBTFUL":1,"QUESTIONABLE":2,"PROBABLE":3}

def _date(text):
    return date.fromisoformat(str(text)[:10])

def _timestamp(text):
    if isinstance(text,datetime):dt=text
    elif isinstance(text,str) and text.strip():
        try:dt=datetime.fromisoformat(text.replace("Z","+00:00"))
        except ValueError:raise ValueError("invalid_source_timestamp")
    else:raise ValueError("missing_source_timestamp")
    if dt.tzinfo is None:raise ValueError("source_timestamp_needs_timezone")
    return dt.astimezone(timezone.utc)

def decode_ftn_read(row):
    season=int(row.get("season",0))
    if season<2023:raise ValueError("2023_plus_ftn_convention_only")
    code=str(row.get("read_thrown") or "").strip().upper()
    if code not in FTN_CODES_2023_PLUS:
        return None
    return FTN_CODES_2023_PLUS[code]

def pre2024_ftn_read(row,*,kickoff_utc):
    if int(row.get("season",0))!=2023:
        raise ValueError("ftn_not_2023_train_eligible")
    pulled=_timestamp(row.get("date_pulled"))
    kickoff=_timestamp(kickoff_utc)
    # Strict experiment asof must precede 2024 even if the game is 2023.
    if pulled.date()>=CUTOFF or pulled>=kickoff:
        return None,"retrospective_or_postkickoff_charting_quarantined"
    return decode_ftn_read(row),"ftn_charted_and_source_available_pre2024"

def _identities(s):
    if not isinstance(s,str):return frozenset()
    # nflverse fields are space/comma separated GSIS IDs; parse exact GSIS
    # tokens, never loose player-name substrings.
    return frozenset(re.findall(r"(?:00-\d{7}|\d{10})",s))

def _eleven_personnel(text):
    if not isinstance(text,str):return False
    matches={m.group(2).upper():int(m.group(1)) for m in
        re.finditer(r"(\d+)\s*(RB|TE|WR)\b",text.upper())}
    return matches.get("RB")==1 and matches.get("TE")==1 and matches.get("WR")==3

def historical_participation(participation_rows,schedule_by_game):
    """Return team offense 11 rate, player on-field rates; never route rate.

    2023 records are prohibited due to after-postseason FTN release.
    Identified per-game player snap shares are observational training labels
    of earlier games, only to be used in subsequent chronological forecasts.
    """
    team_play=defaultdict(lambda:{"n":0,"eleven":0})
    player_on=defaultdict(int)
    team_offense_on=defaultdict(int)
    defensive_group=defaultdict(lambda:{"all":0,"eleven":0})
    for row in participation_rows:
        year=int(row.get("season") or str(row.get("nflverse_game_id",""))[:4])
        if year not in ALLOWED_PRE2024_PARTICIPATION_SEASONS:
            raise ValueError("participation_2023_ftn_or_2024_plus_quarantined")
        game=str(row.get("nflverse_game_id") or "")
        day=schedule_by_game.get(game)
        if day is None:continue
        if _date(day)>=CUTOFF:raise ValueError("2024_plus_participation_label")
        team=str(row.get("possession_team") or "")
        if not team:continue
        offense=_identities(row.get("offense_players"))
        defense=_identities(row.get("defense_players"))
        if not offense or not defense:continue
        key=(game,team,str(day))
        is11=_eleven_personnel(row.get("offense_personnel"))
        team_play[key]["n"]+=1
        team_play[key]["eleven"]+=int(is11)
        team_offense_on[key]+=1
        for pid in offense:player_on[(game,team,str(day),pid)]+=1
        for pid in defense:
            data=defensive_group[(game,str(day),pid)]
            data["all"]+=1
            data["eleven"]+=int(is11)
    rate={}
    for (game,team,day),m in team_play.items():
        if m["n"]>=15:
            rate[(game,team)]={"gameday":day,"offense_11_rate":m["eleven"]/m["n"],
                               "n_play":m["n"],"year":int(day[:4])}
    snap=[]
    for (game,team,day,pid),n in player_on.items():
        base=team_offense_on.get((game,team,day),0)
        if base>=15:
            snap.append({"gameday":day,"game_id":game,"team":team,"player_id":pid,
                         "offense_snap_share":n/base,"observed_offense_snaps":n,
                         "role_metric":"offense_snap_share_not_route_share"})
    defensive=[]
    for (game,day,pid),m in defensive_group.items():
        if m["all"]>=5:
            defensive.append({"gameday":day,"game_id":game,"player_id":pid,
                 "defense_snap_n":m["all"],"defense_on_11_snap_n":m["eleven"],
                 "defense_on_11_share":m["eleven"]/m["all"]})
    return {"team_11_personnel":rate,
            "player_offense_snaps":snap,"defender_personnel_exposure":defensive,
            "routes_run_rate_available":False,
            "participation_2023_used":False,
            "participation_2024_plus_used":False}

def select_pregame_injury_rows(rows,game_day_by_team_week,*,asof_utc):
    """Game reports pre-kickoff and pre-2024 only. Never assume active status.

    Data are censored to report timestamp; the latest eligible report is
    retained. No 2024 reports enter this training/validation workflow.
    """
    asof=_timestamp(asof_utc)
    if asof.date()>=CUTOFF:raise ValueError("2024_plus_injury_asof")
    selected={}
    for r in rows:
        year=int(r.get("season") or 0)
        if year not in (2021,2022,2023):
            raise ValueError("2024_plus_injury_dataset_forbidden")
        pid=str(r.get("gsis_id") or "")
        if not pid or r.get("game_type",r.get("season_type","REG"))!="REG":
            continue
        key=(year,int(r.get("week") or 0),str(r.get("team") or ""))
        game_day=game_day_by_team_week.get(key)
        if game_day is None or _date(game_day)>=CUTOFF:continue
        try:stamp=_timestamp(r.get("date_modified"))
        except ValueError:continue
        if stamp>=asof or stamp.date()>=CUTOFF or stamp.date()>=_date(game_day):
            continue
        ident=(key,pid)
        prior=selected.get(ident)
        if prior is None or stamp>prior[0]:
            selected[ident]=(stamp,{"report_status":str(r.get("report_status") or "").upper(),
                "practice_status":str(r.get("practice_status") or "").upper(),
                "injury_report_asof":stamp.isoformat(),
                "injury_body_part":str(r.get("report_primary_injury") or "").upper(),
                "source":"nflverse_pre2024_report_only",
                "actual_active_status_verified":False})
    return {k:v[1] for k,v in selected.items()}

def three_game_exposure_trend(snap_rows,player_id,asof):
    day=_date(asof)
    if day>CUTOFF:raise ValueError("2024_snap_trend_forbidden")
    h=sorted([r for r in snap_rows if str(r.get("player_id"))==str(player_id)
      and _date(r.get("gameday"))<day],key=lambda r:r["gameday"],reverse=True)
    if len(h)<6:return None
    vals=[float(r["offense_snap_share"]) for r in h[:6]]
    if any(not math.isfinite(v) or not 0<=v<=1 for v in vals):
        raise ValueError("invalid_snap_share")
    recent=sum(vals[:3])/3.
    preceding=sum(vals[3:6])/3.
    return {"recent_3game_snap_share":recent,
            "prior_3game_snap_share":preceding,
            "snap_share_change":recent-preceding,
            "route_participation_rate":None,
            "source_metric":"observed_snap_share_not_route_rate"}
