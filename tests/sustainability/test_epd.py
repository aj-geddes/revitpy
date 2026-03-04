"""
Unit tests for EpdDatabase functionality.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from revitpy.sustainability.epd import _GENERIC_EPDS, EpdDatabase
from revitpy.sustainability.types import EpdRecord, LifecycleStage


@pytest.fixture
def epd_db() -> EpdDatabase:
    """Fixture providing an EpdDatabase instance."""
    return EpdDatabase()


class TestEpdDatabase:
    """Tests for EpdDatabase."""

    def test_generic_epds_populated(self, epd_db):
        """Test that generic EPDs are available in the cache."""
        result = epd_db.lookup("concrete")

        assert result is not None
        assert result.material_name == "Concrete"
        assert result.gwp_per_kg == pytest.approx(0.13)

    def test_lookup_exact_match(self, epd_db):
        """Test exact key match in lookup."""
        result = epd_db.lookup("steel")

        assert result is not None
        assert result.gwp_per_kg == pytest.approx(1.55)

    def test_lookup_fuzzy_match(self, epd_db):
        """Test fuzzy keyword matching in lookup."""
        result = epd_db.lookup("structural steel beam")

        assert result is not None
        assert result.material_name == "Steel"

    def test_lookup_case_insensitive(self, epd_db):
        """Test that lookup is case-insensitive."""
        result = epd_db.lookup("CONCRETE")

        assert result is not None
        assert result.material_name == "Concrete"

    def test_lookup_returns_none_for_unknown(self, epd_db):
        """Test that lookup returns None for unknown materials."""
        result = epd_db.lookup("unobtanium")

        assert result is None

    def test_lookup_with_category_fallback(self, epd_db):
        """Test lookup falls back to category-based match."""
        result = epd_db.lookup("portland cement", category="Concrete")

        assert result is not None
        assert result.category == "Concrete"

    def test_get_generic_epd_direct_key(self, epd_db):
        """Test generic EPD retrieval by direct key."""
        result = epd_db.get_generic_epd("concrete")

        assert result is not None
        assert result.gwp_per_kg == pytest.approx(0.13)

    def test_get_generic_epd_category_match(self, epd_db):
        """Test generic EPD retrieval by category name."""
        result = epd_db.get_generic_epd("Metals")

        assert result is not None
        assert result.category == "Metals"

    def test_get_generic_epd_fuzzy_match(self, epd_db):
        """Test generic EPD retrieval with fuzzy matching."""
        result = epd_db.get_generic_epd("insul")

        assert result is not None
        assert result.material_name == "Insulation"

    def test_get_generic_epd_returns_none_for_unknown(self, epd_db):
        """Test generic EPD returns None for unknown categories."""
        result = epd_db.get_generic_epd("exotic_material_xyz")

        assert result is None

    def test_generic_epd_values(self, epd_db):
        """Test correctness of key generic EPD GWP values."""
        concrete = epd_db.lookup("concrete")
        steel = epd_db.lookup("steel")
        timber = epd_db.lookup("timber")
        glass = epd_db.lookup("glass")
        aluminum = epd_db.lookup("aluminum")
        brick = epd_db.lookup("brick")

        assert concrete.gwp_per_kg == pytest.approx(0.13)
        assert steel.gwp_per_kg == pytest.approx(1.55)
        assert timber.gwp_per_kg == pytest.approx(0.45)
        assert glass.gwp_per_kg == pytest.approx(0.86)
        assert aluminum.gwp_per_kg == pytest.approx(8.24)
        assert brick.gwp_per_kg == pytest.approx(0.24)

    def test_generic_epds_have_lifecycle_stages(self, epd_db):
        """Test that generic EPDs include lifecycle stage data."""
        result = epd_db.lookup("concrete")

        assert len(result.lifecycle_stages) == 3
        assert LifecycleStage.A1_RAW_MATERIALS in result.lifecycle_stages

    def test_save_and_load_cache(self, epd_db, tmp_path):
        """Test cache serialization round-trip."""
        cache_file = tmp_path / "epd_cache.json"
        epd_db.save_cache(cache_file)

        assert cache_file.exists()

        new_db = EpdDatabase(cache_path=cache_file)
        result = new_db.lookup("concrete")

        assert result is not None
        assert result.gwp_per_kg == pytest.approx(0.13)

    def test_save_cache_creates_directory(self, epd_db, tmp_path):
        """Test that save_cache creates parent directories."""
        cache_file = tmp_path / "subdir" / "nested" / "cache.json"
        epd_db.save_cache(cache_file)

        assert cache_file.exists()

    def test_load_cache_nonexistent_file(self, epd_db, tmp_path):
        """Test that loading nonexistent cache doesn't raise."""
        epd_db.load_cache(tmp_path / "nonexistent.json")
        # Should silently skip.

    def test_load_cache_invalid_json(self, epd_db, tmp_path):
        """Test that loading invalid JSON doesn't raise."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json {{{", encoding="utf-8")

        epd_db.load_cache(bad_file)
        # Should log error but not raise.

    def test_cache_contents_json_structure(self, epd_db, tmp_path):
        """Test that saved cache has valid JSON structure."""
        cache_file = tmp_path / "cache.json"
        epd_db.save_cache(cache_file)

        data = json.loads(cache_file.read_text(encoding="utf-8"))

        assert "concrete" in data
        assert "gwp_per_kg" in data["concrete"]
        assert "lifecycle_stages" in data["concrete"]

    def test_database_init_with_cache_path(self, tmp_path):
        """Test initializing database with a cache path."""
        cache_file = tmp_path / "cache.json"

        # Save some data first.
        db1 = EpdDatabase()
        db1.save_cache(cache_file)

        # Load it in a new instance.
        db2 = EpdDatabase(cache_path=cache_file)
        result = db2.lookup("steel")

        assert result is not None
        assert result.gwp_per_kg == pytest.approx(1.55)

    def test_database_init_without_token(self):
        """Test that database initializes correctly without API token."""
        db = EpdDatabase()
        assert db._api_token is None

    @pytest.mark.asyncio
    async def test_lookup_async_falls_back_to_local(self, epd_db):
        """Test that async lookup falls back to local cache."""
        result = await epd_db.lookup_async("concrete")

        assert result is not None
        assert result.material_name == "Concrete"

    @pytest.mark.asyncio
    async def test_lookup_async_returns_none_for_unknown(self, epd_db):
        """Test that async lookup returns None for unknown materials."""
        result = await epd_db.lookup_async("unobtanium")

        assert result is None

    @pytest.mark.asyncio
    async def test_search_async_local_results(self, epd_db):
        """Test that async search returns results from local cache."""
        results = await epd_db.search_async("concrete")

        assert len(results) >= 1
        assert any(r.material_name == "Concrete" for r in results)

    @pytest.mark.asyncio
    async def test_search_async_respects_limit(self, epd_db):
        """Test that async search respects the limit parameter."""
        results = await epd_db.search_async("steel", limit=1)

        assert len(results) <= 1
