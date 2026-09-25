"""space_planning.analysis against hand calculations."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from space_planning import analysis

WEEK = pd.date_range("2025-03-03", periods=168, freq="h")  # starts on a Monday
BUSINESS = (WEEK.dayofweek < 5) & (WEEK.hour >= 8) & (WEEK.hour < 18)


def occupancy(counts: dict[int, np.ndarray]) -> pd.DataFrame:
    return pd.concat(
        [
            pd.DataFrame({"timestamp": WEEK, "room_id": room, "occupants": values})
            for room, values in counts.items()
        ],
        ignore_index=True,
    )


ROOMS = pd.DataFrame(
    {"room_id": [1, 2, 3], "area_m2": [100.0, 80.0, 20.0], "capacity": [10, 4, 0]}
)


def test_utilization_features():
    occ = occupancy({1: np.where(BUSINESS, 5, 0), 2: np.zeros(168, int)})
    features = analysis.utilization_features(ROOMS, occ)
    assert list(features.index) == [1, 2]  # room 3 (capacity 0) dropped
    assert features.loc[1, "mean_utilization"] == pytest.approx(0.5)
    assert features.loc[1, "peak_utilization"] == pytest.approx(0.5)
    assert features.loc[1, "occupied_hours_share"] == pytest.approx(1.0)
    assert features.loc[2, "mean_utilization"] == 0.0
    assert features.loc[2, "occupied_hours_share"] == 0.0
    assert features["area_per_seat_m2"].tolist() == pytest.approx([10.0, 20.0])


def test_nights_and_weekends_are_ignored():
    base = np.where(BUSINESS, 5, 0)
    noisy = base.copy()
    noisy[(WEEK.hour == 3) | (WEEK.dayofweek == 5)] = 10
    a = analysis.utilization_features(ROOMS, occupancy({1: base}))
    b = analysis.utilization_features(ROOMS, occupancy({1: noisy}))
    pd.testing.assert_frame_equal(a, b)


def test_cluster_rooms_names_groups_by_utilization():
    rng = np.random.default_rng(0)
    levels = [0.1] * 3 + [0.5] * 3 + [0.9] * 3
    features = pd.DataFrame(
        {
            "mean_utilization": [v + rng.uniform(-0.02, 0.02) for v in levels],
            "peak_utilization": [min(v + 0.1, 1.0) for v in levels],
            "occupied_hours_share": [v + rng.uniform(-0.03, 0.03) for v in levels],
        },
        index=pd.Index(range(9), name="room_id"),
    )
    result = analysis.cluster_rooms(features)
    assert result.labels.tolist() == ["underused"] * 3 + ["typical"] * 3 + ["busy"] * 3
    assert result.silhouette > 0.5
    assert list(result.centers.index) == ["underused", "typical", "busy"]
    assert result.centers["mean_utilization"].is_monotonic_increasing


def test_cluster_rooms_needs_enough_rows():
    features = pd.DataFrame(
        {
            "mean_utilization": [0.1, 0.5],
            "peak_utilization": [0.2, 0.6],
            "occupied_hours_share": [0.1, 0.5],
        }
    )
    with pytest.raises(ValueError):
        analysis.cluster_rooms(features, n_clusters=3)


def test_forecast_on_a_weekly_pattern():
    index = pd.date_range("2025-03-03", periods=4 * 168, freq="h")
    series = pd.Series(
        np.where((index.dayofweek < 5) & (index.hour >= 8) & (index.hour < 18), 5, 0),
        index=index,
    )
    result = analysis.forecast_room_occupancy(series)
    assert result.mae_naive == pytest.approx(0.0)
    assert result.mae_model <= result.mae_naive + 0.05
    assert len(result.predictions) == 168
    assert (result.predictions >= 0).all()


def test_forecast_needs_two_weeks():
    series = pd.Series(0.0, index=pd.date_range("2025-03-03", periods=240, freq="h"))
    with pytest.raises(ValueError):
        analysis.forecast_room_occupancy(series)


def test_assign_teams_minimises_spare_seats():
    teams = pd.DataFrame({"team": ["A", "B"], "headcount": [8, 3]})
    rooms = pd.DataFrame({"room_id": [1, 2, 3], "capacity": [4, 10, 9]})
    result = analysis.assign_teams(teams, rooms)
    assert result["room_id"].tolist() == [3, 1]
    assert result["spare_seats"].sum() == 2


def test_assign_teams_rejects_impossible_requests():
    rooms = pd.DataFrame({"room_id": [1, 2], "capacity": [4, 10]})
    with pytest.raises(ValueError, match="Big"):
        analysis.assign_teams(
            pd.DataFrame({"team": ["Big", "B"], "headcount": [50, 3]}), rooms
        )
    with pytest.raises(ValueError):
        analysis.assign_teams(
            pd.DataFrame({"team": ["A", "B", "C"], "headcount": [1, 1, 1]}), rooms
        )
