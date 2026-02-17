"""PVGIS API client for fetching solar radiation data."""

from __future__ import annotations

from datetime import datetime
import math
from typing import Any

import aiohttp

from .const import LOGGER, PVGIS_API_URL


class PVGISError(Exception):
    """Base exception for PVGIS API errors."""


class PVGISConnectionError(PVGISError):
    """Exception for connection errors."""


class PVGISApiError(PVGISError):
    """Exception for API errors."""


class PVGISData:
    """Parsed PVGIS hourly radiation data."""

    def __init__(
        self,
        hourly_data: dict[tuple[int, int, int], float],
        irradiance_data: dict[tuple[int, int, int], float] | None = None,
        sun_height_data: dict[tuple[int, int, int], float] | None = None,
    ) -> None:
        """Initialize PVGISData.

        Args:
            hourly_data: Mapping from (month, day, hour) to power output in watts.
            irradiance_data: Mapping from (month, day, hour) to irradiance in W/m².
            sun_height_data: Mapping from (month, day, hour) to sun height in degrees.

        """
        self.hourly_data = hourly_data
        self.irradiance_data = irradiance_data or {}
        self.sun_height_data = sun_height_data or {}

    def get_power(self, month: int, day: int, hour: int) -> float:
        """Get power output in watts for a given month, day, and hour.

        Args:
            month: Month (1-12).
            day: Day of month (1-31).
            hour: Hour of day (0-23).

        Returns:
            Power output in watts, or 0 if no data for this time.

        """
        return self.hourly_data.get((month, day, hour), 0.0)

    def get_irradiance(self, month: int, day: int, hour: int) -> float:
        """Get irradiance in W/m² for a given month, day, and hour.

        Args:
            month: Month (1-12).
            day: Day of month (1-31).
            hour: Hour of day (0-23).

        Returns:
            Irradiance in W/m², or 0 if no data for this time.

        """
        return self.irradiance_data.get((month, day, hour), 0.0)

    def get_sun_height(self, month: int, day: int, hour: int) -> float:
        """Get sun height in degrees for a given month, day, and hour.

        Args:
            month: Month (1-12).
            day: Day of month (1-31).
            hour: Hour of day (0-23).

        Returns:
            Sun height in degrees, or 0 if no data for this time.

        """
        return self.sun_height_data.get((month, day, hour), 0.0)

    def get_clearsky_power(self, month: int, day: int, hour: int) -> float:
        """Calculate clear-sky power for a given month, day, and hour.

        Uses the ratio method: P_clearsky = P_tmy × (G_clearsky / G_tmy)
        where G_clearsky is calculated from sun position and day of year.

        If irradiance or sun height data is not available, returns the
        TMY power value (fallback to old behavior).

        Args:
            month: Month (1-12).
            day: Day of month (1-31).
            hour: Hour of day (0-23).

        Returns:
            Clear-sky power output in watts.

        """
        tmy_power = self.get_power(month, day, hour)
        tmy_irradiance = self.get_irradiance(month, day, hour)
        sun_height = self.get_sun_height(month, day, hour)

        # If we don't have irradiance or sun height data, return TMY power
        if not tmy_irradiance or not sun_height:
            return tmy_power

        # Calculate day of year (approximate - good enough for this purpose)
        days_in_month = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        day_of_year = sum(days_in_month[:month]) + day

        # Calculate clear-sky irradiance
        clearsky_irradiance = calculate_clearsky_irradiance(sun_height, day_of_year)

        # Avoid division by zero
        if tmy_irradiance < 1.0:
            return tmy_power

        # Scale power by irradiance ratio
        scaling_factor = clearsky_irradiance / tmy_irradiance
        # Clamp to reasonable range (TMY shouldn't be higher than clear-sky)
        scaling_factor = max(1.0, min(scaling_factor, 2.0))

        return tmy_power * scaling_factor


async def fetch_pvgis_data(
    session: aiohttp.ClientSession,
    latitude: float,
    longitude: float,
    peakpower: float,
    loss: float,
    angle: float,
    aspect: float,
    mountingplace: str = "free",
    pvtechchoice: str = "crystSi",
) -> PVGISData:
    """Fetch hourly PV production data from PVGIS API.

    Args:
        session: aiohttp client session.
        latitude: Latitude in decimal degrees.
        longitude: Longitude in decimal degrees.
        peakpower: Nominal power of the PV system in kW.
        loss: System losses in percent.
        angle: Inclination angle from horizontal.
        aspect: Orientation angle, 0=south, 90=west, -90=east.
        mountingplace: "free" or "building".
        pvtechchoice: PV technology type.

    Returns:
        PVGISData with hourly power data.

    Raises:
        PVGISConnectionError: If the connection to PVGIS fails.
        PVGISApiError: If the API returns an error.

    """
    params: dict[str, Any] = {
        "lat": latitude,
        "lon": longitude,
        "outputformat": "json",
        "pvcalculation": 1,
        "peakpower": peakpower,
        "loss": loss,
        "angle": angle,
        "aspect": aspect,
        "mountingplace": mountingplace,
        "pvtechchoice": pvtechchoice,
    }

    try:
        async with session.get(PVGIS_API_URL, params=params) as response:
            if response.status != 200:
                text = await response.text()
                raise PVGISApiError(
                    f"PVGIS API returned status {response.status}: {text}"
                )
            data = await response.json(content_type=None)
    except aiohttp.ClientError as err:
        raise PVGISConnectionError(f"Failed to connect to PVGIS API: {err}") from err

    return _parse_pvgis_response(data)


