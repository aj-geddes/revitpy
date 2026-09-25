"""Room utilization features, clustering, forecasting and team assignment.

Pure functions on pandas DataFrames; nothing here touches Revit.

The original concept used an LSTM (TensorFlow) for occupancy prediction. For
hourly room counts a gradient-boosted tree on hour/weekday features is enough
and is compared against a same-hour-last-week baseline, so scikit-learn is
used instead.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import KMeans
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, silhouette_score
from sklearn.preprocessing import StandardScaler


def utilization_features(rooms: pd.DataFrame, occupancy: pd.DataFrame) -> pd.DataFrame:
    """
    Compute room utilization features from rooms and occupancy data.

    Parameters
    ----------
    rooms : pd.DataFrame
        Room metadata with columns: room_id (int), area_m2 (float), capacity (int).
    occupancy : pd.DataFrame
        Long-format occupancy data with columns: timestamp (datetime64),
        room_id (int), occupants (int).

    Returns
    -------
    pd.DataFrame
        Features indexed by room_id with columns:
        ["mean_utilization", "peak_utilization", "occupied_hours_share", "area_per_seat_m2"].
    """
    # Drop rooms with capacity <= 0
    rooms = rooms[rooms["capacity"] > 0].copy()

    # Filter occupancy to business hours (Mon-Fri, 8 <= hour < 18)
    occupancy = occupancy.copy()
    occupancy["timestamp"] = pd.to_datetime(occupancy["timestamp"])
    occupancy["hour"] = occupancy["timestamp"].dt.hour
    occupancy["weekday"] = occupancy["timestamp"].dt.weekday

    business_mask = (
        (occupancy["weekday"] < 5)  # Mon-Fri (0-4)
        & (occupancy["hour"] >= 8)
        & (occupancy["hour"] < 18)
    )
    business_occupancy = occupancy[business_mask].copy()

    # Compute utilization ratio
    business_occupancy["utilization"] = business_occupancy[
        "occupants"
    ] / business_occupancy["room_id"].map(rooms.set_index("room_id")["capacity"])

    # Aggregate per room
    room_ids = rooms["room_id"].values
    result_data = []

    for room_id in room_ids:
        room_util = business_occupancy[business_occupancy["room_id"] == room_id]
        capacity = rooms.loc[rooms["room_id"] == room_id, "capacity"].iloc[0]
        area = rooms.loc[rooms["room_id"] == room_id, "area_m2"].iloc[0]

        if len(room_util) == 0:
            # No business-hour rows
            result_data.append(
                {
                    "room_id": room_id,
                    "mean_utilization": 0.0,
                    "peak_utilization": 0.0,
                    "occupied_hours_share": 0.0,
                    "area_per_seat_m2": area / capacity,
                }
            )
        else:
            util_vals = room_util["utilization"].values
            mean_util = np.mean(util_vals)
            peak_util = np.percentile(util_vals, 95)
            occupied_hours_share = np.mean(room_util["occupants"] > 0)
            area_per_seat = area / capacity

            result_data.append(
                {
                    "room_id": room_id,
                    "mean_utilization": mean_util,
                    "peak_utilization": peak_util,
                    "occupied_hours_share": occupied_hours_share,
                    "area_per_seat_m2": area_per_seat,
                }
            )

    result_df = pd.DataFrame(result_data).set_index("room_id")
    result_df.index.name = "room_id"
    return result_df.sort_index()


@dataclass
class ClusterResult:
    """Result of room clustering."""

    labels: pd.Series
    silhouette: float
    centers: pd.DataFrame


def cluster_rooms(
    features: pd.DataFrame, n_clusters: int = 3, seed: int = 0
) -> ClusterResult:
    """
    Cluster rooms based on utilization features.

    Parameters
    ----------
    features : pd.DataFrame
        Features with columns ["mean_utilization", "peak_utilization", "occupied_hours_share"].
    n_clusters : int, optional
        Number of clusters (default: 3).
    seed : int, optional
        Random seed (default: 0).

    Returns
    -------
    ClusterResult
        Clustering result with labels, silhouette score, and cluster centers.

    Raises
    ------
    ValueError
        If number of features < n_clusters.
    """
    # Validate input
    if len(features) < n_clusters:
        raise ValueError(
            f"Number of features ({len(features)}) must be >= n_clusters ({n_clusters})"
        )

    # Select and scale features
    feature_cols = ["mean_utilization", "peak_utilization", "occupied_hours_share"]
    X = features[feature_cols].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Perform clustering
    kmeans = KMeans(n_clusters=n_clusters, n_init=10, random_state=seed)
    labels = kmeans.fit_predict(X_scaled)

    # Compute silhouette score
    unique_labels = np.unique(labels)
    if 1 < len(unique_labels) < len(features):
        silhouette = silhouette_score(X_scaled, labels)
    else:
        silhouette = 0.0

    # Compute cluster centers in original units
    centers_data = []
    for label in range(n_clusters):
        mask = labels == label
        if np.any(mask):
            center = X[mask].mean(axis=0)
        else:
            center = np.zeros(len(feature_cols))
        centers_data.append(center)

    centers_df = pd.DataFrame(
        centers_data,
        columns=feature_cols,
        index=[f"cluster_{i}" for i in range(n_clusters)],
    )

    # Name clusters by ascending mean_utilization
    if n_clusters == 3:
        name_map = ["underused", "typical", "busy"]
    else:
        name_map = [f"cluster_{i}" for i in range(n_clusters)]

    # Sort cluster centers by mean_utilization and assign names
    mean_util_order = centers_df["mean_utilization"].argsort().values
    new_names = [name_map[i] for i in range(n_clusters)]
    new_index = [None] * n_clusters
    for rank, orig_idx in enumerate(mean_util_order):
        new_index[orig_idx] = new_names[rank]

    centers_df.index = new_index

    # Create labels Series with room_id index
    names = np.array(new_index, dtype=object)
    labels_series = pd.Series(names[labels], index=features.index, name="cluster")

    return ClusterResult(
        labels=labels_series,
        silhouette=float(silhouette),
        centers=centers_df.sort_values("mean_utilization"),
    )


@dataclass
class ForecastResult:
    """Result of occupancy forecasting."""

    mae_model: float
    mae_naive: float
    predictions: pd.Series


def forecast_room_occupancy(
    series: pd.Series, test_days: int = 7, seed: int = 0
) -> ForecastResult:
    """
    Forecast room occupancy using a gradient boosting model vs. naive baseline.

    Parameters
    ----------
    series : pd.Series
        Hourly occupants with DatetimeIndex.
    test_days : int, optional
        Number of days for testing (default: 7).
    seed : int, optional
        Random seed (default: 0).

    Returns
    -------
    ForecastResult
        Forecast results with MAE for model and naive baseline, and predictions.

    Raises
    ------
    ValueError
        If series length is insufficient.
    """
    # Validate input
    min_length = (test_days + 7) * 24
    if len(series) < min_length:
        raise ValueError(
            f"Series length ({len(series)}) must be >= {(test_days + 7) * 24}"
        )

    # Create features
    idx = series.index
    features = pd.DataFrame({"hour": idx.hour, "weekday": idx.weekday}, index=idx)

    # Split train/test
    test_size = test_days * 24
    train_end_idx = len(series) - test_size

    X_train = features.iloc[:train_end_idx]
    y_train = series.iloc[:train_end_idx]
    X_test = features.iloc[train_end_idx:]
    y_test = series.iloc[train_end_idx:]

    # Fit model
    model = HistGradientBoostingRegressor(random_state=seed)
    model.fit(X_train, y_train)

    # Predictions
    y_pred = model.predict(X_test)
    y_pred = np.clip(y_pred, 0, None)
    predictions = pd.Series(y_pred, index=X_test.index, name="prediction")

    # Naive baseline: shift by 168 hours (1 week)
    y_naive = series.shift(168).iloc[train_end_idx:]

    # Compute MAE
    mae_model = mean_absolute_error(y_test, predictions)
    mae_naive = mean_absolute_error(y_test, y_naive)

    return ForecastResult(
        mae_model=float(mae_model), mae_naive=float(mae_naive), predictions=predictions
    )


def assign_teams(teams: pd.DataFrame, rooms: pd.DataFrame) -> pd.DataFrame:
    """
    Assign teams to rooms minimizing total spare seats.

    Parameters
    ----------
    teams : pd.DataFrame
        Team data with columns: team (str), headcount (int).
    rooms : pd.DataFrame
        Room data with columns: room_id (int), capacity (int).

    Returns
    -------
    pd.DataFrame
        Assignment results with columns: team, headcount, room_id, capacity, spare_seats.

    Raises
    ------
    ValueError
        If more teams than rooms, or if any assignment is infeasible.
    """
    # Validate input
    if len(teams) > len(rooms):
        raise ValueError("Number of teams cannot exceed number of rooms")

    # Build cost matrix (teams x rooms)
    headcounts = teams["headcount"].values
    capacities = rooms["capacity"].values

    cost_matrix = np.full((len(teams), len(rooms)), 1e6)
    for i, hc in enumerate(headcounts):
        for j, cap in enumerate(capacities):
            if cap >= hc:
                cost_matrix[i, j] = cap - hc  # spare seats

    # Solve assignment problem
    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    # Check for infeasible assignments
    for i, j in zip(row_ind, col_ind, strict=True):
        if cost_matrix[i, j] >= 1e6:
            raise ValueError(
                f"Cannot assign team '{teams.iloc[i]['team']}' to any room"
            )

    # Build result DataFrame
    assignments = []
    for i, j in zip(row_ind, col_ind, strict=True):
        team_name = str(teams.iloc[i]["team"])
        headcount = int(teams.iloc[i]["headcount"])
        room_id = int(rooms.iloc[j]["room_id"])
        capacity = int(rooms.iloc[j]["capacity"])
        spare_seats = capacity - headcount
        assignments.append(
            {
                "team": team_name,
                "headcount": headcount,
                "room_id": room_id,
                "capacity": capacity,
                "spare_seats": spare_seats,
            }
        )

    result_df = pd.DataFrame(assignments)
    result_df = result_df.sort_values("team").reset_index(drop=True)
    return result_df
