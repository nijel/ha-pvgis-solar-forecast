"""Tests for the PVGIS Solar Forecast energy platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant.core import HomeAssistant

from custom_components.pvgis_solar_forecast.const import DOMAIN
from custom_components.pvgis_solar_forecast.energy import async_get_solar_forecast

from .conftest import MOCK_CONFIG_DATA, MOCK_CONFIG_OPTIONS

from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.mark.asyncio
async def test_get_solar_forecast(
    hass: HomeAssistant,
    mock_pvgis_fetch: AsyncMock,
    enable_custom_integrations: None,
) -> None:
    """Test getting solar forecast for energy dashboard."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA,
        options=MOCK_CONFIG_OPTIONS,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await async_get_solar_forecast(hass, entry.entry_id)
    assert result is not None
    assert "wh_hours" in result
    assert len(result["wh_hours"]) > 0


@pytest.mark.asyncio
async def test_get_solar_forecast_invalid_entry(hass: HomeAssistant) -> None:
    """Test getting solar forecast with invalid config entry ID."""
    result = await async_get_solar_forecast(hass, "nonexistent")
    assert result is None
