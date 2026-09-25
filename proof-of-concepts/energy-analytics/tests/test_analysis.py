"""energy_analytics.analysis against hand calculations."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from energy_analytics import analysis


def envelope() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "level": ["L2", "L1", "L1", "L3"],
            "area_m2": [150.0, 100.0, 200.0, 80.0],
            "u_value_w_m2k": [0.2, 0.5, 0.3, 0.4],
        }
    )


def test_envelope_ua_sums_per_level():
    result = analysis.envelope_ua(envelope())
    assert result.name == "ua_w_per_k"
    assert list(result.index) == ["L1", "L2", "L3"]
    assert result.to_numpy() == pytest.approx([50.0 + 60.0, 30.0, 32.0])


def test_upgrade_candidates_filters_strictly_and_sorts():
    source = envelope()
    before = source.copy()
    result = analysis.upgrade_candidates(source, 0.3)
    # 0.3 is not strictly above the threshold.
    assert result["u_value_w_m2k"].tolist() == [0.5, 0.4]
    assert result["heat_loss_w_per_k"].tolist() == pytest.approx([50.0, 32.0])
    pd.testing.assert_frame_equal(source, before)


def test_daily_totals():
    index = pd.date_range("2025-01-01", periods=48, freq="h")
    hourly = pd.DataFrame(
        {
            "outdoor_temp_c": np.arange(48, dtype=float),
            "total_kwh": 2.0,
            "heating_kwh": 1.5,
        },
        index=index,
    )
    daily = analysis.daily_totals(hourly)
    assert len(daily) == 2
    assert daily["outdoor_temp_c"].tolist() == pytest.approx([11.5, 35.5])
    assert daily["total_kwh"].tolist() == pytest.approx([48.0, 48.0])
    assert daily["heating_kwh"].tolist() == pytest.approx([36.0, 36.0])
    assert "electricity_kwh" not in daily


def test_change_point_predict():
    fit = analysis.ChangePointFit(100.0, 20.0, 15.0, 0.99, 0.01)
    assert fit.predict(np.array([5.0, 15.0, 25.0])) == pytest.approx(
        [300.0, 100.0, 100.0]
    )


def test_fit_change_point_recovers_known_parameters():
    temps = np.linspace(-5, 25, 200)
    noise = np.random.default_rng(0).normal(0, 2, 200)
    daily = pd.DataFrame(
        {
            "outdoor_temp_c": temps,
            "total_kwh": 100.0 + 20.0 * np.maximum(0, 15.0 - temps) + noise,
        },
        index=pd.date_range("2025-01-01", periods=200, freq="D"),
    )
    fit = analysis.fit_change_point(daily)
    assert fit.base_kwh_per_day == pytest.approx(100.0, abs=3)
    assert fit.slope_kwh_per_degc_day == pytest.approx(20.0, abs=1)
    assert fit.balance_point_c == pytest.approx(15.0, abs=0.7)
    assert fit.r2 > 0.95
    assert 0 < fit.cv_rmse < 0.05


def test_fit_change_point_needs_ten_rows():
    daily = pd.DataFrame({"outdoor_temp_c": [1.0] * 5, "total_kwh": [2.0] * 5})
    with pytest.raises(ValueError):
        analysis.fit_change_point(daily)


def test_fit_hourly_model_learns_the_drivers():
    index = pd.date_range("2025-01-01", periods=24 * 60, freq="h")
    rng = np.random.default_rng(0)
    hour = index.hour.to_numpy()
    temp = 5 + 8 * np.sin(2 * np.pi * hour / 24) + rng.normal(0, 1, len(index))
    occupied = (index.dayofweek < 5) & (hour >= 8) & (hour < 18)
    total = (
        50 + 3 * np.maximum(0, 15 - temp) + 20 * occupied + rng.normal(0, 1, len(index))
    )
    metered = pd.DataFrame(
        {"outdoor_temp_c": temp, "occupied": occupied, "total_kwh": total}, index=index
    )
    fit = analysis.fit_hourly_model(metered)
    assert fit.r2 > 0.8
    assert set(fit.feature_importance) == {
        "outdoor_temp_c",
        "hour",
        "weekday",
        "occupied",
    }
    assert sum(fit.feature_importance.values()) == pytest.approx(1.0)


def test_eui():
    assert analysis.eui_kwh_m2(1000.0, 100.0) == 10.0
    with pytest.raises(ValueError):
        analysis.eui_kwh_m2(1000.0, 0.0)
