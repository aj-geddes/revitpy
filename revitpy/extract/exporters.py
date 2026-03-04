"""
Data export for RevitPy.

This module provides the DataExporter class for writing extracted
data to various file formats (CSV, JSON, Excel, Parquet) and
returning data as plain dicts for downstream consumption.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from loguru import logger

from .exceptions import ExportError
from .types import ExportConfig, ExportFormat

# Optional dependency flags
try:
    import openpyxl  # noqa: F401

    _HAS_OPENPYXL = True
except ImportError:
    _HAS_OPENPYXL = False

try:
    import pyarrow  # noqa: F401
    import pyarrow.parquet  # noqa: F401

    _HAS_PYARROW = True
except ImportError:
    _HAS_PYARROW = False


class DataExporter:
    """Export tabular data to various formats.

    Data is expected as a list of dicts, where each dict represents
    a row with string keys mapping to scalar values.
    """

    def export(
        self,
        data: list[dict[str, Any]],
        config: ExportConfig,
    ) -> Path | list[dict[str, Any]]:
        """Export data according to the given configuration.

        Args:
            data: List of row dicts.
            config: Export configuration.

        Returns:
            Output Path for file formats, or list[dict] for DICT format.

        Raises:
            ExportError: If export fails.
        """
        fmt = config.format

        try:
            if fmt == ExportFormat.CSV:
                return self.to_csv(
                    data,
                    config.output_path,
                    include_headers=config.include_headers,
                    decimal_places=config.decimal_places,
                )
            if fmt == ExportFormat.JSON:
                return self.to_json(
                    data,
                    config.output_path,
                    decimal_places=config.decimal_places,
                )
            if fmt == ExportFormat.EXCEL:
                return self.to_excel(
                    data,
                    config.output_path,
                    sheet_name=config.sheet_name,
                    include_headers=config.include_headers,
                )
            if fmt == ExportFormat.PARQUET:
                return self.to_parquet(data, config.output_path)
            if fmt == ExportFormat.DICT:
                return self.to_dicts(data)

            raise ExportError(
                f"Unsupported export format: {fmt}",
                export_format=str(fmt),
            )

        except ExportError:
            raise
        except Exception as exc:
            raise ExportError(
                f"Export failed: {exc}",
                export_format=str(fmt),
                output_path=str(config.output_path) if config.output_path else None,
                cause=exc,
            ) from exc

    def to_csv(
        self,
        data: list[dict[str, Any]],
        path: Path | None,
        *,
        include_headers: bool = True,
        decimal_places: int = 2,
    ) -> Path:
        """Export data to CSV.

        Args:
            data: List of row dicts.
            path: Output file path.
            include_headers: Whether to write a header row.
            decimal_places: Rounding precision for floats.

        Returns:
            The output Path.

        Raises:
            ExportError: If path is None or write fails.
        """
        if path is None:
            raise ExportError(
                "Output path is required for CSV export",
                export_format="csv",
            )

        path = Path(path)
        rounded = self._round_floats(data, decimal_places)

        if not rounded:
            path.write_text("", encoding="utf-8")
            return path

        fieldnames = list(rounded[0].keys())

        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            if include_headers:
                writer.writeheader()
            writer.writerows(rounded)

        logger.info("Exported {} rows to CSV: {}", len(rounded), path)
        return path

    def to_json(
        self,
        data: list[dict[str, Any]],
        path: Path | None,
        *,
        decimal_places: int = 2,
    ) -> Path:
        """Export data to JSON.

        Args:
            data: List of row dicts.
            path: Output file path.
            decimal_places: Rounding precision for floats.

        Returns:
            The output Path.

        Raises:
            ExportError: If path is None or write fails.
        """
        if path is None:
            raise ExportError(
                "Output path is required for JSON export",
                export_format="json",
            )

        path = Path(path)
        rounded = self._round_floats(data, decimal_places)

        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rounded, fh, indent=2, default=str)

        logger.info("Exported {} rows to JSON: {}", len(rounded), path)
        return path

    def to_excel(
        self,
        data: list[dict[str, Any]],
        path: Path | None,
        *,
        sheet_name: str = "Sheet1",
        include_headers: bool = True,
    ) -> Path:
        """Export data to Excel (xlsx).

        Requires the optional openpyxl dependency.

        Args:
            data: List of row dicts.
            path: Output file path.
            sheet_name: Name of the worksheet.
            include_headers: Whether to write a header row.

        Returns:
            The output Path.

        Raises:
            ExportError: If openpyxl is not installed or write fails.
        """
        if not _HAS_OPENPYXL:
            raise ExportError(
                "openpyxl is required for Excel export. "
                "Install it with: pip install openpyxl",
                export_format="excel",
            )

        if path is None:
            raise ExportError(
                "Output path is required for Excel export",
                export_format="excel",
            )

        path = Path(path)

        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_name

        if data:
            fieldnames = list(data[0].keys())

            if include_headers:
                ws.append(fieldnames)

            for row in data:
                ws.append([row.get(col) for col in fieldnames])

        wb.save(str(path))

        logger.info("Exported {} rows to Excel: {}", len(data), path)
        return path

    def to_parquet(
        self,
        data: list[dict[str, Any]],
        path: Path | None,
    ) -> Path:
        """Export data to Parquet.

        Requires the optional pyarrow dependency.

        Args:
            data: List of row dicts.
            path: Output file path.

        Returns:
            The output Path.

        Raises:
            ExportError: If pyarrow is not installed or write fails.
        """
        if not _HAS_PYARROW:
            raise ExportError(
                "pyarrow is required for Parquet export. "
                "Install it with: pip install pyarrow",
                export_format="parquet",
            )

        if path is None:
            raise ExportError(
                "Output path is required for Parquet export",
                export_format="parquet",
            )

        path = Path(path)

        import pyarrow as pa
        import pyarrow.parquet as pq

        if not data:
            # Empty table
            table = pa.table({})
        else:
            # Build column arrays
            fieldnames = list(data[0].keys())
            columns = {col: [row.get(col) for row in data] for col in fieldnames}
            table = pa.table(columns)

        pq.write_table(table, str(path))

        logger.info("Exported {} rows to Parquet: {}", len(data), path)
        return path

    def to_dicts(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return data as a list of dicts (passthrough).

        Useful as a no-op export for pandas-ready consumption.

        Args:
            data: List of row dicts.

        Returns:
            A shallow copy of the input data.
        """
        return [dict(row) for row in data]

    @staticmethod
    def _round_floats(
        data: list[dict[str, Any]], decimal_places: int
    ) -> list[dict[str, Any]]:
        """Round all float values in the data to the given precision."""
        rounded: list[dict[str, Any]] = []
        for row in data:
            new_row: dict[str, Any] = {}
            for key, value in row.items():
                if isinstance(value, float):
                    new_row[key] = round(value, decimal_places)
                else:
                    new_row[key] = value
            rounded.append(new_row)
        return rounded
