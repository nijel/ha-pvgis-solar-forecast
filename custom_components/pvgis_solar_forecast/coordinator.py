"""DataUpdateCoordinator for the PVGIS Solar Forecast integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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
    CONF_WEATHER_ENTITY_SECONDARY,
    DEFAULT_LOSS,
    DEFAULT_MOUNTING_PLACE,
    DEFAULT_PV_TECH,
    DOMAIN,
    LOGGER,
    PV_TECH_API_MAP,
    SNOW_FACTOR_COVERED,
    SNOW_MELT_RADIATION_HOURS,
    SNOW_MELT_RADIATION_THRESHOLD,
    SNOW_SLIDE_INCLINATION,
    SNOW_TEMP_THRESHOLD,
)
from .pvgis import PVGISData, PVGISError, fetch_pvgis_data

type PVGISSolarForecastConfigEntry = ConfigEntry[PVGISSolarForecastCoordinator]

# PVGIS data doesn't change - refetch monthly
PVGIS_REFRESH_INTERVAL = timedelta(days=30)

# Forecast update interval - every 30 minutes to pick up weather changes
FORECAST_UPDATE_INTERVAL = timedelta(minutes=30)

# Shorter retry interval if weather entity is not available at startup
STARTUP_RETRY_INTERVAL = timedelta(minutes=1)

# Number of days to forecast (7 days)
FORECAST_DAYS = 7

# Number of days to keep historical forecasts
HISTORICAL_DAYS = 7


@dataclass
class SolarArrayData:
    """Data for a single solar array."""

    name: str
    pvgis_data: PVGISData | None = None
    last_pvgis_fetch: datetime | None = None


@dataclass
class ForecastSnapshot:
    """A snapshot of forecast data at a specific time."""

    timestamp: datetime
    wh_hours: dict[str, float]


@dataclass
class SolarForecastData:
    """Solar forecast data for all arrays."""

    arrays: dict[str, SolarArrayForecast] = field(default_factory=dict)
    total: SolarArrayForecast | None = None
    cloud_coverage_used: float | None = None
    weather_entity_available: bool = True
    clear_sky_power_now: float = 0.0
    clear_sky_energy_today: float = 0.0  # in kWh
    # Historical forecast snapshots: list of past forecasts
    historical_snapshots: list[ForecastSnapshot] = field(default_factory=list)
    # Snow detection: per-array manual overrides {array_name: snow_covered}
    snow_overrides: dict[str, bool | None] = field(default_factory=dict)


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
    # Energy production for days 0-6 (day 0 = today, day 1 = tomorrow, etc.)
    energy_production_days: dict[int, float] = field(default_factory=dict)
    power_production_now: float = 0.0
    energy_current_hour: float = 0.0
    energy_next_hour: float = 0.0
    power_highest_peak_time_today: datetime | None = None
    power_highest_peak_time_tomorrow: datetime | None = None
    peak_power_today: float = 0.0
    peak_power_tomorrow: float = 0.0
    # Per-array clear sky diagnostics
    clear_sky_power_now: float = 0.0
    clear_sky_energy_today: float = 0.0  # in kWh
    # Snow detection status
    snow_covered: bool = False


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
        self._weather_entity_secondary: str = entry.options.get(
            CONF_WEATHER_ENTITY_SECONDARY, ""
        )

    def update_config(self, entry: PVGISSolarForecastConfigEntry) -> None:
        """Update configuration from entry options (after reconfiguration)."""
        self._arrays_config = entry.options.get(CONF_ARRAYS, [])
        self._weather_entity = entry.options.get(CONF_WEATHER_ENTITY, "")
        self._weather_entity_secondary = entry.options.get(
            CONF_WEATHER_ENTITY_SECONDARY, ""
        )
        # Reset cached PVGIS data so arrays are re-fetched with new config
        self._arrays_data = {}

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
                        peakpower=array_config[CONF_MODULES_POWER],
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

        # Get weather data for snow detection
        (
            temperature_data,
            precipitation_data,
            snow_data,
            _,
        ) = await self._async_get_weather_data()

        # If weather entity is not available, schedule an early retry
        if not weather_available:
            self.update_interval = STARTUP_RETRY_INTERVAL
        else:
            self.update_interval = FORECAST_UPDATE_INTERVAL

        # Compute forecasts
        result = SolarForecastData()
        result.weather_entity_available = weather_available

        # Preserve snow overrides from previous state
        if self.data and self.data.snow_overrides:
            result.snow_overrides = self.data.snow_overrides.copy()

        total_wh: dict[str, float] = {}
        total_clear_sky_now = 0.0
        total_clear_sky_today = 0.0

        # Track current cloud coverage for diagnostics
        if cloud_coverage:
            now_key = now.replace(minute=0, second=0, microsecond=0).isoformat()
            if now_key in cloud_coverage:
                result.cloud_coverage_used = cloud_coverage[now_key]
            else:
                # Use first available cloud coverage value
                for cov in cloud_coverage.values():
                    result.cloud_coverage_used = cov
                    break

        for array_config in self._arrays_config:
            array_name = array_config["name"]
            array_data = self._arrays_data.get(array_name)
            if array_data is None or array_data.pvgis_data is None:
                continue

            # Detect snow on this array
            snow_covered = self._detect_snow_on_array(
                array_name,
                array_config,
                array_data.pvgis_data,
                temperature_data,
                precipitation_data,
                snow_data,
                now,
            )

            forecast = self.compute_forecast(
                array_data.pvgis_data,
                cloud_coverage,
                now,
                snow_covered,
                array_config,
                temperature_data,
                precipitation_data,
                snow_data,
            )

            # Set snow status on forecast
            forecast.snow_covered = snow_covered

            # Compute per-array clear sky diagnostics
            array_clear_sky_now = array_data.pvgis_data.get_power(
                now.month, now.day, now.hour
            )
            array_clear_sky_today = sum(
                array_data.pvgis_data.get_power(now.month, now.day, h)
                for h in range(24)
            )
            forecast.clear_sky_power_now = round(array_clear_sky_now)
            forecast.clear_sky_energy_today = round(array_clear_sky_today / 1000.0, 2)

            result.arrays[array_name] = forecast

            # Accumulate totals
            for ts, wh in forecast.wh_hours.items():
                total_wh[ts] = total_wh.get(ts, 0.0) + wh

            total_clear_sky_now += array_clear_sky_now
            total_clear_sky_today += array_clear_sky_today

        result.clear_sky_power_now = round(total_clear_sky_now)
        result.clear_sky_energy_today = round(total_clear_sky_today / 1000.0, 2)

        # Compute total forecast
        result.total = self.compute_total_forecast(total_wh, now)

        # Store historical forecast snapshot and clean up old ones
        if self.data:
            result.historical_snapshots = self._cleanup_historical_snapshots(
                self.data.historical_snapshots, now
            )

        # Add current forecast as a new snapshot
        result.historical_snapshots.append(
            ForecastSnapshot(timestamp=now, wh_hours=total_wh.copy())
        )

        return result

    async def _async_get_cloud_coverage_from_entity(
        self, entity_id: str
    ) -> dict[str, float]:
        """Get cloud coverage forecast from a single weather entity.

        Args:
            entity_id: The weather entity ID to fetch from.

        Returns:
            Cloud coverage dict mapping ISO timestamps to coverage percentage (0-100).
        """
        state = self.hass.states.get(entity_id)
        if state is None:
            LOGGER.debug(
                "Weather entity %s not available",
                entity_id,
            )
            return {}

        forecast_data: dict[str, float] = {}

        # Try to get forecast via service call (modern HA approach)
        try:
            service_response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"type": "hourly"},
                target={"entity_id": entity_id},
                blocking=True,
                return_response=True,
            )

            if service_response and entity_id in service_response:
                forecasts = service_response[entity_id].get("forecast", [])
                for item in forecasts:
                    dt_str = item.get("datetime")
                    cloud = item.get("cloud_coverage")
                    if dt_str is not None and cloud is not None:
                        forecast_data[dt_str] = float(cloud)

                if forecast_data:
                    return forecast_data
        except HomeAssistantError:
            LOGGER.debug(
                "Failed to get hourly forecast from %s via service, "
                "trying daily forecast",
                entity_id,
            )

        # Fallback: try daily forecast
        try:
            service_response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"type": "daily"},
                target={"entity_id": entity_id},
                blocking=True,
                return_response=True,
            )

            if service_response and entity_id in service_response:
                forecasts = service_response[entity_id].get("forecast", [])
                for item in forecasts:
                    dt_str = item.get("datetime")
                    cloud = item.get("cloud_coverage")
                    if dt_str is not None and cloud is not None:
                        forecast_data[dt_str] = float(cloud)
        except HomeAssistantError:
            LOGGER.debug(
                "Failed to get daily forecast from %s via service, "
                "falling back to state attributes",
                entity_id,
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

        return forecast_data

    async def _async_get_cloud_coverage(self) -> tuple[dict[str, float], bool]:
        """Get cloud coverage forecast from weather entities.

        Uses the weather.get_forecasts service to get hourly forecast data,
        which is the modern HA approach (the forecast attribute was deprecated).

        Fetches from primary weather entity, and if secondary is configured,
        also fetches from it and merges the data (primary takes precedence).

        Gracefully handles the case where the weather entity is not yet
        available (e.g., during HA startup), returning clear-sky defaults.

        Returns:
            Tuple of (cloud_coverage_dict, weather_entity_available).
            Cloud coverage dict maps ISO timestamps to coverage percentage (0-100).

        """
        if not self._weather_entity:
            return {}, True

        state = self.hass.states.get(self._weather_entity)
        if state is None:
            LOGGER.debug(
                "Weather entity %s not available yet, using clear-sky forecast",
                self._weather_entity,
            )
            return {}, False

        # Get forecast from primary weather entity
        forecast_data = await self._async_get_cloud_coverage_from_entity(
            self._weather_entity
        )

        # If secondary weather entity is configured, fetch and merge
        if self._weather_entity_secondary:
            secondary_forecast = await self._async_get_cloud_coverage_from_entity(
                self._weather_entity_secondary
            )

            # Merge: add timestamps from secondary that are not in primary
            for ts, coverage in secondary_forecast.items():
                if ts not in forecast_data:
                    forecast_data[ts] = coverage

            if secondary_forecast:
                LOGGER.debug(
                    "Merged cloud coverage: %d timestamps from primary, %d from secondary",
                    len([ts for ts in forecast_data if ts not in secondary_forecast]),
                    len([ts for ts in forecast_data if ts in secondary_forecast]),
                )

        return forecast_data, True

    async def _async_get_weather_data(
        self,
    ) -> tuple[dict[str, float], dict[str, float], dict[str, float], bool]:
        """Get temperature, precipitation, and snow data from weather entity.

        Returns:
            Tuple of (temperature_dict, precipitation_dict, snow_dict, available).
            Temperature in °C, precipitation/snow in mm.
        """
        if not self._weather_entity:
            return {}, {}, {}, True

        state = self.hass.states.get(self._weather_entity)
        if state is None:
            LOGGER.debug(
                "Weather entity %s not available for snow detection",
                self._weather_entity,
            )
            return {}, {}, {}, False

        temperature_data: dict[str, float] = {}
        precipitation_data: dict[str, float] = {}
        snow_data: dict[str, float] = {}

        # Try to get forecast via service call
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
                    if dt_str is None:
                        continue

                    temp = item.get("temperature")
                    if temp is not None:
                        temperature_data[dt_str] = float(temp)

                    precip = item.get("precipitation")
                    if precip is not None:
                        precipitation_data[dt_str] = float(precip)

                    # Some weather providers have explicit snow field
                    snow = item.get("snow")
                    if snow is not None:
                        snow_data[dt_str] = float(snow)

                if temperature_data:
                    return temperature_data, precipitation_data, snow_data, True
        except HomeAssistantError:
            LOGGER.debug(
                "Failed to get weather data from %s for snow detection",
                self._weather_entity,
            )

        return {}, {}, {}, True

    def _detect_snow_on_array(
        self,
        array_name: str,
        array_config: dict[str, Any],
        pvgis_data: PVGISData,
        temperature_data: dict[str, float],
        precipitation_data: dict[str, float],
        snow_data: dict[str, float],
        now: datetime,
    ) -> bool:
        """Detect if array is likely covered by snow.

        Detection logic:
        1. Check manual override first
        2. Look for recent snow in forecast (last 24 hours)
        3. Check if temperature is below threshold
        4. Check if there has been enough radiation to melt snow
        5. Consider panel inclination (steeper angles shed snow better)

        Args:
            array_name: Name of the array.
            array_config: Array configuration dict.
            pvgis_data: PVGIS data for the array.
            temperature_data: Temperature forecast dict.
            precipitation_data: Precipitation forecast dict.
            snow_data: Snow forecast dict (if available).
            now: Current datetime.

        Returns:
            True if array is likely covered by snow.
        """
        # Check for manual override
        if self.data and array_name in self.data.snow_overrides:
            override = self.data.snow_overrides[array_name]
            if override is not None:
                return override

        # Get panel inclination (declination)
        inclination = array_config.get(CONF_DECLINATION, 0)

        # Look back 24 hours for snow events
        lookback_hours = 24
        recent_snow = False

        for hour_offset in range(-lookback_hours, 1):
            dt = now.replace(minute=0, second=0, microsecond=0) + timedelta(
                hours=hour_offset
            )
            dt_str = dt.isoformat()

            # Check if there was snow
            if dt_str in snow_data and snow_data[dt_str] > 0:
                recent_snow = True

            # Check for precipitation + cold temperature (implicit snow)
            if dt_str in temperature_data:
                temp = temperature_data[dt_str]
                if temp < SNOW_TEMP_THRESHOLD:
                    if dt_str in precipitation_data and precipitation_data[dt_str] > 0:
                        recent_snow = True

        # If no recent snow, panels are clear
        if not recent_snow:
            return False

        # Snow detected - check if it has melted
        # Calculate cumulative radiation since snow event
        cumulative_radiation_hours = 0.0

        for hour_offset in range(-lookback_hours, 1):
            dt = now.replace(minute=0, second=0, microsecond=0) + timedelta(
                hours=hour_offset
            )
            dt_str = dt.isoformat()

            # Check temperature - snow doesn't melt if too cold
            if dt_str in temperature_data:
                temp = temperature_data[dt_str]
                if temp < SNOW_TEMP_THRESHOLD:
                    # Reset counter when cold
                    cumulative_radiation_hours = 0.0
                    continue

            # Get radiation from PVGIS data
            clear_sky_power = pvgis_data.get_power(dt.month, dt.day, dt.hour)

            # Estimate radiation (W/m²) from power
            # Rough approximation: panel power ~= radiation * area * efficiency
            # Assuming ~200 W/m² per kW of panel power in good conditions
            estimated_radiation = (
                clear_sky_power / (array_config[CONF_MODULES_POWER] * 1000) * 200
                if array_config[CONF_MODULES_POWER] > 0
                else 0
            )

            # Count hours with significant radiation
            if estimated_radiation > SNOW_MELT_RADIATION_THRESHOLD:
                cumulative_radiation_hours += 1.0

        # Adjust melt threshold based on inclination
        # Steeper panels shed snow more easily
        melt_hours_needed = SNOW_MELT_RADIATION_HOURS
        if inclination > SNOW_SLIDE_INCLINATION:
            # Reduce needed melt time for steep panels
            angle_factor = (inclination - SNOW_SLIDE_INCLINATION) / 60.0
            melt_hours_needed *= max(0.5, 1.0 - angle_factor)

        # If enough radiation to melt snow, panels are clear
        if cumulative_radiation_hours >= melt_hours_needed:
            return False

        # Snow still present
        return True

    def _predict_snow_for_hour(
        self,
        array_config: dict[str, Any],
        pvgis_data: PVGISData,
        temperature_data: dict[str, float],
        precipitation_data: dict[str, float],
        snow_data: dict[str, float],
        target_dt: datetime,
    ) -> bool:
        """Predict if array will be covered by snow at a specific future hour.

        Similar to _detect_snow_on_array but for future forecast times.

        Args:
            array_config: Array configuration dict.
            pvgis_data: PVGIS data for the array.
            temperature_data: Temperature forecast dict.
            precipitation_data: Precipitation forecast dict.
            snow_data: Snow forecast dict (if available).
            target_dt: Target datetime to predict snow for.

        Returns:
            True if array is predicted to be covered by snow at target_dt.
        """
        # Get panel inclination (declination)
        inclination = array_config.get(CONF_DECLINATION, 0)

        # Look back from target time for snow events
        lookback_hours = 24
        recent_snow = False

        # Check if snow is predicted at target time or recently before
        for hour_offset in range(-lookback_hours, 1):
            dt = target_dt + timedelta(hours=hour_offset)
            dt_str = dt.isoformat()

            # Check if there will be snow
            if dt_str in snow_data and snow_data[dt_str] > 0:
                recent_snow = True

            # Check for precipitation + cold temperature (implicit snow)
            if dt_str in temperature_data:
                temp = temperature_data[dt_str]
                if temp < SNOW_TEMP_THRESHOLD:
                    if dt_str in precipitation_data and precipitation_data[dt_str] > 0:
                        recent_snow = True

        # If no snow predicted, panels will be clear
        if not recent_snow:
            return False

        # Snow predicted - check if it will have melted by target time
        # Calculate cumulative radiation from snow event to target time
        cumulative_radiation_hours = 0.0

        for hour_offset in range(-lookback_hours, 1):
            dt = target_dt + timedelta(hours=hour_offset)
            dt_str = dt.isoformat()

            # Check temperature - snow doesn't melt if too cold
            if dt_str in temperature_data:
                temp = temperature_data[dt_str]
                if temp < SNOW_TEMP_THRESHOLD:
                    # Reset counter when cold
                    cumulative_radiation_hours = 0.0
                    continue

            # Get radiation from PVGIS data
            clear_sky_power = pvgis_data.get_power(dt.month, dt.day, dt.hour)

            # Estimate radiation (W/m²) from power
            estimated_radiation = (
                clear_sky_power / (array_config[CONF_MODULES_POWER] * 1000) * 200
                if array_config[CONF_MODULES_POWER] > 0
                else 0
            )

            # Count hours with significant radiation
            if estimated_radiation > SNOW_MELT_RADIATION_THRESHOLD:
                cumulative_radiation_hours += 1.0

        # Adjust melt threshold based on inclination
        melt_hours_needed = SNOW_MELT_RADIATION_HOURS
        if inclination > SNOW_SLIDE_INCLINATION:
            angle_factor = (inclination - SNOW_SLIDE_INCLINATION) / 60.0
            melt_hours_needed *= max(0.5, 1.0 - angle_factor)

        # If enough radiation to melt snow, panels will be clear
        if cumulative_radiation_hours >= melt_hours_needed:
            return False

        # Snow still predicted to be present
        return True

    def set_snow_override(self, array_name: str, snow_covered: bool | None) -> None:
        """Set manual override for snow coverage on an array.

        Args:
            array_name: Name of the array.
            snow_covered: True if covered, False if clear, None to remove override.
        """
        if self.data is None:
            return

        if snow_covered is None:
            # Remove override
            self.data.snow_overrides.pop(array_name, None)
        else:
            # Set override
            self.data.snow_overrides[array_name] = snow_covered

        LOGGER.info(
            "Snow override set for %s: %s",
            array_name,
            "covered" if snow_covered else "clear" if snow_covered is False else "auto",
        )

    def compute_forecast(
        self,
        pvgis_data: PVGISData,
        cloud_coverage: dict[str, float],
        now: datetime,
        snow_covered: bool = False,
        array_config: dict[str, Any] | None = None,
        temperature_data: dict[str, float] | None = None,
        precipitation_data: dict[str, float] | None = None,
        snow_data: dict[str, float] | None = None,
    ) -> SolarArrayForecast:
        """Compute forecast for a single array."""
        forecast = SolarArrayForecast()
        today = now.date()
        tomorrow = today + timedelta(days=1)

        # Build hourly forecast for 7 days
        total_hours = FORECAST_DAYS * 24
        wh_hours: dict[str, float] = {}
        detailed: list[dict[str, Any]] = []
        today_total = 0.0
        today_remaining = 0.0
        tomorrow_total = 0.0
        day_totals: dict[int, float] = {}
        current_hour_wh = 0.0
        next_hour_wh = 0.0
        now_power = 0.0
        peak_power_today = 0.0
        peak_time_today: datetime | None = None
        peak_power_tomorrow = 0.0
        peak_time_tomorrow: datetime | None = None

        for hour_offset in range(total_hours):
            dt = now.replace(minute=0, second=0, microsecond=0) + timedelta(
                hours=hour_offset
            )
            # Get clear-sky power from PVGIS
            clear_sky_power = pvgis_data.get_power(dt.month, dt.day, dt.hour)

            # Apply cloud coverage factor
            cloud_factor = self.get_cloud_factor(dt, cloud_coverage)
            adjusted_power = clear_sky_power * cloud_factor

            # Predict snow for this specific hour if weather data available
            hour_snow_covered = snow_covered  # Default to current state
            if (
                array_config is not None
                and temperature_data is not None
                and precipitation_data is not None
                and snow_data is not None
                and hour_offset > 0  # Only predict for future hours
            ):
                hour_snow_covered = self._predict_snow_for_hour(
                    array_config,
                    pvgis_data,
                    temperature_data,
                    precipitation_data,
                    snow_data,
                    dt,
                )

            # Apply snow factor if snow is predicted for this hour
            snow_factor = 1.0
            if hour_snow_covered:
                snow_factor = SNOW_FACTOR_COVERED
                adjusted_power *= snow_factor

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
                    "snow_covered": hour_snow_covered,
                }
            )

            # Track per-day totals (day 0 = today)
            day_offset = (dt.date() - today).days
            if 0 <= day_offset < FORECAST_DAYS:
                day_totals[day_offset] = (
                    day_totals.get(day_offset, 0.0) + adjusted_power
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
        forecast.energy_production_days = {
            d: round(v, 1) for d, v in day_totals.items()
        }
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
        day_totals: dict[int, float] = {}
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

            # Track per-day totals
            day_offset = (dt.date() - today).days
            if 0 <= day_offset < FORECAST_DAYS:
                day_totals[day_offset] = day_totals.get(day_offset, 0.0) + wh

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
        forecast.energy_production_days = {
            d: round(v, 1) for d, v in day_totals.items()
        }
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
            dt: The datetime to get the factor for (must be timezone-aware).
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
            # Ensure forecast_dt has the same timezone awareness as dt.
            # dt is always timezone-aware (from datetime.now().astimezone()).
            # Naive ISO timestamps from weather providers are assumed to represent
            # the same timezone as dt (typically the user's local timezone).
            if forecast_dt.tzinfo is None and dt.tzinfo is not None:
                forecast_dt = forecast_dt.replace(tzinfo=dt.tzinfo)
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

    @staticmethod
    def _cleanup_historical_snapshots(
        snapshots: list[ForecastSnapshot], now: datetime
    ) -> list[ForecastSnapshot]:
        """Clean up historical snapshots older than HISTORICAL_DAYS.

        Args:
            snapshots: List of historical forecast snapshots.
            now: Current datetime.

        Returns:
            Filtered list of snapshots within the retention period.
        """
        cutoff_time = now - timedelta(days=HISTORICAL_DAYS)
        return [s for s in snapshots if s.timestamp >= cutoff_time]
