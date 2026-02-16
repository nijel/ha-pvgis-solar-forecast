"""Tests for the PVGIS Solar Forecast config flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from custom_components.pvgis_solar_forecast.const import (
    CONF_ARRAYS,
    CONF_AZIMUTH,
    CONF_DECLINATION,
    CONF_LOSS,
    CONF_MODULES_POWER,
    CONF_MOUNTING_PLACE,
    CONF_PV_TECH,
    CONF_WEATHER_ENTITY,
    DOMAIN,
)
from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.asyncio
async def test_user_step(hass: HomeAssistant, enable_custom_integrations: None) -> None:
    """Test the user step of the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_user_step_to_array(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test user step transitions to array step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "My Solar",
            CONF_LATITUDE: 45.0,
            CONF_LONGITUDE: 8.0,
            CONF_WEATHER_ENTITY: "weather.home",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "array"


@pytest.mark.asyncio
async def test_full_config_flow(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test the full config flow from user to array to creation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Step 1: User info
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "My Solar",
            CONF_LATITUDE: 45.0,
            CONF_LONGITUDE: 8.0,
            CONF_WEATHER_ENTITY: "weather.home",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "array"

    # Step 2: Add array (without add_another)
    with patch(
        "custom_components.pvgis_solar_forecast.async_setup_entry",
        return_value=True,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_NAME: "South Roof",
                CONF_DECLINATION: 35,
                CONF_AZIMUTH: 0,
                CONF_MODULES_POWER: 5000,
                CONF_LOSS: 14.0,
                CONF_MOUNTING_PLACE: "free",
                CONF_PV_TECH: "crystSi",
                "add_another": False,
            },
        )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "My Solar"
    assert result3["data"] == {
        CONF_LATITUDE: 45.0,
        CONF_LONGITUDE: 8.0,
    }
    assert result3["options"][CONF_WEATHER_ENTITY] == "weather.home"
    assert len(result3["options"][CONF_ARRAYS]) == 1
    assert result3["options"][CONF_ARRAYS][0]["name"] == "South Roof"


@pytest.mark.asyncio
async def test_multiple_arrays(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test adding multiple arrays."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "My Solar",
            CONF_LATITUDE: 45.0,
            CONF_LONGITUDE: 8.0,
            CONF_WEATHER_ENTITY: "",
        },
    )

    # Add first array with add_another=True
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_NAME: "South Roof",
            CONF_DECLINATION: 35,
            CONF_AZIMUTH: 0,
            CONF_MODULES_POWER: 5000,
            CONF_LOSS: 14.0,
            CONF_MOUNTING_PLACE: "free",
            CONF_PV_TECH: "crystSi",
            "add_another": True,
        },
    )

    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "array"

    # Add second array
    with patch(
        "custom_components.pvgis_solar_forecast.async_setup_entry",
        return_value=True,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {
                CONF_NAME: "East Wall",
                CONF_DECLINATION: 90,
                CONF_AZIMUTH: -90,
                CONF_MODULES_POWER: 3000,
                CONF_LOSS: 14.0,
                CONF_MOUNTING_PLACE: "building",
                CONF_PV_TECH: "CIS",
                "add_another": False,
            },
        )

    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert len(result4["options"][CONF_ARRAYS]) == 2
    assert result4["options"][CONF_ARRAYS][0]["name"] == "South Roof"
    assert result4["options"][CONF_ARRAYS][1]["name"] == "East Wall"
