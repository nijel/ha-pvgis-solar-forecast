"""Config flow for PVGIS Solar Forecast integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_ARRAYS,
    CONF_AZIMUTH,
    CONF_DECLINATION,
    CONF_LOSS,
    CONF_MODULES_POWER,
    CONF_MOUNTING_PLACE,
    CONF_PV_TECH,
    CONF_WEATHER_ENTITY,
    DEFAULT_AZIMUTH,
    DEFAULT_DECLINATION,
    DEFAULT_LOSS,
    DEFAULT_MOUNTING_PLACE,
    DEFAULT_PV_TECH,
    DOMAIN,
)


class PVGISSolarForecastConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PVGIS Solar Forecast."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._arrays: list[dict[str, Any]] = []
        self._name: str = ""
        self._latitude: float = 0.0
        self._longitude: float = 0.0
        self._weather_entity: str = ""

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> PVGISSolarForecastOptionsFlow:
        """Get the options flow for this handler."""
        return PVGISSolarForecastOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self._name = user_input[CONF_NAME]
            self._latitude = user_input[CONF_LATITUDE]
            self._longitude = user_input[CONF_LONGITUDE]
            self._weather_entity = user_input.get(CONF_WEATHER_ENTITY, "")
            return await self.async_step_array()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=self.hass.config.location_name
                    ): str,
                    vol.Required(
                        CONF_LATITUDE, default=self.hass.config.latitude
                    ): cv.latitude,
                    vol.Required(
                        CONF_LONGITUDE, default=self.hass.config.longitude
                    ): cv.longitude,
                    vol.Optional(CONF_WEATHER_ENTITY, default=""): str,
                }
            ),
        )

    async def async_step_array(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle adding a solar array."""
        if user_input is not None:
            self._arrays.append(
                {
                    "name": user_input[CONF_NAME],
                    CONF_DECLINATION: user_input[CONF_DECLINATION],
                    CONF_AZIMUTH: user_input[CONF_AZIMUTH],
                    CONF_MODULES_POWER: user_input[CONF_MODULES_POWER],
                    CONF_LOSS: user_input[CONF_LOSS],
                    CONF_MOUNTING_PLACE: user_input[CONF_MOUNTING_PLACE],
                    CONF_PV_TECH: user_input[CONF_PV_TECH],
                }
            )

            if user_input.get("add_another", False):
                return await self.async_step_array()

            return self.async_create_entry(
                title=self._name,
                data={
                    CONF_LATITUDE: self._latitude,
                    CONF_LONGITUDE: self._longitude,
                },
                options={
                    CONF_WEATHER_ENTITY: self._weather_entity,
                    CONF_ARRAYS: self._arrays,
                },
            )

        array_num = len(self._arrays) + 1

        return self.async_show_form(
            step_id="array",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=f"Array {array_num}"): str,
                    vol.Required(
                        CONF_DECLINATION, default=DEFAULT_DECLINATION
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=90)),
                    vol.Required(CONF_AZIMUTH, default=DEFAULT_AZIMUTH): vol.All(
                        vol.Coerce(int), vol.Range(min=-180, max=180)
                    ),
                    vol.Required(CONF_MODULES_POWER): vol.All(
                        vol.Coerce(int), vol.Range(min=1)
                    ),
                    vol.Required(CONF_LOSS, default=DEFAULT_LOSS): vol.All(
                        vol.Coerce(float), vol.Range(min=0, max=100)
                    ),
                    vol.Required(
                        CONF_MOUNTING_PLACE, default=DEFAULT_MOUNTING_PLACE
                    ): vol.In(["free", "building"]),
                    vol.Required(CONF_PV_TECH, default=DEFAULT_PV_TECH): vol.In(
                        ["crystSi", "CIS", "CdTe", "Unknown"]
                    ),
                    vol.Optional("add_another", default=False): bool,
                }
            ),
        )


class PVGISSolarForecastOptionsFlow(OptionsFlow):
    """Handle options flow for PVGIS Solar Forecast."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        weather_entity = self.config_entry.options.get(CONF_WEATHER_ENTITY, "")

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_WEATHER_ENTITY,
                        default=weather_entity,
                    ): str,
                }
            ),
        )
