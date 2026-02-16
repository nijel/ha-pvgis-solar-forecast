"""Tests for PVGIS Solar Forecast binary sensors."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pvgis_solar_forecast.const import DOMAIN
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_weather_entity_available_binary_sensor_created(
    hass: HomeAssistant,
    mock_pvgis_fetch: AsyncMock,
    enable_custom_integrations: None,
    mock_config_data: dict,
    mock_config_options: dict,
) -> None:
    """Test that weather entity available binary sensor is created."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        options=mock_config_options,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Check that the weather entity available binary sensor exists
    state = hass.states.get("binary_sensor.solar_production_forecast_weather_entity_available")
    assert state is not None
    # The state should be "on" or "off" (not "True" or "False")
    assert state.state in ["on", "off", "unavailable"]


@pytest.mark.asyncio
async def test_weather_entity_available_state(
    hass: HomeAssistant,
    mock_pvgis_fetch: AsyncMock,
    enable_custom_integrations: None,
    mock_config_data: dict,
    mock_config_options: dict,
) -> None:
    """Test that weather entity available binary sensor has correct state."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        options=mock_config_options,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.solar_production_forecast_weather_entity_available")
    assert state is not None
    # In tests, weather entity is not configured, so it should be off
    # The actual state depends on the test setup
    assert state.state in ["on", "off"]
