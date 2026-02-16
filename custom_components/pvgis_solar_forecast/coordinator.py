"""DataUpdateCoordinator for the PVGIS Solar Forecast integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CLOUD_FACTOR_CLEAR,
    CLOUD_FACTOR_OVERCAST,
    CONF_ARRAYS,
    CONF_AZIMUTH,
    CONF_DECLINATION,
    CONF_LOSS,
    CONF_MODULES_POWER,
    CONF_MOUNTING_PLACE,
    CONF_PV_TECH,
    CONF_WEATHER_ENTITY,
    DEFAULT_LOSS,
    DEFAULT_MOUNTING_PLACE,
    DEFAULT_PV_TECH,
    DOMAIN,
    LOGGER,
    PV_TECH_API_MAP,
)
from .pvgis import PVGISData, PVGISError, fetch_pvgis_data

type PVGISSolarForecastConfigEntry = ConfigEntry[PVGISSolarForecastCoordinator]

# PVGIS data doesn't change - refetch monthly
PVGIS_REFRESH_INTERVAL = timedelta(days=30)

# Forecast update interval - every 30 minutes to pick up weather changes
FORECAST_UPDATE_INTERVAL = timedelta(minutes=30)


@dataclass
class SolarArrayData:
    """Data for a single solar array."""

    name: str
    pvgis_data: PVGISData | None = None
    last_pvgis_fetch: datetime | None = None


@dataclass
class SolarForecastData:
    """Solar forecast data for all arrays."""

    arrays: dict[str, SolarArrayForecast] = field(default_factory=dict)
    total: SolarArrayForecast | None = None
    cloud_coverage_used: float | None = None
    weather_entity_available: bool = True


@dataclass
class SolarArrayForecast:
    """Forecast data for a single array or the total."""

    # Energy production forecast by hour: {datetime_iso: wh}
    wh_hours: dict[str, float] = field(default_factory=dict)
    # Detailed forecast: list of {period_start: iso, pv_estimate: kw}
    detailed_forecast: list[dict[str, Any]] = field(default_factory=list)
    energy_production_today: float = 0.0
    energy_production_today_remaining: float = 0.0
    energy_production_tomorrow: float = 0.0
    power_production_now: float = 0.0
    energy_current_hour: float = 0.0
    energy_next_hour: float = 0.0
    power_highest_peak_time_today: datetime | None = None
    power_highest_peak_time_tomorrow: datetime | None = None
    peak_power_today: float = 0.0
    peak_power_tomorrow: float = 0.0


class PVGISSolarForecastCoordinator(DataUpdateCoordinator[SolarForecastData]):
    """Coordinator for PVGIS Solar Forecast data."""

    config_entry: PVGISSolarForecastConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: PVGISSolarForecastConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=FORECAST_UPDATE_INTERVAL,
        )
        self._arrays_data: dict[str, SolarArrayData] = {}
        self._latitude = entry.data[CONF_LATITUDE]
        self._longitude = entry.data[CONF_LONGITUDE]
        self._arrays_config: list[dict[str, Any]] = entry.options.get(CONF_ARRAYS, [])
        self._weather_entity: str = entry.options.get(CONF_WEATHER_ENTITY, "")

    async def _async_update_data(self) -> SolarForecastData:
        """Fetch and compute solar forecast data."""
        session = async_get_clientsession(self.hass)
        now = datetime.now().astimezone()

        # Fetch/refresh PVGIS data for each array
        for array_config in self._arrays_config:
            array_name = array_config["name"]
            array_data = self._arrays_data.get(array_name)

            if array_data is None:
                array_data = SolarArrayData(name=array_name)
                self._arrays_data[array_name] = array_data

            # Refresh PVGIS data if needed (monthly)
            if (
                array_data.pvgis_data is None
                or array_data.last_pvgis_fetch is None
                or (now - array_data.last_pvgis_fetch) > PVGIS_REFRESH_INTERVAL
            ):
                # Map lowercase pv_tech key to PVGIS API value
                pv_tech_key = array_config.get(CONF_PV_TECH, DEFAULT_PV_TECH)
                pv_tech_api = PV_TECH_API_MAP.get(pv_tech_key, pv_tech_key)

                try:
                    array_data.pvgis_data = await fetch_pvgis_data(
                        session=session,
                        latitude=self._latitude,
                        longitude=self._longitude,
                        peakpower=array_config[CONF_MODULES_POWER] / 1000,
                        loss=array_config.get(CONF_LOSS, DEFAULT_LOSS),
                        angle=array_config[CONF_DECLINATION],
                        aspect=array_config[CONF_AZIMUTH],
                        mountingplace=array_config.get(
                            CONF_MOUNTING_PLACE, DEFAULT_MOUNTING_PLACE
                        ),
                        pvtechchoice=pv_tech_api,
                    )
                    array_data.last_pvgis_fetch = now
                except PVGISError as err:
                    if array_data.pvgis_data is None:
                        raise UpdateFailed(
                            f"Failed to fetch PVGIS data for {array_name}: {err}"
                        ) from err
                    LOGGER.warning(
                        "Failed to refresh PVGIS data for %s, using cached: %s",
                        array_name,
                        err,
                    )

        # Get weather forecast for cloud coverage
        cloud_coverage, weather_available = await self._async_get_cloud_coverage()

        # Compute forecasts
        result = SolarForecastData()
        result.weather_entity_available = weather_available
        total_wh: dict[str, float] = {}

        # Track current cloud coverage for diagnostics
        if cloud_coverage:
            now_key = now.replace(minute=0, second=0, microsecond=0).isoformat()
            if now_key in cloud_coverage:
                result.cloud_coverage_used = cloud_coverage[now_key]
            else:
                # Find closest
                for cov in cloud_coverage.values():
                    result.cloud_coverage_used = cov
                    break

        for array_config in self._arrays_config:
            array_name = array_config["name"]
            array_data = self._arrays_data.get(array_name)
            if array_data is None or array_data.pvgis_data is None:
                continue

            forecast = self.compute_forecast(array_data.pvgis_data, cloud_coverage, now)
            result.arrays[array_name] = forecast

            # Accumulate totals
            for ts, wh in forecast.wh_hours.items():
                total_wh[ts] = total_wh.get(ts, 0.0) + wh

        # Compute total forecast
        result.total = self.compute_total_forecast(total_wh, now)

        return result

    async def _async_get_cloud_coverage(self) -> tuple[dict[str, float], bool]:
        """Get cloud coverage forecast from weather entity.

        Uses the weather.get_forecasts service to get hourly forecast data,
        which is the modern HA approach (the forecast attribute was deprecated).

        Returns:
            Tuple of (cloud_coverage_dict, weather_entity_available).
            Cloud coverage dict maps ISO timestamps to coverage percentage (0-100).

        """
        if not self._weather_entity:
            return {}, True

        state = self.hass.states.get(self._weather_entity)
        if state is None:
            LOGGER.warning("Weather entity %s not found", self._weather_entity)
            return {}, False

        forecast_data: dict[str, float] = {}

        # Try to get forecast via service call (modern HA approach)
        try:
            service_response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"type": "hourly"},
                target={"entity_id": self._weather_entity},
                blocking=True,
                return_response=True,
            )

            if service_response and self._weather_entity in service_response:
                forecasts = service_response[self._weather_entity].get("forecast", [])
                for item in forecasts:
                    dt_str = item.get("datetime")
                    cloud = item.get("cloud_coverage")
                    if dt_str is not None and cloud is not None:
                        forecast_data[dt_str] = float(cloud)

                if forecast_data:
                    return forecast_data, True
        except Exception:  # noqa: BLE001
            LOGGER.debug(
                "Failed to get hourly forecast from %s via service, "
                "trying daily forecast",
                self._weather_entity,
            )

        # Fallback: try daily forecast
        try:
            service_response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"type": "daily"},
                target={"entity_id": self._weather_entity},
                blocking=True,
                return_response=True,
            )

            if service_response and self._weather_entity in service_response:
                forecasts = service_response[self._weather_entity].get("forecast", [])
                for item in forecasts:
                    dt_str = item.get("datetime")
                    cloud = item.get("cloud_coverage")
                    if dt_str is not None and cloud is not None:
                        forecast_data[dt_str] = float(cloud)
        except Exception:  # noqa: BLE001
            LOGGER.debug(
                "Failed to get daily forecast from %s via service, "
                "falling back to state attributes",
                self._weather_entity,
            )

        # Final fallback: try deprecated forecast attribute
        if not forecast_data:
            forecasts = state.attributes.get("forecast", [])
            if forecasts:
                for item in forecasts:
                    dt_str = item.get("datetime")
                    cloud = item.get("cloud_coverage")
                    if dt_str is not None and cloud is not None:
                        forecast_data[dt_str] = float(cloud)

        return forecast_data, True

    def compute_forecast(
        self,
        pvgis_data: PVGISData,
        cloud_coverage: dict[str, float],
        now: datetime,
    ) -> SolarArrayForecast:
        """Compute forecast for a single array."""
        forecast = SolarArrayForecast()
        today = now.date()
        tomorrow = today + timedelta(days=1)

        # Build hourly forecast for 48 hours
        wh_hours: dict[str, float] = {}
        detailed: list[dict[str, Any]] = []
        today_total = 0.0
        today_remaining = 0.0
        tomorrow_total = 0.0
        current_hour_wh = 0.0
        next_hour_wh = 0.0
        now_power = 0.0
        peak_power_today = 0.0
        peak_time_today: datetime | None = None
        peak_power_tomorrow = 0.0
        peak_time_tomorrow: datetime | None = None

        for hour_offset in range(48):
            dt = now.replace(minute=0, second=0, microsecond=0) + timedelta(
                hours=hour_offset
            )
            # Get clear-sky power from PVGIS
            clear_sky_power = pvgis_data.get_power(dt.month, dt.day, dt.hour)

            # Apply cloud coverage factor
            cloud_factor = self.get_cloud_factor(dt, cloud_coverage)
            adjusted_power = clear_sky_power * cloud_factor

            # Energy in Wh for this hour
            ts_key = dt.isoformat()
            wh_hours[ts_key] = adjusted_power

            # Detailed forecast entry (Solcast-compatible format)
            detailed.append(
                {
                    "period_start": ts_key,
                    "pv_estimate": round(adjusted_power / 1000.0, 4),
                    "pv_estimate_clear_sky": round(clear_sky_power / 1000.0, 4),
                    "cloud_coverage": round(
                        (1.0 - cloud_factor)
                        / (CLOUD_FACTOR_CLEAR - CLOUD_FACTOR_OVERCAST)
                        * 100,
                        1,
                    )
                    if cloud_factor < CLOUD_FACTOR_CLEAR
                    else 0.0,
                }
            )

            if dt.date() == today:
                today_total += adjusted_power
                if dt >= now.replace(minute=0, second=0, microsecond=0):
                    today_remaining += adjusted_power
                if adjusted_power > peak_power_today:
                    peak_power_today = adjusted_power
                    peak_time_today = dt
            elif dt.date() == tomorrow:
                tomorrow_total += adjusted_power
                if adjusted_power > peak_power_tomorrow:
                    peak_power_tomorrow = adjusted_power
                    peak_time_tomorrow = dt

            if hour_offset == 0:
                now_power = adjusted_power
                current_hour_wh = adjusted_power
            elif hour_offset == 1:
                next_hour_wh = adjusted_power

        forecast.wh_hours = wh_hours
        forecast.detailed_forecast = detailed
        forecast.energy_production_today = round(today_total, 1)
        forecast.energy_production_today_remaining = round(today_remaining, 1)
        forecast.energy_production_tomorrow = round(tomorrow_total, 1)
        forecast.power_production_now = round(now_power, 1)
        forecast.energy_current_hour = round(current_hour_wh, 1)
        forecast.energy_next_hour = round(next_hour_wh, 1)
        forecast.power_highest_peak_time_today = peak_time_today
        forecast.power_highest_peak_time_tomorrow = peak_time_tomorrow
        forecast.peak_power_today = round(peak_power_today, 1)
        forecast.peak_power_tomorrow = round(peak_power_tomorrow, 1)

        return forecast

    def compute_total_forecast(
        self, total_wh: dict[str, float], now: datetime
    ) -> SolarArrayForecast:
        """Compute total forecast from accumulated wh_hours."""
        forecast = SolarArrayForecast()
        forecast.wh_hours = total_wh

        today = now.date()
        tomorrow = today + timedelta(days=1)
        today_total = 0.0
        today_remaining = 0.0
        tomorrow_total = 0.0
        now_hour = now.replace(minute=0, second=0, microsecond=0)
        peak_power_today = 0.0
        peak_time_today: datetime | None = None
        peak_power_tomorrow = 0.0
        peak_time_tomorrow: datetime | None = None

        detailed: list[dict[str, Any]] = []

        sorted_items = sorted(total_wh.items())
        for i, (ts, wh) in enumerate(sorted_items):
            dt = datetime.fromisoformat(ts)

            detailed.append(
                {
                    "period_start": ts,
                    "pv_estimate": round(wh / 1000.0, 4),
                }
            )

            if dt.date() == today:
                today_total += wh
                if dt >= now_hour:
                    today_remaining += wh
                if wh > peak_power_today:
                    peak_power_today = wh
                    peak_time_today = dt
            elif dt.date() == tomorrow:
                tomorrow_total += wh
                if wh > peak_power_tomorrow:
                    peak_power_tomorrow = wh
                    peak_time_tomorrow = dt

            if i == 0:
                forecast.power_production_now = round(wh, 1)
                forecast.energy_current_hour = round(wh, 1)
            elif i == 1:
                forecast.energy_next_hour = round(wh, 1)

        forecast.detailed_forecast = detailed
        forecast.energy_production_today = round(today_total, 1)
        forecast.energy_production_today_remaining = round(today_remaining, 1)
        forecast.energy_production_tomorrow = round(tomorrow_total, 1)
        forecast.power_highest_peak_time_today = peak_time_today
        forecast.power_highest_peak_time_tomorrow = peak_time_tomorrow
        forecast.peak_power_today = round(peak_power_today, 1)
        forecast.peak_power_tomorrow = round(peak_power_tomorrow, 1)

        return forecast

    @staticmethod
    def get_cloud_factor(dt: datetime, cloud_coverage: dict[str, float]) -> float:
        """Get cloud factor for a specific datetime.

        Maps cloud coverage percentage to a radiation factor.
        0% clouds = factor 1.0 (full clear sky radiation)
        100% clouds = factor 0.2 (20% of clear sky radiation)

        Args:
            dt: The datetime to get the factor for.
            cloud_coverage: Mapping of ISO timestamps to cloud coverage %.

        Returns:
            Multiplicative factor between CLOUD_FACTOR_OVERCAST and CLOUD_FACTOR_CLEAR.

        """
        if not cloud_coverage:
            return CLOUD_FACTOR_CLEAR

        # Find the closest forecast time
        best_match: float | None = None
        best_diff = timedelta.max

        for ts, coverage in cloud_coverage.items():
            forecast_dt = datetime.fromisoformat(ts)
            diff = abs(dt - forecast_dt)
            if diff < best_diff:
                best_diff = diff
                best_match = coverage

        if best_match is None or best_diff > timedelta(hours=3):
            return CLOUD_FACTOR_CLEAR

        # Linear interpolation: 0% cloud = 1.0, 100% cloud = 0.2
        cloud_pct = min(100, max(0, best_match)) / 100.0
        return CLOUD_FACTOR_CLEAR - cloud_pct * (
            CLOUD_FACTOR_CLEAR - CLOUD_FACTOR_OVERCAST
        )
