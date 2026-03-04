"""
Environmental Product Declaration (EPD) database and lookup.

This module provides EPD data management including generic fallback values,
local caching, and optional async lookup against the EC3 (Embodied Carbon
in Construction Calculator) API.
"""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from .exceptions import EpdLookupError
from .types import EpdRecord, LifecycleStage

# Generic EPD values for common building materials (A1-A3 stages).
# Sources: ICE Database, EPD databases, and industry averages.
_GENERIC_EPDS: dict[str, EpdRecord] = {
    "concrete": EpdRecord(
        material_name="Concrete",
        category="Concrete",
        gwp_per_kg=0.13,
        gwp_per_m3=312.0,
        source="generic-ice",
        lifecycle_stages=[
            LifecycleStage.A1_RAW_MATERIALS,
            LifecycleStage.A2_TRANSPORT,
            LifecycleStage.A3_MANUFACTURING,
        ],
    ),
    "steel": EpdRecord(
        material_name="Steel",
        category="Metals",
        gwp_per_kg=1.55,
        gwp_per_m3=12167.5,
        source="generic-ice",
        lifecycle_stages=[
            LifecycleStage.A1_RAW_MATERIALS,
            LifecycleStage.A2_TRANSPORT,
            LifecycleStage.A3_MANUFACTURING,
        ],
    ),
    "timber": EpdRecord(
        material_name="Timber",
        category="Wood",
        gwp_per_kg=0.45,
        gwp_per_m3=225.0,
        source="generic-ice",
        lifecycle_stages=[
            LifecycleStage.A1_RAW_MATERIALS,
            LifecycleStage.A2_TRANSPORT,
            LifecycleStage.A3_MANUFACTURING,
        ],
    ),
    "glass": EpdRecord(
        material_name="Glass",
        category="Glass",
        gwp_per_kg=0.86,
        gwp_per_m3=2150.0,
        source="generic-ice",
        lifecycle_stages=[
            LifecycleStage.A1_RAW_MATERIALS,
            LifecycleStage.A2_TRANSPORT,
            LifecycleStage.A3_MANUFACTURING,
        ],
    ),
    "aluminum": EpdRecord(
        material_name="Aluminum",
        category="Metals",
        gwp_per_kg=8.24,
        gwp_per_m3=22248.0,
        source="generic-ice",
        lifecycle_stages=[
            LifecycleStage.A1_RAW_MATERIALS,
            LifecycleStage.A2_TRANSPORT,
            LifecycleStage.A3_MANUFACTURING,
        ],
    ),
    "brick": EpdRecord(
        material_name="Brick",
        category="Masonry",
        gwp_per_kg=0.24,
        gwp_per_m3=432.0,
        source="generic-ice",
        lifecycle_stages=[
            LifecycleStage.A1_RAW_MATERIALS,
            LifecycleStage.A2_TRANSPORT,
            LifecycleStage.A3_MANUFACTURING,
        ],
    ),
    "insulation": EpdRecord(
        material_name="Insulation",
        category="Insulation",
        gwp_per_kg=1.86,
        gwp_per_m3=55.8,
        source="generic-ice",
        lifecycle_stages=[
            LifecycleStage.A1_RAW_MATERIALS,
            LifecycleStage.A2_TRANSPORT,
            LifecycleStage.A3_MANUFACTURING,
        ],
    ),
    "gypsum": EpdRecord(
        material_name="Gypsum Board",
        category="Interior Finishes",
        gwp_per_kg=0.39,
        gwp_per_m3=312.0,
        source="generic-ice",
        lifecycle_stages=[
            LifecycleStage.A1_RAW_MATERIALS,
            LifecycleStage.A2_TRANSPORT,
            LifecycleStage.A3_MANUFACTURING,
        ],
    ),
}


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
    ) -> None:
        self._api_token = api_token
        self._cache: dict[str, EpdRecord] = {}
        self._cache_path = Path(cache_path) if cache_path else None

        # Pre-populate cache with generic values.
        for key, epd in _GENERIC_EPDS.items():
            self._cache[key] = epd

        if self._cache_path and self._cache_path.exists():
            self.load_cache(self._cache_path)

        logger.debug(
            "EpdDatabase initialized with {} cached entries",
            len(self._cache),
        )

    def lookup(
        self,
        material_name: str,
        category: str | None = None,
    ) -> EpdRecord | None:
        """Look up an EPD record for a material.

        Searches the local cache first using exact match, then tries
        fuzzy keyword matching. Falls back to category-based generic
        lookup when no direct match is found.

        Args:
            material_name: Name of the material to look up.
            category: Optional material category for narrowing the search.

        Returns:
            Matching EpdRecord or ``None`` if not found.
        """
        key = material_name.lower().strip()

        # Exact cache match.
        if key in self._cache:
            logger.debug("EPD cache hit for '{}'", material_name)
            return self._cache[key]

        # Fuzzy keyword match against cache keys.
        for cache_key, epd in self._cache.items():
            if cache_key in key or key in cache_key:
                logger.debug(
                    "EPD fuzzy match: '{}' -> '{}'",
                    material_name,
                    cache_key,
                )
                return epd

        # Fuzzy keyword match against generic EPD keys.
        for generic_key in _GENERIC_EPDS:
            if generic_key in key or key in generic_key:
                logger.debug(
                    "EPD generic fuzzy match: '{}' -> '{}'",
                    material_name,
                    generic_key,
                )
                return _GENERIC_EPDS[generic_key]

        # Category-based fallback.
        if category:
            epd = self.get_generic_epd(category)
            if epd:
                return epd

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
        results: list[EpdRecord] = []
        query_lower = query.lower().strip()

        # Search local cache.
        for key, epd in self._cache.items():
            if query_lower in key or key in query_lower:
                results.append(epd)
            if len(results) >= limit:
                return results

        # Search generic database.
        for key, epd in _GENERIC_EPDS.items():
            if query_lower in key or key in query_lower:
                if epd not in results:
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
        """Get a generic EPD record for a material category.

        Args:
            material_category: Category name (e.g. "Concrete", "Metals").

        Returns:
            Matching generic EpdRecord or ``None``.
        """
        cat_lower = material_category.lower().strip()

        # Direct key match.
        if cat_lower in _GENERIC_EPDS:
            return _GENERIC_EPDS[cat_lower]

        # Match against category fields of generic EPDs.
        for epd in _GENERIC_EPDS.values():
            if cat_lower in epd.category.lower():
                return epd

        # Fuzzy keyword match.
        for key in _GENERIC_EPDS:
            if key in cat_lower or cat_lower in key:
                return _GENERIC_EPDS[key]

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
        data: dict[str, dict] = {}

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
            }

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info("Saved {} EPD records to cache", len(data))
