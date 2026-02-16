"""Tests for forecast persistence and restoration."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pvgis_solar_forecast.const import DOMAIN
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_restore_last_forecast_on_startup(
    hass: HomeAssistant,
    mock_pvgis_fetch: AsyncMock,
    enable_custom_integrations: None,
    mock_config_data: dict,
    mock_config_options: dict,
) -> None:
    """Test that forecast is restored on startup when available."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        options=mock_config_options,
    )
    entry.add_to_hass(hass)

    # Mock the weather entity to be unavailable during first refresh
    with patch(
        "custom_components.pvgis_solar_forecast.coordinator.PVGISSolarForecastCoordinator._async_get_cloud_coverage"
    ) as mock_cloud:
        mock_cloud.return_value = ({}, False)  # Empty coverage, not available

        # First setup - no stored forecast yet
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data

        # Verify we have some forecast data (from clear-sky)
        assert coordinator.data is not None
        assert coordinator.data.total is not None

        # Now unload the entry
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        # Setup again - should restore the forecast
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data

        # Verify data is available immediately after setup (before first refresh completes)
        assert coordinator.data is not None
        assert coordinator.data.total is not None

        # The restored forecast should have the same wh_hours
        # (though compute_total_forecast may recalculate some values based on current time)
        restored_wh = coordinator.data.total.wh_hours
        assert len(restored_wh) > 0


@pytest.mark.asyncio
async def test_old_forecast_not_restored(
    hass: HomeAssistant,
    mock_pvgis_fetch: AsyncMock,
    enable_custom_integrations: None,
    mock_config_data: dict,
    mock_config_options: dict,
) -> None:
    """Test that forecasts older than 24 hours are not restored."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        options=mock_config_options,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data

    # Manually save a forecast with an old timestamp
    now = datetime.now().astimezone()
    old_timestamp = now - timedelta(hours=25)  # More than 24 hours old

    await coordinator._store.async_save(
        {
            "timestamp": old_timestamp.isoformat(),
            "wh_hours": {"2024-01-01T12:00:00+00:00": 1000.0},
        }
    )

    # Try to restore - should return None due to age
    restored = await coordinator.async_restore_last_forecast()
    assert restored is None


@pytest.mark.asyncio
async def test_save_forecast_after_update(
    hass: HomeAssistant,
    mock_pvgis_fetch: AsyncMock,
    enable_custom_integrations: None,
    mock_config_data: dict,
    mock_config_options: dict,
) -> None:
    """Test that forecast is saved after each update."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        options=mock_config_options,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data

    # Verify forecast was saved
    stored_data = await coordinator._store.async_load()
    assert stored_data is not None
    assert "timestamp" in stored_data
    assert "wh_hours" in stored_data
    assert len(stored_data["wh_hours"]) > 0

    # Verify timestamp is recent (within last minute)
    now = datetime.now().astimezone()
    stored_timestamp = datetime.fromisoformat(stored_data["timestamp"])
    age = now - stored_timestamp
    assert age < timedelta(minutes=1)
