"""Member checks, a 2D frame solve and modal periods from a model's steel frame.

Inside Revit (RevitPy add-in or Live Server)::

    from structural_analysis import run
    print(run(__revit__).to_text())

Outside Revit, ``run()`` uses the demo building. The checks are simplified
elastic checks for demonstration, not a design-code verification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from poc_common import connect, source_label

from revitpy.sustainability import CarbonCalculator, MaterialData

from .analysis import (
    E_STEEL,
    SECTIONS,
    check_beam,
    check_column,
    column_lateral_stiffness,
    natural_periods,
    solve_frame_2d,
)
from .model_data import floor_areas, levels, members, write_checks

__all__ = ["StructuralReport", "run"]

G = 9.81


@dataclass
class StructuralReport:
    """Results of :func:`run`."""

    source: str
    checks: pd.DataFrame
    periods_s: np.ndarray
    approx_period_s: float
    roof_drift_mm: float
    drift_limit_mm: float
    steel_tonnes: float
    steel_carbon_t: float
    written: int = 0
    notes: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        beams = self.checks[self.checks["kind"] == "beam"]
        columns = self.checks[self.checks["kind"] == "column"]
        failing = self.checks[~self.checks["passes"]]
        lines = [
            f"Structural analysis - {self.source}",
            f"{len(beams)} beams, {len(columns)} columns, "
            f"{self.steel_tonnes:.1f} t steel ({self.steel_carbon_t:.1f} tCO2e A1-A3)",
            "",
            f"Beam checks: max utilization {beams['utilization'].max():.2f}, "
            f"{int((~beams['passes']).sum())} failing",
            f"Column checks: max utilization {columns['utilization'].max():.2f}, "
            f"{int((~columns['passes']).sum())} failing",
            *(
                f"  FAILS {r.name:<18} {r.section:<7} utilization "
                f"{r.utilization:.2f} ({r.governing})"
                for r in failing.sort_values("utilization", ascending=False)
                .head(8)
                .itertuples()
            ),
            "",
            "Modal periods (shear-building model): "
            + ", ".join(f"{t:.2f} s" for t in self.periods_s),
            f"  ASCE 7 approximate period for comparison: {self.approx_period_s:.2f} s",
            f"Frame on gridline 1 under notional loads: roof drift "
            f"{self.roof_drift_mm:.1f} mm (limit h/400 = {self.drift_limit_mm:.0f} mm)",
        ]
        if self.written:
            lines += ["", f"Wrote check results to Comments on {self.written} members."]
        lines += [f"Note: {n}" for n in self.notes]
        return "\n".join(lines)


def _member_checks(
    frame: pd.DataFrame, level_order: list[str], dead_kpa: float, live_kpa: float
) -> pd.DataFrame:
    rows = []
    for m in frame.itertuples(index=False):
        section = SECTIONS.get(m.section)
        if section is None or m.length_m <= 0:
            continue
        if m.kind == "beam":
            c = check_beam(
                m.length_m,
                (dead_kpa + live_kpa) * m.tributary_width_m,
                section,
                w_deflection_kn_m=live_kpa * m.tributary_width_m,
            )
            governing = (
                "deflection"
                if c.deflection_utilization > c.bending_utilization
                else "bending"
            )
        else:
            # The column carries its tributary area on its own level and above.
            floors = len(level_order) - level_order.index(m.level)
            axial = (dead_kpa + live_kpa) * m.tributary_area_m2 * floors
            c = check_column(m.length_m, axial, section)
            governing = "buckling" if c.euler_kn < c.squash_kn else "yield"
        rows.append(
            {
                "element_id": m.element_id,
                "name": m.name,
                "kind": m.kind,
                "level": m.level,
                "section": m.section,
                "utilization": c.utilization,
                "passes": c.passes,
                "governing": governing,
            }
        )
    return pd.DataFrame(rows)


def _gridline_frame_drift(
    frame: pd.DataFrame,
    level_order: list[str],
    story_heights: list[float],
    story_weights_kn: list[float],
) -> tuple[float, float]:
    """Solve the frame on gridline 1 under 1% notional lateral loads.

    Bay count and width come from the model (columns named ``C-<x>1`` and the
    median beam span). Beam-column joints are assumed rigid.
    """
    beams = frame[frame["kind"] == "beam"]
    cols = frame[frame["kind"] == "column"]
    line1 = cols[cols["name"].str.match(r"C-[A-Z]1 ")]
    n_cols = max(int(line1.groupby("level").size().max()), 2)
    bay = float(beams["length_m"].median())
    beam_section = SECTIONS[beams["section"].mode().iloc[0]]

    xs = np.arange(n_cols) * bay
    ys = np.concatenate([[0.0], np.cumsum(story_heights)])
    nodes = np.array([(x, y) for y in ys for x in xs])
    idx = {(i, j): j * n_cols + i for j in range(len(ys)) for i in range(n_cols)}

    members, areas, inertias = [], [], []
    for j in range(1, len(ys)):
        level_cols = cols[cols["level"] == level_order[j - 1]]
        col_section = SECTIONS[level_cols["section"].mode().iloc[0]]
        for i in range(n_cols):
            members.append((idx[i, j - 1], idx[i, j]))
            areas.append(col_section.area_m2)
            inertias.append(col_section.ix_m4)
        for i in range(n_cols - 1):
            members.append((idx[i, j], idx[i + 1, j]))
            areas.append(beam_section.area_m2)
            inertias.append(beam_section.ix_m4)

    supports = {idx[i, 0]: (True, True, True) for i in range(n_cols)}
    # Share of the storey weight carried by this frame (one of three gridlines).
    loads = {
        idx[0, j]: (0.01 * story_weights_kn[j - 1] * 1000.0 / 3.0, 0.0, 0.0)
        for j in range(1, len(ys))
    }
    result = solve_frame_2d(nodes, members, E_STEEL, areas, inertias, supports, loads)
    roof_drift = float(result.displacements[idx[0, len(ys) - 1], 0]) * 1000.0
    return roof_drift, float(ys[-1]) * 1000.0 / 400.0


def run(
    app: Any | None = None,
    *,
    dead_kpa: float = 4.0,
    live_kpa: float = 2.5,
    write: bool = True,
) -> StructuralReport:
    """Check beams and columns and estimate lateral behaviour.

    Args:
        app: ``__revit__`` inside Revit; ``None`` uses the demo model.
        dead_kpa: Superimposed dead load incl. slab self-weight (kPa).
        live_kpa: Office live load (kPa).
        write: Write each member's utilization to ``Comments``.
    """
    api = connect(app)
    source = source_label(api, app)
    frame = members(api)
    if frame.empty:
        raise ValueError("No Structural Framing or Structural Columns found")
    unknown = sorted(set(frame["section"]) - set(SECTIONS))
    notes = (
        [f"sections not in the demo table were skipped: {unknown}"] if unknown else []
    )

    lvl = levels(api)
    level_order = [name for name in lvl["level"] if name in set(frame["level"])]
    checks = _member_checks(frame, level_order, dead_kpa, live_kpa)

    # Shear-building model: storey mass from floor area, stiffness from columns.
    areas = floor_areas(api)
    masses, stiffnesses, heights = [], [], []
    for name in level_order:
        cols = frame[(frame["kind"] == "column") & (frame["level"] == name)]
        height = float(cols["length_m"].median())
        heights.append(height)
        masses.append(areas.get(name, 0.0) * dead_kpa * 1000.0 / G)
        stiffnesses.append(
            sum(
                column_lateral_stiffness(SECTIONS[s], height)
                for s in cols["section"]
                if s in SECTIONS
            )
        )
    periods = natural_periods(masses, stiffnesses)
    approx = 0.0724 * sum(heights) ** 0.8  # ASCE 7 Ta, steel moment frame (SI)
    weights_kn = [m * G / 1000.0 for m in masses]
    drift, drift_limit = _gridline_frame_drift(frame, level_order, heights, weights_kn)

    mass_kg = sum(
        SECTIONS[m.section].mass_kg_m * m.length_m
        for m in frame.itertuples()
        if m.section in SECTIONS
    )
    calculator = CarbonCalculator()
    carbon = calculator.summarize(
        calculator.calculate(
            [MaterialData(name="Steel", category="Steel", mass_kg=mass_kg)]
        )
    )

    written = write_checks(api, checks) if write else 0
    return StructuralReport(
        source=source,
        checks=checks,
        periods_s=periods,
        approx_period_s=approx,
        roof_drift_mm=drift,
        drift_limit_mm=drift_limit,
        steel_tonnes=mass_kg / 1000.0,
        steel_carbon_t=carbon.total_embodied_carbon_kgco2e / 1000.0,
        written=written,
        notes=notes,
    )
