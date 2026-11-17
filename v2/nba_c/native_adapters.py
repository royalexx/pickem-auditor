"""Versioned native owner transport for synthetic engineering verification.

The adapter invokes the real S producer and preserves its immutable fitted
artifact, source manifest, code bytes, uncertainty and G/O lineage. Outcome
transport has a separate root and API. No transport receipt authenticates a
source or permits historical fitting/evaluation; real admission stays closed.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
import math
import re
from pathlib import Path
from zoneinfo import ZoneInfo
import sys

from v2.nba_architecture.v2_contracts import canonical, verify, validate_pregame, digest, instant
from v2.nba_architecture.families_v2 import validate_forecast, validate_integration
from .physical_counts import partial_counts_feasible
from .warehouse import ForecastWarehouse, WarehouseError, _write_once, _read

VERSION = "nba-c-native-owner-handoff/1.0.0"
P1_VERSION = "nba-p1-native-handoff/1.0.0"


def _req(condition, reason):
    if not condition:
        raise WarehouseError(reason)


def _nullable_number(value):
    return value is None or type(value) in (int,float) and math.isfinite(value)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _strict_json(raw):
    def pairs(items):
        output={}
        for key,value in items:
            _req(key not in output,"NATIVE_DUPLICATE_JSON_KEY")
            output[key]=value
        return output
    def bad_constant(value):
        raise WarehouseError("NATIVE_NONFINITE_JSON")
    try:
        return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad_constant)
    except (ValueError,UnicodeDecodeError) as exc:
        raise WarehouseError("NATIVE_INVALID_SOURCE_JSON") from exc


def _mode(evidence_mode):
    _req(evidence_mode == "synthetic_engineering",
         "NATIVE_REAL_ADMISSION_REGISTRY_UNAVAILABLE")


def _raw(value, expected, reason):
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise WarehouseError(reason) from exc
    _req(_sha(raw) == expected, reason)
    return raw


def _packed_source(node):
    """Integrity only: exact source/ancestor bytes do not establish admission."""
    _req(isinstance(node, dict) and set(node)=={"capture","raw_base64","prior"} and
         isinstance(node.get("capture"), dict) and isinstance(node.get("prior"), list), "NATIVE_SOURCE_BUNDLE")
    previous = None
    for number, item in enumerate(node["prior"] + [node], 1):
        _req(isinstance(item, dict) and set(item)=={"capture","raw_base64","prior"} and
             isinstance(item.get("capture"), dict) and (item is node or item.get("prior") == []),
             "NATIVE_SOURCE_ANCESTRY")
        capture = item["capture"]
        _req(set(capture)=={"schema","url","raw_sha256","retrieved_at","revision","supersedes_receipt_sha256"}
             and capture["schema"]=="nba-p1-prior-game-evidence/1.0.0", "NATIVE_CAPTURE_SCHEMA")
        _raw(item.get("raw_base64"), capture.get("raw_sha256"),
             "NATIVE_SOURCE_BYTES_CHANGED")
        _req(type(capture.get("revision")) is int and capture["revision"] == number and
             capture.get("supersedes_receipt_sha256") ==
             (digest(previous) if previous is not None else None),
             "NATIVE_SOURCE_ANCESTRY")
        if previous is not None:
            _req(capture["url"] == previous["url"] and
                 instant(capture["retrieved_at"]) > instant(previous["retrieved_at"]),
                 "NATIVE_SOURCE_REVISION_CLOCK_OR_IDENTITY")
        previous = capture


def _minute_string(value):
    match=re.fullmatch(r"PT(\d+)M(\d+(?:\.\d+)?)S",value) if isinstance(value,str) else None
    _req(match is not None and Fraction(match[2])<60,"NATIVE_OFFICIAL_MINUTE_FORMAT")
    return Fraction(match[1])+Fraction(match[2])/60


def _box_stats(stats):
    allowed={"points","rebounds","assists","threes","steals","blocks","turnovers",
        "pra","pr","pa","ra","fgm","fga","fg3a","ftm","fta","oreb","dreb","personal_fouls"}
    _req(isinstance(stats,dict) and set(stats)<=allowed and
         all(type(value) is int and value>=0 for value in stats.values()),"NATIVE_BOX_STAT_SCHEMA")
    for made,attempted in (("fgm","fga"),("threes","fg3a"),("ftm","fta"),("fg3a","fga"),("threes","fgm")):
        if made in stats and attempted in stats:
            _req(stats[made]<=stats[attempted],"NATIVE_SHOOTING_ACCOUNTING")
    if "points" in stats:
        minimum=(2*stats["fgm"]+stats.get("threes",0) if "fgm" in stats else 3*stats.get("threes",0))+stats.get("ftm",0)
        _req(stats["points"]>=minimum,"NATIVE_POINT_ACCOUNTING")
    if all(k in stats for k in ("fgm","threes","ftm","points")):
        _req(stats["points"]==2*stats["fgm"]+stats["threes"]+stats["ftm"],"NATIVE_POINT_ACCOUNTING")
    if all(k in stats for k in ("oreb","dreb","rebounds")):
        _req(stats["oreb"]+stats["dreb"]==stats["rebounds"],"NATIVE_REBOUND_ACCOUNTING")
    for combo,parts in {"pr":("points","rebounds"),"pa":("points","assists"),
                       "ra":("rebounds","assists"),"pra":("points","rebounds","assists")}.items():
        if combo in stats and all(k in stats for k in parts):
            _req(stats[combo]==sum(stats[k] for k in parts),"NATIVE_COMBINATION_ACCOUNTING")
    _req(partial_counts_feasible(stats),"NATIVE_INTEGER_STAT_ACCOUNTING")


def _accounting(record,node):
    """Recompute transport summaries from retained bytes, never authenticate."""
    _packed_source(node)
    def descriptor(value):
        return {"capture":value["capture"],"prior":[descriptor(x) for x in value["prior"]]}
    _req(record["accounting_evidence"]==descriptor(node),"NATIVE_ACCOUNTING_DESCRIPTOR_JOIN")
    _req(record["source_raw_sha256"]==node["capture"]["raw_sha256"] and
         instant(record["observed_at"])>=instant(node["capture"]["retrieved_at"]),
         "NATIVE_ACCOUNTING_SOURCE_OR_CLOCK")
    games=[]
    for item in node["prior"]+[node]:
        raw=_raw(item["raw_base64"],item["capture"]["raw_sha256"],"NATIVE_SOURCE_BYTES_CHANGED")
        game=_strict_json(raw)["game"]
        _req(record["game_id"]=="nba:game:"+str(game["gameId"]) and
             item["capture"]["url"]=="https://cdn.nba.com/static/json/liveData/boxscore/boxscore_"+str(game["gameId"])+".json",
             "NATIVE_OFFICIAL_GAME_IDENTITY")
        _req(instant(item["capture"]["retrieved_at"])>instant(game["gameTimeUTC"]),
             "NATIVE_ACCOUNTING_CAPTURE_CLOCK")
        if games:
            _req(game["gameId"]==games[-1]["gameId"] and all(
                 game[k]["teamId"]==games[-1][k]["teamId"] for k in ("homeTeam","awayTeam")),
                 "NATIVE_OFFICIAL_ANCESTOR_IDENTITY")
        games.append(game)
    game=games[-1]
    _req(game["gameStatus"]==3 and type(game["period"]) is int and game["period"]>=4 and
         _minute_string(game["gameClock"])==0,"NATIVE_OFFICIAL_DURATION_REQUIRED")
    cap=48+5*(game["period"]-4)
    teams=[game[k]["teamId"] for k in ("homeTeam","awayTeam")]
    _req(all(type(team) is int and team>0 for team in teams) and teams[0]!=teams[1],
         "NATIVE_OFFICIAL_TEAM_IDENTITY")
    people=[("nba:team:"+str(game[k]["teamId"]),person) for k in ("homeTeam","awayTeam")
            for person in game[k].get("players",[]) if "nba:player:"+str(person.get("personId"))==record["player_id"]]
    _req(len(people)==1 and people[0][0]==record["team_id"],"NATIVE_OFFICIAL_PLAYER_TEAM")
    person=people[0][1]
    if record["state"] not in ("PLAYED","PLAYED_ZERO_MINUTES"):
        _req(record["minutes"] is None and record["stats"]=={},"NATIVE_NONPARTICIPATION_FILL")
        if record["state"]=="DNP":
            _req(person.get("played")=="0","NATIVE_OFFICIAL_DNP")
        else:
            _req(person.get("played") in (None,"unknown"),"NATIVE_OFFICIAL_UNKNOWN_PARTICIPATION")
        rawstats=person.get("statistics",{})
        _req(isinstance(rawstats,dict),"NATIVE_NONPARTICIPATION_RAW_STATS")
        count_keys={"points","reboundsTotal","assists","threePointersMade","fieldGoalsMade",
            "fieldGoalsAttempted","threePointersAttempted","freeThrowsMade","freeThrowsAttempted",
            "reboundsOffensive","reboundsDefensive","steals","blocks","turnovers","foulsPersonal"}
        supplied=[value for key,value in rawstats.items() if key in count_keys]
        _req(all(type(value) is int and value==0 for value in supplied),
             "NATIVE_NONPARTICIPATION_POSITIVE_CREDIT")
        if "minutes" in rawstats:
            _req(_minute_string(rawstats["minutes"])==0,"NATIVE_NONPARTICIPATION_POSITIVE_MINUTES")
        return game["gameTimeUTC"],None
    _req(person.get("played")=="1","NATIVE_OFFICIAL_PARTICIPATION")
    stats=person["statistics"];exact=_minute_string(stats["minutes"])
    displayed=record["minutes"]
    _req(type(displayed) in (int,float) and Fraction(str(displayed))<=cap and exact<=cap,
         "NATIVE_MINUTES_EXCEED_DURATION")
    names={'points':'points','rebounds':'reboundsTotal','assists':'assists','threes':'threePointersMade',
        'fgm':'fieldGoalsMade','fga':'fieldGoalsAttempted','fg3a':'threePointersAttempted',
        'ftm':'freeThrowsMade','fta':'freeThrowsAttempted','oreb':'reboundsOffensive',
        'dreb':'reboundsDefensive','steals':'steals','blocks':'blocks','turnovers':'turnovers',
        'personal_fouls':'foulsPersonal'}
    normalized={key:stats[value] for key,value in names.items() if value in stats}
    for key,parts in {'pr':('points','rebounds'),'pa':('points','assists'),
                      'ra':('rebounds','assists'),'pra':('points','rebounds','assists')}.items():
        if all(part in normalized for part in parts):
            normalized[key]=sum(normalized[part] for part in parts)
    _box_stats(normalized)
    _req(exact!=0 or not any(normalized.values()),"NATIVE_ZERO_MINUTE_CREDIT_UNRESOLVED")
    _box_stats(record["stats"])
    _req(all(type(value) is int and value>=0 and normalized.get(key)==value
             for key,value in record['stats'].items()),"NATIVE_OFFICIAL_STAT_JOIN")
    if displayed==0 and any(record['stats'].values()):
        _req(0<exact<Fraction(1,2),"NATIVE_ZERO_MINUTE_CREDIT_UNRESOLVED")
    else:
        _req(displayed>=0 and abs(Fraction(str(displayed))-exact)<=Fraction(1,2),
             "NATIVE_OFFICIAL_MINUTE_JOIN")
    _req((record["state"]=="PLAYED_ZERO_MINUTES" and displayed==0) or
         (record["state"]=="PLAYED" and displayed>0),"NATIVE_PARTICIPATION_MINUTE_JOIN")
    return game["gameTimeUTC"],float(exact)


def validate_p1_export(export, *, outcome=False):
    _req(isinstance(export, dict) and export.get("schema") == P1_VERSION,
         "NATIVE_P1_SCHEMA")
    _req(export.get("admission_status") == "BLOCKED", "NATIVE_P1_ADMISSION_NOT_ACCEPTED")
    if not outcome:
        _req(export.get("kind") in ("prior_game_export", "pregame_context_export"),
             "NATIVE_OUTCOME_IN_FORECAST_SOURCE")
        if export["kind"] == "prior_game_export":
            _packed_source(export["evidence_bundle"])
        else:
            for source in export["sources"]:
                _raw(source["raw_base64"], source["raw_sha256"], "NATIVE_SOURCE_BYTES_CHANGED")
        return
    _req(export.get("kind") == "outcome_export" and export.get("scoring_authorized") is False,
         "NATIVE_P1_OUTCOME_NOT_ADMITTED")
    _req(set(export)=={"schema","kind","game_id","player_id","team_id","source_profile",
        "admission_status","missing_requirements","status","participation","stats","official_count",
        "displayed_minutes","exact_minutes","event_start_at","event_end_at","outcome_released_at",
        "vault_schema","revisions","correction_version","scoring_authorized"},"NATIVE_OUTCOME_EXPORT_FIELDS")
    _req(isinstance(export["revisions"],list) and all(isinstance(export[k],str) and
         ":" in export[k] and export[k].strip()==export[k] for k in ("game_id","player_id")),
         "NATIVE_OUTCOME_EXPORT_IDENTITY")
    _req(_nullable_number(export.get("displayed_minutes")) and
         _nullable_number(export.get("exact_minutes")) and
         (export.get("correction_version") is None or type(export["correction_version"]) is int),
         "NATIVE_OUTCOME_SUMMARY_SCALAR_TYPE")
    _req(export.get("source_profile")=="unadmitted_isolated_outcome_vault" and
         export.get("event_end_at") is None and export.get("outcome_released_at") is None and
         export.get("official_count") is None,"NATIVE_UNSUPPORTED_OUTCOME_CLAIM")
    required=["INDEPENDENT_SOURCE_ADMISSION","SOURCE_BOUND_EVENT_END",
              "SOURCE_BOUND_OUTCOME_RELEASE_CLOCK"]+([] if export["revisions"] else ["OFFICIAL_OUTCOME_MISSING"])
    _req(export.get("missing_requirements")==required and
         export.get("status")==("UNADMITTED" if export["revisions"] else "UNRESOLVED"),
         "NATIVE_OUTCOME_ADMISSION_SUMMARY")
    previous = None
    previous_record=None
    event_start=None
    latest_exact=None
    for number, revision in enumerate(export["revisions"], 1):
        raw = _raw(revision["record_raw_base64"], revision["record_raw_sha256"],
                   "NATIVE_VAULT_RECORD_BYTES_CHANGED")
        record = revision["record"]
        _req(raw == canonical(record) + b"\n", "NATIVE_VAULT_RECORD_MISMATCH")
        fields={"schema","kind","content_hash","game_id","player_id","team_id","state",
            "minutes","stats","source_id","source_raw_sha256","observed_at","official_status",
            "revision","supersedes_sha256"}
        if record["schema"]=="nba-p1-official-outcome-vault/1.1.0":fields.add("accounting_evidence")
        _req(set(record)==fields and record["schema"] in ("nba-p1-official-outcome-vault/1.0.0",
             "nba-p1-official-outcome-vault/1.1.0") and record["kind"]=="official_outcome",
             "NATIVE_VAULT_RECORD_SCHEMA")
        _req(type(record["revision"]) is int and record["state"] in
             ("PLAYED","PLAYED_ZERO_MINUTES","DNP","UNRESOLVED","VOID") and
             isinstance(record["stats"],dict) and all(type(x) is int and x>=0 for x in record["stats"].values()),
             "NATIVE_VAULT_RECORD_STATE")
        _box_stats(record["stats"])
        _req(all(isinstance(record[key],str) and ":" in record[key] and record[key].strip()==record[key]
                 for key in ("game_id","player_id","team_id","source_id")) and
             isinstance(record["official_status"],str) and bool(record["official_status"]),
             "NATIVE_VAULT_RECORD_IDENTITY_OR_STATUS")
        instant(record["observed_at"])
        if revision["accounting_evidence"] is None:
            if record["state"] in ("DNP","UNRESOLVED","VOID"):
                _req(record["minutes"] is None and record["stats"]=={},"NATIVE_NONPARTICIPATION_FILL")
            elif record["state"]=="PLAYED_ZERO_MINUTES":
                _req(type(record["minutes"]) in (int,float) and record["minutes"]==0 and
                     not any(record["stats"].values()),"NATIVE_ZERO_MINUTE_CREDIT_UNRESOLVED")
            else:
                _req(type(record["minutes"]) in (int,float) and 0<record["minutes"]<=48,
                     "NATIVE_OFFICIAL_DURATION_REQUIRED")
        verify(record)
        source = _raw(revision["source_raw_base64"], revision["source_raw_sha256"],
                      "NATIVE_VAULT_SOURCE_BYTES_CHANGED")
        _req(_sha(source) == record["source_raw_sha256"], "NATIVE_VAULT_SOURCE_JOIN")
        _req(record["game_id"] == export["game_id"] and
             record["player_id"] == export["player_id"], "NATIVE_VAULT_IDENTITY")
        _req(record["revision"] == number and record["supersedes_sha256"] == previous,
             "NATIVE_VAULT_CORRECTION_CHAIN")
        if previous_record is not None:
            _req(record["team_id"]==previous_record["team_id"] and
                 instant(record["observed_at"])>instant(previous_record["observed_at"]),
                 "NATIVE_CORRECTION_IDENTITY_OR_CLOCK")
        previous_record=record
        previous = record["content_hash"]
        latest_exact=None
        if revision["accounting_evidence"] is not None:
            start,latest_exact=_accounting(record,revision["accounting_evidence"])
            _req(event_start is None or instant(start)==instant(event_start),
                 "NATIVE_OUTCOME_EVENT_START_CONFLICT")
            event_start=start
        else:
            _req(record.get("accounting_evidence") is None,"NATIVE_ACCOUNTING_DESCRIPTOR_JOIN")
    _req(export["correction_version"] == (len(export["revisions"]) or None),
         "NATIVE_VAULT_CORRECTION_VERSION")
    _req(export.get("event_start_at")==event_start and export.get("exact_minutes")==latest_exact,
         "NATIVE_OUTCOME_SOURCE_DERIVED_CLOCK_OR_MINUTES")
    latest = export["revisions"][-1]["record"] if export["revisions"] else None
    if latest is not None:
        _req(export["participation"] == latest["state"] and
             export["stats"] == latest["stats"] and
             export["displayed_minutes"] == latest["minutes"] and
             export["team_id"] == latest["team_id"] and
             export["vault_schema"] == latest["schema"], "NATIVE_VAULT_SUMMARY_JOIN")
    else:
        _req(export["participation"] == "UNRESOLVED" and export["stats"] == {} and
             export["team_id"] is None and export["official_count"] is None and
             export["displayed_minutes"] is None and export["vault_schema"] is None,
             "NATIVE_VAULT_UNRESOLVED_SUMMARY")


class NativeForecastArchive:
    """Forecast-only native transport; accepts no vault or outcome argument."""
    def __init__(self, root):
        self.root = Path(root) / "native_forecast_only"
        self.forecasts = ForecastWarehouse(root)

    def _store(self, kind, value):
        raw = canonical(value) + b"\n"
        sha = _sha(raw)
        _write_once(self.root / kind / (sha + ".json"), raw)
        return sha

    def _get(self, kind, sha):
        _req(isinstance(sha,str) and len(sha)==64 and
             all(c in "0123456789abcdef" for c in sha), "NATIVE_FORECAST_SHA")
        obj=_read(self.root/kind/(sha+".json"))
        _req(_sha(canonical(obj)+b"\n")==sha, "NATIVE_FORECAST_BYTES_CHANGED")
        return obj

    def get_s(self, sha):
        receipt=self._get("intake_receipts",sha)
        _req(receipt["schema"]==VERSION and receipt["kind"]=="P2_prediction_intake",
             "NATIVE_S_RECEIPT_SCHEMA")
        refs=receipt["refs"]
        objects={name:self._get(name,refs[name]) for name in
            ("pregame","source_manifest","p1_source_exports","producer_code","native_prediction")}
        for name in ("game_state","opportunity"):
            if name in refs:
                objects[name]=self._get(name,refs[name]);verify(objects[name])
        artifact=refs["fitted_artifact_raw_sha256"]
        raw=(self.root/"fitted_artifacts"/(artifact+".raw")).read_bytes()
        _req(_sha(raw)==artifact,"NATIVE_S_ARTIFACT_BYTES_CHANGED")
        objects["fitted_artifact_bytes"]=raw
        data=json.loads(raw)
        used={key:objects["source_manifest"][key] for key in data["source_receipts"]
              if key in objects["source_manifest"]}
        _req(set(used)==set(data["source_receipts"]) and
             _sha(canonical(used))==data["source_manifest_sha256"],
             "NATIVE_S_SOURCE_MANIFEST_JOIN")
        for export in objects["p1_source_exports"]:
            self._source_attachment(export,objects["pregame"],data)
        codes={}
        for item in objects["producer_code"]:
            code_sha=item["raw_sha256"]
            code=(self.root/"code_bytes"/(code_sha+".raw")).read_bytes()
            _req(_sha(code)==code_sha,"NATIVE_S_CODE_BYTES_CHANGED")
            codes[item["relative_path"]]=code_sha
        _req(codes.get("model.py")==data["code_sha256"],"NATIVE_S_CODE_ARTIFACT_JOIN")
        prediction=objects["native_prediction"]
        if receipt["forecast_manifest_sha256"] is not None:
            _,stored=self.forecasts.get(receipt["forecast_manifest_sha256"])
            _req(stored["pregame"]==objects["pregame"] and
                 stored["distribution"]==prediction["distribution"],
                 "NATIVE_S_STORED_FORECAST_JOIN")
            validate_forecast(prediction["distribution"],objects["pregame"],
                g=objects.get("game_state"),o=objects.get("opportunity"))
        else:
            _req(prediction["distribution"] is None and prediction["abstain_reason"] is not None,
                 "NATIVE_S_ABSTENTION_JOIN")
        return receipt,objects

    def _source_attachment(self,export,pregame,artifact):
        validate_p1_export(export)
        cutoff=min(instant(pregame["training_cutoff_at"]),instant(artifact["training_cutoff_at"]))
        if export["kind"]=="prior_game_export":
            node=export["evidence_bundle"]
            raw=_raw(node["raw_base64"],node["capture"]["raw_sha256"],"NATIVE_SOURCE_BYTES_CHANGED")
            game=_strict_json(raw)["game"]
            game_id="nba:game:"+str(game["gameId"])
            _req(export["exposure"]["game_id"]==game_id and
                 export["game_start_at"]==game["gameTimeUTC"],"NATIVE_PRIOR_SOURCE_IDENTITY")
            _req(export["profile"]==export["source_profile"] and export["profile"] in
                 ("synthetic_engineering","unadmitted_source_reconstruction") and
                 export["role"] is None and export["role_evidence"] is None,
                 "NATIVE_PRIOR_UNSUPPORTED_ADMISSION_OR_ROLE")
            _req(all(export["clocks"][key] is None for key in ("provider_published_at",
                 "first_defensible_available_at","collector_observed_at","outcome_available_at")),
                 "NATIVE_PRIOR_UNSUPPORTED_AVAILABILITY")
            _req(export["clocks"]["retrieved_at"]==node["capture"]["retrieved_at"] and
                 instant(export["clocks"]["ingested_at"])>=instant(node["capture"]["retrieved_at"]),
                 "NATIVE_PRIOR_RETRIEVAL_CLOCK")
            exposure=export["exposure"]
            _req(_nullable_number(exposure["exact_minutes"]) and
                 type(exposure["overtime_periods"]) is int and
                 type(exposure["duration_minutes"]) in (int,float) and
                 exposure["overtime_periods"]==game["period"]-4 and
                 exposure["duration_minutes"]==48+5*(game["period"]-4) and
                 exposure["game_date"]==instant(game["gameTimeUTC"]).astimezone(ZoneInfo("America/Toronto")).date().isoformat() and
                 exposure["raw_sha256"]==node["capture"]["raw_sha256"] and
                 exposure["receipt_sha256"]==digest(node["capture"]) and
                 exposure["retrieved_at"]==node["capture"]["retrieved_at"] and
                 exposure["original_pregame_available_at"] is None and
                 exposure["certification"]=="HISTORICAL_RECONSTRUCTION_UNCERTIFIED" and
                 exposure["source_status"]=="OFFICIAL_BYTES_CONSISTENT_AUTHENTICITY_REVIEW_REQUIRED",
                 "NATIVE_PRIOR_EXPOSURE_SUMMARY_JOIN")
            denominator=export["candidate_denominator"]
            _req(set(denominator)=={"attempted","admitted","quarantined"} and
                 all(type(x) is int for x in denominator.values()) and
                 denominator=={"attempted":1,"admitted":0,"quarantined":1},
                 "NATIVE_PRIOR_DENOMINATOR")
            def descriptor(item):
                return {"capture":item["capture"],"prior":[descriptor(x) for x in item["prior"]]}
            state=("PLAYED_ZERO_MINUTES" if exposure["displayed_minutes"]==0 else "PLAYED") if exposure["participation"]=="played" else "DNP" if exposure["participation"]=="dnp" else "UNRESOLVED"
            _,exact=_accounting({"accounting_evidence":descriptor(node),
                "source_raw_sha256":node["capture"]["raw_sha256"],
                "observed_at":export["clocks"]["ingested_at"],"game_id":game_id,
                "player_id":exposure["player_id"],"team_id":exposure["team_id"],
                "state":state,"minutes":exposure["displayed_minutes"],"stats":exposure["stats"]},node)
            _req(exposure["exact_minutes"]==exact,"NATIVE_PRIOR_EXACT_MINUTE_JOIN")
            _req(game_id!=pregame["game_id"] and
                 instant(game["gameTimeUTC"])<cutoff,"NATIVE_TARGET_OR_POST_CUTOFF_SOURCE")
            for name in ("provider_published_at","first_defensible_available_at","outcome_available_at"):
                value=export["clocks"][name]
                _req(value is None or instant(value)<=cutoff,"NATIVE_POST_CUTOFF_SOURCE_CLOCK")
            # Modern retrieval and missing original availability are retained,
            # never converted to a source-admitted pregame feature.
        else:
            _req(export["game_id"]==pregame["game_id"] and
                 export["input_freeze_at"]==pregame["input_freeze_at"] and
                 export["event_start_at"]==pregame["event_start_at"],"NATIVE_P1_CONTEXT_IDENTITY")
            _req(export["source_profile"]=="unadmitted_adapter_export" and
                 export["home_team_id"] is None and export["home_identity_evidence"] is None and
                 export["roster_completeness"]=={"status":"UNPROVEN","proof_references":[]},
                 "NATIVE_P1_CONTEXT_UNSUPPORTED_CERTIFICATION")
            denominator=export["candidate_denominator"]
            _req(set(denominator)=={"observed_candidates","complete_population","admitted"} and
                 type(denominator["observed_candidates"]) is int and
                 denominator["observed_candidates"]==len(export["players"]) and
                 denominator["complete_population"] is None and type(denominator["admitted"]) is int and
                 denominator["admitted"]==0,"NATIVE_CONTEXT_DENOMINATOR")
            for person in export["players"]:
                _req(all(person[k] is None for k in ("membership","role","role_evidence",
                     "participation_probability","participation_authentication")) and
                     person["role_uncertainty"]=="UNKNOWN","NATIVE_P1_CONTEXT_FALSE_FIT")
            for source in export["sources"]:
                _req(source["admission_basis"] is None and source["admission_status"]=="REVIEW_REQUIRED",
                     "NATIVE_P1_CONTEXT_FALSE_SOURCE_ADMISSION")
                for name,value in source["clocks"].items():
                    _req(value is None or instant(value)<=instant(pregame["input_freeze_at"]),
                         "NATIVE_POST_FREEZE_CONTEXT_SOURCE")

    def put_s(self, producer, fitted, *, frozen_pregame, target_player_id,
              role, source_manifest, source_exports=(), opportunity=None,
              game_state=None, conditioning="unconditional", seed=0,
              evidence_mode=""):
        """Invoke the loaded P2 package; no substitute forecast is constructed."""
        _mode(evidence_mode)
        validate_pregame(frozen_pregame)
        _req(type(fitted.payload) is bytes, "NATIVE_FITTED_BYTES_REQUIRED")
        module = sys.modules.get(producer.predict.__module__)
        _req(module is not None and getattr(module, "predict", None) is producer.predict,
             "NATIVE_S_PRODUCER_REQUIRED")
        model_path = Path(module.__file__).resolve()
        _req(model_path.name == "model.py", "NATIVE_S_PRODUCER_PATH")
        data = fitted.data
        _req(data["code_sha256"] == _sha(model_path.read_bytes()), "NATIVE_S_CODE_ARTIFACT_JOIN")
        _req(fitted.artifact_sha256 == _sha(fitted.payload), "NATIVE_S_ARTIFACT_BYTES")
        used = {k: source_manifest[k] for k in data["source_receipts"] if k in source_manifest}
        _req(set(used) == set(data["source_receipts"]) and
             _sha(canonical(used)) == data["source_manifest_sha256"], "NATIVE_S_SOURCE_MANIFEST_JOIN")
        exports = deepcopy(list(source_exports))
        for export in exports:
            self._source_attachment(export,frozen_pregame,data)
        prediction = producer.predict(fitted, frozen_pregame=frozen_pregame,
            target_player_id=target_player_id, role=role, opportunity=opportunity,
            game_state=game_state, conditioning=conditioning, seed=seed)
        refs = {"pregame": self._store("pregame", frozen_pregame),
                "source_manifest": self._store("source_manifest", source_manifest),
                "p1_source_exports": self._store("p1_source_exports", exports)}
        artifact_sha = _sha(fitted.payload)
        _write_once(self.root / "fitted_artifacts" / (artifact_sha + ".raw"), fitted.payload)
        refs["fitted_artifact_raw_sha256"] = artifact_sha
        code = []
        for path in sorted(model_path.parent.glob("*.py")):
            raw = path.read_bytes(); sha = _sha(raw)
            _write_once(self.root / "code_bytes" / (sha + ".raw"), raw)
            code.append({"relative_path": path.name, "raw_sha256": sha})
        refs["producer_code"] = self._store("producer_code", code)
        for name, obj in (("game_state", game_state), ("opportunity", opportunity)):
            if obj is not None:
                verify(obj); refs[name] = self._store(name, obj)
        forecast_key = None
        if prediction.distribution is not None:
            distribution = prediction.distribution
            validate_forecast(distribution, frozen_pregame, g=game_state, o=opportunity)
            _req(distribution["lineage"]["S"]["artifact_sha256"] == artifact_sha and
                 distribution["player_id"] == target_player_id,
                 "NATIVE_S_DISTRIBUTION_ARTIFACT_JOIN")
            forecast_key = self.forecasts.put(frozen_pregame, distribution)
        response = {"distribution": prediction.distribution,
                    "abstain_reason": prediction.abstain_reason,
                    "parameters": prediction.parameters, "uncertainty": prediction.uncertainty}
        refs["native_prediction"] = self._store("native_prediction", response)
        receipt = {"schema": VERSION, "kind": "P2_prediction_intake",
            "evidence_mode": evidence_mode, "source_admission": "BLOCKED",
            "independent_acceptance": "PENDING", "not_predictive_evaluation": True,
            "attempted": 1, "produced": int(prediction.distribution is not None),
            "abstained": int(prediction.distribution is None), "refs": refs,
            "forecast_manifest_sha256": forecast_key,
            "missing_prerequisites": ["INDEPENDENT_SOURCE_ADMISSION",
                "INDEPENDENT_LATEST_OWNER_HANDOFF_ACCEPTANCE"]}
        return self._store("intake_receipts", receipt), receipt

    def _check_j(self,result,inputs,manifest_raw,code,artifact_hashes):
        p,g,o,side,source_manifest,roles=inputs
        bundle=result["bundle"]
        validate_integration(bundle,p,g,o)
        manifest=result["integration_manifest"]
        _req(isinstance(manifest,dict) and manifest.get("version")=="NBA-P2-P3-to-J/2.0.0" and
             manifest.get("law_contract")=="NBA-J-CONSTRAINED-LATENT-RATE/0.1.0-PROPOSAL" and
             manifest.get("independent_acceptance")=="PENDING" and
             manifest.get("real_integration")=="BLOCKED" and
             manifest.get("evidence_mode")=="latest_synthetic_engineering" and
             result.get("status")=="SYNTHETIC_PROPOSED_CONSTRAINED_LAW_PENDING_INDEPENDENT_ACCEPTANCE_REAL_BLOCKED",
             "NATIVE_J_UNSUPPORTED_ACCEPTANCE_OR_VERSION")
        _req(manifest["owner_registry"]==json.loads(manifest_raw) and
             manifest["owner_registry_raw_sha256"]==_sha(manifest_raw) and
             manifest["consumer_code_files"]==code and manifest["artifacts"]==artifact_hashes and
             manifest["source_manifest_sha256"]==digest(source_manifest) and
             manifest["roles_sha256"]==digest(roles) and manifest["sidecar_sha256"]==side["content_hash"],
             "NATIVE_J_CODE_ARTIFACT_SOURCE_JOIN")
        expected={"pregame":p["content_hash"],"G":g["content_hash"],"O":o["content_hash"],
                  "S":digest(manifest),"O_sidecar":side["content_hash"]}
        _req(result["input_shas"]==expected,"NATIVE_J_INPUT_JOIN")
        _req(bundle["lineage"]["S"]["artifact_sha256"]==digest(manifest) and
             bundle["lineage"]["S"]["version"]==manifest["version"] and
             bundle["lineage"]["S"]["code_sha256"]==code["v2/nba_joint/integration_v2.py"] and
             bundle["lineage"]["J"]["code_sha256"]==code["v2/nba_joint/p4.py"],
             "NATIVE_J_MANIFEST_LINEAGE_JOIN")
        _req(result["scenario_hashes"]=={x["scenario_id"]:digest(x) for x in bundle["scenarios"]},
             "NATIVE_J_SCENARIO_HASH_JOIN")
        _req(len(result["audit_rows"])==len(bundle["scenarios"]),"NATIVE_J_AUDIT_POPULATION")
        for scenario,audit in zip(bundle["scenarios"],result["audit_rows"]):
            _req(audit["scenario_id"]==scenario["scenario_id"] and
                 audit["scenario_sha256"]==digest(scenario) and
                 audit["event_ledger_sha256"]==digest(audit["event_ledger"]),
                 "NATIVE_J_AUDIT_SCENARIO_JOIN")

    def put_j(self, producer, *, pregame, game_state, opportunity, sidecar,
              artifacts, source_manifest, roles, upstream_root, event_parameters,
              distributions_builder, seed=42, evidence_mode=""):
        """Invoke actual P4 consumer and PMF producer; no caller result accepted."""
        _mode(evidence_mode)
        _req(producer.simulate_latest.__module__==producer.__name__ and
             Path(producer.__file__).name=="integration_v2.py", "NATIVE_J_PRODUCER_REQUIRED")
        result=producer.simulate_latest(pregame,game_state,opportunity,sidecar,artifacts,
            source_manifest,roles,upstream_root=upstream_root,
            evidence_mode="latest_synthetic_engineering",event_parameters=event_parameters,seed=seed)
        root=Path(producer.__file__).resolve().parents[2]
        manifest=result["integration_manifest"]
        registry_raw=Path(producer.REGISTRY).read_bytes()
        code={path:_sha((root/path).read_bytes()) for path in manifest["consumer_code_files"]}
        ah={name:_sha(artifact.payload) for name,artifact in artifacts.items()}
        inputs=(pregame,game_state,opportunity,sidecar,source_manifest,roles)
        self._check_j(result,inputs,registry_raw,code,ah)
        # Actual P4 PMF derivation from these same draws, never new sampling.
        _req(distributions_builder.__module__.endswith("nba_joint.p4"),"NATIVE_J_PMF_PRODUCER_REQUIRED")
        pmfs=distributions_builder(result,pregame,frozen_at=pregame["forecast_at"],seed=seed)
        distributions=[distribution for values in pmfs.values() for distribution in values.values()]
        stored=[]
        for distribution in distributions:
            validate_forecast(distribution,pregame,g=game_state,o=opportunity,scenarios=result["bundle"])
            _req(distribution["pipeline_mode"]=="S_O_J","NATIVE_J_COMPLETE_PIPELINE")
            stored.append(self.forecasts.put(pregame,distribution,scenarios=result["bundle"],
                game_state=game_state,opportunity=opportunity))
        _req(bool(stored),"NATIVE_J_DISTRIBUTIONS_REQUIRED")
        refs={name:self._store(name,value) for name,value in zip(
            ("pregame","game_state","opportunity","sidecar","source_manifest","roles"),inputs)}
        refs["native_j_results"]=self._store("native_j_results",result)
        refs["code_inventory"]=self._store("code_inventory",code)
        registry_sha=_sha(registry_raw)
        _write_once(self.root/"raw_registry"/(registry_sha+".raw"),registry_raw)
        refs["registry_raw_sha256"]=registry_sha
        for path,sha in code.items():
            _write_once(self.root/"code_bytes"/(sha+".raw"),(root/path).read_bytes())
        for name,artifact in artifacts.items():
            _write_once(self.root/"fitted_artifacts"/(ah[name]+".raw"),artifact.payload)
        # Preserve every actual pinned upstream code byte and original synthetic
        # raw/context source. These are engineering bytes, never authentication.
        native_files={}
        for owner,pin in manifest["owner_registry"]["owners"].items():
            for path,expected in pin["files"].items():
                raw=(Path(upstream_root)/owner/path).read_bytes()
                _req(_sha(raw)==expected,"NATIVE_J_UPSTREAM_CODE_BYTES")
                _write_once(self.root/"code_bytes"/(expected+".raw"),raw)
                native_files[owner+"/"+path]=expected
        for path in sorted(Path(producer.FIXTURES).iterdir()):
            if path.is_file():
                raw=path.read_bytes();sha=_sha(raw)
                _write_once(self.root/"native_source_bytes"/(sha+".raw"),raw)
                native_files[path.name]=sha
        refs["native_source_inventory"]=self._store("native_source_inventory",native_files)
        receipt={"schema":VERSION,"kind":"P4_joint_intake","evidence_mode":evidence_mode,
            "source_admission":"BLOCKED","independent_acceptance":"PENDING",
            "upstream_integration_manifest":deepcopy(manifest),"refs":refs,
            "fitted_artifact_raw_sha256":ah,"forecast_manifest_sha256":stored,
            "outcome_accessed":False,"native_result_status":result["status"]}
        return self._store("intake_receipts",receipt),receipt

    def get_j(self,sha):
        receipt=self._get("intake_receipts",sha)
        _req(receipt["schema"]==VERSION and receipt["kind"]=="P4_joint_intake", "NATIVE_J_RECEIPT_SCHEMA")
        refs=receipt["refs"]
        objects={name:self._get(name,refs[name]) for name in
            ("pregame","game_state","opportunity","sidecar","source_manifest","roles",
             "native_j_results","code_inventory","native_source_inventory")}
        registry_sha=refs["registry_raw_sha256"]
        registry_raw=(self.root/"raw_registry"/(registry_sha+".raw")).read_bytes()
        _req(_sha(registry_raw)==registry_sha,"NATIVE_J_REGISTRY_BYTES_CHANGED")
        for path,code_sha in objects["code_inventory"].items():
            _req(_sha((self.root/"code_bytes"/(code_sha+".raw")).read_bytes())==code_sha,
                 "NATIVE_J_CODE_BYTES_CHANGED")
        for name,sha in receipt["fitted_artifact_raw_sha256"].items():
            _req(_sha((self.root/"fitted_artifacts"/(sha+".raw")).read_bytes())==sha,
                 "NATIVE_J_FITTED_BYTES_CHANGED")
        for name,sha in objects["native_source_inventory"].items():
            kind="code_bytes" if name.startswith(("P2/","P3/")) else "native_source_bytes"
            _req(_sha((self.root/kind/(sha+".raw")).read_bytes())==sha,"NATIVE_J_SOURCE_BYTES_CHANGED")
        inputs=tuple(objects[name] for name in
            ("pregame","game_state","opportunity","sidecar","source_manifest","roles"))
        self._check_j(objects["native_j_results"],inputs,registry_raw,
            objects["code_inventory"],receipt["fitted_artifact_raw_sha256"])
        _req(receipt["upstream_integration_manifest"]==objects["native_j_results"]["integration_manifest"],
             "NATIVE_J_RECEIPT_MANIFEST_JOIN")
        for key in receipt["forecast_manifest_sha256"]:
            _,forecast=self.forecasts.get(key)
            _req(forecast["pregame"]==objects["pregame"] and
                 forecast["scenarios"]==objects["native_j_results"]["bundle"],
                 "NATIVE_J_STORED_FORECAST_JOIN")
        return receipt,objects


class NativeOutcomeArchive:
    """P1 native outcome/correction transport; never imports a forecast producer."""
    def __init__(self, root):
        self.root = Path(root) / "native_outcome_only"

    def put_p1(self, export, *, evidence_mode=""):
        _mode(evidence_mode)
        validate_p1_export(export, outcome=True)
        raw = canonical(export) + b"\n"; sha = _sha(raw)
        _write_once(self.root / (sha + ".json"), raw)
        return sha

    def get(self, sha):
        _req(isinstance(sha, str) and len(sha) == 64 and
             all(c in "0123456789abcdef" for c in sha), "NATIVE_OUTCOME_SHA")
        export = _read(self.root / (sha + ".json"))
        _req(_sha(canonical(export) + b"\n") == sha, "NATIVE_OUTCOME_BYTES_CHANGED")
        validate_p1_export(export, outcome=True)
        return export

    def scoring_disposition(self, sha):
        export = self.get(sha)
        return {"status": "BLOCKED", "scored": False,
            "participation": export["participation"], "source_profile": export["source_profile"],
            "correction_version": export["correction_version"],
            "missing_prerequisites": list(export["missing_requirements"]),
            "reason": "P1_NATIVE_OUTCOME_NOT_INDEPENDENTLY_ADMITTED"}
