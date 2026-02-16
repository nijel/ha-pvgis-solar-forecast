"""Button platform for PVGIS Solar Forecast."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PVGISSolarForecastConfigEntry, PVGISSolarForecastCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PVGISSolarForecastConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PVGIS Solar Forecast buttons."""
    coordinator = entry.runtime_data

    # Create snow override buttons for each array
    entities: list[SnowOverrideButton] = []
    if coordinator.data and coordinator.data.arrays:
        for array_name in coordinator.data.arrays:
            # "Mark as Snow Covered" button
            entities.append(
                SnowOverrideButton(
                    entry_id=entry.entry_id,
                    coordinator=coordinator,
                    array_name=array_name,
                    snow_covered=True,
                )
            )
            # "Mark as Snow Free" button
            entities.append(
                SnowOverrideButton(
                    entry_id=entry.entry_id,
                    coordinator=coordinator,
                    array_name=array_name,
                    snow_covered=False,
                )
            )

    async_add_entities(entities)


class SnowOverrideButton(
    CoordinatorEntity[PVGISSolarForecastCoordinator], ButtonEntity
):
    """Button to override snow status on a solar array."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        *,
        entry_id: str,
        coordinator: PVGISSolarForecastCoordinator,
        array_name: str,
        snow_covered: bool,
    ) -> None:
        """Initialize snow override button."""
        super().__init__(coordinator=coordinator)
        self._array_name = array_name
        self._snow_covered = snow_covered

        action = "covered" if snow_covered else "clear"
        self._attr_unique_id = f"{entry_id}_{array_name}_snow_override_{action}"
        self._attr_name = f"Mark as snow {action} - {array_name}"
        self._attr_icon = "mdi:snowflake-alert" if snow_covered else "mdi:snowflake-off"

        device_id = f"{entry_id}_{array_name}"
        device_name = f"Solar forecast - {array_name}"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, device_id)},
            manufacturer="PVGIS",
            model="Solar Forecast",
            name=device_name,
            configuration_url="https://re.jrc.ec.europa.eu/pvg_tools/en/",
        )

    async def async_press(self) -> None:
        """Handle button press to override snow status."""
        # Set the override
        self.coordinator.set_snow_override(self._array_name, self._snow_covered)

        # Request immediate refresh to apply the override
        await self.coordinator.async_request_refresh()
