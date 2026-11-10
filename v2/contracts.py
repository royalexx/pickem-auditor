"""V2.5 shadow-only immutable pregame, market and distribution contracts.

No implicit timestamps, prices, event identifiers or settlement assumptions.
These contracts supplement, rather than replace, Phase 0R certification.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Protocol
from urllib.parse import urlparse


class ContractError(ValueError):
    """Integrity fault; a snapshot must not be certified or scored."""


def utc(value: str, name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"missing_timestamp:{name}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"invalid_timestamp:{name}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractError(f"naive_timestamp:{name}")
    return parsed.astimezone(timezone.utc)


def require_id(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"missing_identity:{name}")


def require_sha(value: str, name: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ContractError(f"invalid_sha256:{name}")


def finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ContractError(f"invalid_number:{name}")
    return float(value)


def canonical_hash(record: dict) -> str:
    data = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class EventProbabilities:
    over: float
    under: float
    push: float

    def __post_init__(self) -> None:
        for name, val in (("over", self.over), ("under", self.under), ("push", self.push)):
            if not 0 <= finite(val, name) <= 1:
                raise ContractError(f"probability_range:{name}")
        if abs(math.fsum((self.over, self.under, self.push)) - 1.0) > 1e-10:
            raise ContractError("probability_complementarity")

    def conditional_over(self) -> float | None:
        nonpush = self.over + self.under
        return self.over / nonpush if nonpush > 0 else None


class PredictiveDistribution(Protocol):
    def probabilities(self, line: float) -> EventProbabilities: ...
    def to_record(self) -> dict: ...


@dataclass(frozen=True)
class DiscreteDistribution:
    """A finite, exact mass function; signed outcomes are permitted."""
    masses: tuple[tuple[float, float], ...]

    def __post_init__(self) -> None:
        if (not isinstance(self.masses, tuple) or not self.masses or
                any(not isinstance(item, tuple) or len(item) != 2 for item in self.masses)):
            raise ContractError("distribution_masses_must_be_immutable_pairs")
        values = []
        for x, p in self.masses:
            values.append(finite(x, "support"))
            if not 0 <= finite(p, "mass") <= 1:
                raise ContractError("negative_or_large_mass")
        if values != sorted(set(values)):
            raise ContractError("distribution_support_not_sorted_unique")
        if abs(math.fsum(p for _, p in self.masses) - 1.0) > 1e-10:
            raise ContractError("distribution_mass_not_one")

    def probabilities(self, line: float) -> EventProbabilities:
        line = finite(line, "line")
        under = math.fsum(p for x, p in self.masses if x < line)
        push = math.fsum(p for x, p in self.masses if x == line)
        over = math.fsum(p for x, p in self.masses if x > line)
        return EventProbabilities(over, under, push)

    def to_record(self) -> dict:
        return {"kind": "discrete", "masses": [list(x) for x in self.masses]}


@dataclass(frozen=True)
class FixedLineDistribution:
    """An ORIGINAL, immutable three-way forecast for exactly one offered line.

    This is not an inferred outcome distribution. It cannot be reused on a
    different line or sampled as if it were a predictive simulation. The
    archived Over and Under must have originated from one paired contract.
    """
    line: float
    over: float
    under: float
    push: float

    def __post_init__(self) -> None:
        finite(self.line, "original_line")
        EventProbabilities(self.over, self.under, self.push)

    def probabilities(self, line: float) -> EventProbabilities:
        if finite(line, "line") != self.line:
            raise ContractError("fixed_line_cannot_be_repriced")
        return EventProbabilities(self.over, self.under, self.push)

    def to_record(self) -> dict:
        return {"kind": "fixed_line", "line": self.line, "over": self.over,
                "under": self.under, "push": self.push}


@dataclass(frozen=True)
class PoissonDistribution:
    rate: float

    def __post_init__(self) -> None:
        if not 0 <= finite(self.rate, "rate") <= 300:
            raise ContractError("unsupported_poisson_rate")

    def _pmf(self, k: int) -> float:
        if k < 0:
            return 0.0
        if self.rate == 0:
            return 1.0 if k == 0 else 0.0
        return math.exp(-self.rate + k * math.log(self.rate) - math.lgamma(k + 1))

    def probabilities(self, line: float) -> EventProbabilities:
        line = finite(line, "line")
        lower = math.ceil(line) - 1  # count strictly less than L
        if lower < 0:
            under = 0.0
        elif lower >= 10000:
            under = 1.0
        else:
            under = min(1.0, math.fsum(self._pmf(k) for k in range(lower + 1)))
        push = self._pmf(int(line)) if line >= 0 and line.is_integer() else 0.0
        # Prevent floating-point cancellation from creating negative P(over).
        over = max(0.0, 1.0 - under - push)
        total = math.fsum((under, push, over))
        return EventProbabilities(over / total, under / total, push / total)

    def to_record(self) -> dict:
        return {"kind": "poisson", "rate": self.rate}


@dataclass(frozen=True)
class NormalDistribution:
    """Continuous signed-outcome diagnostic (not a claim of suitable yardage tails)."""
    mean: float
    sd: float

    def __post_init__(self) -> None:
        finite(self.mean, "mean")
        if finite(self.sd, "sd") <= 0:
            raise ContractError("nonpositive_sd")

    def probabilities(self, line: float) -> EventProbabilities:
        z = (finite(line, "line") - self.mean) / (self.sd * math.sqrt(2.0))
        under = 0.5 * math.erfc(-z)
        return EventProbabilities(1.0 - under, under, 0.0)

    def to_record(self) -> dict:
        return {"kind": "normal", "mean": self.mean, "sd": self.sd}


def parse_distribution(record: dict) -> PredictiveDistribution:
    if not isinstance(record, dict):
        raise ContractError("distribution_not_object")
    kind = record.get("kind")
    if kind == "discrete":
        masses = record.get("masses")
        if not isinstance(masses, list) or any(not isinstance(x, list) or len(x) != 2 for x in masses):
            raise ContractError("invalid_discrete_masses")
        return DiscreteDistribution(tuple((x[0], x[1]) for x in masses))
    if kind == "fixed_line":
        return FixedLineDistribution(record["line"], record["over"],
                                     record["under"], record["push"])
    if kind == "poisson":
        return PoissonDistribution(record["rate"])
    if kind == "normal":
        return NormalDistribution(record["mean"], record["sd"])
    raise ContractError("unsupported_distribution")


@dataclass(frozen=True)
class SourceReceipt:
    source_id: str
    first_available_at: str
    retrieved_at: str
    content_sha256: str
    source_uri: str | None
    archive_path: str
    source_kind: str = "provider_publication"  # or archive_possession

    def __post_init__(self) -> None:
        require_id(self.source_id, "source_id")
        require_sha(self.content_sha256, "source_content")
        require_id(self.archive_path, "archive_path")
        if (self.archive_path.startswith("/") or "\\" in self.archive_path
                or ".." in self.archive_path.split("/")
                or not all(self.archive_path.split("/"))):
            raise ContractError("invalid_archive_path")
        first = utc(self.first_available_at, "first_available_at")
        collected = utc(self.retrieved_at, "retrieved_at")
        if first > collected:
            raise ContractError("source_retrieved_before_available")
        if self.source_kind == "provider_publication":
            url = urlparse(self.source_uri or "")
            if url.scheme != "https" or not url.netloc:
                raise ContractError("invalid_source_uri")
        elif self.source_kind == "archive_possession":
            # An on-disk collector input does not have a trusted publication
            # timestamp. Its first-known time is archive possession ONLY.
            if self.source_uri is not None or first != collected:
                raise ContractError("archive_possession_provenance_not_exact")
        else:
            raise ContractError("invalid_source_kind")


@dataclass(frozen=True)
class MarketQuote:
    quote_id: str
    contract_id: str
    event_id: str
    event_start_at: str
    sport: str
    league: str
    season: int
    team_id: str
    opponent_id: str
    player_id: str
    stat_key: str
    period: str
    line: float
    book: str
    product_type: str
    quote_at: str
    quote_receipt_sha256: str
    settlement_policy: str
    quote_kind: str  # real | synthetic; synthetic never supports market-edge claims
    accepted: bool = True
    reject_reason: str | None = None
    over_decimal_odds: float | None = None
    under_decimal_odds: float | None = None
    quote_archive_path: str | None = None

    def __post_init__(self) -> None:
        for name in ("quote_id", "contract_id", "event_id", "sport", "league", "team_id", "opponent_id", "player_id", "stat_key", "period", "book", "product_type", "settlement_policy"):
            require_id(getattr(self, name), name)
        if isinstance(self.season, bool) or not isinstance(self.season, int) or self.season < 1900:
            raise ContractError("invalid_season")
        if self.settlement_policy != "strict_gt_lt_equal_push":
            raise ContractError("unsupported_settlement_policy")
        line=finite(self.line, "line")
        if self.accepted:
            from .stat_registry import canonical_stat
            stat=canonical_stat(self.sport,self.stat_key,self.period)
            if self.stat_key != stat.key:
                raise ContractError("noncanonical_stat_key")
            if stat.value_kind != "signed_count" and line < 0:
                raise ContractError("negative_line_on_nonnegative_stat")
            if self.team_id == self.opponent_id:
                raise ContractError("identical_team_and_opponent_identity")
        require_sha(self.quote_receipt_sha256, "quote_receipt")
        if self.quote_archive_path is not None:
            relative = self.quote_archive_path
            if (not isinstance(relative, str) or not relative.strip()
                    or relative.startswith("/") or "\\" in relative
                    or ".." in relative.split("/")):
                raise ContractError("invalid_quote_archive_path")
        if self.quote_kind not in ("real", "synthetic"):
            raise ContractError("invalid_quote_kind")
        if self.accepted and utc(self.quote_at, "quote_at") >= utc(self.event_start_at, "event_start_at"):
            raise ContractError("quote_not_pregame")
        if not self.accepted and not self.reject_reason:
            raise ContractError("rejection_reason_missing")
        if self.accepted and self.reject_reason:
            raise ContractError("accepted_quote_has_rejection_reason")
        for name in ("over_decimal_odds", "under_decimal_odds"):
            odds = getattr(self, name)
            if odds is not None and finite(odds, name) <= 1:
                raise ContractError("invalid_decimal_odds")

    def settlement_key(self) -> tuple[str, str, str, str]:
        return self.event_id, self.player_id, self.stat_key, self.period


def no_vig_over(quote: MarketQuote) -> float | None:
    if quote.quote_kind != "real" or not quote.accepted or quote.product_type != "sportsbook_two_sided":
        return None
    if quote.over_decimal_odds is None or quote.under_decimal_odds is None:
        return None
    a = 1.0 / quote.over_decimal_odds
    b = 1.0 / quote.under_decimal_odds
    return a / (a + b)


@dataclass(frozen=True)
class ForecastSnapshot:
    forecast_id: str
    run_id: str
    model_id: str
    model_version: str
    quote_id: str
    contract_id: str
    event_id: str
    sport: str
    league: str
    season: int
    team_id: str
    opponent_id: str
    player_id: str
    stat_key: str
    period: str
    line: float
    quote_receipt_sha256: str
    forecast_at: str
    input_freeze_at: str
    decision_cutoff_at: str
    model_training_cutoff_at: str
    model_artifact_sha256: str
    code_commit: str
    sources: tuple[SourceReceipt, ...]
    distribution: PredictiveDistribution
    schema_version: str = field(default="v25-shadow-1")

    def validate_against(self, quote: MarketQuote) -> None:
        for name in ("forecast_id", "run_id", "model_id", "model_version", "code_commit"):
            require_id(getattr(self, name), name)
        require_sha(self.model_artifact_sha256, "model_artifact")
        if self.schema_version != "v25-shadow-1":
            raise ContractError("unsupported_forecast_schema")
        if not isinstance(self.sources, tuple):
            raise ContractError("sources_must_be_immutable_tuple")
        if len(self.code_commit) != 40 or any(c not in "0123456789abcdef" for c in self.code_commit):
            raise ContractError("invalid_code_commit_sha")
        for name in ("quote_id", "contract_id", "event_id", "sport", "league", "season", "team_id", "opponent_id", "player_id", "stat_key", "period", "line", "quote_receipt_sha256"):
            if getattr(self, name) != getattr(quote, name):
                raise ContractError(f"forecast_quote_mismatch:{name}")
        start = utc(quote.event_start_at, "event_start_at")
        forecast = utc(self.forecast_at, "forecast_at")
        freeze = utc(self.input_freeze_at, "input_freeze_at")
        decision = utc(self.decision_cutoff_at, "decision_cutoff_at")
        trained = utc(self.model_training_cutoff_at, "model_training_cutoff_at")
        if not trained <= freeze <= decision <= forecast < start:
            raise ContractError("forecast_temporal_order_invalid")
        if utc(quote.quote_at, "quote_at") > freeze:
            raise ContractError("quote_after_input_freeze")
        if not self.sources:
            raise ContractError("source_receipts_missing")
        seen = set()
        for receipt in self.sources:
            if receipt.source_id in seen:
                raise ContractError("duplicate_source_receipt")
            seen.add(receipt.source_id)
            if utc(receipt.retrieved_at, "retrieved_at") > freeze:
                raise ContractError("future_source_retrieval")
        from .stat_registry import canonical_stat
        stat=canonical_stat(self.sport,self.stat_key,self.period)
        if stat.value_kind == "signed_count" and isinstance(self.distribution, PoissonDistribution):
            raise ContractError("poisson_cannot_model_signed_yardage")
        if stat.value_kind == "count" and isinstance(self.distribution, DiscreteDistribution):
            if any(x < 0 or not float(x).is_integer() for x,_p in self.distribution.masses):
                raise ContractError("negative_or_fractional_support_for_count")
        if stat.value_kind == "count" and isinstance(self.distribution, NormalDistribution):
            raise ContractError("continuous_normal_cannot_certify_integer_count_support")
        self.distribution.probabilities(self.line)

    def to_record(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "forecast_id": self.forecast_id, "run_id": self.run_id,
            "model_id": self.model_id, "model_version": self.model_version,
            "quote_id": self.quote_id, "contract_id": self.contract_id, "event_id": self.event_id,
            "sport": self.sport, "league": self.league, "season": self.season,
            "team_id": self.team_id, "opponent_id": self.opponent_id,
            "quote_receipt_sha256": self.quote_receipt_sha256,
            "player_id": self.player_id, "stat_key": self.stat_key,
            "period": self.period, "line": self.line,
            "forecast_at": self.forecast_at, "input_freeze_at": self.input_freeze_at,
            "decision_cutoff_at": self.decision_cutoff_at,
            "model_training_cutoff_at": self.model_training_cutoff_at,
            "model_artifact_sha256": self.model_artifact_sha256,
            "code_commit": self.code_commit,
            "sources": [vars(r) for r in self.sources],
            "distribution": self.distribution.to_record(),
        }

    @property
    def snapshot_sha256(self) -> str:
        return canonical_hash(self.to_record())


def parse_quote(row: dict) -> MarketQuote:
    return MarketQuote(**row)


def parse_snapshot(row: dict) -> ForecastSnapshot:
    copy = dict(row)
    copy["sources"] = tuple(SourceReceipt(**r) for r in copy["sources"])
    copy["distribution"] = parse_distribution(copy["distribution"])
    return ForecastSnapshot(**copy)
