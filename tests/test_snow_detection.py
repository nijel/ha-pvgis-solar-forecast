"""Tests for snow detection in the PVGIS Solar Forecast coordinator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.pvgis_solar_forecast.const import (
    CONF_AZIMUTH,
    CONF_DECLINATION,
    CONF_MODULES_POWER,
    SNOW_FACTOR_COVERED,
    SNOW_TEMP_THRESHOLD,
)
from custom_components.pvgis_solar_forecast.coordinator import (
    PVGISSolarForecastCoordinator,
    SolarForecastData,
)


class TestSnowDetection:
    """Test snow detection logic."""

    def test_no_snow_when_no_recent_precipitation(self, mock_pvgis_data) -> None:
        """Test that no snow is detected when there's no recent precipitation."""
        # Create a minimal coordinator instance for testing
        coordinator = PVGISSolarForecastCoordinator.__new__(
            PVGISSolarForecastCoordinator
        )
        coordinator.data = None

        now = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)
        array_config = {
            "name": "Test Array",
            CONF_DECLINATION: 35,
            CONF_AZIMUTH: 0,
            CONF_MODULES_POWER: 5.0,
        }

        # No precipitation or snow data
        temperature_data = {}
        precipitation_data = {}
        snow_data = {}

        result = coordinator._detect_snow_on_array(
            "Test Array",
            array_config,
            mock_pvgis_data,
            temperature_data,
            precipitation_data,
            snow_data,
            now,
        )

        assert result is False

    def test_snow_detected_with_cold_and_precipitation(self, mock_pvgis_data) -> None:
        """Test that snow is detected with cold temperature and precipitation."""
        coordinator = PVGISSolarForecastCoordinator.__new__(
            PVGISSolarForecastCoordinator
        )
        coordinator.data = None

        now = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)
        array_config = {
            "name": "Test Array",
            CONF_DECLINATION: 35,
            CONF_AZIMUTH: 0,
            CONF_MODULES_POWER: 5.0,
        }

        # Recent cold temperature with precipitation (implies snow)
        temperature_data = {}
        precipitation_data = {}
        snow_data = {}

        # Add snow event 2 hours ago
        snow_time = now - timedelta(hours=2)
        temperature_data[snow_time.isoformat()] = (
            SNOW_TEMP_THRESHOLD - 1
        )  # Below threshold
        precipitation_data[snow_time.isoformat()] = 5.0  # 5mm precipitation

        result = coordinator._detect_snow_on_array(
            "Test Array",
            array_config,
            mock_pvgis_data,
            temperature_data,
            precipitation_data,
            snow_data,
            now,
        )

        assert result is True

    def test_snow_detected_with_explicit_snow_data(self, mock_pvgis_data) -> None:
        """Test that snow is detected when weather provides explicit snow data."""
        coordinator = PVGISSolarForecastCoordinator.__new__(
            PVGISSolarForecastCoordinator
        )
        coordinator.data = None

        now = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)
        array_config = {
            "name": "Test Array",
            CONF_DECLINATION: 35,
            CONF_AZIMUTH: 0,
            CONF_MODULES_POWER: 5.0,
        }

        # Explicit snow data
        temperature_data = {}
        precipitation_data = {}
        snow_data = {}

        # Add snow event 1 hour ago
        snow_time = now - timedelta(hours=1)
        snow_data[snow_time.isoformat()] = 3.0  # 3mm of snow

        result = coordinator._detect_snow_on_array(
            "Test Array",
            array_config,
            mock_pvgis_data,
            temperature_data,
            precipitation_data,
            snow_data,
            now,
        )

        assert result is True

    def test_manual_override_covered(self, mock_pvgis_data) -> None:
        """Test that manual override works for snow covered status."""
        coordinator = PVGISSolarForecastCoordinator.__new__(
            PVGISSolarForecastCoordinator
        )
        coordinator.data = SolarForecastData()
        coordinator.data.snow_overrides = {"Test Array": True}

        now = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)
        array_config = {
            "name": "Test Array",
            CONF_DECLINATION: 35,
            CONF_AZIMUTH: 0,
            CONF_MODULES_POWER: 5.0,
        }

        # No actual snow in weather data
        temperature_data = {}
        precipitation_data = {}
        snow_data = {}

        result = coordinator._detect_snow_on_array(
            "Test Array",
            array_config,
            mock_pvgis_data,
            temperature_data,
            precipitation_data,
            snow_data,
            now,
        )

        # Should return True due to manual override
        assert result is True

    def test_manual_override_clear(self, mock_pvgis_data) -> None:
        """Test that manual override works for snow clear status."""
        coordinator = PVGISSolarForecastCoordinator.__new__(
            PVGISSolarForecastCoordinator
        )
        coordinator.data = SolarForecastData()
        coordinator.data.snow_overrides = {"Test Array": False}

        now = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)
        array_config = {
            "name": "Test Array",
            CONF_DECLINATION: 35,
            CONF_AZIMUTH: 0,
            CONF_MODULES_POWER: 5.0,
        }

        # Actual snow in weather data
        temperature_data = {}
        precipitation_data = {}
        snow_data = {}

        snow_time = now - timedelta(hours=1)
        snow_data[snow_time.isoformat()] = 5.0  # Recent snow

        result = coordinator._detect_snow_on_array(
            "Test Array",
            array_config,
            mock_pvgis_data,
            temperature_data,
            precipitation_data,
            snow_data,
            now,
        )

        # Should return False due to manual override
        assert result is False

    def test_snow_factor_application(self, mock_pvgis_data) -> None:
        """Test that snow factor is correctly applied to power production."""
        coordinator = PVGISSolarForecastCoordinator.__new__(
            PVGISSolarForecastCoordinator
        )

        now = datetime(2024, 7, 1, 12, 0, tzinfo=UTC)
        cloud_coverage = {}

        # Compute forecast without snow
        forecast_no_snow = coordinator.compute_forecast(
            mock_pvgis_data, cloud_coverage, now, snow_covered=False
        )

        # Compute forecast with snow
        forecast_with_snow = coordinator.compute_forecast(
            mock_pvgis_data, cloud_coverage, now, snow_covered=True
        )

        # Power production should be reduced by snow factor
        assert forecast_with_snow.power_production_now == pytest.approx(
            forecast_no_snow.power_production_now * SNOW_FACTOR_COVERED
        )
        assert forecast_with_snow.energy_production_today == pytest.approx(
            forecast_no_snow.energy_production_today * SNOW_FACTOR_COVERED
        )

    def test_set_snow_override(self) -> None:
        """Test setting snow override on coordinator."""
        coordinator = PVGISSolarForecastCoordinator.__new__(
            PVGISSolarForecastCoordinator
        )
        coordinator.data = SolarForecastData()

        # Set override to covered
        coordinator.set_snow_override("Test Array", True)
        assert coordinator.data.snow_overrides["Test Array"] is True

        # Set override to clear
        coordinator.set_snow_override("Test Array", False)
        assert coordinator.data.snow_overrides["Test Array"] is False

        # Remove override
        coordinator.set_snow_override("Test Array", None)
        assert "Test Array" not in coordinator.data.snow_overrides

    def test_forecast_snow_prediction(self, mock_pvgis_data) -> None:
        """Test that snow is predicted per-hour in the forecast."""
        coordinator = PVGISSolarForecastCoordinator.__new__(
            PVGISSolarForecastCoordinator
        )

        now = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)
        cloud_coverage = {}

        # Setup weather data with snow predicted in 2 hours
        temperature_data = {}
        precipitation_data = {}
        snow_data = {}

        # Snow predicted in 2 hours
        future_snow_time = now + timedelta(hours=2)
        snow_data[future_snow_time.isoformat()] = 5.0  # 5mm of snow

        array_config = {
            "name": "Test Array",
            CONF_DECLINATION: 35,
            CONF_AZIMUTH: 0,
            CONF_MODULES_POWER: 5.0,
        }

        # Compute forecast with per-hour snow prediction
        forecast = coordinator.compute_forecast(
            mock_pvgis_data,
            cloud_coverage,
            now,
            snow_covered=False,
            array_config=array_config,
            temperature_data=temperature_data,
            precipitation_data=precipitation_data,
            snow_data=snow_data,
        )

        # Check that detailed forecast includes snow_covered field
        assert len(forecast.detailed_forecast) > 0
        first_hour = forecast.detailed_forecast[0]
        assert "snow_covered" in first_hour

        # First hour (now) should not have snow
        assert first_hour["snow_covered"] is False

        # Future hours should have snow predicted
        # Find the hour with snow
        snow_found = False
        for i, hour_data in enumerate(forecast.detailed_forecast):
            if i > 0 and "snow_covered" in hour_data and hour_data["snow_covered"]:
                snow_found = True
                break

        assert snow_found, "Snow should be predicted in future hours"
