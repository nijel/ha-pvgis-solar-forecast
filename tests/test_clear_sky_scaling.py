"""Tests for clear sky calculation with seasonal variations."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.pvgis_solar_forecast.coordinator import (
    PVGISSolarForecastCoordinator,
)
from custom_components.pvgis_solar_forecast.pvgis import (
    PVGISData,
    calculate_clearsky_irradiance,
)

UTC = ZoneInfo("UTC")


@pytest.fixture
def mock_pvgis_data_with_irradiance() -> PVGISData:
    """Create mock PVGIS data with irradiance and sun height for testing."""
    hourly_data = {}
    irradiance_data = {}
    sun_height_data = {}

    # Create realistic data for multiple days
    for day in range(1, 8):
        for hour in range(24):
            # Simulate sun height (parabolic curve during day)
            if 6 <= hour <= 18:
                # Peak at noon (hour 12)
                sun_height = 50.0 * (1 - ((hour - 12) / 6) ** 2)
                # Power increases with sun height
                hourly_data[(1, day, hour)] = 100.0 * hour * sun_height
                # TMY irradiance (reduced by typical clouds, ~70% of clear-sky)
                irradiance_data[(1, day, hour)] = 500.0 * sun_height / 50.0
                sun_height_data[(1, day, hour)] = sun_height
            else:
                # Nighttime
                hourly_data[(1, day, hour)] = 0.0
                irradiance_data[(1, day, hour)] = 0.0
                sun_height_data[(1, day, hour)] = 0.0

    return PVGISData(hourly_data, irradiance_data, sun_height_data)


class TestClearSkyCalculation:
    """Test clear sky calculation with seasonal variations."""

    def test_clearsky_irradiance_model(self) -> None:
        """Test the clear-sky irradiance calculation function."""
        # Test at different sun heights
        irr_low = calculate_clearsky_irradiance(10.0, 1)
        irr_mid = calculate_clearsky_irradiance(45.0, 180)
        irr_high = calculate_clearsky_irradiance(90.0, 180)

        # Higher sun = more irradiance
        assert irr_low < irr_mid < irr_high
        # Reasonable values
        assert 0 < irr_low < 200
        assert 500 < irr_mid < 800
        assert 900 < irr_high < 1100

        # Sun below horizon = zero
        assert calculate_clearsky_irradiance(-10.0, 1) == 0.0

    def test_clear_sky_scaled_above_tmy(
        self, mock_pvgis_data_with_irradiance: PVGISData
    ) -> None:
        """Test that clear_sky values are higher than TMY baseline."""
        # TMY power at noon
        tmy_power = mock_pvgis_data_with_irradiance.get_power(1, 1, 12)
        # Clear-sky power at noon
        clearsky_power = mock_pvgis_data_with_irradiance.get_clearsky_power(1, 1, 12)

        # Clear-sky should be higher than TMY
        assert clearsky_power > tmy_power
        # Reasonable scaling (1.2x to 1.8x depending on typical cloudiness)
        ratio = clearsky_power / tmy_power if tmy_power > 0 else 1.0
        assert 1.2 <= ratio <= 1.8

    def test_clear_sky_independent_of_clouds(
        self, mock_pvgis_data_with_irradiance: PVGISData
    ) -> None:
        """Test that clear_sky values don't change with cloud coverage."""
        now = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)

        coordinator = PVGISSolarForecastCoordinator.__new__(
            PVGISSolarForecastCoordinator
        )

        # Forecast with no clouds
        clear_forecast = coordinator.compute_forecast(
            mock_pvgis_data_with_irradiance, {}, now
        )

        # Forecast with 100% clouds starting from midnight to cover all hours
        cloud_coverage = {}
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        for h in range(7 * 24):  # 7 days
            dt = today_start + timedelta(hours=h)
            cloud_coverage[dt.isoformat()] = 100.0

        cloudy_forecast = coordinator.compute_forecast(
            mock_pvgis_data_with_irradiance, cloud_coverage, now
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

    def test_clear_sky_fallback_without_irradiance(self) -> None:
        """Test that clear-sky calculation falls back to TMY when irradiance data is missing."""
        # Create PVGIS data without irradiance
        hourly_data = {(1, 1, 12): 5000.0}
        pvgis_data = PVGISData(hourly_data)

        # Without irradiance data, should return TMY power
        clearsky = pvgis_data.get_clearsky_power(1, 1, 12)
        assert clearsky == 5000.0

    def test_coordinator_uses_clearsky_method(
        self, mock_pvgis_data_with_irradiance: PVGISData
    ) -> None:
        """Test that coordinator uses get_clearsky_power for sensors."""
        now = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)

        coordinator = PVGISSolarForecastCoordinator.__new__(
            PVGISSolarForecastCoordinator
        )

        forecast = coordinator.compute_forecast(
            mock_pvgis_data_with_irradiance, {}, now
        )

        # Verify that detailed forecast has clear_sky values
        noon_entry = forecast.detailed_forecast[12]
        assert noon_entry["pv_estimate_clear_sky"] > 0

        # Clear-sky should be higher than estimate (no clouds = TMY baseline)
        assert noon_entry["pv_estimate_clear_sky"] >= noon_entry["pv_estimate"]
