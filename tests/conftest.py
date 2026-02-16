"""Fixtures for PVGIS Solar Forecast tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.pvgis_solar_forecast.const import (
    CONF_ARRAYS,
    CONF_AZIMUTH,
    CONF_DECLINATION,
    CONF_LOSS,
    CONF_MODULES_POWER,
    CONF_MOUNTING_PLACE,
    CONF_PV_TECH,
    CONF_WEATHER_ENTITY,
)
from custom_components.pvgis_solar_forecast.pvgis import (
    PVGISData,
    _parse_pvgis_response,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE

MOCK_PVGIS_RESPONSE = {
    "outputs": {
        "hourly": [
            {"time": "20160101:0000", "P": 0.0},
            {"time": "20160101:0600", "P": 50.0},
            {"time": "20160101:0700", "P": 200.0},
            {"time": "20160101:0800", "P": 500.0},
            {"time": "20160101:0900", "P": 800.0},
            {"time": "20160101:1000", "P": 1000.0},
            {"time": "20160101:1100", "P": 1200.0},
            {"time": "20160101:1200", "P": 1300.0},
            {"time": "20160101:1300", "P": 1200.0},
            {"time": "20160101:1400", "P": 1000.0},
            {"time": "20160101:1500", "P": 700.0},
            {"time": "20160101:1600", "P": 400.0},
            {"time": "20160101:1700", "P": 100.0},
            {"time": "20160101:1800", "P": 0.0},
            {"time": "20160701:0500", "P": 100.0},
            {"time": "20160701:0600", "P": 300.0},
            {"time": "20160701:0700", "P": 600.0},
            {"time": "20160701:0800", "P": 900.0},
            {"time": "20160701:0900", "P": 1200.0},
            {"time": "20160701:1000", "P": 1500.0},
            {"time": "20160701:1100", "P": 1800.0},
            {"time": "20160701:1200", "P": 2000.0},
            {"time": "20160701:1300", "P": 1800.0},
            {"time": "20160701:1400", "P": 1500.0},
            {"time": "20160701:1500", "P": 1200.0},
            {"time": "20160701:1600", "P": 800.0},
            {"time": "20160701:1700", "P": 400.0},
            {"time": "20160701:1800", "P": 100.0},
            {"time": "20160701:1900", "P": 0.0},
        ]
    }
}

MOCK_CONFIG_DATA = {
    CONF_LATITUDE: 45.0,
    CONF_LONGITUDE: 8.0,
}

MOCK_CONFIG_OPTIONS = {
    CONF_WEATHER_ENTITY: "weather.home",
    CONF_ARRAYS: [
        {
            "name": "South Roof",
            CONF_DECLINATION: 35,
            CONF_AZIMUTH: 0,
            CONF_MODULES_POWER: 5.0,
            CONF_LOSS: 14.0,
            CONF_MOUNTING_PLACE: "free",
            CONF_PV_TECH: "crystsi",
        }
    ],
}


def create_mock_pvgis_data() -> PVGISData:
    """Create mock PVGISData from the test response."""
    return _parse_pvgis_response(MOCK_PVGIS_RESPONSE)


@pytest.fixture
def mock_config_data() -> dict:
    """Provide mock config data."""
    return MOCK_CONFIG_DATA.copy()


@pytest.fixture
def mock_config_options() -> dict:
    """Provide mock config options."""
    return MOCK_CONFIG_OPTIONS.copy()


@pytest.fixture
def mock_pvgis_response() -> dict:
    """Provide mock PVGIS API response."""
    return MOCK_PVGIS_RESPONSE.copy()


@pytest.fixture
def mock_pvgis_data() -> PVGISData:
    """Provide mock PVGISData."""
    return create_mock_pvgis_data()


@pytest.fixture
def mock_pvgis_fetch() -> Generator[AsyncMock]:
    """Mock PVGIS API fetch."""
    with patch(
        "custom_components.pvgis_solar_forecast.coordinator.fetch_pvgis_data",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.return_value = create_mock_pvgis_data()
        yield mock_fetch
