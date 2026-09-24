"""
Deterministic, scored name matching for lookup tables.

Free-text names coming out of a building model (``"Aluminum-Clad Timber
Window"``, ``"Concrete - Cast-in-Place 30 MPa"``) rarely equal the keys of
a factor, cost, or classification table. This module maps such names onto
table keys in a way that is:

* **Deterministic** -- the result never depends on dict insertion order.
* **Tiered** -- an exact match beats a whole-token match, which beats a
  raw substring match.
* **Explainable** -- every result records *how* it matched, a heuristic
  confidence, and any competing keys that would have produced a
  different answer.

Tiers
-----
``EXACT``
    The normalized query equals the normalized key (confidence 1.0).
``TOKEN``
    The key's tokens occur contiguously in the query's tokens
    (confidence 0.5-0.9, scaled by how much of the query the key covers).
``SUBSTRING``
    The compact key occurs inside the compact query (or vice versa) but
    not on token boundaries (confidence 0.15-0.45).

Within a tier the winner is the key whose match ends *latest* in the
query (English compound nouns are head-final: in "Aluminum-Clad Timber
Window" the head is "timber window", not "aluminum"), then the longest
key, then the alphabetically first key.

The confidence value is a heuristic indicator of match quality intended
to drive warnings and human review. It is **not** a statistical
probability.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

from loguru import logger

T = TypeVar("T")

LOW_CONFIDENCE_THRESHOLD: float = 0.5
"""Matches below this confidence are logged as warnings."""

_AMBIGUITY_PENALTY: float = 0.6
_NON_ALNUM = re.compile(r"[^0-9a-z]+")


class MatchType(Enum):
    """How a query was matched to a lookup key."""

    EXACT = "exact"
    TOKEN = "token"  # noqa: S105 - enum label, not a credential
    SUBSTRING = "substring"
    CATEGORY = "category"
    NONE = "none"


@dataclass(frozen=True)
class MatchResult:
    """Outcome of matching a free-text query against lookup keys.

    Attributes:
        key: The matched key (original spelling), or ``None``.
        match_type: The tier that produced the match.
        confidence: Heuristic match quality in ``[0, 1]``.
        query: The original query string.
        candidates: Competing keys from the winning tier that map to a
            different value and are not part of the winner's span.
    """

    key: str | None
    match_type: MatchType
    confidence: float
    query: str
    candidates: tuple[str, ...] = ()

    @property
    def matched(self) -> bool:
        """Whether any key was matched."""
        return self.key is not None

    @property
    def ambiguous(self) -> bool:
        """Whether competing keys with different values also matched."""
        return bool(self.candidates)

    @property
    def low_confidence(self) -> bool:
        """Whether the match falls below :data:`LOW_CONFIDENCE_THRESHOLD`."""
        return self.confidence < LOW_CONFIDENCE_THRESHOLD


@dataclass(frozen=True)
class _Candidate:
    key: str
    value: Any
    confidence: float
    start: int
    end: int
    compact_len: int
    normalized: str


def normalize(text: str) -> str:
    """Lowercase and collapse every run of non-alphanumerics to one space."""
    return _NON_ALNUM.sub(" ", text.lower()).strip()


def _singularize(token: str) -> str:
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    """Normalize ``text`` and split it into (naively singularized) tokens."""
    normalized = normalize(text)
    if not normalized:
        return []
    return [_singularize(tok) for tok in normalized.split()]


def _compact(text: str) -> str:
    return normalize(text).replace(" ", "")


def _token_len(tokens: list[str]) -> int:
    return sum(len(t) for t in tokens)


def _exact_tier(
    query_tokens: list[str], mapping: Mapping[str, Any]
) -> list[_Candidate]:
    out: list[_Candidate] = []
    for key, value in mapping.items():
        if tokenize(key) == query_tokens:
            out.append(
                _Candidate(
                    key,
                    value,
                    1.0,
                    0,
                    len(query_tokens) - 1,
                    len(_compact(key)),
                    normalize(key),
                )
            )
    return out


def _token_tier(
    query_tokens: list[str], mapping: Mapping[str, Any]
) -> list[_Candidate]:
    out: list[_Candidate] = []
    query_len = _token_len(query_tokens) or 1
    for key, value in mapping.items():
        key_tokens = tokenize(key)
        width = len(key_tokens)
        if width == 0 or width > len(query_tokens):
            continue
        last: tuple[int, int] | None = None
        for i in range(len(query_tokens) - width + 1):
            if query_tokens[i : i + width] == key_tokens:
                last = (i, i + width - 1)
        if last is None:
            continue
        coverage = min(_token_len(key_tokens) / query_len, 1.0)
        out.append(
            _Candidate(
                key,
                value,
                0.5 + 0.4 * coverage,
                last[0],
                last[1],
                len(_compact(key)),
                normalize(key),
            )
        )
    return out


def _substring_tier(query_compact: str, mapping: Mapping[str, Any]) -> list[_Candidate]:
    out: list[_Candidate] = []
    if len(query_compact) < 3:
        return out
    for key, value in mapping.items():
        key_compact = _compact(key)
        if len(key_compact) < 3:
            continue
        if key_compact in query_compact:
            start = query_compact.rfind(key_compact)
            end = start + len(key_compact) - 1
        elif query_compact in key_compact:
            start, end = 0, 0
        else:
            continue
        coverage = min(len(key_compact), len(query_compact)) / max(
            len(key_compact), len(query_compact)
        )
        out.append(
            _Candidate(
                key,
                value,
                0.15 + 0.3 * coverage,
                start,
                end,
                len(key_compact),
                normalize(key),
            )
        )
    return out


def match_key(
    query: str,
    mapping: Mapping[str, T],
    *,
    context: str = "",
    warn: bool = True,
    low_confidence_threshold: float = LOW_CONFIDENCE_THRESHOLD,
) -> MatchResult:
    """Match ``query`` to the best key of ``mapping``.

    Args:
        query: Free-text name to match (e.g. a Revit material name).
        mapping: Lookup table whose keys are candidate names.
        context: Label included in warnings (e.g. ``"EPD lookup"``).
        warn: Log a warning for low-confidence or ambiguous matches.
        low_confidence_threshold: Confidence below which to warn.

    Returns:
        A :class:`MatchResult`. ``key`` is ``None`` when nothing matched.
    """
    query_tokens = tokenize(query)
    if not query_tokens:
        return MatchResult(None, MatchType.NONE, 0.0, query)

    tiers: tuple[tuple[MatchType, list[_Candidate]], ...] = (
        (MatchType.EXACT, _exact_tier(query_tokens, mapping)),
        (MatchType.TOKEN, _token_tier(query_tokens, mapping)),
        (MatchType.SUBSTRING, _substring_tier(_compact(query), mapping)),
    )
    match_type, tier = next(
        ((mt, cands) for mt, cands in tiers if cands),
        (MatchType.NONE, []),
    )
    if not tier:
        return MatchResult(None, MatchType.NONE, 0.0, query)

    tier.sort(key=lambda c: (-c.end, -c.compact_len, c.normalized, c.key))
    winner = tier[0]

    competing = sorted(
        {
            c.key
            for c in tier[1:]
            if c.value != winner.value
            and not (winner.start <= c.start and c.end <= winner.end)
        }
    )
    confidence = winner.confidence
    if competing:
        confidence *= _AMBIGUITY_PENALTY

    result = MatchResult(
        key=winner.key,
        match_type=match_type,
        confidence=round(confidence, 3),
        query=query,
        candidates=tuple(competing),
    )

    if warn and (result.confidence < low_confidence_threshold or result.ambiguous):
        logger.warning(
            "{}Low-confidence match for '{}': -> '{}' ({}, confidence={:.3f}){}",
            f"[{context}] " if context else "",
            query,
            result.key,
            match_type.value,
            result.confidence,
            f"; competing keys: {list(competing)}" if competing else "",
        )

    return result


def best_match_value(
    query: str,
    mapping: Mapping[str, T],
    *,
    context: str = "",
    warn: bool = True,
    low_confidence_threshold: float = LOW_CONFIDENCE_THRESHOLD,
) -> tuple[T | None, MatchResult]:
    """Return ``(mapping[best_key], result)``, or ``(None, result)``."""
    result = match_key(
        query,
        mapping,
        context=context,
        warn=warn,
        low_confidence_threshold=low_confidence_threshold,
    )
    if result.key is None:
        return None, result
    return mapping[result.key], result
