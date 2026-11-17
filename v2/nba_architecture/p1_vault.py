"""P1 official NBA outcome vault -- isolated from the pregame feature builder.

Append-only content-addressed records. Official results and their corrections
MUST NOT be imported into p1_history or upstream S/O/J feature builders.
A provider HTTP capture is not automatically NBA-official adjudication:
the caller must identify its authorized source and preserve exact raw bytes.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import math
import os

from .v2_contracts import canonical, digest, seal, verify, instant
from .p1_history import _stats, _strict_json, HistoryIntegrityError, fail

VAULT_VERSION = "nba-p1-official-outcome-vault/1.1.0"
LEGACY_VAULT_VERSION = "nba-p1-official-outcome-vault/1.0.0"
STATES = frozenset({"PLAYED", "PLAYED_ZERO_MINUTES", "DNP",
                    "UNRESOLVED", "VOID"})


def _valid_event_id(value):
    if not isinstance(value, str) or ":" not in value or value.strip() != value:
        fail("VAULT_NONCANONICAL_ID")
    return value


def _validate(v, evidence=None):
    expected = {"schema", "kind", "content_hash", "game_id", "player_id",
                  "team_id", "state", "minutes", "stats", "source_id",
                  "source_raw_sha256", "observed_at", "official_status",
                  "revision", "supersedes_sha256"}
    if v.get("schema") == VAULT_VERSION:
        expected.add("accounting_evidence")
    if set(v) != expected:
        fail("VAULT_FIELDS")
    verify(v)
    if v["schema"] not in (VAULT_VERSION, LEGACY_VAULT_VERSION) or v["kind"] != "official_outcome":
        fail("VAULT_SCHEMA")
    for key in ("game_id", "player_id", "team_id", "source_id"):
        _valid_event_id(v[key])
    if v["state"] not in STATES:
        fail("VAULT_STATE")
    _stats(v["stats"])
    minutes = v["minutes"]
    if v["state"] in ("DNP", "UNRESOLVED", "VOID"):
        if minutes is not None or v["stats"]:
            fail("VAULT_NONPARTICIPATION_ZERO_FILL")
    elif v["state"] == "PLAYED_ZERO_MINUTES":
        if evidence is None and any(v["stats"].values()):
            fail("ZERO_MINUTE_CREDIT_UNRESOLVED")
        if minutes != 0 or type(minutes) is bool:
            fail("VAULT_PLAYED_ZERO")
    else:
        if type(minutes) not in (int, float) or not math.isfinite(minutes) or minutes <= 0:
            fail("VAULT_PLAYED_MINUTES")
        if evidence is None and minutes > 48:
            fail("VAULT_GAME_DURATION_EVIDENCE_REQUIRED")
    if evidence is not None:
        from .p1_evidence import duration, adjudicate_player
        d = duration(evidence, game_id=v["game_id"])
        g = _strict_json(evidence["raw"])["game"]
        teams = {'nba:team:' + str(g[k]['teamId']) for k in ('homeTeam', 'awayTeam')}
        if v["team_id"] not in teams:
            fail("OFFICIAL_TEAM_CONFLICT")
        adjudicate_player(dict(game_id=v["game_id"], player_id=v["player_id"],
            team_id=v["team_id"], opponent_id=next(iter(teams - {v["team_id"]})),
            game_date=d["game_date"], minutes=minutes, stats=v["stats"],
            participation='played' if v["state"] in ('PLAYED', 'PLAYED_ZERO_MINUTES') else
                          'dnp' if v["state"] == 'DNP' else 'unknown'), evidence)
        if instant(v["observed_at"]) < instant(evidence["capture"]["retrieved_at"]):
            fail("VAULT_OFFICIAL_EVIDENCE_OBSERVED_LATER")
        if v["source_raw_sha256"] != evidence["capture"]["raw_sha256"]:
            fail("VAULT_ACCOUNTING_SOURCE_CONFLICT")
    if not isinstance(v["official_status"], str) or not v["official_status"]:
        fail("VAULT_OFFICIAL_STATUS")
    instant(v["observed_at"])
    if type(v["revision"]) is not int or v["revision"] < 1:
        fail("VAULT_REVISION")
    if (not isinstance(v["source_raw_sha256"], str) or len(v["source_raw_sha256"]) != 64
            or any(c not in "0123456789abcdef" for c in v["source_raw_sha256"])):
        fail("VAULT_SOURCE_HASH")
    if v["revision"] == 1 and v["supersedes_sha256"] is not None:
        fail("VAULT_FIRST_REVISION")
    if v["revision"] > 1 and v["supersedes_sha256"] is None:
        fail("VAULT_CORRECTION_PARENT")
    return True


class OfficialOutcomeVault:
    """Isolated append-only vault. Each revision is a new SHA-addressed file."""

    def __init__(self, root):
        self.root = Path(root)

    def records(self):
        items = []
        for path in sorted(self.root.glob("*.json")):
            raw = path.read_bytes()
            try:
                v = _strict_json(raw)
            except (ValueError, UnicodeDecodeError) as exc:
                raise HistoryIntegrityError("VAULT_CORRUPTED_JSON") from exc
            evidence = self._load_evidence(v.get("accounting_evidence"))
            _validate(v, evidence)
            origin = self.root / "sources" / (v["source_raw_sha256"] + ".raw")
            if not origin.is_file() or hashlib.sha256(origin.read_bytes()).hexdigest() != v["source_raw_sha256"]:
                fail("VAULT_ORIGINAL_SOURCE_MISSING_OR_TAMPERED")
            if path.name != v["content_hash"] + ".json":
                fail("VAULT_FILENAME_SHA_MISMATCH")
            if raw != canonical(v) + b"\n":
                fail("VAULT_RAW_BYTES_MODIFIED")
            items.append(v)
        groups = {}
        for row in items:
            groups.setdefault((row["game_id"], row["player_id"]), []).append(row)
        for rows in groups.values():
            rows.sort(key=lambda x: x["revision"])
            for n, row in enumerate(rows, 1):
                if row["revision"] != n:
                    fail("VAULT_REVISION_GAP")
                if n > 1:
                    prior = rows[n-2]
                    if row["supersedes_sha256"] != prior["content_hash"]:
                        fail("VAULT_BROKEN_CHAIN")
                    if row["team_id"] != prior["team_id"] or instant(row["observed_at"]) <= instant(prior["observed_at"]):
                        fail("VAULT_REVISION_IDENTITY_OR_CLOCK")
        return items

    def _load_evidence(self, descriptor):
        if descriptor is None:
            return None
        def load(item):
            if set(item) != {"capture", "prior"}:
                fail("VAULT_EVIDENCE_FIELDS")
            sha = item["capture"]["raw_sha256"]
            if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
                fail("VAULT_SOURCE_HASH")
            raw = (self.root / "sources" / (sha + ".raw")).read_bytes()
            return dict(capture=item["capture"], raw=raw, prior=[load(x) for x in item["prior"]])
        return load(descriptor)

    def append(self, *, game_id, player_id, team_id, state, minutes, stats,
               source_id, source_bytes, observed_at, official_status,
               revision=1, supersedes_sha256=None, official_game_evidence=None):
        if not isinstance(source_bytes, bytes) or not source_bytes:
            fail("VAULT_ORIGINAL_SOURCE_BYTES_REQUIRED")
        if not isinstance(stats, dict):
            fail("VAULT_STATS_REQUIRED")
        def descriptor(item):
            if item is None:
                return None
            return dict(capture=item["capture"], prior=[descriptor(x) for x in item["prior"]])
        payload = seal(dict(
            schema=VAULT_VERSION, kind="official_outcome",
            game_id=game_id, player_id=player_id, team_id=team_id,
            state=state, minutes=minutes, stats=stats, source_id=source_id,
            source_raw_sha256=hashlib.sha256(source_bytes).hexdigest(),
            observed_at=observed_at, official_status=official_status,
            revision=revision, supersedes_sha256=supersedes_sha256,
            accounting_evidence=descriptor(official_game_evidence)))
        _validate(payload, official_game_evidence)
        matching = [x for x in self.records()
                    if x["game_id"] == game_id and x["player_id"] == player_id]
        if revision == 1:
            if matching:
                fail("VAULT_DUPLICATE_OR_CORRECTION_NOT_VERSIONED")
        else:
            if len(matching) != revision - 1:
                fail("VAULT_MISSING_CORRECTION_HISTORY")
            prior = max(matching, key=lambda x: x["revision"])
            if (prior["revision"] != revision - 1 or
                prior["content_hash"] != supersedes_sha256):
                fail("VAULT_CORRECTION_CHAIN_BROKEN")
            if instant(observed_at) <= instant(prior["observed_at"]):
                fail("VAULT_CORRECTION_BACKDATED")
            if prior["team_id"] != team_id:
                fail("VAULT_CORRECTION_TEAM_CONFLICT")
        self.root.mkdir(parents=True, exist_ok=True)
        originals = self.root / "sources"
        originals.mkdir(parents=True, exist_ok=True)
        # Preserve every official source revision before publishing the record.
        if official_game_evidence is not None:
            for item in official_game_evidence["prior"] + [official_game_evidence]:
                ep = originals / (item["capture"]["raw_sha256"] + ".raw")
                if ep.exists():
                    if ep.read_bytes() != item["raw"]:
                        fail("VAULT_SOURCE_BYTES_CONFLICT")
                else:
                    try:
                        with ep.open("xb") as stream:
                            stream.write(item["raw"])
                            stream.flush()
                            os.fsync(stream.fileno())
                    except FileExistsError:
                        if ep.read_bytes() != item["raw"]:
                            fail("VAULT_SOURCE_BYTES_CONFLICT")
        source_path = originals / (payload["source_raw_sha256"] + ".raw")
        if source_path.exists():
            if source_path.read_bytes() != source_bytes:
                fail("VAULT_SOURCE_BYTES_CONFLICT")
        else:
            try:
                raw_fd = os.open(source_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                if source_path.read_bytes() != source_bytes:
                    fail("VAULT_SOURCE_BYTES_CONFLICT")
            else:
                with os.fdopen(raw_fd, "wb") as original_stream:
                    original_stream.write(source_bytes)
                    original_stream.flush()
                    os.fsync(original_stream.fileno())
        path = self.root / (payload["content_hash"] + ".json")
        raw = canonical(payload) + b"\n"
        # Exclusive creation: never replace an existing outcome or correction.
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        return payload

    def latest(self, game_id, player_id):
        rows = [x for x in self.records()
                if x["game_id"] == game_id and x["player_id"] == player_id]
        if not rows:
            return None  # Missing official result is not a played-zero.
        rows.sort(key=lambda x: x["revision"])
        for n, row in enumerate(rows, 1):
            if row["revision"] != n:
                fail("VAULT_REVISION_GAP")
            if n > 1 and row["supersedes_sha256"] != rows[n-2]["content_hash"]:
                fail("VAULT_BROKEN_CHAIN")
        return rows[-1]

    def outcome_status(self, game_id, player_id):
        """Explicit missing-result handoff, never a zero-filled settlement."""
        row = self.latest(game_id, player_id)
        if row is None:
            return dict(schema=VAULT_VERSION, game_id=game_id, player_id=player_id,
                        state="UNRESOLVED", reason="MISSING_OFFICIAL_RESULT",
                        content_hash=None, minutes=None, stats={})
        return row
