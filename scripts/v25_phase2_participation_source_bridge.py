"""NFL 2024 research bridge: assemble *strictly earlier* roster and snaps.

Current injury data may be included only if its recorded modification time
precedes the current game's per-event forecast freeze. Original 2024 snapshot
capture is unavailable, so all retrospective injury evidence is downgraded.
Current-week roster snapshots, realized snaps, targets, final scores and
routes are NEVER used as input. All source rows are research-only.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import math

ROLES={"WR","TE","RB"}
OFFICIAL_STATUS={"ACT","INA","RES","DEV","CUT"}
READABLE_INJURY={"Out","Doubtful","Questionable","Note"}

def _parse_date(value):
    if isinstance(value,datetime):
        return value.astimezone(timezone.utc) if value.tzinfo is not None else None
    if isinstance(value,str):
        try:
            x=datetime.fromisoformat(value.replace("Z","+00:00"))
            return x.astimezone(timezone.utc) if x.tzinfo is not None else None
        except ValueError:
            return None
    return None

def _season_week(row):
    try:
        year=int(row["season"]);week=int(row["week"])
    except (KeyError,ValueError,TypeError):
        return None
    if year not in (2021,2022,2023,2024) or not 1<=week<=18:
        return None
    return year,week

def _pregame_freeze_for_event(schedule):
    day=schedule["gameday"]
    clock=schedule.get("gametime")
    if not day or not clock:
        raise ValueError("missing_kickoff_schedule_time")
    local=datetime.fromisoformat(str(day)+"T"+str(clock))
    cutoff=local.replace(tzinfo=ZoneInfo("America/New_York")).astimezone(
        timezone.utc)-timedelta(hours=2)
    return cutoff

def collect_nfl_source_context(nflreadpy):
    """Load public sources without assuming they were originally frozen."""
    players=nflreadpy.load_players().select(["gsis_id","pfr_id"]).to_dicts()
    pfr_map=defaultdict(set)
    for row in players:
        if isinstance(row["gsis_id"],str) and row["gsis_id"] and isinstance(row["pfr_id"],str) and row["pfr_id"]:
            pfr_map[row["pfr_id"]].add(row["gsis_id"])
    unique_pfr={key:next(iter(values)) for key,values in pfr_map.items() if len(values)==1}

    raw_rosters=nflreadpy.load_rosters_weekly(
        seasons=[2021,2022,2023,2024]).select([
            "season","week","team","gsis_id","position","status","game_type"
        ]).to_dicts()
    rosters=[]
    seen=set()
    for row in raw_rosters:
        key=_season_week(row)
        if key is None or row["game_type"]!="REG" or row["position"] not in ROLES:continue
        pid=row["gsis_id"];team=row["team"]
        if not isinstance(pid,str) or not pid or not isinstance(team,str):continue
        identity=(*key,team,pid)
        if identity in seen:continue
        seen.add(identity)
        rosters.append({
          "season":key[0],"week":key[1],"team":team,
          "player_id":pid,"role":row["position"],
          "status":row["status"] if row["status"] in OFFICIAL_STATUS else "OTHER",
          "source_claim":"prior_week_archive_unverified_original_capture",
        })

    raw_snap=nflreadpy.load_snap_counts(
        seasons=[2021,2022,2023,2024]).select([
          "season","week","team","pfr_player_id","position",
          "offense_snaps","offense_pct","game_id","game_type"
        ]).to_dicts()
    plays={}
    for x in raw_snap:
        key=_season_week(x)
        if key is None or x["game_type"]!="REG":continue
        off=x["offense_snaps"]
        if not isinstance(off,(int,float)) or not math.isfinite(off) or off<0:continue
        game=(key[0],key[1],x["team"],x["game_id"])
        plays[game]=max(plays.get(game,0.),float(off))
    snaps=[];seen=set()
    for x in raw_snap:
        key=_season_week(x)
        if key is None or x["game_type"]!="REG" or x["position"] not in ROLES:continue
        pid=unique_pfr.get(x["pfr_player_id"])
        if not pid:continue
        team=x["team"];ident=(*key,team,pid)
        if ident in seen:continue
        seen.add(ident)
        off=x["offense_snaps"]
        if not isinstance(off,(float,int)) or not math.isfinite(off) or off<0:continue
        played=plays.get((key[0],key[1],team,x["game_id"]),0.)
        if played<1 or off>played+1:continue
        snap_share=x["offense_pct"]
        if not isinstance(snap_share,(int,float)) or not math.isfinite(snap_share):
            snap_share=off/played
        if not 0<=snap_share<=1.01:continue
        snaps.append({
          "season":key[0],"week":key[1],"team":team,
          "player_id":pid,"role":x["position"],
          "offense_snaps":float(off),"offense_pct":float(snap_share),
          "team_plays":float(played),
          "source_claim":"previously_finished_game_postgame_exposure",
        })
    raw_inj=nflreadpy.load_injuries(
        seasons=[2024]).select([
         "season","week","team","gsis_id","position",
         "report_status","date_modified","game_type"
        ]).to_dicts()
    injuries=defaultdict(list)
    for row in raw_inj:
        key=_season_week(row)
        if key is None or key[0]!=2024 or row["game_type"]!="REG":continue
        if row["position"] not in ROLES:continue
        pid=row["gsis_id"]
        if not isinstance(pid,str) or not pid:continue
        m=_parse_date(row["date_modified"])
        if m is None:continue
        injuries[(key[1],row["team"])].append({
          "player_id":pid,"role":row["position"],"date_modified":m,
          "report_status":row["report_status"] if row["report_status"] in READABLE_INJURY else "Unspecified",
        })
    schedule=nflreadpy.load_schedules(
        seasons=[2024]).select([
          "season","week","game_type","game_id","gameday",
          "gametime","home_team","away_team"
        ]).to_dicts()
    game_cutoffs={}
    for x in schedule:
        k=_season_week(x)
        if k is None or k[0]!=2024 or x["game_type"]!="REG":continue
        when=_pregame_freeze_for_event(x)
        for team in (x["home_team"],x["away_team"]):
            game_cutoffs[(k[1],x["game_id"],team)]=when
    return {
       "rosters":rosters,"snaps":snaps,
       "injuries":dict(injuries),"cutoffs":game_cutoffs,
       "counts":{"weekly_roster_rows":len(rosters),
                 "snap_rows_with_unambiguous_pfr_to_gsis":len(snaps),
                 "n_unique_pfr_mapping":len(unique_pfr),
                 "n_current_injury_modification_rows":sum(map(len,injuries.values())),
                 "2024_schedule_team_entries":len(game_cutoffs)},
       "source_certified":False,
    }

def build_asof_context(context,week,pregame_schedule):
    """Match original current-week game ID, reject any future history labels."""
    previous=lambda item:item["season"]<2024 or item["season"]==2024 and item["week"]<week
    candidates={s["team"] for s in pregame_schedule}
    rosters=[x for x in context["rosters"]
             if previous(x) and x["team"] in candidates]
    snaps=[x for x in context["snaps"]
           if previous(x) and x["team"] in candidates]
    inj=[]
    for game in pregame_schedule:
        cutoff=context["cutoffs"].get((week,game["event_id"],game["team"]))
        if cutoff is None:
            raise ValueError("2024_schedule_does_not_match_source_kickoff")
        eligible=[x for x in context["injuries"].get((week,game["team"]),[])
                  if x["date_modified"]<=cutoff]
        # Keep latest unique player observation as of this GAME only.
        latest={}
        for x in sorted(eligible,key=lambda r:r["date_modified"]):
            latest[x["player_id"]]=x
        for x in latest.values():
            inj.append({
              "week":week,"event_id":game["event_id"],"team":game["team"],
              "player_id":x["player_id"],"role":x["role"],
              "report_status":x["report_status"],
              "date_modified":x["date_modified"].isoformat(),
              "freeze_at":cutoff.isoformat(),
              "source_claim":"retrospectively_retrieved_dated_report_not_original_capture",
            })
    assert all(previous(x) for x in rosters) and all(previous(x) for x in snaps)
    return {
      "lagged_roster_context":rosters,
      "lagged_snap_context":snaps,
      "dated_pregame_injury_context":inj,
      "source_provenance_assertion":"RESEARCH_ONLY_UNVERIFIED_ORIGINAL_2024_CAPTURE",
    }
