"""Tests for the PVGIS Solar Forecast config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

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
                CONF_MODULES_POWER: 5.0,
                CONF_LOSS: 14.0,
                CONF_MOUNTING_PLACE: "free",
                CONF_PV_TECH: "crystsi",
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
        },
    )

    # Add first array with add_another=True
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_NAME: "South Roof",
            CONF_DECLINATION: 35,
            CONF_AZIMUTH: 0,
            CONF_MODULES_POWER: 5.0,
            CONF_LOSS: 14.0,
            CONF_MOUNTING_PLACE: "free",
            CONF_PV_TECH: "crystsi",
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
                CONF_MODULES_POWER: 3.0,
                CONF_LOSS: 14.0,
                CONF_MOUNTING_PLACE: "building",
                CONF_PV_TECH: "cis",
                "add_another": False,
            },
        )

    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert len(result4["options"][CONF_ARRAYS]) == 2
    assert result4["options"][CONF_ARRAYS][0]["name"] == "South Roof"
    assert result4["options"][CONF_ARRAYS][1]["name"] == "East Wall"


@pytest.mark.asyncio
async def test_options_flow(
    hass: HomeAssistant,
    mock_pvgis_fetch: AsyncMock,
    enable_custom_integrations: None,
    mock_config_data: dict,
    mock_config_options: dict,
) -> None:
    """Test options flow for reconfiguring panels."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        options=mock_config_options,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Start options flow
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # Configure weather entity
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_WEATHER_ENTITY: "weather.new_weather"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "edit_array"

    # Edit existing array
    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        {
            CONF_NAME: "South Roof Updated",
            CONF_DECLINATION: 40,
            CONF_AZIMUTH: 10,
            CONF_MODULES_POWER: 6.0,
            CONF_LOSS: 12.0,
            CONF_MOUNTING_PLACE: "free",
            CONF_PV_TECH: "crystsi",
            "remove_array": False,
        },
    )

    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "add_array"

    # Finish without adding new array (add_another=False means don't save this)
    result4 = await hass.config_entries.options.async_configure(
        result3["flow_id"],
        {
            CONF_NAME: "Array 2",
            CONF_DECLINATION: 35,
            CONF_AZIMUTH: 0,
            CONF_MODULES_POWER: 1.0,
            CONF_LOSS: 14.0,
            CONF_MOUNTING_PLACE: "free",
            CONF_PV_TECH: "crystsi",
            "add_another": False,
        },
    )

    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert result4["data"][CONF_WEATHER_ENTITY] == "weather.new_weather"
    assert len(result4["data"][CONF_ARRAYS]) == 1
    assert result4["data"][CONF_ARRAYS][0]["name"] == "South Roof Updated"
    assert result4["data"][CONF_ARRAYS][0][CONF_MODULES_POWER] == 6.0
