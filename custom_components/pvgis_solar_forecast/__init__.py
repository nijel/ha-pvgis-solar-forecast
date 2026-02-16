"""The PVGIS Solar Forecast integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import PVGISSolarForecastConfigEntry, PVGISSolarForecastCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BUTTON]


async def async_setup_entry(
    hass: HomeAssistant, entry: PVGISSolarForecastConfigEntry
) -> bool:
    """Set up PVGIS Solar Forecast from a config entry."""
    coordinator = PVGISSolarForecastCoordinator(hass, entry)

    # Try to restore last forecast to provide immediate data on startup
    restored_data = await coordinator.async_restore_last_forecast()
    if restored_data:
        # Set the restored data as initial coordinator data
        # This will be replaced by fresh data after first refresh
        coordinator.data = restored_data

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: PVGISSolarForecastConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: PVGISSolarForecastConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
