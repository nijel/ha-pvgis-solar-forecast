"""Tests for PVGIS Solar Forecast sensors."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pvgis_solar_forecast.const import DOMAIN
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_sensors_created(
    hass: HomeAssistant,
    mock_pvgis_fetch: AsyncMock,
    enable_custom_integrations: None,
    mock_config_data: dict,
    mock_config_options: dict,
) -> None:
    """Test that sensors are created."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        options=mock_config_options,
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
    mock_config_data: dict,
    mock_config_options: dict,
) -> None:
    """Test that sensor values are populated."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        options=mock_config_options,
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
async def test_sensor_forecast_attributes(
    hass: HomeAssistant,
    mock_pvgis_fetch: AsyncMock,
    enable_custom_integrations: None,
    mock_config_data: dict,
    mock_config_options: dict,
) -> None:
    """Test that sensors expose forecast data in attributes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        options=mock_config_options,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.pvgis_energy_production_today")
    assert state is not None
    assert "wh_hours" in state.attributes
    assert isinstance(state.attributes["wh_hours"], dict)
    assert len(state.attributes["wh_hours"]) > 0
    assert "detailedForecast" in state.attributes
    assert isinstance(state.attributes["detailedForecast"], list)
    assert len(state.attributes["detailedForecast"]) > 0
    # Check detailed forecast structure
    entry0 = state.attributes["detailedForecast"][0]
    assert "period_start" in entry0
    assert "pv_estimate" in entry0


@pytest.mark.asyncio
async def test_array_sensors_created(
    hass: HomeAssistant,
    mock_pvgis_fetch: AsyncMock,
    enable_custom_integrations: None,
    mock_config_data: dict,
    mock_config_options: dict,
) -> None:
    """Test that per-array sensors are created."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        options=mock_config_options,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Check for the array-specific sensor
    state = hass.states.get("sensor.pvgis_energy_production_today_2")
    assert state is not None


@pytest.mark.asyncio
async def test_diagnostic_sensors_created(
    hass: HomeAssistant,
    mock_pvgis_fetch: AsyncMock,
    enable_custom_integrations: None,
    mock_config_data: dict,
    mock_config_options: dict,
) -> None:
    """Test that diagnostic sensors are created."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        options=mock_config_options,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.pvgis_weather_entity_available")
    assert state is not None

    state = hass.states.get("sensor.pvgis_clear_sky_power_now")
    assert state is not None

    state = hass.states.get("sensor.pvgis_clear_sky_energy_today")
    assert state is not None


@pytest.mark.asyncio
async def test_per_array_diagnostic_sensors_created(
    hass: HomeAssistant,
    mock_pvgis_fetch: AsyncMock,
    enable_custom_integrations: None,
    mock_config_data: dict,
    mock_config_options: dict,
) -> None:
    """Test that per-array diagnostic sensors are created."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        options=mock_config_options,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Per-array clear sky sensors should exist
    # Entity IDs may be auto-generated, check by iterating states
    all_states = hass.states.async_all()
    sensor_ids = [s.entity_id for s in all_states if s.entity_id.startswith("sensor.")]
    clear_sky_sensors = [s for s in sensor_ids if "clear_sky" in s]
    # Should have at least total + per-array clear sky sensors
    assert len(clear_sky_sensors) >= 4  # 2 total + 2 per-array


@pytest.mark.asyncio
async def test_multi_day_sensors_created(
    hass: HomeAssistant,
    mock_pvgis_fetch: AsyncMock,
    enable_custom_integrations: None,
    mock_config_data: dict,
    mock_config_options: dict,
) -> None:
    """Test that multi-day energy production sensors are created."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        options=mock_config_options,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Check that day 2-6 sensors exist (for the total forecast)
    all_states = hass.states.async_all()
    sensor_ids = [s.entity_id for s in all_states if s.entity_id.startswith("sensor.")]
    day_sensors = [s for s in sensor_ids if "energy_production_day" in s]
    # Should have day 2-6 for total and per-array
    assert len(day_sensors) >= 5
