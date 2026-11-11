"""Official-only NHL/NBA postgame snapshot importer for certified Phase 1 cohorts.

Pure verification/extraction. Network and disk operations belong to the CLI.
Missing/future/live/DNP cases do not acquire a synthetic zero actual.
The source is a *postgame* independent artifact; it never changes the
original frozen forecast or the bookmaker quote time.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math

NBA_ABBREVS={"NY":"NYK","GS":"GSW","SA":"SAS","UTAH":"UTA",
             "NO":"NOP","PHO":"PHX","BKN":"BKN"}
NBA_FIELDS=("PTS","REB","AST","3PT")
NBA_MARKETS=("points","rebounds","assists","threes","pr","pa","ra","pra")
NHL_MARKETS=("shots on goal",)


class SettlementCaptureError(ValueError):pass


def instant(s):
    if not isinstance(s,str) or "T" not in s:
        raise SettlementCaptureError("source_time_missing")
    try: date=datetime.fromisoformat(s.replace("Z","+00:00"))
    except ValueError as exc:raise SettlementCaptureError("source_time_invalid") from exc
    if date.tzinfo is None:raise SettlementCaptureError("source_time_naive")
    return date.astimezone(timezone.utc)


def normalized_team(t,sport):
    txt=str(t or "").strip().upper()
    return NBA_ABBREVS.get(txt,txt) if sport=="NBA" else txt


def exact_int(value,label):
    if isinstance(value,bool):raise SettlementCaptureError("boolean_count:"+label)
    if isinstance(value,int):n=value
    elif isinstance(value,str) and value.isdigit():n=int(value)
    else:raise SettlementCaptureError("invalid_integer_count:"+label)
    if n<0:raise SettlementCaptureError("negative_count:"+label)
    return n


def original_event_scope(contracts):
    groups=defaultdict(list)
    for c in contracts:
        if not isinstance(c,dict) or c.get("sport") not in ("NBA","NHL"):
            raise SettlementCaptureError("unsupported_original_contract")
        key=(c["sport"],str(c["event_id"]))
        groups[key].append(c)
    result={}
    for (sport,event), rows in groups.items():
        starts={instant(c["event_start"]) for c in rows}
        if len(starts)!=1:raise SettlementCaptureError("inconsistent_frozen_game_start")
        teams={normalized_team(c["team_id"],sport) for c in rows}
        teams|={normalized_team(c["opponent_id"],sport) for c in rows}
        if len(teams)!=2:raise SettlementCaptureError("ambiguous_frozen_game_teams")
        ident=set()
        for c in rows:
            token=(str(c["player_id"]),c["stat"],float(c["line"]))
            if token in ident:raise SettlementCaptureError("duplicate_frozen_prop")
            ident.add(token)
            if c["stat"] not in (NBA_MARKETS if sport=="NBA" else NHL_MARKETS):
                raise SettlementCaptureError("unsupported_market_stat")
            if instant(c["input_freeze_at"])>=next(iter(starts)):
                raise SettlementCaptureError("nonpregame_original_input")
        result[(sport,event)]={
            "sport":sport,"event_id":event,"teams":teams,"start":next(iter(starts)),
            "contracts":rows}
    return result


def schedule_games(sport, payload, *, game_date):
    found=[]
    if sport=="NHL":
        for day in payload.get("gameWeek",[]):
            for g in day.get("games",[]):
                if day.get("date")!=game_date:continue
                found.append({"sport":"NHL","id":str(g["id"]),
                    "teams":{normalized_team(g["homeTeam"]["abbrev"],"NHL"),
                             normalized_team(g["awayTeam"]["abbrev"],"NHL")},
                    "start":instant(g["startTimeUTC"]),
                    "status":g["gameState"]})
    else:
        for e in payload.get("events",[]):
            comp=e.get("competitions",[])
            if len(comp)!=1:raise SettlementCaptureError("NBA_competition_ambiguous")
            teams={normalized_team(c["team"]["abbreviation"],"NBA")
                   for c in comp[0].get("competitors",[])}
            state=e.get("status",{}).get("type",{})
            found.append({"sport":"NBA","id":str(e["id"]),"teams":teams,
                "start":instant(e["date"]),
                "status":"FINAL" if state.get("completed") is True and
                             state.get("name")=="STATUS_FINAL"
                             else "NOT_FINAL"})
    if len(found)!=len({r["id"] for r in found}):
        raise SettlementCaptureError("duplicate_official_schedule_id")
    return found


def match_schedule(events, schedules, *, max_start_shift_minutes=90):
    unique={}
    for ident, group in events.items():
        candidates=[g for g in schedules
                    if g["sport"]==group["sport"]
                    and g["teams"]==group["teams"]
                    and abs((g["start"]-group["start"]).total_seconds())
                        <=60*max_start_shift_minutes]
        if len(candidates)>1:
            raise SettlementCaptureError("multiple_official_games_match_one_event")
        if len(candidates)==1:
            if candidates[0]["id"] in unique.values():
                raise SettlementCaptureError("one_official_game_maps_multiple_events")
            unique[ident]=candidates[0]["id"]
    return unique


def nhl_stat_rows(source, *, expected_teams):
    if source.get("gameState")!="FINAL":
        raise SettlementCaptureError("NHL_source_not_final")
    home=normalized_team(source["homeTeam"]["abbrev"],"NHL")
    away=normalized_team(source["awayTeam"]["abbrev"],"NHL")
    if {home,away}!=expected_teams:
        raise SettlementCaptureError("NHL_source_teams_mismatch")
    if source.get("limitedScoring"):
        raise SettlementCaptureError("NHL_limited_scoring")
    result={}
    for key,team in (("homeTeam",home),("awayTeam",away)):
        section=source.get("playerByGameStats",{}).get(key,{})
        for role in ("forwards","defense"):
            for p in section.get(role,[]):
                pid=str(p["playerId"])
                if pid in result:raise SettlementCaptureError("duplicate_NHL_player")
                sog=exact_int(p.get("sog"),"NHL_sog")
                toi=p.get("toi")
                if not isinstance(toi,str) or ":" not in toi:
                    raise SettlementCaptureError("NHL_missing_toi")
                mm,ss=toi.split(":")
                if not mm.isdigit() or not ss.isdigit() or int(ss)>=60:
                    raise SettlementCaptureError("NHL_invalid_toi")
                seconds=60*int(mm)+int(ss)
                if seconds<=0:continue
                result[pid]={"team":team,"shots on goal":sog,
                    "observed_workload_minutes":seconds/60,
                    "position":str(p.get("position",""))}
    if not result:raise SettlementCaptureError("NHL_final_no_skaters")
    return result


def nba_stat_rows(source, *, expected_teams):
    header=source.get("header",{}).get("competitions",[])
    if len(header)!=1:raise SettlementCaptureError("NBA_summary_missing_competition")
    status=header[0].get("status",{}).get("type",{})
    if status.get("name")!="STATUS_FINAL" or status.get("completed") is not True:
        raise SettlementCaptureError("NBA_source_not_final")
    teams={normalized_team(c["team"]["abbreviation"],"NBA")
           for c in header[0].get("competitors",[])}
    if teams!=expected_teams:raise SettlementCaptureError("NBA_source_teams_mismatch")
    out={}
    seen=set()
    for group in source.get("boxscore",{}).get("players",[]):
        team=normalized_team(group["team"]["abbreviation"],"NBA")
        if team not in teams:raise SettlementCaptureError("NBA_stat_team_not_scheduled")
        for subset in group.get("statistics",[]):
            labels=subset.get("labels",[])
            if not set(NBA_FIELDS+("MIN",)).issubset(set(labels)) or len(set(labels))!=len(labels):
                raise SettlementCaptureError("NBA_stat_labels_untrusted")
            for a in subset.get("athletes",[]):
                pid=str(a["athlete"]["id"])
                if (team,pid) in seen:raise SettlementCaptureError("NBA_duplicate_player")
                seen.add((team,pid))
                if a.get("didNotPlay") is True:continue
                raw=a.get("stats",[])
                if len(raw)!=len(labels):
                    raise SettlementCaptureError("NBA_stats_label_length_mismatch")
                data=dict(zip(labels,raw))
                minutes=data["MIN"]
                if not isinstance(minutes,str) or not minutes.strip():continue
                try:
                    if ":" in minutes:
                        m,s=minutes.split(":")
                        minutes_float=int(m)+int(s)/60
                    else: minutes_float=float(minutes)
                except (ValueError,TypeError):
                    raise SettlementCaptureError("NBA_invalid_minutes")
                if not math.isfinite(minutes_float) or minutes_float<=0:continue
                threes=data["3PT"]
                if not isinstance(threes,str) or "-" not in threes:
                    raise SettlementCaptureError("NBA_bad_3pt_string")
                made,attempts=threes.split("-",1)
                t=exact_int(made,"3PT_made")
                if t>exact_int(attempts,"3PT_attempts"):
                    raise SettlementCaptureError("NBA_made_gt_attempted")
                pts=exact_int(data["PTS"],"points")
                reb=exact_int(data["REB"],"rebounds")
                ast=exact_int(data["AST"],"assists")
                if pid in out:raise SettlementCaptureError("NBA_duplicate_player_id")
                out[pid]={"team":team,"points":pts,"rebounds":reb,"assists":ast,
                    "threes":t,"pr":pts+reb,"pa":pts+ast,"ra":reb+ast,
                    "pra":pts+reb+ast,"observed_workload_minutes":minutes_float,
                    "position":a.get("athlete",{}).get("position",{}).get("abbreviation")}
    if not out:raise SettlementCaptureError("NBA_final_no_players")
    return out


def settlement_rows_for_final(original_group, source, *, game_id, url,
                              raw_digest, source_path, observed_at):
    sport=original_group["sport"]
    rows=(nhl_stat_rows(source,expected_teams=original_group["teams"])
          if sport=="NHL" else
          nba_stat_rows(source,expected_teams=original_group["teams"]))
    if sport=="NHL" and str(source.get("id"))!=str(game_id):
        raise SettlementCaptureError("NHL_source_game_id_mismatch")
    collection=instant(observed_at)
    if collection<=original_group["start"]:
        raise SettlementCaptureError("postgame_collection_before_original_game")
    output=[];unresolved=[]
    known=set()
    for c in original_group["contracts"]:
        k=(str(c["player_id"]),c["stat"])
        if k in known:
            # Same player/stat may have multiple frozen lines. Settlement
            # identity is player/stat/game, NOT line-specific.
            continue
        known.add(k)
        actual=rows.get(str(c["player_id"]))
        if not actual:
            unresolved.append({"sport":sport,"event_id":original_group["event_id"],
                "player_id":str(c["player_id"]),"stat":c["stat"],
                "reason":"missing_or_did_not_play_in_verified_final_boxscore"})
            continue
        if actual["team"]!=normalized_team(c["team_id"],sport):
            unresolved.append({
                "sport":sport,"event_id":original_group["event_id"],
                "player_id":str(c["player_id"]),"stat":c["stat"],
                "reason":"official_player_team_disagrees_frozen_offer",
                "original_frozen_team":str(c["team_id"]),
                "official_postgame_team":actual["team"],
                "source_only_postgame_identity_evidence":True,
            })
            continue
        if c["stat"] not in actual:
            raise SettlementCaptureError("unsupported_official_stat")
        output.append({
            "sport":sport,"event_id":original_group["event_id"],
            "player_id":str(c["player_id"]),"stat":c["stat"],
            "period":"full","status":"settled",
            "actual":actual[c["stat"]],
            "source_url":url,
            "source_sha256":raw_digest,
            "source_archive_path":source_path,
            "retrieved_at":observed_at,
            "settled_at":observed_at,
            "settlement_clock_semantics":
                "collector_first_verified_provider_final_no_whistle_claim",
            "official_game_id":str(game_id),
            "observed_workload_minutes":actual["observed_workload_minutes"],
            "position_after_game_research_only":actual.get("position"),
        })
    return output,unresolved
