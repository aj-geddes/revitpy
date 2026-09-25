"""Envelope heat loss, metered-energy regression and embodied carbon for a model.

Inside Revit (RevitPy add-in or Live Server)::

    from energy_analytics import run
    print(run(__revit__).to_text())

Outside Revit, ``run()`` uses the demo building (a RevitPy mock model).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from poc_common import connect, source_label
from poc_common.timeseries import hourly_weather, metered_energy

from revitpy.sustainability import BuildingCarbonSummary, CarbonBenchmark

from .analysis import (
    ChangePointFit,
    HourlyModelFit,
    daily_totals,
    envelope_ua,
    eui_kwh_m2,
    fit_change_point,
    fit_hourly_model,
    upgrade_candidates,
)
from .model_data import (
    embodied_carbon,
    envelope_table,
    flag_upgrade_candidates,
    gross_floor_area_m2,
)

__all__ = ["EnergyReport", "run"]


@dataclass
class EnergyReport:
    """Results of :func:`run`."""

    source: str
    floor_area_m2: float
    ua_by_level: pd.Series
    candidates: pd.DataFrame
    daily: pd.DataFrame
    change_point: ChangePointFit
    hourly_model: HourlyModelFit
    annual_kwh: float
    eui_kwh_m2: float
    carbon: BuildingCarbonSummary
    carbon_benchmark: CarbonBenchmark
    flagged: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def model_ua_w_per_k(self) -> float:
        return float(self.ua_by_level.sum())

    @property
    def metered_ua_w_per_k(self) -> float:
        """Heat loss coefficient implied by the metered data (kWh/K-day -> W/K)."""
        return self.change_point.slope_kwh_per_degc_day * 1000.0 / 24.0

    def to_text(self) -> str:
        cp = self.change_point
        lines = [
            f"Energy analytics - {self.source}",
            f"Gross floor area: {self.floor_area_m2:,.0f} m2",
            "",
            "Envelope heat loss (U x A) by level:",
            *(f"  {lvl:<10} {ua:8,.0f} W/K" for lvl, ua in self.ua_by_level.items()),
            f"  {'total':<10} {self.model_ua_w_per_k:8,.0f} W/K",
            "",
            f"Upgrade candidates ({len(self.candidates)}):",
            *(
                f"  {r.name:<28} U={r.u_value_w_m2k:.2f}  {r.heat_loss_w_per_k:6,.0f} W/K"
                for r in self.candidates.head(8).itertuples()
            ),
            "",
            "Change-point model on daily metered energy (ASHRAE Guideline 14, 3P):",
            f"  base load {cp.base_kwh_per_day:,.0f} kWh/day, balance point "
            f"{cp.balance_point_c:.1f} C, slope {cp.slope_kwh_per_degc_day:.1f} kWh/K-day",
            f"  R2 {cp.r2:.3f}, CV(RMSE) {cp.cv_rmse:.1%}",
            f"  heat loss implied by meter {self.metered_ua_w_per_k:,.0f} W/K "
            f"vs model {self.model_ua_w_per_k:,.0f} W/K",
            f"Hourly random forest (last 20% held out): R2 {self.hourly_model.r2:.3f}, "
            f"MAE {self.hourly_model.mae_kwh:.1f} kWh",
            f"Annual energy {self.annual_kwh:,.0f} kWh, EUI {self.eui_kwh_m2:.0f} kWh/m2",
            "",
            "Embodied carbon, walls + floors (A1-A3, generic ICE factors):",
            f"  {self.carbon.total_embodied_carbon_kgco2e / 1000:,.1f} tCO2e, "
            f"{self.carbon_benchmark.actual_kgco2e_per_m2:.0f} kgCO2e/m2 "
            f"({self.carbon_benchmark.rating} vs "
            f"{self.carbon_benchmark.target_kgco2e_per_m2:.0f} target, "
            f"{self.carbon_benchmark.benchmark_source})",
        ]
        if self.flagged:
            lines += ["", f"Wrote a note to Comments on {self.flagged} elements."]
        lines += [f"Note: {n}" for n in self.notes]
        return "\n".join(lines)


def run(
    app: Any | None = None,
    *,
    metered: pd.DataFrame | None = None,
    days: int = 365,
    wall_u_max: float = 1.0,
    window_u_max: float = 2.0,
    seed: int = 0,
    write: bool = True,
    html: Path | None = None,
) -> EnergyReport:
    """Run the energy analysis.

    Args:
        app: ``__revit__`` inside Revit; ``None`` uses the demo model.
        metered: Hourly meter data (DatetimeIndex; ``outdoor_temp_c``,
            ``occupied``, ``total_kwh``). Synthetic data is generated from the
            model's heat loss when omitted.
        days: Days of synthetic data to generate.
        wall_u_max: Wall U-value (W/m2K) above which a wall is a candidate.
        window_u_max: Window U-value above which a window is a candidate.
        seed: Seed for the synthetic data.
        write: Write notes to the candidates' ``Comments`` (one transaction).
        html: Write an interactive Plotly chart to this path.
    """
    api = connect(app)
    source = source_label(api, app)
    notes = []

    envelope = envelope_table(api)
    if envelope.empty:
        raise ValueError("No exterior walls or windows with 'U-Value (W/m2K)' found")
    ua = envelope_ua(envelope)
    floor_area = gross_floor_area_m2(api)

    if metered is None:
        weather = hourly_weather(days=days, seed=seed)
        metered = metered_energy(weather, float(ua.sum()), floor_area, seed=seed)
        notes.append("meter data is synthetic, generated from the model's U x A")

    daily = daily_totals(metered)
    change_point = fit_change_point(daily)
    hourly = fit_hourly_model(metered, seed=seed)
    annual = float(daily["total_kwh"].sum()) * 365.0 / max(len(daily), 1)
    carbon, benchmark = embodied_carbon(api, floor_area)
    candidates = pd.concat(
        [
            upgrade_candidates(envelope[envelope["kind"] == "wall"], wall_u_max),
            upgrade_candidates(envelope[envelope["kind"] == "window"], window_u_max),
        ]
    ).sort_values("heat_loss_w_per_k", ascending=False)

    flagged = flag_upgrade_candidates(api, candidates) if write else 0
    if html is not None:
        from .dashboard import write_dashboard

        write_dashboard(daily, change_point, envelope, Path(html))
        notes.append(f"chart written to {html}")

    return EnergyReport(
        source=source,
        floor_area_m2=floor_area,
        ua_by_level=ua,
        candidates=candidates,
        daily=daily,
        change_point=change_point,
        hourly_model=hourly,
        annual_kwh=annual,
        eui_kwh_m2=eui_kwh_m2(annual, floor_area),
        carbon=carbon,
        carbon_benchmark=benchmark,
        flagged=flagged,
        notes=notes,
    )
