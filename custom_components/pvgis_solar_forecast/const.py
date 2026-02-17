"""Constants for the PVGIS Solar Forecast integration."""

from __future__ import annotations

import logging

DOMAIN = "pvgis_solar_forecast"
LOGGER = logging.getLogger(__package__)

PVGIS_API_URL = "https://re.jrc.ec.europa.eu/api/seriescalc"

CONF_ARRAYS = "arrays"
CONF_ARRAY_NAME = "name"
CONF_DECLINATION = "declination"
CONF_AZIMUTH = "azimuth"
CONF_MODULES_POWER = "modules_power"  # stored as kWp
CONF_LOSS = "loss"
CONF_WEATHER_ENTITY = "weather_entity"
CONF_WEATHER_ENTITY_SECONDARY = "weather_entity_secondary"
CONF_MOUNTING_PLACE = "mounting_place"
CONF_PV_TECH = "pv_tech"

# Default values
DEFAULT_DECLINATION = 35
DEFAULT_AZIMUTH = 0
DEFAULT_LOSS = 14.0
DEFAULT_MOUNTING_PLACE = "free"
DEFAULT_PV_TECH = "crystsi"

# PV tech option keys (lowercase for HA translation validation)
# and their corresponding PVGIS API values
PV_TECH_OPTIONS = ["crystsi", "cis", "cdte", "unknown"]
PV_TECH_API_MAP = {
    "crystsi": "crystSi",
    "cis": "CIS",
    "cdte": "CdTe",
    "unknown": "Unknown",
}

# Mounting place options
MOUNTING_PLACE_OPTIONS = ["free", "building"]

# Cloud coverage to radiation factor mapping
# Maps cloud coverage percentage to a multiplicative factor for clear-sky radiation
CLOUD_FACTOR_CLEAR = 1.0  # 0% clouds
CLOUD_FACTOR_OVERCAST = 0.2  # 100% clouds

# Snow detection constants
# Temperature threshold (°C) - snow persists below this
SNOW_TEMP_THRESHOLD = 2.0
# Hours of sunlight (radiation) needed to melt snow on panels
SNOW_MELT_RADIATION_HOURS = 4.0
# Radiation threshold (W/m²) to consider as "sunny" for melting
SNOW_MELT_RADIATION_THRESHOLD = 300.0
# Snow factor for covered panels (heavy production reduction)
SNOW_FACTOR_COVERED = 0.05  # 5% of normal production when snow covered
# Inclination threshold (degrees) - higher tilt helps snow slide off
SNOW_SLIDE_INCLINATION = 30.0
