"""Tests for the PVGIS Solar Forecast energy platform."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pvgis_solar_forecast.const import DOMAIN
from custom_components.pvgis_solar_forecast.coordinator import ForecastSnapshot
from custom_components.pvgis_solar_forecast.energy import async_get_solar_forecast
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_get_solar_forecast(
    hass: HomeAssistant,
    mock_pvgis_fetch: AsyncMock,
    enable_custom_integrations: None,
    mock_config_data: dict,
    mock_config_options: dict,
) -> None:
    """Test getting solar forecast for energy dashboard."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        options=mock_config_options,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await async_get_solar_forecast(hass, entry.entry_id)
    assert result is not None
    assert "wh_hours" in result
    assert len(result["wh_hours"]) > 0


@pytest.mark.asyncio
async def test_get_solar_forecast_with_historical_data(
    hass: HomeAssistant,
    mock_pvgis_fetch: AsyncMock,
    enable_custom_integrations: None,
    mock_config_data: dict,
    mock_config_options: dict,
) -> None:
    """Test getting solar forecast includes historical forecast data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        options=mock_config_options,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Get the coordinator and add a historical snapshot
    coordinator = entry.runtime_data
    now = datetime.now().astimezone()
    past_time = now - timedelta(hours=2)
    past_hour = past_time.replace(minute=0, second=0, microsecond=0)
    
    # Create a historical snapshot with past forecast data
    historical_wh_hours = {
        (past_hour - timedelta(hours=1)).isoformat(): 1000.0,
        past_hour.isoformat(): 1500.0,
        (past_hour + timedelta(hours=1)).isoformat(): 2000.0,
    }
    
    if coordinator.data:
        coordinator.data.historical_snapshots.append(
            ForecastSnapshot(timestamp=past_time, wh_hours=historical_wh_hours)
        )
    
    result = await async_get_solar_forecast(hass, entry.entry_id)
    assert result is not None
    assert "wh_hours" in result
    
    # Verify that past forecast data is included
    wh_hours = result["wh_hours"]
    assert len(wh_hours) > 0
    
    # The historical data for times before now should be included
    for ts_str in historical_wh_hours:
        forecast_time = datetime.fromisoformat(ts_str)
        if forecast_time < now.replace(minute=0, second=0, microsecond=0):
            assert ts_str in wh_hours


@pytest.mark.asyncio
async def test_get_solar_forecast_invalid_entry(hass: HomeAssistant) -> None:
    """Test getting solar forecast with invalid config entry ID."""
    result = await async_get_solar_forecast(hass, "nonexistent")
    assert result is None
