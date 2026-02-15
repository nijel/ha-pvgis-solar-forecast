"""Energy platform for PVGIS Solar Forecast."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .coordinator import PVGISSolarForecastCoordinator


async def async_get_solar_forecast(
    hass: HomeAssistant, config_entry_id: str
) -> dict[str, dict[str, float | int]] | None:
    """Get solar forecast for a config entry ID."""
    if (entry := hass.config_entries.async_get_entry(config_entry_id)) is None:
        return None

    if not isinstance(entry.runtime_data, PVGISSolarForecastCoordinator):
        return None

    data = entry.runtime_data.data
    if data is None or data.total is None:
        return None

    return {"wh_hours": data.total.wh_hours}
