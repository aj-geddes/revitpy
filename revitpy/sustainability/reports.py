"""
Sustainability report generation.

This module provides report generation for sustainability assessments
in JSON, CSV, and HTML formats, as well as certification documentation
helpers for LEED, BREEAM, and other green building rating systems.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from loguru import logger

from .exceptions import ReportGenerationError
from .types import (
    BuildingCarbonSummary,
    CertificationSystem,
    ReportFormat,
)


class SustainabilityReporter:
    """Generates sustainability assessment reports in multiple formats."""

    def __init__(self) -> None:
        logger.debug("SustainabilityReporter initialized")

    def generate(
        self,
        summary: BuildingCarbonSummary,
        format: ReportFormat = ReportFormat.JSON,
        output_path: str | Path | None = None,
    ) -> str | Path:
        """Generate a sustainability report in the specified format.

        Args:
            summary: Building carbon summary data.
            format: Output format (JSON, CSV, or HTML).
            output_path: Optional file path. When provided the report is
                written to disk and the Path is returned. Otherwise the
                report content is returned as a string.

        Returns:
            Report content as a string, or the output Path.

        Raises:
            ReportGenerationError: If generation fails.
        """
        dispatch = {
            ReportFormat.JSON: self.to_json,
            ReportFormat.CSV: self.to_csv,
            ReportFormat.HTML: self.to_html,
        }

        generator = dispatch.get(format)
        if generator is None:
            raise ReportGenerationError(
                f"Unsupported report format: {format.value}",
                report_format=format.value,
            )

        return generator(summary, path=output_path)

    def to_json(
        self,
        summary: BuildingCarbonSummary,
        path: str | Path | None = None,
    ) -> str | Path:
        """Generate a JSON sustainability report.

        Args:
            summary: Building carbon summary data.
            path: Optional file path to write to.

        Returns:
            JSON string or Path to the written file.
        """
        data = {
            "report_type": "sustainability_carbon_assessment",
            "calculation_date": summary.calculation_date,
            "total_embodied_carbon_kgco2e": (summary.total_embodied_carbon_kgco2e),
            "material_count": summary.material_count,
            "by_material": summary.by_material,
            "by_system": summary.by_system,
            "by_level": summary.by_level,
            "by_lifecycle_stage": summary.by_lifecycle_stage,
        }

        content = json.dumps(data, indent=2)

        if path is not None:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            logger.info("JSON report written to {}", path)
            return path

        return content

    def to_csv(
        self,
        summary: BuildingCarbonSummary,
        path: str | Path | None = None,
    ) -> str | Path:
        """Generate a CSV sustainability report.

        The CSV contains rows for each material with its carbon contribution.

        Args:
            summary: Building carbon summary data.
            path: Optional file path to write to.

        Returns:
            CSV string or Path to the written file.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(
            [
                "Material",
                "Embodied Carbon (kgCO2e)",
                "Percentage",
            ]
        )

        total = summary.total_embodied_carbon_kgco2e
        for material, carbon in sorted(
            summary.by_material.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            pct = (carbon / total * 100) if total > 0 else 0.0
            writer.writerow([material, f"{carbon:.2f}", f"{pct:.1f}%"])

        writer.writerow([])
        writer.writerow(["Total", f"{total:.2f}", "100.0%"])
        writer.writerow([])
        writer.writerow(["Calculation Date", summary.calculation_date])
        writer.writerow(["Material Count", summary.material_count])

        content = output.getvalue()

        if path is not None:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            logger.info("CSV report written to {}", path)
            return path

        return content

    def to_html(
        self,
        summary: BuildingCarbonSummary,
        path: str | Path | None = None,
    ) -> str | Path:
        """Generate an HTML sustainability report.

        Uses Jinja2 if available, otherwise falls back to string
        formatting.

        Args:
            summary: Building carbon summary data.
            path: Optional file path to write to.

        Returns:
            HTML string or Path to the written file.

        Raises:
            ReportGenerationError: If HTML generation fails.
        """
        try:
            content = self._render_html(summary)
        except Exception as exc:
            raise ReportGenerationError(
                f"HTML report generation failed: {exc}",
                report_format="html",
                cause=exc,
            ) from exc

        if path is not None:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            logger.info("HTML report written to {}", path)
            return path

        return content

    def generate_certification_docs(
        self,
        summary: BuildingCarbonSummary,
        system: CertificationSystem,
    ) -> dict:
        """Generate certification documentation helpers.

        Produces a dictionary of documentation content suitable for
        submission with green building certification applications.

        Args:
            summary: Building carbon summary data.
            system: Target certification system.

        Returns:
            Dictionary with certification-specific documentation sections.
        """
        base = {
            "certification_system": system.value,
            "total_embodied_carbon_kgco2e": (summary.total_embodied_carbon_kgco2e),
            "material_count": summary.material_count,
            "calculation_date": summary.calculation_date,
            "by_material": summary.by_material,
        }

        if system == CertificationSystem.LEED:
            base["credits"] = {
                "MRc1": {
                    "name": "Building Life-Cycle Impact Reduction",
                    "description": (
                        "Whole-building life cycle assessment "
                        "demonstrating embodied carbon reduction"
                    ),
                    "applicable_materials": list(summary.by_material.keys()),
                    "potential_points": self._estimate_leed_points(summary),
                },
            }
        elif system == CertificationSystem.BREEAM:
            base["credits"] = {
                "Mat01": {
                    "name": "Life Cycle Impacts",
                    "description": (
                        "Environmental life cycle assessment of building materials"
                    ),
                    "applicable_materials": list(summary.by_material.keys()),
                    "potential_credits": self._estimate_breeam_credits(summary),
                },
            }
        elif system == CertificationSystem.DGNB:
            base["credits"] = {
                "ENV1.1": {
                    "name": "Life Cycle Assessment",
                    "description": "Building life cycle assessment",
                    "applicable_materials": list(summary.by_material.keys()),
                },
            }
        elif system == CertificationSystem.GREENSTAR:
            base["credits"] = {
                "Materials": {
                    "name": "Life Cycle Impacts",
                    "description": ("Comparative life cycle assessment"),
                    "applicable_materials": list(summary.by_material.keys()),
                },
            }
        else:
            base["credits"] = {}

        logger.info(
            "Generated {} certification docs ({} materials)",
            system.value,
            summary.material_count,
        )
        return base

    @staticmethod
    def _estimate_leed_points(summary: BuildingCarbonSummary) -> int:
        """Estimate potential LEED MRc1 points based on carbon data."""
        if summary.material_count >= 5:
            return 3
        if summary.material_count >= 3:
            return 2
        return 1

    @staticmethod
    def _estimate_breeam_credits(summary: BuildingCarbonSummary) -> int:
        """Estimate potential BREEAM Mat01 credits based on carbon data."""
        if summary.material_count >= 5:
            return 6
        if summary.material_count >= 3:
            return 4
        return 2

    @staticmethod
    def _render_html(summary: BuildingCarbonSummary) -> str:
        """Render HTML report, using Jinja2 if available."""
        try:
            from jinja2 import Template

            template = Template(_HTML_TEMPLATE)
            return template.render(
                summary=summary,
                total=summary.total_embodied_carbon_kgco2e,
                materials=sorted(
                    summary.by_material.items(),
                    key=lambda x: x[1],
                    reverse=True,
                ),
            )
        except ImportError:
            return _render_html_fallback(summary)


def _render_html_fallback(summary: BuildingCarbonSummary) -> str:
    """Render HTML report without Jinja2."""
    total = summary.total_embodied_carbon_kgco2e
    rows = ""
    for material, carbon in sorted(
        summary.by_material.items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        pct = (carbon / total * 100) if total > 0 else 0.0
        rows += (
            f"<tr><td>{material}</td><td>{carbon:.2f}</td><td>{pct:.1f}%</td></tr>\n"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Sustainability Report</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 2em; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background-color: #2e7d32; color: white; }}
tr:nth-child(even) {{ background-color: #f2f2f2; }}
h1 {{ color: #2e7d32; }}
.summary {{ margin: 1em 0; }}
</style>
</head>
<body>
<h1>Sustainability Carbon Assessment</h1>
<div class="summary">
<p><strong>Total Embodied Carbon:</strong> {total:.2f} kgCO2e</p>
<p><strong>Materials Assessed:</strong> {summary.material_count}</p>
<p><strong>Date:</strong> {summary.calculation_date}</p>
</div>
<h2>Carbon by Material</h2>
<table>
<tr><th>Material</th><th>kgCO2e</th><th>%</th></tr>
{rows}
<tr><td><strong>Total</strong></td>
<td><strong>{total:.2f}</strong></td>
<td><strong>100.0%</strong></td></tr>
</table>
</body>
</html>"""


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Sustainability Report</title>
<style>
body { font-family: Arial, sans-serif; margin: 2em; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
th { background-color: #2e7d32; color: white; }
tr:nth-child(even) { background-color: #f2f2f2; }
h1 { color: #2e7d32; }
.summary { margin: 1em 0; }
</style>
</head>
<body>
<h1>Sustainability Carbon Assessment</h1>
<div class="summary">
<p><strong>Total Embodied Carbon:</strong> {{ total|round(2) }} kgCO2e</p>
<p><strong>Materials Assessed:</strong> {{ summary.material_count }}</p>
<p><strong>Date:</strong> {{ summary.calculation_date }}</p>
</div>
<h2>Carbon by Material</h2>
<table>
<tr><th>Material</th><th>kgCO2e</th><th>%</th></tr>
{% for material, carbon in materials %}
{% set pct = (carbon / total * 100) if total > 0 else 0.0 %}
<tr><td>{{ material }}</td>
<td>{{ "%.2f"|format(carbon) }}</td>
<td>{{ "%.1f"|format(pct) }}%</td></tr>
{% endfor %}
<tr><td><strong>Total</strong></td>
<td><strong>{{ "%.2f"|format(total) }}</strong></td>
<td><strong>100.0%</strong></td></tr>
</table>
</body>
</html>"""
