"""PVGIS API client for fetching solar radiation data."""

from __future__ import annotations

from datetime import datetime
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

    def __init__(self, hourly_data: dict[tuple[int, int, int], float]) -> None:
        """Initialize PVGISData.

        Args:
            hourly_data: Mapping from (month, day, hour) to power output in watts.

        """
        self.hourly_data = hourly_data

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

    for item in hourly_items:
        try:
            time_str = item["time"]
            power = float(item["P"])
        except (KeyError, ValueError, TypeError) as err:
            LOGGER.warning("Skipping malformed PVGIS data item: %s (%s)", item, err)
            continue

        try:
            dt = datetime.strptime(time_str, "%Y%m%d:%H%M")
        except ValueError as err:
            LOGGER.warning("Skipping invalid time format: %s (%s)", time_str, err)
            continue

        key = (dt.month, dt.day, dt.hour)
        # Average if we have multiple years of data for the same time
        if key in hourly_data:
            hourly_data[key] = (hourly_data[key] + power) / 2
        else:
            hourly_data[key] = power

    return PVGISData(hourly_data)
