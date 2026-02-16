"""Tests for the PVGIS Solar Forecast coordinator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.pvgis_solar_forecast.coordinator import (
    PVGISSolarForecastCoordinator,
    SolarArrayForecast,
)
from custom_components.pvgis_solar_forecast.pvgis import PVGISData


class TestCloudFactor:
    """Test cloud factor calculation."""

    def test_no_cloud_data(self) -> None:
        """Test that no cloud data returns clear sky factor."""
        factor = PVGISSolarForecastCoordinator.get_cloud_factor(
            datetime(2024, 7, 1, 12, 0, tzinfo=UTC), {}
        )
        assert factor == 1.0

    def test_clear_sky(self) -> None:
        """Test 0% cloud coverage."""
        now = datetime(2024, 7, 1, 12, 0, tzinfo=UTC)
        coverage = {now.isoformat(): 0.0}
        factor = PVGISSolarForecastCoordinator.get_cloud_factor(now, coverage)
        assert factor == 1.0

    def test_fully_overcast(self) -> None:
        """Test 100% cloud coverage."""
        now = datetime(2024, 7, 1, 12, 0, tzinfo=UTC)
        coverage = {now.isoformat(): 100.0}
        factor = PVGISSolarForecastCoordinator.get_cloud_factor(now, coverage)
        assert factor == pytest.approx(0.2)

    def test_partial_clouds(self) -> None:
        """Test 50% cloud coverage."""
        now = datetime(2024, 7, 1, 12, 0, tzinfo=UTC)
        coverage = {now.isoformat(): 50.0}
        factor = PVGISSolarForecastCoordinator.get_cloud_factor(now, coverage)
        assert factor == pytest.approx(0.6)

    def test_closest_forecast_time(self) -> None:
        """Test that the closest forecast time is used."""
        dt = datetime(2024, 7, 1, 12, 30, tzinfo=UTC)
        coverage = {
            datetime(2024, 7, 1, 12, 0, tzinfo=UTC).isoformat(): 20.0,
            datetime(2024, 7, 1, 13, 0, tzinfo=UTC).isoformat(): 80.0,
        }
        factor = PVGISSolarForecastCoordinator.get_cloud_factor(dt, coverage)
        # Should use 12:00 (20% clouds) as it's closer
        assert factor == pytest.approx(0.84)

    def test_too_far_forecast(self) -> None:
        """Test that forecasts more than 3 hours away are ignored."""
        dt = datetime(2024, 7, 1, 12, 0, tzinfo=UTC)
        coverage = {
            datetime(2024, 7, 1, 18, 0, tzinfo=UTC).isoformat(): 100.0,
        }
        factor = PVGISSolarForecastCoordinator.get_cloud_factor(dt, coverage)
        assert factor == 1.0


class TestComputeForecast:
    """Test forecast computation."""

    def test_compute_forecast_clear_sky(self, mock_pvgis_data: PVGISData) -> None:
        """Test computing forecast with clear sky (no clouds)."""
        # Use a January date to match our test data
        now = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)

        coordinator = PVGISSolarForecastCoordinator.__new__(
            PVGISSolarForecastCoordinator
        )
        forecast = coordinator.compute_forecast(mock_pvgis_data, {}, now)

        assert isinstance(forecast, SolarArrayForecast)
        assert forecast.power_production_now > 0
        assert len(forecast.wh_hours) == 48

    def test_compute_forecast_with_clouds(self, mock_pvgis_data: PVGISData) -> None:
        """Test that clouds reduce production."""
        now = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)

        coordinator = PVGISSolarForecastCoordinator.__new__(
            PVGISSolarForecastCoordinator
        )

        # Clear sky forecast
        clear_forecast = coordinator.compute_forecast(mock_pvgis_data, {}, now)

        # Overcast forecast
        cloud_coverage = {}
        for h in range(48):
            dt = now + timedelta(hours=h)
            cloud_coverage[dt.isoformat()] = 100.0

        cloudy_forecast = coordinator.compute_forecast(
            mock_pvgis_data, cloud_coverage, now
        )

        # Cloudy should produce less
        assert (
            cloudy_forecast.energy_production_today
            < clear_forecast.energy_production_today
        )

    def test_compute_total_forecast(self) -> None:
        """Test computing total forecast from wh_hours."""
        now = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)
        today = now.date()
        tomorrow = today + timedelta(days=1)

        wh_hours = {}
        for h in range(24):
            dt = datetime(today.year, today.month, today.day, h, tzinfo=UTC)
            wh_hours[dt.isoformat()] = 100.0 if 6 <= h <= 18 else 0.0
        for h in range(24):
            dt = datetime(tomorrow.year, tomorrow.month, tomorrow.day, h, tzinfo=UTC)
            wh_hours[dt.isoformat()] = 200.0 if 6 <= h <= 18 else 0.0

        coordinator = PVGISSolarForecastCoordinator.__new__(
            PVGISSolarForecastCoordinator
        )
        forecast = coordinator.compute_total_forecast(wh_hours, now)

        assert forecast.energy_production_today == 1300.0  # 13 hours * 100
        assert forecast.energy_production_tomorrow == 2600.0  # 13 hours * 200
