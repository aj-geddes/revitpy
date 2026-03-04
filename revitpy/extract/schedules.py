"""
Schedule building for RevitPy.

This module provides the ScheduleBuilder class for constructing
tabular schedule views from extracted data, with support for
column selection, filtering, sorting, grouping, and totals.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from loguru import logger

from .exceptions import ScheduleError
from .types import ScheduleConfig


class ScheduleBuilder:
    """Build schedule views from tabular data.

    A schedule is a list of dicts (rows), each containing string keys
    and arbitrary values. The builder applies column projection,
    filtering, sorting, grouping, and optional totals.
    """

    def __init__(self, config: ScheduleConfig | None = None) -> None:
        self._config = config or ScheduleConfig()

    @property
    def config(self) -> ScheduleConfig:
        """Return the current schedule configuration."""
        return self._config

    def build(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply full schedule pipeline to data.

        Steps: filter -> sort -> project columns -> add totals.

        Args:
            data: List of row dicts.

        Returns:
            Processed list of row dicts.

        Raises:
            ScheduleError: If schedule building fails.
        """
        try:
            result = list(data)

            # 1. Filter
            if self._config.filters:
                result = self.filter_data(result, self._config.filters)

            # 2. Sort
            if self._config.sort_by:
                result = self.sort_data(result, self._config.sort_by)

            # 3. Column projection
            if self._config.columns:
                result = self._project_columns(result, self._config.columns)

            # 4. Totals
            if self._config.include_totals and self._config.columns:
                result = self.add_totals(result, self._config.columns)

            logger.debug("Built schedule with {} rows", len(result))
            return result

        except ScheduleError:
            raise
        except Exception as exc:
            raise ScheduleError(
                f"Failed to build schedule: {exc}",
                cause=exc,
            ) from exc

    def filter_data(
        self,
        data: list[dict[str, Any]],
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Filter rows by matching column values.

        Each filter entry maps a column name to an expected value.
        Only rows where all filter conditions match are returned.

        Args:
            data: List of row dicts.
            filters: Dict mapping column names to required values.

        Returns:
            Filtered list of row dicts.
        """
        result: list[dict[str, Any]] = []
        for row in data:
            match = True
            for col, expected in filters.items():
                actual = row.get(col)
                if isinstance(expected, list):
                    if actual not in expected:
                        match = False
                        break
                elif actual != expected:
                    match = False
                    break
            if match:
                result.append(row)
        return result

    def sort_data(
        self,
        data: list[dict[str, Any]],
        sort_by: list[str],
    ) -> list[dict[str, Any]]:
        """Sort rows by one or more columns.

        Column names prefixed with '-' are sorted descending.

        Args:
            data: List of row dicts.
            sort_by: List of column names (prefix '-' for descending).

        Returns:
            Sorted list of row dicts.
        """
        result = list(data)

        # Apply sorts in reverse order for stable multi-key sort
        for col_spec in reversed(sort_by):
            descending = col_spec.startswith("-")
            col_name = col_spec.lstrip("-")
            result.sort(
                key=lambda row, c=col_name: (
                    row.get(c) is None,
                    row.get(c, ""),
                ),
                reverse=descending,
            )

        return result

    def group_data(
        self,
        data: list[dict[str, Any]],
        group_by: str,
    ) -> dict[str, list[dict[str, Any]]]:
        """Group rows by a column value.

        Args:
            data: List of row dicts.
            group_by: Column name to group by.

        Returns:
            Dict mapping group keys to lists of row dicts.
        """
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in data:
            key = str(row.get(group_by, "Ungrouped"))
            grouped[key].append(row)
        return dict(grouped)

    def add_totals(
        self,
        data: list[dict[str, Any]],
        columns: list[str],
    ) -> list[dict[str, Any]]:
        """Add a totals row to the data.

        Numeric columns are summed; non-numeric columns show 'TOTAL'
        for the first column and empty strings for the rest.

        Args:
            data: List of row dicts.
            columns: Column names to consider.

        Returns:
            Data with an appended totals row.
        """
        if not data:
            return data

        totals_row: dict[str, Any] = {}
        first_col = columns[0] if columns else None

        for col in columns:
            # Try summing numeric values
            numeric_values = []
            for row in data:
                val = row.get(col)
                if isinstance(val, int | float):
                    numeric_values.append(val)

            if numeric_values:
                totals_row[col] = sum(numeric_values)
            elif col == first_col:
                totals_row[col] = "TOTAL"
            else:
                totals_row[col] = ""

        result = list(data)
        result.append(totals_row)
        return result

    def _project_columns(
        self,
        data: list[dict[str, Any]],
        columns: list[str],
    ) -> list[dict[str, Any]]:
        """Project rows to only include specified columns."""
        return [{col: row.get(col) for col in columns} for row in data]
