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
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

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
    MOUNTING_PLACE_OPTIONS,
    PV_TECH_OPTIONS,
)

WEATHER_ENTITY_SELECTOR = EntitySelector(EntitySelectorConfig(domain="weather"))

MOUNTING_PLACE_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=MOUNTING_PLACE_OPTIONS,
        mode=SelectSelectorMode.DROPDOWN,
        translation_key="mounting_place",
    )
)

PV_TECH_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=PV_TECH_OPTIONS,
        mode=SelectSelectorMode.DROPDOWN,
        translation_key="pv_tech",
    )
)

POWER_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=0.01,
        step=0.01,
        mode=NumberSelectorMode.BOX,
        unit_of_measurement="kWp",
    )
)


def _get_array_schema(
    defaults: dict[str, Any] | None = None, array_num: int = 1
) -> vol.Schema:
    """Get the schema for a solar array configuration step."""
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=d.get(CONF_NAME, f"Array {array_num}")
            ): str,
            vol.Required(
                CONF_DECLINATION,
                default=d.get(CONF_DECLINATION, DEFAULT_DECLINATION),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=90)),
            vol.Required(
                CONF_AZIMUTH,
                default=d.get(CONF_AZIMUTH, DEFAULT_AZIMUTH),
            ): vol.All(vol.Coerce(int), vol.Range(min=-180, max=180)),
            vol.Required(
                CONF_MODULES_POWER,
                default=d.get(CONF_MODULES_POWER),
            ): POWER_SELECTOR,
            vol.Required(CONF_LOSS, default=d.get(CONF_LOSS, DEFAULT_LOSS)): vol.All(
                vol.Coerce(float), vol.Range(min=0, max=100)
            ),
            vol.Required(
                CONF_MOUNTING_PLACE,
                default=d.get(CONF_MOUNTING_PLACE, DEFAULT_MOUNTING_PLACE),
            ): MOUNTING_PLACE_SELECTOR,
            vol.Required(
                CONF_PV_TECH,
                default=d.get(CONF_PV_TECH, DEFAULT_PV_TECH),
            ): PV_TECH_SELECTOR,
            vol.Optional("add_another", default=False): bool,
        }
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
                    vol.Optional(
                        CONF_WEATHER_ENTITY,
                    ): WEATHER_ENTITY_SELECTOR,
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
            data_schema=_get_array_schema(array_num=array_num),
        )


class PVGISSolarForecastOptionsFlow(OptionsFlow):
    """Handle options flow for PVGIS Solar Forecast."""

    def __init__(self) -> None:
        """Initialize the options flow."""
        self._arrays: list[dict[str, Any]] = []
        self._weather_entity: str = ""
        self._editing_index: int = 0

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options - main menu."""
        if user_input is not None:
            self._weather_entity = user_input.get(CONF_WEATHER_ENTITY, "")
            # Start editing arrays from the beginning
            self._arrays = []
            existing_arrays = self.config_entry.options.get(CONF_ARRAYS, [])
            self._editing_index = 0
            if existing_arrays:
                return await self.async_step_edit_array()
            return await self.async_step_add_array()

        weather_entity = self.config_entry.options.get(CONF_WEATHER_ENTITY, "")

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_WEATHER_ENTITY,
                        description={"suggested_value": weather_entity},
                    ): WEATHER_ENTITY_SELECTOR,
                }
            ),
        )

    async def async_step_edit_array(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit an existing solar array."""
        existing_arrays = self.config_entry.options.get(CONF_ARRAYS, [])

        if user_input is not None:
            if not user_input.get("remove_array", False):
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

            self._editing_index += 1

            # More existing arrays to edit?
            if self._editing_index < len(existing_arrays):
                return await self.async_step_edit_array()

            # Offer to add new array
            return await self.async_step_add_array()

        # Show form pre-populated with existing array data
        current_array = existing_arrays[self._editing_index]
        array_num = self._editing_index + 1

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_NAME,
                    default=current_array.get(CONF_NAME, f"Array {array_num}"),
                ): str,
                vol.Required(
                    CONF_DECLINATION,
                    default=current_array.get(CONF_DECLINATION, DEFAULT_DECLINATION),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=90)),
                vol.Required(
                    CONF_AZIMUTH,
                    default=current_array.get(CONF_AZIMUTH, DEFAULT_AZIMUTH),
                ): vol.All(vol.Coerce(int), vol.Range(min=-180, max=180)),
                vol.Required(
                    CONF_MODULES_POWER,
                    default=current_array.get(CONF_MODULES_POWER),
                ): POWER_SELECTOR,
                vol.Required(
                    CONF_LOSS, default=current_array.get(CONF_LOSS, DEFAULT_LOSS)
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
                vol.Required(
                    CONF_MOUNTING_PLACE,
                    default=current_array.get(
                        CONF_MOUNTING_PLACE, DEFAULT_MOUNTING_PLACE
                    ),
                ): MOUNTING_PLACE_SELECTOR,
                vol.Required(
                    CONF_PV_TECH,
                    default=current_array.get(CONF_PV_TECH, DEFAULT_PV_TECH),
                ): PV_TECH_SELECTOR,
                vol.Optional("remove_array", default=False): bool,
            }
        )

        return self.async_show_form(
            step_id="edit_array",
            data_schema=schema,
            description_placeholders={
                "array_name": current_array.get(CONF_NAME, f"Array {array_num}")
            },
        )

    async def async_step_add_array(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Optionally add a new solar array."""
        if user_input is not None:
            if user_input.get("add_another", False):
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
                return await self.async_step_add_array()

            # Save all options without adding this array
            return self.async_create_entry(
                title="",
                data={
                    CONF_WEATHER_ENTITY: self._weather_entity,
                    CONF_ARRAYS: self._arrays,
                },
            )

        array_num = len(self._arrays) + 1

        return self.async_show_form(
            step_id="add_array",
            data_schema=_get_array_schema(array_num=array_num),
        )
