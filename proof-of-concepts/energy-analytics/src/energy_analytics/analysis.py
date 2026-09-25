"""Envelope heat loss, change-point regression and an hourly ML model.

Pure functions on pandas DataFrames: nothing here touches Revit, so it can be
tested and reused on any data source.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score


def envelope_ua(envelope: pd.DataFrame) -> pd.Series:
    """
    Compute UA (W/K) for each level as sum(u_value * area).

    Parameters
    ----------
    envelope : pd.DataFrame
        With columns: level (str), area_m2 (float), u_value_w_m2k (float).

    Returns
    -------
    pd.Series
        UA per level, indexed by level, sorted, named "ua_w_per_k".
    """
    ua = (envelope["u_value_w_m2k"] * envelope["area_m2"]).groupby(envelope["level"])
    return ua.sum().sort_index().rename("ua_w_per_k")


def upgrade_candidates(envelope: pd.DataFrame, u_threshold: float) -> pd.DataFrame:
    """
    Return rows with u_value_w_m2k > u_threshold, with added heat_loss_w_per_k column.

    Parameters
    ----------
    envelope : pd.DataFrame
        Input envelope data (not modified).
    u_threshold : float
        Threshold for u_value_w_m2k.

    Returns
    -------
    pd.DataFrame
        Filtered rows with added heat_loss_w_per_k = u_value_w_m2k * area_m2,
        sorted descending by heat_loss_w_per_k.
    """
    df = envelope.copy()
    df["heat_loss_w_per_k"] = df["u_value_w_m2k"] * df["area_m2"]
    mask = df["u_value_w_m2k"] > u_threshold
    result = df.loc[mask].copy()
    return result.sort_values("heat_loss_w_per_k", ascending=False)


def daily_totals(metered: pd.DataFrame) -> pd.DataFrame:
    """
    Resample hourly metered data to daily totals/means.

    Parameters
    ----------
    metered : pd.DataFrame
        Hourly data with DatetimeIndex and columns: outdoor_temp_c, total_kwh,
        optionally heating_kwh, electricity_kwh.

    Returns
    -------
    pd.DataFrame
        Daily resampled data: outdoor_temp_c (mean), kwh columns (sum).
    """
    resample_rules = {"outdoor_temp_c": "mean"}
    for col in ["total_kwh", "heating_kwh", "electricity_kwh"]:
        if col in metered.columns:
            resample_rules[col] = "sum"
    return metered.resample("D").agg(resample_rules)


@dataclass(frozen=True)
class ChangePointFit:
    """Result of fitting a 3-parameter heating change-point model."""

    base_kwh_per_day: float
    slope_kwh_per_degc_day: float
    balance_point_c: float
    r2: float
    cv_rmse: float

    def predict(self, temp_c: np.ndarray | pd.Series | float) -> np.ndarray:
        """
        Predict energy use (kWh/day) given outdoor temperature.

        Parameters
        ----------
        temp_c : np.ndarray | pd.Series | float
            Outdoor temperature(s) in °C.

        Returns
        -------
        np.ndarray
            Predicted energy use (kWh/day).
        """
        temp = np.asarray(temp_c)
        return self.base_kwh_per_day + self.slope_kwh_per_degc_day * np.maximum(
            0, self.balance_point_c - temp
        )


def fit_change_point(
    daily: pd.DataFrame, temp_col: str = "outdoor_temp_c", energy_col: str = "total_kwh"
) -> ChangePointFit:
    """
    Fit ASHRAE Guideline 14 style 3-parameter heating change-point model.

    Model: E = base + slope * max(0, Tb - T)

    Parameters
    ----------
    daily : pd.DataFrame
        Daily data with temp_col and energy_col.
    temp_col : str, optional
        Column name for outdoor temperature (default: "outdoor_temp_c").
    energy_col : str, optional
        Column name for energy use (default: "total_kwh").

    Returns
    -------
    ChangePointFit
        Fitted model parameters and statistics.

    Raises
    ------
    ValueError
        If fewer than 10 valid rows after dropping NaNs.
    """
    # Drop NaN rows
    df = daily[[temp_col, energy_col]].dropna()
    if len(df) < 10:
        raise ValueError("At least 10 valid rows required for change-point fitting")

    T = df[temp_col].values
    E = df[energy_col].values

    # Grid search over balance points
    T_min, T_max = T.min(), T.max()
    balance_points = np.linspace(T_min, T_max, 81)
    best_sse = np.inf
    best_params = (0.0, 0.0, T_min)

    for Tb in balance_points:
        x = np.maximum(0, Tb - T)
        X = np.column_stack([np.ones_like(x), x])
        coeffs, _, _, _ = np.linalg.lstsq(X, E, rcond=None)
        base, slope = coeffs
        if slope < 0:
            continue
        sse = float(np.sum((E - X @ coeffs) ** 2))
        if sse < best_sse:
            best_sse = sse
            best_params = (max(float(base), 0.0), float(slope), float(Tb))

    # Refine with curve_fit
    def model_func(T, base, slope, Tb):
        return base + slope * np.maximum(0, Tb - T)

    try:
        popt, _ = curve_fit(
            model_func,
            T,
            E,
            p0=best_params,
            bounds=([0, 0, T_min], [np.inf, np.inf, T_max]),
            maxfev=10000,
        )
        base, slope, Tb = popt
        pred = model_func(T, base, slope, Tb)
        sse = np.sum((E - pred) ** 2)
    except (RuntimeError, ValueError):
        # Keep grid result
        base, slope, Tb = best_params
        pred = base + slope * np.maximum(0, Tb - T)
        sse = best_sse

    # Compute r2 and cv_rmse
    sst = np.sum((E - np.mean(E)) ** 2)
    r2 = 1 - sse / sst if sst > 0 else 0.0
    rmse = np.sqrt(sse / len(E))
    cv_rmse = rmse / np.mean(E) if np.mean(E) > 0 else 0.0

    return ChangePointFit(
        base_kwh_per_day=float(base),
        slope_kwh_per_degc_day=float(slope),
        balance_point_c=float(Tb),
        r2=float(r2),
        cv_rmse=float(cv_rmse),
    )


@dataclass
class HourlyModelFit:
    """Result of fitting an hourly energy model."""

    r2: float
    mae_kwh: float
    feature_importance: dict[str, float]
    model: RandomForestRegressor


def fit_hourly_model(
    metered: pd.DataFrame, seed: int = 0, test_fraction: float = 0.2
) -> HourlyModelFit:
    """
    Fit a RandomForest model for hourly energy prediction.

    Parameters
    ----------
    metered : pd.DataFrame
        Hourly data with DatetimeIndex and columns: outdoor_temp_c, occupied, total_kwh.
    seed : int, optional
        Random seed for reproducibility (default: 0).
    test_fraction : float, optional
        Fraction of data for testing (default: 0.2).

    Returns
    -------
    HourlyModelFit
        Model fit results.
    """
    # Create features
    df = metered.copy()
    df["hour"] = df.index.hour
    df["weekday"] = df.index.dayofweek
    df["occupied"] = df["occupied"].astype(int)

    feature_cols = ["outdoor_temp_c", "hour", "weekday", "occupied"]
    X = df[feature_cols].values
    y = df["total_kwh"].values

    # Chronological split
    n = len(df)
    n_test = max(1, int(n * test_fraction))
    X_train, X_test = X[:-n_test], X[-n_test:]
    y_train, y_test = y[:-n_test], y[-n_test:]

    # Fit model
    model = RandomForestRegressor(
        n_estimators=60, max_depth=12, random_state=seed, n_jobs=1
    )
    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)

    # Feature importance
    importance = {
        name: float(value)
        for name, value in zip(feature_cols, model.feature_importances_, strict=True)
    }

    return HourlyModelFit(
        r2=float(r2), mae_kwh=float(mae), feature_importance=importance, model=model
    )


def eui_kwh_m2(annual_kwh: float, floor_area_m2: float) -> float:
    """
    Compute Energy Use Intensity (EUI) in kWh/m²/year.

    Parameters
    ----------
    annual_kwh : float
        Annual energy use in kWh.
    floor_area_m2 : float
        Floor area in m².

    Returns
    -------
    float
        EUI in kWh/m²/year.

    Raises
    ------
    ValueError
        If floor_area_m2 <= 0.
    """
    if floor_area_m2 <= 0:
        raise ValueError("floor_area_m2 must be positive")
    return annual_kwh / floor_area_m2
