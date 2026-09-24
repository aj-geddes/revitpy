"""
Unit tests for deterministic scored name matching.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from loguru import logger

from revitpy.sustainability.matching import (
    MatchType,
    best_match_value,
    match_key,
    normalize,
    tokenize,
)

MAP = {
    "aluminum": "ALU",
    "timber": "TIM",
    "glass": "GLA",
    "glass wool": "GW",
    "steel": "STL",
    "concrete": "CON",
}
REVERSED_MAP = dict(reversed(list(MAP.items())))


@pytest.fixture
def warnings() -> Iterator[list[str]]:
    """Capture loguru WARNING messages."""
    messages: list[str] = []
    handler_id = logger.add(messages.append, level="WARNING", format="{message}")
    try:
        yield messages
    finally:
        logger.remove(handler_id)


class TestNormalization:
    def test_normalize(self):
        assert (
            normalize("Aluminum-Clad  Timber_Window") == "aluminum clad timber window"
        )

    def test_tokenize_singularizes(self):
        assert tokenize("Bricks") == ["brick"]
        assert tokenize("glass") == ["glass"]


class TestMatchTiers:
    def test_exact_match_is_case_and_punctuation_insensitive(self):
        result = match_key("CONCRETE", MAP)

        assert result.key == "concrete"
        assert result.match_type == MatchType.EXACT
        assert result.confidence == 1.0
        assert not result.ambiguous

    def test_compound_name_prefers_head_noun_and_flags_ambiguity(self):
        result = match_key("Aluminum-Clad Timber Window", MAP)

        assert result.key == "timber"
        assert result.match_type == MatchType.TOKEN
        assert result.ambiguous
        assert result.candidates == ("aluminum",)
        assert result.low_confidence

    def test_longest_key_within_span_is_not_ambiguous(self):
        result = match_key("Glass Wool Insulation", MAP)

        assert result.key == "glass wool"
        assert not result.ambiguous

    def test_token_beats_substring(self):
        result = match_key("Steel Beam", MAP)

        assert result.key == "steel"
        assert result.match_type == MatchType.TOKEN

    def test_substring_tier_is_low_confidence(self):
        result = match_key("Steelwork", MAP)

        assert result.key == "steel"
        assert result.match_type == MatchType.SUBSTRING
        assert result.confidence < 0.5

    def test_query_inside_key_is_substring(self):
        result = match_key("conc", MAP)

        assert result.key == "concrete"
        assert result.match_type == MatchType.SUBSTRING

    def test_no_match(self):
        result = match_key("unobtanium", MAP)

        assert result.key is None
        assert result.match_type == MatchType.NONE
        assert result.confidence == 0.0
        assert not result.matched

    def test_empty_query(self):
        assert match_key("", MAP).match_type == MatchType.NONE
        assert match_key("  --  ", MAP).match_type == MatchType.NONE

    def test_same_value_candidates_are_not_ambiguous(self):
        result = match_key("Wood Timber Panel", {"wood": "B1030", "timber": "B1030"})

        assert not result.ambiguous


class TestDeterminism:
    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("Aluminum-Clad Timber Window", "timber"),
            ("Timber Frame with Steel Connectors", "steel"),
            ("Glass Wool Insulation", "glass wool"),
            ("Concrete-Filled Steel Tube", "steel"),
        ],
    )
    def test_result_independent_of_insertion_order(self, query, expected):
        forward = match_key(query, MAP, warn=False)
        backward = match_key(query, REVERSED_MAP, warn=False)

        assert forward == backward
        assert forward.key == expected

    def test_equal_length_ties_break_alphabetically(self):
        mapping = {"zinc": 1, "iron": 2}
        forward = match_key("ironzinc", mapping, warn=False)
        backward = match_key("ironzinc", dict(reversed(mapping.items())), warn=False)

        assert forward == backward


class TestWarnings:
    def test_ambiguous_match_warns(self, warnings):
        match_key("Aluminum-Clad Timber Window", MAP, context="test")

        assert len(warnings) == 1
        assert "Aluminum-Clad Timber Window" in warnings[0]
        assert "aluminum" in warnings[0]

    def test_warn_false_is_silent(self, warnings):
        match_key("Aluminum-Clad Timber Window", MAP, warn=False)

        assert warnings == []

    def test_exact_match_is_silent(self, warnings):
        match_key("CONCRETE", MAP)

        assert warnings == []


class TestBestMatchValue:
    def test_returns_value_and_result(self):
        value, result = best_match_value("Aluminum-Clad Timber Window", MAP, warn=False)

        assert value == "TIM"
        assert result.key == "timber"

    def test_unknown_returns_none(self):
        value, result = best_match_value("unobtanium", MAP)

        assert value is None
        assert result.match_type == MatchType.NONE
