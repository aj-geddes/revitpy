"""
Cost estimation for RevitPy.

This module provides the CostEstimator class for mapping extracted
quantities to cost data, producing itemized cost breakdowns and
aggregated cost summaries.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from loguru import logger

from .exceptions import CostEstimationError
from .types import (
    AggregationLevel,
    CostItem,
    CostSource,
    CostSummary,
    QuantityItem,
)


class CostEstimator:
    """Estimate costs by mapping quantities to a cost database.

    The cost database is a dict mapping category/material names (str)
    to unit costs (float). It can be loaded from CSV, JSON, or YAML
    files, or provided directly as a dict.
    """

    def __init__(self, cost_database: dict[str, float] | Path | None = None) -> None:
        self._database: dict[str, float] = {}
        self._source: CostSource = CostSource.MANUAL

        if isinstance(cost_database, dict):
            self._database = dict(cost_database)
            self._source = CostSource.MANUAL
        elif isinstance(cost_database, (str, Path)):
            self.load_database(Path(cost_database))

    @property
    def database(self) -> dict[str, float]:
        """Return a copy of the current cost database."""
        return dict(self._database)

    def load_database(self, path: Path) -> None:
        """Load cost data from a file.

        Supports CSV, JSON, and YAML formats. The file format is
        auto-detected from the file extension.

        Args:
            path: Path to the cost database file.

        Raises:
            CostEstimationError: If the file cannot be loaded.
        """
        path = Path(path)
        suffix = path.suffix.lower()

        try:
            if suffix == ".csv":
                self._load_csv(path)
                self._source = CostSource.CSV_FILE
            elif suffix == ".json":
                self._load_json(path)
                self._source = CostSource.JSON_FILE
            elif suffix in (".yaml", ".yml"):
                self._load_yaml(path)
                self._source = CostSource.YAML_FILE
            else:
                raise CostEstimationError(
                    f"Unsupported cost database format: {suffix}",
                    category=None,
                )
        except CostEstimationError:
            raise
        except Exception as exc:
            raise CostEstimationError(
                f"Failed to load cost database from {path}",
                cause=exc,
            ) from exc

        logger.info("Loaded {} cost entries from {}", len(self._database), path)

    def _load_csv(self, path: Path) -> None:
        """Load cost data from a CSV file.

        Expected columns: name/category, unit_cost/cost.
        """
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                name = row.get("name") or row.get("category", "")
                cost_str = row.get("unit_cost") or row.get("cost", "0")
                if name:
                    self._database[name.strip()] = float(cost_str)

    def _load_json(self, path: Path) -> None:
        """Load cost data from a JSON file.

        Expects a top-level dict mapping names to unit costs.
        """
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)

        if isinstance(data, dict):
            for key, value in data.items():
                self._database[str(key)] = float(value)
        elif isinstance(data, list):
            for entry in data:
                name = entry.get("name") or entry.get("category", "")
                cost = entry.get("unit_cost") or entry.get("cost", 0)
                if name:
                    self._database[str(name)] = float(cost)

    def _load_yaml(self, path: Path) -> None:
        """Load cost data from a YAML file."""
        import yaml  # noqa: F811

        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        if isinstance(data, dict):
            for key, value in data.items():
                self._database[str(key)] = float(value)

    def estimate(
        self,
        quantities: list[QuantityItem],
        aggregation: AggregationLevel = AggregationLevel.CATEGORY,
    ) -> CostSummary:
        """Map quantities to costs and produce a summary.

        For each QuantityItem, the estimator looks up the unit cost
        by category name. If a category is not found in the database,
        it is skipped with a warning.

        Args:
            quantities: List of QuantityItem instances.
            aggregation: Level at which to aggregate cost totals.

        Returns:
            CostSummary with itemized costs and aggregated totals.

        Raises:
            CostEstimationError: If estimation fails.
        """
        items: list[CostItem] = []
        by_category: dict[str, float] = defaultdict(float)
        by_system: dict[str, float] = defaultdict(float)
        by_level: dict[str, float] = defaultdict(float)
        total_cost = 0.0

        for qty in quantities:
            unit_cost = self._lookup_cost(qty)
            if unit_cost is None:
                logger.debug(
                    "No cost data for category '{}', skipping",
                    qty.category,
                )
                continue

            line_cost = qty.value * unit_cost
            cost_item = CostItem(
                description=(f"{qty.element_name} - {qty.quantity_type.value}"),
                quantity=qty.value,
                unit=qty.unit,
                unit_cost=unit_cost,
                total_cost=line_cost,
                source=self._source,
                category=qty.category,
                system=qty.system,
            )
            items.append(cost_item)
            total_cost += line_cost
            by_category[qty.category] += line_cost
            if qty.system:
                by_system[qty.system] += line_cost
            if qty.level:
                by_level[qty.level] += line_cost

        summary = CostSummary(
            items=items,
            total_cost=total_cost,
            by_category=dict(by_category),
            by_system=dict(by_system),
            by_level=dict(by_level),
        )

        logger.info(
            "Estimated costs: {} items, total={:.2f}",
            len(items),
            total_cost,
        )
        return summary

    def _lookup_cost(self, qty: QuantityItem) -> float | None:
        """Look up unit cost for a quantity item.

        Tries exact category match, then case-insensitive, then
        partial match.
        """
        # Exact match
        if qty.category in self._database:
            return self._database[qty.category]

        # Case-insensitive match
        lower_category = qty.category.lower()
        for key, value in self._database.items():
            if key.lower() == lower_category:
                return value

        # Partial match
        for key, value in self._database.items():
            if key.lower() in lower_category or lower_category in key.lower():
                return value

        return None
