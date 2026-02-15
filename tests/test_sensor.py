"""Tests for PVGIS Solar Forecast sensors."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant

from custom_components.pvgis_solar_forecast.const import DOMAIN

from .conftest import MOCK_CONFIG_DATA, MOCK_CONFIG_OPTIONS

from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.mark.asyncio
async def test_sensors_created(
    hass: HomeAssistant,
    mock_pvgis_fetch: AsyncMock,
    enable_custom_integrations: None,
) -> None:
    """Test that sensors are created."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA,
        options=MOCK_CONFIG_OPTIONS,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Check that the total forecast sensors exist
    # Entity IDs are auto-generated from device name and entity name
    state = hass.states.get("sensor.pvgis_energy_production_today")
    assert state is not None

    state = hass.states.get("sensor.pvgis_power_production_now")
    assert state is not None


@pytest.mark.asyncio
async def test_sensor_values(
    hass: HomeAssistant,
    mock_pvgis_fetch: AsyncMock,
    enable_custom_integrations: None,
) -> None:
    """Test that sensor values are populated."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA,
        options=MOCK_CONFIG_OPTIONS,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # The power production now sensor should have a numeric value
    state = hass.states.get("sensor.pvgis_power_production_now")
    assert state is not None
    # Value might be 0 if running tests at night, but should be a number
    assert state.state != "unavailable"


@pytest.mark.asyncio
async def test_array_sensors_created(
    hass: HomeAssistant,
    mock_pvgis_fetch: AsyncMock,
    enable_custom_integrations: None,
) -> None:
    """Test that per-array sensors are created."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA,
        options=MOCK_CONFIG_OPTIONS,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Check for the array-specific sensor
    state = hass.states.get("sensor.pvgis_energy_production_today_2")
    assert state is not None
