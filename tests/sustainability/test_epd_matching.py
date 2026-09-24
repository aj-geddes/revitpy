"""
Tests for EPD provenance, the insulation split, and scored matching.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from revitpy.sustainability.epd import (
    _GENERIC_EPDS,
    GENERIC_FALLBACK_MAX_CONFIDENCE,
    ICE_V2_SOURCE,
    EpdDatabase,
)
from revitpy.sustainability.types import EpdRecord


@pytest.fixture
def db() -> EpdDatabase:
    return EpdDatabase()


class TestProvenance:
    @pytest.mark.parametrize("key", sorted(_GENERIC_EPDS))
    def test_builtin_record_is_sourced(self, key):
        record = _GENERIC_EPDS[key]

        assert record.source == ICE_V2_SOURCE
        assert record.source_year == 2011
        assert "ICE v2.0 row" in record.notes
        assert len(record.lifecycle_stages) == 3
        if record.gwp_per_m3 is not None:
            assert record.assumed_density_kg_m3 is not None
            assert record.gwp_per_m3 == pytest.approx(
                record.gwp_per_kg * record.assumed_density_kg_m3, rel=1e-3
            )

    def test_lookup_does_not_mutate_builtin_records(self, db):
        db.lookup("concrete")

        assert _GENERIC_EPDS["concrete"].match_type is None
        assert _GENERIC_EPDS["concrete"].match_confidence is None


class TestInsulationSplit:
    @pytest.mark.parametrize(
        ("name", "gwp", "key"),
        [
            ("Mineral Wool Batt", 1.28, "mineral wool"),
            ("EPS Insulation Board", 3.29, "eps"),
            ("Glass Wool Insulation", 1.35, "glass wool"),
            ("Rockwool Slab", 1.12, "rockwool"),
            ("Stone Wool Insulation", 1.12, "stone wool"),
            ("PIR Board", 4.26, "pir"),
        ],
    )
    def test_specific_types(self, db, name, gwp, key):
        result = db.lookup(name)

        assert result is not None
        assert result.gwp_per_kg == pytest.approx(gwp)
        assert result.matched_key == key
        assert not result.is_generic_fallback

    def test_generic_insulation_is_low_confidence(self, db):
        result = db.lookup("Insulation")

        assert result is not None
        assert result.matched_key == "insulation"
        assert result.is_generic_fallback
        assert result.match_confidence is not None
        assert result.match_confidence <= GENERIC_FALLBACK_MAX_CONFIDENCE

    def test_xps_uses_flagged_generic_polystyrene(self, db):
        result = db.lookup("Rigid XPS Insulation Board")

        assert result is not None
        assert result.matched_key == "xps"
        assert result.is_generic_fallback
        assert result.match_confidence is not None
        assert result.match_confidence <= GENERIC_FALLBACK_MAX_CONFIDENCE
        assert "XPS" in result.notes


class TestMatching:
    def test_exact(self, db):
        result = db.lookup("Concrete")

        assert result is not None
        assert result.match_type == "exact"
        assert result.match_confidence == 1.0

    def test_compound_name(self, db):
        result = db.lookup("Aluminum-Clad Timber Window")

        assert result is not None
        assert result.matched_key == "timber"
        assert result.match_type == "token"
        assert result.match_confidence is not None
        assert result.match_confidence < 0.5

    def test_compound_name_is_order_independent(self):
        forward = EpdDatabase()
        backward = EpdDatabase()
        backward._cache = dict(reversed(list(backward._cache.items())))

        for name in ("Aluminum-Clad Timber Window", "Steel-Reinforced Concrete Slab"):
            assert forward.lookup(name) == backward.lookup(name)

    def test_category_fallback_is_flagged(self, db):
        result = db.lookup("portland cement", category="Concrete")

        assert result is not None
        assert result.match_type == "category"
        assert result.match_confidence is not None
        assert result.match_confidence <= 0.3

    def test_category_representative_is_deterministic(self, db):
        generic = db.get_generic_epd("Metals")

        assert generic is not None
        assert generic.material_name == "Steel"


class TestOverrides:
    def test_constructor_override(self):
        db = EpdDatabase(
            overrides={
                "concrete": EpdRecord(
                    material_name="Project Concrete",
                    category="Concrete",
                    gwp_per_kg=0.2,
                    source="Supplier EPD 2024",
                )
            }
        )
        result = db.lookup("concrete")

        assert result is not None
        assert result.gwp_per_kg == pytest.approx(0.2)
        assert result.source == "Supplier EPD 2024"

    def test_register(self, db):
        db.register(
            "CLT",
            EpdRecord(
                material_name="CLT",
                category="Wood",
                gwp_per_kg=0.44,
                source="Supplier EPD 2023",
            ),
        )
        result = db.lookup("CLT Floor Panel")

        assert result is not None
        assert result.gwp_per_kg == pytest.approx(0.44)

    def test_cache_round_trip_keeps_provenance(self, db, tmp_path: Path):
        cache = tmp_path / "c.json"
        db.save_cache(cache)

        result = EpdDatabase(cache_path=cache).lookup("insulation")

        assert result is not None
        assert result.source_year == 2011
        assert result.is_generic_fallback
        assert result.notes