def _parse_pvgis_response(data: dict[str, Any]) -> PVGISData:
    """Parse PVGIS JSON response into PVGISData.

    The response contains hourly data averaged over multiple years.
    The 'time' field is in format 'YYYYMMDD:HHMM' in UTC.
    The 'P' field is the PV system power output in watts.
    The 'G(i)' field is global irradiance on inclined plane in W/m².
    The 'H_sun' field is sun height in degrees.

    Args:
        data: Parsed JSON response from PVGIS API.

    Returns:
        PVGISData object.

    Raises:
        PVGISApiError: If the response format is unexpected.

    """
    try:
        hourly_items = data["outputs"]["hourly"]
    except (KeyError, TypeError) as err:
        raise PVGISApiError(f"Unexpected PVGIS response format: {err}") from err

    hourly_data: dict[tuple[int, int, int], float] = {}
    irradiance_data: dict[tuple[int, int, int], float] = {}
    sun_height_data: dict[tuple[int, int, int], float] = {}

    for item in hourly_items:
        try:
            time_str = item["time"]
            power = float(item["P"])
        except (KeyError, ValueError, TypeError) as err:
            LOGGER.warning("Skipping malformed PVGIS data item: %s (%s)", item, err)
            continue

        # Parse optional fields
        irradiance = item.get("G(i)", 0.0)
        sun_height = item.get("H_sun", 0.0)

        try:
            dt = datetime.strptime(time_str, "%Y%m%d:%H%M")
        except ValueError as err:
            LOGGER.warning("Skipping invalid time format: %s (%s)", time_str, err)
            continue

        key = (dt.month, dt.day, dt.hour)
        # Average if we have multiple years of data for the same time
        if key in hourly_data:
            hourly_data[key] = (hourly_data[key] + power) / 2
            if irradiance:
                irradiance_data[key] = (
                    irradiance_data.get(key, 0.0) + float(irradiance)
                ) / 2
            if sun_height:
                sun_height_data[key] = (
                    sun_height_data.get(key, 0.0) + float(sun_height)
                ) / 2
        else:
            hourly_data[key] = power
            if irradiance:
                irradiance_data[key] = float(irradiance)
            if sun_height:
                sun_height_data[key] = float(sun_height)

    return PVGISData(hourly_data, irradiance_data, sun_height_data)


def calculate_clearsky_irradiance(sun_height_deg: float, day_of_year: int) -> float:
    """Calculate clear-sky irradiance using a simplified Ineichen model.

    This model estimates the irradiance under clear-sky conditions based on
    sun position and Earth-Sun distance. It accounts for atmospheric
    transmission including Rayleigh scattering and aerosol absorption.

    Args:
        sun_height_deg: Sun height above horizon in degrees (0-90).
        day_of_year: Day of year (1-365).

    Returns:
        Clear-sky irradiance in W/m², or 0 if sun is below horizon.

    """
    if sun_height_deg <= 0:
        return 0.0

    # Solar constant (W/m²)
    solar_constant = 1361.0

    # Earth-Sun distance correction factor
    b = 2 * math.pi * (day_of_year - 1) / 365
    distance_factor = 1.00011 + 0.034221 * math.cos(b) + 0.00128 * math.sin(b)

    # Air mass calculation (simplified Kasten-Young formula)
    sun_height_rad = math.radians(sun_height_deg)
    zenith_deg = 90.0 - sun_height_deg
    air_mass = 1.0 / (
        math.cos(math.radians(zenith_deg))
        + 0.50572 * (96.07995 - zenith_deg) ** -1.6364
    )
    air_mass = max(1.0, min(air_mass, 40.0))  # Clamp to reasonable range

    # Atmospheric transmission (simplified for typical clear-sky)
    # This accounts for Rayleigh scattering and aerosol absorption
    # Using a typical turbidity factor
    transmission = 0.75 ** (air_mass**0.678)

    # Clear-sky irradiance
    clearsky = (
        solar_constant * distance_factor * math.sin(sun_height_rad) * transmission
    )

    return max(0.0, clearsky)
