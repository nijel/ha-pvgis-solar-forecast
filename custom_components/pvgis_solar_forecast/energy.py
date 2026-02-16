"""Energy platform for PVGIS Solar Forecast."""

from __future__ import annotations

from datetime import datetime

from homeassistant.core import HomeAssistant

from .coordinator import PVGISSolarForecastCoordinator


async def async_get_solar_forecast(
    hass: HomeAssistant, config_entry_id: str
) -> dict[str, dict[str, float | int]] | None:
    """Get solar forecast for a config entry ID.

    Returns both historical forecast data (past forecasts for times that have passed)
    and future forecast data. This allows the Energy dashboard to compare forecasts
    against actual production.
    """
    if (entry := hass.config_entries.async_get_entry(config_entry_id)) is None:
        return None

    if not isinstance(entry.runtime_data, PVGISSolarForecastCoordinator):
        return None

    data = entry.runtime_data.data
    if data is None or data.total is None:
        return None

    now = datetime.now().astimezone()
    now_hour = now.replace(minute=0, second=0, microsecond=0)

    # Start with current/future forecast data
    wh_hours = data.total.wh_hours.copy()

    # Add historical forecast data (past forecasts for times that have already passed)
    # For each historical snapshot, include the forecast values for times that were
    # in the future when the forecast was made, but are now in the past
    for snapshot in data.historical_snapshots:
        # Only include forecasts that are now in the past
        for ts_str, wh_value in snapshot.wh_hours.items():
            # Skip if already covered by current forecast
            if ts_str in wh_hours:
                continue

            forecast_time = datetime.fromisoformat(ts_str)
            forecast_hour = forecast_time.replace(minute=0, second=0, microsecond=0)

            # If this forecast time is in the past (relative to now), include it
            if forecast_hour < now_hour:
                wh_hours[ts_str] = wh_value

    return {"wh_hours": wh_hours}
