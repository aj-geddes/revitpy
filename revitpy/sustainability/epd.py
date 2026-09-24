"""
Environmental Product Declaration (EPD) database and lookup.

This module provides EPD data management including generic fallback values,
local caching, and optional async lookup against the EC3 (Embodied Carbon
in Construction Calculator) API.

The built-in factors are screening-level generic averages (cradle-to-gate,
A1-A3) from the ICE database, each carrying its source row, data year and
any density assumption. They are not product EPDs; register product- or
region-specific records with :meth:`EpdDatabase.register` or the
``overrides`` constructor argument.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from loguru import logger

from .exceptions import EpdLookupError
from .matching import (
    LOW_CONFIDENCE_THRESHOLD,
    MatchType,
    best_match_value,
    match_key,
)
from .types import EpdRecord, LifecycleStage

_A1_A3: tuple[LifecycleStage, ...] = (
    LifecycleStage.A1_RAW_MATERIALS,
    LifecycleStage.A2_TRANSPORT,
    LifecycleStage.A3_MANUFACTURING,
)

ICE_V2_SOURCE = (
    "ICE v2.0 (Hammond & Jones, Inventory of Carbon & Energy, University of "
    "Bath, Jan 2011), summary tables"
)
"""Citation for the built-in generic factors.

ICE v3.0 (Circular Ecology, 2019) values could not be verified against the
primary publication when these records were written, so the built-in
factors cite the ICE v2.0 summary tables, which were checked line by line.
ICE is a cradle-to-gate (A1-A3) generic inventory, not a product EPD, so
no ``valid_until`` date applies; ``source_year`` records the data vintage.
"""

_DENSITY_NOTE = "gwp_per_m3 derived from an assumed density, not from ICE"


def _ice(
    name: str,
    category: str,
    gwp_per_kg: float,
    ice_row: str,
    *,
    density: float | None = None,
    notes: str = "",
    generic: bool = False,
) -> EpdRecord:
    """Build a built-in generic record citing an ICE v2.0 row."""
    parts = [f"ICE v2.0 row: {ice_row}."]
    if density is not None:
        parts.append(f"{_DENSITY_NOTE} ({density:g} kg/m3).")
    if notes:
        parts.append(notes)
    return EpdRecord(
        material_name=name,
        category=category,
        gwp_per_kg=gwp_per_kg,
        gwp_per_m3=round(gwp_per_kg * density, 2) if density is not None else None,
        source=ICE_V2_SOURCE,
        lifecycle_stages=list(_A1_A3),
        valid_until=None,
        source_year=2011,
        assumed_density_kg_m3=density,
        notes=" ".join(parts),
        is_generic_fallback=generic,
    )


_MINERAL_WOOL = _ice(
    "Mineral Wool Insulation",
    "Insulation",
    1.28,
    "Insulation / Mineral wool, 1.28 kgCO2e/kg",
    notes="Density varies widely by product; no volumetric factor provided.",
)
_ROCK_WOOL = _ice(
    "Rock Wool (Stone Wool) Insulation",
    "Insulation",
    1.12,
    "Insulation / Rockwool, 1.12 kgCO2e/kg",
    notes="ICE comments this row as 'Cradle to Grave'.",
)
_GLASS_WOOL = _ice(
    "Glass Wool (Fibreglass) Insulation",
    "Insulation",
    1.35,
    "Insulation / Fibreglass (Glasswool), 1.35 kgCO2/kg",
    notes=(
        "ICE gives kgCO2 only (no kgCO2e) and flags 'poor data'; treat as a "
        "lower bound for GWP."
    ),
)
_EPS = _ice(
    "Expanded Polystyrene (EPS) Insulation",
    "Insulation",
    3.29,
    "Plastics / Expanded Polystyrene, 3.29 kgCO2e/kg",
)
_POLYSTYRENE = _ice(
    "Polystyrene (generic)",
    "Insulation",
    3.43,
    "Plastics / General Purpose Polystyrene, 3.43 kgCO2e/kg",
    notes=(
        "ICE v2.0 has no XPS-specific row. XPS blowing agents can raise GWP "
        "substantially; use a product EPD for XPS."
    ),
    generic=True,
)
_PUR_PIR = _ice(
    "Polyurethane / PIR Rigid Foam Insulation",
    "Insulation",
    4.26,
    "Plastics / Polyurethane Rigid Foam, 4.26 kgCO2e/kg",
)
_GENERIC_INSULATION = _ice(
    "Insulation (generic)",
    "Insulation",
    1.86,
    "Insulation / General Insulation, 1.86 kgCO2/kg",
    notes=(
        "Market-share blend of mineral wool and foam products (kgCO2 only). "
        "Mineral wool (~1.1-1.3) and EPS/PUR foams (~3.3-4.3 kgCO2e/kg) "
        "differ by 3x; identify the insulation type."
    ),
    generic=True,
)

# Built-in generic A1-A3 factors keyed by lookup name. Aliases share a
# record. Override any entry via ``EpdDatabase(overrides=...)`` or
# :meth:`EpdDatabase.register`.
_GENERIC_EPDS: dict[str, EpdRecord] = {
    "concrete": _ice(
        "Concrete",
        "Concrete",
        0.107,
        "Concrete / General, 0.107 kgCO2e/kg",
        density=2400.0,
        notes=(
            "ICE strongly recommends a specific mix over the general value "
            "(e.g. 25/30 MPa: 0.113; RC adds rebar)."
        ),
    ),
    "steel": _ice(
        "Steel",
        "Metals",
        1.46,
        "Steel / General - UK (EU) Average Recycled Content, 1.46 kgCO2e/kg",
        density=7850.0,
        notes="EU average recycled content 59%.",
    ),
    "timber": _ice(
        "Timber",
        "Wood",
        0.31,
        "Timber / General, 0.31 kgCO2e/kg fossil (+0.41 biogenic)",
        density=500.0,
        notes="Fossil carbon only; biogenic carbon and storage excluded.",
    ),
    "glass": _ice(
        "Glass",
        "Glass",
        0.91,
        "Glass / Primary Glass, 0.91 kgCO2e/kg",
        density=2500.0,
    ),
    "aluminum": _ice(
        "Aluminum",
        "Metals",
        9.16,
        "Aluminium / General, 9.16 kgCO2e/kg",
        density=2700.0,
        notes="Worldwide average recycled content assumed by ICE.",
    ),
    "brick": _ice(
        "Brick",
        "Masonry",
        0.24,
        "Bricks / General (Common Brick), 0.24 kgCO2e/kg",
        density=1800.0,
    ),
    "gypsum": _ice(
        "Gypsum Board",
        "Interior Finishes",
        0.39,
        "Plaster / Plasterboard, 0.39 kgCO2e/kg",
        density=800.0,
    ),
    "mineral wool": _MINERAL_WOOL,
    "rock wool": _ROCK_WOOL,
    "rockwool": _ROCK_WOOL,
    "stone wool": _ROCK_WOOL,
    "glass wool": _GLASS_WOOL,
    "fiberglass": _GLASS_WOOL,
    "fibreglass": _GLASS_WOOL,
    "eps": _EPS,
    "expanded polystyrene": _EPS,
    "polystyrene": _POLYSTYRENE,
    "xps": _POLYSTYRENE,
    "extruded polystyrene": _POLYSTYRENE,
    "polyurethane": _PUR_PIR,
    "pir": _PUR_PIR,
    "pur": _PUR_PIR,
    "polyisocyanurate": _PUR_PIR,
    "insulation": _GENERIC_INSULATION,
}

GENERIC_FALLBACK_MAX_CONFIDENCE = 0.3
"""Confidence cap for matches that land on a generic fallback record."""

_CATEGORY_CONFIDENCE = 0.2

# Explicit representative record for each generic category, so category
# fallback never depends on dict order (e.g. "Metals" -> steel, not
# whichever metal happened to be listed first).
_CATEGORY_DEFAULTS: dict[str, str] = {
    "concrete": "concrete",
    "metals": "steel",
    "metal": "steel",
    "wood": "timber",
    "glass": "glass",
    "masonry": "brick",
    "interior finishes": "gypsum",
    "insulation": "insulation",
}


def _with_match(
    epd: EpdRecord,
    match_type: MatchType,
    confidence: float,
    key: str | None,
) -> EpdRecord:
    """Return a copy of ``epd`` annotated with how it was matched."""
    return replace(
        epd,
        lifecycle_stages=list(epd.lifecycle_stages),
        match_type=match_type.value,
        match_confidence=round(confidence, 3),
        matched_key=key,
    )


class EpdDatabase:
    """Environmental Product Declaration database with cache and API support.

    Provides EPD lookup from a local cache of generic values and optionally
    from the EC3 API when an API token is supplied.
    """

    def __init__(
        self,
        *,
        api_token: str | None = None,
        cache_path: Path | str | None = None,
        overrides: dict[str, EpdRecord] | None = None,
    ) -> None:
        self._api_token = api_token
        self._cache: dict[str, EpdRecord] = {}
        self._cache_path = Path(cache_path) if cache_path else None

        # Pre-populate cache with generic values.
        for key, epd in _GENERIC_EPDS.items():
            self._cache[key] = epd

        if self._cache_path and self._cache_path.exists():
            self.load_cache(self._cache_path)

        for key, epd in (overrides or {}).items():
            self.register(key, epd)

        logger.debug(
            "EpdDatabase initialized with {} cached entries",
            len(self._cache),
        )

    def register(self, key: str, epd: EpdRecord) -> None:
        """Add or replace a record, e.g. a project-specific product EPD.

        Registered records take part in matching exactly like the
        built-in generic records, and replace any record under the same
        (case-insensitive) key.

        Args:
            key: Lookup name (matched case-insensitively).
            epd: The EPD record to use for that name.
        """
        self._cache[key.lower().strip()] = epd

    def lookup(
        self,
        material_name: str,
        category: str | None = None,
    ) -> EpdRecord | None:
        """Look up an EPD record for a material.

        Matching is deterministic and scored (see
        :mod:`revitpy.sustainability.matching`). Specific records are
        tried before generic fallback records. Within each pass: exact
        name, then
        whole-token match (e.g. "Aluminum-Clad Timber Window" ->
        "timber"), then substring. When nothing matches, a
        category-level generic record is used if ``category`` is given.

        The returned record is a copy annotated with ``match_type``,
        ``match_confidence`` and ``matched_key``. Matches that land on a
        generic fallback record (e.g. "insulation") are capped at
        :data:`GENERIC_FALLBACK_MAX_CONFIDENCE`. Low-confidence or
        ambiguous matches are logged as warnings.

        Args:
            material_name: Name of the material to look up.
            category: Optional material category used as a last resort.

        Returns:
            Annotated EpdRecord copy, or ``None`` if not found.
        """
        # Specific records first, so "Glass Wool Insulation" resolves to
        # glass wool rather than a generic fallback; the catch-all generic
        # "insulation" record is tried last of all.
        passes = (
            {k: v for k, v in self._cache.items() if not v.is_generic_fallback},
            {k: v for k, v in self._cache.items() if v is not _GENERIC_INSULATION},
            self._cache,
        )
        result = match_key(material_name, passes[0], warn=False)
        for mapping in passes[1:]:
            if result.key is not None:
                break
            result = match_key(material_name, mapping, warn=False)
        if result.key is not None:
            epd = self._cache[result.key]
            confidence = result.confidence
            if epd.is_generic_fallback:
                confidence = min(confidence, GENERIC_FALLBACK_MAX_CONFIDENCE)
            if confidence < LOW_CONFIDENCE_THRESHOLD or result.ambiguous:
                logger.warning(
                    "Low-confidence EPD match for '{}': -> '{}' ({}, "
                    "confidence={:.2f}{}{}). Screening-level factor; verify.",
                    material_name,
                    result.key,
                    result.match_type.value,
                    confidence,
                    ", generic fallback" if epd.is_generic_fallback else "",
                    f", competing: {list(result.candidates)}"
                    if result.ambiguous
                    else "",
                )
            else:
                logger.debug(
                    "EPD match '{}' -> '{}' ({}, {:.2f})",
                    material_name,
                    result.key,
                    result.match_type.value,
                    confidence,
                )
            return _with_match(epd, result.match_type, confidence, result.key)

        if category:
            fallback = self._generic_for_category(category)
            if fallback is not None:
                key, epd = fallback
                logger.warning(
                    "No EPD match for '{}'; using category fallback '{}' -> '{}' "
                    "(confidence={:.2f})",
                    material_name,
                    category,
                    key,
                    _CATEGORY_CONFIDENCE,
                )
                return _with_match(epd, MatchType.CATEGORY, _CATEGORY_CONFIDENCE, key)

        logger.warning("No EPD found for material '{}'", material_name)
        return None

    async def lookup_async(
        self,
        material_name: str,
        category: str | None = None,
    ) -> EpdRecord | None:
        """Asynchronously look up an EPD record, querying EC3 API if available.

        Falls back to the synchronous local lookup when no API token is set.

        Args:
            material_name: Name of the material to look up.
            category: Optional material category for the search.

        Returns:
            Matching EpdRecord or ``None`` if not found.

        Raises:
            EpdLookupError: If the API request fails.
        """
        # Try local cache first.
        local = self.lookup(material_name, category)
        if local is not None:
            return local

        if not self._api_token:
            return None

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                params: dict[str, str] = {"name": material_name}
                if category:
                    params["category"] = category

                response = await client.get(
                    "https://buildingtransparency.org/api/epds",
                    params=params,
                    headers={"Authorization": f"Bearer {self._api_token}"},
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

                if data and isinstance(data, list) and len(data) > 0:
                    item = data[0]
                    epd = EpdRecord(
                        material_name=item.get("name", material_name),
                        category=item.get("category", category or ""),
                        gwp_per_kg=float(item.get("gwp", 0.0)),
                        source="ec3-api",
                        manufacturer=item.get("manufacturer"),
                    )
                    self._cache[material_name.lower().strip()] = epd
                    return epd
        except ImportError:
            logger.warning("httpx not available for async EPD lookup")
        except Exception as exc:
            raise EpdLookupError(
                f"EC3 API lookup failed for '{material_name}': {exc}",
                material_name=material_name,
                category=category,
                cause=exc,
            ) from exc

        return None

    async def search_async(
        self,
        query: str,
        limit: int = 10,
    ) -> list[EpdRecord]:
        """Search for EPD records matching a query.

        Searches the local cache using keyword matching. When an EC3
        API token is configured the remote API is also queried.

        Args:
            query: Search query string.
            limit: Maximum number of results to return.

        Returns:
            List of matching EpdRecord instances.
        """
        scored: list[tuple[int, float, str, EpdRecord]] = []
        tier_rank = {MatchType.EXACT: 0, MatchType.TOKEN: 1, MatchType.SUBSTRING: 2}
        for key, epd in self._cache.items():
            match = match_key(query, {key: epd}, warn=False)
            if match.key is None:
                continue
            scored.append(
                (
                    tier_rank.get(match.match_type, 3),
                    -match.confidence,
                    key,
                    _with_match(epd, match.match_type, match.confidence, key),
                )
            )
        scored.sort(key=lambda item: item[:3])

        results: list[EpdRecord] = []
        seen: set[str] = set()
        for _, _, _, epd in scored:
            if epd.material_name in seen:
                continue
            seen.add(epd.material_name)
            results.append(epd)
            if len(results) >= limit:
                return results

        if self._api_token:
            try:
                import httpx

                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        "https://buildingtransparency.org/api/epds",
                        params={"search": query, "limit": limit},
                        headers={
                            "Authorization": f"Bearer {self._api_token}",
                        },
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    data = response.json()

                    for item in data[:limit]:
                        epd = EpdRecord(
                            material_name=item.get("name", query),
                            category=item.get("category", ""),
                            gwp_per_kg=float(item.get("gwp", 0.0)),
                            source="ec3-api",
                            manufacturer=item.get("manufacturer"),
                        )
                        results.append(epd)
            except ImportError:
                logger.warning("httpx not available for async EPD search")
            except Exception as exc:
                logger.warning("EC3 API search failed: {}", exc)

        return results[:limit]

    def get_generic_epd(self, material_category: str) -> EpdRecord | None:
        """Get the built-in generic EPD record for a material category.

        Args:
            material_category: Category name (e.g. "Concrete", "Metals").

        Returns:
            Matching generic EpdRecord or ``None``.
        """
        found = self._generic_for_category(material_category)
        return found[1] if found is not None else None

    @staticmethod
    def _generic_for_category(category: str) -> tuple[str, EpdRecord] | None:
        """Resolve a category to a generic record deterministically.

        Tries the generic record keys first, then the explicit
        :data:`_CATEGORY_DEFAULTS` table (e.g. "Metals" -> steel).
        """
        result = match_key(category, _GENERIC_EPDS, warn=False)
        if result.key is not None:
            return result.key, _GENERIC_EPDS[result.key]
        key, match = best_match_value(category, _CATEGORY_DEFAULTS, warn=False)
        if key is not None:
            return key, _GENERIC_EPDS[key]
        return None

    def load_cache(self, path: Path | str) -> None:
        """Load cached EPD records from a JSON file.

        Args:
            path: Path to the JSON cache file.
        """
        path = Path(path)
        if not path.exists():
            logger.warning("Cache file not found: {}", path)
            return

        try:
            with open(path) as f:
                data = json.load(f)

            for key, record in data.items():
                stages = [LifecycleStage(s) for s in record.get("lifecycle_stages", [])]
                self._cache[key] = EpdRecord(
                    material_name=record["material_name"],
                    category=record["category"],
                    gwp_per_kg=float(record["gwp_per_kg"]),
                    gwp_per_m3=(
                        float(record["gwp_per_m3"])
                        if record.get("gwp_per_m3") is not None
                        else None
                    ),
                    source=record.get("source", "cache"),
                    lifecycle_stages=stages,
                    valid_until=record.get("valid_until"),
                    manufacturer=record.get("manufacturer"),
                    source_year=record.get("source_year"),
                    assumed_density_kg_m3=record.get("assumed_density_kg_m3"),
                    notes=record.get("notes", ""),
                    is_generic_fallback=bool(record.get("is_generic_fallback", False)),
                )

            logger.info("Loaded {} EPD records from cache", len(data))
        except (json.JSONDecodeError, KeyError) as exc:
            logger.error("Failed to load EPD cache: {}", exc)

    def save_cache(self, path: Path | str) -> None:
        """Save cached EPD records to a JSON file.

        Args:
            path: Path to the JSON cache file to write.
        """
        path = Path(path)
        data: dict[str, dict[str, Any]] = {}

        for key, epd in self._cache.items():
            data[key] = {
                "material_name": epd.material_name,
                "category": epd.category,
                "gwp_per_kg": epd.gwp_per_kg,
                "gwp_per_m3": epd.gwp_per_m3,
                "source": epd.source,
                "lifecycle_stages": [s.value for s in epd.lifecycle_stages],
                "valid_until": epd.valid_until,
                "manufacturer": epd.manufacturer,
                "source_year": epd.source_year,
                "assumed_density_kg_m3": epd.assumed_density_kg_m3,
                "notes": epd.notes,
                "is_generic_fallback": epd.is_generic_fallback,
            }

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info("Saved {} EPD records to cache", len(data))
