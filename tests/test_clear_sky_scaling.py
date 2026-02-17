"""Tests for clear sky scaling factor feature."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.pvgis_solar_forecast.const import CLEAR_SKY_FACTOR
from custom_components.pvgis_solar_forecast.coordinator import (
    PVGISSolarForecastCoordinator,
)
from custom_components.pvgis_solar_forecast.pvgis import PVGISData

UTC = ZoneInfo("UTC")


@pytest.fixture
def mock_pvgis_data() -> PVGISData:
    """Create mock PVGIS data for testing."""
    hourly_data = {}
    # Create data for multiple days to test forecast
    for day in range(1, 8):
        for hour in range(24):
            if 6 <= hour <= 18:
                # Daytime: power increases linearly with hour
                hourly_data[(1, day, hour)] = 1000.0 * hour
            else:
                # Nighttime: no production
                hourly_data[(1, day, hour)] = 0.0
    return PVGISData(hourly_data)


class TestClearSkyScaling:
    """Test clear sky scaling factor functionality."""

    def test_clear_sky_scaled_above_pvgis_baseline(
        self, mock_pvgis_data: PVGISData
    ) -> None:
        """Test that clear_sky values are scaled above PVGIS TMY baseline."""
        now = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)

        coordinator = PVGISSolarForecastCoordinator.__new__(
            PVGISSolarForecastCoordinator
        )

        # Compute forecast with no clouds (baseline)
        forecast = coordinator.compute_forecast(mock_pvgis_data, {}, now)

        # Get PVGIS baseline value for current hour
        pvgis_baseline = mock_pvgis_data.get_power(now.month, now.day, now.hour)

        # Check that pv_estimate_clear_sky in detailed forecast is scaled
        current_hour_entry = forecast.detailed_forecast[12]  # Hour 12 (noon)
        clear_sky_value = current_hour_entry["pv_estimate_clear_sky"] * 1000  # kW to W

        expected_clear_sky = pvgis_baseline * CLEAR_SKY_FACTOR

        assert clear_sky_value == pytest.approx(expected_clear_sky, rel=0.01)
        assert clear_sky_value > pvgis_baseline  # Should be higher than baseline

    def test_clear_sky_independent_of_clouds(self, mock_pvgis_data: PVGISData) -> None:
        """Test that clear_sky values don't change with cloud coverage."""
        now = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)

        coordinator = PVGISSolarForecastCoordinator.__new__(
            PVGISSolarForecastCoordinator
        )

        # Forecast with no clouds
        clear_forecast = coordinator.compute_forecast(mock_pvgis_data, {}, now)

        # Forecast with 100% clouds starting from midnight to cover all hours
        cloud_coverage = {}
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        for h in range(7 * 24):  # 7 days
            dt = today_start + timedelta(hours=h)
            cloud_coverage[dt.isoformat()] = 100.0

        cloudy_forecast = coordinator.compute_forecast(
            mock_pvgis_data, cloud_coverage, now
        )

        # Check that pv_estimate_clear_sky is the same in both forecasts
        for i in range(len(clear_forecast.detailed_forecast)):
            clear_entry = clear_forecast.detailed_forecast[i]
            cloudy_entry = cloudy_forecast.detailed_forecast[i]

            assert clear_entry["pv_estimate_clear_sky"] == pytest.approx(
                cloudy_entry["pv_estimate_clear_sky"], rel=0.0001
            )

            # But pv_estimate should differ significantly (skip very low values)
            if clear_entry["pv_estimate"] > 1.0:  # Skip nighttime/twilight hours
                assert cloudy_entry["pv_estimate"] < clear_entry["pv_estimate"]

    def test_clear_sky_energy_today_scaled(self, mock_pvgis_data: PVGISData) -> None:
        """Test that clear_sky_energy_today is properly scaled."""
        now = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)

        coordinator = PVGISSolarForecastCoordinator.__new__(
            PVGISSolarForecastCoordinator
        )

        forecast = coordinator.compute_forecast(mock_pvgis_data, {}, now)

        # Calculate expected clear_sky_energy_today
        total_pvgis_today = sum(
            mock_pvgis_data.get_power(now.month, now.day, h) for h in range(24)
        )
        expected_clear_sky_today = (
            total_pvgis_today * CLEAR_SKY_FACTOR / 1000.0
        )  # Wh to kWh

        # Note: clear_sky_energy_today is not set by compute_forecast directly
        # It's calculated in the coordinator's _async_update_data method
        # So we'll just verify the scaling is applied in detailed forecast
        total_from_detailed = sum(
            entry["pv_estimate_clear_sky"] for entry in forecast.detailed_forecast[:24]
        )

        assert total_from_detailed == pytest.approx(expected_clear_sky_today, rel=0.01)

    def test_clear_sky_higher_than_baseline_forecast(
        self, mock_pvgis_data: PVGISData
    ) -> None:
        """Test that clear_sky is higher than baseline (no weather) forecast."""
        now = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)

        coordinator = PVGISSolarForecastCoordinator.__new__(
            PVGISSolarForecastCoordinator
        )

        # Forecast with no clouds (uses PVGIS baseline directly for pv_estimate)
        forecast = coordinator.compute_forecast(mock_pvgis_data, {}, now)

        # For daytime hours, pv_estimate_clear_sky should be higher than pv_estimate
        # because it's scaled by CLEAR_SKY_FACTOR
        for i in range(6, 19):  # Daytime hours
            entry = forecast.detailed_forecast[i]
            if entry["pv_estimate"] > 0:
                # Clear sky should be scaled up by CLEAR_SKY_FACTOR
                expected_ratio = CLEAR_SKY_FACTOR
                actual_ratio = (
                    entry["pv_estimate_clear_sky"] / entry["pv_estimate"]
                    if entry["pv_estimate"] > 0
                    else 1.0
                )
                assert actual_ratio == pytest.approx(expected_ratio, rel=0.01)

    def test_clear_sky_with_partial_clouds(self, mock_pvgis_data: PVGISData) -> None:
        """Test clear_sky remains constant with partial clouds."""
        now = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)

        coordinator = PVGISSolarForecastCoordinator.__new__(
            PVGISSolarForecastCoordinator
        )

        # Forecast with 50% clouds starting from midnight
        cloud_coverage = {}
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        for h in range(7 * 24):  # 7 days
            dt = today_start + timedelta(hours=h)
            cloud_coverage[dt.isoformat()] = 50.0

        forecast_50 = coordinator.compute_forecast(mock_pvgis_data, cloud_coverage, now)

        # Forecast with 75% clouds starting from midnight
        cloud_coverage_75 = {}
        for h in range(7 * 24):  # 7 days
            dt = today_start + timedelta(hours=h)
            cloud_coverage_75[dt.isoformat()] = 75.0

        forecast_75 = coordinator.compute_forecast(
            mock_pvgis_data, cloud_coverage_75, now
        )

        # Clear sky values should be identical
        for i in range(len(forecast_50.detailed_forecast)):
            entry_50 = forecast_50.detailed_forecast[i]
            entry_75 = forecast_75.detailed_forecast[i]

            assert entry_50["pv_estimate_clear_sky"] == pytest.approx(
                entry_75["pv_estimate_clear_sky"], rel=0.0001
            )

            # But pv_estimate should differ
            if entry_50["pv_estimate"] > 1.0:  # Skip nighttime/twilight
                assert entry_75["pv_estimate"] < entry_50["pv_estimate"]
