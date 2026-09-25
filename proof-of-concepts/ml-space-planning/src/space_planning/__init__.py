"""Room utilization analytics: clustering, forecasting and team-to-room assignment.

Inside Revit (RevitPy add-in or Live Server)::

    from space_planning import run
    print(run(__revit__, occupancy=my_badge_or_sensor_counts).to_text())

Outside Revit, ``run()`` uses the demo building and synthetic occupancy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from poc_common import connect, room_profiles, source_label
from poc_common.timeseries import room_occupancy

from .analysis import (
    ClusterResult,
    ForecastResult,
    assign_teams,
    cluster_rooms,
    forecast_room_occupancy,
    utilization_features,
)
from .model_data import room_table, write_utilization

__all__ = ["DEMO_TEAMS", "SpacePlanningReport", "run"]

# Teams looking for a regular project room (name, headcount).
DEMO_TEAMS = pd.DataFrame(
    {
        "team": ["Facades", "Structures", "BIM", "Workshop", "Sprint"],
        "headcount": [8, 14, 5, 25, 9],
    }
)


@dataclass
class SpacePlanningReport:
    """Results of :func:`run`."""

    source: str
    rooms: pd.DataFrame
    features: pd.DataFrame
    clusters: ClusterResult
    forecast_room: str
    forecast: ForecastResult
    assignment: pd.DataFrame
    written: int = 0
    notes: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        names = self.rooms.set_index("room_id")["name"]
        counts = self.clusters.labels.value_counts()
        underused = self.clusters.labels[self.clusters.labels == "underused"].index
        lines = [
            f"Space planning - {self.source}",
            f"{len(self.rooms)} rooms, {self.rooms['area_m2'].sum():,.0f} m2, "
            f"{self.rooms['capacity'].sum()} seats",
            "",
            f"Room clusters (k-means, silhouette {self.clusters.silhouette:.2f}):",
            *(
                f"  {label:<10} {counts.get(label, 0):3d} rooms  "
                f"mean {c.mean_utilization:.0%}  peak {c.peak_utilization:.0%}"
                for label, c in self.clusters.centers.iterrows()
            ),
            "Underused rooms: "
            + (", ".join(names[i] for i in underused[:8]) or "none"),
            "",
            f"Occupancy forecast for {self.forecast_room} (last 7 days held out):",
            f"  gradient boosting MAE {self.forecast.mae_model:.2f} people, "
            f"same-hour-last-week MAE {self.forecast.mae_naive:.2f}",
            "",
            "Team-to-room assignment (minimum spare seats):",
            *(
                f"  {r.team:<11} {r.headcount:3d} -> {names[r.room_id]:<22} "
                f"({r.capacity} seats, {r.spare_seats} spare)"
                for r in self.assignment.itertuples()
            ),
        ]
        if self.written:
            lines += ["", f"Wrote utilization to Comments on {self.written} rooms."]
        lines += [f"Note: {n}" for n in self.notes]
        return "\n".join(lines)


def run(
    app: Any | None = None,
    *,
    occupancy: pd.DataFrame | None = None,
    teams: pd.DataFrame | None = None,
    days: int = 28,
    seed: int = 0,
    write: bool = True,
) -> SpacePlanningReport:
    """Run the space-planning analysis.

    Args:
        app: ``__revit__`` inside Revit; ``None`` uses the demo model.
        occupancy: Hourly counts, long format (``timestamp``, ``room_id``,
            ``occupants``). Synthetic when omitted.
        teams: ``team`` / ``headcount`` table; defaults to :data:`DEMO_TEAMS`.
        days: Days of synthetic occupancy.
        seed: Seed for synthetic data and models.
        write: Write each room's utilization class to ``Comments``.
    """
    api = connect(app)
    source = source_label(api, app)
    notes = []
    rooms = room_table(api)
    if rooms.empty:
        raise ValueError("The model has no rooms")

    if occupancy is None:
        profiles = room_profiles()
        rooms_with_profile = rooms.assign(
            profile=rooms["base_name"].map(profiles).fillna("typical")
        )
        occupancy = room_occupancy(rooms_with_profile, days=days, seed=seed)
        notes.append("occupancy counts are synthetic")

    features = utilization_features(rooms, occupancy)
    clusters = cluster_rooms(features, seed=seed)

    busiest = int(features["mean_utilization"].idxmax())
    series = (
        occupancy[occupancy["room_id"] == busiest]
        .set_index("timestamp")["occupants"]
        .sort_index()
    )
    forecast = forecast_room_occupancy(series, seed=seed)

    candidates = rooms[rooms["department"] == "Shared"]
    assignment = assign_teams(
        DEMO_TEAMS if teams is None else teams, candidates[["room_id", "capacity"]]
    )

    written = write_utilization(api, features, clusters.labels) if write else 0
    return SpacePlanningReport(
        source=source,
        rooms=rooms,
        features=features,
        clusters=clusters,
        forecast_room=str(rooms.set_index("room_id").loc[busiest, "name"]),
        forecast=forecast,
        assignment=assignment,
        written=written,
        notes=notes,
    )
