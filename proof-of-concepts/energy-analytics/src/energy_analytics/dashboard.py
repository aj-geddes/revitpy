"""Interactive Plotly chart of the energy analysis (optional output)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .analysis import ChangePointFit


def build_figure(
    daily: pd.DataFrame, fit: ChangePointFit, envelope: pd.DataFrame
) -> go.Figure:
    """Daily energy vs outdoor temperature with the fitted change-point line,
    next to heat loss (U x A) by element."""
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Daily energy vs outdoor temperature", "Heat loss by element"),
    )
    fig.add_trace(
        go.Scatter(
            x=daily["outdoor_temp_c"],
            y=daily["total_kwh"],
            mode="markers",
            name="metered days",
            marker={"size": 5, "opacity": 0.6},
        ),
        row=1,
        col=1,
    )
    temps = np.linspace(daily["outdoor_temp_c"].min(), daily["outdoor_temp_c"].max())
    fig.add_trace(
        go.Scatter(x=temps, y=fit.predict(temps), mode="lines", name="3P model"),
        row=1,
        col=1,
    )
    loss = (envelope["u_value_w_m2k"] * envelope["area_m2"]).rename("heat_loss")
    ranked = envelope.assign(heat_loss=loss).sort_values("heat_loss")
    fig.add_trace(
        go.Bar(
            x=ranked["heat_loss"],
            y=ranked["name"],
            orientation="h",
            name="U x A (W/K)",
        ),
        row=1,
        col=2,
    )
    fig.update_xaxes(title_text="Outdoor temperature (C)", row=1, col=1)
    fig.update_yaxes(title_text="kWh/day", row=1, col=1)
    fig.update_xaxes(title_text="W/K", row=1, col=2)
    fig.update_layout(height=600, showlegend=True)
    return fig


def write_dashboard(
    daily: pd.DataFrame, fit: ChangePointFit, envelope: pd.DataFrame, path: Path
) -> Path:
    """Write the chart as a self-contained HTML file (Plotly JS from a CDN)."""
    build_figure(daily, fit, envelope).write_html(path, include_plotlyjs="cdn")
    return path
